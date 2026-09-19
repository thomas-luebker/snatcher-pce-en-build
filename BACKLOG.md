# Backlog

## Done
- [x] Web research: no PCE patch exists; one public disassembly; script sources identified (`docs/RESEARCH.md`)
- [x] Project set up with the shared tools; disc unpacked; both data tracks converted and self-tested
- [x] Track 02 vs Track 24 compared — not a plain copy (`docs/FINDINGS.md`)
- [x] Game boots in the headless harness up to the first dialogue

## Done (second round)
- [x] Packed text decoder written and verified against emulator RAM (`tools/snpack.py`)
- [x] First scene bank located: ISO 0x9F000 (sector 318), 0x4000 bytes, mapped at $8000, same in both tracks; sentence pointers are CPU addresses

## Done (third round)
- [x] Say command found and verified against the live command queue: `12 <speaker> 00 <offset16>`; end-of-sentence rule fixed
- [x] Full first-pass dump of the Japanese script: `tools/dump_script.py` -> 9,285 distinct messages in 82 candidate banks
- [x] Bridge test against the PSX Japanese dump: 33 % exact on first try

## Done (sixth round)
- [x] Scene memory layout, slack and scene table location worked out
- [x] **First English on screen**: 34 messages of scene 1, fullwidth letters, no code changes (`tools/poc_scene1.py`, `build-poc/`, single bin in `build-poc-single/`, `deploy_sd.sh`)

## Done (seventh round)
- [x] **Hardware test passed** (2026-09-18): POC boots on the Turbo EverDrive Pro, English text and English voice clips in the first scene, both judged good
- [x] Voice experiment: 30 Sega CD clips re-encoded to OKI ADPCM into the slots of table 86 (`VOICE=30 tools/poc_scene1.py`), listening set in `work/audio/listen/`

## Done (eighth round)
- [x] **Narrow font works**: letter-pair cells, 36 letters per line, renderer hook in the dialogue bank + font in bank $69 (`tools/sncells.py`, `tools/snhack.py`)
- [x] Speaker names in English (`tools/snnames.py`), menu/topic words of scene 1 in English (`tools/snwords.py`)
- [x] POC build now: narrow text (41 messages), names, menus, 30 English voice clips

## Done (ninth round)
- [x] **Hardware test of the narrow-font build passed** (readable on CRT, stable)
- [x] Load table decoded (destination bank = byte 4 + $68): only $68-$6A are never overwritten; $82+$1800 is the best home for a resident dictionary

## Done (tenth round)
- [x] Huffman + word-token coding (`tools/snhuff.py`), 6280 decoder in bank $82, all-pairs cells: **scene 1 completely English (552 messages, names, menus) and it fits** — `tools/build_scene.py` -> `build-en/`, single bin in `build-en-single/`
- [x] 55 PC Engine-only lines of scene 1 translated by hand (`translations/scene_9f000.json`)

## Stage 2 proper (what a full translation needs)
- [x] ~~Word dictionary~~ -> Huffman + tokens, done
- [ ] **Hardware test of the full-scene build**, and check bank `$82`+`$1800` survives a cutscene / act change (big `$6C` loads run over `$82`)
- [ ] Roll out: per scene = menu word table + hand translations for unaligned lines; generalise `build_scene.py` (text start, loaded size from the scene table); Track 24's own layout
- [ ] The second menu word list (`あたり` …), colour codes inside messages (dropped for now), a 1-byte marker would save ~550 bytes per scene
- [ ] Verify the free regions deeper into the game (more save states) before relying on them
- [ ] Typography: visible gap after F, z and digits (0.5 % of characters); a roomier bank would allow a full 12-row font and digit pairs
- [ ] Re-pack whole scenes (all say pointers), all 33 slots, both tracks (Track 24 has its own layout)
- [ ] Plain-SJIS text: command menus, topic words, item names, speaker names

