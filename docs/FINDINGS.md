# Findings (measured here)

Redump set *Snatcher CD-ROMantic (Japan)*, 24 tracks.

## Disc

- Track 02 (data): 34,120 user sectors after the 225-sector pregap. Track 24 (second data track):
  33,973. `cdsector.py` reproduces both raw tracks bit for bit from their ISOs.
- IPL: loads 22 sectors from sector 2 to `$3000`, executes at `$3000`. Title `SNATCHER CD-ROM2konami`.
- **Track 24 is not a plain copy of Track 02.** Of its sectors, 19,252 sit at the same position as in
  Track 02, 3,813 are shifted by 2 sectors, 1,796 by 171, smaller groups by -2768 / +4957 / +4955, and
  **1,449 sectors do not occur in Track 02 at all.** Both tracks have to be understood before
  anything is patched — on Dead of the Brain the game read from the second data track and a patch
  to Track 02 alone showed nothing on real hardware.

## Emulator

- The headless harness boots the disc: RUN at the System Card, RUN at the title (`初めから`),
  RUN again → first dialogue at JUNKER HQ reception (`受付嬢 / JUNKER本部です。何のご用でしょうか？`)
  around frame 5500.
- Text is drawn with 16x16 (or 12-wide) kanji glyphs, 2 lines visible in that box, speaker name in
  yellow above.

## Script text — verified 2026-09-18 (save state at the first dialogue + `tools/snpack.py`)

- **The packed text encoding in the public disassembly is right.** `tools/snpack.py` implements it
  (12-bit codes: kanji pair / end / kana run / single 0x81-0x84 character) and, scanning emulator RAM
  for a position that decodes to the on-screen `何のご用でしょうか？`, finds exactly one: SysCardRAM
  offset `0x2E51A`, raw `9b dd 0c 93 27 70 10 7c 5b 5e 5a 4a 90 80`. Sentences follow each other
  byte-aligned (`ここから先へはＪＵＮＫＥＲ関係者しか入れません。` is next).
- The decoded sentence sits in base RAM at `$3619` with the print control codes in front
  (`F9 01`, `FE 01`, `FB 01 02`, text, `FF`) — matching the disassembly's control-code list.
- **Scene banks:** that RAM is a 0x4000-byte scene bank in SysCardRAM banks 22-23 (physical `$7E/$7F`),
  identical to ISO `0x9F000-0xA3000` (sector 318) **in both data tracks**. The bank is addressed at
  `$8000-$BFFF`: the script refers to the sentence as CPU pointer `$A51A` (bytes `1a a5` at bank offset
  `0x2946`, preceded by what looks like a speaker byte). MPR at that moment: `ff f8 68 69 86 87 85 00`.
- The same reception sentence occurs at 13 places in Track 02 (`0x6B0A0`, `0x7B0A0`, `0x830A0`, …) —
  other scene banks carry their own copy.
- Text and script bytecode are interleaved: groups of consecutive sentences are separated by a few
  bytes of commands, so a blind sequential walk derails. Enumerating all text needs the script
  interpreter's command formats (`cmd_table` in the disassembly's `engine.asm`, `sentence_st0_init`
  reads 4 bytes: speaker, pointer, flags) — a pointer-pattern heuristic alone is too noisy.
- Plain-SJIS data also exists: speaker names (`受付嬢 ff 32 …`) in the dialogue bank and `FF`-separated
  topic/menu words (`ＪＵＮＫＥＲの任務`, `ＪＵＮＫＥＲ証`, …) inside scene banks.

## Script structure and full dump — 2026-09-18, third pass

- **End of sentence:** on a byte boundary a zero *byte* ends the text (2 nibbles); mid-byte it is the
  12-bit code `0,T<$40`. With that rule the decoded text matches the PSX Japanese dump character for
  character (`これより先は関係者以外の方は、立入禁止になっております。`).
- **Say command:** the scene bank begins with its script. A message is said with
  `12 <speaker> 00 <lo> <hi>` where lo/hi is the **offset of the packed text inside the bank**. The
  engine turns it into queue command `08`: the live queue at `$3C10` held `08 03 00 0a 25` while bank
  offset `0x250A` decodes to `ＪＵＮＫＥＲ本部です。<82F2>何のご用でしょうか？`. (My earlier "pointer $A51A"
  was a coincidence inside packed text.)
- Speaker byte N is entry N-1 of the name table (`2`=ギリアン, `3`=受付嬢, Metal Gear, Napoleon, …).
- `<82F2>` inside a message (run byte `$F2`, not a valid SJIS code) separates the lines/pages of one message.
- **`tools/dump_script.py`** finds scene banks by voting (every `12 ss 00 lo hi` whose target decodes to
  clean Japanese votes for the sector-aligned bases it could belong to) and dumps all messages:
  **82 candidate banks, 10,144 say commands, 9,285 distinct messages, 261,494 characters** in Track 02.
  The strong banks (150-470 messages each) lie between ISO `0x49000` and `0x149000`; candidates above
  `0x1B5800` have 8-90 votes and need checking (false positives or small special scenes).
- **Bridge test:** 25.6 % of the PCE messages equal a line of the PSX Japanese dump exactly (after
  normalising punctuation), 33.4 % when every `<82F2>` part is matched separately. The Saturn dump
  matches almost nothing as is (different line breaking). Fuzzy matching not tried yet.

## Which track is read — one-letter experiment (2026-09-18)

- Two test discs, each with a single letter of the first line changed (`ＪＵＮＫＥＲ` -> `ＫＵＮＫＥＲ`, run
  byte `69`->`6A`, which is nibble-shifted: ISO byte `0xA150C` `97`->`A7`) in only one track.
  **Emulator: the Track 02 change shows on screen, the Track 24 change does not.**
- But on the Turbo EverDrive Pro, Dead of the Brain served data from its *last* data track. Snatcher's
  Track 24 is laid out differently from Track 02 (the game's own scene table, LBA `0x9E + 0x10·n`, fits
  Track 24's regular 0x8000 grid), so both tracks have to be patched, each at its own bank locations,
  and the same one-letter test should be repeated on real hardware (`work/test-t02mod`, `work/test-t24mod`).
- Scene table (`scene_desc_tables.bin` in the disassembly): 8-byte entries, bytes 1-2 = LBA, byte 4 = type
  (`$16` = 33 scene banks, `$05` = 106 others), byte 6 = a count. The first scene is LBA `0x13E` = ISO `0x9F000`.
- `dump_script.py`'s bank detection by voting is too crude for Track 02 (it excluded the true bank
  `0x9F000` in favour of an overlapping candidate); it should be rebuilt on the scene table.

## Dump rebuilt on the scene table (2026-09-18, fourth pass)

- `tools/dump_script.py` now takes its slots from the game's scene table (slot = up to 0x8000 bytes from
  each table LBA) and keeps a candidate only if it chains back to back with a neighbouring message or is
  clean Japanese ending like a sentence. Result: **Track 02: 35 slots, 13,658 say commands, 13,035
  distinct (slot, offset) messages, 10,254 distinct texts, 314 k characters**; Track 24: 38 slots, 9,481
  messages. The first scene alone has 616 say commands.
- **60.9 % of the distinct Track 02 texts occur verbatim in the PSX Japanese dump** (every `<82F2>` part
  matched after normalising punctuation) — before any fuzzy matching. That validates the dump and makes
  the PSX dump a solid bridge.
- In the scene script a say appears as `63 12 <speaker> 00 <lo> <hi>`, usually preceded by `1c`. Other
  frequent ops around it: `20 xx 00`, `f1 <lo> <hi>` (looks like a bank-internal address), `54 60 1e`,
  `39 xx 22`, `3a`, `58 xx 00`, `4c`, `69 2e 10 …`. The grammar is not worked out, so voice requests
  (`$F6 idx` lives in *animation* scripts) are not yet tied to text lines; the first scene has no voice.

## Sega CD disc and the direct JP -> EN bridge (2026-09-18, fifth pass)

- The user's *Snatcher (USA)* image (redump, 21 tracks, Track 01 = Mode 1 data without pregap) is unpacked
  to `segacd/files/` (gitignored): `SP00-SP38.BIN` scripts, `PCMLD_01.BIN` (84.7 MB voice PCM),
  `PCMLT_01.BIN` (clip table), `SUBCODE.BIN`, `DATA_*.BIN`.
- **The Sega CD port kept the storage order of the PC Engine scene text.** PCE slot `0x9F000` from offset
  `0x250A` and `sp06` from `0x3B20` correspond line for line (reception lines, Gillian's remarks, the
  recruiting poster, the door …). The PSX detour is not needed.
- `tools/text_align.py`: per scene, monotone alignment of the two lists in storage order with gaps both
  ways (the Sega CD has more content; the PCE has lines that were cut). Length alone drifts badly
  (topic words like `ABOUT BLASTER` head the English file but are not say-messages on PCE), so the score
  adds language-independent cues: final `?`/`!`/ellipsis, shared numbers, fullwidth Latin words found in the
  English. On the first scene that reproduces **17 of 17 hand-checked pairs** and gives 514 pairs of 612
  messages; spot checks in the middle are correct translations.
- Known wrinkle: the 0x8000 slot windows overlap neighbouring scenes, so some messages are dumped twice
  under two slots.

### Whole-game alignment, first results

- Exhaustive search (every PCE slot against every `sp` file, `work/full_search.py`): 11 of 33 slots find a
  partner with score/line >= 0.5 — `0x9F000`/`0x87000`/`0x8F000` -> sp06 (JUNKER HQ at different story
  points; the PCE stores such variants separately, the Sega CD merges them), `0xAF000` -> sp08 (0.86),
  `0x10F000` -> sp26 (0.82), `0x147000` -> sp37 (0.83), `0x137000` -> sp33, `0x77000` -> sp20,
  `0xD7000` -> sp13, `0x5F000` -> sp35, `0x12F000` -> sp32, `0xEF000` -> sp21.
- The other ~20 slots score 0.1-0.4; sp26 "wins" seven of them, which says the score is not decisive
  there. Likely reasons: a PCE slot draws on more than one Sega CD file (39 files vs 33 scenes), heavier
  rewriting, and chance say-patterns still in the dump. Next: align each weak slot against *all* files
  with local (Smith-Waterman style) segments instead of one global partner.
- Current output `work/text_align.json`: 11,077 pairs, trustworthy only for the high-scoring slots
  (about 4,500 pairs).

## Voice clips: tables compared (2026-09-18)

- `PCMLT_01.BIN`: 8-byte header, then 2,195 entries `04 0x gggg ssss llll` (big endian: group, start
  sector, length in sectors of `PCMLD_01.BIN`); 1,270 with a length, **1,215 unique clips, 88.5 min**,
  median 3.58 s. PCE: **1,238 playable clips, 97.4 min, median 3.58 s**.
