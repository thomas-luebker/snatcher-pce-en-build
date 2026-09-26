#!/usr/bin/env python3
"""Log which CD audio track the PC Engine game plays, and when.

  cdtrace.py CUE [--frames 30000] [--state work/first-dialogue.state] [--shots work/cdtrace]

Why this exists: the Sega CD and PC Engine versions do not share music recordings, so no amount of
comparing the audio will say which track stands in for which (tools/match_cutscenes.py and
docs/FINDINGS.md record how thoroughly that fails). What the two versions *do* share is the story,
so the order tracks are played in lines up even when the sound does not. This logs that order for
the PC Engine side; the Sega CD side is logged the same way from its own emulator, and the two
sequences are matched by position rather than by sound.

How it reads the track: script command $0E stores a track number at $26F5, and the CD state machine
copies it to $26F9 before handing it to the BIOS ($7F masks the track out; $FC/$FD/$FE are fades and
stops, not tracks). Both live in the console's 8 KB work RAM, so the core hands them over directly.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retro  # noqa: E402

PENDING, PLAYING = 0x26F5, 0x26F9
FADES = {0xFC: "fade out", 0xFD: "stop (long fade)", 0xFE: "stop (short fade)"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cue")
    ap.add_argument("--frames", type=int, default=30000)
    ap.add_argument("--state", help="save state to start from, instead of booting")
    ap.add_argument("--shots", help="folder for a screenshot at each track change")
    ap.add_argument("--core", default="emu/mednafen_pce_libretro.dylib")
    a = ap.parse_args()

    e = retro.Emu(os.path.abspath(a.core), os.path.expanduser("~/.mednafen/firmware"))
    e.load(os.path.abspath(a.cue))
    if a.state:
        e.load_state(a.state)
    if a.shots:
        os.makedirs(a.shots, exist_ok=True)
    if e.ram() is None:
        raise SystemExit("this core will not expose work RAM - cannot trace")

    # RUN a couple of times early, the way hangtest.py starts the game, then leave it alone: the
    # cutscenes play on their own and pressing buttons through them only skips what we want to see.
    press = {}
    for f in range(400, 460):
        press[f] = {"start"}
    for f in range(2500, 2520):
        press[f] = {"start"}

    last_play, last_pend, events = None, None, []
    print(f"{'frame':>7} {'time':>8}  event")
    for f in range(a.frames):
        e.run(press.get(f, ()))
        pend, play = e.peek(PENDING), e.peek(PLAYING)
        if pend != last_pend and pend in FADES:
            print(f"{f:7d} {f/60:7.1f}s  {FADES[pend]}")
            events.append((f, "fade", pend))
        if play != last_play and play not in (None, 0):
            track = play & 0x7F
            if track and track < 0x64:
                print(f"{f:7d} {f/60:7.1f}s  play track {track}", flush=True)
                events.append((f, "play", track))
                if a.shots:
                    e.screenshot(f"{a.shots}/f{f:06d}_track{track:02d}.png")
        last_play, last_pend = play, pend

    order = [t for _, k, t in events if k == "play"]
    print(f"\ntrack play order: {order}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
