#!/usr/bin/env python3
"""Swap the Sega CD English voice clips into the PC Engine clip slots (all tables).

Pairing: translations/clip_align.json (made by tools/clip_align.py, then re-paired by meaning with
tools/clip_pair.py and clip_stray.py; ships with the repository because Whisper output is not reproducible).
A slot keeps its size and place. If the English take is longer than the slot holds at 16 kHz, it is
encoded at a lower ADPCM rate (rate byte of the table entry: 14 = 16 kHz, 13 = 10.7 kHz, 12 = 8 kHz) so the
whole line still fits; only if even 8 kHz is too short is it cut with a fade. The rate byte is patched in
every table copy (sectors 86..106 and the boot copy of table 86 at sector 54).
"""
import json
import os
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import okienc  # noqa: E402

SECT = 2048
RATES = [(14, 16000), (13, 32000 / 3), (12, 8000)]
TABLES = [86, 90, 94, 98, 102, 106]
BOOT_COPY = {86: 54}


def take_samples(pcm, d, take):
    """A take, or a slice of one: "515:0-3.2" is seconds 0-3.2 of take 515 -- Konami sometimes recorded two of
    the PC Engine's lines as one (Random's and Metal's at the top of Queen's basement stairs, 24 Sep)."""
    if isinstance(take, int):
        return scd_samples(pcm, d["scd"][take])
    j, rng = take.split(":")
    a, b = rng.split("-")
    smp = scd_samples(pcm, d["scd"][int(j)])
    return smp[int(float(a) * 16000):int(float(b) * 16000) if b else None]


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


def edges(smp, hz, room):
    """Start and end a clip the way the original ones do: quiet. The clip data is padded with $88, which
    keeps the decoder near silence, but the clip still has to arrive there: a fade and a moment of real
    silence let the encoder's step size decay first, so the handover is inaudible."""
    n = len(smp)
    fi, fo = int(0.005 * hz), int(0.03 * hz)
    for k in range(min(fi, n)):
        smp[k] = int(smp[k] * k / fi)
    for k in range(min(fo, n)):
        smp[n - 1 - k] = int(smp[n - 1 - k] * k / fo)
    return smp + [0] * max(0, min(int(0.08 * hz), room - n))


FIXUPS = "translations/clip_fixups.tsv"
# The pairing ships with the repository. An old work/audio/clip_align.json (the order-only pairing the first
# public build made) is deliberately NOT read: it is the pairing that left whole scenes Japanese on hardware.
ALIGN = "translations/clip_align.json"
SCD_FILES = os.environ.get("SCD_FILES", "segacd/files")     # your Sega CD data-track files (PCMLD_01.BIN)


