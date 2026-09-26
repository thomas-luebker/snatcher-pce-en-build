# Snatcher CD-ROMantic — English for the PC Engine

Build an English version of **Snatcher CD-ROMantic** (Konami, PC Engine Super CD-ROM², 1992, Japan
only) from discs you already own. The game never left Japan on the PC Engine; the Sega CD version did,
in English, two years later. These tools move that English onto the PC Engine disc and translate the
content the Sega CD version never had.

**What is here is the tooling and the translation tables** — the English per scene, the voice pairing,
the credit and answer tables. The game itself, its audio and its discs are not: you bring your own rips,
and `build.sh` assembles the English image from them locally.

## What you get

| | |
|---|---|
| Text | all 32 scene slots, 9,201 messages, plus menus, topic words and character names |
| Voices | ~1,200 in-game clips in English, re-encoded per clip to fit the original slots |
| Intro | the opening narration, aligned so the visuals stay in step |
| Cutscenes | all 15 voiced cutscenes dubbed: English speech over the PC Engine's own music |
| Title | NEW GAME / CONTINUE, drawn into video memory at runtime |
| Puzzles | the typed answers, the computer name search and the door quiz, solvable in English |
| Staff roll | the ending credits in English |
| Verified | played from start to ending on real hardware (PC Engine + Turbo EverDrive Pro), and every fault found there is a check the build runs before it hands you an image |

Still Japanese, on purpose: Jamie's farewell in the ending (the Sega CD replaced that scene, so there is no
English to lay over it and the original voices are kept rather than silence), a handful of in-game lines
the Sega CD never recorded, and the opening staff roll's headings, which the cutscene engine draws with
its own font.

The cutscenes are not whole-track swaps — the two versions use different music recordings, and the
pictures are cued to positions inside the PC Engine's. So Demucs splits both into voice and music,
and each English line is laid over the PC Engine's own music where its Japanese counterpart was.
`docs/FINDINGS.md` records how that was found, and the three ways of asking that gave confident wrong
answers first.

## What you need

1. **Your own rip of Snatcher CD-ROMantic (Japan)** — Redump layout, 24 tracks plus a `.cue`. Required.
2. **Your own Sega CD rip of Snatcher (USA)** — for the English *voices*, the intro narration and the
   cutscenes. Without it you still get the full English text; the Japanese voices are kept, and the
   build says so.
3. **Python 3.** The cutscene dub also wants a venv with Demucs, which `setup.sh` offers to create
   (`NO_VENV=1` skips it; the cutscenes then stay Japanese).

## Build

```
./setup.sh      # fetches the public prerequisites and says what is still missing
./build.sh      # -> work/single/Snatcher (English).bin + .cue, for emulators and flash carts
```

`build.sh` runs `tools/verify_build.py` before it merges the image: each check there is a fault that
was found by playing the game through on a PC Engine, and none of them gets to come back unnoticed.
`VOICES=0 ./build.sh` forces the text-only build; `SCD_FILES=`, `SCD_RIP=` and `VENV=` point the script
somewhere else. `BUILD.md` has the details, and how to check a build before you trust it.

## How the text works

English does not fit where Japanese was: a kanji costs 12 bits, and English needs about 2.5 characters
per Japanese one. So the text is re-encoded as word tokens plus canonical Huffman — around 4 bits per
character — and decoded by a routine added to the game. English is drawn as two 6-pixel letters inside
each 12-pixel character cell, giving 36 letters per line without disturbing the game's spacing logic.
`docs/FINDINGS.md` is the long version, including the things that cost days to work out: the second
data track a flash cart may read from, the free memory that turns out not to be free, and the screens
where what looks like text is data the game compares against. `docs/ENGINE.md` is the engine as
measured — memory map, loads, the script, the renderer — and `docs/DEBUG_MENU.md` maps Konami's own
debug menu, which reaches every chapter and shootout.

## Credit

The English dialogue is Konami's official Sega CD localisation, dumped and published by
**Artemio Urbina (Junker HQ)**. The disassembly this project read to understand the text engine is
**buranko-kun**'s. This project matched the two scripts, translated the PC Engine-only content, and
wrote the code that lets the game display English.

Respect the people above, and own the discs you build from.
