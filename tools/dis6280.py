#!/usr/bin/env python3
"""A HuC6280 disassembler, enough to read the game's own code.

  dis6280.py ISO OFFSET ORG LENGTH        e.g.  dis6280.py disc/track02.iso 0x309a0 0xA9A0 0x100

buranko-kun's disassembly covers the engine, dialogue and scene5 banks; the name-entry overlay (ISO
0x30000, CPU $A000) is not in it, and that is where the answer screens live. Zero page on this CPU is
$2000-$20FF, so `lda <$28` reads $2028.
"""
import sys

# base 6502/65C02 by (mnemonic, mode) per opcode; modes: imp a imm zp zpx zpy abs abx aby ind inx iny izp rel iax
_M = {}


def _t(op, mn, mode):
    _M[op] = (mn, mode)


for base, mn in ((0x00, "ora"), (0x20, "and"), (0x40, "eor"), (0x60, "adc"),
                 (0x80, "sta"), (0xA0, "lda"), (0xC0, "cmp"), (0xE0, "sbc")):
    _t(base + 0x01, mn, "inx"); _t(base + 0x05, mn, "zp"); _t(base + 0x09, mn, "imm")
    _t(base + 0x0D, mn, "abs"); _t(base + 0x11, mn, "iny"); _t(base + 0x12, mn, "izp")
    _t(base + 0x15, mn, "zpx"); _t(base + 0x19, mn, "aby"); _t(base + 0x1D, mn, "abx")
del _M[0x89]
_t(0x89, "bit", "imm")
for base, mn in ((0x00, "asl"), (0x20, "rol"), (0x40, "lsr"), (0x60, "ror")):
    _t(base + 0x06, mn, "zp"); _t(base + 0x0A, mn, "a"); _t(base + 0x0E, mn, "abs")
    _t(base + 0x16, mn, "zpx"); _t(base + 0x1E, mn, "abx")
for op, mn, mode in ((0xA2, "ldx", "imm"), (0xA6, "ldx", "zp"), (0xB6, "ldx", "zpy"), (0xAE, "ldx", "abs"), (0xBE, "ldx", "aby"),
                     (0xA0, "ldy", "imm"), (0xA4, "ldy", "zp"), (0xB4, "ldy", "zpx"), (0xAC, "ldy", "abs"), (0xBC, "ldy", "abx"),
                     (0x86, "stx", "zp"), (0x96, "stx", "zpy"), (0x8E, "stx", "abs"),
                     (0x84, "sty", "zp"), (0x94, "sty", "zpx"), (0x8C, "sty", "abs"),
                     (0x64, "stz", "zp"), (0x74, "stz", "zpx"), (0x9C, "stz", "abs"), (0x9E, "stz", "abx"),
                     (0xE0, "cpx", "imm"), (0xE4, "cpx", "zp"), (0xEC, "cpx", "abs"),
                     (0xC0, "cpy", "imm"), (0xC4, "cpy", "zp"), (0xCC, "cpy", "abs"),
                     (0xE6, "inc", "zp"), (0xF6, "inc", "zpx"), (0xEE, "inc", "abs"), (0xFE, "inc", "abx"), (0x1A, "inc", "a"),
                     (0xC6, "dec", "zp"), (0xD6, "dec", "zpx"), (0xCE, "dec", "abs"), (0xDE, "dec", "abx"), (0x3A, "dec", "a"),
                     (0x24, "bit", "zp"), (0x2C, "bit", "abs"), (0x34, "bit", "zpx"), (0x3C, "bit", "abx"),
                     (0x04, "tsb", "zp"), (0x0C, "tsb", "abs"), (0x14, "trb", "zp"), (0x1C, "trb", "abs"),
                     (0x4C, "jmp", "abs"), (0x6C, "jmp", "ind"), (0x7C, "jmp", "iax"), (0x20, "jsr", "abs"),
                     (0x10, "bpl", "rel"), (0x30, "bmi", "rel"), (0x50, "bvc", "rel"), (0x70, "bvs", "rel"),
                     (0x90, "bcc", "rel"), (0xB0, "bcs", "rel"), (0xD0, "bne", "rel"), (0xF0, "beq", "rel"),
                     (0x80, "bra", "rel"), (0x44, "bsr", "rel"),
                     (0x00, "brk", "imp"), (0x08, "php", "imp"), (0x28, "plp", "imp"), (0x48, "pha", "imp"),
                     (0x68, "pla", "imp"), (0xDA, "phx", "imp"), (0xFA, "plx", "imp"), (0x5A, "phy", "imp"),
                     (0x7A, "ply", "imp"), (0x18, "clc", "imp"), (0x38, "sec", "imp"), (0x58, "cli", "imp"),
                     (0x78, "sei", "imp"), (0xB8, "clv", "imp"), (0xD8, "cld", "imp"), (0xF8, "sed", "imp"),
                     (0x40, "rti", "imp"), (0x60, "rts", "imp"), (0xEA, "nop", "imp"),
                     (0x8A, "txa", "imp"), (0x98, "tya", "imp"), (0xAA, "tax", "imp"), (0xA8, "tay", "imp"),
                     (0x9A, "txs", "imp"), (0xBA, "tsx", "imp"), (0xE8, "inx", "imp"), (0xC8, "iny", "imp"),
                     (0xCA, "dex", "imp"), (0x88, "dey", "imp"),
                     # HuC6280
                     (0x02, "sxy", "imp"), (0x22, "sax", "imp"), (0x42, "say", "imp"), (0x62, "cla", "imp"),
                     (0x82, "clx", "imp"), (0xC2, "cly", "imp"), (0x54, "csl", "imp"), (0xD4, "csh", "imp"),
                     (0xF4, "set", "imp"), (0x03, "st0", "imm"), (0x13, "st1", "imm"), (0x23, "st2", "imm"),
                     (0x43, "tma", "imm"), (0x53, "tam", "imm"),
                     (0x73, "tii", "blk"), (0xC3, "tdd", "blk"), (0xD3, "tin", "blk"), (0xE3, "tia", "blk"), (0xF3, "tai", "blk"),
                     (0x83, "tst", "tzp"), (0xA3, "tst", "tzpx"), (0x93, "tst", "tabs"), (0xB3, "tst", "tabsx")):
    _t(op, mn, mode)
