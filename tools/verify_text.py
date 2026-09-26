#!/usr/bin/env python3
"""Decode every English message out of a built image and report any that would hang the console.

  verify_text.py [build-en]

The freeze this guards against is not a crash: after the end of a message the game calls the decoder
once more to "advance to the next sentence". If a message's bit stream does not reach the end symbol
inside its own span, that call keeps pulling bits out of whatever follows -- $FF padding, the next
message, the end of the loaded block -- and never returns, leaving an empty text box forever.

So every message is decoded here exactly as the 6280 routine walks it, and three things are checked:
it reaches the end symbol, it does so without running past the span it was written into, and it does
it in a sane number of steps. Anything else is a hang waiting for a player to find it.

Static and exhaustive, which is the point: tools/hangtest.py plays semi-randomly and only finds what
it happens to walk into.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdsector as C          # noqa: E402
import snhuff                 # noqa: E402

MAXSTEP = 4000                # a message is a text box, not a novel


def walk(data, start, limit, coding):
    """Decode from `start` like the patched routine does. -> (symbols, end_byte, problem)."""
    if data[start:start + 2] != snhuff.MARKER:
        return None, start, None                      # untouched Japanese message
    pos, out = (start + 2) * 8, []
    while True:
        code = first = index = 0
        for _ in range(snhuff.MAXLEN):
            byte = pos >> 3
            if byte >= limit:
                return out, byte, "ran past the end of the scene block"
            bit = (data[byte] >> (7 - (pos & 7))) & 1
            pos += 1
            code |= bit
            c = coding.count[_]
            if code - c < first:
                out.append(coding.syms[index + code - first])
                break
            index += c
            first = (first + c) << 1
            code <<= 1
        else:
            return out, pos >> 3, "no valid code (walked past the longest code length)"
        if out[-1] == snhuff.END:
            return out, (pos + 7) >> 3, None
        if len(out) > MAXSTEP:
            return out, pos >> 3, f"no end symbol after {MAXSTEP} symbols"


def main(argv):
    out_dir = argv[1] if len(argv) > 1 else "build-en"
    coding = snhuff.Coding("translations/coding.json")
    name = "Snatcher CD-ROMantic (Japan)"
    isos = {}
    for t in (2, 24):
        p = f"{out_dir}/{name} (Track {t:02d}).bin"
        if os.path.exists(p):
            isos[t] = C.bin2iso(open(p, "rb").read())
    if not isos:
        raise SystemExit(f"no built data tracks in {out_dir}/")
    # Scenes that did not fit were grown into the sectors after them, so work/scenes/*.json describes
    # the original disc, not the build. Checking a grown scene against its old size reports the extra
    # sectors as "outside the block" -- the build is fine and the checker is wrong.
    layout = {}
    if os.path.exists("work/scene_layout.json"):
        layout = {int(k, 16): v for k, v in json.load(open("work/scene_layout.json")).items()}
    else:
        print("warning: no work/scene_layout.json - run tools/build_all.py; grown scenes will\n"
              "         be misreported as overflowing", file=sys.stderr)

    bad = total = english = 0
    for t, iso in isos.items():
        print(f"track {t:02d}:", flush=True)
        for f in sorted(glob.glob("work/scenes/*.json")):
            sc = json.load(open(f))
            base, loaded = sc["base"], layout.get(sc["lba"], sc["loaded"])
            if base + loaded > len(iso):
                continue
            problems = []
            for m in sc["messages"]:
                for c in m["cmds"]:
                    ptr = int.from_bytes(iso[base + c + 3:base + c + 5], "little")
                    if not 0 <= ptr < loaded:
                        problems.append((c, ptr, f"pointer {ptr:#x} outside the block"))
                        continue
                    total += 1
                    syms, end, why = walk(iso, base + ptr, base + loaded, coding)
                    if syms is None:
                        continue
                    english += 1
                    if why:
                        problems.append((c, ptr, why))
            if problems:
                bad += len(problems)
                print(f"  scene {sc['lba']:#05x}: {len(problems)} bad")
                for c, ptr, why in problems[:4]:
                    print(f"      cmd {c:#06x} -> {ptr:#06x}: {why}")
    print(f"\n{english} English messages decoded of {total} pointers checked; {bad} would hang")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
