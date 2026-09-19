#!/usr/bin/env python3
"""Per-scene data straight from the game's scene table:  scenes.py  ->  work/scenes/<lba>.json

Each type-$16 table entry (ISO 0xC000-0xD000: `00 lo hi 04 16 00 nn 00`) is one scene slot of nn sectors,
identical in both data tracks. For every slot: the true messages (say commands `12 ss 00 lo hi` whose target
decodes; chance hits inside another message dropped), the start of the text area, and the menu word list in
front of it.
"""
import json
import os
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import dump_script as D  # noqa: E402
import snpack  # noqa: E402
import snwords  # noqa: E402

ENTRY = re.compile(rb"\x00[\x00-\xff][\x00-\x03]\x04\x16\x00[\x01-\x20]\x00", re.S)
SAY = re.compile(rb"\x12[\x00-\x4a]\x00", re.S)
NAMES = "reference/snatcher-disasm/data/dialogue_6D47-6F27_names.bin"


def table(iso):
    return [((m.group()[1] | (m.group()[2] << 8)), m.group()[6]) for m in ENTRY.finditer(iso, 0xC000, 0xD000)]


def messages(iso, base, loaded):
    found = {}
    for m in SAY.finditer(iso, base, base + loaded):
        i = m.start()
        ptr = iso[i + 3] | (iso[i + 4] << 8)
        if 0x40 <= ptr < loaded:
            pairs, end = snpack.decode(iso, base + ptr, 0, limit=500)
            if end is None or len(pairs) < 1 or (end >> 1) - base > loaded:
                continue
            t = D.render(pairs)
            r = found.setdefault(ptr, {"ptr": ptr, "end": (end >> 1) - base, "cmds": [], "speaker": iso[i + 1], "jp": t})
            r["cmds"].append(i - base)
    # The text area is one unbroken chain of back-to-back messages (each starts where the previous ends).
    # Link every candidate to the one starting at its end and keep the chain that covers the most bytes;
    # chance hits (pattern inside the script or inside packed text) do not form long chains.
    by_ptr = {r["ptr"]: r for r in found.values()}
    ends = {r["end"] for r in found.values()}
    chains = []
    for r in sorted(found.values(), key=lambda r: r["ptr"]):
        if r["ptr"] in ends:
            continue                                  # not the head of a chain
        chain, cur = [], r
        while cur is not None:
            chain.append(cur)
            cur = by_ptr.get(cur["end"])
        chains.append(chain)
    chains.sort(key=lambda c: c[0]["ptr"] - c[-1]["end"])             # longest (in bytes) first
    main_chain = chains[0] if chains else []
    # further chains count as text when they lie after the main one's start, do not overlap a kept chain,
    # and look like Japanese (a broken chain means one message in between is reached some other way)
    kept = [main_chain] if main_chain else []
    for c in chains[1:]:
        lo, hi = c[0]["ptr"], c[-1]["end"]
        if any(lo < k[-1]["end"] and hi > k[0]["ptr"] for k in kept):
            continue
        text = "".join(m["jp"] for m in c)
        jp = sum(1 for ch in text if "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff" or ch in "。、？！ー　・…")
        if len(c) >= 2 and jp > 0.6 * len(re.sub(r"<[0-9A-F]{4}>", "", text)):
            kept.append(c)
    kept.sort(key=lambda c: c[0]["ptr"])
    for n, c in enumerate(kept):
        for m in c:
            m["region"] = n
    return [m for c in kept for m in c], [[c[0]["ptr"], c[-1]["end"]] for c in kept], list(found.values())


def main():
    iso = open("disc/track02.iso", "rb").read()
    names = [x[1:].decode("cp932", "replace") if x[:1] and x[0] < 0x80 else x.decode("cp932", "replace")
             for x in open(NAMES, "rb").read().split(b"\xff")]
    os.makedirs("work/scenes", exist_ok=True)
    total = 0
    for lba, n in table(iso):
        base, loaded = lba * 0x800, n * 0x800
        chain, regions, allm = messages(iso, base, loaded)
        if not chain:
            print(f"scene {lba:#05x}: no messages")
            continue
        text_start, text_end = regions[0][0], regions[-1][1]
        for r in chain:
            r["speaker_name"] = names[r["speaker"] - 1] if 0 < r["speaker"] <= len(names) else ""
        words = snwords.word_list(iso, base, text_start)
        last = max(i for i in range(loaded) if iso[base + i] not in (0x00, 0xFF)) + 1
        json.dump({"lba": lba, "base": base, "loaded": loaded, "text_start": text_start, "text_end": text_end, "regions": regions,
                   "data_end": last, "words": [{"off": o, "jp": t, "size": z} for o, t, z in words], "messages": chain},
                  open(f"work/scenes/{lba:03x}.json", "w"), ensure_ascii=False, indent=1)
        total += len(chain)
        print(f"scene {lba:#05x}: {len(chain):4d} messages {text_start:#06x}-{text_end:#06x} (data ends {last:#06x} of {loaded:#06x}), "
              f"{len(words):3d} menu words, {len(regions)} regions covering {sum(b - a for a, b in regions)} of {text_end - text_start} bytes")
    print(total, "messages in all scenes")


if __name__ == "__main__":
    main()
