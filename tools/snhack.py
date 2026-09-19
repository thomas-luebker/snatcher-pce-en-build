#!/usr/bin/env python3
"""Code patch for Snatcher PCE: letter-pair cells (tools/sncells.py) and dictionary tokens (tools/sndict.py).

  snhack.py apply iso_in iso_out      (same offsets in both data tracks)
  snhack.py font work/font.png        (preview of the font)

Only RAM banks $68-$6A are never a load target, and their free tails are small, so the patch is split:

  $6A (dialogue bank, ISO 0xF000) tail $7F50-$7FFF   trampolines only. Two hooks:
        $648C  jsr $69C2  ->  jsr GLYPH_HOOK    SJIS lead $89-$97 = letter-pair cell, drawn by us
        $7272  (entry of decode_next_pair)  ->  jmp DEC_HOOK
                                                 lead $88/$98 = dictionary token, expanded into cells
  $82 tail +$1800-$1FFF (ISO 0x1C800)              all real code + the dictionary. Loaded once at boot
        with the clip tables; the 3-sector table switches do not reach it.
  $69 tail +$1CD2-$1FFF (ISO 0xD000 + $1CD2)       the 6x9 font.

A trampoline maps $82 -> MPR4 ($8000) and $69 -> MPR5 ($A000) with interrupts off, calls the dispatcher
at $9800 with the function number in X, and restores both.
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
CODE_BANK, CODE_ISO, CODE_ORG, CODE_END = 0x82, 0x1C800, 0x9800, 0xA000
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


def build_trampolines():
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
    a.b(0x08, 0x78, 0x5A)                                           # php ; sei ; phy
    a.b(0x43, 0x10, 0x48, 0x43, 0x20, 0x48)                         # tma #$10 ; pha ; tma #$20 ; pha
    a.b(0xA9, CODE_BANK, 0x53, 0x10, 0xA9, FONT_BANK, 0x53, 0x20)   # lda #$82 ; tam #$10 ; lda #$69 ; tam #$20
    a.w(0x20, CODE_ORG)                                             # jsr dispatcher (X = function, X = status back)
    a.b(0x68, 0x53, 0x20, 0x68, 0x53, 0x10, 0x7A, 0x28, 0x60)       # pla ; tam #$20 ; pla ; tam #$10 ; ply ; plp ; rts
    code = a.link()
    assert TRAMP_ORG + len(code) <= TRAMP_END, f"trampolines: {len(code)} bytes, {TRAMP_END - TRAMP_ORG} free"
    return code, a.labels["glyph_hook"], a.labels["dec_hook"]


def build_code(coding):
    """Everything that runs from bank $82 (seen at $9800). coding = snhuff.Coding."""
    G1, a = sncells.G1, Asm(CODE_ORG)
    N_LO, N_HI, LEFT, RIGHT, P_LO, P_HI = 0x02, 0x03, 0x04, 0x05, 0x00, 0x01
    a.b(0x7C); a.dw("table")                                        # jmp (table,x)
    a.label("table"); a.dw("glyph"); a.dw("step"); a.dw("init")

    # ---- glyph: compose two 6x9 glyphs into the 16x16 buffer at ($FA) -------------------------------
    a.label("glyph")
    for z in (N_LO, N_HI, LEFT, RIGHT):
        a.b(0xA5, z, 0x48)                                          # save the scratch zero page
    a.b(0xA5, 0xF9, 0xC9, 0xE0); a.r(0x90, "k_low")                 # k = lead - $88, or lead - $E0 + 24
    a.b(0x38, 0xE9, 0xE0 - 24 - 0x88)                               # bring $E0.. down next to $9F
    a.label("k_low"); a.b(0x38, 0xE9, 0x88)
    a.b(0x85, LEFT)                                                 # keep k: the spacing is 191, not 192
    a.b(0x64, N_HI, 0x4A, 0x66, N_HI, 0x4A, 0x66, N_HI, 0x85, N_LO)  # k*64 = (N_LO<<8)|N_HI
    a.b(0xA5, N_HI, 0x0A, 0x85, P_LO, 0xA5, N_LO, 0x2A, 0x85, P_HI)  # P = k*128
    a.b(0x18, 0xA5, P_LO, 0x65, N_HI, 0x85, P_LO, 0xA5, P_HI, 0x65, N_LO, 0x85, P_HI)   # P = k*192
    a.b(0x38, 0xA5, P_LO, 0xE5, LEFT, 0x85, P_LO, 0xA5, P_HI, 0xE9, 0x00, 0x85, P_HI)   # P = k*191
    a.b(0x38, 0xA5, 0xF8, 0xE9, 0x40)                               # t = trail - $40
    a.b(0x18, 0x65, P_LO, 0x85, N_LO, 0xA5, P_HI, 0x69, 0x00, 0x85, N_HI)               # N = k*192 + t
    a.b(0x64, LEFT)                                                 # left = N / G1, right = N % G1
    a.label("div")
    a.b(0xA5, N_HI); a.r(0xD0, "sub"); a.b(0xA5, N_LO, 0xC9, G1); a.r(0x90, "divdone")
    a.label("sub")
    a.b(0x38, 0xA5, N_LO, 0xE9, G1, 0x85, N_LO, 0xA5, N_HI, 0xE9, 0x00, 0x85, N_HI, 0xE6, LEFT); a.r(0x80, "div")
    a.label("divdone"); a.b(0xA5, N_LO, 0x85, RIGHT)
    a.label("draw")
    a.b(0xC2, 0xA9, 0x00)
    a.label("clr"); a.b(0x91, 0xFA, 0xC8, 0xC0, 0x20); a.r(0xD0, "clr")
    a.b(0xA5, LEFT); a.w(0x20, "gptr"); a.b(0xA0, TOP * 2, 0x82)
    a.label("lrow"); a.w(0x20, "fetch"); a.b(0x91, 0xFA, 0xC8, 0xC8, 0xE8, 0xE0, ROWS); a.r(0xD0, "lrow")
    a.b(0xA5, RIGHT); a.w(0x20, "gptr"); a.b(0xA0, TOP * 2, 0x82)
    a.label("rrow"); a.w(0x20, "fetch"); a.b(0x48)
    a.b(0x4A, 0x4A, 0x4A, 0x4A, 0x4A, 0x4A, 0x11, 0xFA, 0x91, 0xFA, 0xC8)
    a.b(0x68, 0x0A, 0x0A, 0x91, 0xFA, 0xC8, 0xE8, 0xE0, ROWS); a.r(0xD0, "rrow")
    for z in (RIGHT, LEFT, N_HI, N_LO):
        a.b(0x68, 0x85, z)
    a.b(0x60)
    a.label("gptr")                                                 # A = glyph index -> P = font + A*9 ; index G1-1 = BLANK (P = 0)
    a.b(0xC9, G1 - 1); a.r(0xD0, "gp2"); a.b(0x64, P_HI, 0x64, P_LO, 0x60)
    a.label("gp2")
    assert ROWS == 9
    a.b(0x85, P_LO, 0x64, P_HI, 0x0A, 0x26, P_HI, 0x0A, 0x26, P_HI, 0x0A, 0x26, P_HI)
    a.b(0x18, 0x65, P_LO, 0x90, 0x02, 0xE6, P_HI)
    a.b(0x18, 0x69, FONT_ORG & 0xFF, 0x85, P_LO, 0xA5, P_HI, 0x69, FONT_ORG >> 8, 0x85, P_HI, 0x60)
    a.label("fetch")
    a.b(0xA5, P_HI); a.r(0xD0, "f1"); a.b(0x62, 0x60)
    a.label("f1"); a.b(0x5A, 0x8A, 0xA8, 0xB1, P_LO, 0x7A, 0x60)

    # ---- text decoder: Huffman symbols -> glyphs / word tokens -> letter-pair cells -----------------
    import snhuff
    G, NL, END, TOK0 = snhuff.G, snhuff.NL, snhuff.END, snhuff.TOK0
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
    a.label("ga1"); a.b(0xC9, NL); a.r(0xD0, "ga2"); a.w(0x4C, "do_nl")
    a.label("ga2")
    a.w(0x8D, "leftsym")
    a.label("have_a")
    a.w(0x20, "getsym"); a.r(0x90, "got_b"); a.w(0x4C, "want")
    a.label("got_b")
    a.b(0xC9, G); a.r(0x90, "pair_b")
    a.w(0x8D, "pendsym"); a.b(0xA9, G1 - 1)                         # line break / end: left + BLANK now, that symbol next time
    a.label("pair_b")
    a.w(0x8D, "n_lo"); a.w(0x9C, "n_hi")                            # n = right + left * G1
    a.w(0xAE, "leftsym")
    a.label("mul"); a.b(0xE0, 0x00); a.r(0xF0, "mul_done")
    a.b(0x18); a.w(0xAD, "n_lo"); a.b(0x69, G1); a.w(0x8D, "n_lo"); a.r(0x90, "mul1"); a.w(0xEE, "n_hi")
    a.label("mul1"); a.b(0xCA); a.r(0x80, "mul")
    a.label("mul_done")
    a.b(0xA9, 0xFF); a.w(0x8D, "leftsym")
    a.label("emit_n")                                               # n -> SJIS lead $88.. (then $E0..) + n/191, trail $40 + n%191
    a.b(0xA2, 0x88)
    a.label("e_div")
    a.w(0xAD, "n_hi"); a.r(0xD0, "e_sub"); a.w(0xAD, "n_lo"); a.b(0xC9, 191); a.r(0x90, "e_done")
    a.label("e_sub")
    a.b(0x38); a.w(0xAD, "n_lo"); a.b(0xE9, 191); a.w(0x8D, "n_lo"); a.r(0xB0, "e_s1"); a.w(0xCE, "n_hi")
    a.label("e_s1"); a.b(0xE8); a.r(0x80, "e_div")
    a.label("e_done")
    a.b(0xE0, 0xA0); a.r(0x90, "e_lead"); a.b(0x8A, 0x18, 0x69, 0x40, 0xAA)   # lead >= $A0 -> + $40 ($E0..)
    a.label("e_lead")
    a.w(0x8E, 0x360D)                                               # stx $360D
    a.b(0x18); a.w(0xAD, "n_lo"); a.b(0x69, 0x40); a.w(0x8D, 0x360E)
    a.b(0xA2, 0x00, 0x60)
    a.label("do_nl")
    a.b(0xA9, 0x82); a.w(0x8D, 0x360D); a.b(0xA9, 0xF2); a.w(0x8D, 0x360E); a.b(0xA2, 0x00, 0x60)
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
    a.label("count"); a.b(*coding.count)
    a.label("syms"); a.b(*coding.syms)
    a.label("dict")
    for w in coding.tokens:
        a.b(len(w), *[sncells.GLYPHS.index(c) for c in w])
    code = a.link()
    assert CODE_ORG + len(code) <= CODE_END, f"bank $82 code + dictionary = {len(code)} bytes, {CODE_END - CODE_ORG} free"
    return code, a.labels["count"] - CODE_ORG


def apply(iso, coding=None):
    import snhuff
    coding = coding or snhuff.Coding()
    iso = bytearray(iso)
    tramp, glyph_hook, dec_hook = build_trampolines()
    code, code_only = build_code(coding)
    font = font_bytes()
    assert len(font) <= 0x2000 - 0x1CD2, f"font is {len(font)} bytes"
    base = DIALOGUE_ISO - 0x6000
    assert iso[base + GLYPH_SITE:base + GLYPH_SITE + 3] == GLYPH_ORIG, "glyph call site differs"
    assert iso[base + DEC_SITE:base + DEC_SITE + 8] == DEC_ORIG, "decoder entry differs"
    for off, blob in ((base + TRAMP_ORG, tramp), (CODE_ISO, code), (FONT_ISO, font)):
        assert set(iso[off:off + len(blob)]) == {0xFF}, f"target area at ISO {off:#x} is not free"
        iso[off:off + len(blob)] = blob
    iso[base + GLYPH_SITE:base + GLYPH_SITE + 3] = bytes([0x20]) + glyph_hook.to_bytes(2, "little")
    iso[base + DEC_SITE:base + DEC_SITE + 3] = bytes([0x4C]) + dec_hook.to_bytes(2, "little")
    return bytes(iso), {"trampolines": len(tramp), "code": code_only, "tables+dictionary": len(code) - code_only, "font": len(font)}


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
