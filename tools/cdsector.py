#!/usr/bin/env python3
"""CD-ROM Mode 1 sector helpers: raw 2352-byte track <-> 2048-byte ISO.

The PC Engine translation tools work on Track 02 as a 2048-byte/sector ISO
(TurboRip layout). Redump sets ship it as a raw 2352-byte .bin with the
3-second pregap (225 sectors) at the start of the file.

  cdsector.py bin2iso  track02.bin  track02.iso
  cdsector.py iso2bin  track02.iso  original-track02.bin  out.bin
  cdsector.py selftest original-track02.bin

iso2bin takes sync/header and the pregap from the original raw track and
regenerates EDC + ECC P/Q (ECMA-130) for every sector. selftest rebuilds the
original track from its own user data and must reproduce it bit for bit.
"""
import sys

PREGAP = 225            # sectors of pregap inside a redump Track 02 .bin
RAW, USER, HDR = 2352, 2048, 16
SYNC = bytes([0] + [255] * 10 + [0])

_edc = [0] * 256
_f = [0] * 256
_b = [0] * 256
for _i in range(256):
    _j = ((_i << 1) ^ (0x11D if _i & 0x80 else 0)) & 0xFF
    _f[_i] = _j
    _b[_i ^ _j] = _i
    _e = _i
    for _ in range(8):
        _e = (_e >> 1) ^ (0xD8018001 if _e & 1 else 0)
    _edc[_i] = _e


def edc(data):
    e = 0
    for x in data:
        e = (e >> 8) ^ _edc[(e ^ x) & 0xFF]
    return e.to_bytes(4, "little")


def _ecc_block(sec, major, minor, mmult, minc, off):
    size = major * minor
    for mj in range(major):
        idx = (mj >> 1) * mmult + (mj & 1)
        a = b = 0
        for _ in range(minor):
            t = sec[12 + idx]
            idx += minc
            if idx >= size:
                idx -= size
            a ^= t
            b ^= t
            a = _f[a]
        a = _b[_f[a] ^ b]
        sec[off + mj] = a
        sec[off + major + mj] = a ^ b


def build_sector(header4, user):
    """Mode 1 sector from a 4-byte header (MSF + mode) and 2048 bytes of data."""
    s = bytearray(RAW)
    s[0:12] = SYNC
    s[12:16] = header4
    s[16:16 + USER] = user
    s[2064:2068] = edc(s[0:2064])
    # Mode 1: the address stays in place for ECC (only Mode 2 zeroes it)
    _ecc_block(s, 86, 24, 2, 86, 2076)
    _ecc_block(s, 52, 43, 86, 88, 2248)
    return bytes(s)


def bin2iso(raw, pregap=PREGAP):
    n = len(raw) // RAW
    return b"".join(raw[i * RAW + HDR:i * RAW + HDR + USER] for i in range(pregap, n))


def iso2bin(iso, original_raw, pregap=PREGAP):
    n = len(original_raw) // RAW
    if len(iso) != (n - pregap) * USER:
        raise SystemExit(f"ISO has {len(iso) // USER} sectors, original track has {n - pregap}")
    out = bytearray(original_raw[:pregap * RAW])
    for k in range(n - pregap):
        i = pregap + k
        out += build_sector(original_raw[i * RAW + 12:i * RAW + 16], iso[k * USER:(k + 1) * USER])
    return bytes(out)


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    cmd = argv[1]
    if cmd == "bin2iso" and len(argv) == 4:
        open(argv[3], "wb").write(bin2iso(open(argv[2], "rb").read()))
    elif cmd == "iso2bin" and len(argv) == 5:
        open(argv[4], "wb").write(iso2bin(open(argv[2], "rb").read(), open(argv[3], "rb").read()))
    elif cmd == "selftest" and len(argv) == 3:
        raw = open(argv[2], "rb").read()
        ok = iso2bin(bin2iso(raw), raw) == raw
        print("selftest:", "OK - original track reproduced bit for bit" if ok else "FAILED")
        sys.exit(0 if ok else 1)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
