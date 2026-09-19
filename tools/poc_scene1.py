#!/usr/bin/env python3
"""Proof of concept: English for the first lines of the first scene, with no code changes.

  poc_scene1.py [columns]

English is written in fullwidth letters through the game's own text format (tools/snpack.py) into
the ~1.9 KB of free space at the end of the first scene (slot 0x9F000, loaded part ends at +0x6874),
and the matching say commands are re-pointed. The slot is identical in both data tracks, so both
are patched. Output: build-poc/ (multi-bin) for the emulator.
"""
import json
import os
import re
import shutil
import sys
import textwrap

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import cdsector as C  # noqa: E402
import snpack  # noqa: E402
import sncells  # noqa: E402
import snhack  # noqa: E402
import snnames  # noqa: E402
import snwords  # noqa: E402

BANK, FREE_LO, FREE_HI = 0x9F000, 0x6878, 0x6FF8
N = "Snatcher CD-ROMantic (Japan)"


def clean(en):
    en = re.sub(r"</?cc[^>]*>", "", en).replace("<nl>", " ")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", en)).strip()


def voices(isos, count):
    """EXPERIMENT: put the Sega CD English candidates (tools/clip_align.py: order + duration, not verified by
    ear) into the slots of the first `count` clips of PCE table 86. Same slot size: a longer English take is
    cut with a short fade, a shorter one is padded with ADPCM silence ($88)."""
    sys.path.insert(0, "tools")
    import okienc
    from voice_test import scd_samples
    d = json.load(open("work/audio/clip_align.json"))
    partner = {i: j for i, j in d["pairs"] if i is not None and j is not None}
    pcm = open("segacd/files/PCMLD_01.BIN", "rb").read()
    original = bytes(isos[2])
    idx = [i for i, c in enumerate(d["pce"]) if c["table"] == 86][:count]
    done = both = 0
    for i in idx:
        if i not in partner:
            continue
        c = d["pce"][i]
        size, off = c["sectors"] * 2048, c["lba"] * 2048
        smp = scd_samples(pcm, d["scd"][partner[i]])[:size * 2]
        fade = min(800, len(smp))
        if len(smp) == size * 2:                                   # truncated: fade the last 50 ms
            smp[-fade:] = [int(v * (fade - k) / fade) for k, v in enumerate(smp[-fade:])]
        data = okienc.encode(smp)[:size].ljust(size, b"\x88")
        old = original[off:off + size]
        isos[2][off:off + size] = data
        if bytes(isos[24][off:off + size]) == old:                 # same clip at the same place in Track 24
            isos[24][off:off + size] = data
            both += 1
        done += 1
    print(f"voice experiment: {done} clips of table 86 replaced in Track 02, {both} of them also in Track 24")


def main():
    cols = int(sys.argv[1]) if len(sys.argv) > 1 else 18     # measured: 18 fullwidth characters x 3 lines per page
    pairs = [p for p in json.load(open("work/text_align.json")) if p["bank"] == BANK]
    pairs.sort(key=lambda p: p["ptr"])
    says = [r for r in json.load(open("work/script_t02.json")) if r["bank"] == BANK]
    isos = {2: bytearray(open("disc/track02.iso", "rb").read()), 24: bytearray(open("disc/track24.iso", "rb").read())}
    assert isos[2][BANK:BANK + 0x7000] == isos[24][BANK:BANK + 0x7000], "slot differs between the tracks"
    assert set(isos[2][BANK + FREE_LO:BANK + FREE_HI]) <= {0x00, 0xFF}, "free area is not free"
    cursor, done = FREE_LO, 0
    if not os.environ.get("WIDE"):
        for t in isos:                                  # menu words first: the ones that do not fit in place take slack
            c, a, b, c_missing = snwords.apply(isos[t], BANK, 0x250A, snwords.SCENE1, FREE_LO, FREE_HI)
        print(f"menu words: {a} in place, {b} moved ({c - FREE_LO} bytes of slack), {c_missing} untouched")
        cursor = c
    for p in pairs:
        if os.environ.get("WIDE"):                      # first POC: fullwidth letters, no code change
            lines = textwrap.wrap(clean(p["en"]), cols)
            text = "".join(l + ("" if len(l) == cols or i == len(lines) - 1 else "\n") for i, l in enumerate(lines))
            data = snpack.encode_english(text)
        else:                                           # letter-pair cells, needs the renderer hook
            data = sncells.encode(clean(p["en"]))
        if cursor + len(data) > FREE_HI:
            break
        cmds = [r["cmd"] for r in says if r["ptr"] == p["ptr"]]
        for iso in isos.values():
            iso[BANK + cursor:BANK + cursor + len(data)] = data
            for c in cmds:
                assert iso[BANK + c] == 0x12
                iso[BANK + c + 3:BANK + c + 5] = cursor.to_bytes(2, "little")
        cursor += len(data)
        done += 1
    if not os.environ.get("WIDE"):
        for t in isos:
            isos[t] = bytearray(snnames.apply(snhack.apply(bytes(isos[t]))[0])[0])
    if os.environ.get("VOICE"):
        voices(isos, int(os.environ["VOICE"]))
    out = "build-poc"
    os.makedirs(out, exist_ok=True)
    for f in os.listdir("disc"):
        if f.endswith(".bin") and "(Track 02)" not in f and "(Track 24)" not in f:
            dst = f"{out}/{f}"
            if not os.path.lexists(dst):
                os.symlink(os.path.abspath(f"disc/{f}"), dst)
    shutil.copy(f"disc/{N}.cue", f"{out}/{N}.cue")
    for t, iso in isos.items():
        raw = open(f"disc/{N} (Track {t:02d}).bin", "rb").read()
        open(f"{out}/{N} (Track {t:02d}).bin", "wb").write(C.iso2bin(bytes(iso), raw))
    print(f"{done} messages in English ({cursor - FREE_LO} bytes of {FREE_HI - FREE_LO} used), {cols} columns; "
          f"last: {clean(pairs[done - 1]['en'])[:50]!r}")


if __name__ == "__main__":
    main()
