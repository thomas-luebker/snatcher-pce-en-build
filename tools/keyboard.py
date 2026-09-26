#!/usr/bin/env python3
"""An English keyboard for the game's own name-entry screen.

  keyboard.py            -> patch disc/track02.iso in memory and print what changed

The screen Gillian types a name on (Gibson's computer; the reception asking your name) is driven by an
overlay, not by the scene -- the scene only supplies the dictionary. Inside the overlay the engine
keeps ONE byte per character and expands it when it needs Shift-JIS:

    code < $20   ->  $81 <code + $40>     punctuation
    code $20-$3F ->  $82 <code + $1F>     digits and symbols
    code >= $40  ->  $83 <code>           katakana

which is why English could not just be typed: full-width Latin ($82 60..79) would need codes $41-$5A,
and those are katakana. The keys are a 12-column grid of these codes ($00 empty, $01 the cell a key
spills into, $02-$1B function keys), one grid per keyboard: a digit keypad for the videophone and
Katrina's door, a kana grid for names. Which grid is used comes from $351F, and the engine sets that
from the first character of the scene's first key word.

So this patch does two things to every copy of the overlay on a track:

  * it teaches the expander a fourth range, $A0-$B9 -> $82 60..79, i.e. Ａ-Ｚ. Added, not swapped:
    digits, kana and punctuation keep their codes, so the videophone and the door quiz are untouched.
    The new code goes in the overlay's own tail padding, which is zero on disc and still zero in RAM
    while the screen runs (checked in the emulator before this was written).
  * it rewrites the kana grid as A-Z, five to a row, in the cells the kana rows had.

The dictionary stays as tools/namesearch.py writes it: full-width Latin, which is what typing now
produces. That file also keeps a katakana character in front of the first key word, so the engine
still picks this grid.

Nothing here is looked up by a fixed offset: the overlay is found by the expander's own bytes, and its
addresses are read out of the pointer table that sits beside the grids.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import snhack  # noqa: E402

ENC = bytes.fromhex("b99036c940b011")            # lda $3690,Y ; cmp #$40 ; bcs kana
SIG = bytes.fromhex("82c2c010f035") + ENC        # ...with the loop head in front, to be sure
TAIL = bytes.fromhex("e89d3e36e8c880")           # inx ; sta $363E,X ; inx ; iny ; bra loop
KANA_ROW = bytes.fromhex("4143454749")           # ア イ ウ エ オ, the grid's first row of keys
ROW_IN_GRID = 25                                 # where that row sits inside the grid
PTRS_AFTER_GRID = 0xF0                           # and where the grid pointers sit after it
LATIN0, LETTERS = 0xA0, 26                       # Ａ..Ｚ as codes $A0..$B9
NEED = 32                                        # bytes of padding the new code wants


# The keys the player sees are not text: they are a picture, decompressed into VRAM with the rest of
# the computer screen, and the tiles are shared between keys that look alike, so they cannot simply be
# overwritten. Instead the panel's map cells are pointed at tiles of our own, drawn into VRAM whenever
# the keyboard opens -- 8x8 letters in the cells the kana had, in the order the engine types them.
GLYPHS = {
    "A": (".XXX.", "X...X", "X...X", "XXXXX", "X...X", "X...X"),
    "B": ("XXXX.", "X...X", "XXXX.", "X...X", "X...X", "XXXX."),
    "C": (".XXX.", "X...X", "X....", "X....", "X...X", ".XXX."),
    "D": ("XXXX.", "X...X", "X...X", "X...X", "X...X", "XXXX."),
    "E": ("XXXXX", "X....", "XXXX.", "X....", "X....", "XXXXX"),
    "F": ("XXXXX", "X....", "XXXX.", "X....", "X....", "X...."),
    "G": (".XXX.", "X....", "X....", "X..XX", "X...X", ".XXX."),
    "H": ("X...X", "X...X", "XXXXX", "X...X", "X...X", "X...X"),
    "I": ("XXXXX", "..X..", "..X..", "..X..", "..X..", "XXXXX"),
    "J": ("..XXX", "...X.", "...X.", "...X.", "X..X.", ".XX.."),
    "K": ("X...X", "X..X.", "XXX..", "X..X.", "X...X", "X...X"),
    "L": ("X....", "X....", "X....", "X....", "X....", "XXXXX"),
    "M": ("X...X", "XX.XX", "X.X.X", "X...X", "X...X", "X...X"),
    "N": ("X...X", "XX..X", "X.X.X", "X..XX", "X...X", "X...X"),
    "O": (".XXX.", "X...X", "X...X", "X...X", "X...X", ".XXX."),
    "P": ("XXXX.", "X...X", "X...X", "XXXX.", "X....", "X...."),
    "Q": (".XXX.", "X...X", "X...X", "X.X.X", "X..X.", ".XX.X"),
    "R": ("XXXX.", "X...X", "XXXX.", "X..X.", "X...X", "X...X"),
    "S": (".XXXX", "X....", ".XXX.", "....X", "X...X", ".XXX."),
    "T": ("XXXXX", "..X..", "..X..", "..X..", "..X..", "..X.."),
    "U": ("X...X", "X...X", "X...X", "X...X", "X...X", ".XXX."),
    "V": ("X...X", "X...X", "X...X", "X...X", ".X.X.", "..X.."),
    "W": ("X...X", "X...X", "X...X", "X.X.X", "XX.XX", "X...X"),
    "X": ("X...X", ".X.X.", "..X..", "..X..", ".X.X.", "X...X"),
    "Y": ("X...X", ".X.X.", "..X..", "..X..", "..X..", "..X.."),
    "Z": ("XXXXX", "....X", "...X.", "..X..", ".X...", "XXXXX"),
}
VARS = ("curlo", "curhi", "rows", "cnt", "wlo", "whi", "flag", "left", "rowlo", "rowhi")
ROWS = 6
DATA_BANK = 0x82                                 # where our block lives, and with it the letters
DISP = 0x0C                                      # the screen's control register with the picture off                                         # pixel rows per letter; the eighth is blank
TILE_A, TILE_B = 0x1F0, 0x6F0                    # two runs of VRAM tiles this screen leaves unused
BLANK = TILE_B + 10                              # and one more for the empty halves
CELLS, GAPS = 24, (5, 11, 17)                    # cells across a row of keys, and the gaps between groups
PANEL = 33 * 64 + 4                              # the map address of the first key cell (row 33, column 4)


def masks():
    out = bytearray()
    for c in sorted(GLYPHS):
        for r in range(ROWS):
            row = GLYPHS[c][r]
            m = 0
            for x, ch in enumerate(row):
                if ch == "X":
                    m |= 1 << (7 - x)
            out.append(m)
    return bytes(out)


def _draw(org, letters_at, vars_at, fetch_at):
    """Put our letters on the keys, assembled to run at `org` inside the overlay.

    The keys are tiles of a decompressed picture, and tiles are shared between keys that look alike, so
    the routine invents no tiles: for every cell of the panel it reads the tile number out of the map and
    draws into that tile. Sharing then works in our favour -- every lower half is blanked, which is what
    we want -- and nothing but pixels changes. Ink is colour 0 on the panel's colour 13, as the kana are.
    """
    f = snhack.Asm(fetch_at)                             # A = row Y of the letter, or nothing
    f.labels.update({v: vars_at + i for i, v in enumerate(VARS)})
    f.w(0xAD, "flag"); f.r(0xF0, "none")
    f.b(0xC0, ROWS); f.r(0xB0, "none")
    f.label("src"); f.w(0xB9, letters_at); f.b(0x60)
    f.label("none"); f.b(0xA9, 0x00, 0x60)
    # VRAM can only be written while the picture is off: the VDC drops writes during display, which
    # tore the panel apart when this ran with the screen up.
    f.label("off"); f.b(0x03, 0x05, 0x13, DISP & 0xFF, 0x23, 0x00, 0x60)
    f.label("on"); f.b(0x03, 0x05, 0x13, (DISP | 0xC0) & 0xFF, 0x23, 0x00)
    f.b(0x03, 0x00, 0x60)                                # leave a harmless register selected
    helpers = f.link()

    a = snhack.Asm(org)
    a.labels.update({k: v for k, v in f.labels.items()})
    a.label("draw")
    a.w(0x8D, 0x351F)                                    # the store we replaced: the keyboard's kind
    a.b(0xC9, 0x03); a.r(0xF0, "ours")                   # letters only on the one for names
    a.b(0x60)
    a.label("ours")
    a.b(0x48, 0x08, 0x78)                                # pha ; php ; sei -- the caller wants these back
    a.b(0x43, 0x10, 0x48)                                # tma #$10 ; pha: borrow $8000 for our block
    a.b(0xA9, DATA_BANK, 0x53, 0x10)
    a.w(0x20, "off")
    a.imm(0xA9, "glyphs", "lo"); a.w(0x8D, "src", 1)     # the glyph read is self-modifying
    a.imm(0xA9, "glyphs", "hi"); a.w(0x8D, "src", 2)
    a.b(0xA9, PANEL & 0xFF); a.w(0x8D, "curlo")
    a.b(0xA9, PANEL >> 8); a.w(0x8D, "curhi")
    a.b(0xA9, 0x06); a.w(0x8D, "rows")                   # three lines of keys: tops and bottoms
    a.b(0x82)                                            # clx: letters drawn so far
    a.label("row")
    a.b(0xA9, 0x05); a.w(0x8D, "cnt")
    a.w(0xAD, "rows"); a.b(0xC9, 0x03); a.r(0xB0, "wide")   # the bottom row keeps its right-hand
    a.b(0xA9, CELLS // 2); a.r(0x80, "setleft")             # groups: ゛ ゜ and 決定, still Enter
    a.label("wide"); a.b(0xA9, CELLS)
    a.label("setleft"); a.w(0x8D, "left")
    a.w(0xAD, "curlo"); a.w(0x8D, "rowlo")               # remember where this row began
    a.w(0xAD, "curhi"); a.w(0x8D, "rowhi")
    a.label("cell")
    a.b(0x03, 0x01)                                      # st0 #1: MARR, to read this cell's tile
    a.w(0xAD, "curlo"); a.w(0x8D, 0x0002)
    a.w(0xAD, "curhi"); a.w(0x8D, 0x0003)
    a.b(0x03, 0x02)
    a.w(0xAD, 0x0002); a.w(0x8D, "wlo")
    a.w(0xAD, 0x0003); a.b(0x29, 0x0F); a.w(0x8D, "whi")
    for _ in range(4):                                   # tile * 16 = where its pixels live
        a.w(0x0E, "wlo"); a.w(0x2E, "whi")
    a.b(0x03, 0x00)                                      # st0 #0: MAWR
    a.w(0xAD, "wlo"); a.w(0x8D, 0x0002)
    a.w(0xAD, "whi"); a.w(0x8D, 0x0003)
    a.b(0x03, 0x02)                                      # st0 #2: and write pixels from here on
    a.w(0x9C, "flag")                                    # blank unless this cell earns a letter
    a.w(0xAD, "rows"); a.b(0x4A); a.r(0xB0, "paint")     # the lower half of a key is always blank
    a.w(0xAD, "cnt"); a.r(0xD0, "iskey")
    a.b(0xA9, 0x05); a.w(0x8D, "cnt"); a.r(0x80, "paint")   # the gap between two groups of keys
    a.label("iskey")
    a.w(0xCE, "cnt")
    a.b(0xE0, 26); a.r(0xB0, "paint")                    # only 26 keys carry a letter
    a.b(0xE8); a.b(0xA9, 0x01); a.w(0x8D, "flag")
    a.label("paint")
    a.b(0xC2)                                            # cly
    a.label("d1")                                        # planes 0 and 1
    a.w(0x20, "fetch"); a.b(0x49, 0xFF); a.w(0x8D, 0x0002); a.w(0x9C, 0x0003)
    a.b(0xC8, 0xC0, 0x08); a.r(0xD0, "d1")
    a.b(0xC2)
    a.label("d2")                                        # planes 2 and 3
    a.w(0x20, "fetch"); a.b(0x49, 0xFF); a.w(0x8D, 0x0002); a.w(0x8D, 0x0003)
    a.b(0xC8, 0xC0, 0x08); a.r(0xD0, "d2")
    a.w(0xAD, "flag"); a.r(0xF0, "nextcell")             # a letter was drawn: step over it
    a.b(0x18); a.w(0xAD, "src", 1); a.b(0x69, ROWS); a.w(0x8D, "src", 1); a.r(0x90, "nextcell")
    a.w(0xEE, "src", 2)
    a.label("nextcell")
    a.w(0xEE, "curlo"); a.r(0xD0, "same"); a.w(0xEE, "curhi")
    a.label("same")
    a.w(0xCE, "left"); a.r(0xF0, "rowdone"); a.w(0x4C, "cell")   # too long for a branch
    a.label("rowdone")
    a.b(0x18); a.w(0xAD, "rowlo"); a.b(0x69, 64); a.w(0x8D, "curlo")   # on to the next map row
    a.w(0xAD, "rowhi"); a.b(0x69, 0x00); a.w(0x8D, "curhi")
    a.w(0xCE, "rows"); a.r(0xF0, "alldone"); a.w(0x4C, "row")
    a.label("alldone")
    a.w(0x20, "on")
    a.b(0x68, 0x53, 0x10)                                # give $8000 back
    a.b(0x28, 0x68, 0x60)                                # plp ; pla ; rts

    a.labels["glyphs"] = letters_at
    for i, v in enumerate(VARS):                         # the variables live in another gap
        a.labels[v] = vars_at + i
    a.labels["fetch"] = fetch_at                         # the helpers' own labels came in above
    code = a.link()

    f = snhack.Asm(fetch_at)                             # A = row Y of the letter, or nothing
    f.labels.update({v: vars_at + i for i, v in enumerate(VARS)})
    f.w(0xAD, "flag"); f.r(0xF0, "none")
    f.b(0xC0, ROWS); f.r(0xB0, "none")
    f.label("src"); f.w(0xB9, letters_at); f.b(0x60)
    f.label("none"); f.b(0xA9, 0x00, 0x60)
    # VRAM can only be written safely while the picture is off: the VDC drops writes during display,
    # which tore the panel apart when this ran with the screen up.
    f.label("off"); f.b(0x03, 0x05, 0x13, DISP & 0xFF, 0x23, 0x00, 0x60)
    f.label("on"); f.b(0x03, 0x05, 0x13, (DISP | 0xC0) & 0xFF, 0x23, 0x00)
    f.b(0x03, 0x00, 0x60)                                # leave a harmless register selected
    return code, helpers, a.labels["draw"], letters_at, f.labels["off"], f.labels["on"]


def copies(iso):
    out, i = [], -1
    while True:
        i = iso.find(SIG, i + 1)
        if i < 0:
            return out
        out.append(i + SIG.index(ENC))


def _map(iso, enc):
    """-> (offset -> CPU address, grid offset) for the copy holding `enc`.

    The overlay is loaded at a different address in each copy, so the address is read out of the copy
    itself: the pointer the engine uses to reach this grid IS the grid's address."""
    lo = max(0, enc - 0x3000)
    row = iso.rfind(KANA_ROW, lo, enc)
    assert row > 0, "the kana row is not in front of the expander"
    grid = row - ROW_IN_GRID
    base = int.from_bytes(iso[grid + PTRS_AFTER_GRID + 6:grid + PTRS_AFTER_GRID + 8], "little")
    assert 0x8000 <= base < 0xE000, f"grid pointer {base:#06x} is not an address"
    return (lambda o, b=base, ref=grid: b + (o - ref)), grid


