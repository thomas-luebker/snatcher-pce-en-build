# Audio: can the Sega CD English voices replace the Japanese ones? (investigation, 2026-09-18)

Short answer: **the in-game voice lines, yes, and more easily than expected; the voiced cutscenes, only
with a lot of manual audio work.** The PCE game plays voice in two completely different ways:

1. **~1,180 dry ADPCM clips** (speech + some SFX, ~95 min, 16 kHz) on Track 02, indexed by six plain
   8-byte-per-clip tables (LBA, sector count, rate, play mode). Fully relocatable and resizable by editing
   the tables. The Sega CD version stores the equivalent as **1,214 PCM segments at the same 16 kHz** in
   one file (`PCMLD_01.BIN`), and a GPL extractor exists.
2. **Voiced cinematics baked into CD-DA tracks** (voice + music + SFX already mixed, ~34 min across
   ~14 tracks), synchronised to the picture by sub-Q timecodes in the script. Same on the Sega CD
   ("rest of the dialogue is in the redbook tracks, mixed with music").

Legend: **[V]** verified here (measurement / emulator / bytes on disc), **[D]** read from the public
disassembly and interpreted by me (code logic checked, not traced in a debugger), **[I]** inference,
**[W]** from the web.

Scratch files are in `work/audio/` (gitignored): `cliptable.py` (table parser + stats), `okidec.py`
(decoder), `okienc.py` (encoder + SNR test), `adlog.py` (emulator audio-state logger), `specgram.py`,
`verify_xcorr.py`, logs `log_*.txt`, `trackmap.txt`, decoded WAVs in `clips/`, spectrogram sheets `spec_*.png`.

---

## 1. How the PCE game plays voice

### 1.1 The playback code [D, partly V]

`reference/snatcher-disasm/home/dialogue.asm` `$6000-$6371` is the CD/ADPCM driver. **Its comments name the
BIOS calls wrongly** (e.g. `$E033` "CD sector read", `$E03C` "CD ADPCM stream"). With the real System
Card 3.0 jump table the calls are:

| Address | Real BIOS call | Used in |
|---|---|---|
| `$E033` | `AD_TRANS` (CD sectors -> ADPCM RAM) | handler 0/1 at `$6281` |
| `$E03C` | `AD_PLAY` (play from ADPCM RAM) | handler 3 `$62ED`, handler 7 `$62C2` |
| `$E03F` | `AD_CPLAY` (stream ADPCM straight from CD) | handler 2 `$631D` |
| `$E042` / `$E045` | `AD_STOP` / `AD_STAT` | cancel, busy polling (`$6219`, `$6360`, script cmd `$0A`) |
| `$E012` / `$E018` / `$E02D` / `$E01E` | `CD_PLAY` / `CD_PAUSE` / `CD_FADE` / `CD_SUBQ` | CD-DA state machine `$6000-$60EF` |

No direct writes to `$1808-$180E` were found in the disassembled parts; everything goes through the BIOS.

Mechanism:
- `bank_mpr4_save` (`$6140`) maps physical bank `[$3F80] + $1A` into MPR4 (`$8000`). `$3F80` = `$68` in the
  save state [V], so this is bank `$82` = **`HuC.CDRAM` offset `0x4000`** (not SysCardRAM).
- **Table A** at `$8000`: 8-byte entries, index 1-based, requested by writing the index to `$26F3`
  (`$635D`; issued by animation-script opcode `$F6 idx`, `dialogue_r20.inc` `$791B`).
- **Table B** at `$8800`: 8-byte entries, requested via `$26F4` (adventure-script cmd `$0C idx`,
  animation-script opcode `$EA idx`). Plays a *slice* of what is already in ADPCM RAM (sound-effect banks).
- `cd_status_poll` (`$6219`, called from the frame ISR) services the requests; `$230E` holds the priority
  of the playing clip; a new request with lower priority is dropped (`cmp $230E / bcc`).
- Script cmd `$0A` (`$4C21`) blocks until no request is pending **and `AD_STAT` reports idle** — i.e.
  the script waits for the *actual end of the clip*, not for a fixed number of frames.

### 1.2 Table format [V for the bytes, D for the field meaning, V for LBA/count/rate]

Table A entry: `prio, cmd, lbaH, lbaL, lbaM, countL, countH, rate`

