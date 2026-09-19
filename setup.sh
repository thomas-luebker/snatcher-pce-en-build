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

print
say "public prerequisites are in place"
print "Still needed from you:"
[[ -f "disc/Snatcher CD-ROMantic (Japan).cue" ]] && print "  disc/            ok" || print "  disc/            MISSING - your own Snatcher (Japan) rip"
[[ -d "Snatcher (USA)" ]] && print "  Snatcher (USA)/  ok" || print "  Snatcher (USA)/  missing - only needed for English voices/intro"
[[ -f ~/.mednafen/firmware/syscard3.pce ]] && print "  System Card      ok" || print "  System Card      missing - ~/.mednafen/firmware/syscard3.pce (test harness only)"
print
print "Then: see BUILD.md"