HOOK = bytes.fromhex("8d1f35")                   # sta $351F -- the keyboard's kind being chosen, which
                                                 # happens once when it opens (the routine that picks the
                                                 # layout runs every frame, and drawing there tore the
                                                 # screen up mid-display)


def _room(iso, at):
    n = 0
    while iso[at + n] == 0:
        n += 1
    return n


def _gaps(iso, enc):
    """The overlay's two smaller stretches of padding, for the pieces that do not fit beside the rest."""
    out, i = [], enc - 0x2000
    while i < enc:
        if iso[i] == 0:
            j = i
            while iso[j] == 0:
                j += 1
            if 16 <= j - i < 200:
                out.append(i)
            i = j
        else:
            i += 1
    assert len(out) >= 2, "the overlay has nowhere to put the row fetcher"
    return out


def _free(iso, enc, cpu):
    """The overlay's tail padding: the first long run of zeros after the expander."""
    i = enc
    while i < enc + 0x2000:
        if iso[i] == 0 and iso[i:i + NEED] == bytes(NEED):
            j = i
            while iso[j] == 0:
                j += 1
            if j - i >= NEED:
                return i
            i = j
        i += 1
    raise AssertionError("no padding in the overlay for the new code")


# Drawing our letters onto the keys hangs off the store that chooses the keyboard -- the routine that
# picks the layout runs every frame, and drawing there tore the screen apart. The letters themselves
# live in our own block in bank $82, which this maps in while it needs them: the overlay's padding has
# no room for them, and the store's caller wants its registers back untouched.
DRAW_KEYS = True


