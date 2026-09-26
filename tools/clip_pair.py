#!/usr/bin/env python3
"""Pair PC Engine voice clips with Sega CD English clips by what they say.

  work/venv/bin/python tools/clip_pair.py        -> translations/clip_align.json (order-only one kept as work/audio/clip_align_order.json)

The first pairing (tools/clip_align.py) used only order and duration. On hardware that left lines Japanese
(Gibson's body in the factory) and, worse, slid a whole run of lines by three places (the time-bomb escape:
"We're getting out of here!" played on the line after the one that says it). Transcripts of both sides
(Whisper: translations/asr/pce_asr.json in Japanese, translations/asr/scd_asr.json in English) make content the join:

  score(i, j) = meaning   LaBSE cross-language similarity of the two transcripts
              + duration  -|log(length ratio)|, weighted more where a transcript is noise
  pairing     = order-preserving alignment (both games play their clips in story order) with gaps on
                both sides: PC Engine lines the Sega CD cut stay Japanese, Sega CD lines with no PC Engine
                slot are left out.

Whisper returns stock phrases or nothing for screams, grunts and effects; those clips are recognised as
noise and paired on duration and position alone.
"""
import json
import math
import os
import re

import numpy as np

ALIGN = "translations/clip_align.json"
KEEP = "work/audio/clip_align_order.json"
STOCK = re.compile(r"ご視聴ありがとうございました|thank you\.?$|the end\.?$|音楽|bgm", re.I)


def noise(text, lang):
    """Whisper's output for a scream, a grunt or an effect: nothing, a stock phrase, or words in the wrong
    script ("OH представ kilograms" for an English scream, "pursuant" for a Japanese one)."""
    t = text.strip()
    if not t or STOCK.search(t):
        return True
    if lang == "ja":
        return len(re.findall(r"[぀-ヿ一-鿿]", t)) < 2
    if re.search(r"[^\x00-\x7f‘-”…—]", t):
        return True
    return len(re.findall(r"[A-Za-z]", t)) < 2


def fill_gaps(pairs, pn, sn, pce, scd, sim):
    """Fill the gaps between two confident pairs by order and length.

    Content cannot help inside a gap: it is where the transcripts are weakest -- screams and grunts come
    back as nonsense on both sides ("Eeeh! Eeeh!", "dinosaurs", "pursuant"), and a loose localisation
    scores low ("ひどいことをしやがる" -> "Dear God!"). But a gap is short and both games play their clips in
    the same order, so a local alignment on duration alone is reliable there. Only within one section:
    at a section boundary the Sega CD adds and cuts whole scenes.
    """
    out, k = [], 0
    table = lambda i: pce[i]["table"]
    while k < len(pairs):
        if pairs[k][0] is not None and pairs[k][1] is not None:
            out.append(pairs[k]); k += 1; continue
        run = []
        while k < len(pairs) and (pairs[k][0] is None or pairs[k][1] is None):
            run.append(pairs[k]); k += 1
        ps = [i for i, j in run if i is not None]
        ss = [j for i, j in run if j is not None]
        before = out[-1][0] if out else None
        after = pairs[k][0] if k < len(pairs) else None
        same = before is not None and after is not None and all(table(i) == table(before) == table(after) for i in ps)
        got = local_pairs(ps, ss, pce, scd, sim, pn, sn) if same else {}
        out += [[i, got.get(i)] for i in ps]
        out += [[None, j] for j in ss if j not in got.values()]
    return out


