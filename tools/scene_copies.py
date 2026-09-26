#!/usr/bin/env python3
"""Scenes that exist on the disc more than once, and are loaded from the copy the scene table does not name.

  scene_copies.py          -> list the copies of the name-search screen on both tracks

Track 24 carries a second set of scene banks at its own offsets -- 17 of the 33 scenes have one. For
most of them it does not matter, because the game loads the bank the scene table names and that is the
one the build patches. The name-search screen is the exception, and hardware proved it: the computer
kept showing the katakana keyboard while the patched bank sat unread at sector 254. Its second copy, at
sector 83 of track 24, is what Gillian actually reads.

So that copy is built too. It is the same screen with fewer records, at different offsets, so nothing
can be mapped by position: the English is matched to it **by the Japanese it replaces**, message for
message and word for word, out of the scene's own translation file.
"""
import json
import os
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import scenes as S  # noqa: E402
import snwords  # noqa: E402

HEAD = bytes.fromhex("4c205004f1970c1c")            # the name-search screen's script header
SECTORS = 6


def find(iso, head=HEAD):
    out, i = [], -1
    while True:
        i = iso.find(head, i + 1)
        if i < 0:
            return out
        out.append(i)


def describe(iso, base, loaded=SECTORS * 0x800):
    """A scene description for a copy that is not in the scene table."""
    chain, regions, _ = S.messages(iso, base, loaded)
    if not chain:
        return None
    text_start, text_end = regions[0][0], regions[-1][1]
    words = snwords.word_list(iso, base, text_start)
    return {"lba": base // 0x800, "base": base, "loaded": loaded, "text_start": text_start,
            "text_end": text_end, "regions": regions,
            "words": [{"off": o, "jp": t, "size": z} for o, t, z in words], "messages": chain}


def translation(copy, scene, words_en, msgs_en):
    """The scene's English, keyed to this copy's own offsets by the Japanese each one replaces."""
    by_jp = {m["jp"]: msgs_en[m["ptr"]] for m in scene["messages"] if m["ptr"] in msgs_en}
    msgs = {m["ptr"]: by_jp[m["jp"]] for m in copy["messages"] if m["jp"] in by_jp}
    wmap = {w["off"]: t for w in scene["words"] if (t := words_en.get(w["off"])) for _ in (0,)}
    by_word = {w["jp"]: wmap[w["off"]] for w in scene["words"] if w["off"] in wmap}
    words = {w["off"]: by_word[w["jp"]] for w in copy["words"] if w["jp"] in by_word}
    return words, msgs, len(msgs), len(words)


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for trk in (2, 24):
        iso = open(f"disc/track{trk:02d}.iso", "rb").read()
        for off in find(iso):
            d = describe(iso, off)
            n = len(d["messages"]) if d else 0
            print(f"track {trk:02d}: copy at {off:#08x} (sector {off // 0x800}): "
                  f"{n} messages, {len(d['words']) if d else 0} words")


if __name__ == "__main__":
    main()
