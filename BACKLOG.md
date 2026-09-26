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

## Done (19 Sep 2026, evening)
- [x] **Intro freeze fixed** (emulator): code in bank $68 top ($5CE2-$5FFF), tables + dictionary at $82+$1800
  behind a magic word, re-read from sector 57 when a load has wiped them. Reproduced first with the intro
  NOT skipped (`work/press_intro.txt`); details and the three wrong assumptions in `docs/FINDINGS.md`
- [x] **Cutscenes dubbed**: 15 tracks, English speech from the Sega CD over the PC Engine music (`tools/cutscene_dub.py`)
- [x] **Hardware test** (19 Sep night): intro, reception, Chief, Harry's blaster, flight to the factory (dubbed
  track 20, English) -- all good. Crash after the blaster found and fixed on the way (animation records at $5C00)
- [ ] Play on from the factory; cutscenes by ear (listening set in `work/cutscene/listen/`); weak spots PCE 10
  at 263-300 s, PCE 4 at 26 s (1.4 s overlap)

## Voice pairing by content (19 Sep night)
- [x] `tools/clip_pair.py`: all 1,238 PC Engine clips transcribed (Japanese) and paired with the 1,215 Sega CD
  clips by meaning (LaBSE) + order + duration. Fixes Gibson in the factory (was Japanese), the time-bomb
  escape (English was three lines late), English speech that had been put on sound-effect slots, and English
  on PC Engine-only scenes (e.g. the videotape shop). 1,002 clips English; 8 slightly cut (>=87% kept)
- [ ] ~40 correct pairings are rejected because the English is >2.3x the Japanese slot: grow those slots
  (relocate clip data, edit the clip tables) instead of leaving the line Japanese
- [ ] Review the ~230 pairs that changed against the old pairing, by reading (as for the cutscenes)

## Open hardware reports
- [x] Katrina's door showed "Dummy F" and "8*" among the numbers on the bust question (21 Sep): the
  answer list holds part-typed shapes -- ０★, ０★★, ８★, ★★★ -- where ★ stands for a digit not yet
  entered. They are data like the digits themselves, and are left alone now
- [x] Katrina's file on Jordan read the Sega CD text (21 Sep): the builder reads work/scenes_resolved,
  not translations/scenes, so the retranslation was never built. Her file now carries the Japanese
  measurements (B 81, W 58, H 83) with the US age 18, which is what makes the door quiz solvable
- [x] **Five files of fixes had never shipped** (21 Sep): the blaster's SELECT, the RUN button for
  number entry, button II for the flashlight and the Gibson records were all in translations/scenes,
  which the build ignored in favour of the stale generated copy. Ported into translations/scenes_ref
  and the stale copy retired; the build now compares the two by content and says so
- [ ] `tools/resolve_refs.py` cannot regenerate work/scenes_resolved: KeyError 8435, a Sega CD reference
  it cannot find. Until that is fixed, edits have to go into both the ref file and the generated one
- [ ] ~~Katrina's file on Jordan still reads the Sega CD text~~ ("Age: 18 ... 43kg ... blood type O-") while
  `translations/scenes/0fe.tsv` holds the retranslation from the Japanese (age 14, B81 W58 H83), which is
  what the door quiz matches. The text on screen is not reachable from scene 0x0FE's say commands, so it
  lives somewhere else -- find where the records are really stored before retranslating again
- [ ] **Scene banks exist twice on track 24** (21 Sep): 17 of 33 scenes have a second copy at its own
  offset, and for the name search the game reads *that* one (sector 83), not the one the scene table
  names. Only 0x0FE is built in both copies so far (`tools/scene_copies.py`). If another screen shows
  Japanese on hardware while the build says it is translated, it is this

- [x] Jordan name search showed no characters to pick (20 Sep): the katakana grid and the name dictionary
  were being translated as menu words; they stay Japanese now (`tools/build_all.py`, KANA_GRID)
- [x] "I cant search in the comuter as the interface is japanese" (21 Sep, branch `computer-search`):
  the screen is a typed lookup -- the keys are the keyboard, the entries are what the typed name is
  compared with, grouped by first character (the videophone is the same screen with digits). Both are
  now written in the game's own full-width Latin, the encoding the videophone's digits already use, so
  typed and stored bytes are identical and the renderer is not involved. Keyboard
  ＡＢＣＫＤＥＦＨＧＩＯＵＪＬＲＭＮＰＱＳＴＶＷＸＹＺ; the input field holds ten characters and every
  record is reachable within it (asserted at build time). **Hardware test outstanding: type GIBSON**
  - the romaji rendering tried the day before is reverted: it never reached this screen, because these
    characters come from the scene's own words, and it put a bank switch in front of every character
- [x] Katrina's door quiz rejected every answer and the videophone showed no numbers (20 Sep): the numeric
  entries those screens match against were being translated; digit-only words are now left alone
- [x] Katrina's file on Jordan shows the Sega CD rewrite (age 18, no measurements) while the door quiz
  wants the Japanese values (14, B81 W58 H83, and Gibson 55) -- retranslate that record from the Japanese
