#!/usr/bin/env python3
"""The ending staff roll in English (translations/credits.tsv).

  credits.py            -> every line of the ending roll, with its translation or "(none)"

The ending roll is data in the image loaded from LBA 0x82 (bank $85): 45 headings, then 68 names, each a
line of 14 full-width cells (28 bytes; a few are 22-30) padded with full-width spaces, separated by `FF`
and the colour/spacing codes `FE 01`, `FE 02`, `F9 80/82`. The lines are plain SJIS drawn by the dialogue renderer -- so a kanji whose lead byte is in
the ranges our letter-pair cells took over ($88-$9F, $E0-$EF) came out as letter salad on the console
(24 Sep, the end of the game), while the kana headings drew fine.

Each translated line is written as letter-pair cells, centred in the same number of bytes, so the roll's
timing and layout do not change; 28 letters is the most a line takes. Every copy on both tracks is
replaced by content (the cart serves track 24). Lines with no translation are left as they are.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sncells  # noqa: E402

TSV = "translations/credits.tsv"
ROLLS = ((130 * 2048, 133 * 2048),)                                # the ending roll's image (LBA 0x82, 3 sectors)
IMAGE = (130 * 2048, 133 * 2048)
# The opening roll (sector 170, drawn over the intro) is NOT touched: the cutscene engine draws it with its own
# font, which renders kanji and knows nothing of our cells -- translating it put garbage tiles across the intro
# on hardware (24 Sep). Only the ending roll goes through the dialogue renderer and the glyph hook.
# The caption under the Junker HQ tower at the end of the intro (sector 127, in the block the intro loads through
# the scene loader) is plain SJIS drawn by the dialogue renderer, and 本 ($96) is one of our cell leads: with our
# block out of memory in the intro that jumped into nothing and the game hung (hardware, 26 Sep). Full-width Latin
# ($82) goes through the game's own path, so "HQ" needs neither hook nor block. Same 40 bytes.
SJ = lambda t: t.encode("shift_jis")
CAPTION_JP = SJ("コナミオムニビル　　") + b"\xfb\x06\x03" + SJ("ＪＵＮＫＥＲ本部") + b"\xff"
CAPTION_EN = SJ("コナミオムニビル　") + b"\xfb\x06\x03" + SJ("ＪＵＮＫＥＲ　ＨＱ") + b"\xff"
LINE = re.compile(rb"((?:[\x81-\x9f\xe0-\xef][\x40-\xfc]){4,})")  # a run of full-width characters
PAD = b"\x81\x40"


def table():
    out = {}
    for ln in open(TSV, encoding="utf-8"):
        if ln.startswith("#") or not ln.strip():
            continue
        jp, en = ln.rstrip("\n").split("\t")[:2]
        out[jp] = en.replace(" (?)", "").strip()
    return out


def lines(iso):
    """-> [(offset, raw bytes, text)] for every credit line in both rolls."""
    out = []
    for lo, hi in ROLLS:
        for m in LINE.finditer(iso, lo, hi):
            raw = m.group(1)
            try:
                text = raw.decode("cp932")
            except UnicodeDecodeError:
                continue
            out.append((m.start(), raw, text.strip("　 ")))
    return out


def render(en, nbytes):
    """English as letter-pair cells, centred in nbytes (an even number)."""
    body = sncells.sjis_plain(en)
    if len(body) > nbytes:
        raise SystemExit(f"credit line {en!r} needs {len(body)} bytes, the slot has {nbytes}")
    left = (nbytes - len(body)) // 4                       # cells of padding on the left
    right = (nbytes - len(body)) // 2 - left
    return PAD * left + body + PAD * right


def apply(isos):
    """Rewrite the ending roll's image and every exact copy of it on both tracks."""
    t = table()
    originals = {k: bytes(v) for k, v in isos.items()}
    lo, hi = IMAGE
    image = originals[2][lo:hi]
    # where the whole 3-sector image sits on each track (track 24 carries it too, at its own offset)
    places = []
    for k, src in originals.items():
        at = 0
        while True:
            at = src.find(image[:256], at)
            if at < 0:
                break
            if src[at:at + len(image)] == image:
                places.append((k, at))
            at += 1
    done, missing = 0, []
    for off, raw, text in lines(originals[2]):
        en = t.get(text)
        if en is None:
            if re.search(r"[\u4e00-\u9fff\u3040-\u30ff]", text):
                missing.append(text)
            continue
        new = render(en, len(raw))
        assert len(new) == len(raw)
        for k, at in places:
            p = at + (off - lo)
            assert originals[k][p:p + len(raw)] == raw
            isos[k][p:p + len(raw)] = new
        done += 1
    assert len(CAPTION_EN) == len(CAPTION_JP)
    caps = 0
    for k, src in originals.items():
        at = src.find(CAPTION_JP)
        assert at >= 0 and src.find(CAPTION_JP, at + 1) < 0, f"track {k}: the Junker HQ caption is not where expected"
        isos[k][at:at + len(CAPTION_JP)] = CAPTION_EN
        caps += 1
    return (f"credits: {done} lines in English in {len(places)} copies of the ending roll; untranslated: {missing}; "
            f"Junker HQ caption on {caps} tracks")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    iso = open("disc/track02.iso", "rb").read()
    t = table()
    for off, raw, text in lines(iso):
        print(f"{off:#07x} {len(raw):2d}B {text:<16} -> {t.get(text, '(none)')}")
