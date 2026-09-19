================================================================================
*                    SNATCHER CD-ROMantic  (PC Engine)                         *
*                       English Translation Patch                              *
*                          v0.1 TEST  (19 Sep 2026)                            *
*                                                                              *
*     Patch tools, script port and PC Engine-only translation -- this project  *
*     English dialogue -- Konami's official Sega CD localisation,              *
*                         dumped by Artemio Urbina / Junker HQ                 *
*     PC Engine disassembly used as reference -- buranko-kun                   *
================================================================================

  THIS IS A TEST RELEASE. The whole game is translated, but only the opening
  has been played through on hardware. Expect rough edges and please report
  them (see "Reporting problems").


What this is
------------

Snatcher CD-ROMantic (Konami, 1992) never left Japan on the PC Engine. The
Sega CD version did, in English, two years later. This patch moves that English
onto the PC Engine disc:

  Text     all 32 scenes, 9,201 messages, plus menus, topic words and
           character names
  Voices   about 1,200 in-game voice clips replaced with the Sega CD English
           recordings
  Intro    the opening narration replaced with the Sega CD track

The PC Engine version has a good deal of content the Sega CD version cut, and
some it reworded. Those lines have no official English, so they were translated
for this patch and are the places most likely to read oddly.

Still Japanese:
  - the "start" option on the title screen (it is a picture built by the game
    at runtime, not text)
  - cutscene audio other than the opening narration

The English voice clips are fitted into the slots the Japanese ones used. Where
an English line is longer, it is re-encoded at a lower sample rate so the whole
line still fits, so some lines sound duller than the originals. Nine of the
1,200 were still too long and are cut short.


Which patch to use
------------------

  full/        English text, English voices, English intro narration   (~74 MB)
  text-only/   English text, the original Japanese voices              (~2 MB)

Both patch the same two data tracks. The full patch additionally replaces the
intro audio track. Pick one, do not apply both.


What you need
-------------

  1. Your own copy of the game, as a Redump-style rip:

       Snatcher CD-ROMantic (Japan) (Track 01).bin  ... through Track 24
       Snatcher CD-ROMantic (Japan).cue

     24 tracks. No game data is included with this patch.

  2. xdelta3 -- the patching tool.

       macOS    brew install xdelta
       Linux    apt install xdelta3   (or your package manager)
       Windows  xdelta3.exe from https://github.com/jmacd/xdelta-gpl/releases


How to patch
------------

Put the .xdelta files next to your .bin files. For the full patch:

  xdelta3 -d -s "Snatcher CD-ROMantic (Japan) (Track 02).bin" Snatcher_Track02.xdelta t02.bin
  xdelta3 -d -s "Snatcher CD-ROMantic (Japan) (Track 24).bin" Snatcher_Track24.xdelta t24.bin
  xdelta3 -d -s "Snatcher CD-ROMantic (Japan) (Track 17).bin" Snatcher_Track17.xdelta t17.bin

For the text-only patch, do the first two only.

Then replace the originals with the patched files (back them up first):

  mv t02.bin "Snatcher CD-ROMantic (Japan) (Track 02).bin"
  mv t24.bin "Snatcher CD-ROMantic (Japan) (Track 24).bin"
  mv t17.bin "Snatcher CD-ROMantic (Japan) (Track 17).bin"

The .cue file does not change. A checksum error from xdelta means your rip is
not the one this was built against.

  IMPORTANT: patch BOTH data tracks. Track 24 is a second copy of the game
  data, and a flash cart may serve the game from either one. Patching only
  track 02 can leave you with a game that is still Japanese on real hardware.


Playing it
----------

  Emulator     Load the .cue file. Mednafen and Beetle PCE both work. You need
               a Super CD-ROM System v3.0 System Card, as for the original game.

  Real console Copy the folder to your flash cart's SD card, one folder per
               game. On a Turbo EverDrive Pro you also need a System Card in
               edturbo/bios/ -- "Super CD-ROM System (Japan) (v3.0).pce" is the
               recommended one. Do not leave macOS "._" files in that folder;
               the cart takes the first file it finds as the System Card.

               Many flash carts want a single .bin rather than 24 separate
               ones. Patch the separate tracks first, then merge.

  Saving       Works as on the original: the game uses the console's backup
               memory.


Reporting problems
------------------

The most useful reports say where it happened, what you were doing, and what
you saw. A photo or screenshot beats a description. Especially worth reporting:

  - a voice line that does not match what is on screen. Most clips were paired
    automatically and only the opening was checked by ear, so this is the most
    likely fault in the patch.
  - the intro narration drifting out of step with the pictures
  - text running off the box or cut off mid-word
  - a line that makes no sense for the situation
  - anything that freezes or crashes
  - Japanese text where English should be

Scenes worth extra attention: the Jordan database, the save and load screens,
and the quiz. Those had the least reliable automatic matching.


Credits and thanks
------------------

  The English dialogue is Konami's official Sega CD localisation. It was dumped
  and published by Artemio Urbina (Junker HQ), without which none of this would
  have been possible.

  The technical groundwork on the PC Engine version -- the disassembly this
  project read to understand the text engine -- is buranko-kun's.

  This project matched the two scripts, translated the PC Engine-only content,
  and wrote the code that lets the game display English.
