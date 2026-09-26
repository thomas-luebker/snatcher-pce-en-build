#!/usr/bin/env python3
"""The title menu in English: the lettering written into VRAM while the title is on screen.

The pixels cannot be put on the disc. 初めから is three sprites (see docs/FINDINGS.md) whose patterns come
out of the compressed title screen, and four of the sixteen planes are not literal runs, so there is
nothing to overwrite. They are written into VRAM at runtime instead.

Where the pieces go:

  ISO 0x1DF230 ($8230)  the routine     | inside the title screen's own load -- 23 sectors from LBA 958
  ISO 0x1DF400 ($8400)  3,200 bytes     | into bank $6C, which holds 7,632 bytes of $FF there. Checked in
                        of patterns     | two save states: still $FF in RAM while the title is up.
  ISO 0x00CBEC ($5BEC)  a 17-byte stub  | engine bank $68, after the resident loader_hook ($5BB3-$5BEB)

The hook is `jsr $8006` in scene_01_handler ($4542). Engine state $01 **is** the title -- read out of the
save states, which have $18 = 1 at the title and 5 or 3 in play -- so this runs at the title and nowhere
else, and bank $6C holds the title block every time (checked in all three title states). The stub calls
the displaced $8006 first, maps $6C over MPR4, calls the routine and puts MPR4 back from the stack, since
bank_switch_3 computes it from $3F80 and it is not a constant.

The routine fires once: it goes ahead only while VRAM $6780 still reads $0253, the first word of 初, which
is false the moment it has written its own pixels there. Handing the VDC 640 words takes longer than the
blanking interval and the VDC drops VRAM writes during active display, so it blanks the picture through
the game's own CR shadow (ZP $28/$29) and restores it after -- one frame, once, while the title fades in.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import snhack  # noqa: E402
import title_text  # noqa: E402

BLOCK_ISO, BLOCK_ORG = 0x1DF000, 0x8000       # the title load: LBA 958 -> bank $6C at MPR4
CODE_ORG, DATA_ORG = 0x8230, 0x8400     # the routine is 240 bytes, so the pixels start a page clear of it
STUB_ORG, STUB_ISO, STUB_ROOM = 0x5BEC, 0x00CBEC, 20
HOOK_ISO, HOOK_OLD = 0x00B542, bytes.fromhex("200680")   # `jsr $8006` in scene_01_handler
TEXT = (("NEW GAME", "new"), ("CONTINUE", "continue"))
JP_FIRST = (0x53, 0x02)                       # VRAM $6780 word 0 of 初 -- the "not done yet" signal
AR, DL, DH = 0x0000, 0x0002, 0x0003           # VDC address register and data port (absolute, not ZP)
CR_LO, CR_HI = 0x28, 0x29                     # the game's own CR shadow, in zero page


def cells(text=TEXT):
    """Every 16x16 pattern cell both menu lines are built from, as {vram address: 64 words}."""
    out = {}
    for words, row in text:
        out.update(title_text.patterns(words, row))
    return out


def runs(pats):
    """The cells grouped into stretches that are contiguous in VRAM, so each is one run of bytes.

    They do not form one block: the cells belong to seven sprites scattered over $6680-$6EC0, and what
    sits between them belongs to something else -- $6E80 holds six non-zero words of another sprite, so
    the 16x32 sprite's two halves are written as two runs of one rather than as three cells.
    """
    out = []
    for a in sorted(pats):
        if out and a == out[-1][0] + out[-1][1] * 0x40:
            out[-1][1] += 1
        else:
            out.append([a, 1])
    return [tuple(r) for r in out]


def data(pats, order):
    """The patterns as one block, in run order, so the routine can stream each run straight at the VDC."""
    out = bytearray()
    for start, n in order:
        for i in range(n):
            for w in pats[start + i * 0x40]:
                out += w.to_bytes(2, "little")
    assert len(out) == sum(n for _, n in order) * 128, len(out)
    return bytes(out)


def routine(order):
    a = snhack.Asm(CODE_ORG)
    st = lambda addr: (0x8D, addr & 0xFF, addr >> 8)              # sta abs
    ld = lambda addr: (0xAD, addr & 0xFF, addr >> 8)              # lda abs
    reg = lambda n: (0xA9, n) + st(AR)                            # select a VDC register

    a.b(*reg(1), 0xA9, 0x80, *st(DL), 0xA9, 0x67, *st(DH))        # MARR = $6780
    a.b(*reg(2))
    a.b(*ld(DL), 0xC9, JP_FIRST[0]); a.r(0xD0, "out")             # already English? then nothing to do
    a.b(*ld(DH), 0xC9, JP_FIRST[1]); a.r(0xF0, "go")
    a.label("out")
    a.b(0x60)
    a.label("go")
    a.b(*reg(5), 0xA5, CR_LO, 0x29, 0x3F, *st(DL), 0xA5, CR_HI, *st(DH))   # blank: CR without BG/SPR
    src = lambda addr: (0xB9, addr & 0xFF, addr >> 8)             # lda abs,y
    at = DATA_ORG
    for i, (start, n) in enumerate(order):
        a.b(*reg(0), 0xA9, start & 0xFF, *st(DL), 0xA9, start >> 8, *st(DH))   # MAWR = first cell
        a.b(*reg(2))
        left, page = n * 128, 0
        while left:                                               # at most 256 bytes a block, Y indexes it
            n = min(256, left)
            a.b(0xA0, 0x00)
            a.label(f"blk{i}_{page}")
            a.b(*src(at), *st(DL), 0xC8, *src(at), *st(DH), 0xC8)
            if n < 256:
                a.b(0xC0, n)                                      # cpy #n -- a full block leaves on Y wrapping
            a.r(0xD0, f"blk{i}_{page}")
            at += n; left -= n; page += 1
    a.b(*reg(5), 0xA5, CR_LO, *st(DL), 0xA5, CR_HI, *st(DH))      # picture back on
    a.b(0x60)
    return a.link()


def stub():
    a = snhack.Asm(STUB_ORG)
    a.b(0x20, HOOK_OLD[1], HOOK_OLD[2])                           # jsr $8006 -- the call we displaced
    a.b(0x43, 0x10, 0x48)                                         # tma #$10 ; pha
    a.b(0xA9, 0x6C, 0x53, 0x10)                                   # lda #$6C ; tam #$10
    a.b(0x20, CODE_ORG & 0xFF, CODE_ORG >> 8)                     # jsr routine
    a.b(0x68, 0x53, 0x10, 0x60)                                   # pla ; tam #$10 ; rts
    return a.link()


def patch(iso, text=TEXT):
    pats = cells(text)
    order = runs(pats)
    code, blob, hook = routine(order), data(pats, order), stub()
    assert len(hook) <= STUB_ROOM, f"stub is {len(hook)} bytes, {STUB_ROOM} free"
    assert bytes(iso[HOOK_ISO:HOOK_ISO + 3]) == HOOK_OLD, "scene_01_handler does not look as expected"
    code_at = BLOCK_ISO + CODE_ORG - BLOCK_ORG
    data_at = BLOCK_ISO + DATA_ORG - BLOCK_ORG
    for at, part in ((code_at, code), (data_at, blob), (STUB_ISO, hook)):
        assert all(b == 0xFF for b in iso[at:at + len(part)]), f"{at:#08x} is not free"
        iso[at:at + len(part)] = part
    iso[HOOK_ISO:HOOK_ISO + 3] = bytes([0x20, STUB_ORG & 0xFF, STUB_ORG >> 8])
    return (f"title: {' / '.join(t for t, _ in text)}, {len(code)} bytes of code + {len(blob)} of "
            f"pixels ({len(pats)} cells in {len(order)} runs) in the title's own load")


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    iso = bytearray(open("disc/track02.iso", "rb").read())
    print(patch(iso))


if __name__ == "__main__":
    main()