- [x] **Flickering / picture shaking while text draws and menus scroll** (20 Sep): the cell mapping needed a
  multiply and two divisions per character, done by repeated addition inside the interrupt with interrupts
  off (~3,600 cycles/cell against an ~8-10k cycle vblank), which delayed the raster split. The mapping is now
  division-free (`tools/sncells.py`); ~100 cycles. Not reproducible in the emulator -- judge on hardware
- [ ] ~~Flickering in some scenes~~ (20 Sep, details to come). Where to look first: the glyph/decoder calls run
  with interrupts off (`mapcall` does `sei`), so a long line could cost a frame -- that would flicker while
  text draws; the loader hook adds a sector read to loads that wiped the block (~11 frames), which would show
  at scene changes instead. Ask which scene, during text or on a still picture, whole screen or part.

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
- [ ] Hardware test: the English title, the shortened menu words, and the 42 restored voice clips
- [ ] Playtest the full build; check the scenes that grew (0x0de, 0x1be, 0x21e, 0x26e) and the low-confidence alignments (0x09e, 0x0ce, 0x0fe, 0x1fe, 0x27e)
- [ ] Voice pairing is still only order+duration for most clips - verify by ear as you play
- [x] **Title menu `初めから` -> `NEW GAME`** (21 Sep, `tools/title_text.py` + `tools/title_patch.py`).
  Rewriting the runs in place turned out **not** to work: four of the sixteen planes the glyphs are made
  of are not literal runs, and none of the sprites' top halves is, so English drawn into the writable
  planes has the kana showing through it. The lettering is written into VRAM at runtime instead, from
  code that rides inside the title screen's own load. Verified from a cold boot in the emulator
- [x] **`つづきから` -> `CONTINUE`** (21 Sep): `tools/retro.py --bram` boots with the card's own save, which
  puts both lines on screen; the second line is 128x32 with one corner parked off screen, and uses a
  different palette pair than the first. Verified from a cold boot in the emulator
- [x] Hardware test of the English title: `▶ NEW GAME` confirmed on the PC Engine (22 Sep). CONTINUE with a
  save present still to be seen on hardware
- [x] **Typed answers** (22 Sep, `tools/answers.py`): three things on these screens look like text and are
  data -- the fallback word (its first byte picks the keyboard: stays Japanese), the entries (matched
  against full-width Latin, so stored that way), and the field width (ten now). Verified in the emulator
  through the real phone call: Napoleon accepts ENDED
- [x] Hardware test of the typed answers, first riddle (22 Sep): Napoleon accepts, the Plaza scene plays,
  no portrait flicker, keypad behaves. Still ahead in the story: the second riddle (REIGN), BENSON at
  Outer Heaven, QUEEN at the hospital
- [x] 0x19E and 0x1CE menu words found and translated (22 Sep): neither scene had a word list on record;
  0x1CE's text had been overwriting its own menu words. Copies now take text start and words from the scene
- [x] Every duplicated scene is built (22 Sep): Outer Heaven's entrance (0x1BE's twin at sector 275)
  showed Japanese menu words through the English renderer. Real copies are told from stray sectors by
  the whole script matching; 0x1BE's 398-byte shortfall was found in its Sega CD verbosity
- [x] Videophone recordings (22 Sep): Plato's Cavern's greeting, Katrina half asleep and the labs' afternoon
  greeting were Japanese -- unclaimed English takes twenty clips away, added to `clip_fixups.tsv`. Still
  Japanese on the phone, no English take exists: 「ギリアン危ない」, 「おやすみなさい」, the 「キャー!エッチ!」
  line (its English is 2.5x the slot), and four garbled ones the transcripts cannot name
- [x] 24 Sep 19:51 image on hardware: apart from the intro, flawless up to the abandoned factory (Thomas, 24 Sep late); the factory shows none of the door glitches seen on 23 Sep on the same code -- the fault may not be stable (FINDINGS, door section)
- [x] Intro broken by the credits step (24 Sep, from hardware, same evening): the opening roll at sector 170 belongs
  to the cutscene engine, not the dialogue renderer; left untouched now. A "which sectors did the build change"
  gate follows, so an unexpected write is a failure
- [x] The staff roll in English (24 Sep, from hardware): kanji names had gone through the letter-pair hook as
  salad. `translations/credits.tsv` + `tools/credits.py`, 130 lines as cells in the same slots, every copy; gate check
- [x] **Game finished on hardware (24 Sep)**: Act 3 through the ending. The one Japanese stretch left in the ending is
  deliberate: Jamie's farewell with Harry's cap (track 16, 49-75 s) has no Sega CD counterpart -- Konami replaced it
  with Katrina and Mika seeing Gillian off -- so `cutscene_dub.py` keeps the original voices there (KEEP_JP) rather
  than silence; English resumes at "Metal?"