| cmd | meaning | count range on disc |
|---|---|---|
| 1 | `AD_TRANS` only (load an SFX bank; slices then played through table B), rate byte 0 | 3-31 sectors |
| 2 | `AD_TRANS`, then `AD_PLAY` of `count*2048` bytes (`_AH = count<<3`) | 2-31 sectors (hard max 31: one byte) |
| 3 | `AD_CPLAY` — streamed from CD, not limited by the 64 KB buffer | 32-126 sectors (16-bit field) |

Table B entry: `prio, addrL, addrH, lenL, lenH, rate, mode, 0` (e.g. `01 00 28 00 28 0e 00 00` = play
`$2800` bytes from ADPCM address `$2800`). 40 entries, identical in all six tables.

Example (first voiced-era table, RAM = disc): `A25 = 08 02 00 09 20 14 00 0e` -> prio 8, load+play,
LBA `0x002009` = 8201, 20 sectors, rate code 14.

### 1.3 Where the tables and clips are on disc [V]

- Bank `$82` in the first-dialogue save state is byte-identical to **ISO sector 54** (`0x1B000`, 0x2000 bytes).
- Six tables, one bank each, at **ISO sectors 86, 90, 94, 98, 102, 106** (`0x2B000 + n*0x2000`). Sector 54 is
  the boot copy of table 86 (differs only in fill bytes `0x1086-0x17FF`). Identical in Track 02 and Track 24.
  Which game section loads which table was not traced [unknown]; the six clip regions are disjoint and
  ascending, so they look like six consecutive story sections [I].
- Each table's clips are **contiguous, sector-aligned, back to back**:

| Table @sector | A entries (cmd1/2/3) | Clip LBA range (Track 02) | Sectors | Longest clip |
|---|---|---|---|---|
| 86 | 134 (15/104/15) | 7858-10246 | 2388 | 126 sect = 32.3 s |
| 90 | 254 (15/215/24) | 10418-14610 | 4192 | 73 |
| 94 | 225 (14/197/14) | 15026-18462 | 3436 | 65 |
| 98 | **255** (15/214/26) — full, index is one byte | 18610-22680 | 4070 | 80 |
| 102 | 245 (15/198/32) | 23218-27479 | 4261 | 72 |
| 106 | 216 (17/131/68) | 27826-33594 | 5768 | 105 |

- **Totals:** 1,329 entries; by content hash **1,212 unique** (31 SFX banks, 1,002 load+play clips,
  179 streamed clips). Unique load+play = 13,365 sectors = **57.0 min**, streamed = 8,609 sectors =
  **36.7 min**, SFX banks 1.7 min -> **~95 min / 45.8 MB of ADPCM**, i.e. 75 % of the 70 MB data track.
  (Durations include the padding to the sector boundary, <0.26 s per clip.)
- Every clip starts with a run of `0x00` and ends with `0x88` padding to the sector end (2 clips: `0x80`).
- **The LBAs are Track 02 addresses.** Proof 1: the emulator's CD state shows absolute sector 14373 for
  the first ADPCM load = Track 02 start (4174) + 10199 = entry A133 of table 86. Proof 2: in Track 02
  all 1,329 clips end in `0x88` padding; in Track 24, tables 90 and 94 do not fit (only 34/254 and 212/225
  clips end in padding — the data there is shifted, cf. the "+2 sectors" group in FINDINGS.md). Track 24
  differs from Track 02 in sectors 10777-15025 and 18108-18461 of the audio area. So **audio is read from
  Track 02**, and Track 24 cannot be a working mirror for sections 2-3 as it stands. [V for the facts, I for
  "never read from Track 24"].
- The gaps between the regions (10246-10418, 14610-15026, 18462-18610, 22680-23218, 27479-27826; ~1,620
  sectors) hold unreferenced ADPCM-looking data that differs between the two tracks; the tail
  33594-34120 has 150 zero sectors. Possibly mastering filler = free space [I, unverified].
- Track 02 only: two more table-like blocks at sectors 162/166 with other LBAs (5882...) and no B part —
  probably stale data from an earlier build [I].

### 1.4 What the clips are [V by spectrogram of 12 samples, I for the whole set]

