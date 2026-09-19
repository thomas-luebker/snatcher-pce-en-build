#!/usr/bin/env python3
"""Tile the screenshots of a run into one contact sheet:  sheet.py work/shots [cols]"""
import glob
import struct
import sys
import zlib

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import retro  # noqa: E402


def read_png(p):
    d = open(p, "rb").read()
    w, h = struct.unpack(">II", d[16:24])
    i, idat = 8, b""
    while i < len(d):
        n = struct.unpack(">I", d[i:i + 4])[0]
        if d[i + 4:i + 8] == b"IDAT":
            idat += d[i + 8:i + 8 + n]
        i += 12 + n
    raw = zlib.decompress(idat)
    return w, h, [raw[y * (w * 3 + 1) + 1:(y + 1) * (w * 3 + 1)] for y in range(h)]


d, cols = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3
files = sorted(glob.glob(d + "/f*.png"))
imgs = [read_png(f) for f in files]
W, H = max(i[0] for i in imgs), max(i[1] for i in imgs)
rows_n = (len(imgs) + cols - 1) // cols
sheet = bytearray(W * cols * H * rows_n * 3)
for k, (w, h, rows) in enumerate(imgs):
    ox, oy = (k % cols) * W, (k // cols) * H
    for y in range(h):
        sheet[((oy + y) * W * cols + ox) * 3:((oy + y) * W * cols + ox + w) * 3] = rows[y]
retro.write_png(d + "/sheet.png", W * cols, H * rows_n, bytes(sheet))
print(len(imgs), "frames:", " ".join(f[-10:-4].lstrip("0") for f in files))
