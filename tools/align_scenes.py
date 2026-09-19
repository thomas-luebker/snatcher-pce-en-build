#!/usr/bin/env python3
"""Match every scene's Japanese messages to the Sega CD English:  align_scenes.py  -> work/aligned/<lba>.json

For each scene (work/scenes/*.json) the message list is aligned (tools/text_align.py: storage order,
length + punctuation/number/Latin cues) against every Sega CD script file; the best file wins. Each message
gets its English candidate (or none) and the scene gets a score per line, so weak scenes can be treated
with suspicion downstream.
"""
import glob
import json
import os
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import text_align as TA  # noqa: E402


def main():
    scd = TA.scd_files("reference/junkerhq-dumps/scd")
    os.makedirs("work/aligned", exist_ok=True)
    done = {}
    for f in sorted(glob.glob("work/scenes/*.json")):
        sc = json.load(open(f))
        msgs = sc["messages"]
        key = "".join(m["jp"] for m in msgs)
        if key in done:                                   # identical scene stored several times
            best = done[key]
        else:
            best = None
            for name, lines in scd.items():
                if not lines or not 0.25 < len(lines) / len(msgs) < 4:
                    continue
                pairs, score = TA.align(msgs, lines, TA.RATIO)
                norm = score / max(len(msgs), len(lines))
                if best is None or norm > best[0]:
                    best = (norm, name, pairs)
            done[key] = best
        norm, name, pairs = best
        en = {i: scd[name][j] for i, j in pairs}
        out = [{"ptr": m["ptr"], "speaker": m.get("speaker_name", ""), "jp": m["jp"],
                "en": TA_clean(en[i]["en"]) if i in en else None} for i, m in enumerate(msgs)]
        json.dump({"lba": sc["lba"], "scd_file": name, "score": round(norm, 3), "messages": out},
                  open(f"work/aligned/{sc['lba']:03x}.json", "w"), ensure_ascii=False, indent=1)
        print(f"scene {sc['lba']:#05x}: {len(msgs):4d} msgs -> {name} score/line {norm:.2f}, {len(pairs)} paired", flush=True)


def TA_clean(en):
    import re
    en = re.sub(r"</?cc[^>]*>", "", en).replace("<nl>", " ")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", en)).strip()


if __name__ == "__main__":
    main()