def patch(iso, letters_at=0):
    """-> (patched track, one-line report). `letters_at` is where our block keeps the letter shapes."""
    iso = bytearray(iso)
    done = []
    for enc in copies(iso):
        cpu, kana = _map(iso, enc)
        plain = enc + 7                                        # cmp #$20 ...
        kana_case = enc + 7 + iso[enc + 6]                     # the `bcs` target
        store = iso.find(TAIL, enc, enc + 0x80)
        assert store > 0, "the expander's tail is not where it should be"
        free = _free(iso, enc, cpu)
        a, b, c = cpu(kana_case), cpu(plain), cpu(store)
        code = bytes([0xB9, 0x90, 0x36,                        # lda $3690,Y
                      0xC9, LATIN0, 0xB0, 0x0B,                # cmp #$A0 ; bcs latin
                      0xC9, 0x40, 0x90, 0x03,                  # cmp #$40 ; bcc plain
                      0x4C, a & 0xFF, a >> 8,                  # jmp kana
                      0x4C, b & 0xFF, b >> 8,                  # jmp plain
                      0xEA,
                      0xA9, 0x82,                              # latin: lda #$82
                      0x9D, 0x3E, 0x36,                        # sta $363E,X   (the lead byte)
                      0xB9, 0x90, 0x36,                        # lda $3690,Y
                      0x18, 0x69, 0xC0,                        # clc ; adc #$C0     = code - $40
                      0x4C, c & 0xFF, c >> 8])                 # jmp store
        assert len(code) == NEED
        iso[free:free + NEED] = code
        f = cpu(free)
        iso[enc:enc + 7] = bytes([0x4C, f & 0xFF, f >> 8, 0xEA, 0xEA, 0xEA, 0xEA])
        n = _letters(iso, kana)
        # and put our letters on the keys: the panel is a picture, so they are drawn into its tiles
        # every time the keyboard opens, from a routine hung on the call that sets the window up.
        if not DRAW_KEYS:
            done.append((enc, f, n, False))
            continue
        # Everything goes in the overlay's one genuine tail run. The two shorter zero runs before the
        # expander are not padding: they are the wall rows of the two keyboard grids -- $00 cells the
        # cursor may not enter. Code put there became keys: the cursor could walk below the 0 on the
        # videophone keypad and type whatever byte of our display-off helper it landed on (hardware,
        # 22 Sep: "entering numbers does not really work well").
        main_at = free + NEED
        probe, fprobe, *_ = _draw(cpu(main_at), letters_at, 0, 0)     # only the sizes are wanted
        if len(probe) + len(fprobe) + len(VARS) > _room(iso, main_at):
            done.append((enc, f, n, False))                 # this copy has no room; only one needs it
            continue
        fetch_at = main_at + len(probe)
        vars_at = fetch_at + len(fprobe)
        sites = []
        i = enc - 0x4000
        while True:
            i = iso.find(HOOK, i + 1, enc)
            if i < 0:
                break
            sites.append(i)
        if not sites:                                      # only the copy the game loads has this shape
            done.append((enc, f, n, False))
            continue
        site = sites[-1]
        code2, fetch, entry, _, _, _ = _draw(cpu(main_at), letters_at, cpu(vars_at), cpu(fetch_at))
        if len(code2) > _room(iso, main_at) or len(fetch) > _room(iso, fetch_at) \
                or len(VARS) > _room(iso, vars_at):
            done.append((enc, f, n, False))                 # this copy has no room; only one needs it
            continue
        iso[main_at:main_at + len(code2)] = code2
        iso[fetch_at:fetch_at + len(fetch)] = fetch
        iso[site:site + 3] = bytes([0x20, entry & 0xFF, entry >> 8])   # jsr us instead of the store
        done.append((enc, f, n, True))
    assert done, "the name-entry overlay is not on this track"
    assert not DRAW_KEYS or any(d[3] for d in done), "no copy of the overlay takes the letters"
    return bytes(iso), ("keyboard: " + ", ".join(
        f"{n} keys at ${f:04X}" + (" with letters drawn" if drawn else "") for _, f, n, drawn in done))


