#!/usr/bin/env python3
"""Voice experiments.

  voice_test.py listen [table] [count]   -> work/audio/listen/: WAV pairs (PCE Japanese clip / Sega CD candidate)
                                             for the first clips of a PCE table, plus the next Sega CD clips in order
  voice_test.py patch                    -> swaps the English candidates into build-poc/ for the clips of table 86
                                             (same slot size: truncated with a fade or padded with silence)

The pairing comes from work/audio/clip_align.json (table order + duration only, NOT verified by ear).
"""
import json
import os
import sys

sys.path.insert(0, "tools")
sys.path.insert(0, "tools")
import okidec  # noqa: E402
import okienc  # noqa: E402

SECT = 2048
PCM = "segacd/files/PCMLD_01.BIN"


def scd_samples(pcm, c):
    raw = pcm[c["start"] * SECT:(c["start"] + c["sectors"]) * SECT]
    raw = raw.split(b"\xff")[0]
    return [((b & 0x7F) if b & 0x80 else -(b & 0x7F)) * 256 for b in raw]


def main(argv):
    d = json.load(open("work/audio/clip_align.json"))
    pce, scd = d["pce"], d["scd"]
    partner = {i: j for i, j in d["pairs"] if i is not None and j is not None}
    pcm = open(PCM, "rb").read()
    iso = open("disc/track02.iso", "rb").read()
    if argv[1] == "listen":
        table, count = int(argv[2]) if len(argv) > 2 else 86, int(argv[3]) if len(argv) > 3 else 30
        out = "work/audio/listen"
        os.makedirs(out, exist_ok=True)
        idx = [i for i, c in enumerate(pce) if c["table"] == table][:count]
        lines = []
        for n, i in enumerate(idx):
            c = pce[i]
            okidec.write_wav(f"{out}/{n:02d}_A{c['idx']:03d}_pce_jp.wav", okidec.decode(iso[c["lba"] * SECT:(c["lba"] + c["sectors"]) * SECT]), 16000)
            j = partner.get(i)
            if j is not None:
                okidec.write_wav(f"{out}/{n:02d}_A{c['idx']:03d}_scd_en_entry{scd[j]['entry']:04d}.wav", scd_samples(pcm, scd[j]), 16000)
            lines.append(f"{n:02d}  PCE table {table} A{c['idx']} {c['sec']:.2f}s  <->  "
                         + (f"SCD entry {scd[j]['entry']} {scd[j]['sec']:.2f}s" if j is not None else "no candidate"))
        open(f"{out}/INDEX.txt", "w").write("\n".join(lines) + "\n")
        print(f"{len(idx)} pairs written to {out}/ (see INDEX.txt)")
    elif argv[1] == "patch":
        from cdsector import iso2bin
        N = "Snatcher CD-ROMantic (Japan)"
        isos = {2: bytearray(open("work/poc_track02.iso", "rb").read()) if os.path.exists("work/poc_track02.iso") else None}
        raise SystemExit("patch mode needs the POC ISOs; run tools/poc_scene1.py with VOICE=1 instead")


if __name__ == "__main__":
    main(sys.argv)
