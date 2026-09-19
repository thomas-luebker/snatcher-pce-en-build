#!/usr/bin/env python3
"""Check aligned clip pairs by audio: loudness envelopes (50 Hz) of the PCE ADPCM clip and the Sega CD PCM clip.

  clip_verify.py work/audio/clip_align.json work/audio/clip_verify.json

Identical sound effects / jingles correlate near 1 -> anchors that prove (or disprove) the alignment locally.
Speech in two languages does not correlate; for those pairs only the local anchor context counts.
"""
import json
import math
import sys

sys.path.insert(0, "tools")
import okidec  # noqa: E402

WIN = 320                                   # 20 ms at 16 kHz


def envelope(samples):
    out = []
    for i in range(0, len(samples) - WIN + 1, WIN):
        s = samples[i:i + WIN]
        m = sum(s) / WIN
        out.append(math.sqrt(sum((x - m) ** 2 for x in s) / WIN))
    while out and out[-1] < 40:             # strip trailing silence/padding
        out.pop()
    return out


def corr(a, b):
    n = min(len(a), len(b))
    if n < 15:
        return 0.0
    best = -1.0
    for shift in range(-6, 7):              # +-120 ms
        x = a[max(0, shift):][:n - abs(shift)]
        y = b[max(0, -shift):][:n - abs(shift)]
        k = min(len(x), len(y))
        if k < 15:
            continue
        x, y = x[:k], y[:k]
        mx, my = sum(x) / k, sum(y) / k
        sx = math.sqrt(sum((v - mx) ** 2 for v in x)); sy = math.sqrt(sum((v - my) ** 2 for v in y))
        if sx and sy:
            best = max(best, sum((p - mx) * (q - my) for p, q in zip(x, y)) / (sx * sy))
    return best


def main(argv):
    d = json.load(open(argv[1]))
    iso = open("disc/track02.iso", "rb").read()
    pcm = open("segacd/files/PCMLD_01.BIN", "rb").read()
    env_p, env_s = {}, {}

    def pce_env(i):
        if i not in env_p:
            c = d["pce"][i]
            env_p[i] = envelope(okidec.decode(iso[c["lba"] * 2048:(c["lba"] + c["sectors"]) * 2048]))
        return env_p[i]

    def scd_env(j):
        if j not in env_s:
            c = d["scd"][j]
            raw = pcm[c["start"] * 2048:(c["start"] + c["sectors"]) * 2048]
            # 8-bit sign-magnitude, 0xFF = end marker
            sm = [((b & 0x7F) if b & 0x80 else -(b & 0x7F)) * 256 for b in raw if b != 0xFF]
            env_s[j] = envelope(sm)
        return env_s[j]

    out = []
    pairs = [(i, j) for i, j in d["pairs"] if i is not None and j is not None]
    for n, (i, j) in enumerate(pairs):
        a, b = pce_env(i), scd_env(j)
        out.append({"pce": i, "scd": j, "corr": round(corr(a, b), 3),
                    "len_pce": round(len(a) / 50, 2), "len_scd": round(len(b) / 50, 2)})
        if n % 200 == 0:
            print(f"  {n}/{len(pairs)}", flush=True)
    json.dump(out, open(argv[2], "w"), indent=0)
    hi = [o for o in out if o["corr"] >= 0.8]
    print(f"{len(out)} pairs checked; envelope correlation >= 0.8 (same audio): {len(hi)}; "
          f">= 0.6: {sum(1 for o in out if o['corr'] >= 0.6)}; median corr "
          f"{sorted(o['corr'] for o in out)[len(out) // 2]:.2f}")


if __name__ == "__main__":
    main(sys.argv)