I cannot listen in this environment; I judged spectrograms (`work/audio/spec_clips*.png`). Of 12 decoded
samples, 9 are clearly **dry speech** (harmonic stacks with moving formants and pauses, no music under
it) and 3 are effects (incl. A25 of table 86, the 5.12 s vehicle-like sweep at the arrival at the Konami
Omni Building). In-game music is PSG (33 tracks in the disassembly), which is why the clips are dry.
RESEARCH.md quotes 1,130 voiced lines for the PS1 port; ~1,180 clips minus effects is the same order.

### 1.5 CD-DA tracks [V for usage/timing, I for content classification]

Emulator log of the un-skipped opening (`work/audio/log_opening.txt`): Konami logo = Track 21 (4 s);
prologue = **Track 17 complete (132.7 s) with no ADPCM and no on-screen text** (pictures of the
Lucifer-Alpha lab etc.), then Track 18 (17.8 s), Track 19 (191 s, cast roll), Track 22 (4 s, "ACT 1").
The first ADPCM voice/effect only plays after that. So the prologue narration is inside Track 17.

Spectrogram classification, one 11 s window per track (`work/audio/spec_cdda_*.png`) — a heuristic:

| Tracks | Length | Looks like |
|---|---|---|
| 01 | 53 s | clean speech (standard "this is a CD-ROM" warning) |
| 03-14, 16, 17 | 33-422 s each, **together 34.3 min** | **speech over music/ambience** = voiced cinematics |
| 19, 23 | 191 s, 300 s | music only (opening / ending themes) |
| 15, 18, 21, 22 | 4-18 s | effects / jingles |
| 20 | 30 s | unclear (music, maybe speech) |

Sync: script cmd `$1B` (`engine.asm` `$4C38`) compares the script's M:S:F (converted with `EX_BINBCD`
`$E0B4`) against the sub-Q position that `CD_SUBQ` (`$E01E`, buffer `$20A0` -> ZP `$A2` track, `$A4-$A6`
M/S/F) returns [D]. **Cutscene pictures are keyed to timecodes inside the CD-DA track.**

## 2. Format proof: decoder, WAV, sample rate

- `work/audio/okidec.py`: standard OKI/MSM5205 (49-step table, index deltas `-1,-1,-1,-1,2,4,6,8`,
  12-bit accumulator starting at `0x800`, **high nibble first**), rate = `32000/(16-code)`.
  `python3 work/audio/okidec.py disc/track02.iso --table 86 38 out.wav` decodes by table entry.
  Decoded examples: `work/audio/clip_t86_A025_lba8201.wav`, `work/audio/clips/*.wav` (12 files; e.g.
  `t86_A038.wav` 8.7 s speech, `t86_A102.wav` 32.3 s streamed speech).
- **Rate = 16 kHz, determined three independent ways [V]:**
  1. the table's rate byte `0x0E` is what the game passes as `_DH` to `AD_PLAY`/`AD_CPLAY`, and the emulator's
     `APCM.ADPCM.SampleFreq` reads 14 while playing -> 32000/(16-14) = 16,000 Hz. All 1,238 playable
     entries use `0x0E`; none uses a lower rate.
  2. timing: clip A25 (40,960 bytes) plays from frame ~4168 to 4474 = 306 frames = 5.11 s; 81,920 samples
     / 16,000 = 5.12 s. The `$6000`-byte SFX slice: 184 frames = 3.07 s vs 3.072 s computed.
  3. waveform: my decode of A25, resampled to 44.1 kHz, cross-correlated against the emulator's captured
     output (with Track 17 music playing on top) over a 1.5 s window: **NCC 0.80** with high-nibble-first
     at 16 kHz, 0.27 with low-nibble-first (`work/audio/verify_xcorr.py`). A wrong rate cannot stay aligned
     over 1.5 s.
- The speech spectrograms show plausible pitch/formant structure at 16 kHz (sanity check only).

## 3. The Sega CD side (web research; no disc here)

- **`PCMLD_01.BIN`, 80.8 MB raw PCM: "all of the sound effects and most of the dialogue"; the rest of the
  dialogue is in the redbook tracks, mixed with music.** Artemio Urbina's converter (GPL, C source):
  https://github.com/ArtemioUrbina/Snatcher-PCM2WAV , https://junkerhq.net/Snatcher/PCM2WAV/ [W]
