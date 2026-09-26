#!/usr/bin/env python3
"""Code patch for Snatcher PCE: letter-pair cells (tools/sncells.py) and dictionary tokens (tools/sndict.py).

  snhack.py apply iso_in iso_out      (same offsets in both data tracks)
  snhack.py font work/font.png        (preview of the font)

Only RAM banks $68-$6A are never a load target, and their free tails are small, so the patch is split:

  $6A (dialogue bank, ISO 0xF000) tail $7F50-$7FFF   trampolines only. Two hooks:
        $648C  jsr $69C2  ->  jsr GLYPH_HOOK    SJIS lead $89-$97 = letter-pair cell, drawn by us
        $7272  (entry of decode_next_pair)  ->  jmp DEC_HOOK
                                                 lead $88/$98 = dictionary token, expanded into cells
  $82 tail +$1800-$1FFF (ISO 0x1C800, sector 57)   one 2 KB block, seen at $9800: magic word "EN", the
        dispatcher and all the code, the Huffman tables and the dictionary. Loaded at boot with the clip
        tables -- but the cutscene / act loads overwrite it (the freeze at the end of the intro).
  $68 $5BB3-$5BFF (ISO 0xCBB3)                      the resident part: loader_hook. Every load that wipes the
        block is made by the game's scene_loader_main, so its success path ($54F1 stz $3F21) calls
        loader_hook, which re-reads sector 57 right there if the magic word is gone -- the drive has
        just finished the loader's read and no CD audio has started. (Re-reading at the next English
        line instead would stop a CD-DA cutscene that is playing by then.)
        Only these 77 bytes of the $68 tail are safe: $5C00-$5FFF is the game's table of 10-byte
        animation records, which reached $5D0D in Harry's blaster scene. Code placed at $5BB3 and later
        at $5CE2 was overwritten by it -- the second time was the crash after the blaster.
  $69 tail +$1CD2-$1FFF (ISO 0xD000 + $1CD2)       the 6x9 font.

A trampoline maps $82 -> MPR4 ($8000) and $69 -> MPR5 ($A000) with interrupts off, calls the dispatcher
at $9802 with the function number in X, and restores both.
(The engine bank's $5C40 tail is $FF on disc but work RAM at runtime; code put there was overwritten.
 tools/snhack_v1.py is the first, glyph-only version of this patch.)
"""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sncells  # noqa: E402

DIALOGUE_ISO = 0xF000
GLYPH_SITE, GLYPH_ORIG = 0x648C, bytes.fromhex("20c269")            # jsr $69C2
DEC_SITE, DEC_ORIG = 0x7272, bytes.fromhex("ad0b36f0034c6673")      # lda $360B ; beq +3 ; jmp $7366
TRAMP_ORG, TRAMP_END = 0x7F50, 0x8000
RES_ORG, RES_END, RES_ISO = 0x5BB3, 0x5C00, 0xCBB3                 # bank $68 (ISO 0xB000), always at MPR2
DATA_BANK, DATA_ISO, DATA_ORG, DATA_END = 0x82, 0x1C800, 0x9800, 0xA000
DATA_SECTOR = DATA_ISO // 2048                                       # 57: the BIOS counts from the booted track
MAGIC = b"EN"
FONT_BANK, FONT_ISO, FONT_ORG, FONT_END = 0x69, 0xD000 + 0x1CD2, 0xA000 + 0x1CD2, 0xC000
ROWS, TOP, SRC_ROW = 9, 2, 2
FONT_TTF, FONT_SIZE = "/System/Library/Fonts/Monaco.ttf", 9


def font_bytes():
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(FONT_TTF, FONT_SIZE)
    out = bytearray()
    for ch in sncells.GLYPHS:
        img = Image.new("L", (6, 12), 0)
        d = ImageDraw.Draw(img)
        d.fontmode = "1"
        d.text((0, 0), ch, font=f, fill=255)
        rows = []
        for y in range(SRC_ROW, SRC_ROW + ROWS):
            b = 0
            for x in range(6):
                if img.getpixel((x, y)):
                    b |= 0x80 >> x
            rows.append(b)
        if ch == "I":                                   # Monaco's bare stem leaves a hole in the pair ("I tems"): add serifs
            used = [k for k, r in enumerate(rows) if r]
            rows = [0x70 if k in (used[0], used[-1]) else (0x20 if used[0] < k < used[-1] else 0) for k in range(ROWS)]
        out += bytes(rows)
    return bytes(out)


