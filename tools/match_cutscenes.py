#!/usr/bin/env python3
"""Match PC Engine cutscene audio tracks to their Sega CD counterparts.

  match_cutscenes.py                 -> work/cutscene_match.json
  match_cutscenes.py --validate      -> only check the known-good pair (PCE 17 = SCD 3)

Why this is not simply "find the track that sounds the same": the two versions do not share
recordings, and an earlier attempt to correlate raw audio produced nothing. What they do share is
the *cue* -- a cutscene is the same animation in both versions, so the music bed underneath follows
the same shape in time, even when played by different hardware. So the comparison is made on the
loudness envelope at 20 Hz, and -- this is the part the first attempt got wrong -- at every possible
time offset, because the two tracks do not start at the same point in the cue. That is the same
trick tools/intro_audio.py already uses to line the intro up.

The score is a Pearson correlation over the overlapping region, so it is comparable between pairs of
very different lengths. Read the margin between the best and second-best candidate as much as the
absolute score: a cue that matches one track and nothing else is a real match.

Needs numpy.
"""
import glob
import json
import os
import re
import sys

import numpy as np

RATE = 44100
HZ = 20                                   # envelope resolution
WIN = RATE // HZ                          # samples per envelope point
# A lag only counts if the two tracks overlap over most of the shorter one. 25 s was not enough:
# it let a 422 s track "match" another 422 s track on a 107 s fragment at a +315 s lag, scoring well
# while the tracks -- which, being the same length, can only truly align at lag 0 -- correlate 0.04
# there. Requiring near-total overlap is what makes the score mean "this is the same cue".
MIN_OVERLAP_FRAC = 0.85

PCE_CUE, PCE_DIR = "disc/Snatcher CD-ROMantic (Japan).cue", "disc"
SCD_DIR = os.environ.get("SCD_RIP", "Snatcher (USA)")

# Tracks the user identified by ear as carrying voice; 17 is the intro and is already replaced.
VOICE = [1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 20]
KNOWN = (17, 3)                           # verified on hardware -- the method must reproduce this


def tracks(cue, folder):
    """-> {number: (path, mode)} in cue order."""
    out, f = {}, None
    for ln in open(cue, encoding="latin1"):
        m = re.match(r'\s*FILE "(.+)" BINARY', ln)
        if m:
            f = m.group(1)
        m2 = re.match(r"\s*TRACK (\d+) (\S+)", ln)
        if m2 and f:
            out[int(m2.group(1))] = (os.path.join(folder, f), m2.group(2))
    return out


