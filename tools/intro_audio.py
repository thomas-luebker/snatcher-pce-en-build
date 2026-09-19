#!/usr/bin/env python3
"""Put the Sega CD's English intro narration on the PC Engine disc.

  intro_audio.py [--dry]

The intro (confirmed by tracing the CD during a run) is PCE CD-DA track 17, 133 s. Its Sega CD
counterpart is track 3 (the matcher's only strong candidate for it). Both are plain 44.1 kHz stereo
CD audio, so the track is copied in raw - but first the two are aligned on their loudness envelope at
0.1 s resolution, because the game cues the intro visuals to positions inside the track: the copy
starts at the offset where the music beds line up, and is cut to exactly the PCE track's length.
"""
import array
import glob
import math
import os
import re
import sys

RATE, BPS = 44100, 4
SECTOR = 2352
PCE_CUE, PCE_DIR = "disc/Snatcher CD-ROMantic (Japan).cue", "disc"
SCD_DIR = os.environ.get("SCD_RIP", "Snatcher (USA)")          # your own Sega CD rip, wherever it lives
_cues = sorted(glob.glob(os.path.join(SCD_DIR, "*.cue")))
SCD_CUE = _cues[0] if _cues else os.path.join(SCD_DIR, "missing.cue")
OUT = "build-en"

# (PC Engine track, Sega CD track) pairs that carry the same cue in both versions, so the Sega CD
# recording -- which has the English speech on it -- can stand in for the Japanese one.
#
# Only pairs with independent corroboration are listed. Establishing one is deliberately hard,
# because the two soundtracks are largely NOT the same recordings: see tools/match_cutscenes.py for
# the matcher, and docs/FINDINGS.md for why most PC Engine cutscene tracks have no counterpart.
# A wrong pair puts the wrong music under a scene, which is worse than leaving the speech Japanese.
PAIRS = [
    (17, 3),    # the opening narration. Verified on real hardware. Correlates 0.39 at alignment.
    (20, 14),   # CANDIDATE, not verified by ear. The only pair in the whole disc that scores above
                # the verified intro pair (0.48 vs 0.39) with the PC Engine track fully contained in
                # the Sega CD one. Remove this line if the scene comes out with the wrong music.
]
# Nothing else qualifies, and the near miss is worth recording so it is not retried:
# PCE 10 (422.20s) and SCD 19 (422.63s) agree in length to 0.43s, and the matcher ranked them top
# with every rival at zero -- but two tracks of equal length can only align at offset 0, and there
# they correlate 0.04, against 0.42 for the intro pair. The matcher's score came from overlapping a
# 107s fragment at a +315s lag. Equal duration was a coincidence; the cue is not the same.


def track_file(cue, folder, want):
    f = None
    for ln in open(cue, encoding="latin1"):
        m = re.match(r'\s*FILE "(.+)" BINARY', ln)
        if m:
            f = m.group(1)
        m2 = re.match(r"\s*TRACK (\d+)", ln)
        if m2 and f and int(m2.group(1)) == want:
            return os.path.join(folder, f), f
    raise SystemExit(f"track {want} not found in {cue}")


def envelope(data, win):
    out = []
    for i in range(len(data) // win):
        s = array.array("h")
        s.frombytes(data[i * win:(i + 1) * win])
        acc = 0
        for v in s[::8]:
            acc += v * v
        out.append(math.sqrt(acc / (len(s) // 8 + 1)))
    return out


def best_offset(a, b, win):
    """Offset (in windows) into b at which b best matches a."""
    n = len(a)
    best, bestsh = -2.0, 0
    for sh in range(0, max(1, len(b) - n + 1)):
        y = b[sh:sh + n]
        if len(y) < n:
            break
        mx, my = sum(a) / n, sum(y) / n
        sx = math.sqrt(sum((v - mx) ** 2 for v in a)) or 1
        sy = math.sqrt(sum((v - my) ** 2 for v in y)) or 1
        c = sum((p - mx) * (q - my) for p, q in zip(a, y)) / (sx * sy)
        if c > best:
            best, bestsh = c, sh
    return bestsh, best


def swap(pce_track, scd_track, dry):
    pce_path, pce_name = track_file(PCE_CUE, PCE_DIR, pce_track)
    scd_path, _ = track_file(SCD_CUE, SCD_DIR, scd_track)
    pce, scd = open(pce_path, "rb").read(), open(scd_path, "rb").read()
    win = RATE * BPS // 10                                   # 0.1 s
    off, c = best_offset(envelope(pce, win), envelope(scd, win), win)
    start = off * win
    print(f"PCE track {pce_track}: {len(pce) / (RATE * BPS):.1f}s   Sega CD track {scd_track}: "
          f"{len(scd) / (RATE * BPS):.1f}s")
    print(f"  aligned at {start / (RATE * BPS):.2f}s into the Sega CD track, correlation {c:.2f}")
    out = scd[start:start + len(pce)]
    out = out.ljust(len(pce), b"\0")                          # pad with silence if it runs short
    assert len(out) == len(pce) and len(out) % SECTOR == 0
    if dry:
        return
    dst = os.path.join(OUT, pce_name)
    if os.path.islink(dst):
        os.unlink(dst)
    open(dst, "wb").write(out)
    print(f"  wrote {dst} ({len(out)} bytes)")


def main():
    dry = "--dry" in sys.argv
    only = [a for a in sys.argv[1:] if a.isdigit()]
    for pce_track, scd_track in PAIRS:
        if only and str(pce_track) not in only:
            continue
        swap(pce_track, scd_track, dry)


if __name__ == "__main__":
    main()
