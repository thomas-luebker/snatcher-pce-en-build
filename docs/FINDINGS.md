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
