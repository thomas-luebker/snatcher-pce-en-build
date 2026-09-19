#!/usr/bin/env python3
"""Build an English Snatcher image: code patch + names + one fully repacked scene (so far: slot 0x9F000).

  build_scene.py            -> build-en/ (multi-bin, for the emulator)
  VOICE=30 build_scene.py   -> also swaps in the first Sega CD voice clips (experiment, see poc_scene1.py)

Scene repack: the menu words stay where they are when the English fits (else they move), then the whole
text area is rewritten message by message in the original order and every say command
(`12 <speaker> 00 <lo> <hi>`) is re-pointed. English comes from the alignment with the Sega CD script,
hand translations fill the PC Engine-only lines. A "message" that starts inside another one is a chance
hit of the byte pattern and is left alone.
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import cdsector as C  # noqa: E402
import dump_script as D  # noqa: E402
import sncells  # noqa: E402
import snhack  # noqa: E402
import snhuff  # noqa: E402
import snnames  # noqa: E402
import snpack  # noqa: E402
import snwords  # noqa: E402

N = "Snatcher CD-ROMantic (Japan)"
SCENES = {0x9F000: {"text_start": 0x250A, "loaded": 0x7000, "words": snwords.SCENE1,
                    "manual": "translations/scene_9f000.json"}}
SAY = re.compile(rb"\x12[\x00-\x4a]\x00", re.S)


def clean(en):
    en = re.sub(r"</?cc[^>]*>", "", en).replace("<nl>", " ")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", en)).strip()


def true_messages(iso, base, text_start, loaded):
    """All say commands of the slot whose target decodes; chance hits inside another message dropped."""
    found = {}
    for m in SAY.finditer(iso, base, base + text_start):
        i = m.start()
        ptr = iso[i + 3] | (iso[i + 4] << 8)
        if text_start <= ptr < loaded:
            pairs, end = snpack.decode(iso, base + ptr, 0, limit=500)
            if end is not None:
                found.setdefault(ptr, {"ptr": ptr, "end": (end >> 1) - base, "cmds": [], "jp": D.render(pairs)})
                found[ptr]["cmds"].append(i - base)
    kept, pos = [], text_start
    for ptr in sorted(found):
        if ptr < pos:
            continue
        kept.append(found[ptr])
        pos = found[ptr]["end"]
    return kept


def build_scene(iso, base, cfg, coding, report):
    pairs = {p["ptr"]: clean(p["en"]) for p in json.load(open("work/text_align.json")) if p["bank"] == base}
    manual = {int(k, 16): v for k, v in json.load(open(cfg["manual"]))["entries"].items()}
    msgs = true_messages(bytes(iso), base, cfg["text_start"], cfg["loaded"])
    covered = sum(m["end"] - m["ptr"] for m in msgs)
    report.append(f"slot {base:#x}: {len(msgs)} messages cover {covered} of "
                  f"{msgs[-1]['end'] - cfg['text_start']} text bytes")
    cursor, a, b, miss = snwords.apply(iso, base, cfg["text_start"], cfg["words"], cfg["text_start"], cfg["loaded"])
    report.append(f"  menu words: {a} in place, {b} moved, {miss} untouched")
    blob, new_ptr, untranslated = bytearray(), {}, 0
    for m in msgs:
        en = manual.get(m["ptr"]) or pairs.get(m["ptr"])
        if en is None:
            untranslated += 1
            en = "(untranslated)"
        new_ptr[m["ptr"]] = cursor + len(blob)
        blob += coding.encode(en)
    end = cursor + len(blob)
    report.append(f"  text: Japanese {msgs[-1]['end'] - cfg['text_start']} bytes -> English {end - cfg['text_start']} bytes "
                  f"(limit {cfg['loaded'] - cfg['text_start']}); {untranslated} untranslated")
    if end > cfg["loaded"]:
        raise SystemExit(f"scene {base:#x} does not fit: needs {end - cfg['loaded']} more bytes")
    iso[base + cursor:base + cfg["loaded"]] = bytes(blob).ljust(cfg["loaded"] - cursor, b"\xff")
    for m in msgs:
        for c in m["cmds"]:
            iso[base + c + 3:base + c + 5] = new_ptr[m["ptr"]].to_bytes(2, "little")


def main():
    coding = snhuff.Coding()
    isos = {2: open("disc/track02.iso", "rb").read(), 24: open("disc/track24.iso", "rb").read()}
    report = []
    for t in isos:
        data, sizes = snhack.apply(isos[t], coding)
        data, n = snnames.apply(data)
        isos[t] = bytearray(data)
    report.append(f"code patch: {sizes}; names {n} bytes")
    for base, cfg in SCENES.items():
        assert isos[2][base:base + cfg["loaded"]] == isos[24][base:base + cfg["loaded"]], "slot differs between tracks"
        r = []
        for t in isos:
            r = []
            build_scene(isos[t], base, cfg, coding, r)
        report += r
    if os.environ.get("VOICE"):
        import poc_scene1
        poc_scene1.voices(isos, int(os.environ["VOICE"]))
    out = "build-en"
    os.makedirs(out, exist_ok=True)
    for f in os.listdir("disc"):
        if f.endswith(".bin") and "(Track 02)" not in f and "(Track 24)" not in f:
            if not os.path.lexists(f"{out}/{f}"):
                os.symlink(os.path.abspath(f"disc/{f}"), f"{out}/{f}")
    shutil.copy(f"disc/{N}.cue", f"{out}/{N}.cue")
    for t, iso in isos.items():
        raw = open(f"disc/{N} (Track {t:02d}).bin", "rb").read()
        open(f"{out}/{N} (Track {t:02d}).bin", "wb").write(C.iso2bin(bytes(iso), raw))
    print("\n".join(report))


if __name__ == "__main__":
    main()