def local_pairs(ps, ss, pce, scd, sim, pn, sn):
    """Order-preserving alignment of the leftovers, on duration plus whatever the transcripts still say
    -> {pce index: scd index}. Duration decides for screams and grunts; where both sides have real words
    the similarity breaks ties, so a grunt cannot steal a line from its neighbour on length alone."""
    n, m = len(ps), len(ss)
    if not n or not m:
        return {}
    def fits(i, j):  # noqa: E306
        slot8k = pce[i]["sectors"] * 2048 * 2 / 8000
        return (abs(math.log(max(0.2, pce[i]["sec"]) / max(0.2, scd[j]["sec"]))) < math.log(3.0)
                and scd[j]["sec"] <= 1.15 * slot8k)

    # Same number of leftovers on both sides: they are the same lines, in order. This is the common case
    # in a gap and it needs no guessing -- which matters because the transcripts here are the unreliable
    # ones (Whisper writes real-looking words for screams: "dinosaurs", "ile").
    if n == m and all(fits(ps[k], ss[k]) for k in range(n)):
        return {ps[k]: ss[k] for k in range(n)}
    NEG, GAP = -1e9, -0.15
    D = [[NEG] * (m + 1) for _ in range(n + 1)]
    B = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        D[i][0] = GAP * i
    for j in range(m + 1):
        D[0][j] = GAP * j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            opts = [(D[i - 1][j] + GAP, 1), (D[i][j - 1] + GAP, 2)]
            if fits(ps[i - 1], ss[j - 1]):
                pi, sj = ps[i - 1], ss[j - 1]
                score = 0.2 - abs(math.log(max(0.2, pce[pi]["sec"]) / max(0.2, scd[sj]["sec"])))
                score += 0.35 if pn[pi] == sn[sj] else -0.35      # speech with speech, a grunt with a grunt
                if not pn[pi] and not sn[sj]:
                    score += 2.0 * max(0.0, float(sim[pi, sj]) - 0.25)
                opts.append((D[i - 1][j - 1] + score, 0))
            D[i][j], B[i][j] = max(opts)
    got, i, j = {}, n, m
    while i > 0 and j > 0:
        b = B[i][j]
        if b == 0:
            got[ps[i - 1]] = ss[j - 1]; i, j = i - 1, j - 1
        elif b == 1:
            i -= 1
        else:
            j -= 1
    return got


def snap_neighbours(pairs, pce, scd, sim):
    """Move a pairing onto the neighbour of a confident pair.

    Around a pair both sides agree on, the clip before it is the clip before it in the other version too.
    Whisper sometimes garbles a line (Harry's drunk greeting came out as "ご機関か"), so its similarity is
    low and the aligner can attach that English take to a better-scoring line further back, leaving the
    real one Japanese -- even though it sits right next to an anchor. This puts it back.
    """
    by_p = {i: j for i, j in pairs if i is not None and j is not None}
    by_s = {j: i for i, j in by_p.items()}
    # A pair is an anchor when it clearly says the same thing, or when it sits next to one that does:
    # consecutive pairs move together, so the neighbour's agreement vouches for it.
    strong = {i for i, j in by_p.items() if float(sim[i, j]) >= 0.45}
    anchors = {i for i in by_p if i in strong or (i + 1 in strong and by_p.get(i + 1) == by_p[i] + 1)
               or (i - 1 in strong and by_p.get(i - 1) == by_p[i] - 1)}
    moved = 0
    for i, j in sorted(by_p.items()):
        if i not in anchors:
            continue
        for di, dj in ((-1, -1), (1, 1)):
            i2, j2 = i + di, j + dj
            if not (0 <= i2 < len(pce) and 0 <= j2 < len(scd)):
                continue
            if i2 in by_p or j2 not in by_s:
                continue                                   # the neighbour must be free, its partner taken
            owner = by_s[j2]
            if abs(owner - i2) <= 2:
                continue                                   # only when the current owner is far away
            slot8k = pce[i2]["sectors"] * 2048 * 2 / 8000
            if scd[j2]["sec"] > 1.15 * slot8k:
                continue
            if float(sim[owner, j2]) > float(sim[i2, j2]) + 0.25:
                continue                                   # the far pair really does say the same thing
            del by_p[owner]
            by_p[i2] = j2
            by_s[j2] = i2
            moved += 1
    if moved:
        print(f"{moved} pairing(s) moved onto the neighbour of a confident pair")
    out = []
    for i, j in pairs:
        if i is not None:
            out.append([i, by_p.get(i)])
        elif j not in by_s:
            out.append([None, j])
    return out


