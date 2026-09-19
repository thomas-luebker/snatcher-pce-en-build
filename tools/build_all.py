#!/usr/bin/env python3
"""Build the English Snatcher image: code patch + names + every scene + (optionally) the English voices.

  build_all.py              -> build-en/   (multi-bin, for the emulator)
  VOICE=1 build_all.py      -> also swap in the Sega CD voice clips (all tables)

Per scene: the menu words are rewritten in place where the English fits (else they move into the slack),
then the whole text area is re-encoded message by message (tools/snhuff.py) and every say command
`12 <speaker> 00 <lo> <hi>` re-pointed. Scene data comes from work/scenes/<lba>.json (the game's own scene
table), English from translations/scenes/<lba>.tsv. Scenes with identical Japanese share one translation.
"""
import glob
import json
import os
import shutil
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import cdsector as C  # noqa: E402
import sncells  # noqa: E402
import snhack  # noqa: E402
import snhuff  # noqa: E402
import snnames  # noqa: E402

N = "Snatcher CD-ROMantic (Japan)"


def load_tsv(path):
    words, msgs = {}, {}
    for line in open(path):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        kind, key, *rest = line.split("\t")
        text = rest[-1] if rest else ""
        (words if kind == "W" else msgs)[int(key, 16)] = text
    return words, msgs


SCENES_DIR = os.environ.get("SCENES", "work/scenes_resolved" if os.path.isdir("work/scenes_resolved")
                            else "translations/scenes")


def translation_for(lba, scenes):
    """The scene's own file, or that of the scene with identical Japanese text."""
    p = f"{SCENES_DIR}/{lba:03x}.tsv"
    if os.path.exists(p):
        return load_tsv(p)
    key = "".join(m["jp"] for m in scenes[lba]["messages"])
    for other, sc in scenes.items():
        if other != lba and "".join(m["jp"] for m in sc["messages"]) == key:
            q = f"{SCENES_DIR}/{other:03x}.tsv"
            if os.path.exists(q):
                w, m = load_tsv(q)
                # same text, possibly different offsets: map by position
                wmap = {a["off"]: b for a, b in zip(scenes[lba]["words"], w.values())}
                mmap = {a["ptr"]: b for a, b in zip(scenes[lba]["messages"], m.values())}
                return wmap, mmap
    return None


def enlarge(iso, lba, old_n, new_n):
    """Give a scene more sectors: patch the count byte of its table entry wherever it appears.
    Safe up to 16 sectors = 4 RAM banks ($7E-$81, the size of the game's own largest scene) and only
    into sectors that no other load-table entry claims."""
    pat = bytes([0x00, lba & 0xFF, lba >> 8, 0x04, 0x16, 0x00, old_n, 0x00])
    hits = 0
    i = iso.find(pat)
    while i >= 0:
        iso[i + 6] = new_n
        hits += 1
        i = iso.find(pat, i + 1)
    return hits


