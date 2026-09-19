#!/usr/bin/env python3
"""Align PC Engine Japanese messages with the Sega CD English script, scene by scene.

  text_align.py work/script_t02.json reference/junkerhq-dumps/scd work/text_align.json

Finding: the Sega CD port kept the *order of the text data* of the PC Engine scenes (first scene:
bank 0x9F000 from offset 0x250A <-> sp06.txt from 0x3B20, line for line). So per scene this is a
monotone alignment of two lists in storage order; the Sega CD has extra lines (more content) and
the PCE has lines that were cut, hence gaps both ways. Score = length fit (Gale-Church style).
"""
import glob
import json
import math
import re
import sys
from collections import defaultdict

TAG = re.compile(r"<[^>]*>")
RATIO = 2.6            # English characters per Japanese character, refined below


def scd_files(folder):
    out = {}
    for f in sorted(glob.glob(folder + "/sp*.txt")):
        lines = []
        for ln in open(f, "rb").read().decode("latin1").splitlines():
            m = re.match(r"0x([0-9a-fA-F]+): (.*)", ln)
            if m:
                lines.append({"off": int(m.group(1), 16), "en": m.group(2)})
        out[f.split("/")[-1][:4]] = lines
    return out


def jlen(s):
    return max(1, len(TAG.sub("", s).replace("　", "")))


def elen(s):
    return max(1, len(TAG.sub(" ", s)))


def feats(text, japanese):
    """Language-independent cues: final punctuation, ellipsis, digits, Latin words, page count."""
    import unicodedata
    t = unicodedata.normalize("NFKC", TAG.sub(" ", text.replace("<82F2>", " / ").replace("<nl>", " ")))
    t = t.replace("\u30fb\u30fb\u30fb", "...").replace("\u2026", "...").strip()
    end = t[-1:] if t[-1:] in "?!" else ("." if t.endswith("...") else "")
    return {"end": end, "q": "?" in t, "ex": "!" in t, "ell": "..." in t,
            "num": frozenset(re.findall(r"\d+", t)),
            "lat": frozenset(w.upper() for w in re.findall(r"[A-Za-z]{3,}", t)) if japanese else None,
            "up": t.upper()}


def cue_score(f, g):
    s = 0.0
    s += 0.6 if f["end"] == g["end"] else -0.5
    s += 0.25 if f["q"] == g["q"] else -0.25
    s += 0.2 if f["ex"] == g["ex"] else -0.2
    s += 0.15 if f["ell"] == g["ell"] else -0.15
    if f["num"] or g["num"]:
        s += 1.2 if f["num"] & g["num"] else -0.4
    if f["lat"]:
        s += 0.8 if any(w in g["up"] for w in f["lat"]) else -0.3
    return s


def align(jp, en, ratio, gap=1.3):
    n, m = len(jp), len(en)
    a = [jlen(x["jp"]) * ratio for x in jp]
    b = [elen(x["en"]) for x in en]
    fj = [feats(x["jp"], True) for x in jp]
    fe = [feats(x["en"], False) for x in en]
    S = [[0.0] * (m + 1) for _ in range(n + 1)]
    T = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        S[i][0], T[i][0] = -gap * i, 1
    for j in range(1, m + 1):
        S[0][j], T[0][j] = -gap * j, 2
    for i in range(1, n + 1):
        ai, Si, Sp, Ti, fji = a[i - 1], S[i], S[i - 1], T[i], fj[i - 1]
        for j in range(1, m + 1):
            sc = 0.6 - 1.2 * abs(math.log((ai + 6) / (b[j - 1] + 6))) + cue_score(fji, fe[j - 1])
            best, t = Sp[j - 1] + sc, 0
            if Sp[j] - gap > best:
                best, t = Sp[j] - gap, 1
            if Si[j - 1] - gap > best:
                best, t = Si[j - 1] - gap, 2
            Si[j], Ti[j] = best, t
    pairs, i, j = [], n, m
    while i or j:
        t = T[i][j]
        if t == 0:
            pairs.append((i - 1, j - 1)); i -= 1; j -= 1
        elif t == 1:
            i -= 1
        else:
            j -= 1
    return pairs[::-1], S[n][m]


def main(argv):
    msgs = [r for r in json.load(open(argv[1])) if not r["dup"]]
    scenes = defaultdict(list)
    for r in msgs:
        scenes[r["bank"]].append(r)
    for rs in scenes.values():
        rs.sort(key=lambda r: r["ptr"])
    scd = scd_files(argv[2])
    result, total_pairs = [], 0
    for bank, rs in sorted(scenes.items()):
        best = None
        # shortlist Sega CD files by shared numbers / Latin words (cheap), then run the full DP on the top 4
        jt = set().union(*[feats(r["jp"], True)["num"] | feats(r["jp"], True)["lat"] for r in rs])
        short = []
        for name, lines in scd.items():
            if not lines or not 0.4 < len(lines) / len(rs) < 2.5:
                continue
            up = " ".join(feats(x["en"], False)["up"] for x in lines)
            words = set(re.findall(r"[A-Z]{3,}|\d+", up))
            short.append((len(jt & words) / (len(jt) + 1), name))
        short = [n for _, n in sorted(short, reverse=True)[:4]]
        for name, lines in scd.items():
            if name not in short:
                continue
            pairs, score = align(rs, lines, RATIO)
            norm = score / max(len(rs), len(lines))
            if best is None or norm > best[0]:
                best = (norm, name, pairs)
        if best is None:
            print(f"slot {bank:#x}: {len(rs)} messages - no Sega CD file of comparable size")
            continue
        norm, name, pairs = best
        total_pairs += len(pairs)
        print(f"slot {bank:#x}: {len(rs):4d} msgs -> {name} ({len(scd[name]):4d} lines): {len(pairs):4d} pairs, score/line {norm:.2f}")
        for i, j in pairs:
            result.append({"bank": bank, "ptr": rs[i]["ptr"], "speaker": rs[i]["speaker_name"], "jp": rs[i]["jp"],
                           "scd_file": name, "scd_off": scd[name][j]["off"], "en": scd[name][j]["en"]})
    json.dump(result, open(argv[3], "w"), ensure_ascii=False, indent=1)
    print(f"{total_pairs} JP/EN pairs of {len(msgs)} PCE messages")


if __name__ == "__main__":
    main(sys.argv)
