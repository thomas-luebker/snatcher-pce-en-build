#!/usr/bin/env python3
"""English text coding for Snatcher PCE: word tokens + canonical Huffman over glyph symbols.

  snhuff.py build reference/junkerhq-dumps/scd translations/coding.json

Symbols: 0..G-1 = glyphs of sncells.GLYPHS, G = line break, G+1 = end of message, G+2.. = word tokens
(strings of glyphs, stored in the resident dictionary). The patched decoder (tools/snhack.py) walks the
bit stream MSB first with the canonical tables COUNT[len] / SYMS[], expands tokens and pairs the glyphs
into letter-pair cells. An English message starts with the marker bytes $1F $FF, which cannot occur at
the start of a Japanese message, so untouched scenes keep working.
"""
import glob
import heapq
import os
import json
import re
import sys
from collections import Counter

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sncells  # noqa: E402

G = len(sncells.GLYPHS)
NL, END, TOK0 = G, G + 1, G + 2
MARKER = b"\x1f\xff"
MAXLEN = 15


def clean(en):
    en = re.sub(r"</?cc[^>]*>", "", en).replace("<nl>", " ")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", en)).strip()


def corpus(folder):
    """Accepts either Junker HQ's published dump (sp*.txt) or the user's own Sega CD files (SP*.BIN)."""
    if glob.glob(os.path.join(folder, "SP*.BIN")):
        import scd_script
        return [scd_script.clean(t) for strs in scd_script.load(folder).values()
                for t in strs.values() if scd_script.clean(t)]
    out = []
    for f in sorted(glob.glob(folder + "/sp*.txt")):
        for ln in open(f, "rb").read().decode("latin1").splitlines():
            m = re.match(r"0x[0-9a-fA-F]+: (.*)", ln)
            if m and clean(m.group(1)):
                out.append(clean(m.group(1)))
    return out


def screen_chars(line):
    return sncells.normalise(line)


def symbols(text, tokens):
    """Message -> symbol list (with NL / END)."""
    by_len = {}
    for k, w in enumerate(tokens):
        by_len.setdefault(len(w), {})[w] = k
    sizes = sorted(by_len, reverse=True)
    out = []
    lines = sncells.wrap(text)
    for n, line in enumerate(lines):
        s = screen_chars(line)
        i = 0
        while i < len(s):
            for z in sizes:
                k = by_len[z].get(s[i:i + z])
                if k is not None:
                    out.append(TOK0 + k)
                    i += z
                    break
            else:
                out.append(sncells.GLYPHS.index(s[i]))
                i += 1
        if n != len(lines) - 1:
            if len(s) < sncells.CELLS_PER_LINE * 2 - 1:
                out.append(NL)                       # the decoder closes an open pair with BLANK before a line break
            elif len(s) % 2:
                out.append(sncells.GLYPHS.index(" "))  # full line wraps by itself: complete its last cell
    out.append(END)
    return out


def pick_tokens(lines, count):
    """Greedy in rounds: frequent strings of 3-12 glyphs, scored by the bits they save (~4.6 bits per glyph, ~9 per token)."""
    tokens = []
    rounds = 10
    for _ in range(rounds):
        by_len = {}
        for w in tokens:
            by_len.setdefault(len(w), set()).add(w)
        sizes = sorted(by_len, reverse=True)
        c = Counter()
        for s in lines:
            i, start = 0, 0
            segs = []
            while i < len(s):
                for z in sizes:
                    if s[i:i + z] in by_len[z]:
                        if i > start:
                            segs.append(s[start:i])
                        i += z
                        start = i
                        break
                else:
                    i += 1
            if len(s) > start:
                segs.append(s[start:])
            for seg in segs:
                for z in range(3, 13):
                    for j in range(len(seg) - z + 1):
                        c[seg[j:j + z]] += 1
        ranked = sorted(c.items(), key=lambda kv: -(kv[1] * (len(kv[0]) * 4.6 - 9)))
        picked = []
        for g, k in ranked:
            if len(picked) >= count // rounds + 1 or len(tokens) + len(picked) >= count:
                break
            if k < 12 or any(g in p or p in g for p in picked):
                continue
            picked.append(g)
        tokens += picked
    return tokens[:count]


