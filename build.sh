#!/bin/zsh
# Build the English Snatcher image from your own disc(s), in the only order that works, with the checks
# that keep old faults from coming back. See BUILD.md.
#
#   ./build.sh            -> work/single/Snatcher (English).bin + .cue, verified
#   ./build.sh --emu      -> also a cold boot in the emulator (a minute more)
#   ./deploy_sd.sh        -> copy that image to the EverDrive card and verify the copy
#
#   build_all.py      both data tracks: text, names, menus, keyboard, title, answers, voices, credits. It
#                     also relinks tracks 03-20 to the Japanese originals, so the two audio stages MUST follow
#   intro_audio.py    track 17, the English intro narration          (needs your Sega CD rip)
#   cutscene_dub.py   the 15 dubbed cutscenes                         (needs your Sega CD rip and Demucs)
#   verify_build.py   every regression found on hardware so far, checked on the built tracks
#   binmerge.py       one .bin + .cue for the cart
#
# A stage whose input is missing is skipped, and says so in yellow, in build-en/report.txt and again in
# the verify step: a build that silently produces a worse image than it could is the one fault we never
# want again.
#
#   VOICES=0          text only: no voices, no intro, no cutscenes
#   SCD_FILES=dir     your Sega CD data-track files (PCMLD_01.BIN, PCMLT_01.BIN)   default segacd/files
#   SCD_RIP=dir       your Sega CD rip (.cue + tracks)                              default "Snatcher (USA)"
#   VENV=dir          a Python venv with demucs and soundfile, for the cutscenes   default work/venv
set -e -o pipefail
cd "$(dirname "$0")"
N="Snatcher CD-ROMantic (Japan)"
SCD_FILES=${SCD_FILES:-segacd/files}
SCD_RIP=${SCD_RIP:-Snatcher (USA)}
VENV=${VENV:-work/venv}
VOICES=${VOICES:-1}
export SCD_FILES SCD_RIP
mkdir -p build-en work/single

say()  { print -P "%F{green}==>%f $*"; }
warn() { print -P "%F{yellow}==> $*%f"; }

[[ -f "disc/$N.cue" ]] || { print "no 'disc/$N.cue' -- put your own rip in disc/ (see ./setup.sh)"; exit 2; }

# the data tracks as plain ISOs, and the scene descriptions read from them: both come from your disc
for t in 02 24; do
  [[ -f disc/track$t.iso ]] || { say "disc/track$t.iso"; python3 tools/cdsector.py bin2iso "disc/$N (Track $t).bin" disc/track$t.iso; }
done
if [[ ! -d work/scenes ]] || [[ disc/track02.iso -nt work/scenes ]]; then
  say "scene descriptions (tools/scenes.py)"
  python3 tools/scenes.py > work/scenes.log && print "    $(tail -1 work/scenes.log)"
fi

voice=0; intro=0; dub=0
if [[ $VOICES != 1 ]]; then
  warn "VOICES=$VOICES: text only -- voices, intro and cutscenes stay Japanese"
else
  if [[ -f "$SCD_FILES/PCMLD_01.BIN" ]]; then voice=1
  else warn "no $SCD_FILES/PCMLD_01.BIN -- the in-game voices stay Japanese (run ./setup.sh with your Sega CD rip in place)"; fi
  if ls "$SCD_RIP"/*.cue >/dev/null 2>&1; then
    intro=1
    if [[ -x $VENV/bin/python ]] && $VENV/bin/python -c "import demucs, soundfile, numpy" 2>/dev/null; then dub=1
    else warn "no Demucs in $VENV -- the cutscenes stay Japanese (python3 -m venv $VENV && $VENV/bin/pip install demucs soundfile)"; fi
  else
    warn "no .cue in '$SCD_RIP' -- the intro and the cutscenes stay Japanese (set SCD_RIP=)"
  fi
fi

say "data tracks"
if (( voice )); then python3 tools/build_all.py | tee build-en/report.txt | tail -4
else VOICE=0 python3 tools/build_all.py | tee build-en/report.txt | tail -4; fi

if (( intro )); then
  say "intro narration"
  python3 tools/intro_audio.py | tail -1
else
  print "intro: SKIPPED -- no Sega CD rip, track 17 is the Japanese original" >> build-en/report.txt
fi

if (( dub )); then
  say "cutscenes (Demucs splits each track the first time: slow once, cached in work/cutscene)"
  $VENV/bin/python tools/cutscene_dub.py build | grep -c "wrote" | sed 's/^/    tracks written: /'
else
  print "cutscenes: SKIPPED -- no Sega CD rip or no Demucs, the cutscenes are the Japanese originals" >> build-en/report.txt
fi

say "verify"
python3 tools/verify_build.py "$@"

say "merge"
python3 tools/binmerge.py "build-en/$N.cue" work/single "Snatcher (English)" | tail -1
say "done: work/single/Snatcher (English).bin  (for emulators and flash carts; ./deploy_sd.sh puts it on an EverDrive card)"
