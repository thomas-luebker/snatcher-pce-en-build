#!/usr/bin/env python3
"""English "cell" text for Snatcher PCE: two 6-pixel letters per 12-pixel character cell.

The game draws 12x12 kanji cells, 18 per line. A cell is an SJIS pair; we redefine the kanji lead bytes
$88-$9F and $E0-$F7 (48 leads x 191 usable trails = 9168 codes; the print loop takes $15-$F7 as a lead) as letter pairs, drawn by the renderer hook in
tools/snhack.py:

    k = lead - $88  (or lead - $E0 + 24),  n = k * 191 + (trail - $40)      trail $FF is never used:
    the game takes it as the end of a menu word / speaker name
    left = GLYPHS[n // G1], right = GLYPHS[n % G1]        G1 = number of glyphs + 1, last index = BLANK

Every glyph pairs with every other, so there are no gaps. 36 letters per line, 3 lines per page.
Japanese kanji use the same code range: text that is still Japanese shows as letter pairs.
"""
import textwrap

BLANK = "\x00"
GLYPHS = (" eoatihnrslucmdwp'ygbfvT.IkASONEHWCGRYMJDLPU-B\"KjqVx" + "Fz0123456789!?(),:QZX/#;" + "%&+*=~_[]<>$@")
G1 = len(GLYPHS) + 1
CELLS_PER_LINE, LINES_PER_PAGE = 18, 3
TRAILS = 191                             # trail byte $40..$FE; $FF is the game's string terminator
assert len(set(GLYPHS)) == len(GLYPHS) and G1 * G1 <= 48 * TRAILS


def sjis(n):
    k, t = divmod(n, TRAILS)
    return bytes([0x88 + k if k < 24 else 0xE0 + k - 24, 0x40 + t])


def normalise(text):
    return "".join(c if c in GLYPHS else "?" for c in text)


def cells(line):
    """One line of ASCII -> list of cell numbers."""
    line = normalise(line)
    idx = [GLYPHS.index(c) for c in line]
    if len(idx) % 2:
        idx.append(G1 - 1)
    return [idx[i] * G1 + idx[i + 1] for i in range(0, len(idx), 2)]


def wrap(text):
    return textwrap.wrap(text, CELLS_PER_LINE * 2, break_long_words=True) or [""]


def sjis_plain(text):
    """Cells as plain 2-byte SJIS (menu words, speaker names)."""
    return b"".join(sjis(n) for n in cells(text))
