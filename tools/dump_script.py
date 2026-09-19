#!/usr/bin/env python3
"""Find Snatcher's scene banks on a data track and dump every message.

  dump_script.py disc/track02.iso work/script_t02.json [work/script_t02.txt]

Scene slots come from the game's own scene table (8-byte entries: byte 1-2 = LBA,
byte 3 = $04, byte 4 = type; type $16 = the 33 adventure scenes on a 0x8000 grid
from LBA $9E, other types are checked too). A slot is up to 0x8000 bytes. Its script says a message with
    12 <speaker> 00 <lo> <hi>        (offset of the packed text inside the bank)
(the engine turns this into queue command 08; verified against a save state:
queue held `08 03 00 0a 25` while bank offset 0x250A decoded to the line on
screen). Banks are found by voting: every `12 ss 00 lo hi` whose target decodes
to clean Japanese votes for the bank bases it could belong to.
"""
import json
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import snpack  # noqa: E402

BANK, SECTOR, MAX_SPEAKER = 0x8000, 0x800, 0x4A
TABLE = "reference/snatcher-disasm/data/scene_desc_tables.bin"
SAY = re.compile(rb"\x12[\x00-\x4a]\x00", re.S)
NAMES = "reference/snatcher-disasm/data/dialogue_6D47-6F27_names.bin"


def render(pairs):
    out = []
    for p in pairs:
        try:
            out.append(p.decode("cp932"))
        except UnicodeDecodeError:
            out.append(f"<{p.hex().upper()}>")
    return "".join(out)


def message(iso, base, ptr):
    pairs, end = snpack.decode(iso, base + ptr, 0, limit=400)
    if end is None or len(pairs) < 2:
        return None
    t = render(pairs)
    esc = t.count("<")
    jp = sum(1 for c in t if "぀" <= c <= "ヿ" or "一" <= c <= "鿿" or c in "。、？！ー　・…")
    if esc > 6 or jp < 0.6 * (len(t) - esc * 6):
        return None
    return t, (end >> 1) - base


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    iso = open(argv[1], "rb").read()
    tab = open(TABLE, "rb").read()
    lbas = sorted({(e[1] | (e[2] << 8)) for e in (tab[i:i + 8] for i in range(0, len(tab) - 7, 8))
                   if e[0] == 0 and e[3] == 4 and 0 < (e[1] | (e[2] << 8)) < len(iso) // SECTOR})
    bounds = [l * SECTOR for l in lbas] + [len(iso)]
    votes, sites, banks = Counter(), defaultdict(list), []
    for base, nxt in zip(bounds, bounds[1:]):
        size = min(BANK, nxt - base)
        for m in SAY.finditer(iso, base, base + size):
            i = m.start()
            ptr = iso[i + 3] | (iso[i + 4] << 8)
            if 0x40 <= ptr < size and message(iso, base, ptr):
                votes[base] += 1
                sites[base].append(i)
        if votes[base] >= 3:
            banks.append(base)
    try:
        names = [x[1:].decode("cp932", "replace") if x[:1] == b"2" else x.decode("cp932", "replace")
                 for x in open(NAMES, "rb").read().split(b"\xff")]
    except OSError:
        names = []
    out = []
    for base in banks:
        seen = set()
        for i in sorted(sites[base]):
            sp, ptr = iso[i + 1], iso[i + 3] | (iso[i + 4] << 8)
            msg = message(iso, base, ptr)
            if not msg:
                continue
            out.append({"bank": base, "cmd": i - base, "speaker": sp,
                        "speaker_name": names[sp - 1] if 0 < sp <= len(names) else "",
                        "ptr": ptr, "end": msg[1], "jp": msg[0], "dup": ptr in seen})
            seen.add(ptr)
    # True messages lie back to back in a slot's text area. Keep a message if it touches a neighbour;
    # an isolated one only if it is clean Japanese ending like a sentence. This drops chance hits of
    # the byte pattern inside packed text and graphics.
    by_bank = defaultdict(list)
    for r in out:
        by_bank[r["bank"]].append(r)
    kept = []
    for rs in by_bank.values():
        starts, ends = {r["ptr"] for r in rs}, {r["end"] for r in rs}
        for r in rs:
            clean = "<" not in r["jp"].replace("<82F2>", "") and r["jp"][-1:] in "。？！…・　」"
            if r["ptr"] in ends or r["end"] in starts or clean:
                kept.append(r)
    dropped, out = len(out) - len(kept), kept
    print(f"dropped {dropped} isolated / unclean candidates")
    json.dump(out, open(argv[2], "w"), ensure_ascii=False, indent=1)
    if len(argv) > 3:
        with open(argv[3], "w") as f:
            for r in out:
                if not r["dup"]:
                    f.write(f"[{r['bank']:#08x}+{r['ptr']:04x}] {r['speaker_name'] or r['speaker']}: {r['jp']}\n")
    uniq = [r for r in out if not r["dup"]]
    print(f"{len(banks)} scene banks, {len(out)} say commands, {len(uniq)} distinct messages, "
          f"{sum(len(r['jp']) for r in uniq)} characters")
    print("banks:", " ".join(f"{b:#x}({votes[b]})" for b in banks[:60]))


if __name__ == "__main__":
    main(sys.argv)
