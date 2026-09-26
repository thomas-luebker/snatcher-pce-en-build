#!/usr/bin/env python3
"""English lettering for the title menu, as sprite patterns.

  title_text.py preview work/title_en.png            -> what the words look like
  title_text.py state IN OUT ["NEW GAME"]            -> patch a save state's VRAM and see it in the game

初めから is three sprites, not four -- two 32x32 and one 16x32, side by side at y=144: **80x32 pixels**
in all, with the kana sitting low in it. セーブした所から sits under it at y=176 and is wider: three 32x32
sprites, a 32x16 and a 16x16, and the sprite that would carry the last cell's bottom half is parked off
screen, so that corner cannot be drawn at all and the English is fitted into the seven columns before it.
See ROWS below for how all that maps onto 16x16 pattern cells.

The two rows use **different colour indices for the same look**: palette 3 is palette 1 with the blues
rotated, so 初めから is drawn in $D/$E and セーブした所から in $C/$F. The game swaps palettes to highlight
the selected line, so each row's English keeps the indices its own kana used -- anything else changes
colour when the cursor moves.

The pixels cannot be rewritten on disc: of the sixteen planes the bottom cells are made of, four are not
literal runs inside the compressed title screen, and none of the top cells is (see docs/FINDINGS.md). So
these patterns are written into VRAM at runtime instead, and this module is where they are drawn.

The lettering copies the original's material rather than inventing one: white along the top of each
stroke, blue below it, over a dark gold edge.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

# Read out of the sprite table (VRAM $1000) with a save on the card, so both lines are on screen. A
# 32x32 sprite's four cells are +$00 top-left, +$40 top-right, +$80 bottom-left, +$C0 bottom-right;
# each column below is (top cell, bottom cell).
ROWS = {
    # 初めから: $6700 and $6800 at x=80 and 112 (32x32), $6E40 at x=144 (16x32). Five columns.
    "new": dict(
        cells=[(0x6700, 0x6780), (0x6740, 0x67C0), (0x6800, 0x6880), (0x6840, 0x68C0), (0x6E40, 0x6EC0)],
        blank=[], outline=0x02, body=0x0E, hilight=0x0D),
    # セーブした所から: $6900, $6A00, $6D00 (32x32) at x=80/112/144, $6680 (32x16) at x=176 and $6E00
    # (16x16) at x=176 y=192. That leaves the eighth column with a top cell ($66C0) but no bottom -- its
    # sprite is parked at x=-64 -- so the English uses the seven columns that are whole and $66C0 is
    # cleared, which is what removes the tail of ら from the end of the line.
    "continue": dict(
        cells=[(0x6900, 0x6980), (0x6940, 0x69C0), (0x6A00, 0x6A80), (0x6A40, 0x6AC0),
               (0x6D00, 0x6D80), (0x6D40, 0x6DC0), (0x6680, 0x6E00)],
        blank=[0x66C0], outline=0x02, body=0x0F, hilight=0x0C),
}
H = 32
FONT = "/System/Library/Fonts/Monaco.ttf"
TOP = 10                                       # first pixel row of the lettering, matching where the kana sit


def mask(text, W, size):
    """The letters as a 1-bit image W x H, centred, at the largest size that still fits."""
    for pt in range(size, 5, -1):
        f = ImageFont.truetype(FONT, pt)
        img = Image.new("1", (W, H), 0)
        d = ImageDraw.Draw(img)
        d.fontmode = "1"                       # no antialiasing: every pixel is on or off
        lo, up, hi, dn = d.textbbox((0, 0), text, font=f)
        if hi - lo <= W - 2 and dn - up <= H - TOP - 1:
            d.text(((W - (hi - lo)) // 2 - lo, TOP - up), text, font=f, fill=1)
            return img, pt
    raise SystemExit(f"{text!r} does not fit in {W}x{H}")


def draw(text, row="new", size=20):
    """-> a W x H list of rows of colour indices, outlined and shaded like that row's own kana."""
    r = ROWS[row]
    W = 16 * len(r["cells"])
    OUTLINE, BODY, HILIGHT = r["outline"], r["body"], r["hilight"]
    img, _ = mask(text, W, size)
    on = img.load()
    px = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if not on[x, y]:
                continue
            # white along the top edge of each stroke, blue below it: the bevel the kana are drawn with
            px[y][x] = HILIGHT if y == 0 or not on[x, y - 1] else BODY
    for y in range(H):                          # a one-pixel dark edge, drawn around what is already there
        for x in range(W):
            if px[y][x] or not any(0 <= y + dy < H and 0 <= x + dx < W and on[x + dx, y + dy]
                                   for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                continue
            px[y][x] = OUTLINE
    return px


def patterns(text, row="new", size=20):
    """-> {vram word address: 64 words} for every 16x16 cell this row is built from."""
    r = ROWS[row]
    px = draw(text, row, size)
    out = {a: [0] * 64 for a in r["blank"]}
    for i, (top_cell, bottom_cell) in enumerate(r["cells"]):
        for half, addr in ((0, top_cell), (1, bottom_cell)):
            words = []
            for p in range(4):
                for y in range(16):
                    line = px[half * 16 + y]
                    w = 0
                    for x in range(16):
                        if (line[i * 16 + x] >> p) & 1:
                            w |= 1 << (15 - x)
                    words.append(w)
            out[addr] = words
    return out


# What the indices mean on screen, for the preview only: a dark gold edge, white along the top of each
# stroke and blue below it, in whichever pair of indices that row uses.
SHADE = {0x02: (108, 36, 0), 0x0D: (252, 252, 252), 0x0E: (0, 144, 252),
         0x0C: (252, 252, 252), 0x0F: (0, 144, 252)}


def preview(rows, path, scale=6):
    """rows: [(text, row name), ...] -- drawn one above the other, as the title stacks them."""
    drawn = [(draw(t, r), r) for t, r in rows]
    W = max(len(px[0]) for px, _ in drawn)
    img = Image.new("RGB", (W * scale, H * len(drawn) * scale), (24, 16, 8))
    d = ImageDraw.Draw(img)
    for n, (px, _) in enumerate(drawn):
        for y in range(H):
            for x in range(len(px[0])):
                if px[y][x]:
                    y0 = (n * H + y) * scale
                    d.rectangle([x * scale, y0, x * scale + scale - 1, y0 + scale - 1],
                                fill=SHADE.get(px[y][x], (255, 0, 255)))
    img.save(path)
    print(f"{[t for t, _ in rows]} -> {path}")


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if sys.argv[1] == "preview":
        preview([("NEW GAME", "new"), ("CONTINUE", "continue")], sys.argv[2])
    elif sys.argv[1] == "state":
        sys.path.insert(0, "tools")
        import patch_vram
        words = {}
        words.update(patterns("NEW GAME", "new"))
        words.update(patterns("CONTINUE", "continue"))
        patch_vram.apply(sys.argv[2], sys.argv[3], words)


if __name__ == "__main__":
    main()
