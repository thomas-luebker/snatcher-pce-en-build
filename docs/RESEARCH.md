# Research: Snatcher CD-ROMantic (PCE) English translation — state of the world, 2026-09-18

Web research by a sub-agent. romhacking.net (Cloudflare) and the live Junker HQ forum (403) could not be
fetched; forum content comes from Wayback copies. Claims from the public disassembly are one
unreviewed author's and need checking in an emulator.

## 1. Existing PCE efforts

- **No PCE patch exists.** Time Extension (Sept 2026) says PC Engine and Saturn remain untranslated:
  https://www.timeextension.com/news/2026/09/konamis-oft-maligned-playstation-port-of-snatcher-is-finally-in-english-for-what-its-worth
  CDRomance lists only the Japanese image: https://cdromance.org/turbografx-cd/snatcher-cd-romantic-japan/
  PCEngine-FX threads (2015, 2017): https://www.pcengine-fx.com/forums/index.php?topic=20111.0 , https://www.pcengine-fx.com/forums/index.php?topic=22273.0
- **Junker HQ project (announced 2007 by Marc Laidlaw), abandoned.** Same plan as ours: Sega CD English
  into the PCE version, deleted scenes translated fresh, no subtitles for voiced scenes. Never found a
  hacker. Thread (via Wayback): http://forums.junkerhq.net/viewtopic.php?f=1&t=1389 ; recruiting call on
  Ys Utopia with NightWolve, Tomaitheous, Dave Shadoff: https://www.ysutopia.net/forums/index.php?topic=305.0
- **Active groundwork: https://github.com/buranko-kun/snatcher** (created 2026-05-25, last push 2026-06-12).
  Byte-identical pceas reassembly of IPL, engine bank, scene-5 bank, dialogue bank, music engine; commits
  labelled "translate:" add an ASCII font shim and a dormant English redirect hook. No script, patch or
  release. AI-assisted; referenced `../reference/` docs and `../tools/` are not in the public repo.
- **PS1 patch by pepa (v0.9.1, 2026-09-15)**, closest precedent: https://github.com/pepasjc/snatcher-translated
  — 12,004 strings in 39 scene banks, subtitles for 1,121 of 1,130 voiced lines, redrawn graphics, xdelta
  against the redump BIN. Fresh AI-assisted translation; no script or tools published.

## 2. Technical documentation of the PCE data

- Artemio Urbina, 2001: "Part of it is in SJIS and part table coded", "J == 69 82"
  (https://junkerhq.net/news2001.html). Inference: `69 82` is fullwidth J (SJIS `82 69`) byte-swapped.
  A PCE dump was never published (https://junkerhq.net/Dumps/index.html).
- buranko-kun disassembly (`home/dialogue.asm`, `REASSEMBLY.md`), unverified:
  - Glyphs via System Card `EX_GETFNT` ($E060); renderer at $6473/$647D draws 32-byte tiles into $3B80;
    override table at $6A07 with 23 custom glyphs `[sjis_lo, sjis_hi, ptr_lo, ptr_hi]`; copy routine $69FC.
  - Print loop $66D4; control codes: $FF end, $FD newline, $FE xx column, $FC xx delay, $FB a b cursor,
    $FA a b window, $F9 xx style/colour, $F8 a b anchor, $20 space, $00-$14 small tile (2 bytes),
    $15-$F7 lead byte of an SJIS pair. A style bit selects 16 px or 12 px advance.
  - Script is **nibble-packed**: `decode_next_pair` at $7272 pulls 12 bits through a nibble fetcher at
    $5341 and rebuilds an SJIS pair. 74-entry speaker name table at $6D47.
  - Boot sector checks a `\0\0SNATCHER` ID at $3296.
  - Its English idea: fullwidth Latin mapped to ASCII, drawn by Dave Shadoff's System Card font patch
    (https://github.com/dshadoff/SYSCARD_Translatefont — players would need a patched System Card), plus a
    redirect via sentinel byte $01 into 1,101 bytes of padding at $5BB3-$5FFF.
  - Not documented: adventure-script opcodes, where text pointers live, how banks map to disc sectors.

## 3. Script sources

- **Official Sega CD English dump** (Artemio, 2001): 39 files sp00-sp38, ~10,700 offset-tagged strings.
  https://junkerhq.net/files/SnatcherSCD_c.zip (with control codes), https://junkerhq.net/files/SnatcherSCD_nc.zip ,
  HTML with scene names https://junkerhq.net/Dumps/SCDSnatcher/menu.html . US and EU text identical.
  Raw SP files: https://github.com/ox-carnage/Snatcher-Sega-CD ; Spanish re-inserter documenting the format:
  https://github.com/girianshido/Sega-CD-Snatcher-Language-Patcher
- Voiced lines are **not** in that dump; partial transcripts (all of Act 3) are in the Junker HQ thread.
- There is **no Japanese Sega CD script** (the Sega CD version was not released in Japan).
- **Japanese dumps exist for every version except PCE** (plain SJIS lines, scene order, no offsets):
  PSX https://junkerhq.net/files/SnatcherPSX.zip (15,044 lines), Saturn https://junkerhq.net/files/SnatcherSat.zip
  (19,955), MSX2 https://junkerhq.net/files/SnatcherMSX.zip , PC-88 https://junkerhq.net/files/SnatcherPC88Text.zip
- No public side-by-side JP/EN data. **Bridge idea (untested):** PCE Japanese -> PSX Japanese -> Sega CD
  English; PSX/Saturn are back-ports of the Sega CD scenario and share its 39-scene division.
- Local copies: `reference/junkerhq-dumps/`.

## 4. PCE vs Sega CD differences that matter for text

- Act 3 exists in both; Sega CD extends it and adds a longer Gillian/Jamie intro (https://www.hardcoregaming101.net/snatcher/).
- PCE text is "often longer, more slapstick"; PCE-only lines (Aristotle pun, Mika chains, videotape scene)
  have no Sega CD English (https://www.movie-censorship.com/report.php?ID=958309 , https://junkerhq.net/Snatcher/PCE/info.html).
- The Gibson candy thread was added for the 32-bit versions: in PSX/Saturn dumps, not on PCE.
- Names/dates: Gaudi -> Jordan, Joy Division -> Plato's Cavern, Altamira -> Alton Plaza, Catherine (14) ->
  Katrina (18), Randam -> Random, Madnar -> Modnar, 2042 -> 2047. With Japanese voices you hear "Gaudi"
  while reading "Jordan" — pepa kept the Japanese names for that reason.

## 5. Data tracks

- Redump (http://redump.org/disc/35095/): 24 tracks; Track 2 data 34,345 sectors, Track 24 data 34,198
  sectors, different hashes — not a bit-identical copy. The disassembly's boot code seeks track $02 and
  then $24; its `t24_bank_*.bin` files suggest script banks were pulled from Track 24.

## Assessment

Write the 12-bit decoder (disassembly as a map, every claim checked in the emulator), dump the PCE
Japanese, align PCE-JP -> PSX-JP -> SCD-EN, translate PCE-only lines fresh. Carry an own 8-pixel font
through the glyph-override path so players do not need a patched System Card. Main unknowns: space and
pointers (English will not fit at 12 bits/char), which data track is read, where plain-SJIS menu text
lives, accuracy of the disassembly, share of PCE-only lines, voiced scenes, graphics.