def fixups(d):
    """Pairs settled by hand: a lone Japanese line in an English scene, whose English runs long.

    The aligner refuses a take more than about 15% longer than the slot, which is right in general --
    a wrong pair is worse than a Japanese one -- but it leaves these stranded among English voices.
    They are listed by table and clip number, and squeezed to fit rather than cut.
    """
    if not os.path.exists(FIXUPS):
        return 0
    where = {(c["table"], c["idx"]): i for i, c in enumerate(d["pce"])}
    n = 0
    for line in open(FIXUPS, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        table, idx, scd = line.split("\t")[:3]
        table, idx = int(table), int(idx)
        scd = int(scd) if ":" not in scd else scd          # "515:0-3.2" = seconds 0-3.2 of take 515, see take_samples
        i = where.get((table, idx))
        if i is None:
            continue
        # A hand pair wins: it replaces whatever the aligner gave this clip (the three Napoleon clips that
        # held Oleen Hospital's takes, 23 Sep), and it may reuse a take another clip already plays -- the
        # game itself repeats lines between scenes (the HQ emergency call), and each slot gets its own copy.
        d["pairs"] = [[a, b] for a, b in d["pairs"] if a != i]
        d["pairs"].append([i, scd])
        d.setdefault("hand", set()).add(i)
        n += 1
    return n


SHARED = 4


def sound_effects(d, iso):
    """Clips that are the game's shared sound-effect bank, not speech: entries 12-18 and 22-25 of every table
    hold the same eleven recordings, byte for byte. No line of speech repeats that often (three at most), so
    a Japanese clip found SHARED or more times is a sound effect and is never replaced. Paired anyway, one
    take was copied over every copy -- "Gillian, behind you!" over the Act 1 title card (26 Sep)."""
    seen = {}
    for i, c in enumerate(d["pce"]):
        seen.setdefault(iso[c["lba"] * SECT:(c["lba"] + c["sectors"]) * SECT], []).append(i)
    return {i for g in seen.values() if len(g) >= SHARED for i in g}


def drop_sound_effects(d, iso):
    """Drop the pairs on the shared sound effects, and let a hand pair speak for every byte-identical copy of
    its Japanese: the copies step writes a take over every copy, so an aligner pair on a copy would silently
    undo the hand pair (Jamie's voicemail, 94/217, is the same recording as 90/174). -> real pairs dropped."""
    sfx = sound_effects(d, iso)
    clip = lambda i: iso[d["pce"][i]["lba"] * SECT:(d["pce"][i]["lba"] + d["pce"][i]["sectors"]) * SECT]
    handed = {clip(i) for i in d.get("hand", ())}
    real = lambda p: p[0] is not None and p[1] is not None
    before = sum(map(real, d["pairs"]))
    d["pairs"] = [[a, b] for a, b in d["pairs"]
                  if a not in sfx and (a is None or a in d.get("hand", ()) or clip(a) not in handed)]
    return before - sum(map(real, d["pairs"]))


def squeeze(smp, factor, hz):
    """Speed speech up by `factor` without dropping its end: overlap-add, 30 ms windows."""
    if factor <= 1.0:
        return smp
    win = max(64, int(0.030 * hz))
    half = win // 2
    step = int(half * factor)
    out = []
    pos = 0
    while pos + win < len(smp):
        head = smp[pos:pos + half]
        if out:
            for k in range(half):                      # cross-fade into what is already there
                w = k / half
                out[len(out) - half + k] = int(out[len(out) - half + k] * (1 - w) + head[k] * w)
            out.extend(smp[pos + half:pos + win])
        else:
            out.extend(smp[pos:pos + win])
        pos += step
    out.extend(smp[pos:])
    return out


def apply(isos, limit=None):
    d = json.load(open(ALIGN))
    fixed = fixups(d)
    pcm = open(os.path.join(SCD_FILES, "PCMLD_01.BIN"), "rb").read()
    original = bytes(isos[2])
    sfx = drop_sound_effects(d, original)
    originals = {t: bytes(iso) for t, iso in isos.items()}      # pristine copies to search: the tracks change as we go
    partner = {i: j for i, j in d["pairs"] if i is not None and j is not None}
    copies = 0
    done, rates, cut, squeezed, cache = 0, {14: 0, 13: 0, 12: 0}, 0, 0, {}
    for i, c in enumerate(d["pce"]):
        if i not in partner or (limit is not None and done >= limit):
            continue
        size, off = c["sectors"] * SECT, c["lba"] * SECT
        if off not in cache:
            src = take_samples(pcm, d, partner[i])
            for code, hz in RATES:
                smp = resample(src, 16000, hz)
                if len(smp) <= size * 2:
                    break
            else:
                over = len(smp) / (size * 2)
                if over <= 1.6:                        # speed it up rather than lose the end of it
                    smp = squeeze(smp, over * 1.02, hz)[:size * 2]
                    squeezed += 1
                else:
                    smp = smp[:size * 2]
                    fade = min(600, len(smp))
                    smp[-fade:] = [int(v * (fade - k) / fade) for k, v in enumerate(smp[-fade:])]
                    cut += 1
            data = okienc.encode(edges(smp, hz, size * 2), pad=b"\x08")[:size].ljust(size, b"\x08")
            old = original[off:off + size]
            # Every copy of the clip, on both tracks. Track 24 carries the speech a second time and 244 clips
            # sit at another offset there -- and the EverDrive serves the last data track, so a copy left
            # alone is what the console plays (24 Sep: a whole scene Japanese in front of Queen's Hospital).
            for t in isos:
                src, at = originals[t], 0
                while True:
                    at = src.find(old[:64], at)
                    if at < 0:
                        break
                    if src[at:at + size] == old:
                        isos[t][at:at + size] = data
                        if at != off:
                            copies += 1
                    at += 1
            cache[off] = code
            rates[code] += 1
        code = cache[off]
        for ts in [c["table"]] + ([BOOT_COPY[c["table"]]] if c["table"] in BOOT_COPY else []):
            e = ts * SECT + (c["idx"] - 1) * 8
            for t in isos:
                if isos[t][e + 2:e + 7] == original[c["table"] * SECT + (c["idx"] - 1) * 8 + 2:][:5]:
                    isos[t][e + 7] = code
        done += 1
    return (f"voices: {done} table entries, {len(cache)} clips re-encoded (16 kHz: {rates[14]}, "
            f"10.7 kHz: {rates[13]}, 8 kHz: {rates[12]}, squeezed to fit: {squeezed}, cut: {cut}); "
            f"{fixed} pairs from {os.path.basename(FIXUPS)}; {copies} copies at other offsets replaced too; "
            f"{sfx} pairs dropped (shared sound effects, copies of a hand pair)")


if __name__ == "__main__":
    isos = {2: bytearray(open("disc/track02.iso", "rb").read())}
    print(apply(isos, int(sys.argv[1]) if len(sys.argv) > 1 else None))