class Asm:
    def __init__(self, org):
        self.org, self.out, self.labels, self.fix = org, bytearray(), {}, []

    def label(self, n):
        self.labels[n] = self.org + len(self.out)

    def b(self, *d):
        self.out += bytes(d)

    def w(self, op, addr, add=0):
        self.out.append(op)
        if isinstance(addr, str):
            self.fix.append((len(self.out), addr, "abs", add))
            addr = 0
        else:
            addr += add
        self.out += (addr & 0xFFFF).to_bytes(2, "little")

    def dw(self, label):
        self.fix.append((len(self.out), label, "abs", 0))
        self.out += b"\0\0"

    def imm(self, op, label, part):                                 # lda #<label / #>label
        self.out.append(op)
        self.fix.append((len(self.out), label, part, 0))
        self.out.append(0)

    def r(self, op, label):
        self.out.append(op)
        self.fix.append((len(self.out), label, "rel", 0))
        self.out.append(0)

    def link(self):
        for pos, name, kind, add in self.fix:
            t = self.labels[name] + add
            if kind == "abs":
                self.out[pos:pos + 2] = t.to_bytes(2, "little")
            elif kind == "lo":
                self.out[pos] = t & 0xFF
            elif kind == "hi":
                self.out[pos] = t >> 8
            else:
                d = t - (self.org + pos + 1)
                assert -128 <= d <= 127, name
                self.out[pos] = d & 0xFF
        return bytes(self.out)


