#!/usr/bin/env python3
"""Turn translations/scenes/*.tsv into reference form, so no Sega CD dialogue is stored here.

  make_refs.py segacd/files            -> translations/scenes_ref/*.tsv

Each line becomes either
    R <key> sp06:3b20[:mask]   the English is Konami's, read from the user's own disc at that
                               offset; the optional hex mask says which letters we upper-cased
                               (menu words are Title Case here, ALL CAPS on the Sega CD)
    T <key> <text>             the English is this project's own work, stored inline
No characters of the Sega CD script are written out. tools/resolve_refs.py turns this back into text
at build time, against the user's own disc.
"""
import glob
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import scd_script  # noqa: E402


def case_mask(ours, theirs):
    """Hex bitmap of which letters of `theirs` we upper-cased; None if the text differs otherwise."""
    if len(ours) != len(theirs) or ours.lower() != theirs.lower():
        return None
    bits = [c.isupper() for c in ours]
    n = 0
    for i, b in enumerate(bits):
        if b:
            n |= 1 << i
    return f"{n:x}"


def main(argv):
    scd = scd_script.load(argv[1])
    exact, fold = {}, defaultdict(list)
    for name, strs in scd.items():
        for off, text in strs.items():
            c = scd_script.clean(text)
            exact.setdefault(c, (name, off))
            fold[c.lower()].append((name, off, c))
    os.makedirs("translations/scenes_ref", exist_ok=True)
    tot = ref = cased = own = 0
    for path in sorted(glob.glob("translations/scenes/*.tsv")):
        out = []
        for line in open(path):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            kind, key, *rest = line.split("\t")
            text = rest[-1] if rest else ""
            c = scd_script.clean(text)
            tot += 1
            if c in exact:
                name, off = exact[c]
                out.append(f"R\t{kind}{key}\t{name}:{off:x}")
                ref += 1
                continue
            hit = None
            for name, off, theirs in fold.get(c.lower(), []):
                m = case_mask(c, theirs)
                if m is not None:
                    hit = (name, off, m)
                    break
            if hit:
                out.append(f"R\t{hit[0]}{''}\t{hit[0]}:{hit[1]:x}:{hit[2]}".replace(f"R\t{hit[0]}\t", f"R\t{kind}{key}\t"))
                cased += 1
                continue
            out.append(f"T\t{kind}{key}\t{text}")
            own += 1
        open(f"translations/scenes_ref/{os.path.basename(path)}", "w").write("\n".join(out) + "\n")
    print(f"{tot} lines: {ref} direct references, {cased} references + case mask, {own} our own text")


if __name__ == "__main__":
    main(sys.argv)
