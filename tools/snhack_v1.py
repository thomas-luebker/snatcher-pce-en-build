#!/usr/bin/env python3
"""Code patch for Snatcher PCE: draw "letter pair" cells (see tools/sncells.py).

  snhack.py apply iso_in iso_out      (same offsets in both data tracks)
  snhack.py font work/font.png        (preview of the 6x10 font)

Hook: the glyph renderer in the dialogue bank (ISO 0xF000, mapped at $6000) calls
`jsr $69C2` (custom-glyph override search) at $648C before asking the System Card for a kanji.
That call is redirected to new code in the bank's free tail ($7F50-$7FFF). For SJIS lead bytes
$89-$97 it composes two 6x10 glyphs into the 16x16 glyph buffer at ($FA) and returns A=0
("glyph ready"); everything else goes on to $69C2 unchanged.

The font (GLYPHS x 10 rows, 6 bits left-aligned per byte) sits in the engine bank's unused tail
at $5C40 (ISO 0xB000 + $1C40); the engine bank is resident at $4000.
"""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sncells  # noqa: E402

DIALOGUE_ISO = 0xF000                         # RAM bank $6A, mapped at $6000 while text is drawn
CALL_SITE, ORIGINAL_CALL = 0x648C, bytes.fromhex("20c269")          # jsr $69C2
CODE_ORG, CODE_END = 0x7F50, 0x8000          # part A: decode the cell number (dialogue bank tail, 176 bytes free)
# Part B (compose the glyphs) + font live in the free tail of RAM bank $69 (ISO 0xD000, 814 x $FF at +$1CD2,
# unchanged across save states). Bank $69 shares the $6000 window with the dialogue bank, so part A maps it
# into MPR4 ($8000) for the duration of the call, interrupts off. (The engine bank's $5C40 tail looked free
# on disc but is work RAM at runtime: code placed there was overwritten within a second.)
FONT_BANK, FONT_BANK_ISO = 0x69, 0xD000
B_OFF, B_END = 0x1CD2, 0x2000
DRAW_ORG = 0x8000 + B_OFF
ROWS, TOP, SRC_ROW = 9, 2, 2        # glyph rows kept (Monaco 9 uses pixel rows 1-10; row 1 only in 3 glyphs), first buffer row, first source row
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
        for y in range(12):
            b = 0
            for x in range(6):
                if img.getpixel((x, y)):
                    b |= 0x80 >> x
            rows.append(b)
        rows = rows[SRC_ROW:SRC_ROW + ROWS]
        out += bytes(rows)
    return bytes(out)


class Asm:
    def __init__(self, org):
        self.org, self.out, self.labels, self.fix = org, bytearray(), {}, []

    def label(self, n):
        self.labels[n] = self.org + len(self.out)

    def b(self, *d):
        self.out += bytes(d)

    def w(self, op, addr):
        self.out.append(op)
        if isinstance(addr, str):
            self.fix.append((len(self.out), addr, "abs")); addr = 0
        self.out += addr.to_bytes(2, "little")

    def r(self, op, label):
        self.out.append(op); self.fix.append((len(self.out), label, "rel")); self.out.append(0)

    def link(self):
        for pos, name, kind in self.fix:
            t = self.labels[name]
            if kind == "abs":
                self.out[pos:pos + 2] = t.to_bytes(2, "little")
            else:
                d = t - (self.org + pos + 1)
                assert -128 <= d <= 127, name
                self.out[pos] = d & 0xFF
        return bytes(self.out)