def build_trampolines(entry):
    a = Asm(TRAMP_ORG)
    a.label("glyph_hook")
    a.b(0xA5, 0xF9, 0xC9, 0x88); a.r(0x90, "g_orig")               # lda <$F9 ; < $88: not a cell
    a.b(0xC9, 0xA0); a.r(0x90, "g_cell")                           # $88-$9F: cell
    a.b(0xC9, 0xE0); a.r(0x90, "g_orig"); a.b(0xC9, 0xF8); a.r(0x90, "g_cell")    # $E0-$F7: cell
    a.label("g_orig"); a.w(0x4C, 0x69C2)
    a.label("g_cell"); a.b(0xA2, 0x00); a.w(0x20, "mapcall"); a.b(0x62, 0x60)     # ldx #0 ; jsr mapcall ; cla ; rts
    # decode_next_pair: English messages start with $1F $FF and are decoded by us, everything else as before
    a.label("dec_hook")
    # After the end of an English message the game calls this once more to "advance to the next
    # sentence". Without this guard the decoder would keep pulling bits from a finished stream and
    # never return - the game then waits forever with an empty text box.
    a.w(0xAD, 0x3607); a.r(0xF0, "d_live")                         # lda $3607 ; beq live
    a.w(0xAD, 0x360C); a.r(0x10, "d_orig")                         # bpl: not ours
    a.w(0x9C, 0x360C); a.b(0x60)                                   # stz $360C ; rts
    a.label("d_live")
    a.w(0xAD, 0x360C); a.r(0x30, "d_eng"); a.r(0xD0, "d_orig")     # bmi: English in progress ; bne: Japanese mid-byte
    a.w(0x20, "peek"); a.b(0xC9, 0x1F); a.r(0xD0, "d_orig")
    a.w(0x20, "skip"); a.w(0x20, "peek"); a.b(0xC9, 0xFF); a.r(0xF0, "d_start")
    a.b(0xA5, 0xE0); a.r(0xD0, "d_undo"); a.b(0xC6, 0xE1)          # not the marker: step back one byte
    a.label("d_undo"); a.b(0xC6, 0xE0); a.r(0x80, "d_orig")
    a.label("d_start")
    a.w(0x20, "skip"); a.b(0xA9, 0x80); a.w(0x8D, 0x360C)
    a.b(0xDA, 0xA2, 0x04); a.w(0x20, "mapcall"); a.b(0xFA)         # phx ; ldx #4 (init) ; plx
    a.label("d_eng"); a.b(0xDA)                                     # phx
    a.label("d_loop"); a.b(0xA2, 0x02); a.w(0x20, "mapcall")       # step: X=1 -> wants the next byte in $360F
    a.b(0xE0, 0x01); a.r(0xD0, "d_done")
    a.w(0x20, "peek"); a.w(0x8D, 0x360F); a.w(0x20, "skip"); a.r(0x80, "d_loop")
    a.label("d_done"); a.b(0xFA, 0x60)                              # plx ; rts
    a.label("d_orig")                                               # the instructions overwritten at $7272
    a.w(0xAD, 0x360B); a.r(0xF0, "o_np"); a.w(0x4C, 0x7366)
    a.label("o_np"); a.w(0x4C, 0x727A)
    a.label("peek")                                                 # A = byte at the text pointer, as the game fetches it
    a.b(0x64, 0x92, 0xA5, 0xE0, 0x85, 0x90, 0xA5, 0xE1, 0x85, 0x91); a.w(0x4C, 0x5341)
    a.label("skip"); a.b(0xE6, 0xE0); a.r(0xD0, "sk1"); a.b(0xE6, 0xE1)
    a.label("sk1"); a.b(0x60)
    a.label("mapcall")
    # No sei here. The game's interrupt handler saves MPR3-6 on entry and restores them on exit
    # (engine.asm vblank_irq_handler / vbi_restore_exit), so our mapping survives an interrupt. What
    # a sei did was hold off the raster interrupt for a whole glyph, and on the videophone -- where the
    # portrait sits below a mid-frame split -- that showed as the portrait flickering while Napoleon
    # spoke and while menus redrew (hardware, 22 Sep).
    import os
    sei = os.environ.get("SNATCHER_SEI") == "1"                     # hardware A/B only: the pre-22-Sep behaviour
    a.b(0x5A)                                                       # phy
    if sei:
        a.b(0x08, 0x78)                                             # php ; sei
    a.b(0x43, 0x10, 0x48, 0x43, 0x20, 0x48)                         # tma #$10 ; pha ; tma #$20 ; pha
    a.b(0xA9, DATA_BANK, 0x53, 0x10, 0xA9, FONT_BANK, 0x53, 0x20)   # lda #$82 ; tam #$10 ; lda #$69 ; tam #$20
    a.w(0x20, entry)                                             # jsr dispatcher (X = function, X = status back)
    a.b(0x68, 0x53, 0x20, 0x68, 0x53, 0x10)                         # pla ; tam #$20 ; pla ; tam #$10
    if sei:
        a.b(0x28)                                                   # plp
    a.b(0x7A, 0x60)                                                 # ply ; rts
    code = a.link()
    assert TRAMP_ORG + len(code) <= TRAMP_END, f"trampolines: {len(code)} bytes, {TRAMP_END - TRAMP_ORG} free"
    return code, a.labels["glyph_hook"], a.labels["dec_hook"]


def build_block(coding, extra=b""):
    """The 2 KB block for bank $82 + $1800 (seen at $9800): magic word, then code, then tables.

    `extra` rides along at the end for code that is not ours to hold: the name-entry overlay has no room
    left for the keyboard's letters, but it can map this bank in for as long as it needs them.
    """
    code = _code(coding, DATA_ORG + len(MAGIC))
    block = MAGIC + code + extra
    assert DATA_ORG + len(block) <= DATA_END, f"bank $82 block = {len(block)} bytes, {DATA_END - DATA_ORG} free"
    return block, DATA_ORG + len(MAGIC) + len(code)


