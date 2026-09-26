#!/usr/bin/env python3
"""Match PC Engine CD-DA tracks to Sega CD ones by their MUSIC, ignoring the speech on top.

  match_music.py  ->  work/music_match.json

Both discs carry the same score, but the narration differs by language, which drowns a plain
loudness comparison. Averaging blocks of samples is a crude low-pass, leaving bass and percussion:
the same cue then lines up tightly whatever is being said over it. Reported with the margin over the
runner-up, because a confident match is what makes a swap safe.
"""
import array
import json
import math
import os
import re
import sys

RATE, BPS = 44100, 4
LOW = 16                      # average this many samples -> keeps roughly the bass/drum band
WIN = RATE // 4               # 0.25 s


def tracks(cue, folder):
    out, f = [], None
    for ln in open(cue, encoding="latin1"):
        m = re.match(r'\s*FILE "(.+)" BINARY', ln)
        if m:
            f = m.group(1)
        m2 = re.match(r"\s*TRACK (\d+) (\S+)", ln)
        if m2 and f:
            out.append((int(m2.group(1)), m2.group(2), os.path.join(folder, f)))
            f = None
    return out


def envelope(path):
    data = open(path, "rb").read()
    s = array.array("h")
    s.frombytes(data[:len(data) // 2 * 2])
    mono = [(s[i] + s[i + 1]) // 2 for i in range(0, len(s) - 1, 2)]
    low = [sum(mono[i:i + LOW]) // LOW for i in range(0, len(mono) - LOW, LOW)]
    per = WIN // LOW
    out = []
    for i in range(0, len(low) - per, per):
        w = low[i:i + per]
        m = sum(w) / len(w)
        out.append(math.sqrt(sum((v - m) ** 2 for v in w) / len(w)))
    return out


def corr(a, b, maxshift=12):
    if not 0.75 < len(a) / len(b) < 1.33:
        return -1.0
    best = -1.0
    for sh in range(-maxshift, maxshift + 1):
        x, y = a[max(0, sh):], b[max(0, -sh):]
        n = min(len(x), len(y))
        if n < 0.7 * max(len(a), len(b)):
            continue
        x, y = x[:n], y[:n]
        mx, my = sum(x) / n, sum(y) / n
        sx = math.sqrt(sum((v - mx) ** 2 for v in x)) or 1
        sy = math.sqrt(sum((v - my) ** 2 for v in y)) or 1
        best = max(best, sum((p - mx) * (q - my) for p, q in zip(x, y)) / (sx * sy))
    return best


def main():
    pce = [t for t in tracks("disc/Snatcher CD-ROMantic (Japan).cue", "disc") if t[1] == "AUDIO"]
    scd = [t for t in tracks("Snatcher (USA)/Snatcher (USA).cue", "Snatcher (USA)") if t[1] == "AUDIO"]
    print("reading...", flush=True)
    pe = {n: envelope(p) for n, _, p in pce}
    se = {n: envelope(p) for n, _, p in scd}
    out = {}
    for n in sorted(pe):
        sc = sorted(((corr(pe[n], se[m]), m) for m in se), reverse=True)
        (c1, m1), (c2, m2) = sc[0], sc[1]
        out[n] = {"scd": m1, "corr": round(c1, 3), "margin": round(c1 - c2, 3),
                  "pce_sec": round(len(pe[n]) / 4), "scd_sec": round(len(se[m1]) / 4)}
        flag = "CONFIDENT" if c1 > 0.7 and c1 - c2 > 0.2 else "likely" if c1 > 0.5 and c1 - c2 > 0.1 else "unsure"
        print(f"PCE {n:2d} ({out[n]['pce_sec']:4d}s) -> SCD {m1:2d} ({out[n]['scd_sec']:4d}s)  "
              f"corr {c1:.2f}  margin {c1 - c2:+.2f}  {flag}", flush=True)
    json.dump(out, open("work/music_match.json", "w"), indent=1)


if __name__ == "__main__":
    main()