def code_lengths(freq):
    """Huffman code lengths, limited to MAXLEN by flattening rare symbols."""
    floor = 1
    while True:
        heap = [(max(w, floor), i, (s,)) for i, (s, w) in enumerate(sorted(freq.items()))]
        heapq.heapify(heap)
        lens = Counter()
        n = len(heap)
        while len(heap) > 1:
            a = heapq.heappop(heap)
            b = heapq.heappop(heap)
            for s in a[2] + b[2]:
                lens[s] += 1
            n += 1
            heapq.heappush(heap, (a[0] + b[0], n, a[2] + b[2]))
        if max(lens.values()) <= MAXLEN:
            return dict(lens)
        floor *= 2


def canonical(lens):
    """-> (COUNT[1..MAXLEN], SYMS sorted by (length, symbol), {symbol: (code, length)})"""
    syms = sorted(lens, key=lambda s: (lens[s], s))
    count = [0] * (MAXLEN + 1)
    for s in syms:
        count[lens[s]] += 1
    codes, code, prev = {}, 0, 0
    for s in syms:
        code <<= lens[s] - prev
        prev = lens[s]
        codes[s] = (code, lens[s])
        code += 1
    return count[1:], syms, codes


def build(folder, ntokens):
    texts = corpus(folder)
    lines = [screen_chars(l) for t in texts for l in sncells.wrap(t)]
    tokens = pick_tokens(lines, ntokens)
    freq = Counter()
    for t in texts:
        freq.update(symbols(t, tokens))
    for s in range(TOK0 + len(tokens)):
        freq.setdefault(s, 1)                          # every symbol must be codable
    lens = code_lengths(freq)
    bits = sum(freq[s] * lens[s] for s in freq)
    return tokens, lens, bits, sum(len(t) for t in texts)


class Coding:
    def __init__(self, path="translations/coding.json"):
        d = json.load(open(path))
        self.tokens = d["tokens"]
        self.lens = {int(k): v for k, v in d["lengths"].items()}
        self.count, self.syms, self.codes = canonical(self.lens)

    def encode(self, text):
        bits = []
        for s in symbols(text, self.tokens):
            code, n = self.codes[s]
            bits += [(code >> (n - 1 - k)) & 1 for k in range(n)]
        bits += [0] * (-len(bits) % 8)
        return MARKER + bytes(int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8))

    def decode(self, data):
        """Reference decoder (mirrors the 6280 routine) -> list of symbols."""
        assert data[:2] == MARKER
        pos, out = 16, []
        while True:
            code = first = index = 0
            for n in range(MAXLEN):
                bit = (data[pos >> 3] >> (7 - (pos & 7))) & 1
                pos += 1
                code |= bit
                c = self.count[n]
                if code - c < first:
                    out.append(self.syms[index + code - first])
                    break
                index += c
                first = (first + c) << 1
                code <<= 1
            if out[-1] == END:
                return out


if __name__ == "__main__":
    if sys.argv[1] == "build":
        n = int(sys.argv[4]) if len(sys.argv) > 4 else 150
        tokens, lens, bits, chars = build(sys.argv[2], n)
        json.dump({"_about": "Word tokens and Huffman code lengths for the English text (tools/snhuff.py). "
                             "Changing this file changes every encoded message and the resident tables.",
                   "tokens": tokens, "lengths": {str(k): v for k, v in sorted(lens.items())}},
                  open(sys.argv[3], "w"), indent=1)
        print(f"{len(tokens)} tokens, {len(lens)} symbols, max length {max(lens.values())}; corpus {bits // 8} bytes for "
              f"{chars} characters = {bits / chars:.2f} bits/char; dictionary {sum(1 + len(t) for t in tokens)} bytes")
        print("tokens:", tokens[:24])
        c = Coding(sys.argv[3])
        t = "Welcome to Junker Headquarters. May I help you? It's 2042, F-zero!"
        assert c.decode(c.encode(t)) == symbols(t, c.tokens), "round trip failed"
        print("round trip ok:", len(t), "chars ->", len(c.encode(t)), "bytes")
