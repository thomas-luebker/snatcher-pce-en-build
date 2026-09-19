#!/usr/bin/env python3
"""Merge a multi-bin cue (one FILE per track, redump style) into a single bin + cue.

  binmerge.py "build/Dead of the Brain 1&2 (Japan).cue" build-single "Dead of the Brain 2 (English TEST)"

Track files are concatenated in order; every INDEX time is shifted by the
sectors that precede its file in the merged image. All tracks are 2352 bytes
per sector (AUDIO and MODE1/2352).
"""
import os
import re
import sys

SECTOR = 2352


def msf(frames):
    return f"{frames // 4500:02d}:{frames // 75 % 60:02d}:{frames % 75:02d}"


def main(argv):
    if len(argv) != 4:
        raise SystemExit(__doc__)
    cue, outdir, name = argv[1], argv[2], argv[3]
    src = os.path.dirname(cue)
    os.makedirs(outdir, exist_ok=True)
    lines, offset = [f'FILE "{name}.bin" BINARY'], 0
    with open(os.path.join(outdir, name + ".bin"), "wb") as out:
        for line in open(cue):
            m = re.match(r'\s*FILE "(.+)" BINARY', line)
            if m:
                path = os.path.join(src, m.group(1))
                size = os.path.getsize(path)
                assert size % SECTOR == 0, path
                base = offset                       # frames before this file
                with open(path, "rb") as f:
                    while chunk := f.read(1 << 22):
                        out.write(chunk)
                offset += size // SECTOR
                continue
            m = re.match(r"(\s*INDEX \d\d) (\d\d):(\d\d):(\d\d)", line)
            if m:
                frames = (int(m.group(2)) * 60 + int(m.group(3))) * 75 + int(m.group(4))
                lines.append(f"{m.group(1)} {msf(base + frames)}")
            elif line.strip().startswith("TRACK"):
                assert "AUDIO" in line or "MODE1/2352" in line, line
                lines.append(line.rstrip())
            # CATALOG and anything else is dropped
    open(os.path.join(outdir, name + ".cue"), "w").write("\n".join(lines) + "\n")
    print(f"{name}.bin: {offset} sectors, {offset * SECTOR} bytes, {sum(1 for l in lines if 'TRACK' in l)} tracks")


if __name__ == "__main__":
    main(sys.argv)
