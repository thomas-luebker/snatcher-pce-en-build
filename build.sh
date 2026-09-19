#!/bin/zsh
# Build the English Snatcher image from your own disc(s). See BUILD.md.
set -e
cd "$(dirname "$0")"
SCD_TEXT=${SCD_TEXT:-reference/junkerhq-dumps/scd}   # English script: Junker HQ's public dump, or your own Sega CD files
SCD_FILES=${SCD_FILES:-segacd/files}                 # your Sega CD data-track files (PCMLD/PCMLT) - for the voices
SCD_RIP=${SCD_RIP:-Snatcher (USA)}                   # your Sega CD rip (.bin/.cue) - for the intro narration
VOICES=${VOICES:-1}
export SCD_FILES SCD_RIP
mkdir -p work/audio

print -P "%F{green}==>%f text (source: $SCD_TEXT)"
python3 tools/resolve_refs.py "$SCD_TEXT" work/scenes_resolved | tail -1
python3 tools/snhuff.py build "$SCD_TEXT" translations/coding.json 150 | head -1
python3 tools/scenes.py > work/scenes.log && print "    $(tail -1 work/scenes.log)"

do_voices=0
if [[ $VOICES == 1 && -f "$SCD_FILES/PCMLD_01.BIN" && -f "$SCD_FILES/PCMLT_01.BIN" ]]; then
  do_voices=1
  print -P "%F{green}==>%f voices (source: $SCD_FILES)"
  [[ -f work/audio/clip_align.json ]] || python3 tools/clip_align.py disc/track02.iso "$SCD_FILES/PCMLT_01.BIN" work/audio/clip_align.json | tail -1
elif [[ $VOICES == 1 ]]; then
  print -P "%F{yellow}==>%f no Sega CD data files in $SCD_FILES - keeping the Japanese voices"
  print "    (run ./setup.sh with your Sega CD rip in place, or set SCD_FILES=)"
fi

if (( do_voices )); then
  SCENES=work/scenes_resolved VOICE=1 python3 tools/build_all.py | tail -2
else
  SCENES=work/scenes_resolved python3 tools/build_all.py | tail -1
fi

if (( do_voices )) && ls "$SCD_RIP"/*.cue >/dev/null 2>&1; then
  print -P "%F{green}==>%f intro narration (source: $SCD_RIP)"
  python3 tools/intro_audio.py | tail -1
else
  print -P "%F{yellow}==>%f no Sega CD .cue in '$SCD_RIP' - the intro narration stays Japanese"
fi

python3 tools/binmerge.py "build-en/Snatcher CD-ROMantic (Japan).cue" build-en-single "Snatcher (English)"
print
print -P "%F{green}==>%f done: build-en-single/  (single .bin + .cue, for emulators and flash carts)"
