# Build record — what this repository produces

This repository holds tools, translation tables and research -- not the game, its audio or its disc,
which you supply from your own copies. It turns a Japanese
redump of *Snatcher CD-ROMantic* into a disc image with the game in English: text, in-game voices, the
intro narration and the cutscenes.

## Reproduce

```
./setup.sh              # fetches the public prerequisites and says what is still missing
./build.sh              # data tracks, intro, cutscenes, VERIFY, merge  -> work/single/Snatcher (English).bin
./build.sh --emu        # the same plus a cold boot in the emulator (a minute more)
./deploy_sd.sh          # copy that image to the EverDrive card (volume PCE) and verify the copy
```

`build.sh` runs the stages in the only order that works and keeps the build's own report in
`build-en/report.txt`. **`tools/verify_build.py` sits between the build and the merge and stops the
chain on any fault we have already met on hardware**; `deploy_sd.sh` runs it again and refuses an image
that fails or that is older than the last report. Testing this game means playing it through on a PC
Engine, an evening per pass, so nothing that was found once is allowed to come back unnoticed:

| check | the evening it cost |
|---|---|
| the voice step ran, ≥ 1,091 clips | a bare `build_all.py` shipped every spoken line Japanese |
| tracks 03-20 are dubbed files, not links to the originals | the same build reverted the intro and 15 cutscenes |
| no scene or copy over budget, none "STAYS JAPANESE" | Outer Heaven's entrance in Japanese |
| every copy of every scene carries English menu words | the J-Division street; the name search |
| the two data tracks hold every scene identically | copies overrunning into the next scene on track 24 |
| typed-answer fields are ten, fallbacks pick a keyboard, entries are full-width Latin | Napoleon's password, three times over |
| the keypad grid is byte-identical, the letter grid has no hidden keys | an N typed on the videophone, リルレレレレ |
| the title hook, stub and patterns are in place | — |
| the door quiz's digits are untouched | "Dummy F" among Katrina's answers |
| every say command points at a message that decodes as English | Metal's 「店の外に出ました」 outside Plato's Cavern; three of Napoleon's replies overwritten |
| every line whose Japanese ends in `<82F5>` carries the close-without-waiting code | Ivan's door: the shootout under a waiting text box, no cursor |
| no paired voice clip survives in Japanese anywhere on either track | a whole scene Japanese in front of Queen's Hospital: the cart plays track 24's copies |
| every translated credit line is gone from both tracks | the staff roll's names as letter salad |
| the loader hook skips engine states 2/3 (intro, cutscene engine) | the intro's circuit board and street scene as garbage tiles |
| the Junker HQ caption carries no cell-lead kanji | the intro hung at the Junker HQ picture |
| the shared sound-effect bank is untouched; identical Japanese clips carry one English take | Metal's "Gillian, behind you!" over the Act 1 card |
| every message decodes and terminates (`verify_text.py`) | the empty-text-box hang |
| `--emu`: a cold boot shows the English title and reaches the English reception; the whole intro, unskipped, reaches play | the Junker HQ hang, which a boot that skips the intro never sees |

A stage whose input is missing -- no Sega CD rip, no Demucs, or `VOICES=0` -- is skipped in yellow, written
into the report as `SKIPPED`, and listed again by the verify step; the image is then a text-only (or
text-and-voices) build and says so. `SCD_FILES=`, `SCD_RIP=` and `VENV=` point the build elsewhere.

Source-data steps are deliberate, not part of a build, because a change in them is a change to review:
`tools/scenes.py` (scene descriptions from the disc), `tools/align_scenes.py`, `tools/clip_pair.py` and
`tools/clip_stray.py` (voice pairing), `tools/snhuff.py build` (the text coding).

