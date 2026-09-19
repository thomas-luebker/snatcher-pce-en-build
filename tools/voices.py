#!/usr/bin/env python3
"""Swap the Sega CD English voice clips into the PC Engine clip slots (all tables).

Pairing: work/audio/clip_align.json (table order + duration; confirmed by ear only for the first lines).
A slot keeps its size and place. If the English take is longer than the slot holds at 16 kHz, it is
encoded at a lower ADPCM rate (rate byte of the table entry: 14 = 16 kHz, 13 = 10.7 kHz, 12 = 8 kHz) so the
whole line still fits; only if even 8 kHz is too short is it cut with a fade. The rate byte is patched in
every table copy (sectors 86..106 and the boot copy of table 86 at sector 54).
"""
import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import okienc  # noqa: E402

SECT = 2048
RATES = [(14, 16000), (13, 32000 / 3), (12, 8000)]
TABLES = [86, 90, 94, 98, 102, 106]
BOOT_COPY = {86: 54}


def scd_samples(pcm, c):
    raw = pcm[c["start"] * SECT:(c["start"] + c["sectors"]) * SECT].split(b"\xff")[0]
    return [((b & 0x7F) if b & 0x80 else -(b & 0x7F)) * 256 for b in raw]


def resample(s, src, dst):
    if dst >= src:
        return s
    step, out, pos = src / dst, [], 0.0
    while pos < len(s) - 1:
        a, b = int(pos), min(len(s), int(pos + step) + 1)
        out.append(sum(s[a:b]) // (b - a))                 # box filter: crude low-pass + decimation
        pos += step
    return out


def apply(isos, limit=None):
    d = json.load(open("work/audio/clip_align.json"))
    pcm = open("segacd/files/PCMLD_01.BIN", "rb").read()
    original = bytes(isos[2])
    partner = {i: j for i, j in d["pairs"] if i is not None and j is not None}
    done, rates, cut, cache = 0, {14: 0, 13: 0, 12: 0}, 0, {}
    for i, c in enumerate(d["pce"]):
        if i not in partner or (limit is not None and done >= limit):
            continue
        size, off = c["sectors"] * SECT, c["lba"] * SECT
        if off not in cache:
            src = scd_samples(pcm, d["scd"][partner[i]])
            for code, hz in RATES:
                smp = resample(src, 16000, hz)
                if len(smp) <= size * 2:
                    break
            else:
                smp = smp[:size * 2]
                fade = min(600, len(smp))
                smp[-fade:] = [int(v * (fade - k) / fade) for k, v in enumerate(smp[-fade:])]
                cut += 1
            data = okienc.encode(smp)[:size].ljust(size, b"\x88")
            old = original[off:off + size]
            for t in isos:
                if bytes(isos[t][off:off + size]) == old:
                    isos[t][off:off + size] = data
            cache[off] = code
            rates[code] += 1
        code = cache[off]
        for ts in [c["table"]] + ([BOOT_COPY[c["table"]]] if c["table"] in BOOT_COPY else []):
            e = ts * SECT + (c["idx"] - 1) * 8
            for t in isos:
                if isos[t][e + 2:e + 7] == original[c["table"] * SECT + (c["idx"] - 1) * 8 + 2:][:5]:
                    isos[t][e + 7] = code
        done += 1
    return f"voices: {done} table entries, {len(cache)} clips re-encoded (16 kHz: {rates[14]}, 10.7 kHz: {rates[13]}, 8 kHz: {rates[12]}, cut: {cut})"


if __name__ == "__main__":
    isos = {2: bytearray(open("disc/track02.iso", "rb").read())}
    print(apply(isos, int(sys.argv[1]) if len(sys.argv) > 1 else None))
