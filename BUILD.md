# Build record — what this repository produces

This repository holds tools, translation data and research, never game data. It turns a Japanese
redump of *Snatcher CD-ROMantic* into a disc image with the game in English: text, in-game voices and
the intro narration.

## Reproduce

```
python3 tools/snhuff.py build reference/junkerhq-dumps/scd translations/coding.json 150   # coding tables
python3 tools/scenes.py                                                                  # scene data from the game's own table
python3 tools/align_scenes.py                                                            # English candidates per scene
VOICE=1 python3 tools/build_all.py                                                       # -> build-en/
python3 tools/intro_audio.py                                                             # English intro narration
python3 tools/binmerge.py "build-en/Snatcher CD-ROMantic (Japan).cue" build-en-single "Snatcher (English WIP)"
./deploy_sd.sh                                                                           # -> SD card named PCE, verified
```

Needs, none of them committed here:
- `disc/` — the redump set, plus `track02.iso` and `track24.iso` (`tools/cdsector.py bin2iso`)
- `Snatcher (USA)/` and `segacd/files/` — a Sega CD redump and its extracted data track, for the
  English voice clips (`PCMLD_01.BIN`, `PCMLT_01.BIN`) and the intro track
- `reference/junkerhq-dumps/scd/` — the Sega CD script dump (Junker HQ)
- `reference/snatcher-disasm/` — buranko-kun's PC Engine disassembly
- `emu/mednafen_pce_libretro.dylib` and `~/.mednafen/firmware/syscard3.pce` for the test harness

## This version

- All 32 scene slots repacked: **9,201 messages**, plus menu/topic words and speaker names
- Text stored as word tokens + canonical Huffman (~4.05 bits/character), decoded by a 6280 routine
  added to the game; English drawn as two 6-pixel letters per 12-pixel cell, 36 letters per line
- ~1,200 in-game voice clips replaced with the Sega CD English takes, rate-adapted per clip
- Intro narration replaced with the Sega CD track, envelope-aligned so the visuals stay cued
- Both data tracks (02 and 24) patched; four scenes grown into unclaimed sectors to fit their English
- Verified on a PC Engine with a Turbo EverDrive Pro

Still Japanese: the title menu `初めから` (sprites built at runtime) and the cutscene audio other than
the intro. Most voice-clip pairings are automatic and unverified by ear.

## Checking a build before you trust it

- `python3 tools/hangtest.py "build-en/Snatcher CD-ROMantic (Japan).cue" 30000` — plays the build
  headlessly and reports any stretch where the picture stops changing
- `python3 tools/retro.py <cue> --frames N --press ... --every M` plus `tools/sheet.py` — contact
  sheet of what the game actually draws
