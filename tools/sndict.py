#!/usr/bin/env python3
"""Build the 192-entry dictionary of frequent letter groups for Snatcher's English text.

  sndict.py reference/junkerhq-dumps/scd translations/dictionary.json

A token is one 12-bit code (SJIS lead $88 / $98, unused by the letter-pair cells) that the patched
decoder expands into 2-6 cells, i.e. an even-length string of pair-alphabet characters starting on a
cell boundary (" the", "you ", "ing ", " that "). Selection is greedy in rounds: count candidate groups
in the text not yet covered, take the best by bits saved, re-tokenise, repeat.
"""
import glob
import json
import re
import sys
from collections import Counter

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sncells  # noqa: E402

TOKENS, ROUNDS, SIZES = 192, 12, (4, 6, 8, 10, 12)
PAIRABLE = set(sncells.ALPHA[:-1])


def corpus(folder):
    lines = []
    for f in sorted(glob.glob(folder + "/sp*.txt")):
        for ln in open(f, "rb").read().decode("latin1").splitlines():
            m = re.match(r"0x[0-9a-fA-F]+: (.*)", ln)
            if m:
                t = re.sub(r"</?cc[^>]*>", "", m.group(1)).replace("<nl>", " ")
                t = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", t)).strip()
                if t:
                    lines += sncells.wrap(t)
    return lines


def segments(line, words):
    """Yield the stretches of `line` that are still plain cells (start on a cell boundary, pairable characters only)."""
    by_len = {}
    for w in words:
        by_len.setdefault(len(w), set()).add(w)
    sizes = sorted(by_len, reverse=True)
    i, start = 0, 0
    n = len(line)
    while i < n:
        hit = 0
        for s in sizes:
            if line[i:i + s] in by_len[s]:
                hit = s
                break
        if hit:
            if i > start:
                yield line[start:i]
            i += hit
            start = i
        elif line[i] not in PAIRABLE:                      # single cell: glyph (+ the space it swallows)
            if i > start:
                yield line[start:i]
            i += 2 if line[i + 1:i + 2] == " " else 1
            start = i
        else:
            i += 2 if line[i + 1:i + 2] in PAIRABLE and i + 1 < n else 1
    if n > start:
        yield line[start:n]


def cost_bits(lines, words):
    return sum(12 * len(sncells.cells(l, words)) for l in lines)


def build(lines):
    words = []
    per_round = TOKENS // ROUNDS
    for _ in range(ROUNDS):
        c = Counter()
        for l in lines:
            for seg in segments(l, words):
                for s in SIZES:
                    for i in range(0, len(seg) - s + 1, 2):
                        c[seg[i:i + s]] += 1
        ranked = sorted(c.items(), key=lambda kv: -(len(kv[0]) // 2 - 1) * kv[1])
        picked = []
        for g, k in ranked:
            if len(picked) >= per_round:
                break
            if any(g in p or p in g for p in picked):       # overlapping picks in one round double-count
                continue
            picked.append(g)
        words += picked
    return words[:TOKENS]


def main(argv):
    lines = corpus(argv[1])
    base = cost_bits(lines, [])
    words = build(lines)
    bits = cost_bits(lines, words)
    json.dump({"_about": "192 dictionary tokens for the English text (order = token number). Built by tools/sndict.py "
                         "from the Sega CD script; changing it changes every encoded message.", "tokens": words},
              open(argv[2], "w"), indent=1)
    print(f"{len(words)} tokens; cells only {base // 8} bytes -> {bits // 8} bytes ({bits / base:.3f}); "
          f"dictionary data {sum(1 + len(w) for w in words)} bytes")
    print("first tokens:", words[:20])


if __name__ == "__main__":
    main(sys.argv)
