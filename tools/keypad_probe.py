#!/usr/bin/env python3
"""Drive a name-entry screen in the emulator and read what the overlay thinks, not what the sprites show.

  keypad_probe.py STATE "right,right,a,down"        -> cursor cell ($36B0) and typed codes ($3690) after each

One press per frame with a gap after it; the overlay's cursor cell is $36B0/$36B1, the count $36B2 and
the typed buffer $3690.. (see docs/FINDINGS.md, the keyboard section). Reading those settles where the
cursor is and what a key typed in one run, where a screenshot of a 7-pixel box does not.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retro  # noqa: E402

CUE = os.environ.get("SNATCHER_CUE", "build-en/Snatcher CD-ROMantic (Japan).cue")   # the original disc for comparisons


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    state, moves = sys.argv[1], [m for m in sys.argv[2].split(",") if m]
    gap = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    emu = retro.Emu(os.path.abspath(os.path.join("emu", "mednafen_pce_libretro.dylib")),
                    os.path.expanduser("~/.mednafen/firmware"))
    emu.load(os.path.abspath(CUE))
    emu.run()
    print("state:", emu.load_state(state))
    for _ in range(gap):
        emu.run()
    def show(tag):
        cell = emu.peek(0x36B0) | (emu.peek(0x36B1) << 8)
        n = emu.peek(0x36B2)
        typed = " ".join(f"{emu.peek(0x3690 + i):02x}" for i in range(n))
        print(f"{tag:>8}: cell {cell:#06x}  count {n}  typed [{typed}]  kind {emu.peek(0x351F)}  field {emu.peek(0x34B9)}")
    show("start")
    for m in moves:
        if m == "until3":                         # press through dialogue until the letter grid is open
            for _ in range(40):
                for _ in range(60):
                    emu.run()
                if emu.peek(0x351F) == 3:
                    break
                emu.run([retro.BUTTONS["a"]])
        elif m.startswith("goto:"):               # goto:HEX -- step right until the cursor is on that cell
            want = int(m[5:], 16)
            for _ in range(40):
                if (emu.peek(0x36B0) | (emu.peek(0x36B1) << 8)) == want:
                    break
                emu.run([retro.BUTTONS["right"]])
                for _ in range(8):
                    emu.run()
        elif m.startswith("w"):                   # wN: just let N frames pass (a call connecting, a line spoken)
            for _ in range(int(m[1:])):
                emu.run()
        else:
            emu.run([retro.BUTTONS[m]])
            for _ in range(gap):
                emu.run()
        show(m)
    if len(sys.argv) > 4:
        emu.screenshot(sys.argv[4])
    if len(sys.argv) > 5:
        emu.save_state(sys.argv[5])


if __name__ == "__main__":
    main()
