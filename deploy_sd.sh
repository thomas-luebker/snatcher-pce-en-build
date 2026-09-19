#!/bin/zsh
# Copy the built disc image onto the Turbo EverDrive SD card (volume "PCE") and verify it.
# Waits up to 30 minutes for the card to be inserted.
cd "$(dirname "$0")/build-en-single" || exit 2
CARD=/Volumes/PCE
# Name the image to copy rather than globbing. build-en-single/ can hold more than one build -- an
# older one kept as a fallback while a new one is tested -- and copying them all into one folder
# leaves the cart to guess which .cue to boot.
NAME=${1:-Snatcher (English)}
[[ -f "$NAME.bin" && -f "$NAME.cue" ]] || { echo "no '$NAME.bin' / '$NAME.cue' in build-en-single"; exit 2; }
DST="$CARD/$NAME"
for i in {1..360}; do [[ -d $CARD ]] && break; sleep 5; done
[[ -d $CARD ]] || { echo "TIMEOUT: no SD card named PCE appeared"; exit 1; }
sleep 3
ls "$CARD/edturbo/bios/"*.pce >/dev/null 2>&1 || echo "WARNING: no System Card in edturbo/bios - CD games will not start"
rm -rf "$DST"; mkdir "$DST" || exit 1
bad=0
for f in "$NAME.bin" "$NAME.cue"; do
  cp -X -L "$f" "$DST/$f" || { echo "COPY FAILED: $f"; bad=1; }
done
find "$DST" -name '._*' -delete
sync
for f in "$NAME.bin" "$NAME.cue"; do
  [[ "$(md5 -q "$f")" == "$(md5 -q "$DST/$f")" ]] || { echo "MISMATCH: $f"; bad=1; }
done
n=$(ls "$DST" | wc -l | tr -d ' ')
(( bad )) && { echo "FAILED - see above"; exit 1; }
echo "OK: $n files in '$DST', all verified, $(du -sh "$DST" | cut -f1)"