def _letters(iso, kana):
    """Put A-Z in the first 26 cells the kana rows had, and make the rest transparent.

    The cursor code ($B903 in the overlay) treats a cell of $00 as a wall -- the move is cancelled -- and
    $01 as glass: it keeps stepping until it reaches a real key. The leftover kana cells used to keep their
    codes so the cursor could still reach 決定, which made them invisible keys: drawn blank, but a press
    on one typed ラ or リ into the field. Thomas found that on hardware, heading down towards 決定 and
    coming away with リルレレレレ. As $01 they can be crossed but never landed on, and 決定 ($08), the
    backspace ($1B) and the ゛゜ keys keep their codes.
    """
    n = 0
    for i in range(kana, kana + 0xB0):
        if iso[i] >= 0x40:                                     # a character cell, not a blank or a key
            iso[i] = LATIN0 + n if n < LETTERS else 0x01
            n += 1
    return min(n, LETTERS)


def main():
    iso = open("disc/track02.iso", "rb").read()
    data, report = patch(iso)
    print(report)
    data = bytearray(data)
    for enc in copies(data):
        _, kana = _map(data, enc)
        rows = [data[kana + r:kana + r + 12] for r in range(-24, 0xA0, 12)]
        for row in rows:
            line = "".join(chr(ord("A") + b - LATIN0) + " " if LATIN0 <= b < LATIN0 + LETTERS
                           else ("  " if b in (0, 1) else "* ") for b in row)
            if line.strip():
                print("   ", line)
        break


if __name__ == "__main__":
    main()