def build_code(font_org=0x9F00):
    """Zero page used: $F8 trail, $F9 lead, $FA/$FB buffer (inputs); scratch $00-$05 (the override
    search itself clobbers $00/$01, the caller reloads them)."""
    K, a, bseg = sncells.K, Asm(CODE_ORG), Asm(DRAW_ORG)
    N_LO, N_HI, LEFT, RIGHT, P_LO, P_HI = 0x02, 0x03, 0x04, 0x05, 0x00, 0x01
    a.label("hook")
    a.b(0xA5, 0xF9, 0xC9, 0x89); a.r(0x90, "orig")                  # lda <$F9 ; cmp #$89 ; bcc orig
    a.b(0xC9, 0x98); a.r(0x90, "cell")                              # cmp #$98 ; bcc cell
    a.label("orig"); a.w(0x4C, 0x69C2)                              # jmp $69C2
    a.label("cell")
    a.b(0xAA)                                                       # tax            (keep lead)
    for z in (N_LO, N_HI, LEFT, RIGHT):
        a.b(0xA5, z, 0x48)                                          # lda <z ; pha   (scratch is restored on exit)
    a.b(0x8A)                                                       # txa
    a.b(0x38, 0xE9, 0x89)                                           # sec ; sbc #$89        k = lead - $89   (0..14)
    a.b(0x64, N_HI, 0x4A, 0x66, N_HI, 0x4A, 0x66, N_HI)             # stz hi ; lsr a ; ror hi ; lsr a ; ror hi   -> a:hi = k*64 (hi byte in A, low in N_HI)
    a.b(0x85, N_LO)                                                 # sta <N_LO            (temporarily: high byte of k*64)
    # k*64 = (N_LO << 8) | N_HI ;  k*192 = k*64*3
    a.b(0xA5, N_HI, 0x0A, 0x85, P_LO, 0xA5, N_LO, 0x2A, 0x85, P_HI)  # P = k*128
    a.b(0x18, 0xA5, P_LO, 0x65, N_HI, 0x85, P_LO, 0xA5, P_HI, 0x65, N_LO, 0x85, P_HI)   # P = k*192
    a.b(0x38, 0xA5, 0xF8, 0xE9, 0x40)                               # sec ; lda <$F8 ; sbc #$40      t = trail - $40
    a.b(0x18, 0x65, P_LO, 0x85, N_LO, 0xA5, P_HI, 0x69, 0x00, 0x85, N_HI)               # N = k*192 + t
    # single cell?  N >= K*K
    kk = K * K
    a.b(0xA5, N_HI, 0xC9, kk >> 8); a.r(0x90, "pair"); a.r(0xD0, "single")
    a.b(0xA5, N_LO, 0xC9, kk & 0xFF); a.r(0x90, "pair")
    a.label("single")
    a.b(0x38, 0xA5, N_LO, 0xE9, kk & 0xFF, 0x18, 0x69, K, 0x85, LEFT)       # left = (N - K*K) + 53: gptr maps 53+s to font entry 52+s
    a.b(0xA9, K - 1, 0x85, RIGHT); a.r(0x80, "call")                # right = BLANK
    a.label("pair")
    a.b(0x64, LEFT)                                                 # left = N / K, right = N % K by repeated subtraction
    a.label("div")
    a.b(0xA5, N_HI); a.r(0xD0, "sub"); a.b(0xA5, N_LO, 0xC9, K); a.r(0x90, "divdone")
    a.label("sub")
    a.b(0x38, 0xA5, N_LO, 0xE9, K, 0x85, N_LO, 0xA5, N_HI, 0xE9, 0x00, 0x85, N_HI, 0xE6, LEFT); a.r(0x80, "div")
    a.label("divdone"); a.b(0xA5, N_LO, 0x85, RIGHT)
    a.label("call")
    a.b(0x08, 0x78, 0x43, 0x10, 0x48, 0xA9, FONT_BANK, 0x53, 0x10)  # php ; sei ; tma #$10 ; pha ; lda #bank ; tam #$10
    a.w(0x20, DRAW_ORG)                                             # jsr draw (part B, seen through MPR4)
    a.b(0x68, 0x53, 0x10, 0x28)                                     # pla ; tam #$10 ; plp
    for z in (RIGHT, LEFT, N_HI, N_LO):
        a.b(0x68, 0x85, z)                                          # pla ; sta <z
    a.b(0x62, 0x60)                                                 # cla ; rts           A=0 -> "glyph ready"
    code_a = a.link()
    a = bseg
    a.label("draw")
    # clear the 32-byte buffer
    a.b(0xC2); a.b(0xA9, 0x00)                                      # cly ; lda #0
    a.label("clr"); a.b(0x91, 0xFA, 0xC8, 0xC0, 0x20); a.r(0xD0, "clr")
    # left glyph -> high bytes
    a.b(0xA5, LEFT); a.w(0x20, "gptr"); a.b(0xA0, TOP * 2)          # ldy #first row*2
    a.b(0x82)                                                       # clx
    a.label("lrow")
    a.w(0x20, "fetch"); a.b(0x91, 0xFA, 0xC8, 0xC8, 0xE8, 0xE0, ROWS); a.r(0xD0, "lrow")
    # right glyph -> bits 9..4 : high byte |= g>>6 , low byte = g<<2
    a.b(0xA5, RIGHT); a.w(0x20, "gptr"); a.b(0xA0, TOP * 2, 0x82)
    a.label("rrow")
    a.w(0x20, "fetch"); a.b(0x48)                                   # pha
    a.b(0x4A, 0x4A, 0x4A, 0x4A, 0x4A, 0x4A, 0x11, 0xFA, 0x91, 0xFA, 0xC8)   # lsr x6 ; ora (fa),y ; sta (fa),y ; iny
    a.b(0x68, 0x0A, 0x0A, 0x91, 0xFA, 0xC8, 0xE8, 0xE0, ROWS); a.r(0xD0, "rrow")
    a.b(0x60)                                                       # rts  (back to part A)
    a.label("gptr")                                                 # A = glyph index -> P = FONT + A*ROWS ; blank if index K-1
    a.b(0xC9, K - 1); a.r(0xD0, "gp1"); a.b(0x64, P_HI, 0x64, P_LO, 0x60)      # blank: P = 0 -> fetch returns 0
    a.label("gp1"); a.r(0x90, "gp2"); a.b(0x3A)                     # index > K-1 (EXTRA): font has no BLANK entry -> index-1
    a.label("gp2")
    a.b(0x85, P_LO, 0x64, P_HI)                                     # P = idx
    assert ROWS == 9
    a.b(0x0A, 0x26, P_HI, 0x0A, 0x26, P_HI, 0x0A, 0x26, P_HI)       # A = idx*8 (carry into P_HI)
    a.b(0x18, 0x65, P_LO, 0x90, 0x02, 0xE6, P_HI)                   # A = idx*9
    a.b(0x18, 0x69, font_org & 0xFF, 0x85, P_LO, 0xA5, P_HI, 0x69, font_org >> 8, 0x85, P_HI, 0x60)
    a.label("fetch")                                                # A = font byte for row X (0 for blank)
    a.b(0xA5, P_HI); a.r(0xD0, "f1"); a.b(0x62, 0x60)               # lda P_HI ; bne f1 ; cla ; rts
    a.label("f1"); a.b(0x5A, 0x8A, 0xA8, 0xB1, P_LO, 0x7A, 0x60)    # phy ; txa ; tay ; lda (P),y ; ply ; rts
    code_b = a.link()
    assert CODE_ORG + len(code_a) <= CODE_END, f"part A is {len(code_a)} bytes, only {CODE_END - CODE_ORG} free"
    if font_org != DRAW_ORG + len(code_b):
        return build_code(DRAW_ORG + len(code_b))                   # second pass with the real font address
    return code_a, code_b, CODE_ORG


def apply(iso):
    iso = bytearray(iso)
    code, code_b, hook = build_code()
    font = font_bytes()
    blob = code_b + font
    assert B_OFF + len(blob) <= B_END, f"part B + font = {len(blob)} bytes, only {B_END - B_OFF} free"
    site = DIALOGUE_ISO + CALL_SITE - 0x6000
    assert iso[site:site + 3] == ORIGINAL_CALL, "unexpected bytes at the call site"
    c0, b0 = DIALOGUE_ISO + CODE_ORG - 0x6000, FONT_BANK_ISO + B_OFF
    assert set(iso[c0:c0 + len(code)]) == {0xFF} and set(iso[b0:b0 + len(blob)]) == {0xFF}, "target area not free"
    iso[c0:c0 + len(code)] = code
    iso[b0:b0 + len(blob)] = blob
    iso[site:site + 3] = bytes([0x20]) + hook.to_bytes(2, "little")
    return bytes(iso), len(code) + len(code_b), len(font)


if __name__ == "__main__":
    if sys.argv[1] == "apply":
        data, n, m = apply(open(sys.argv[2], "rb").read())
        open(sys.argv[3], "wb").write(data)
        print(f"hook {n} bytes, font {m} bytes")
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