def build_resident():
    """loader_hook for $5BB3, called from the loader's success path with the loader's context."""
    a = Asm(RES_ORG)
    a.label("loader_hook")
    a.w(0x9C, 0x3F21)                                               # the instruction the jsr replaced
    a.b(0x43, 0x10, 0x48, 0xA9, DATA_BANK, 0x53, 0x10)              # tma #$10 ; pha ; lda #$82 ; tam #$10
    # Not in engine states 2 and 3, the intro and the cutscene engine: the seek to sector 57 costs the time
    # the intro's pictures are cued in against the CD music, and the circuit board after the skeleton arm and
    # the street scene under the credits came out as garbage tiles (hardware, 24-26 Sep). Nothing draws our
    # text there; the next load in play (state 4/5, the reception first) puts the block back.
    a.b(0xA5, 0x18, 0x4A, 0x3A); a.r(0xF0, "done")                  # lda <$18 ; lsr ; dec ; beq: state 2 or 3
    # One byte of the magic word is enough, and it has to be: only the boot load ($FF) and the two act images
    # ($C7, $A2) ever reach $9800-$9801, so "E" there is our block.
    a.w(0xAD, DATA_ORG); a.b(0xC9, MAGIC[0]); a.r(0xF0, "done")     # block intact?
    a.label("rtry")                                                 # CD_READ ($E009): sector 0:0:57 in $FC/$FD/$FE,
    a.b(0x64, 0xFC, 0x64, 0xFD, 0xA9, DATA_SECTOR, 0x85, 0xFE, 0x64, 0xFF)   # $FF = 0: to local memory
    a.b(0x64, 0xFA, 0xA9, DATA_ORG >> 8, 0x85, 0xFB)                # at $9800
    a.b(0x64, 0xF8, 0xA9, 0x08, 0x85, 0xF9)                         # $0800 bytes
    a.w(0x20, 0xE009); a.b(0xA8); a.r(0xD0, "rtry")                # tay ; bne: again until it succeeds, as the loader does
    a.label("done")
    a.b(0x68, 0x53, 0x10, 0x60)                                     # pla ; tam #$10 ; rts
    code = a.link()
    assert RES_ORG + len(code) <= RES_END, f"loader_hook = {len(code)} bytes, {RES_END - RES_ORG} free"
    assert DATA_ORG & 0xFF == 0
    return code, a.labels["loader_hook"]


LOADER_OK, LOADER_ORIG = 0x54F1, bytes.fromhex("9c213f")            # scene_loader_main_readok: stz $3F21


