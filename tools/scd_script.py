#!/usr/bin/env python3
"""Read the English script out of a Sega CD Snatcher disc the user owns.

  scd_script.py segacd/files            -> work/scd_script.json
  scd_script.py segacd/files --verify reference/junkerhq-dumps/scd

Konami's English text lives in SP00.BIN .. SP38.BIN on the Sega CD data track, as plain ASCII from
offset 0x3800: records separated by $FF, with $F2 for a line break and a few other control bytes.
This project stores no English dialogue of its own; the build reads it from the user's own disc
through this module, which is why the repository can be public.
"""
import glob
import json
import os
import re
import sys

TEXT_START = 0x3800
END, NL = 0xFF, 0xF2


def strings(data):
    """-> {offset: text}. Control bytes below $20 become <XX> so nothing is silently dropped."""
    out, pos = {}, TEXT_START
    while pos < len(data):
        start, buf = pos, []
        while pos < len(data) and data[pos] != END:
            b = data[pos]
            if b == NL:
                buf.append("\n")
            elif 0x20 <= b < 0x7F:
                buf.append(chr(b))
            elif b < 0x20:
                buf.append(f"<{b:02X}>")
            else:
                buf.append(f"<{b:02X}>")
            pos += 1
        pos += 1                                     # step over the $FF
        text = "".join(buf)
        if text.strip():
            out[start] = text
    return out


def clean(text):
    """The plain form used for matching: no tags, single spaces."""
    return re.sub(r"\s+", " ", re.sub(r"<[0-9A-F]{2}>", "", text).replace("\n", " ")).strip()


def load_dump(folder):
    """-> {'sp06': {offset: text}, ...} from Junker HQ's published dump (sp*.txt)."""
    out = {}
    for path in sorted(glob.glob(os.path.join(folder, "sp*.txt"))):
        name = os.path.basename(path)[:4].lower()
        rows = {}
        for ln in open(path, "rb").read().decode("latin1").splitlines():
            m = re.match(r"0x([0-9a-fA-F]+): (.*)", ln)
            if m:
                t = re.sub(r"</?cc[^>]*>", "", m.group(2)).replace("<nl>", "\n")
                rows[int(m.group(1), 16)] = t
        if rows:
            out[name] = rows
    return out


def load(folder):
    """The English script, from either the user's own Sega CD files (SP*.BIN) or Junker HQ's
    published dump (sp*.txt). Both give the same offsets, so references work against either."""
    if glob.glob(os.path.join(folder, "SP*.BIN")):
        out = {}
        for path in sorted(glob.glob(os.path.join(folder, "SP*.BIN"))):
            name = os.path.basename(path).split(".")[0].lower()
            out[name] = strings(open(path, "rb").read())
        return out
    return load_dump(folder)


def verify(folder, dump_folder):
    """Check against Junker HQ's published dump, if the user happens to have it."""
    mine = load(folder)
    ok = bad = missing = 0
    for path in sorted(glob.glob(os.path.join(dump_folder, "sp*.txt"))):
        name = os.path.basename(path)[:4]
        if name not in mine:
            continue
        for ln in open(path, "rb").read().decode("latin1").splitlines():
            m = re.match(r"0x([0-9a-fA-F]+): (.*)", ln)
            if not m:
                continue
            off, want = int(m.group(1), 16), m.group(2)
            got = mine[name].get(off)
            if got is None:
                missing += 1
            elif clean(got) == clean(re.sub(r"</?cc[^>]*>", "", want).replace("<nl>", " ")):
                ok += 1
            else:
                bad += 1
                if bad <= 3:
                    print(f"  {name} {off:#x}\n    mine: {clean(got)[:70]!r}\n    dump: {want[:70]!r}")
    print(f"matches the published dump: {ok} strings; {bad} differ, {missing} not found")
    return bad == 0 and missing == 0


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    if "--verify" in argv:
        sys.exit(0 if verify(argv[1], argv[argv.index("--verify") + 1]) else 1)
    data = load(argv[1])
    os.makedirs("work", exist_ok=True)
    json.dump({k: {str(o): t for o, t in v.items()} for k, v in data.items()},
              open("work/scd_script.json", "w"), ensure_ascii=False, indent=0)
    print(f"{len(data)} script files, {sum(len(v) for v in data.values())} strings -> work/scd_script.json")


if __name__ == "__main__":
    main(sys.argv)