def build_scene(iso, sc, words_en, msgs_en, coding, report):
    base, loaded = sc["base"], sc["loaded"]
    free_end = sc["text_end"]
    # --- menu words -------------------------------------------------------------------------------
    inplace = moved = 0
    relocs = []
    for w in sc["words"]:
        en = words_en.get(w["off"])
        if not en:
            continue
        data = sncells.sjis_plain(en)
        if len(data) <= w["size"]:
            iso[base + w["off"]:base + w["off"] + w["size"] + 1] = (data + b"\xff").ljust(w["size"] + 1, b"\xff")
            inplace += 1
        else:
            relocs.append((w["off"], data))
    # --- messages -------------------------------------------------------------------------------
    # Pointers are arbitrary offsets into the loaded block, so a message may live in any free span:
    # the scene's own text regions, the last one extended to the end of what the scene loads.
    spans = [[lo, hi] for lo, hi in sc["regions"]]
    spans[-1][1] = loaded
    cursor = [lo for lo, _ in spans]
    chunks = {i: bytearray() for i in range(len(spans))}
    new_ptr = {}
    for m in sc["messages"]:
        data = coding.encode(msgs_en.get(m["ptr"]) or "...")
        for i, (lo, hi) in enumerate(spans):
            if cursor[i] + len(data) <= hi:
                new_ptr[m["ptr"]] = cursor[i]
                chunks[i] += data
                cursor[i] += len(data)
                break
        else:
            return f"  OVER BUDGET by {len(data)} bytes at message {m['ptr']:#x}"
    for off, data in relocs:                               # relocated menu words take what is left
        for i, (lo, hi) in enumerate(spans):
            if cursor[i] + len(data) + 1 <= hi:
                pos = cursor[i]
                chunks[i] += data + b"\xff"
                cursor[i] += len(data) + 1
                break
        else:
            return f"  OVER BUDGET: no room for a menu word"
        for j in range(sc["text_start"]):
            if iso[base + j] == 0xF1 and (iso[base + j + 1] | (iso[base + j + 2] << 8)) == off:
                iso[base + j + 1:base + j + 3] = pos.to_bytes(2, "little")
                moved += 1
    for i, (lo, hi) in enumerate(spans):
        iso[base + lo:base + hi] = bytes(chunks[i]).ljust(hi - lo, b"\xff")
    for m in sc["messages"]:
        for c in m["cmds"]:
            iso[base + c + 3:base + c + 5] = new_ptr[m["ptr"]].to_bytes(2, "little")
    used = sum(len(c) for c in chunks.values())
    budget = sum(hi - lo for lo, hi in spans)
    report.append(f"scene {sc['lba']:#05x}: {len(sc['messages']):4d} msgs, words {inplace} in place / {moved} moved, "
                  f"{used:5d} of {budget:5d} bytes")
    return None


def main():
    coding = snhuff.Coding()
    scenes = {}
    for f in sorted(glob.glob("work/scenes/*.json")):
        sc = json.load(open(f))
        scenes[sc["lba"]] = sc
    isos = {2: open("disc/track02.iso", "rb").read(), 24: open("disc/track24.iso", "rb").read()}
    report = []
    for t in isos:
        data, sizes = snhack.apply(isos[t], coding)
        data, nn = snnames.apply(data)
        isos[t] = bytearray(data)
    report.append(f"code: {sizes}, names {nn} bytes")
    skipped = []
    lbas = sorted(scenes)
    for k, lba in enumerate(lbas):
        sc = scenes[lba]
        tr = translation_for(lba, scenes)
        if tr is None:
            skipped.append(lba)
            continue
        # the English may not fit the sectors the scene loads today; it may grow into the unclaimed
        # sectors before the next scene, at most to 16 (4 RAM banks)
        nxt = lbas[k + 1] if k + 1 < len(lbas) else lba + 16
        room = min(16, nxt - lba)
        r = None
        for n in range(sc["loaded"] // 0x800, room + 1):
            trial = {t: bytearray(iso) for t, iso in isos.items()}
            sc["loaded"] = n * 0x800
            for t in trial:
                r = build_scene(trial[t], sc, tr[0], tr[1], coding, report if t == 2 else [])
            if r is None:
                if n != sc["lba"] and n * 0x800 != json.load(open(f"work/scenes/{lba:03x}.json"))["loaded"]:
                    old = json.load(open(f"work/scenes/{lba:03x}.json"))["loaded"] // 0x800
                    for t in trial:
                        enlarge(trial[t], lba, old, n)
                    report[-1] += f"  (grown {old} -> {n} sectors)"
                isos.update(trial)
                break
            report.pop() if report and report[-1].startswith("  ") else None
        if r:
            report.append(f"scene {lba:#05x}: {r} -- left Japanese")
    if skipped:
        report.append(f"no translation for: {[hex(x) for x in skipped]}")
    if os.environ.get("VOICE"):
        import voices
        report.append(voices.apply(isos))
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
