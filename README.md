# Snatcher CD-ROMantic — English for the PC Engine

Build an English version of **Snatcher CD-ROMantic** (Konami, PC Engine Super CD-ROM², 1992, Japan
only) from discs you already own. The game never left Japan on the PC Engine; the Sega CD version did,
in English, two years later. These tools move that English onto the PC Engine disc and translate the
content the Sega CD version never had.

**No game data lives in this repository.** Not the game, not the dialogue, not the audio. What is here
is the tooling, and an index that says *where* each line sits in Konami's script — file and byte
offset, never the words. `build.sh` reads the text from your own source and assembles the image
locally.

## What you get

| | |
|---|---|
| Text | all 32 scene slots, 9,201 messages, plus menus, topic words and character names |
| Voices | ~1,200 in-game clips in English, re-encoded per clip to fit the original slots |
| Intro | the opening narration, aligned so the visuals stay in step |
| Verified | on real hardware (PC Engine + Turbo EverDrive Pro), not only in an emulator |

Still Japanese: the "start" option on the title screen (a picture the game builds at runtime — see
`BACKLOG.md` for what has been ruled out), and the speech in cutscenes other than the opening. That
last one is not an oversight — the two versions do not share music recordings, so there is no Sega CD
track to put in most cutscenes' place. `tools/match_cutscenes.py` is the search, and
`docs/FINDINGS.md` records what it found and the three ways of asking that gave confident wrong
answers first.

## What you need

1. **Your own rip of Snatcher CD-ROMantic (Japan)** — Redump layout, 24 tracks plus a `.cue`. Required.
2. **The English script.** Either Junker HQ's published dump, which `setup.sh` downloads for you, or
   your own Sega CD rip — the tools read either, and both give the same result.
3. **Your own Sega CD rip of Snatcher (USA)** — only for the English *voices* and intro narration.
   Without it you still get the full English text and the Japanese voices are kept.

## Build

```
./setup.sh      # fetches the public prerequisites and says what is still missing
./build.sh      # -> build-en-single/  (a single .bin + .cue, for emulators and flash carts)
```

`VOICES=0 ./build.sh` forces the text-only build. `SCD_TEXT=` and `SCD_DISC=` point the script
somewhere else. `BUILD.md` has the details, and how to check a build before you trust it.

## How the text works

English does not fit where Japanese was: a kanji costs 12 bits, and English needs about 2.5 characters
per Japanese one. So the text is re-encoded as word tokens plus canonical Huffman — around 4 bits per
character — and decoded by a routine added to the game. English is drawn as two 6-pixel letters inside
each 12-pixel character cell, giving 36 letters per line without disturbing the game's spacing logic.
`docs/FINDINGS.md` is the long version, including the things that cost days to work out: the second
data track a flash cart may read from, and the free memory that turns out not to be free.

## Credit

The English dialogue is Konami's official Sega CD localisation, dumped and published by
**Artemio Urbina (Junker HQ)**. The disassembly this project read to understand the text engine is
**buranko-kun**'s. This project matched the two scripts, translated the PC Engine-only content, and
wrote the code that lets the game display English.

Respect the people above, and own the discs you build from.
