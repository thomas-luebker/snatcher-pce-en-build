#!/usr/bin/env python3
"""Where the title screen's 16x16 sprite pixels sit on the disc -> work/title_literals.json

  python3 tools/title_map.py [state]        (default: work/title1165.state, a save state at the title)

The title screen (menu text 初めから included) is drawn from sprites built at runtime, and the pixels are
nowhere on the disc as a block: the screen is LZ-compressed and decompressed straight into VRAM. But the
glyph pixels do not compress, so each bit-plane is stored as one verbatim run of literal bytes, with a
short token between the runs for the zero rows at the bottom. Those runs can be rewritten in place, byte
for byte: patching the 26 literal bytes of the 初 sprite's plane 0 put exactly those pixels on screen in
the emulator. Overwriting past the run hits the token and the glyph comes out blank, so the run length is
the budget for any English lettering.

Caveat: a plane that is mostly zeros matches the compressed stream's zero areas by accident (the entries
that all point at one offset); those are not real literal runs.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mdfnstate  # noqa: E402

LO, HI = 0x1E8000, 0x1EA800                       # the title screen's block on both data tracks


def main(state):
    vram = mdfnstate.parse(state)["VDC.VRAM"]
    word = lambda a: vram[(a & 0xFFFF) * 2] | vram[(a & 0xFFFF) * 2 + 1] << 8
    iso = open("disc/track02.iso", "rb").read()
    iso24 = open("disc/track24.iso", "rb").read()
    region = iso[LO:HI]
    out = {}
    for addr in range(0x6000, 0x7800, 0x40):
        rows = [[word(addr + p * 16 + y) for y in range(16)] for p in range(4)]
        if not any(any(r) for r in rows):
            continue
        ent = {}
        for p in range(4):
            nz = [i for i, w in enumerate(rows[p]) if w]
            if not nz:
                continue
            for n in range(nz[-1] + 1, 3, -1):
                run = b"".join(w.to_bytes(2, "little") for w in rows[p][:n])
                k = region.find(run)
                if k >= 0:
                    ent[p] = {"iso_t02": LO + k, "iso_t24": iso24.find(run), "words": n, "rows": nz[-1] + 1}
                    break
        if ent:
            out[f"{addr:04X}"] = ent
    json.dump(out, open("work/title_literals.json", "w"), indent=1)
    full = [a for a, e in out.items() if len(e) == 4]
    print(f"{len(out)} title sprites with literal runs, {len(full)} with all four planes -> work/title_literals.json")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "work/title1165.state")