## Next
- [ ] Check the weak bank candidates (< 100 votes, above ISO 0x1B5800); look for text that is not said via opcode 12 (menus, topic words in plain SJIS, item names, the Jordan computer)
- [x] Which track: emulator reads Track 02 (one-letter experiment); the EverDrive is known to serve the last data track -> patch both, test on hardware with `work/test-t02mod` / `work/test-t24mod`
- [x] Dump rebuilt on the scene table with a chain filter: 10,254 distinct texts on Track 02, 60.9 % verbatim in the PSX Japanese dump
- [ ] Scene-script grammar (say = `63 12 sp 00 lo hi`; ops `1c 20 f1 54 39 3a 58 4c 69` seen) — needed to tie voice requests to lines and to find non-say text
- [x] Sega CD image provided and unpacked (`segacd/files/`); clip table parsed: 1,215 unique clips / 88.5 min vs PCE 1,238 / 97.4 min, same median 3.58 s, same story order (score 358 vs ~130 shuffled)
- [ ] Go/no-go for English voices and the table-86 prototype wait for the script-based clip map
- [x] Direct bridge found: the Sega CD files keep the PCE text order; `tools/text_align.py` (length + punctuation/number/Latin cues) reproduces 17/17 hand-checked pairs on the first scene; 11 of 33 slots align well game-wide
- [ ] Weak slots (~20): local multi-file alignment instead of one global partner; then list PCE lines without an English partner (need fresh translation)
- [ ] Use the text pairs to tie voice requests to lines on both sides -> real clip map (duration/order alone is unproven: 5 audio anchors in 1,050 pairs)
- [ ] ~~Script command formats~~: work out the "say" command(s) from the disassembly's `cmd_table` / `sentence_st0_init` so every [speaker, pointer] reference in a bank can be enumerated reliably
- [ ] Find all scene banks on the disc (the reception line alone has 13 copies in Track 02) and how the loader picks them; then which track is read
- [ ] Dump the whole PCE Japanese script; find scene/bank boundaries and the pointer scheme
- [ ] Which data track is read at runtime? (log CD reads in the emulator or compare RAM with both tracks)
- [ ] Alignment chain: PCE Japanese -> PSX/Saturn Japanese dump (Junker HQ) -> Sega CD English dump (39 files, offset-tagged). Measure how much matches
- [ ] Decide the English text path: 8-pixel font through the glyph override path vs. re-packing; English will not fit at 12 bits/char, so space is the main question
- [ ] PCE-only lines (longer, more slapstick than Sega CD) need fresh translation; names differ from the Japanese voices (Gaudi/Jordan, Catherine/Katrina, 2042/2047)
- [ ] Voiced scenes have no on-screen text on PCE — subtitles would be new code; graphics with text are a separate job

## Audio (investigated 2026-09-18, see `docs/AUDIO.md`)
- [x] In-game voice = OKI ADPCM clips at 16 kHz on **Track 02**, indexed by six tables of 8-byte entries (ISO sectors 86/90/94/98/102/106; boot copy at 54): 1,329 entries, 1,212 unique, ~95 min, ~75 % of the track. Decoder/encoder in `work/audio/`
- [x] Cutscenes (opening etc.) are Japanese voice mixed into **CD-DA tracks**, keyed by CD timecodes (script cmd `$1B`) — a separate, expensive job; default is to keep them and subtitle
- [x] Sega CD side: `PCMLD_01.BIN`, 8-bit sign-magnitude PCM, 16 kHz, 1,214 clips (extractor: github.com/ArtemioUrbina/Snatcher-PCM2WAV). We do not have the Sega CD disc; no ready-made clip pack was found
- [ ] While building the text pipeline, log every audio request (`$F6 idx`) next to its text line -> clip-to-line map
- [ ] Get the Sega CD clips (own disc), align to PCE entries by order/duration/shared sound effects, measure the match rate, then go/no-go; prototype on table 86 (119 clips)