def _code(coding, org):
    G1, a = sncells.G1, Asm(org)
    N_LO, N_HI, LEFT, RIGHT, P_LO, P_HI = 0x02, 0x03, 0x04, 0x05, 0x00, 0x01
    a.b(0x7C); a.dw("table")                                        # jmp (table,x)
    a.label("table"); a.dw("glyph"); a.dw("step"); a.dw("init")

    # ---- glyph: compose two 6x9 glyphs into the 16x16 buffer at ($FA) -------------------------------
    a.label("glyph")
    for z in (LEFT, RIGHT):
        a.b(0xA5, z, 0x48)                                          # save the scratch zero page
    a.b(0xA5, 0xF9, 0xC9, 0xE0); a.r(0x90, "k_low")                 # lead -> k (the $E0.. range follows $9F)
    a.b(0x38, 0xE9, 0xE0 - 24 - 0x88)
    a.label("k_low"); a.b(0x38, 0xE9, 0x88)
    a.b(0x0A, 0x85, LEFT)                                           # left = k * 2
    a.b(0x38, 0xA5, 0xF8, 0xE9, 0x40)                               # t = trail - $40
    a.b(0xC9, G1); a.r(0x90, "t_low")                               # t >= G1: the odd half of this lead
    a.b(0xE9, G1, 0xE6, LEFT)                                       # t -= G1 ; left += 1
    a.label("t_low"); a.b(0x85, RIGHT)
    a.label("draw")
    # Only the rows above and below the glyph need clearing: in the rows the glyphs cover, the left
    # glyph writes the high byte and the right glyph writes the low byte (a BLANK glyph fetches as 0).
    a.b(0xC2, 0xA9, 0x00)
    a.label("clr"); a.b(0x91, 0xFA, 0xC8, 0xC0, TOP * 2); a.r(0xD0, "clr")
    a.b(0xA0, (TOP + ROWS) * 2)
    a.label("clr2"); a.b(0x91, 0xFA, 0xC8, 0xC0, 0x20); a.r(0xD0, "clr2")
    a.b(0xA5, LEFT); a.w(0x20, "gptr"); a.b(0xA0, TOP * 2, 0xA2, ROWS)   # row pointer, row counter
    a.label("lrow")                                                 # left glyph: font byte -> high byte
    a.b(0xB2, P_LO, 0x91, 0xFA, 0xC8, 0xC8)                         # lda (P) ; sta ($FA),y ; iny ; iny
    a.b(0xE6, P_LO); a.r(0xD0, "l1"); a.b(0xE6, P_HI)
    a.label("l1"); a.b(0xCA); a.r(0xD0, "lrow")
    a.b(0xA5, RIGHT); a.w(0x20, "gptr"); a.b(0xA0, TOP * 2, 0xA2, ROWS)
    a.label("rrow")                                                 # right glyph: 6 pixels on, across the byte edge
    a.b(0xB2, P_LO, 0x48)
    a.b(0x4A, 0x4A, 0x4A, 0x4A, 0x4A, 0x4A, 0x11, 0xFA, 0x91, 0xFA, 0xC8)
    a.b(0x68, 0x0A, 0x0A, 0x91, 0xFA, 0xC8)
    a.b(0xE6, P_LO); a.r(0xD0, "r1"); a.b(0xE6, P_HI)
    a.label("r1"); a.b(0xCA); a.r(0xD0, "rrow")
    for z in (RIGHT, LEFT):
        a.b(0x68, 0x85, z)
    a.b(0x60)
    a.label("gptr")                                                 # A = glyph index -> P = font + A*9 ; index G1-1 = BLANK (P = 0)
    a.b(0xC9, G1 - 1); a.r(0xD0, "gp2")
    a.imm(0xA9, "zeros", "lo"); a.b(0x85, P_LO); a.imm(0xA9, "zeros", "hi"); a.b(0x85, P_HI); a.b(0x60)
    a.label("gp2")
    assert ROWS == 9
    a.b(0x85, P_LO, 0x64, P_HI, 0x0A, 0x26, P_HI, 0x0A, 0x26, P_HI, 0x0A, 0x26, P_HI)
    a.b(0x18, 0x65, P_LO, 0x90, 0x02, 0xE6, P_HI)
    a.b(0x18, 0x69, FONT_ORG & 0xFF, 0x85, P_LO, 0xA5, P_HI, 0x69, FONT_ORG >> 8, 0x85, P_HI, 0x60)

    # ---- text decoder: Huffman symbols -> glyphs / word tokens -> letter-pair cells -----------------
    import snhuff
    G, NL, END, NOWAIT, TOK0 = snhuff.G, snhuff.NL, snhuff.END, snhuff.NOWAIT, snhuff.TOK0
    for v in ("need", "bitbuf", "bitcnt", "code_lo", "code_hi", "first_lo", "first_hi", "index", "len", "t_lo",
              "leftsym", "pendsym", "tokleft", "n_lo", "n_hi", "cnt"):
        a.label(v); a.b(0)
    a.label("init")
    for v in ("need", "bitcnt", "tokleft"):
        a.w(0x9C, v)
    a.b(0xA9, 0xFF); a.w(0x8D, "leftsym"); a.w(0x8D, "pendsym")
    a.label("hreset")                                               # start a new code word
    for v in ("code_lo", "code_hi", "first_lo", "first_hi", "index", "len"):
        a.w(0x9C, v)
    a.b(0x60)

    a.label("step")
    a.w(0xAD, "need"); a.r(0xF0, "s0")
    a.w(0x9C, "need"); a.w(0xAD, 0x360F); a.w(0x8D, "bitbuf"); a.b(0xA9, 0x08); a.w(0x8D, "bitcnt")
    a.label("s0")
    a.w(0xAD, "leftsym"); a.b(0xC9, 0xFF); a.r(0xD0, "have_a")
    a.w(0x20, "getsym"); a.r(0x90, "got_a"); a.w(0x4C, "want")
    a.label("got_a")
    a.b(0xC9, END); a.r(0xD0, "ga1"); a.w(0x4C, "do_end")
    a.label("ga1"); a.b(0xC9, NL); a.r(0xD0, "ga1b"); a.w(0x4C, "do_nl")
    a.label("ga1b"); a.b(0xC9, NOWAIT); a.r(0xD0, "ga2"); a.w(0x4C, "do_f5")
    a.label("ga2")
    a.w(0x8D, "leftsym")
    a.label("have_a")
    a.w(0x20, "getsym"); a.r(0x90, "got_b"); a.w(0x4C, "want")
    a.label("got_b")
    a.b(0xC9, G); a.r(0x90, "pair_b")
    a.w(0x8D, "pendsym"); a.b(0xA9, G1 - 1)                         # line break / end: left + BLANK now, that symbol next time
    a.label("pair_b")
    a.w(0x8D, "n_lo")                                               # right symbol
    a.w(0xAD, "leftsym"); a.b(0x4A); a.w(0x8D, "n_hi")              # k = left >> 1
    a.w(0xAD, "leftsym"); a.b(0x29, 0x01); a.r(0xF0, "e_even")      # odd left: trail += G1
    a.b(0x18); a.w(0xAD, "n_lo"); a.b(0x69, G1); a.w(0x8D, "n_lo")
    a.label("e_even")
    a.b(0xA9, 0xFF); a.w(0x8D, "leftsym")
    a.w(0xAD, "n_hi"); a.b(0xC9, 24); a.r(0x90, "e_lo")             # lead = $88 + k, or $E0 + k - 24
    a.b(0x18, 0x69, 0xE0 - 24); a.r(0x80, "e_st")
    a.label("e_lo"); a.b(0x18, 0x69, 0x88)
    a.label("e_st"); a.w(0x8D, 0x360D)
    a.b(0x18); a.w(0xAD, "n_lo"); a.b(0x69, 0x40); a.w(0x8D, 0x360E)
    a.b(0xA2, 0x00, 0x60)
    a.label("do_nl")
    a.b(0xA9, 0x82); a.w(0x8D, 0x360D); a.b(0xA9, 0xF2); a.w(0x8D, 0x360E); a.b(0xA2, 0x00, 0x60)
    a.label("do_f5")                                                # <82F5>: the box closes without a button
    a.b(0xA9, 0x82); a.w(0x8D, 0x360D); a.b(0xA9, 0xF5); a.w(0x8D, 0x360E); a.b(0xA2, 0x00, 0x60)
    a.label("do_end")
    a.b(0xA9, 0x01); a.w(0x8D, 0x3607); a.b(0xA2, 0x00, 0x60)
    a.label("want")
    a.b(0xA9, 0x01); a.w(0x8D, "need"); a.b(0xA2, 0x01, 0x60)

    a.label("rd")                                                   # A = next dictionary byte (self-modifying pointer)
    a.w(0xAD, 0x0000)
    a.w(0xEE, "rd", 1); a.r(0xD0, "rd_ok"); a.w(0xEE, "rd", 2)
    a.label("rd_ok"); a.b(0x60)

    a.label("getsym")                                               # -> C clear, A = glyph / NL / END ; C set = needs a byte
    a.w(0xAD, "pendsym"); a.b(0xC9, 0xFF); a.r(0xF0, "gs_tok")
    a.b(0x48, 0xA9, 0xFF); a.w(0x8D, "pendsym"); a.b(0x68, 0x18, 0x60)
    a.label("gs_tok")
    a.w(0xAD, "tokleft"); a.r(0xF0, "h_loop")
    a.w(0xCE, "tokleft"); a.w(0x20, "rd"); a.b(0x18, 0x60)
    a.label("h_loop")
    a.w(0xAD, "bitcnt"); a.r(0xD0, "h_bit"); a.b(0x38, 0x60)        # out of bits: sec ; rts
    a.label("h_bit")
    a.w(0xCE, "bitcnt"); a.w(0x0E, "bitbuf"); a.w(0x2E, "code_lo"); a.w(0x2E, "code_hi")
    a.w(0xAE, "len"); a.w(0xBD, "count"); a.w(0x8D, "cnt"); a.w(0xEE, "len")
    a.b(0x38); a.w(0xAD, "code_lo"); a.w(0xED, "first_lo"); a.w(0x8D, "t_lo")
    a.w(0xAD, "code_hi"); a.w(0xED, "first_hi"); a.r(0xD0, "h_next")
    a.w(0xAD, "t_lo"); a.w(0xCD, "cnt"); a.r(0xB0, "h_next")
    a.b(0x18); a.w(0x6D, "index"); a.b(0xAA); a.w(0xBD, "syms")      # symbol = SYMS[index + code - first]
    a.b(0x48); a.w(0x20, "hreset"); a.b(0x68)
    a.b(0xC9, TOK0); a.r(0xB0, "h_token"); a.b(0x18, 0x60)
    a.label("h_next")                                               # index += cnt ; first = (first + cnt) << 1
    a.b(0x18); a.w(0xAD, "index"); a.w(0x6D, "cnt"); a.w(0x8D, "index")
    a.b(0x18); a.w(0xAD, "first_lo"); a.w(0x6D, "cnt"); a.w(0x8D, "first_lo"); a.r(0x90, "h_n1"); a.w(0xEE, "first_hi")
    a.label("h_n1"); a.w(0x0E, "first_lo"); a.w(0x2E, "first_hi"); a.r(0x80, "h_loop")
    a.label("h_token")                                              # walk the length-prefixed dictionary to token A-TOK0
    a.b(0x38, 0xE9, TOK0, 0xAA)
    a.imm(0xA9, "dict", "lo"); a.w(0x8D, "rd", 1)
    a.imm(0xA9, "dict", "hi"); a.w(0x8D, "rd", 2)
    a.label("walk"); a.b(0xE0, 0x00); a.r(0xF0, "found")
    a.w(0x20, "rd"); a.b(0x18); a.w(0x6D, "rd", 1); a.w(0x8D, "rd", 1); a.r(0x90, "w1"); a.w(0xEE, "rd", 2)
    a.label("w1"); a.b(0xCA); a.r(0x80, "walk")
    a.label("found")
    a.w(0x20, "rd"); a.w(0x8D, "tokleft"); a.w(0x4C, "gs_tok")
    a.label("zeros"); a.b(*([0] * ROWS))                            # the BLANK glyph reads from here
    a.label("count"); a.b(*coding.count)
    a.label("syms"); a.b(*coding.syms)
    a.label("dict")
    for w in coding.tokens:
        a.b(len(w), *[sncells.GLYPHS.index(c) for c in w])
    return a.link()


