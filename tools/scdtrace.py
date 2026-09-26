#!/usr/bin/env python3
"""Log which CD audio track the Sega CD game plays, and when.

  scdtrace.py [--frames 40000] [--rip "Snatcher (USA)"] [--shots work/scdtrace]

The companion to tools/cdtrace.py, which does the same for the PC Engine. Between them they answer
the question tools/match_cutscenes.py could not: the two versions do not share music recordings, so
the audio can never be matched directly -- but they do share the story, so the ORDER the tracks are
played in lines up, and that is what pairs them.

The PC Engine side can be read straight out of work RAM, because the game's own track variable is
known ($26F9). Here it is not, so the track is identified from the sound instead -- which works on
this side precisely because it fails on the other one: the emulator is playing the very recordings
that are on the disc, so a window of its output matches its own track almost exactly, and nothing
else. Correlation for the right track sits near 1.0; a wrong one is not close.

Needs numpy, and a Sega CD BIOS in emu/sysgpgx (genesis_plus_gx expects bios_CD_U.bin).
"""
import argparse
import glob
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retro  # noqa: E402

RATE, HZ = 44100, 50
WIN = RATE // HZ
WINDOW_S = 6.0           # how much recent output to identify from
CHECK_EVERY = 120        # frames between identifications
CONFIDENT = 0.80


def tracks(cue, folder):
    out, f = {}, None
    for ln in open(cue, encoding="latin1"):
        m = re.match(r'\s*FILE "(.+)" BINARY', ln)
        if m:
            f = m.group(1)
        m2 = re.match(r"\s*TRACK (\d+) (\S+)", ln)
        if m2 and f:
            out[int(m2.group(1))] = (os.path.join(folder, f), m2.group(2))
    return out


def envelope(samples):
    n = samples.size // WIN * WIN
    if n < WIN:
        return np.zeros(0)
    return np.log1p(np.sqrt((samples[:n].astype(np.float64) ** 2).reshape(-1, WIN).mean(axis=1)))


def identify(win, refs):
    """-> (track, correlation, position). Which reference track this output came from, and where."""
    best, bt, bk = -2.0, None, 0
    a = win - win.mean()
    sa = np.sqrt((a * a).sum()) or 1.0
    for t, b in refs.items():
        if b.size < a.size:
            continue
        # slide the window over the whole track; same recording means a near-exact hit somewhere
        csum = np.concatenate(([0.0], np.cumsum(b)))
        csq = np.concatenate(([0.0], np.cumsum(b * b)))
        n = a.size
        s = csum[n:] - csum[:-n]
        q = csq[n:] - csq[:-n]
        var = np.maximum(q - s * s / n, 1e-9)
        corr = np.correlate(b, a, mode="valid")
        r = (corr - s * a.mean()) / (np.sqrt(var) * sa)
        k = int(np.argmax(r))
        if r[k] > best:
            best, bt, bk = float(r[k]), t, k
    return (bt, best, bk / HZ) if bt is not None else (None, -2.0, 0.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", type=int, default=40000)
    ap.add_argument("--rip", default=os.environ.get("SCD_RIP", "Snatcher (USA)"))
    ap.add_argument("--shots")
    ap.add_argument("--core", default="emu/genesis_plus_gx_libretro.dylib")
    a = ap.parse_args()

    cues = sorted(glob.glob(os.path.join(a.rip, "*.cue")))
    if not cues:
        raise SystemExit(f"no .cue under {a.rip!r}")
    tr = tracks(cues[0], a.rip)
    refs = {}
    for t, (p, mode) in sorted(tr.items()):
        if "AUDIO" in mode:
            refs[t] = envelope(np.fromfile(p, dtype="<i2").reshape(-1, 2).mean(axis=1))
    print(f"{len(refs)} reference audio tracks loaded", flush=True)

    e = retro.Emu(os.path.abspath(a.core), os.path.abspath("emu/sysgpgx"))
    e.load(os.path.abspath(cues[0]))
    e.audio = bytearray()
    if a.shots:
        os.makedirs(a.shots, exist_ok=True)

    press = {f: {3} for f in list(range(600, 660)) + list(range(1500, 1560)) + list(range(2400, 2460))}
    need = int(WINDOW_S * RATE)
    last, order, prev = None, [], None
    print(f"{'frame':>7} {'time':>8}  event")
    for f in range(a.frames):
        e.run(press.get(f, ()))
        if f % CHECK_EVERY or len(e.audio) < need * 4:
            continue
        buf = np.frombuffer(bytes(e.audio[-need * 4:]), dtype="<i2").reshape(-1, 2).mean(axis=1)
        del e.audio[:-need * 4]
        # Silence matches everything. A window with no real signal in it says nothing about which
        # track is playing, so it is not allowed to vote.
        if np.sqrt((buf.astype(np.float64) ** 2).mean()) < 200:
            prev = None
            continue
        t, r, pos = identify(envelope(buf), refs)
        # The real test is not the correlation but whether the match MOVES like a playing track.
        # A window that genuinely comes from track t at position p must be followed, one check
        # later, by a match on the same track at p + (elapsed time). Noise scores high somewhere in
        # some track every time, but never twice in a row in the right place.
        step = CHECK_EVERY / 60.0
        ok = (prev and prev[0] == t and abs((pos - prev[1]) - step) < 0.6)
        prev = (t, pos)
        if r >= CONFIDENT and ok and t != last:
            print(f"{f:7d} {f/60:7.1f}s  track {t}   (match {r:.2f}, {pos:.1f}s into it)", flush=True)
            order.append(t)
            last = t
            if a.shots:
                e.screenshot(f"{a.shots}/f{f:06d}_track{t:02d}.png")
    print(f"\nSega CD track play order: {order}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