- Format, read from `spcm2wav_seg.c` [V from source]: **8-bit sign-magnitude** (`b < 0x80 -> 0x80 - b`, else
  `b`: the RF5C164 native format), **mono, 16,000 Hz** (WAV header `0x3E80`), segments terminated by
  **`0xFF`** (the RF5C164 loop/stop marker). 1,258 segments, 44 of them empty -> **1,214 WAVs**. The
  README says the older method wrongly assumed 8 kHz.
- 80.8 MB / 16,000 B/s = ~84-88 min. PCE: 1,212 unique entries, ~95 min (incl. sector padding). The near
  match in count and duration suggests the Sega CD port kept the PCE's clip structure almost 1:1 [I —
  striking, but unproven; the order of segments vs PCE table order is unknown].
- How the Sega CD game indexes the segments (offset table? in `SPxx.BIN`?) is not publicly documented as
  far as I found. The SP??.BIN files are the scenario/text files (Junker HQ dump), not audio.
- Sega CD redbook: a soundtrack rip lists 11 redbook tracks (https://downloads.khinsider.com/game-soundtracks/album/snatcher-scd);
  forum posts say only the major cutscenes are CD-DA, the majority of dialogue lower-quality PCM
  (https://segaxtreme.net/threads/snatcher-segacd-voice-extractor.6051/ , http://www.forums.junkerhq.net/viewtopic.php?f=1&t=559). [W]
- **Ready-made clip packs:** none found for download. There is a YouTube compilation "Snatcher All Sounds &
  Voice Clips (SEGA-CD Version)" (https://www.youtube.com/watch?v=BCrljgWm8fU) — lossy, unsegmented, not a
  source. The practical route is: own/dump the Sega CD disc, copy `PCMLD_01.BIN` off its ISO9660 file
  system, run the segmenting converter (or a 20-line Python port). redump.org was unreachable; a TCRF user
  page on the Sega CD version returned no usable content (the fetch summary described it as
  prompt-injection-style text; ignored).

## 4. Feasibility

### 4.1 ADPCM clips — feasible, the data structures are friendly

- **Slot size is not a constraint.** Position and length of every clip are table fields (3-byte LBA,
  16-bit sector count). A rebuilt clip region plus six rewritten 8-byte tables is all it takes; no code
  patch is needed for longer/shorter lines. [V for the format, I that nothing else caches lengths]
- **64 KB buffer:** a load+play clip (cmd 2) can be at most 31 sectors = 63,488 bytes = **7.94 s** at 16 kHz.
  Longer English lines simply become cmd 3 (`AD_CPLAY`, streamed; the game already does this for 179
  clips up to 32 s). Caveat: while streaming, the drive is busy — if the script loads graphics or
  starts CD-DA during such a line, behaviour changes [unknown, needs testing per case]. Option: lower rate
  code 13 (10.7 kHz, 11.9 s per buffer) for a borderline line; the rate is per entry.
- **Timing:** the script command that follows a voice line polls `AD_STAT`, so text/scene progression follows
  the real clip length [D]. Mouth animation: not examined — whether lip flaps run for a scripted frame
  count or until `AD_STAT` goes idle is **unknown**; with fixed counts, English lines would show
  too-short/too-long lip movement (cosmetic).
- **Space:** Track 02 is 34,120 sectors and ~75 % ADPCM. English lines at the same rate need about the
  same space (Sega CD total is ~10 % *smaller*). If a section grows: use the unreferenced gap data (after
  proving it is unused), or extend Track 02 and rebuild the CUE — CD-DA is addressed by track number via
  the TOC (the logged play ranges equal the TOC track bounds [V]), so shifting later tracks should be
  harmless [I]; the disc has ~14 min of free capacity (59.8 of 74 min used). Keep each section's clips
  near its scene data: the original layout is clearly seek-optimised.
- **Index limit:** one byte per request -> max 255 clips per table; table 98 is already full. Only
  matters if English needs *more* clips than Japanese in a section.
- **Quality:** source 8-bit/16 kHz -> target 4-bit ADPCM/16 kHz: same bandwidth, no resampling. Measured
  with `okienc.py test` on 12 s of clean CD-DA speech (Track 01): 8-bit quantisation alone 33 dB SNR;
  through my simple MSM5205 encoder **17 dB** waveform SNR, the same whether fed 16-bit or 8-bit input.
  So ADPCM is the bottleneck, the Sega CD's 8-bit source is not; the result should sound like the existing
  Japanese clips (same codec, same rate), i.e. clearly grainier than the Sega CD original [I — not
  listened to]. A better encoder (look-ahead / noise shaping, pre-emphasis-free low-pass at ~7 kHz,
  peak normalisation to avoid slope overload) would gain a few dB. End each clip near mid-scale and pad with
  `0x88` like the originals do.
- **Both data tracks:** patch Track 02 for certain. Track 24's tables are identical but its clip data for
  sections 2-3 is misaligned already, so it is apparently not used for audio; mirror the changes anyway
  where the layout matches, until the "which track is read" question (BACKLOG) is closed.

### 4.2 The real work: mapping, not bytes

- There is **no public mapping** PCE clip <-> Sega CD segment. 1,212 vs 1,214 is encouraging, but the Sega CD
  script was rewritten (shorter lines, censored/changed scenes, Act 3 extended, new Gillian/Jamie intro,
  PCE-only gags — RESEARCH.md §4). Expect a large 1:1 core, plus PCE clips without English counterpart
  (keep Japanese? silence? — a policy decision) and English clips with no PCE slot.
- Matching method [proposal]: (a) order — compare table order per section with segment order in
  `PCMLD_01.BIN`; (b) duration profile — sequence-align the two duration lists (English lines differ in
  length, but effects are identical audio and act as anchors: the SFX banks/effects can be matched by
  waveform correlation after decoding); (c) speaker/scene from the script once the script pipeline
  can enumerate `$F6 idx` requests next to the text lines; (d) ears for the rest.
- Names problem solved as a side effect (English audio says "Jordan", "Katrina", 2047).

### 4.3 CD-DA cinematics — expensive

- ~14 tracks / ~34 min have Japanese voice **mixed into** music and effects. There is no clean music stem on
  the PCE disc, and the Sega CD redbook cutscenes have their own (different) music mix and timing.
- Options: (1) leave them Japanese and subtitle them (subtitles need new code anyway, see BACKLOG);
  (2) replace whole tracks by the corresponding Sega CD redbook tracks — then every cmd `$1B` M:S:F
  timecode in those scenes must be re-timed to the English track, the scene content has to match
  (the Sega CD intro differs), and track lengths change (harmless for TOC addressing [I]); (3) rebuild
  mixes from the PCE music (where an instrumental exists, e.g. soundtrack CD) + English voice — a manual
  audio-production job per scene.
- How many Sega CD redbook cutscenes correspond to PCE CD-DA scenes is **unknown** (11 SCD redbook tracks vs
  ~14 voiced PCE tracks already says: not all).

### 4.4 Recommendation

1. Finish the text pipeline first (as planned). While doing so, record every `$F6`/`$0C`/`$EA` audio request
   with its table number and neighbouring text line — that yields the PCE clip <-> line map for free.
2. Get `PCMLD_01.BIN` from an own Sega CD disc; extract the 1,214 segments; build the duration/effect-anchor
   alignment against the 1,212 PCE entries. **Decide go/no-go on the measured match rate**, not before.
3. Prototype on section 1 only (table 86: 119 playable clips, 2,388 sectors): re-encode, rebuild the region,
   rewrite table 86 + boot copy at sector 54, test in the emulator and on hardware (seek times, streamed
   clips, lip flaps).
4. Treat CD-DA cinematics as a separate, later decision; default = keep Japanese audio + subtitles.

### 4.5 Unknowns (ordered by risk)

1. Match rate PCE clips <-> Sega CD segments; policy for unmatched lines.
2. Which script/loader step selects table 86...106, and whether anything else stores clip lengths
   (e.g. lip-flap durations, fixed waits in cutscene-like in-game sequences).
3. Side effects of turning cmd 2 clips into streamed cmd 3 (drive busy) on real hardware.
4. Whether the gap regions and the Track 02 tail are really free; whether Track 24 is ever read for audio.
5. Subjective quality of re-encoded English speech (not listened to here); encoder tuning.
6. CD-DA scene correspondence and `$1B` timecode tables, if cinematics are ever attempted.
7. Legal/distribution: Konami's voice recordings cannot be shipped; a patch would have to build from the
   user's own Sega CD disc (fine for personal use).
