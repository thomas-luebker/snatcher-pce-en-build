#!/usr/bin/env python3
"""Play a build automatically and report where the picture stops changing.

  hangtest.py CUE [frames]

Presses RUN twice to start, then taps I every 45 frames (and moves the cursor now and then).
A stretch of >=400 identical frames while input is being given counts as a hang.
"""
import hashlib
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
import retro  # noqa: E402

cue = sys.argv[1]
total = int(sys.argv[2]) if len(sys.argv) > 2 else 40000
e = retro.Emu(os.path.abspath("emu/mednafen_pce_libretro.dylib"), os.path.expanduser("~/.mednafen/firmware"))
e.load(os.path.abspath(cue))
random.seed(5)
script = [(3, 400, 460), (3, 2500, 2520), (3, 4000, 4020)]
dirs = [4, 5, 6, 7]
f = 6000
while f < total:
    script.append((8, f, f + 5))
    if f % 450 == 0:
        d = random.choice(dirs)
        script.append((d, f + 10, f + 10 + random.randint(8, 30)))
    f += 45
last, same, worst = None, 0, (0, 0)
for f in range(1, total + 1):
    e.run([b for b, lo, hi in script if lo <= f <= hi])
    if f % 10 == 0:
        h = hashlib.md5(e.frame[0]).hexdigest()
        if h == last:
            same += 10
            if same > worst[0]:
                worst = (same, f)
        else:
            if same >= 400:
                print(f"frozen {same} frames, ended at frame {f}")
            same = 0
        last = h
e.screenshot("work/hang.png")
print(f"ran {total} frames; longest frozen stretch {worst[0]} frames ending at {worst[1]}")
