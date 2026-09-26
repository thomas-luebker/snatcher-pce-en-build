#!/usr/bin/env python3
"""English takes the in-order aligner cannot reach -> work/audio/clip_stray.tsv

  work/venv/bin/python tools/clip_stray.py

tools/clip_pair.py keeps both versions in story order, which is right nearly everywhere and is what
stops a line being paired with a stranger. But the PC Engine sometimes plays a line the Sega CD keeps
somewhere else entirely -- Katrina's goodbye sits twenty clips earlier over there -- and no monotonic
alignment can reach it. Those show up as a Japanese voice in the middle of an English scene.

So this looks only at what is left: every PC Engine clip with no English, against every Sega CD take
nothing claimed, by meaning alone (LaBSE) and with no order to obey. It proposes; a person disposes,
into translations/clip_fixups.tsv.
"""
import json
import sys

MIN_SIM, MIN_WORDS = 0.60, 3


def main():
    d = json.load(open("translations/clip_align.json"))
    pa = json.load(open("translations/asr/pce_asr.json"))
    sa = json.load(open("translations/asr/scd_asr.json"))
    pair = {i: j for i, j in d["pairs"] if i is not None and j is not None}
    used = set(pair.values())
    jp_of = lambda c: pa.get(f"t{c['table']}/A{c['idx']:03d}", {}).get("text", "")   # noqa: E731
    left = [(i, c) for i, c in enumerate(d["pce"]) if i not in pair and len(jp_of(c)) >= MIN_WORDS]
    free = [j for j in range(len(d["scd"])) if j not in used and len(sa[str(j)]["text"].split()) >= MIN_WORDS]
    print(f"{len(left)} clips without English, {len(free)} English takes unclaimed")

    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer("sentence-transformers/LaBSE", device="mps")
    E = m.encode([jp_of(c) for _, c in left], normalize_embeddings=True, batch_size=64)
    F = m.encode([sa[str(j)]["text"] for j in free], normalize_embeddings=True, batch_size=64)
    sim = E @ F.T

    rows = []
    for a, (i, c) in enumerate(left):
        b = int(sim[a].argmax())
        s = float(sim[a][b])
        j = free[b]
        slot = c["sectors"] * 2048 * 2 / 8000
        if s < MIN_SIM or d["scd"][j]["sec"] > 1.6 * slot:
            continue
        rows.append((s, c["table"], c["idx"], j, jp_of(c), sa[str(j)]["text"]))
    rows.sort(reverse=True)
    with open("work/audio/clip_stray.tsv", "w", encoding="utf-8") as f:
        for s, t, x, j, jp, en in rows:
            f.write(f"{t}\t{x}\t{j}\t{en[:70]}\t# {s:.2f}  {jp[:40]}\n")
    print(f"{len(rows)} proposals in work/audio/clip_stray.tsv")
    for s, t, x, j, jp, en in rows[:12]:
        print(f"  {s:.2f}  table {t} idx {x:3d} <- SCD {j:4d}  {jp[:34]:<36} {en[:44]}")


if __name__ == "__main__":
    main()