- Aligning the two lists by table order and duration (`tools/clip_align.py`) scores 358 against ~130 for
  a shuffled order, with runs of up to 72 consecutive pairs — the tables follow the same story order.
  But per-pair it is unproven: comparing loudness envelopes of all 1,050 aligned pairs
  (`tools/clip_verify.py`) finds only 5 with correlation >= 0.8, as expected for speech in two languages.
  A trustworthy clip map has to come from the scripts (voice request next to text line on both sides).

## Memory layout of a scene, free space, and the first English on screen (2026-09-18, sixth pass)

- Scene table entry = `00 <lba lo> <lba hi> 04 <type> 00 <sectors> 00`; the table sits at ISO `0xC585`
  (same in both tracks). The first scene (`0x13E`) loads **14 sectors = 0x7000 bytes into physical banks
  `$7E $7F $80 $81`** (end of System Card RAM running on into CD RAM); text offsets are offsets into that
  block, read through the nibble fetcher's own mapping. The slot's last 0x1000 on disc is other data,
  and the matching RAM (`$81` upper half) is in use too.
- RAM is nearly full during play (only banks `$73`, `$74` empty, `$6D`/`$82` mostly empty).
- The loaded scene ends at `+0x6874`: **1.9 KB of slack per scene, nothing more.**
- **Proof of concept (`tools/poc_scene1.py`, `build-poc/`): 34 messages of the first scene in English,
  no code changes.** English is written as fullwidth letters in the game's own packed format
  (`snpack.encode_english`: runs of 8-bit characters, `<82F2>` = line break), placed in the slack, and the
  say commands re-pointed; both tracks patched identically. Measured in the emulator: the box holds
  **18 fullwidth characters x 3 lines** and wraps/pages by itself (a full 18-character line must not get
  an explicit break as well).
- **Why this does not scale:** fullwidth English costs ~1 byte per character and the English is ~2.2x the
  Japanese in bytes (first scene: ~17 KB of text -> ~37 KB) against 1.9 KB of slack, and 18 columns is
  cramped. A full translation needs (1) a compact English encoding with a new decoder hooked at
  `decode_next_pair` (`$7272`; the dialogue bank has ~1.1 KB of `$FF` padding at `$5BB3-$5FFF` for code),
  and (2) an 8-pixel font with a changed advance in the print loop (`$66D4`), glyphs via the custom-glyph
  override path (`$6A07`/`$69FC`). Command menus (`中に入る 見る 調べる 話す`) and topic words are plain
  SJIS elsewhere and are a separate, easier job.

## Real hardware test of the proof of concept (2026-09-18, PC Engine + Turbo EverDrive Pro)

- The single-bin POC image **boots and plays**; the receptionist's lines are **English on screen** and
  **English voice clips play** when talking to her — text and audio both judged good by Thomas.
  So: the fullwidth-text route, the say-pointer patching, the ADPCM re-encoding of Sega CD clips into
  the original slots, and patching both data tracks all work on the real machine, and the EverDrive copes
  with Snatcher's two differently laid-out data tracks.
- The duration/order clip pairing was at least right for the receptionist's lines (table 86, first
  entries) — still unverified beyond that.
- Still Japanese, as expected: the CD-DA intro/cutscenes, the command menus and everything outside the
  34 patched messages.

## Letter-pair cells: the narrow font (2026-09-18, eighth pass) — works in the emulator

- **Idea:** the game draws 12x12 kanji cells, 18 per line, one 12-bit code each. Two 6-pixel letters fit in
  one cell, so a claimed SJIS range (lead `$89-$97`, trail `$40-$FF`, 2880 codes, all reachable by the packed
  format) is redefined as letter pairs: `n = (lead-$89)*192 + (trail-$40)`; `n < 53*53` = pair from a
  53-symbol alphabet (52 characters chosen by "gap cost" + BLANK), above that = single cell (glyph + blank
  half; its blank doubles as the following space, so punctuation is free). Result: **36 letters per line,
  6 bits per letter, no change to the game's spacing logic** (`tools/sncells.py`).
- **Hook** (`tools/snhack.py`): the glyph renderer's `jsr $69C2` at `$648C` (dialogue bank = RAM bank `$6A`,
  ISO `0xF000`, both tracks) is redirected. Part A (172 of 176 free bytes at `$7F50`) computes the two glyph
  indices; part B + a 76-glyph 6x9 font (Monaco 9, 806 of 814 free bytes) live in the tail of RAM bank `$69`
  (ISO `0xD000` + `$1CD2`), which part A maps into MPR4 for the call with interrupts off.
  **Lesson:** the engine bank's `$5C40` tail is `$FF` on disc but work RAM at runtime — code put there was
  overwritten within a second and the scene fell apart. Free space must be checked across save states.
- Other stable free regions seen in two save states: bank `$7B` +`$0FC4` (4156 bytes, ISO `0x37000`),
  bank `$6D` (~7.6 KB, ISO `0x1F9000`), bank `$82` (~6.6 KB; clip-table bank, reloaded from six disc copies),
  bank `$6C` +`$1758` (1192), bank `$72` (18 KB `$FF`).
- **Speaker names** (`tools/snnames.py`): table `$6D47-$6F27` + pointers `$6F28`, entries = attribute byte
  (`$36` Gillian, `$32` others) + SJIS + `$FF`. Rewritten as cells: 479 of 481 bytes.
- **Menu / topic words** (`tools/snwords.py`): plain SJIS, `$FF`-separated, sorted, directly before the packed
  text (scene 1: 80 words, `0x21E6-0x250A`), referenced from the script as `F1 <lo> <hi>`. As cells an English
  word costs one byte per letter: 67 of 80 fit in place, 13 were moved to slack with their `F1` references
  re-pointed. One word on screen (`あたり`) comes from another list.
- **Seen in the emulator:** "Reception / Welcome to Junker Headquarters. May I help you?", command menu
  Enter / Look / Examine / Talk, object list Reception / Poster / Front pod / Camera / Door,
  "Gillian / It's no use. She's protected by a shield." — stable over many messages.
- **Space, revisited:** at 6 bits per letter English still needs ~1.41x the Japanese bytes (measured on
  4,009 aligned pairs) against 1.9 KB of slack per scene: 41 messages fit in scene 1. The two unused
  kanji leads (`$88`, `$98`: 192 codes) are reserved for a **word dictionary** expanded in
  `decode_next_pair` (`$7272`): the 192 most frequent words as one 12-bit token each should bring English
  to ~0.95x the Japanese size. Needs ~2 KB for code + dictionary -> bank `$7B` or `$6D`, to be verified.

## Hardware test of the narrow-font build, and where resident code can live (2026-09-18, ninth pass)

- **PC Engine + Turbo EverDrive Pro: the narrow-font POC "looks good"** (Thomas) — 6-pixel letters readable on
  the CRT, picture stable while the hook switches MPR4 for every glyph, names and menus fine. Known oddities
  only: gap after F/z/digits, one Japanese menu word (`あたり`), Japanese intro/title.
- **The load table explains RAM:** byte 4 of each 8-byte entry is the destination bank minus `$68`
  (`$16` -> `$7E` scenes, `$1A` -> `$82` clip tables, `$13` -> `$7B`, `$05` -> `$6D`, `$04` -> `$6C` …), byte 6 the
  sector count. `$6D` receives 106 different images of up to 64 sectors (reaching `$7C`), `$6C` up to 100
  sectors (reaching `$84`). **Only `$68`-`$6A` are never a load target** — and `$68`'s tail is work RAM. So the
  "free" regions seen in `$7B`/`$6D`/`$72` are transient; they were even different at the title screen.
- Best remaining home for ~2 KB of resident data: **bank `$82` + `$1800-$1FFF`**. The boot load (LBA `0x36`,
  24 sectors) fills `$82-$87` and leaves that range `$FF` (ISO `0x1C800`); the six 3-sector table switches
  only rewrite `$82` + `$0000-$17FF`. Risk: the big `$6C` loads (cutscenes/acts) run over `$82`; what is
  reloaded afterwards has to be checked.
- **Dictionary simulation:** 192 tokens for frequent even-length letter groups (` the`, `you `, `ing `, …)
  bring the English from 1.41x to ~1.20x the Japanese bytes with a crude selection (1.5 KB of dictionary
  data). Scene 1 can take ~1.11x. Needs better token selection, more tokens (smaller pair alphabet) or
  light condensing of the text in tight scenes.
- **Title menu `初めから`:** three sprites (80x32 px at 80,144; patterns at VRAM `$6700/$6800/$6E40`). Not text
  in any encoding in RAM or on disc, and the sprite patterns are not on disc verbatim either, although the
  title background tiles are (406 tiles around ISO `0x11580`) — so the menu sprites are compressed or
  generated. Cosmetic; parked.

## Whole scenes fit: Huffman + word tokens, all-pairs cells (2026-09-18, tenth pass) — works in the emulator

- **The say commands cover the text area completely.** Scene 1: 552 true messages tile `0x250A-0x6876` byte for
  byte (two messages with colour codes had been dropped by my plausibility filter; candidates that start
  *inside* another message are chance hits of the byte pattern and are ignored — their bytes must not be
  patched). So a scene's text can be rewritten wholesale and every `12 ss 00 lo hi` re-pointed.
- **Coding** (`tools/snhuff.py`, tables in `translations/coding.json`): symbols = 76 glyphs + line break + end +
  150 word tokens (` the`, `you `, `Gillian`, `SNATCHER`, `investigat`…), canonical Huffman, max length 14:
  **4.05 bits per character** on the whole Sega CD script. An English message starts with the marker `1F FF`
  (impossible at the start of a Japanese message), so untouched scenes still decode as before.
  **Scene 1: Japanese 17,260 bytes -> English 17,841 bytes; limit 19,190.**
- **Decoder** (6280, `tools/snhack.py`): `decode_next_pair` (`$7272`) jumps to a trampoline in the dialogue bank
  tail (160 of 176 bytes: marker check, byte fetch through the game's own `$5341`, original entry code, and
  the map-and-call stub). The real work is in bank `$82` +`$1800` (1,896 of 2,048 bytes: glyph composer,
  resumable bit-serial Huffman decoder, token expansion, pairing into cells, tables, dictionary), reached by
  mapping `$82`->MPR4 and `$69`->MPR5 with interrupts off. `$360C` (nibble alignment, used only by the
  decoder itself) doubles as "English message in progress" (`$80`). Y and X are preserved
  (`decode_sentence_main` keeps its output index in Y).
- **All-pairs cells** (`tools/sncells.py`): cell number `n = left*77 + right` over 76 glyphs + BLANK, SJIS lead
  `$88-$9F` then `$E0-$E6`. Every glyph pairs with every other: no more gaps after F, z, digits or before
  punctuation. Cost: kanji in text that is still Japanese now shows as letter pairs.