- [x] **Act 2 played through on hardware (24 Sep, on the 23 Sep 13:45 image)**: everything works; the faults reported
  along the way were all voices -- unpaired clips, and the track-24 copies -- and are in the image waiting for the card
- [x] Voice twins on track 24 (24 Sep, from hardware): 244 clips sit at another offset on the track the cart
  serves and were never replaced there. `voices.py` replaces every copy by content; the gate checks none is left
- [x] Queen's Hospital arrival, office drawers and the stairs (23 Sep, from hardware): 15 lines never paired. The
  rock-paper-scissors on the stairs stays Japanese -- the Sega CD cut that scene. 1,103 clips English
- [x] Shower scene at Gillian's (23 Sep, from hardware): Metal's "serves you right" never paired, the shutters
  joke and "Oh, shut up" shifted by one. Three hand pairs; 1,088 clips English
- [x] Hardware, 23 Sep evening: Gibson's house in Act 2 (Alice, the ransacked house -- the re-paired voices) plays
  perfectly; the HQ emergency call is the game's own gate for it, not a fault
- [x] Jamie's voicemail opened in Japanese (23 Sep, from hardware): clip 94/217 -- Whisper heard only the phone
  tone -- paired to "Hi, Jamie speaking"; the other videophone tape to "this is just a tape". 1,086 clips
- [x] Oleen Hospital voices (23 Sep, from hardware): the aligner had drifted -- Napoleon's Santa scene played
  Oleen's takes and Oleen had none. 35 hand pairs by transcript; hand pairs now override and may reuse a take.
  1,084 clips English. Confirmed on hardware 23 Sep. 199 clips still without a take: re-pair by transcript as they are heard
- [x] Konami's debug menu mapped (23 Sep): 39 entries, each run and matched to its scene; `docs/DEBUG_MENU.md`;
  `debug_menu.py go ... "Shooting/With Ivan"` by name. The way to reach any chapter or shootout in the emulator
- [x] Ivan's door shootout (23 Sep, from hardware): lines ending in `<82F5>` close without a button and
  the English never carried the code, so the box waited while Ivan shot. NOWAIT symbol in coder and
  decoder; `verify_build.py` checks it; `tools/debug_menu.py` reaches every shootout from Konami's debug
  scene. Confirmed in the emulator, to be confirmed at Ivan's door on hardware
- [x] Hardware, 23 Sep (the image before the say-target fix): played through Plato's Cavern and Outer
  Heaven; the Junker HQ computer identifies a person (the English keyboard on the real copy, sector 83).
  The night image with Metal's line and Napoleon's overwritten replies is still to go on the card
- [x] Seven say targets no scene list knew (22 Sep, from hardware): Metal's 「店の外に出ました」 after
  Plato's Cavern's store, two more arrivals in 0x1CE, three of Napoleon's replies and one 「誰かの声」 that
  the repacked text had been writing over. `scenes.py` now follows every say command; `verify_build.py`
  checks every say in the build lands on English. "Plato's Cavern" everywhere (was "Joy", "Plato's Cave")
- [ ] The intro's caption cards (the disclaimer, the dedication, "Moscow, 1991", "50 years later") are drawn by
  the cutscene engine from the act image, not by the dialogue renderer: still Japanese, and a separate job
- [ ] The videophone's "number not in service" card is a Japanese graphic (現在、使われておりません), like
  the title glyphs were -- same kind of job if it is worth doing
- [ ] `tools/keypad_probe.py` reads the overlay's cursor/typed buffer out of the emulator; the keypad and
  letter-grid cell maps are in docs/FINDINGS.md. A direction press right after a different direction is
  swallowed -- allow for it when scripting input
- [x] **Cutscene audio (CD-DA): settled, mostly negative.** The intro (PCE 17 <- SCD 3) works. The
  rest cannot be done by swapping tracks - the two versions do not share recordings, and outside one
  coincidence no two tracks are even the same length. `tools/match_cutscenes.py` automates the search
  and validates against the known-good intro pair; its verdict is that only PCE 20 <- SCD 14 scores
  above that benchmark (0.48 vs 0.39), and it is in `PAIRS` marked unverified. Three earlier methods
  produced confident matches that were artifacts - see `docs/FINDINGS.md`, including the near miss
  (PCE 10 / SCD 19: equal length to 0.43s, correlating 0.04 where they must align).
- [ ] **Cutscene speech, the route that should work**: don't swap tracks. English speech lives apart
  from the music in `PCMLD_01.BIN` (already the source for the 1,050 in-game clips), so mixing it
  onto the original PC Engine music bed keeps the right music by construction. Script cmd `$0E`
  gives the track each scene plays; `work/aligned/<lba>.json` names each scene's Sega CD script file.

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

## Title menu 初めから (solved 2026-09-21 — see docs/FINDINGS.md)
Drawn by sprites: patterns at VRAM $6700 and $6800 (32x32 each) and $6E40 (16x32), cursor at $5280 —
this line was right all along, and a later note that called them four 16x32 sprites was not.
Ruled out along the way, so nobody repeats it:
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
