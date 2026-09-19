#!/usr/bin/env python3
"""Align Sega CD English voice clips with PC Engine clips by table order and duration.

  clip_align.py disc/track02.iso segacd/files/PCMLT_01.BIN work/audio/clip_align.json

Both games keep their voice clips in tables that follow the story. English and Japanese takes of
the same line differ in length but correlate, and the Sega CD has extra content, so this is a
global sequence alignment (Needleman-Wunsch) with gaps on both sides, scored by log duration ratio.
"""
import json
import math
import struct
import sys

sys.path.insert(0, "tools")
import cliptable  # noqa: E402


def pce_clips(iso):
    out = []
    for ts, A, _ in cliptable.tables(iso):
        for e in A:
            if e["cmd"] in (2, 3):
                out.append({"table": ts, "idx": e["idx"], "lba": e["lba"], "sectors": e["n"], "cmd": e["cmd"],
                            "sec": e["n"] * 4096 / 16000})
    return out


def scd_clips(table):
    out, seen = [], set()
    for i in range(8, len(table) - 7, 8):
        a, b, grp, start, ln = struct.unpack(">BBHHH", table[i:i + 8])
        if ln and (start, ln) not in seen:
            seen.add((start, ln))
            out.append({"entry": (i - 8) // 8, "group": grp, "start": start, "sectors": ln, "sec": ln * 2048 / 16000})
    return out


def align(a, b, gap=0.55):
    n, m = len(a), len(b)
    S = [[0.0] * (m + 1) for _ in range(n + 1)]
    T = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        S[i][0], T[i][0] = -gap * i, 1
    for j in range(1, m + 1):
        S[0][j], T[0][j] = -gap * j, 2
    for i in range(1, n + 1):
        ai, Si, Sp, Ti = a[i - 1]["sec"], S[i], S[i - 1], T[i]
        for j in range(1, m + 1):
            sc = 1.0 - 2.2 * abs(math.log(ai / b[j - 1]["sec"]))
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
            pairs.append((i - 1, None)); i -= 1
        else:
            pairs.append((None, j - 1)); j -= 1
    return pairs[::-1], S[n][m]


def main(argv):
    pce = pce_clips(open(argv[1], "rb").read())
    scd = scd_clips(open(argv[2], "rb").read())
    pairs, score = align(pce, scd)
    matched = [(i, j) for i, j in pairs if i is not None and j is not None]
    ratios = [scd[j]["sec"] / pce[i]["sec"] for i, j in matched]
    logs = [math.log(r) for r in ratios]
    mean = sum(logs) / len(logs)
    sd = (sum((x - mean) ** 2 for x in logs) / len(logs)) ** 0.5
    close = sum(1 for r in ratios if 0.8 <= r <= 1.25)
    print(f"PCE {len(pce)} clips, SCD {len(scd)} clips; aligned pairs {len(matched)}, PCE-only "
          f"{sum(1 for i, j in pairs if j is None)}, SCD-only {sum(1 for i, j in pairs if i is None)}")
    print(f"duration ratio EN/JP over pairs: geometric mean {math.exp(mean):.2f}, log-sd {sd:.2f}; "
          f"within +-25%: {close} ({100 * close / len(matched):.0f}%)")
    json.dump({"pce": pce, "scd": scd, "pairs": pairs}, open(argv[3], "w"), indent=0)


if __name__ == "__main__":
    main(sys.argv)