Committed here, because they are source rather than output: the English per scene (`translations/scenes/`,
which the build reads -- `scenes_ref/` is the older index into Konami's script, kept for reference), the text
coding, the credit, name-search and answer tables, the voice pairing (`translations/clip_align.json`) and
the Whisper transcripts both pairings were read from (`translations/asr/`, `translations/cutscene/`).
Whisper does not give the same lines twice, so a rerun would be a new pairing to review, not a build.

Needs, none of them committed here:
- `disc/` — the redump set; `build.sh` makes `track02.iso` and `track24.iso` from it and runs `tools/scenes.py`
- `Snatcher (USA)/` and `segacd/files/` — a Sega CD redump and its extracted data track, for the
  English voice clips (`PCMLD_01.BIN`, `PCMLT_01.BIN`) and the intro track
- `reference/junkerhq-dumps/scd/` — the Sega CD script dump (Junker HQ)
- `reference/snatcher-disasm/` — buranko-kun's PC Engine disassembly
- `emu/mednafen_pce_libretro.dylib` and `~/.mednafen/firmware/syscard3.pce` for the emulator
- `work/venv` with `demucs soundfile` for the cutscene dub (`./setup.sh` offers it; add `mlx-whisper` only to
  re-transcribe). Demucs splits each cutscene track once, slowly, and caches the stems in `work/cutscene/`

## This version

- All 32 scene slots repacked: **9,201 messages**, plus menu/topic words and speaker names
- Text stored as word tokens + canonical Huffman (~4.05 bits/character), decoded by a 6280 routine
  added to the game; English drawn as two 6-pixel letters per 12-pixel cell, 36 letters per line
- ~1,200 in-game voice clips replaced with the Sega CD English takes, rate-adapted per clip
- Intro narration replaced with the Sega CD track, envelope-aligned so the visuals stay cued
- The other 15 voiced cutscenes dubbed: English speech from the Sega CD's CD-DA tracks, separated with
  Demucs and laid line by line over the PC Engine's own music (`tools/cutscene_dub.py`; needs the
  venv: `python3 -m venv work/venv && work/venv/bin/pip install demucs soundfile`)
- Title menu in English: the lettering is written into VRAM at runtime from code carried inside the
  title screen's own load, because its pixels cannot be rewritten on the disc (`tools/title_patch.py`)
- Menu and topic words kept within the sixteen letters a menu column actually draws
- Typed-answer screens (Napoleon's passwords, BENSON, QUEEN, the door quiz) answerable in English: the
  fallback word is left as written because its first byte selects the keyboard, the entries are stored as
  full-width Latin because that is what the keyboard types, and the field is ten (`tools/answers.py`)
- Both data tracks (02 and 24) patched; four scenes grown into unclaimed sectors to fit their English
- The staff roll at the end in English
- Played through from start to ending on a PC Engine with a Turbo EverDrive Pro (24 Sep 2026)

Still Japanese: in the cutscenes, the few lines the Sega CD cut or replaced (PCE 16: Jamie's farewell),
and つづきから on the title, which only appears when there is save data to continue. Most voice-clip pairings are automatic and unverified by ear.

## Checking a build before you trust it

- `python3 tools/hangtest.py "build-en/Snatcher CD-ROMantic (Japan).cue" 30000` — plays the build
  headlessly and reports any stretch where the picture stops changing
- `python3 tools/retro.py <cue> --frames N --press ... --every M` plus `tools/sheet.py` — contact
  sheet of what the game actually draws; `--bram edturbo/.../bram_exp.brm` boots with a real save
- `python3 tools/keypad_probe.py STATE "a,right,until3,..."` — drives a name-entry screen and reads the
  overlay's cursor cell, typed codes, keyboard kind and field width out of RAM after every press
- `python3 tools/dis6280.py ISO OFFSET ORG LENGTH` — disassemble a bank the published disassembly does
  not cover (the script interpreter is `$7C-$7E`, the overlay `$7D` = ISO 0x3B000)

## Releases

`./deploy_sd.sh` keeps the image the card had under `Snatcher (English) previous` (one generation) and copies
every image it puts on the card to `work/releases/<date-time>/` with its report. A build is deterministic from the repo plus the disc, so any release can
be rebuilt from its commit (`git worktree add /tmp/x <commit>`, link `disc reference emu segacd` in, run `./build.sh`).