for i in range(8):
    _t(0x07 + i * 16, f"rmb{i}", "zp"); _t(0x87 + i * 16, f"smb{i}", "zp")
    _t(0x0F + i * 16, f"bbr{i}", "zprel"); _t(0x8F + i * 16, f"bbs{i}", "zprel")

_LEN = {"imp": 1, "a": 1, "imm": 2, "zp": 2, "zpx": 2, "zpy": 2, "abs": 3, "abx": 3, "aby": 3, "ind": 3, "inx": 2,
        "iny": 2, "izp": 2, "rel": 2, "iax": 3, "blk": 7, "tzp": 3, "tzpx": 3, "tabs": 4, "tabsx": 4, "zprel": 3}


def one(d, i, pc):
    """-> (length, text) for the instruction at d[i] whose address is pc."""
    op = d[i]
    if op not in _M:
        return 1, f".db ${op:02X}"
    mn, mode = _M[op]
    n = _LEN[mode]
    if i + n > len(d):                          # an operand running off the end of the bank is data
        return 1, f".db ${op:02X}"
    b = d[i + 1:i + n]
    w = lambda k=0: b[k] | (b[k + 1] << 8)
    if mode in ("imp", "a"):
        arg = "" if mode == "imp" else "a"
    elif mode == "imm":
        arg = f"#${b[0]:02X}"
    elif mode == "zp":
        arg = f"<${b[0]:02X}"
    elif mode == "zpx":
        arg = f"<${b[0]:02X},x"
    elif mode == "zpy":
        arg = f"<${b[0]:02X},y"
    elif mode == "abs":
        arg = f"${w():04X}"
    elif mode == "abx":
        arg = f"${w():04X},x"
    elif mode == "aby":
        arg = f"${w():04X},y"
    elif mode == "ind":
        arg = f"[${w():04X}]"
    elif mode == "iax":
        arg = f"[${w():04X},x]"
    elif mode == "inx":
        arg = f"[<${b[0]:02X},x]"
    elif mode == "iny":
        arg = f"[<${b[0]:02X}],y"
    elif mode == "izp":
        arg = f"[<${b[0]:02X}]"
    elif mode == "rel":
        arg = f"${(pc + 2 + (b[0] - 256 if b[0] > 127 else b[0])) & 0xFFFF:04X}"
    elif mode == "zprel":
        arg = f"<${b[0]:02X},${(pc + 3 + (b[1] - 256 if b[1] > 127 else b[1])) & 0xFFFF:04X}"
    elif mode == "blk":
        arg = f"${w():04X},${w(2):04X},${w(4):04X}"
    elif mode == "tzp":
        arg = f"#${b[0]:02X},<${b[1]:02X}"
    elif mode == "tzpx":
        arg = f"#${b[0]:02X},<${b[1]:02X},x"
    elif mode == "tabs":
        arg = f"#${b[0]:02X},${w(1):04X}"
    else:
        arg = f"#${b[0]:02X},${w(1):04X},x"
    return n, f"{mn} {arg}".rstrip()


def dis(d, org, start=0, end=None):
    """-> [(address, bytes, text)] for d[start:end] loaded at org."""
    out, i = [], start
    end = len(d) if end is None else end
    while i < end:
        n, text = one(d, i, org + i)
        out.append((org + i, d[i:i + n], text))
        i += n
    return out


def main():
    iso, off, org, length = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0), int(sys.argv[4], 0)
    d = open(iso, "rb").read()[off:off + length]
    for a, b, t in dis(d, org):
        print(f"{a:04X}  {b.hex(' '):<20} {t}")


if __name__ == "__main__":
    main()
