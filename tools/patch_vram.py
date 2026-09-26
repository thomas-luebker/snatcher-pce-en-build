#!/usr/bin/env python3
"""Write VRAM into a Mednafen save state, to see a change in the game before writing the code for it.

A save state puts the picture on screen in a few hundred frames instead of the tens of thousands a boot
costs, so a pattern, a tile or a whole screen can be judged in the emulator first. That is how the menu
column was measured (16 letters) and how the title lettering is checked here.
"""
import struct
import sys


def _var(d, want):
    """-> (offset of the variable's bytes in the file, its length)."""
    pos = 32
    while pos + 36 <= len(d):
        sec = d[pos:pos + 32].split(b"\0")[0].decode("latin1")
        size = struct.unpack("<I", d[pos + 32:pos + 36])[0]
        p, end = pos + 36, pos + 36 + size
        while p < end:
            n = d[p]
            name = d[p + 1:p + 1 + n].decode("latin1")
            ln = struct.unpack("<I", d[p + 1 + n:p + 5 + n])[0]
            if f"{sec}.{name}" == want:
                return p + 5 + n, ln
            p += 5 + n + ln
        pos += 36 + size
    raise KeyError(want)


def apply(src, dst, words, var="VDC.VRAM"):
    """words: {vram word address: [16-bit words]}. Writes a copy of the state with those words replaced."""
    d = bytearray(open(src, "rb").read())
    base, ln = _var(d, var)
    for addr, ws in words.items():
        for i, w in enumerate(ws):
            o = base + (addr + i) * 2
            assert base <= o < base + ln, f"{addr + i:#06x} is outside {var}"
            d[o], d[o + 1] = w & 0xFF, w >> 8
    open(dst, "wb").write(d)
    print(f"{src} -> {dst}: {sum(len(w) for w in words.values())} words into {var}")


if __name__ == "__main__":
    sys.exit("import this; see tools/title_text.py for a caller")