def envelope(path):
    """Loudness envelope at HZ points/second: RMS of the mono mix per window."""
    a = np.fromfile(path, dtype="<i2")
    a = a.reshape(-1, 2).mean(axis=1) if a.size % 2 == 0 else a[: a.size // 2 * 2].reshape(-1, 2).mean(axis=1)
    n = a.size // WIN * WIN
    e = np.sqrt((a[:n].astype(np.float64) ** 2).reshape(-1, WIN).mean(axis=1))
    return np.log1p(e)                    # log domain: shape matters, absolute level does not


def score(a, b):
    """-> (excess, r, lag). How much better a lines up with b than with chance.

    Taking the best correlation over every lag is biased: the longer the candidate, the more lags
    there are to find a lucky window in, so a short track scores high against every long track. The
    fix is a null built from the same pair -- b played backwards has the same length, the same number
    of lags and the same envelope statistics, but cannot genuinely align with anything. Whatever the
    reversed track scores is therefore this pair's chance level, and only the excess over it means
    anything."""
    r, lag = correlate(a, b)
    null = max(correlate(a, b[::-1])[0], correlate(a[::-1], b)[0])
    return r - null, r, lag


def correlate(a, b):
    """Best Pearson correlation of a against b over all lags, and the lag (seconds) that gives it.

    Positive lag means b has to start `lag` seconds in to line up with a."""
    na, nb = a.size, b.size
    size = 1 << int(np.ceil(np.log2(na + nb)))
    fa = np.fft.rfft(a, size)
    prod = np.fft.irfft(fa * np.conj(np.fft.rfft(b, size)), size)          # sum a[i]b[i-k]
    fa2 = np.fft.rfft(a * a, size)
    ones_a, ones_b = np.ones(na), np.ones(nb)
    fb1 = np.conj(np.fft.rfft(ones_b, size))
    s_ab = prod
    s_a = np.fft.irfft(fa * fb1, size)                                     # sum of a over overlap
    s_aa = np.fft.irfft(fa2 * fb1, size)
    fa1 = np.fft.rfft(ones_a, size)
    s_b = np.fft.irfft(fa1 * np.conj(np.fft.rfft(b, size)), size)
    s_bb = np.fft.irfft(fa1 * np.conj(np.fft.rfft(b * b, size)), size)
    n = np.fft.irfft(fa1 * fb1, size).round()                              # overlap length per lag

    ok = n >= MIN_OVERLAP_FRAC * min(na, nb)
    if not ok.any():
        return 0.0, 0.0
    num = n * s_ab - s_a * s_b
    den = np.sqrt(np.maximum(n * s_aa - s_a ** 2, 0) * np.maximum(n * s_bb - s_b ** 2, 0))
    r = np.where(ok & (den > 1e-9), num / np.where(den > 1e-9, den, 1), -1.0)
    k = int(np.argmax(r))
    lag = k if k < size // 2 else k - size                                 # unwrap the circular lag
    return float(r[k]), lag / HZ


def main(argv):
    pce = tracks(PCE_CUE, PCE_DIR)
    cues = sorted(glob.glob(os.path.join(SCD_DIR, "*.cue")))
    if not cues:
        raise SystemExit(f"no Sega CD .cue under {SCD_DIR!r} -- set SCD_RIP")
    scd = tracks(cues[0], SCD_DIR)
    audio = lambda t: {k: v[0] for k, v in t.items() if "AUDIO" in v[1]}
    pce, scd = audio(pce), audio(scd)

    print("reading Sega CD envelopes ...", flush=True)
    senv = {k: envelope(v) for k, v in sorted(scd.items())}

    want = [KNOWN[0]] if "--validate" in argv else [KNOWN[0]] + VOICE
    out, matrix, penv_len = {}, {}, {}
    print(f"\n{'PCE':>4} {'len':>7}   best Sega CD candidates (correlation, offset)")
    for t in want:
        if t not in pce:
            continue
        a = envelope(pce[t])
        penv_len[t] = a.size / HZ
        matrix[t] = {j: score(a, b) for j, b in senv.items()}
        scores = sorted(((v, j) for j, v in matrix[t].items()), reverse=True)
        (x1, r1, lag1), j1 = scores[0]
        (x2, _, _), j2 = scores[1]
        margin = x1 - x2
        mark = "MATCH" if x1 > 0.10 and margin > 0.04 else ("maybe" if x1 > 0.06 else "-")
        tail = "  ".join(f"t{j:02d} {s[0]:+.3f}" for s, j in scores[1:4])
        note = "   <- known good" if t == KNOWN[0] else ""
        print(f"{t:4d} {a.size/HZ:6.1f}s   t{j1:02d} excess={x1:+.3f} (r={r1:.2f}) @{lag1:+.1f}s  "
              f"[margin {margin:+.3f}] {mark:5s} | next: {tail}{note}")
        out[str(t)] = {"best": j1, "excess": round(x1, 3), "r": round(r1, 3), "lag": round(lag1, 2),
                       "margin": round(margin, 3), "runner_up": j2, "verdict": mark}

    # --- resolve to a one-to-one assignment -------------------------------------------------
    # Each track above chose its best candidate independently, so several PCE tracks end up
    # claiming the same Sega CD track -- always one of the long ones, which is the search bias the
    # null only partly removes. A cutscene is one cue and a cue is one track, so the mapping has to
    # be a bijection. Claims are settled strongest-first: the pair with the largest excess anywhere
    # in the matrix is fixed, both its tracks leave the pool, and the next strongest is taken.
    pool = sorted(((x, r, lag, t, j) for t, row in matrix.items() for j, (x, r, lag) in row.items()),
                  reverse=True)
    taken_p, taken_s, assign = set(), set(), {}
    for x, r, lag, t, j in pool:
        if t in taken_p or j in taken_s or x <= 0.06:
            continue
        # A candidate has to be able to fill the slot. The replacement is cut to exactly the PC
        # Engine track's length, so a shorter Sega CD track could only be padded out with silence --
        # which is not a cutscene. This is arithmetic, not a heuristic, and it removes most of what
        # the correlation proposes.
        if senv[j].size < MIN_OVERLAP_FRAC * penv_len[t] * HZ:
            continue
        taken_p.add(t); taken_s.add(j)
        assign[t] = {"scd": j, "excess": round(x, 3), "r": round(r, 2), "lag": round(lag, 2)}

    print("\none-to-one assignment (strongest claim wins, each track used once)\n")
    print(f"{'PCE':>4} {'len':>8}  {'SCD':>4} {'len':>8}  {'excess':>7} {'offset':>8}  dur?")
    for t in sorted(assign):
        a = assign[t]
        dp, ds = penv_len[t], senv[a["scd"]].size / HZ
        agree = "yes" if abs(dp - ds) < 1.0 else ""
        print(f"{t:4d} {dp:7.1f}s  {a['scd']:4d} {ds:7.1f}s  {a['excess']:+7.3f} {a['lag']:+7.1f}s  {agree}")
    unmatched = [t for t in want if t not in assign]
    if unmatched:
        print(f"\nno candidate above chance: PCE {', '.join(map(str, unmatched))}")
    out["assignment"] = {str(k): v for k, v in assign.items()}

    if str(KNOWN[0]) in out:
        got = out[str(KNOWN[0])]["best"]
        print(f"\nvalidation: PCE {KNOWN[0]} -> SCD {got}, expected {KNOWN[1]} -- "
              f"{'METHOD CONFIRMED' if got == KNOWN[1] else 'METHOD FAILS, do not trust the rest'}")
        if got != KNOWN[1]:
            return 1
    if "--validate" not in argv:
        os.makedirs("work", exist_ok=True)
        json.dump(out, open("work/cutscene_match.json", "w"), indent=1)
        print("-> work/cutscene_match.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