## Ideas
- [ ] **English voices from the Sega CD version** (user's idea, 2026-09-18): replace the Japanese voice clips with the
  Sega CD English ones. Would fix the name mismatch (hearing "Gaudi", reading "Jordan"). Open questions before it
  is worth planning: how the PCE stores voice (ADPCM streamed from the data track vs. CD audio), clip lengths and
  buffer limits (the PCE ADPCM chip has 64 KB), how clips are indexed by the script, and how many voiced PCE
  scenes have a Sega CD counterpart at all. Text first; audio after the script pipeline works.

## Done (eleventh round, 2026-09-18 night) — the whole game
- [x] Per-scene data from the game's own table (`tools/scenes.py`): 32 scenes, 9,201 messages, menu words, text regions
- [x] Scene-by-scene alignment against all 39 Sega CD files (`tools/align_scenes.py`)
- [x] **All 32 scenes translated** (16 agents, `translations/scenes/*.tsv`): official Sega CD lines where they exist, fresh translation for the PCE-only content
- [x] `tools/build_all.py`: all scenes repacked; messages may use any free span; a scene that does not fit grows into the unclaimed sectors before the next scene (max 16 = 4 RAM banks)
- [x] **All ~1,200 voice clips English** (`tools/voices.py`): a clip too long for its slot is encoded at a lower ADPCM rate (rate byte patched in every table copy) instead of being cut — 622 at 16 kHz, 365 at 10.7 kHz, 63 at 8 kHz, 9 still cut
- [x] Reported fixes: "Bullpen" -> "Detective's room", "I tems" (capital I now has serifs), extra glyphs, first menu word of each list detected

## Next
- [ ] Playtest the full build; check the scenes that grew (0x0de, 0x1be, 0x21e, 0x26e) and the low-confidence alignments (0x09e, 0x0ce, 0x0fe, 0x1fe, 0x27e)
- [ ] Voice pairing is still only order+duration for most clips - verify by ear as you play
- [ ] Intro / cutscenes (CD-DA) still Japanese; title menu `初めから` is a sprite

## Fixed 2026-09-18 night (hardware report: "it also hangs")
- [x] **Hang fixed**: after the end of an English message the game calls `decode_next_pair` once more to
  "advance to the next sentence". The new decoder kept pulling bits from a finished stream and never
  returned, so the game waited forever with an empty text box. `dec_hook` now returns at once when
  `$3607` (end flag) is set and clears `$360C`. Reproduced and confirmed gone with `tools/hangtest.py`
  (freeze detector: run a build, report stretches of identical frames).

## Intro narration in English (done 2026-09-18 night)
- Traced the CD during a run: the intro is **CD-DA track 17 alone** (133 s), started right after the
  title; track 21 (4 s) is the jingle before it. Not tracks 18/19/22 as the audio report had assumed.
- `tools/match_tracks.py` (length-constrained: comparing tracks of very different lengths made short
  ones win everything) pairs PCE 17 with **Sega CD track 3** (134.9 s), correlation 0.50 against 0.06
  for the runner-up - the only strong candidate.
- `tools/intro_audio.py` aligns the two on their loudness envelope at 0.1 s (best fit: 1.80 s into the
  Sega CD track, correlation 0.42 - the Sega CD track has a longer lead-in), then copies raw 44.1 kHz
  stereo audio for exactly the PCE track's length. Alignment matters because the intro visuals are cued
  to positions inside the track. The 5-second loudness profiles of the two tracks match closely.
- Samples for listening: `work/audio/intro/intro_{japanese,english}_{start,end}.wav`.

## Title menu 初めから (not solved - what has been ruled out)
Drawn by sprites: patterns at VRAM $6700 and $6800 (32x32 each) and $6E40 (16x32), cursor at $5280.
Ruled out, so nobody repeats it:
- the glyph pixels are **not on the disc** in any of four bitplane orders (plane-major, row-interleaved,
  big-endian, 1bpp plane 0), and not in RAM either;
- the characters are **not on the disc** as SJIS, JIS, EUC, kuten or byte-swapped, whole or in pieces;
- they are **not in RAM** as text at any point from boot to the title (checked at 7 moments);
- the IPL never calls the System Card font routine; the only `jsr $E060` live at the title is the
  dialogue bank's own `tile_renderer` ($6493), which the title does not appear to use (the patched
  build still draws 初 correctly even though $8F is inside the hook's cell range);
- no code loads the constant $6700/$6800/$6E40 into the VDC address register, so the VRAM address is
  computed, not literal;
- the one 32-byte match of sprite data in RAM/disc (ISO 0x1E9192) is a coincidence - the run is exactly
  32 bytes long.
Narrowed: the title screen is built from ISO `0x1DF000-0x1EA800` (loaded immediately before it). Zeroing
it changes the menu; bisecting converges on `0x1DF000-0x1DF2E0`, but zeroing *that* blanks the whole
title screen, so it is the screen's loader/code, not the glyph data - the bisection metric ("the menu
band changed") cannot tell the two apart.
Next step for whoever picks this up: instruction-level tracing of the VRAM writes to $6700 (Mednafen's
debugger, or a libretro frontend with a memory-write callback) - static searching is exhausted.

## Fixed 2026-09-18 (hardware report: "About Gibson" showed as "Abouibson")
- [x] **Cell encoding could emit the string terminator.** A cell was `lead, $40 + n mod 192`, so a pair
  landing on `n mod 192 == 191` produced trail `$FF` - which the game reads as the end of a menu word or
  speaker name, cutting it in half. The pair "ou" is exactly such a cell, so "About Gibson" broke.
  Spacing is now 191 trails (`$40-$FE`) in `sncells.sjis()` and in both 6280 paths (glyph renderer and
  `emit_n`); checked exhaustively that no cell of the 90x90 pair space can produce `$FF`.
  Only cell-encoded strings were affected (menu words, topic words, speaker names) - message text goes
  through the Huffman decoder and was never at risk.

## Title menu 初めから - second attempt, still not solved
- Re-ran the disc scan over `0x1DF000-0x1EA800` in 2 KB chunks with a better metric: read the sprite
  patterns ($6700/$6800/$6E40) and the title logo tiles out of VRAM separately, instead of hashing a
  band of the screen.
- Result: **no chunk changes the glyphs while leaving the title graphics intact.** Every chunk that
  affects the sprites also destroys the background. So the title screen is processed as one block
  (compressed), and there is no isolated glyph data to find by searching.
- Static analysis is finished. The next attempt needs instruction-level tracing of the VRAM writes to
  $6700 (Mednafen's debugger or a libretro frontend with a write callback).