- Seen in the emulator: reception dialogue, command menu, object list ("Front pod"), Gillian's remarks — clean.

## Not yet verified (claims from the public disassembly, see RESEARCH.md)

- Print loop at `$66D4`, glyphs via `EX_GETFNT`, custom-glyph override table at `$6A07`, the script
  command set. (The 12-bit text packing itself is now verified, see above.)

## Cutscene audio: why swapping tracks fails (superseded -- see "Cutscene audio: dubbed" below)

The intro narration was replaced by copying Sega CD track 3 over PC Engine track 17. The obvious next
step -- do the same for the other cutscenes -- does not work, and it took several dead ends to be
sure of that. Recorded here so the attempts are not repeated.

**How the game picks a track.** Not by timecode, which was the first guess and wasted a search of the
whole disc. Script command `$0E` reads the next script byte and stores it at `$26F5`; the CD state
machine in the dialogue bank masks it with `$7F`, rejects anything `>= $64`, and passes it to BIOS
`$E0B4`/`$E018` (`home/engine.asm` `cmd_0E_sub_0`, `home/dialogue.asm` `cd_playback_tick`). Codes
`$FC`/`$FD`/`$FE` are fade and stop, not tracks. So a scene names an audio track by *number*, in one
byte, and `tools/match_cutscenes.py`'s companion scan reads them straight out of the scene scripts.

**Why the tracks cannot be matched by sound.** The two versions do not share recordings. The
durations barely overlap: the PC Engine has 22 audio tracks, the Sega CD 20, and outside one
coincidence no two are the same length. Three successive attempts each produced confident-looking
matches that were artifacts:

1. *Best correlation over all lags.* Everything matched the longest Sega CD tracks, because the more
   lags a candidate offers, the better the luckiest one looks. Scores were not comparable between
   pairs.
2. *Correcting with a null.* Scoring each pair against the same track reversed -- same length, same
   statistics, no possible true alignment -- removed most of the bias and made the known-good intro
   pair stand out. But seven PC Engine tracks still claimed Sega CD 19.
3. *Requiring a one-to-one assignment.* This produced matches that were arithmetically impossible:
   a 149 s PC Engine cutscene assigned a 21 s Sega CD track. A replacement is cut to the PC Engine
   track's length, so a shorter source could only be padded with silence.

The instructive near miss: PC Engine 10 (422.20 s) and Sega CD 19 (422.63 s) agree in length to
0.43 s, and the matcher ranked them first with every rival at zero. Two tracks of equal length can
only align at offset 0 -- and there they correlate **0.04**, against 0.42 for the intro pair. The
score had come from overlapping a 107 s fragment at a +315 s lag. Equal duration was coincidence.

**What survives.** Scored properly -- envelope correlation with the PC Engine track fully contained
in the Sega CD one, benchmarked against the intro pair's 0.39 -- exactly one candidate beats the
benchmark: PC Engine 20 from Sega CD 14, at 0.48. It is in `PAIRS` in `tools/intro_audio.py`,
labelled unverified. Everything else lands between 0.13 and 0.32, i.e. nothing.

**The route that should work, if this is picked up again.** Do not swap tracks. The English speech
exists separately from the music in `PCMLD_01.BIN` (84.7 MB of RF5C164 PCM), which is already the
source for the ~1,200 in-game clips `tools/voices.py` replaces. Mixing the English narration onto
the *original PC Engine music bed* keeps the right music by construction and removes the matching
problem entirely. The work is in locating each cutscene's narration in that bank and its timing --
`$0E` gives the track a scene plays, and `work/aligned/<lba>.json` already names the Sega CD script
file for each scene, which is the thread to pull.

## The freeze at the end of the intro: bank $82 is a load target (fixed 2026-09-19, see below)

Reported from hardware as a hang at the end of the intro, after the car scene, on the shot of the
high-rise. Measured rather than guessed, by saving emulator states either side of the act change and
reading CD RAM out of them (`HuC.CDRAM`; bank $82 is at offset $4000, so the patch sits at $5800).

| frame | bank $82 + $1800 |
|---|---|
| 2000 (title) | intact -- exact 2048-byte match with the disc |
| 3000 (intro starts) | clobbered |
| through 40000 (11 min) | still clobbered, never restored |

The exact match at frame 2000 proves the address mapping, so the loss afterwards is real. The patch
was built on the assumption in its own docstring -- "Loaded once at boot ... the 3-sector table
switches do not reach it" -- but the cutscene/act loads do reach it. Nothing puts it back, so the
first English message decoded after a cutscene jumps into whatever the load left there. That is the
freeze, and it explains why text works when a scene is entered with the decoder still resident.

Do not compare old save states against a current build to check this: the payload changes whenever
the coding or the patch changes, so a stale state reports a difference that means nothing.

**What is actually safe, measured the same way.** Comparing every state across the act change for
regions that are never written:

- bank $68 tail, +$1BB3..$2000 (1101 bytes): all $FF on disc and still all $FF at runtime, through
  the whole intro and both act changes. Genuinely free -- unlike the engine bank's $5C40 tail, which
  is $FF on disc but work RAM at runtime.
- bank $6A trampolines: untouched, confirming $6A is never a load target.
- `CPU.MPR` is `ff f8 68 6a ...` in every state: **bank $68 is permanently mapped at MPR2**, so code
  in that tail is callable at $5BB3 without mapping anything first. MPR3-MPR6 all move across the act
  change; MPR2 does not.

**The shape of the fix this allows.** The payload splits into 695 bytes of code and 1229 bytes of
tables+dictionary. The code alone fits the 1101-byte safe tail. So the executable half moves to bank
$68, where it cannot be clobbered and is always mapped, and only the data half stays in $82 -- where
the code can check a magic word and re-read that one sector when a load has wiped it.

