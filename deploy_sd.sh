#!/bin/zsh
# Copy the built disc image onto the Turbo EverDrive SD card (volume "PCE") and verify it.
# Waits up to 30 minutes for the card to be inserted.
cd "$(dirname "$0")/build-en-single" || exit 2
CARD=/Volumes/PCE
DST="$CARD/Snatcher (English WIP)"
for i in {1..360}; do [[ -d $CARD ]] && break; sleep 5; done
[[ -d $CARD ]] || { echo "TIMEOUT: no SD card named PCE appeared"; exit 1; }
sleep 3
ls "$CARD/edturbo/bios/"*.pce >/dev/null 2>&1 || echo "WARNING: no System Card in edturbo/bios - CD games will not start"
rm -rf "$DST"; mkdir "$DST" || exit 1
bad=0
for f in *.bin *.cue; do
  cp -X -L "$f" "$DST/$f" || { echo "COPY FAILED: $f"; bad=1; }
done
find "$DST" -name '._*' -delete
sync
for f in *.bin *.cue; do
  [[ "$(md5 -q "$f")" == "$(md5 -q "$DST/$f")" ]] || { echo "MISMATCH: $f"; bad=1; }
done
n=$(ls "$DST" | wc -l | tr -d ' ')
(( bad )) && { echo "FAILED - see above"; exit 1; }
echo "OK: $n files in '$DST', all verified, $(du -sh "$DST" | cut -f1)"
