#!/usr/bin/env python3
"""Read variables out of a Mednafen/beetle save state:  mdfnstate.py state [VARNAME out.bin]"""
import struct
import sys


def parse(path):
    d = open(path, "rb").read()
    assert d[:8] == b"MDFNSVST"
    pos, out = 32, {}
    while pos + 36 <= len(d):
        sec = d[pos:pos + 32].split(b"\0")[0].decode("latin1")
        size = struct.unpack("<I", d[pos + 32:pos + 36])[0]
        body, p = d[pos + 36:pos + 36 + size], 0
        while p < len(body):
            n = body[p]
            name = body[p + 1:p + 1 + n].decode("latin1")
            ln = struct.unpack("<I", body[p + 1 + n:p + 5 + n])[0]
            out[f"{sec}.{name}"] = body[p + 5 + n:p + 5 + n + ln]
            p += 5 + n + ln
        pos += 36 + size
    return out


if __name__ == "__main__":
    v = parse(sys.argv[1])
    if len(sys.argv) == 4:
        open(sys.argv[3], "wb").write(v[sys.argv[2]])
    else:
        for k, b in v.items():
            if len(b) >= 64:
                print(f"{k:40s} {len(b)}")