def apply(iso, coding=None, extra=b""):
    import snhuff
    coding = coding or snhuff.Coding()
    iso = bytearray(iso)
    block, extra_at = build_block(coding, extra)
    resident, loader_hook = build_resident()
    tramp, glyph_hook, dec_hook = build_trampolines(DATA_ORG + len(MAGIC))
    font = font_bytes()
    assert len(font) <= 0x2000 - 0x1CD2, f"font is {len(font)} bytes"
    base = DIALOGUE_ISO - 0x6000
    assert iso[base + GLYPH_SITE:base + GLYPH_SITE + 3] == GLYPH_ORIG, "glyph call site differs"
    assert iso[base + DEC_SITE:base + DEC_SITE + 8] == DEC_ORIG, "decoder entry differs"
    for off, blob in ((base + TRAMP_ORG, tramp), (RES_ISO, resident), (DATA_ISO, block), (FONT_ISO, font)):
        assert set(iso[off:off + len(blob)]) == {0xFF}, f"target area at ISO {off:#x} is not free"
        iso[off:off + len(blob)] = blob
    lo = 0xB000 + LOADER_OK - 0x4000                                  # bank $68 on disc
    assert iso[lo:lo + 3] == LOADER_ORIG, "scene loader success path differs"
    iso[lo:lo + 3] = bytes([0x20]) + loader_hook.to_bytes(2, "little")
    iso[base + GLYPH_SITE:base + GLYPH_SITE + 3] = bytes([0x20]) + glyph_hook.to_bytes(2, "little")
    iso[base + DEC_SITE:base + DEC_SITE + 3] = bytes([0x4C]) + dec_hook.to_bytes(2, "little")
    return bytes(iso), {"trampolines": len(tramp), "resident loader_hook": len(resident),
                        "block at $9800": len(block), "font": len(font)}, extra_at


if __name__ == "__main__":
    if sys.argv[1] == "apply":
        data, sizes = apply(open(sys.argv[2], "rb").read())
        open(sys.argv[3], "wb").write(data)
        print(sizes)
    elif sys.argv[1] == "font":
        from PIL import Image
        f = font_bytes()
        n = len(f) // ROWS
        img = Image.new("L", (n * 7 * 3, (ROWS + 2) * 3), 0)
        for g in range(n):
            for y in range(ROWS):
                for x in range(6):
                    if f[g * ROWS + y] & (0x80 >> x):
                        for dx in range(3):
                            for dy in range(3):
                                img.putpixel(((g * 7 + x) * 3 + dx, (y + 1) * 3 + dy), 255)
        img.save(sys.argv[2])
        print(n, "glyphs,", len(f), "bytes")