The re-read needs no hardcoded LBA, which matters because a flash cart boots the second data track
while an emulator reads the first: the game's own loader computes `sector = disc_base ($3F80) +
offset`, and $3F80 already holds the base of whichever track the console booted from.

The trampoline cannot grow -- bank $6A's tail is exactly 176 bytes and 174 are used -- but it does
not need to: `mapcall`'s `jsr $9800` becomes `jsr $5BB3`, the same three bytes.

## Cutscene audio: dubbed, by transcript instead of by sound (2026-09-19)

The section above concluded that most cutscene audio has to stay Japanese. That was true of swapping
tracks, not of the audio itself. What changed the answer: transcribing both sides.

**Where the English cutscene speech is.** Not in `PCMLD_01.BIN`. All 1,215 Sega CD PCM segments were
transcribed (Whisper large-v3-turbo, `work/asr/scd_asr.json`); the 165 the in-game voices do not use are
ordinary dialogue and phone messages, none longer than 15 s, none narration. The cutscene speech exists
only mixed into the Sega CD's CD-DA tracks. (Side finding: the Sega CD shows no text for voiced lines,
so its script files do not contain them -- transcripts are the only text of what the voices say.)

**Pairing.** Transcribing every CD-DA track of both discs (`work/asr/tracks_view.txt`) pairs them by
content at a glance -- the audio matcher's failures were never about missing counterparts:

| PCE | Sega CD | scene |
|---|---|---|
| 17 | 3 | intro narration |
| 19 | 4 (from 223 s) | Gillian's file after the cast roll (the Sega CD adds a Jamie scene before it) |
| 20 | 20 | "first day on the job" -- the matcher's 20 <- 14 was wrong |
| 3 | 6 | Chief's office |
| 4 | 7 | Random introduces himself |
| 5, 6 | 8, 9 | Metal Gear's case recap, split at different points |
| 7 | 10 | Queen's Hospital records, Jamie |
| 8, 9 | 11 | the turbo-cycle jump |
| 10 | 21 | Chin, Modnar's plan, Random's fireworks (both 408 s) |
| 11 | 12 | Harry's death |
| 12 | 13 | after the Snatcher, Mika |
| 13 | 14 | Jamie's video call |
| 14 | 15 | Mika, dinner at Christmas |
| 16 | 17, 19 | boarding, Metal's temporary body, closing narration |

PCE 1 (CD-player warning skit), 18, 21-23 carry no cutscene speech. Sega CD 18 (the Junkers' future)
and the Katrina/Mika farewell in Sega CD 17 have no PC Engine scene.

**The method** (`tools/cutscene_dub.py`): Demucs (htdemucs, two stems) splits each track into voice and
accompaniment. The PC Engine accompaniment is kept -- right music, exact length, every picture cue where
it was -- and English lines cut from the Sega CD voice stem are laid over it. Checked: Whisper on the PC
Engine accompaniment finds no Japanese left; Whisper on a finished mix reads clean English.

Line placement is a DTW warp from the English timeline onto the Japanese one over the speech on/off
patterns, steered by anchor words both languages share (names, places, numbers). Pairing lines one to
one does not work: Whisper splits sentences differently per language and the scripts differ. The
pictures are the same in both versions, so pauses between exchanges line up and pin the warp.

Things that had to be handled, each seen in real output:
- Whisper fills a 30 s window over music with a stock phrase ("The End", "Thank you.", 「ご視聴ありがとうございました」)
  and drops the lines in it -- this lost the opening lines of several Sega CD cutscenes. Transcribing each
  speech region of the voice stem separately fixes it; stock phrases and repeated-token junk are dropped.
- Chunk edges overlap, so a word can be heard twice: a line may not start before the previous one ended,
  and lines without a real pause between them are merged into one utterance.
- Where the English is longer, lines are pushed back and the schedule catches up in the next pause; a
  backward pass pulls late lines into earlier pauses so nothing runs past the end of the track.
- Where the PC Engine has lines the Sega CD cut or replaced, the Japanese voice stays in (`KEEP_JP`)
  rather than leaving the character silent; `PINS` fixes the rare line the warp cannot place.

Results: all 15 tracks rendered at exactly their original length, loudness within 2 dB of the original,
no clipping. Weak spots: PCE 10 263-300 s (the English Modnar speech is 16 s longer and runs into
Random's turn, caught up by 330 s); PCE 16 ends ~5 s late (the Sega CD's extra sneeze gag).

## The freeze fixed (2026-09-19)

Reproduced headlessly first: the old test scripts pressed START at frame 4000, which **skips the
intro** -- and with it the loads that wipe bank $82, so the emulator never froze. With START only at
the title and the menu, the old build stops on the high-rise shot at ~24,000 frames, exactly as on
hardware. The same input is the regression test now (`work/press_intro.txt`, 40,000 frames).

The fix (`tools/snhack.py`): all code moved to bank $68, which is mapped at MPR2 the whole time and never
a load target; only the Huffman tables and the dictionary stay at $82+$1800, behind a magic word "EN".
At the start of every English message the code checks the word and, when a load has wiped it, reads
sector 57 back. Traced across a full run: wiped at frame 2,785 (intro) and 11,087 (act change),
restored at 24,651 by the first English line at the reception, text correct from there on.

Three things the plan in BACKLOG got wrong, found by tracing:
- **The $68 tail is not all free.** The game keeps a runtime buffer at $5C00 (`cmd_queue_init` sets
  $25/$26 = $5C00) and writes it while text is on screen: up to $5C66 in our runs, up to $5CB9 in the
  disassembly author's. The first attempt, code at $5BB3, overwrote itself with it and the CPU ran
  into the font bank. The code now ends at $5FFF and starts at $5CE2 (floor $5CC0, asserted). 34 bytes
  of headroom are left there -- the code cannot grow much more.
- **$3F80 is the base *bank*, not a sector base.** The loader adds it to the destination bank; sector
  numbers go to the BIOS as they are, and the BIOS counts from the data track it booted from. So the
  data sector is 57 on both tracks.
- **The read has to copy the loader's handshake.** Calling CD_READ straight away with interrupts off
  hung inside the BIOS (polling $1800) while a voice clip was loading. What works is the loader's
  sequence: hold back the pending voice requests ($26F3/$26F7, restored after, so the line's voice still
  plays), `cli`, CD_PAUSE, wait for CD_STAT idle and $2638 clear, CD_READ (sector in $FC/$FD/$FE
  high..low, $FF = 0 local, destination $FA/$FB, byte count $F8/$F9), start over on error, `sei`. The BIOS
  zero page $F8-$FF is saved around it.

Restoring the block overwrites what the act load put at $82+$1800 (ISO 0x1A8800 after the intro).
Nothing visible broke in the emulator; the hardware test is the real check.

## Second hardware report: crash after Gillian gets the blaster (2026-09-19, late)

The intro, the reception and the Chief worked on hardware; the game crashed in Harry's lab after the
blaster. Not reproduced in the emulator (menu-driving that far headlessly was too slow), so this is
the likeliest cause rather than a proven one: the re-read of the tables happened at the first English
line after a load, and it pauses the CD. Right after the blaster the game flies to the abandoned
factory over CD-DA track 20; a re-read then stops the track, and the game, which cues its pictures to
the CD position, waits forever.

Changed: the re-read now happens inside the game's own scene loader. Every wipe seen so far is made by
`scene_loader_main` (the stack at the wipe returns to $54E5 and $41F1), so its success path
(`$54F1 stz $3F21`) now calls a hook that restores the block immediately -- the drive has just finished
the loader's read and no CD audio has started. Traced: wiped at frame 2,785 and 11,225, restored 11
frames later each time, intact long before any message. The message-time check stays as a fallback.
The intro still plays correctly, although the block now overwrites the load's own bytes at $82+$1800
immediately rather than after the intro.

Space: the code is 831 bytes at $5CC1-$5FFF; the game's buffer below it has reached $5CB9 in both
independent observations. There is no room left in bank $68.

## The crash after the blaster: reproduced and fixed (2026-09-19, night)

Reproduced in the emulator by playing there (reception -> Chief -> Engineering; checkpoints
`work/play/checkpoint_corridor.state`, `checkpoint_harry.state`): asking Harry about the Navigator and
then the Blaster crashes the old code exactly as on hardware -- the CPU ends in the I/O page inside the
text routine's mapping.

Cause, read straight out of RAM: **$5C00-$5FFF in bank $68 is the game's table of 10-byte animation
records** (`8a 84 00 04 00 ...`). Harry's scene has more animated objects than any scene measured
before, and its records ran to $5D0D -- through the decoder at $5CE2. The earlier "maximum" of $5CB9
was just the busiest scene anyone had looked at. Nothing at the top of bank $68 is safe.

Fix (`tools/snhack.py`): everything except a 57-byte loader hook moved back into the 2 KB block at
$82+$1800 -- magic word, dispatcher, code, tables, dictionary (1,926 bytes). The hook sits at
$5BB3-$5BEB, below the record table, a range that was untouched in 96 of 97 saved states (the
exception is the 18 Sep proof-of-concept build, which wrote there itself). Since the hook restores
the whole block right after every load, code and data always come back together.

Verified: the Harry checkpoint with the new code written into RAM (a state patcher) runs the same
Navigator/Blaster sequence without crashing and shows English text afterwards; the from-boot run plays
the intro into the reception with text; all 18,408 messages decode. The flight to the factory (CD-DA
track 20) has not been reached in the emulator yet.

## Title menu 初めから: the pixels are on the disc after all (2026-09-20)

Two earlier attempts concluded the glyphs were nowhere on the disc. They are -- the search just could not
see them. What happens: the title screen is LZ-compressed and decompressed **straight into VRAM**, so the
pixels never exist in RAM as a block (checked again here: at the frame the glyph appears, frame 1160, the
bytes are in no RAM at any interleave). But glyph pixels do not compress, so each bit-plane is stored as
one verbatim run of literals, and between the runs sits a short token for the zero rows at the bottom of
the sprite. A search for a whole 128-byte sprite, or even a whole 32-byte plane, therefore always failed;
the earlier "32-byte coincidence at ISO 0x1E9192" was the real data.

The menu text is not font output at all: all four bit-planes carry pixels, because the characters are
drawn in the title's gold gradient. They are part of the artwork.

**The runs can be rewritten in place.** Verified in the emulator: writing 26 bytes at ISO 0x1E9198 (plane 0
of the 初 sprite) put exactly those pixels on screen ($6780 plane 0 read back as the pattern written).
Overwriting 32 bytes instead -- past the literals, into the token -- blanked the glyph. So:

- the literal run length per plane is the budget; the rows after it are whatever the token produces
  (normally zeros, which suits lettering that does not reach the bottom row)
- no need to understand the compression, and nothing moves, so the sector layout stays as it is
- `tools/title_map.py` writes `work/title_literals.json`: per sprite, per plane, the ISO offset in both
  data tracks and the run length. The menu glyphs are at $6780 (初), $67C0 (め), $6880/$68C0 (から) with
  11-13 words per plane; planes that are mostly zeros match the stream's zero areas by accident and are
  not real runs.

Next: design the English lettering (16x16 sprites, gold gradient across the four planes, within each
plane's run length), write it with a tool like the font builder, patch both tracks, and check on hardware.

## The flickering: the cell mapping cost too much time in the interrupt (2026-09-20)

Reported from hardware: flicker in the lower half of the screen while text draws, and in the Chief's room
"the entire image shaking a bit, but only when scrolling through the options".

The renderer hook and the decoder run inside the game's frame interrupt, with interrupts disabled
(`mapcall` does `sei`). The game splits the screen with a raster interrupt (`rcr_irq_handler` in the
vblank handler), so anything that holds interrupts off long enough delays the split and the picture moves
-- and a menu redraw is the heaviest burst of cells there is, which is why scrolling shook the picture.

What cost the time: the cell mapping. A cell was `n = left * G1 + right` packed into an SJIS pair as
`n / 191`, `n % 191`, so every character needed a multiply by 90 and two divisions -- all by repeated
addition or subtraction, up to 90 iterations each. Roughly 3,500-3,700 cycles per cell against a frame of
~119,000 and a vblank of ~8,000-10,000: two characters a frame could fill the whole window.

The mapping is now division-free (`tools/sncells.py`): two left-glyphs share a lead byte and the trail
carries which half plus the right glyph,

    lead = $88 + (left >> 1)   (the $E0.. range follows $9F),   trail = $40 + (left & 1) * G1 + right

so both directions are a shift and a compare, about 100 cycles. All 8,100 cells still map to distinct
valid pairs, the trail never reaches $FF (max $F3) and the lead stays inside the two kanji ranges
(max $F4). The decoder no longer needs the cell number at all: it emits lead/trail from the two symbols
directly. The block in $82 shrank by 120 bytes as a side effect.

Two more cuts in the same path, after the report that the flicker was "pretty bad outside the factory"
(still the build without the mapping fix, but worth going further):

- the 16x16 cell buffer was cleared in full (32 bytes) for every cell, although the rows the glyphs cover
  are written outright -- the left glyph writes the high byte, the right glyph the low byte. Only the
  rows above and below need clearing: 14 bytes instead of 32.
- each glyph row went through a `fetch` subroutine that saved Y, indexed the font by X and restored Y.
  The font pointer now walks the rows itself (`lda (P)` + increment), which removes the call, the register
  juggling and the per-row index. A BLANK glyph points at nine zero bytes instead of being special-cased.

Together those are roughly another 600 cycles per cell, so the whole path is down from ~5,000 cycles to
roughly a quarter of that.

Not reproducible in the emulator: with +3,000 cycles added per call on purpose, Mednafen still showed no
jitter at all, so this one can only be judged on hardware.

## The English did not come from translations/scenes -- and five files of fixes never shipped (2026-09-21)

Katrina's file on Jordan kept showing Konami's US text -- age 18, blood type O-, no measurements --
even though `translations/scenes/0fe.tsv` had been retranslated from the Japanese a day earlier. The
retranslation was never in any build: **the builder prefers `work/scenes_resolved/` when it exists**,
and that directory is generated by `tools/resolve_refs.py` from `translations/scenes_ref/` plus the
user's own Sega CD disc. Hand edits to `translations/scenes/` are silently ignored while it is there.

`tools/build_all.py` now prints which directory it read and compares the two by **content**, warning
when a committed file says something different from the generated one.

Turning that check on found the real damage: **five files differed, 39 lines in all**, and they were
the hardware-driven corrections. The builds played on hardware had been telling the player to
"press the GUN'S START BUTTON" (Konami's Sega CD text for the Justifier light gun) where the PC Engine
wants SELECT, to "press the START button" where it wants RUN, and Konami's phrasing for the flashlight
where it wants button II. The corrections were all sitting in `translations/scenes/`, read by nothing.

Fixed by carrying those 39 lines into `translations/scenes_ref/` as `T` lines, so a regeneration keeps
them, and by retiring the stale `work/scenes_resolved/` so the build reads the committed text. The new
image has SELECT nine times, RUN four times, button II once, and no JUSTIFIER or START BUTTON at all.

The fix for the record itself was a decision, not a translation: the door quiz matches the **Japanese**
numbers (B 81, W 58, H 83), so those had to be on the file for the puzzle to be solvable, while the age
stays at the US 18 so it agrees with the rest of the English script ("Miss Seventeen", 2046). The
Japanese record gives 14, "Miss Thirteen", '41 -- and the quiz never asks her age, so keeping 18 costs
nothing. Changed in `translations/scenes_ref/0fe.tsv` (the source) and in the generated copy, because
`resolve_refs.py` currently stops on a missing Sega CD reference (KeyError 8435) and cannot regenerate.

## The keyboard is a picture, and how the letters got onto it (2026-09-21)

The overlay patch made the keys *type* Latin, but they still *showed* kana, and three builds in a row
looked untouched. The keys are not text in any form the build can reach: the panel is part of the
computer screen's compressed picture, decompressed into VRAM as background tiles (map rows 32-39, one
tile per key across two rows), and tiles are shared between keys that look alike. Only 1 of its 66 tiles
has a run of its pixels verbatim on the disc, so rewriting literal runs -- the title screen's trick --
does not apply.

What works is redrawing the tiles at runtime, from a routine in the overlay's padding
(`tools/keyboard.py`). It walks the panel's map cells and reads each cell's tile number out of the map
rather than inventing tiles, so sharing works in our favour: every lower half is blanked, which is what
we want. Four things it took, each of which failed first:

1. **The letters live in our own block in bank $82**, mapped in with `tma`/`tam` for the duration. The
   overlay's padding (426 bytes) could not hold the code and 156 bytes of letters and still leave room
   to save the caller's registers.
2. **It hangs off the store that chooses the keyboard** (`sta $351F`). The routine that picks the layout
   runs every frame; drawing there tore the screen apart.
3. **VRAM is written with the picture off** (CR bits 6-7 cleared, restored after). The VDC drops writes
   during active display -- that was the garbage on screen, not bad addresses.
4. **The cells past the 26 letters keep their kana codes.** Emptying them in the layout table made them
   unselectable, and the cursor walks *through* them to reach 決定, which is still the Enter key.

Getting there needed the player's own save: the EverDrive keeps backup RAM per game on the SD card
(`edturbo/gamedata/<game>.cue/bram_exp.brm`), and writing those 2048 bytes into the core's save RAM
(`retro_get_memory_data(0)`) before boot makes the game's own Continue work. That turns a card
round-trip into a minute in the emulator, and is how all of the above was measured.

Verified end to end: the keyboard reads A B C D E / F G H I J / K L M N O / P Q R S T / U V W X Y / Z,
typing GIBSON returns "Jean Jack Gibson. Runner, Junker Agency. Age: 55", KATRINA returns her file.

## Some scenes are on the disc twice, and the game reads the other one (2026-09-21)

Found the hard way. With the overlay patched and scene 0x0FE in English, hardware still showed the
katakana keyboard -- but the first key typed `Ａ`. The engine half was working while the screen in
front of it was the original data, which can only mean the game was reading a copy the build never
touched.

Track 24 carries the game's scene banks twice: the one the scene table names, and a second set at its
own offsets. **17 of the 33 scenes have one** (found by searching the track for each scene's first 16
bytes):

    0x09e -> 0x4f000 + 0x87000 0x8f000 0x97000      0x0fe -> 0x29800 and 0x7f000
    0x0ae -> 0x1800 and 0x57000                     0x13e -> 0x49800 and 0x9f000
    0x0de -> 0x19800 and 0x6f000                    0x1be -> 0x89800 and 0xdf000   ... and more

For most of them it makes no difference: the game loads the bank the table names, which is the one the
build patches, and the game reads English. The name-search screen is the exception -- Gibson's computer
reads the copy at **sector 83**, which is why three builds in a row looked untouched there.

`tools/scene_copies.py` finds them by the screen's own script header and builds them as well. A copy is
not the same bank: different offsets, and this one has 18 records where the table's has 91, so nothing
can be mapped by position. The English is keyed to each copy **by the Japanese it replaces**, message
for message and word for word, out of the scene's own translation file.

**If any other screen ever comes back Japanese on hardware while the build says it is translated, this
is the first thing to check.**

## The computer name search: how it really works, and in English (2026-09-21)

The screen Gillian looks a name up on -- Gibson's computer, and the reception asking your name -- took
three wrong attempts before it was understood. What it is:

**The scene holds a two-level table**, and the videophone (0x0AE) is the same screen with digits:

    20 <next group>  F1 <key word>            a group
      20 <next entry>  F1 <word>  <action>    an entry; the action is its record
      ...                                     the last entry of a group has no `20`

The player types; what is typed is matched against the entries of the group whose key holds the first
character; the first entry of every group is the fallback ("No matching names on file."). The phone
proves the shape: group `１` holds 110, 119, 177. So the entries are not read, they are compared with
what the player typed -- which is why translating them broke the search twice.

**The keys are not the scene's words.** An overlay (found by its own code at ISO 0x3B000 and 0x30000 on
track 02, loaded at $A000/$B000) drives every name-entry screen. It keeps ONE byte per character and
expands it only when it needs Shift-JIS:

    code < $20   ->  $81 <code + $40>     punctuation
    code $20-$3F ->  $82 <code + $1F>     digits and symbols
    code >= $40  ->  $83 <code>           katakana

Full-width Latin ($82 60..79) has no code there: it would need $41-$5A, which is katakana. The keys are
a 12-column grid of these codes ($00 empty, $01 the cell a key spills into, $02-$1B function keys) --
one grid for the phone's keypad, one for names -- and `$351F` says which. The engine sets that from the
first character of the scene's first key word: katakana gives the name grid, a $82 character gives the
keypad. Measured: first key `ア` -> buffer fills with $41, `$351F` = 3; first key `Ｚ` -> buffer fills
with $30 ('０'), `$351F` = 2.

That is exactly what came back from hardware when only the dictionary had been translated: "there are
no selectabile latin charcters I can choose numbers but they are not shown". Latin keys had selected the
keypad, whose keys are drawn as part of the videophone's picture -- so on Gibson's computer the grid was
blank and the field filled with digits.

**The English version** (`tools/keyboard.py`, `tools/namesearch.py`):

1. The expander gains a fourth range, **$A0-$B9 -> $82 60..79** (Ａ-Ｚ). Added, not swapped: digits,
   kana and punctuation keep their codes, so the videophone and Katrina's door are untouched. The 32
   bytes go in the overlay's own tail padding -- zero on disc, and still zero in RAM while the screen
   runs. Every address is read out of the copy being patched, so both copies and both tracks are done
   by one routine.
2. The kana grid becomes A-Z, five to a row, in the cells the kana rows had:
   `A B C D E / F G H I J / K L M N O / P Q R S T / U V W X Y / Z`.
3. The dictionary is written in the same full-width Latin, one character per cell, and the first key
   word keeps a katakana character in front of its letters so the grid is still chosen. Nothing can
   type that character; the letters after it are what the search matches on.
4. The kana groups already sorted names by first sound and those map onto Latin initials nearly one to
   one (カ行 = K, ガ行 = G, サ行 = S, マ行 = M), so the tree keeps its shape -- only the group order
   changes, one pointer each. The letters no name starts with go on the two groups that have none.

**The input field holds ten characters** (ten dashes, 12 px apart). `ＫＡＴＲＩＮＡＧＩＢＳＯＮ` cannot be
typed, which costs nothing: every long form leads to the same record as a short one that fits, and
`namesearch.py` asserts that for every record, that every name sits under a key carrying its first
letter, and that every letter is on exactly one key.

Verified in the emulator (the scene put in the reception's slot, which reaches it in a minute):
`$351F` = 3, walking the grid and typing gives internal `a0 a1 a2 a3 a4 a5` and the buffer
`8260 8261 8262 8263 8264 8265` = ＡＢＣＤＥＦ. The matcher reads that same buffer -- at $B9A6 it
terminates `$363E` with $FF at twice the character count and searches with it -- so typed text and the
dictionary meet in one encoding.

## Numbers are data, not text (2026-09-20)

Reported from hardware: Katrina's door quiz rejected every answer, and the videophone showed no numbers.

Both screens work the same way as the Jordan name search: the scene's word list holds the characters the
player types with and the values the typed string is matched against. In scene 0x17E those values are
００, ５０..５９, ６０, ６１, ６４, ７５, ７７, ８０..８４, ８６, ８８, ８９ -- Gibson's age (55) and Katrina's
measurements (81, 58, 83) among them. The translation pass rewrote them as letter-pair cells, so what the
player typed could never match and every answer was wrong, whichever way it was entered (81, 081, 810).
The videophone (0x0AE, 0x0BE) has the same thing: the ten keypad digits plus the numbers that can be
dialled, all rewritten, so the screen had no digits to show.

The rule now: a word made only of full-width digits is left alone. That covers the door quiz, the
videophone, and the year entries in 0x0CE. Scene word counts drop by exactly the digit entries
(0x0AE 104 -> 74, 0x0BE 68 -> 36, 0x17E 82 -> 58) and nothing else changes.

Together with the katakana grid finding above: anything on these screens that the game *matches* rather
than *reads* must stay in the original encoding.

## A menu column is sixteen letters wide (2026-09-21)

Reported from hardware: the topic 「鯨料理の店の事」 came out as **"About Buffalo re"**. Not a bad
translation -- a cut one.

Measured rather than guessed: a 24-letter word (`ABCDEFGHIJKLMNOPQRSTUVWX`) was written over a menu
word **in a save state's RAM** and the state loaded, which puts a menu on screen in 300 frames instead
of the 41,000 a boot needs. It came back as `ABCDEFGHIJKLMNOP` in the reception's object list (two
columns) and again in the command menu below it (one column). So the limit is the **column: eight
cells, sixteen letters**, the same whatever shape the menu is, and nothing warns -- the word is simply
drawn until the column ends. (`work/wtest5`, `work/wtest6`.)

The Japanese never met it: the widest word in a scene's list is eight characters, which is exactly the
column. English is what overran it -- 103 of 1,688 words, some badly ("Concerning Transportation" showed
nine of its letters).

95 were shortened to fit (the other 8 are the name-search dictionary, which is matched and never drawn).
`build_all.py` now carries `MENU_WIDTH = 16` and names any word that would be cut, so this cannot come
back silently: the build says `CUT OFF at 16 letters: ...` instead of the player finding it.

## Title menu: rewriting the artwork is a dead end, but the title's own RAM is wide open (2026-09-21)

The earlier plan was to rewrite the glyph pixels in place, inside the compressed title screen. Measured
per plane, it does not work: of the sixteen bit-planes the four menu glyphs are made of, **four are not
literal runs at all** and two more are only partly literal.

    sprite   plane 0   plane 1   plane 2   plane 3      (words of literal run / rows actually used)
    $6780    13 / 13   13 / 14   12 / 12   12 / 12      all four writable
    $67C0    13 / 13   13 / 14    - / 12    - / 11      planes 2-3 not literal
    $6880    12 / 13   13 / 13   12 / 13   11 / 11      writable
    $68C0    10 / 13    - / 13    - / 12    7 / 11      planes 1-2 not literal

A plane that cannot be written keeps the kana's pixels, and those bits still choose the colour, so
English drawn into the planes that *can* be written comes out with the old glyph showing through it.
The glyphs are gold-gradient artwork, not font output, so there is no plane to spare.

**What is open instead.** The title screen is one load: the table entry at ISO `0xC68D` reads **23 sectors
from LBA 958 into bank `$6C`** (ISO `0x1DF000-0x1EA800`), decompressed straight into VRAM. That load
carries **7,632 bytes of `$FF`** at ISO `0x1DF230` -- and, checked in two save states at the title, those
bytes are still `$FF` in RAM at `$6C+$0230` while the title is on screen. (The `$5C40` lesson applies:
free on disc is not free at runtime. Here it was checked, and it is free.)

So the room for English lettering is in the title's own block, in RAM exactly when it is needed: 512 bytes
carries four 16x16 sprites, and the resident block at `$82+$1800` is also alive at the title (magic `EN`
present in both title states), so code can reach it.

What is still missing before this can be built:

- **the hook**: something that runs once after the screen is decompressed and before the menu is drawn.
  The title sequence is the engine bank's state machine (`scene_init_block`, `scene_01..09_handler`,
  ISO `0xB000`, patchable on disc), driven through SCD calls `$8000/$8003/$8006`
- **the Continue glyphs**: only 初めから is in VRAM in the states here, because neither has save data.
  つづきから needs a title state with backup RAM present (the `bram_exp.brm` route already works)

### The menu word is 80x32, and the English fits it (2026-09-21)

The sprite table settles the geometry that two earlier notes guessed at. It is at VRAM `$1000`
(`VDC.SATB` in the save state), and with the menu up it holds four sprites:

    # 0  y=144 x=144  pattern $6E40  16x32  palette 1
    # 1  y=144 x=112  pattern $6800  32x32  palette 1
    # 2  y=144 x= 80  pattern $6700  32x32  palette 1
    # 3  y=158 x= 56  pattern $5280  16x16  palette 1     the cursor

So 初めから is **three sprites, 80x32 pixels**, exactly as the first note said -- not four 16x32 ones.
A 32x32 sprite's cells are `+$00` top-left, `+$40` top-right, `+$80` bottom-left, `+$C0` bottom-right, so
the word is five columns of (top cell, bottom cell): `$6700/$6780`, `$6740/$67C0`, `$6800/$6880`,
`$6840/$68C0`, `$6E40/$6EC0`. Missing the fifth is visible: the tail of ら stays sitting after the English.

Palette 1 is a gold ramp at 1-11 and blues at 12-15. The kana are blue (`$E`) with white (`$D`) along the
top of each stroke over a dark gold edge -- which is why the menu reads blue on a gold screen, and what
`tools/title_text.py` draws the English with.

**Checked on screen**: with those 640 words written into a save state's VRAM (`tools/patch_vram.py`), the
title shows `▶ NEW GAME` in the game's own colours. That is the whole picture side of the job done; what
is left is the 6280 code to write those patterns at runtime, and つづきから, which needs a title state
with save data before its sprites can be read the same way.

### The title menu in English, from a cold boot (2026-09-21)

Written into VRAM at runtime, since the pixels cannot be put on the disc (`tools/title_patch.py`):

- **the lettering and the routine** live in the title screen's own load -- 23 sectors from LBA 958 into
  bank `$6C`, which carries 7,632 bytes of `$FF`. 240 bytes of code at `$8230`, 1,280 of pixels at `$8400`.
  They are in RAM exactly while the title is up, and nowhere near anything else.
- **the hook** is `jsr $8006` in `scene_01_handler` (ISO `0x00B542`), with a 17-byte stub at `$5BEC`,
  just past the resident `loader_hook`. Engine state `$01` **is** the title -- ZP `$18` reads 1 there and
  5 or 3 in play -- so this runs at the title and nowhere else. The stub makes the displaced call first,
  maps `$6C` over MPR4, calls the routine, and restores MPR4 **from the stack**: `bank_switch_3` computes
  it from `$3F80`, so it is not a constant ($85 by that sum, $71 observed elsewhere).
- **it fires once** because it proceeds only while VRAM `$6780` still reads `$0253`, the first word of 初,
  which stops being true the moment it has written its own pixels there. The VDC drops VRAM writes during
  active display and 640 words is longer than a blanking interval, so it blanks through the game's own CR
  shadow (ZP `$28/$29`) and puts the picture back -- once, while the title is fading in.

Two things caught in the writing: the ten cells are *not* one contiguous stretch (`$6E80`, between the
16x32 sprite's halves, holds six non-zero words of something else, so that sprite is written as two runs
of one), and the routine grew past the address the pixels started at, which the build's own "is not free"
assertion caught rather than the emulator.

**Verified from a cold boot**, not a save state: the title comes up reading `▶ NEW GAME`, and pressing
start plays on through the RSS screen into the reception in English.

## The typed answers did not fit, so two puzzles could not be solved (2026-09-21)

Reported from hardware: on Napoleon's call the field takes four characters and the answer needs more.

He asks for a password, and the answer is カクメイ -- four kana. The scene script sizes the field to
match: `f8 2c 06 00 2b b9 34 <n> 00` writes `<n>` to `$34B9`, and the name-entry code refuses another
character once the count in `$36B2` reaches it (`$B98E`: `ldx $36B2 ; cpx $34B9 ; bcs`). Four is plenty
for カクメイ and hopeless for REVOLUTION, so in English the riddle could not be answered at all and the
game stopped there. The same is true of ベンソン (five) at Outer Heaven -- BENSON is six.

Konami hit this and widened it: the Sega CD's word list has REVOLUTION, and REIGN with RAIGN / RAIN /
RAINE / RANE beside it -- the same near-misses the Japanese carries in kana, for the same two passwords
(*"The revolution is ended"* and *"The hundred days reign"*).

- **Widening the field does not work, and this is the correction to what was written here first.**
  Ten is the engine's own default for these screens and every read of `$34B9` in the overlay compares it
  against the typed count, so it looked safe. On hardware, at ten and again at six, the screen stopped
  taking typed input and drew the answer tree as an ordinary two-column menu -- `WRONG / ☆ / REVOLUTION
  / WAR` beside `NO IDEA / DUNNO / NO CLUE / RAIGN`, with the empty input box still above it -- and
  picking from that menu did not work either. Something else reads this byte and has not been found.
  The fields are back to exactly what Konami wrote, and **the English is written to fit them**: four
  characters for Napoleon's two passwords (`OVER`, `RULE`, with his confirmations reworded to match),
  five at Outer Heaven. `tools/answers.py` now only reports; it writes nothing.
- **Still unsolved: BENSON is six characters in a five-character field**, and a character's name cannot
  be shortened the way a password can. The hospital's `Bishop` and `Knight` are the same. The build
  names them now (`'Benson' (6>5)`) instead of letting them reach a player. Fixing them means finding
  what else `$34B9` does.
- **Every copy, not just the one the scene table names.** There are nineteen of these commands on the
  two tracks and only six sit inside a scene slot: 0x0AE at sector 175 has a twin at 187, 0x22E at 558
  one at 554, track 24 carries more again. Patching the named copy alone is exactly how the name search
  stayed Japanese on hardware for a day. Matching on the whole setup sequence rather than on the store
  is what catches the copy at sector 146, whose answer tree sits behind a jump.
- **☆ is data too.** Every one of these screens carries a ☆ entry as its catch-all, matched and never
  shown -- and it had been translated, so "Star" sat in the middle of Napoleon's password list. The rule
  that protected ★ on the door quiz now covers ☆ as well.

The build reports the widening, and names any answer that would not fit even a full field -- a
wrong-answer entry that cannot be typed only costs its joke, a correct one makes the game unfinishable.

### つづきから -> CONTINUE, and how the second line was reachable at all (2026-09-21)

The Continue line only exists when there is a save to continue, so it could not be read from any save
state here. `tools/retro.py --bram` fixes that: the EverDrive keeps each game's 2 KB at
`edturbo/gamedata/<game>.cue/bram_exp.brm`, and loading that into `retro_get_memory_data(0)` before the
game runs boots the emulator straight into a title that offers both lines -- Thomas's own four saves.

With both on screen the sprite table says what the second line is, and it is not a copy of the first:

    y=176 x= 80  $6900  32x32     y=176 x=176  $6680  32x16
    y=176 x=112  $6A00  32x32     y=192 x=176  $6E00  16x16
    y=176 x=144  $6D00  32x32     y=192 x=-64  $6E80  16x16  -- parked off screen

セーブした所から is eight characters over 128 pixels, but the sprite that would carry the eighth column's
bottom half is **parked off screen**, so that corner cannot be drawn at all. CONTINUE is therefore fitted
into the seven whole columns and `$66C0` is cleared, which is also what takes the tail of ら off the end.

**The two lines use different colour indices for the same look.** Palette 3 is palette 1 with the blues
rotated: white and blue are `$D`/`$E` in one and `$C`/`$F` in the other, and 初めから is drawn in the first
pair, セーブした所から in the second. The game swaps palettes to highlight the selected line, so each row's
English keeps the indices its own kana used -- anything else would change colour when the cursor moves.

25 cells in three runs, 3,200 bytes of pixels. **Verified from a cold boot with the card's own save.**

### What actually chose "menu" over "keyboard": the first word's first byte (2026-09-22)

The correction to the correction above. The field width was never what turned Napoleon's screen into
a list of choices; it was the fallback word, changed in the same build.

Read out of bank `$7C` (the adventure-script interpreter, mapped at `$8000` as engine page `$14`,
disassembled with the new `tools/dis6280.py` since the published disassembly does not cover it):

    928B  jsr $5341 ; and #$03 ; sta $351F      ; one byte from the script stream, low two bits
    9284  lda $351F ; cmp #$02 ; bcc $928E      ; below 2: draw the tree as a two-column menu
    928B  jmp $B734                             ; 2 or 3: open the input screen (digits / letters)

`$5341` is the engine's banked stream reader, and the byte it returns is **the first byte of the first
word of the tree** -- the group's fallback entry (ハズレ, ベンソン以外), which is matched when nothing else
matched and never displayed on a typed screen. Katakana leads with `$83`, so `& 3` gives 3, the letter
grid; a full-width digit leads with `$82` and gives 2, the keypad. Written as letter-pair cells the lead
byte is whatever the first two letters produce, and the low bits are an accident:

    "Miss"            $9B -> 3   the grid      (the original translation, which is why it typed)
    "Wrong" / "WRONG" $98 -> 0   a menu        (the photo)
    "Besides Benson"  $9E -> 2   a digit keypad, for typing a name
    "Other Than Queen" $96 -> 2  the same, at the hospital

So the fallback is now data, like ☆: never translated. With that in place the field goes back to ten
-- the width the name search itself runs this code path at -- and the answers back to Konami's.

**Verified in the emulator on the rebuilt disc, from the HQ save through the phone:** `Use Metal Gear ->
Videophone -> Call`, dial 395644 (the keypad cursor is `1 2 3` at `$0607/09/0B`, `4 5 6` at `$0613/15/17`,
`7 8 9` at `$061F/21/23`, `0` at `$062D`, and the sixth digit dials by itself), Napoleon answers, and the
answer screen opens with **`$351F` = 3 and `$34B9` = 10** -- the letter grid and a ten-dash field. `ENDED`
typed reads as `a4 ad a3 a4 a3` in `$3690`. The overlay's variables were read straight out of the
emulator (`tools/keypad_probe.py`) rather than off 7-pixel sprites, which is what finally made the
cursor map reliable: a direction press immediately after a different direction is swallowed.

Two things noticed on the way, for the backlog: the "number not in service" card on the videophone is a
Japanese *graphic*, and Metal Gear's prompt said "Please enter using kana" (now "using the keyboard").

**And then it still said "Way off!"** -- the third thing on this screen that looks like text and is not.
A key types one byte ($A0-$B9 for A-Z, from the keyboard patch) and the matcher expands it to
full-width Latin, `$8260` for Ａ, before comparing with the entries. The entries had been written as
letter-pair cells like any menu word, so a correctly typed ENDED could never equal anything. This is
exactly what `namesearch.py` already does for the Jordan dictionary, and it now applies to every
typed-answer entry: stored as full-width Latin, upper case, one character per key (`answers.latin`).

**Verified end to end** on the rebuilt disc, from the HQ save: `Use Metal Gear -> Videophone -> Call`,
395644, Napoleon answers, the letter grid opens with a ten-dash field, `ENDED`, 決定 -- and Napoleon:
*"I see, you're the real thing all right... Come to Alton Plaza in the EXG district. We'll meet
there!!"*. So the three rules for these screens: the fallback word stays Japanese (it picks the
keyboard), the entries are full-width Latin (they are matched, not read), and the field is ten.

### Invisible kana keys under the letter grid (2026-09-22, from hardware)

Thomas's first call to Napoleon typed リルレレレレ although the keyboard showed A-Z; the second call
typed Latin and was accepted. Not a second unpatched overlay -- both copies on both tracks carry the
patch, and the overlay comes from one load, LBA 110-121 into `$7B-$7D`. It was the leftover cells: the
kana grid has more character cells than the alphabet needs, and the patch had kept their codes so the
cursor could still walk down to 決定. Drawn blank, but a press on one typed the kana it still held --
ラリルレロ, the row right below Z, exactly where a player heads for 決定 the first time.

The cursor code settles what to put there (`$B903` in the overlay): `$00` is a wall -- the move is
cancelled -- and `$01` is glass, stepped over until a real key. The leftovers are now `$01`: crossable,
never landed on, nothing to type. 決定 turns out to be code `$03` (a wide key, ten cells of it), the
backspace `$1B`, the ゛゜ keys `$02/$04`, all untouched. Verified: from Z, down lands on backspace,
right walks over the glass to 決定, and Napoleon accepts ENDED as before.

Still worth knowing on that screen: backspace is a blank cell under Z, and the "number not in service"
card is a Japanese graphic.

### The keyboard patch's "padding" was the keypad's walls; and the sei that held off the raster split (2026-09-22)

Two more from Thomas's hardware session, both mine.

**Numbers on the videophone "sometimes don't work well."** `keyboard.py` had put its display-off helper
and its variables into what looked like two short runs of padding in the overlay. They are the **wall
rows** of the two keyboard grids -- the `$00` cells the cursor may not enter: `$BAA1` is the keypad's
rows below the 0 key running into the letter grid's top row, `$BB3A` the letter grid's bottom row. With
code in them they became keys: the cursor could walk below the 0 and type whichever byte of the helper
it landed on. The overlay's one genuine tail run (`$BE56`, 426 bytes) holds all four pieces (expander
32, draw 287, fetch 32, vars 10), so everything lives there now, and the build checks both grids come
out with walls exactly where the original has them and the keypad byte-identical.

**The portrait flickers on the videophone** while Napoleon talks and while menus redraw. `mapcall` in
the text hook did `sei` around every glyph so a bank switch could not be interrupted -- but the engine's
interrupt handler saves MPR3-6 on entry and restores them on exit (`vblank_irq_handler`), so the sei
was never needed, and it held off the raster interrupt for a whole glyph. The videophone draws the
portrait below a mid-frame split, which is why only that screen, and only the portrait, showed it.
The sei is gone. The emulator cannot show this either way (240 frames of Napoleon talking: not a line
of jitter, before or after), so it is a hardware check.

Verified from a cold boot with the card's save: the keypad cursor is refused below the 0 again, and
Napoleon still accepts ENDED.

**Confirmed on hardware (22 Sep, image of 12:12):** the keypad behaves, the portrait no longer flickers
while Napoleon talks or menus redraw, and the Alton Plaza scene with him plays through. So the `sei`
was the flicker, and the interrupt handler's own bank save/restore is all the protection the glyph hook
needs -- which also means the "picture shaking" fix of the 20th (cheaper cell mapping) had only shortened
the window, not removed it.

### Every duplicated scene is built now, not just the name search (2026-09-22, from hardware)

Outer Heaven's entrance came up with its menu in Japanese words drawn through the English renderer --
「メタルギア使う」 with 使 as "cJ", 「聞く」 as "AOく" -- while the spoken lines were English. Scene 0x1BE has
a twin at sector 275 of track 24 that the build never touched; the game loaded that one. The name
search taught this on the 21st (0x0FE at sector 83) and the fix had been made for that scene alone.

`build_all.py` now finds every copy of every scene on both tracks -- by the scene's first 48 bytes,
then insisting the whole script matches, because three places (0x0AE at sector 3, 0x1CE at 122,
0x27E at 205) share a leading sector with a scene and are something else after it -- and builds each
with the scene's translation keyed by the Japanese it replaces. Eight real copies on track 24, the
0x09E-0x12E set being four table-named scenes with the same content.

None of the copies can grow: every one is packed against data. 0x1BE is a scene the named build had
grown by a sector, so its copy was 398 bytes short. The Sega CD text for that scene is three to five
times the length of the Japanese (Metal Gear's scan reports), so 27 of its wordiest lines were cut
back to what they say; it now fits with 18 bytes over. The build names a copy that will not fit:
`THIS COPY STAYS JAPANESE`.

Also from the same session: the videophone directory called Plato's Cavern "J Division" (0x0AE, two
words) -- it reads Plato's Cavern now, as 0x18E already did.

### Two scenes had never had their menu words at all; and copies take the scene's layout (2026-09-22)

"Still like that" -- the J-Division street, menu in Japanese through the English renderer, on the
image that built every copy. Two separate faults under one symptom:

- **The copies' layout.** `scene_copies.describe()` works out a copy's text start from its own message
  chains, and on the twins of 0x15E and 0x1DE it accepted a chance chain *inside the word list*, so it saw
  no words before the text and left every menu word Japanese. A real copy is byte-identical to its scene
  through the script and the word list (that is now the test for being a copy), so the build takes
  `text_start` and `words` from the scene and keeps only the copy's own messages beyond them.
- **0x19E and 0x1CE had no word list on record** -- `words: 0` in the scene description since the first
  dump, so their menus were never translated in any copy. 0x19E keeps a 30-byte table between its last
  word and its first message, which defeats a finder that walks back from the text. 0x1CE is worse: a
  chance "message" decodes inside its word list, the text was recorded as starting there, and **the build
  had been writing English text over the menu words** since the first full build. `scenes.py` now looks
  for the fullest word run near the text when the walk-back finds nothing, and moves the text start past
  it when it has to: 0x19E 67 words, 0x1CE 73 words and its text from 0x1E35 instead of 0x1C00, one fake
  message dropped. 44 of the 140 words had no English anywhere yet and were written now; the rest were
  already translated in other scenes. Nothing else in `work/scenes/` changed.

### The copies were spilling into the next scene; and a gate in front of the card (2026-09-22, evening)

Writing `tools/verify_build.py` -- one check per fault found on hardware -- found a fault nobody had
seen yet. Its "both tracks hold every scene identically" check failed for 0x09E, 0x0FE and 0x13E: on
track 24 the first sectors of each, the *script*, were Huffman text. The copies on that track are packed
tighter than the scenes they copy (fewer records, the next slot straight after), and the copy step had
given each copy the scene's own size, so `build_scene`'s last text span ran on into whatever came next:
0x19E's twin at sector 243 over 0x0FE at 254, 0x1DE's at 307 over 0x13E at 318, 0x13E's at 147 over
0x09E at 158. It was on the image of 13:23. A copy's room is now bounded by the next slot on its track.

Three copies had only ever "fitted" by spilling: 0x13E's (469 bytes short), 0x15E's (430), 0x19E's (261).
Paid for in words -- 29, 51 and 19 lines cut back to what the Japanese says -- and they fit with 11, 15
and 21 bytes over. Tight, and the build says so whenever they stop fitting.

The gate: `./build.sh` runs `verify_build.py` between the build and the merge, `./deploy_sd.sh` runs it
again and refuses an image that fails or is older than the last report. The checks are listed in
BUILD.md against the evening each one cost. The first run of the verifier also found that its own
sector slicing was wrong (the track is not aligned the way a naive 2352-byte cut assumes) and that a
moved menu word leaves its Japanese in the old slot, unreferenced -- a check has to follow the reference.

### Seven lines no chain reached; and a check that every say lands on English (2026-09-22, night)

Leaving Plato's Cavern's store, Metal said one line in Japanese: 「・・・店の外に出ました。」. It is in
0x19E at +0x27B3, in the nineteen bytes between the word list and what `scenes.py` called the first
message. The scene lists are built by following back-to-back messages, and that line is in no chain --
nor are six others across the game: two more of Metal's arrivals in 0x1CE before its text start
(「・・・ニールセン家前に出ました。」, 「容疑者、フレディ・ニールセンの家の前です。」), and four *inside* the
text area (three of Napoleon's replies in 0x0CE, 「誰かの声がしましたよ。」 in 0x1CE). The four inside were
worse than untranslated: the repacked English was written over them, so their say commands pointed at
the middle of some other line's Huffman stream.

`scenes.py` now takes every say command (`63 12 ss 00 lo hi`) whose target decodes as Japanese, after
the word list and inside the loaded block, and adds it to the chain and the regions -- text start moves
down to cover the ones before it (0x19E 0x27D1 -> 0x27B3, 0x1CE 0x1E35 -> 0x1E03). Only 0x0CE, 0x19E
and 0x1CE changed. `verify_build.py` has the matching check: every say in a built script must point at
a message that decodes as English to its end symbol. Run against the previous image it named exactly
those seven; nothing else on the disc is reached this way.

Naming: the place is "Plato's Cavern" everywhere now (Konami's name, 72 uses; the doorman's word at
Outer Heaven said "Joy" and a menu word said "Plato's Cave"). "Freddy" for フレディ, as the 34 existing
lines have it.

## The shootout at Ivan's door: a control code the coding never had (2026-09-23, from hardware)

Thomas, on the previous image: at Ivan's door "the scene was glitching out and eventually I could not
shoot back cause there was no cursor". Reproduced in the emulator and fixed.

**What it was.** Forty messages on the disc end in `<82F5>`, and they are exactly the lines spoken as a
shootout begins: 「ギリアン、危ないっ！！」 at Ivan's door, 「頭のスリットの部分を狙って下さい！！」 for Lisa,
「インセクターです！ブラスターで応戦して下さい。」 in the factory, 「鏡の反射を使って、フレディを撃って下さい！」.
`<82F5>` means *close this box without waiting for a button*. The English coding (`snhuff.py`) had two
control symbols, line break and end, so every English line waited -- and behind the waiting box the
shootout had already started: Ivan's shots land, the life bar runs down, the cursor never appears
because the text box owns the pad. In the emulator, from the same state, the original shows "aim for the
slit" and is fighting fifty frames later; the build sat on "Aim for the slit on its head!!" for a
thousand frames with the button marker blinking.

**The fix.** A third control symbol, NOWAIT (G+2; tokens now start at G+3), appended by the builders
whenever the Japanese message ends in `<82F5>`, and emitted by the 6280 decoder as the pair `82 F5`
exactly as a line break is emitted as `82 F2`. The canonical code was not rebuilt: `]` (unused in the
English) gave up half of its length-14 leaf, so NOWAIT and `]` are both 15 bits and every other code
is unchanged. Verified in the emulator on the Lisa sequence: the line closes itself, the shootout runs.
`verify_build.py` now fails if any built line whose Japanese ends in `<82F5>` decodes without NOWAIT.

**How it was reproduced without a save.** Scene 0x09E is Konami's own *command debug* menu -- every
chapter start and, under シューティング, every shooting sequence by name. The scene loader
(`scene_loader_main`, $5451) takes the table entry `6 + scene number` from bank $68 (`$351D` holds the
number), so pointing the reception's entry (#16, ISO 0xC585) at LBA 0x9E boots straight into the menu.
`tools/debug_menu.py` makes that research image from `build-en` or `disc`, boots it, and walks the menus
on screenshots (its input is polled with a cooldown: one-frame presses land two times in three).
Before finding this, two other suspects were cleared: the loader hook's re-read of the decoder block
(the original keeps $FF there during a shootout, nothing to clobber), and the keyboard patch in the
overlay's tail (the shootout leaves those 426 bytes untouched; it rewrites 13 bytes at overlay +$5DE).

### Door animations wrong on hardware, right in the emulator (2026-09-23, open)

Thomas, end of Act 1 on the 17:03 image: "the scenes with door animations are all messed up as the door
graphic overlays the main graphics at times". Ivan's door: pressing SELECT draws the blaster and the
shootout plays, so the `<82F5>` fix above was real but not the whole report.

Ruled out so far: (1) scene data -- every byte the build changes outside the text regions and the word
lists is a re-pointed say, a moved-word reference or a widened answer field (checked for all 33 scenes);
(2) the bank $68 tail -- $5BB3-$5BFF is $FF on disc and the loader hook and title stub sit there; (3) the
emulator -- the knock at Room 301 captured frame by frame, 420 frames, is pixel-identical to the
original above the text line, on the same story path (reached through the debug menu's "Investigate
Ivan", then Look/Ask/Show montage photo/Move Room 301, `debug_menu.py` and the step tool). So it is a
timing effect the emulator does not show. The one timing change since doors were last seen right on
hardware is the `sei` taken out of `mapcall` on 22 Sep. Two control images were made for the card:
the untouched Japanese disc as one image (does the EverDrive show it at all?) and the build with the
sei put back (`SNATCHER_SEI=1 ./build.sh`, A/B only). Next: the same door on all three.

24 Sep: Thomas played all of Act 2 on the same code and "doors looked fine this far" -- so the fault is not
every door; the ones seen wrong were at the end of Act 1 (Ivan's, Freddy's). The A/B stands, on those doors.

24 Sep, late, on the 19:51 image (same code): the abandoned factory, where the door glitch was first seen on
the 17:03 image, "does not have any of the graphics glitches we saw before". Same door code, same scene, no
glitch -- which points away from the build's timing and towards something that varies between runs (the
card, the console's warm-up, where in the scene the animation is interrupted). The A/B on Ivan's and Freddy's
doors is still the test, but it now needs a repeat on the same image first to know the fault is even stable.

## Konami's command-debug menu, mapped (2026-09-23)

Scene 0x09E is Konami's own test menu, and it reaches every chapter and every shootout: seven top-level
entries, five act submenus of chapter starts in story order, eight shootouts and a VRAM test -- 39 entries,
each run in the emulator on the original disc and mapped to the scene it lands in (`docs/DEBUG_MENU.md`).
The retail game never shows the menu, but it does load the scene: the save/quit dialogue and the memory-error
messages live there, so its English was already in the build.

Three things worth knowing. A chapter entry calls a chain of flag routines first (`1c 4e addr`, each routine
a list of `54 flag`), every later chapter calling every earlier one, so the story state is what play would have
left -- but only between scenes: Ivan is still not home on "Investigate Ivan" until the Freddy visit. A
shootout entry runs the sequence inside the debug scene (`1c 6b var value`, then the loads), so `$351D` stays
0 -- a shootout is an action any scene can start, which is why the debug version of Ivan's door skips the
door dialogue. And the jump itself is `f9 2d scene 00 offset`, confirmed by `$351D` on all 39 entries; the
interpreter in bank $7C is not in the disassembly, so the command names in the reference are ours.

`tools/debug_menu.py` now takes entries by name (`go work/debug_en "Shooting/With Ivan"`) and lists them.

## Oleen Hospital: the aligner drifted, and a scene's worth of voices was never paired (2026-09-23, from hardware)

Thomas, Act 2: "in the first hospital there is Japanese dialog after Metal says Snatchers can't tolerate
dogs" -- spoken, and "the other ones seem fitting but Japanese". The text was fine: every say in 0x1FE lands
on English. The voices were not. Metal's line (table 94, clip 90) had been placed by the LaBSE stray sweep
(`clip_fixups.tsv`), and nothing after it in the scene had a take: Gillian's "wrong tree", "Hmm, Olean
Hospital", the HQ emergency call, Alice dead at Katrina's -- 24 clips, A091-A115, all `None` in
`clip_align.json`. The cause is one stretch where the order-preserving aligner slipped: it had given the
Oleen takes (382-398) to Napoleon's Santa-suit scene (A038-A051), so the tissues were handed over to
"It's Alice!" and "The dog is dead" -- fitting nothing, and Oleen was left with no takes to claim.

Fixed with 35 hand pairs, read off the Whisper transcripts side by side (`work/asr/pce_asr.json`,
`scd_asr.json`), and two rule changes in `voices.py`'s `fixups()`: a hand pair now **replaces** the aligner's
pair for that clip, and it **may reuse** a take another clip plays -- the game says the same line in two
places (the HQ call, "Gillian, we should hurry"), and each slot gets its own copy of the audio anyway. 1,084
clips English now (was 1,062); the gate's floor raised to match.

Still 199 clips with no take. Most are sound effects and the debug/save lines, but this stretch shows the
aligner can drift for a whole scene; the remaining Japanese voices heard in play will be re-paired the
same way, by transcript, as they are reported.

## The voices had twins too: 244 clips the console played in Japanese (2026-09-24, from hardware)

Thomas, Act 2: "after the turbocycle scene in front of Queen's Hospital all dialog is Japanese but the last
words from Metal". Those clips were paired and re-encoded -- on track 02. The same lesson as the scene
twins of 21 Sep, one floor down: the EverDrive serves the disc's *last* data track, track 24 carries every
speech clip a second time, and 244 of those copies sit at an offset other than the table's (179 of them
two sectors earlier, 48 of them 4,957 sectors earlier). `voices.py` replaced a copy on track 24 only when it
sat at the same offset as on track 02, so on the track the console reads, 244 clips were still the Japanese
recording -- a whole scene at a time where the shifted region runs, with one English line at its edge.

`voices.py` now finds every copy of a clip's original bytes on both tracks and replaces each (490 copies at
other offsets, once every duplicate is counted). `verify_build.py` checks that no paired clip survives in
Japanese anywhere on either built track; on the previous image it named 476. The rule stands: anything on
this disc may exist twice, and the second copy is the one the cart plays.

## The staff roll: kanji names through the letter-pair hook (2026-09-24, from hardware)

Thomas, at the very end: the credits headings (katakana) were fine, the names were letter salad -- "dく iP TD",
"e* w/ pb O&". The staff roll is plain SJIS in the image loaded from LBA 0x82 (bank $85): 45 headings, then
68 names, each a line of 14 full-width cells padded with full-width spaces, separated by `FF` and the
colour codes `FE 01 / FE 02 / F9 80 / F9 82`; the opening roll's 29 headings sit the same way at sector 170.
It is drawn by the dialogue renderer, so it goes through the glyph hook -- and a kanji whose lead byte is
`$88-$9F` or `$E0-$EF` is, to the hook, a letter-pair cell. The game's dialogue never uses those leads
(that is why the cells could take them); the names in the credits do.

The fix is the translation the roll was missing anyway: `translations/credits.tsv` gives every heading and
name in English (names romanised surname last, three readings marked as guesses in the file), and
`tools/credits.py` writes each line as letter-pair cells centred in the same byte slot -- the roll's
timing and layout are untouched -- into the ending roll's image and its copy on track 24. 98 of the 103 lines
of that roll; the rest are two blanks and three lines that decode as no name at all.
`verify_build.py` checks the built image against the rendered English, line by line, in every copy.
(The first version of this step also rewrote the opening roll -- see the next section for what that did.) The Sega CD's own credits are graphics, so there was no Konami
text to take the wording from.

### The opening roll is the cutscene engine's, and I broke the intro with it (2026-09-24, from hardware)

The 19:51 image put garbage tiles across the intro. Cause: `credits.py` had also translated the 29 headings of
the *opening* roll at sector 170 -- the credits drawn over the intro cutscene. Those are drawn by the cutscene
engine with its own font, which renders kanji perfectly well and knows nothing of our letter-pair cells; fed
cell codes, it drew tile salad. Only the ending roll (the image at LBA 0x82) goes through the dialogue renderer
and the glyph hook, which is what the photographs had shown. `credits.py` now rewrites that one image and its
exact copies, nothing else, and the gate checks the ending roll by image. The lesson generalises: a byte on this
disc is not text because it decodes as text -- it is text because of who draws it.
