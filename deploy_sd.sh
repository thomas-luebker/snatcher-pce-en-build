#!/bin/zsh
# Copy the verified image onto the Turbo EverDrive SD card (volume "PCE") and verify the copy.
# Waits up to 30 minutes for the card to be inserted. Refuses an image that has not passed verify_build.
cd "$(dirname "$0")" || exit 2
CARD=/Volumes/PCE
NAME=${1:-Snatcher (English)}
SRC=work/single
[[ -f "$SRC/$NAME.bin" && -f "$SRC/$NAME.cue" ]] || { echo "no '$NAME.bin' / '$NAME.cue' in $SRC -- run ./build.sh"; exit 2; }
# the image must be younger than the last successful verification, or it was built some other way
[[ -f build-en/report.txt && "$SRC/$NAME.bin" -nt build-en/report.txt ]] || { echo "image is older than the last build report, or there is no report: run ./build.sh"; exit 2; }
python3 tools/verify_build.py >/dev/null || { echo "verify_build.py fails on the current build -- not copying"; exit 1; }
DST="$CARD/$NAME"
for i in {1..360}; do [[ -d $CARD ]] && break; sleep 5; done
[[ -d $CARD ]] || { echo "TIMEOUT: no SD card named PCE appeared"; exit 1; }
sleep 3
ls "$CARD/edturbo/bios/"*.pce >/dev/null 2>&1 || echo "WARNING: no System Card in edturbo/bios - CD games will not start"
mkdir -p "$DST" || exit 1
# Keep what the card had: the previous image stays on the card under "... previous" (one generation) and every
# image that goes on the card is kept locally under work/releases/<date-time>/ -- the image a whole play-through
# was finished on is worth more than the newest build (24 Sep).
if [[ -f "$DST/$NAME.bin" ]] && ! cmp -s "$SRC/$NAME.bin" "$DST/$NAME.bin"; then
  PREV="$CARD/$NAME previous"; mkdir -p "$PREV"
  cp -X "$DST/$NAME.bin" "$PREV/$NAME.bin" && cp -X "$DST/$NAME.cue" "$PREV/$NAME.cue" && echo "previous image kept in '$PREV'"
fi
REL="work/releases/$(date +%Y-%m-%d_%H%M)"; mkdir -p "$REL" && cp "$SRC/$NAME.bin" "$SRC/$NAME.cue" "$REL/" && cp build-en/report.txt "$REL/" && echo "kept locally in $REL"
bad=0
for f in "$NAME.bin" "$NAME.cue"; do
  cp -X -L "$SRC/$f" "$DST/$f" || { echo "COPY FAILED: $f"; bad=1; }
done
find "$DST" -name '._*' -delete
sync
for f in "$NAME.bin" "$NAME.cue"; do
  cmp -s "$SRC/$f" "$DST/$f" || { echo "MISMATCH: $f"; bad=1; }
done
(( bad )) && { echo "FAILED - see above"; exit 1; }
echo "COPIED AND VERIFIED: '$DST' ($(date +%H:%M)); saves in edturbo/gamedata are untouched"
