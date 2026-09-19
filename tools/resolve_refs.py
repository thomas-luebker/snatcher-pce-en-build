#!/usr/bin/env python3
"""Rebuild the full English text from translations/scenes_ref/ and the user's own Sega CD disc.

  resolve_refs.py segacd/files [outdir]        default outdir: work/scenes_resolved

`R key sp06:3b20[:mask]` reads Konami's line from the user's disc (the mask re-cases it, menu words
being Title Case here); `T key text` is this project's own writing. Output is the same tab-separated
form the builder consumes.
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scd_script  # noqa: E402


def apply_mask(text, mask):
    n = int(mask, 16)
    return "".join(c.upper() if n >> i & 1 else c.lower() for i, c in enumerate(text))


def resolve_file(path, scd):
    out = []
    for line in open(path):
        line = line.rstrip("\n")
        if not line.strip():
            continue
        tag, key, val = line.split("\t", 2)
        kind, k = key[0], key[1:]
        if tag == "T":
            out.append((kind, k, val))
            continue
        parts = val.split(":")
        name, off = parts[0], int(parts[1], 16)
        text = scd_script.clean(scd[name][off])
        if len(parts) > 2:
            text = apply_mask(text, parts[2])
        out.append((kind, k, text))
    return out


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    scd = scd_script.load(argv[1])
    outdir = argv[2] if len(argv) > 2 else "work/scenes_resolved"
    os.makedirs(outdir, exist_ok=True)
    n = 0
    for path in sorted(glob.glob("translations/scenes_ref/*.tsv")):
        rows = resolve_file(path, scd)
        with open(os.path.join(outdir, os.path.basename(path)), "w") as f:
            for kind, k, text in rows:
                f.write(f"{kind}\t{k}\t{text}\n")
        n += len(rows)
    print(f"{n} lines resolved into {outdir}")


if __name__ == "__main__":
    main(sys.argv)