def main():
    if not os.path.exists(KEEP):
        raise SystemExit(f"{KEEP} missing: make the order-only pairing first with\n"
                         f"  python3 tools/clip_align.py disc/track02.iso segacd/files/PCMLT_01.BIN {KEEP}")
    d = json.load(open(KEEP))
    pa = json.load(open("translations/asr/pce_asr.json"))
    sa = json.load(open("translations/asr/scd_asr.json"))
    pce, scd = d["pce"], d["scd"]
    pt = [pa.get(f"t{c['table']}/A{c['idx']:03d}", {}).get("text", "") for c in pce]
    st = [sa[str(j)]["text"] for j in range(len(scd))]
    pn, sn = [noise(t, "ja") for t in pt], [noise(t, "en") for t in st]

    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer("sentence-transformers/LaBSE", device="mps")
    E = m.encode([t or "." for t in pt], normalize_embeddings=True, batch_size=64)
    F = m.encode([t or "." for t in st], normalize_embeddings=True, batch_size=64)
    sim = E @ F.T

    n, k = len(pce), len(scd)
    dur = np.array([[-abs(math.log(max(0.2, pce[i]["sec"]) / max(0.2, scd[j]["sec"]))) for j in range(k)] for i in range(n)])
    both = np.outer(~np.array(pn), ~np.array(sn))
    score = np.where(both, (sim - 0.30) * 2.0 + 0.25 * dur, 0.05 + 0.6 * dur)
    # only fair where one side is noise and the other speech: a scream against a sentence
    mixed = np.outer(np.array(pn), ~np.array(sn)) | np.outer(~np.array(pn), np.array(sn))
    score = np.where(mixed, score - 0.25, score)
    # voices.py keeps each clip's slot and can at most halve the rate: English longer than ~2.3x the
    # Japanese slot would be cut off. Those pairs are either wrong ("Talking about me?" <- "I want my pizza!")
    # or right but far too long for the slot -- either way the line is better left Japanese.
    slot8k = np.array([c["sectors"] * 2048 * 2 / 8000 for c in pce])
    too_long = np.array([[scd[j]["sec"] > 1.15 * slot8k[i] for j in range(k)] for i in range(n)])
    score = np.where(too_long, -5.0, score)

    GAP = -0.25
    band = 90                                        # the two orders never drift further apart than this
    NEG = -1e9
    D = np.full((n + 1, k + 1), NEG)
    B = np.zeros((n + 1, k + 1), np.int8)
    D[0, :] = GAP * np.arange(k + 1)
    D[:, 0] = GAP * np.arange(n + 1)
    for i in range(1, n + 1):
        c = i * k / n
        lo, hi = max(1, int(c - band)), min(k, int(c + band))
        for j in range(lo, hi + 1):
            opts = (D[i - 1, j - 1] + score[i - 1, j - 1], D[i - 1, j] + GAP, D[i, j - 1] + GAP)
            b = int(np.argmax(opts))
            D[i, j], B[i, j] = opts[b], b
    pairs, i, j = [], n, k
    while i > 0 or j > 0:
        b = B[i, j] if i > 0 and j > 0 else (1 if i > 0 else 2)
        if b == 0:
            pairs.append([i - 1, j - 1]); i, j = i - 1, j - 1
        elif b == 1:
            pairs.append([i - 1, None]); i -= 1
        else:
            pairs.append([None, j - 1]); j -= 1
    pairs.reverse()
    # a match that scores below a gap is not a translation of the line: keep that line Japanese
    out = []
    for i, j in pairs:
        if i is not None and j is not None and score[i, j] < GAP:
            out += [[i, None], [None, j]]
        else:
            out.append([i, j])
    out = snap_neighbours(out, pce, scd, sim)
    out = fill_gaps(out, pn, sn, pce, scd, sim)
    d["pairs"] = out
    json.dump(d, open(ALIGN, "w"))
    old = {i: j for i, j in json.load(open(KEEP))["pairs"] if i is not None}
    new = {i: j for i, j in out if i is not None}
    same = sum(1 for i in new if new[i] is not None and old.get(i) == new[i])
    print(f"{sum(1 for v in new.values() if v is not None)} of {n} PC Engine clips paired "
          f"(was {sum(1 for v in old.values() if v is not None)}); {same} pairs unchanged")


if __name__ == "__main__":
    main()
