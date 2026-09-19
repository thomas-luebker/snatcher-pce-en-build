#!/usr/bin/env python3
"""Match the PC Engine CD-DA tracks to the Sega CD ones by their loudness envelope.

  match_tracks.py  ->  work/track_match.json

Both discs carry the same score, so the music bed correlates even where the narration is in a
different language. Envelope = RMS per 0.5 s; compared at the best small time shift.
"""
import array
import json
import math
import os
import re
import struct
import sys

SEC = 44100 * 4
WIN = SEC // 2


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
    n = len(data) // WIN
    env = []
    for i in range(n):
        s = array.array("h")
        s.frombytes(data[i * WIN:(i + 1) * WIN])
        acc = 0
        for v in s[::16]:
            acc += v * v
        env.append(math.sqrt(acc / (len(s) // 16 + 1)))
    return env


def corr(a, b, maxshift=8):
    # only compare tracks of comparable length: over a short overlap almost anything correlates,
    # which made short tracks win every time
    if not 0.8 < len(a) / len(b) < 1.25:
        return -1.0
    best = -1.0
    for sh in range(-maxshift, maxshift + 1):
        x = a[max(0, sh):]
        y = b[max(0, -sh):]
        n = min(len(x), len(y))
        if n < 20:
            continue
        if n < 0.75 * max(len(a), len(b)):
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
    print("reading envelopes...", flush=True)
    pe = {n: envelope(p) for n, _, p in pce}
    se = {n: envelope(p) for n, _, p in scd}
    out = {}
    for n in sorted(pe):
        scores = sorted(((corr(pe[n], se[m]), m) for m in se), reverse=True)
        best, second = scores[0], scores[1]
        out[n] = {"scd": best[1], "corr": round(best[0], 3), "runner_up": second[1], "runner_corr": round(second[0], 3),
                  "pce_sec": round(len(pe[n]) / 2, 1), "scd_sec": round(len(se[best[1]]) / 2, 1)}
        print(f"PCE {n:2d} ({out[n]['pce_sec']:6.1f}s) -> SCD {best[1]:2d} ({out[n]['scd_sec']:6.1f}s) "
              f"corr {best[0]:.2f} (next best SCD {second[1]} {second[0]:.2f})", flush=True)
    json.dump(out, open("work/track_match.json", "w"), indent=1)


if __name__ == "__main__":
    main()
