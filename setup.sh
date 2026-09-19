#!/bin/zsh
# Fetch everything the build needs that is public. Run from the repository root.
#
# What it CANNOT fetch, because it is the games themselves -- supply these yourself:
#
#   disc/            your own Redump rip of "Snatcher CD-ROMantic (Japan)" (24 tracks + .cue)
#   Snatcher (USA)/  your own Redump rip of the Sega CD "Snatcher (USA)" -- only needed for the
#                    English voice clips and the intro narration; the text build works without it
#   ~/.mednafen/firmware/syscard3.pce   a Super CD-ROM System v3.0 System Card, for the test harness
#
# Everything else is downloaded below.
set -e
cd "$(dirname "$0")"
mkdir -p reference emu disc segacd work

say() { print -P "%F{green}==>%f $*"; }

# --- numpy, for the cutscene audio matcher ----------------------------------------------------
# Only tools/match_cutscenes.py needs it; the build itself is pure Python, so a failure here is
# not fatal.
if ! python3 -c "import numpy" 2>/dev/null; then
  say "numpy (tools/match_cutscenes.py only)"
  python3 -m pip install --quiet numpy 2>/dev/null || print "  could not install numpy - the build still works without it"
fi

# --- the Sega CD English script dump (Artemio Urbina / Junker HQ) -----------------------------
if [[ ! -d reference/junkerhq-dumps/scd ]]; then
  say "Sega CD English script dump (junkerhq.net)"
  mkdir -p reference/junkerhq-dumps/scd
  curl -fsSL -o work/scd.zip https://junkerhq.net/files/SnatcherSCD_c.zip
  unzip -qo work/scd.zip -d reference/junkerhq-dumps/scd
  rm -f work/scd.zip
fi

# --- Japanese script dumps of the other versions (used for cross-checking) --------------------
for name url in \
  psx https://junkerhq.net/files/SnatcherPSX.zip \
  sat https://junkerhq.net/files/SnatcherSat.zip
do
  if [[ ! -d reference/junkerhq-dumps/$name ]]; then
    say "Japanese script dump: $name"
    mkdir -p reference/junkerhq-dumps/$name
    curl -fsSL -o work/d.zip $url && unzip -qo work/d.zip -d reference/junkerhq-dumps/$name && rm -f work/d.zip
  fi
done

# --- the PC Engine disassembly this project reads (buranko-kun) -------------------------------
if [[ ! -d reference/snatcher-disasm ]]; then
  say "PC Engine disassembly (github.com/buranko-kun/snatcher)"
  git clone --depth 1 -q https://github.com/buranko-kun/snatcher reference/snatcher-disasm
fi

# --- emulator core for the headless test harness ----------------------------------------------
if [[ ! -f emu/mednafen_pce_libretro.dylib ]]; then
  say "libretro PC Engine core (nightly build)"
  case "$(uname -sm)" in
    "Darwin arm64") u=https://buildbot.libretro.com/nightly/apple/osx/arm64/latest/mednafen_pce_libretro.dylib.zip ;;
    "Darwin x86_64") u=https://buildbot.libretro.com/nightly/apple/osx/x86_64/latest/mednafen_pce_libretro.dylib.zip ;;
    Linux*) u=https://buildbot.libretro.com/nightly/linux/x86_64/latest/mednafen_pce_libretro.so.zip ;;
    *) print "  unknown platform - fetch a mednafen_pce libretro core into emu/ yourself"; u="" ;;
  esac
  if [[ -n $u ]]; then curl -fsSL -o work/core.zip $u && unzip -qo work/core.zip -d emu && rm -f work/core.zip; fi
fi

# --- extract the Sega CD data track, if the user has that rip ---------------------------------
SCD_RIP=${SCD_RIP:-Snatcher (USA)}
if [[ ! -f segacd/files/PCMLD_01.BIN ]] && ls "$SCD_RIP"/*"(Track 01).bin" >/dev/null 2>&1; then
  say "extracting the Sega CD data track (for the English voices)"
  python3 - "$SCD_RIP" <<'PY'
import sys, glob, os
sys.path.insert(0, "tools"); import cdsector as C
raw = sorted(glob.glob(os.path.join(sys.argv[1], "*(Track 01).bin")))[0]
os.makedirs("segacd", exist_ok=True)
open("segacd/track01.iso", "wb").write(C.bin2iso(open(raw, "rb").read(), pregap=0))
print("  wrote segacd/track01.iso")
PY
  if command -v 7zz >/dev/null; then 7zz x -y -osegacd/files segacd/track01.iso >/dev/null
  elif command -v 7z  >/dev/null; then 7z  x -y -osegacd/files segacd/track01.iso >/dev/null
  else print "  install p7zip, then: 7zz x -y -osegacd/files segacd/track01.iso"; fi
fi

print
say "public prerequisites are in place"
print "Still needed from you:"
[[ -f "disc/Snatcher CD-ROMantic (Japan).cue" ]] && print "  disc/            ok" || print "  disc/            MISSING - your own Snatcher (Japan) rip"
[[ -f segacd/files/PCMLD_01.BIN ]] && print "  Sega CD files    ok" || print "  Sega CD files    missing - only needed for English voices/intro"
[[ -f ~/.mednafen/firmware/syscard3.pce ]] && print "  System Card      ok" || print "  System Card      missing - ~/.mednafen/firmware/syscard3.pce (test harness only)"
print
print "Then: see BUILD.md"
