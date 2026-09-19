#!/bin/zsh
# Build the English Snatcher image from your own disc(s). See BUILD.md.
set -e
cd "$(dirname "$0")"
SCD_TEXT=${SCD_TEXT:-reference/junkerhq-dumps/scd}     # Junker HQ's public script dump (setup.sh fetches it)
SCD_DISC=${SCD_DISC:-segacd/files}                     # your own Sega CD files - only needed for voices/intro
VOICES=${VOICES:-1}

print -P "%F{green}==>%f English script source: $SCD_TEXT"
python3 tools/resolve_refs.py "$SCD_TEXT" work/scenes_resolved | tail -1
python3 tools/snhuff.py build "$SCD_TEXT" translations/coding.json 150 | head -1
python3 tools/scenes.py > work/scenes.log && print "    scene data: $(tail -1 work/scenes.log)"

if [[ $VOICES == 1 && -d $SCD_DISC ]]; then
  print -P "%F{green}==>%f building with English voices and intro (from $SCD_DISC)"
  SCENES=work/scenes_resolved VOICE=1 python3 tools/build_all.py | tail -2
  python3 tools/intro_audio.py | tail -1
else
  print -P "%F{green}==>%f text only (no Sega CD disc, or VOICES=0) - the Japanese voices are kept"
  SCENES=work/scenes_resolved python3 tools/build_all.py | tail -1
fi

python3 tools/binmerge.py "build-en/Snatcher CD-ROMantic (Japan).cue" build-en-single "Snatcher (English)"
print
print -P "%F{green}==>%f done: build-en-single/  (single .bin + .cue, for emulators and flash carts)"
print "    build-en/ holds the separate tracks; its audio tracks are symlinks into your rip."
