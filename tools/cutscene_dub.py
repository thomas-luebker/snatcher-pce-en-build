#!/usr/bin/env python3
"""English speech for the PC Engine's CD-DA cutscenes, laid over the PC Engine's own music.

  work/venv/bin/python tools/cutscene_dub.py analyse [PCE ...]   stems + transcripts (cached in work/cutscene)
  work/venv/bin/python tools/cutscene_dub.py show PCE             both line lists and the alignment
  work/venv/bin/python tools/cutscene_dub.py render [PCE ...]     -> work/cutscene/out/pceNN.wav (listening)
  work/venv/bin/python tools/cutscene_dub.py build [PCE ...]      -> build-en/<track>.bin

Swapping whole tracks cannot work (docs/FINDINGS.md): the two versions use different recordings and
different music, and the pictures are cued to positions inside the PC Engine track. But both versions
speak the same lines in the same order, which transcripts show plainly -- that is the join. So:

1. Demucs splits every track into voice and accompaniment. The PC Engine accompaniment is the new bed
   (right music, right length, right cue positions); the Sega CD voice stem is the English source.
2. Whisper transcribes both voice stems with timestamps (Japanese / English).
3. The English timeline is warped onto the PC Engine one by DTW over the two speech on/off patterns
   (the pictures are the same, so the pauses fall in the same places), and each English line is cut
   out of the Sega CD voice stem and placed where its moment maps to. A line that would run into the
   previous one is pushed back just enough; the schedule catches up in the next pause.

The transcripts ship with the repository (translations/cutscene/*.json): Whisper does not give the same
lines twice, and the pairing in PAIRS/PINS was read off these ones. So a build needs only Demucs:
  python3 -m venv work/venv && work/venv/bin/pip install demucs soundfile
(add mlx-whisper, Apple silicon only, to re-transcribe; delete a transcript to have it redone).
Demucs runs on the Metal GPU on a Mac and on the CPU elsewhere (DEMUCS_DEVICE= overrides).
"""
import json
import os
import re
import subprocess
import sys

import numpy as np
import soundfile as sf

RATE = 44100
SECTOR = 2352
PCE_CUE, PCE_DIR = "disc/Snatcher CD-ROMantic (Japan).cue", "disc"
SCD_DIR = os.environ.get("SCD_RIP", "Snatcher (USA)")
WORK = "work/cutscene"
TRANSCRIPTS = "translations/cutscene"
DEVICE = os.environ.get("DEMUCS_DEVICE", "mps" if sys.platform == "darwin" else "cpu")
OUT = "build-en"
WHISPER = "mlx-community/whisper-large-v3-turbo"

# PC Engine track -> Sega CD source(s) as (track, from_s, to_s); None = whole track.
# Paired by reading both transcripts (work/asr/tracks_view.txt), not by sound.
PAIRS = {
    3: [(6, None, None)],        # Chief's office after Gibson's death
    4: [(7, None, None)],        # Random introduces himself
    5: [(8, None, 134.0)],       # Metal Gear's case recap, part 1 (up to Outer Heaven)
    6: [(8, 134.0, None), (9, None, None)],   # recap part 2, Random's fake data, Little John
    7: [(10, None, None)],       # Queen's Hospital records, Jamie
    8: [(11, None, 77.0)],       # the turbo-cycle jump
    9: [(11, 77.0, None)],       # "Don't bury me so fast"
    10: [(21, None, None)],      # Chin Shu Oh, Random's fireworks
    11: [(12, None, None)],      # Harry's death
    12: [(13, None, None)],      # after the Snatcher, Mika
    13: [(14, None, None)],      # Jamie's video call
    14: [(15, None, None)],      # Mika, dinner at Christmas
    16: [(17, None, 49.5), (19, 29.0, 70.0), (19, 88.0, 125.0)],  # boarding, Metal's temporary body, closing narration
                                                # (Sega CD 17 from 56 s on is Katrina and Mika seeing
                                                # Gillian off, a scene the PC Engine does not have)
    19: [(4, 220.0, 266.0)],     # Gillian's file after the cast roll
    20: [(20, None, None)],      # "Act 1" -- Gibson has cornered a suspect
}

# Stretches of a PC Engine track (s) whose Japanese lines have no English counterpart: the original
# voice stays in rather than leaving the characters silent.
KEEP_JP = {
    16: [(49.0, 75.3)],          # Jamie's farewell and Metal's "wait, take me with you too" -- the Sega CD
                                 # replaced the first with Katrina and Mika and moved the second to the end
}

# Sync points checked by reading both languages: (Sega CD track, source time of the English line's
# start, PC Engine time of the Japanese line it translates). A pinned line starts exactly there; lines
# between pins are shifted by the pins' offsets, interpolated. `show` prints each English line as
# [track:source time], which is what a pin names.
PINS = {
    4: [(7, 24.4, 20.0), (7, 33.1, 25.3), (7, 36.3, 28.2), (7, 39.5, 29.9), (7, 41.8, 31.3), (7, 50.1, 37.8),
        (7, 59.7, 43.5), (7, 71.3, 56.7), (7, 75.9, 61.3), (7, 82.3, 68.1),
        (7, 120.1, 105.3), (7, 129.7, 111.7), (7, 136.5, 117.1), (7, 140.6, 120.8), (7, 145.7, 129.9)],
    5: [(8, 69.0, 74.9), (8, 77.8, 86.6), (8, 113.9, 125.6), (8, 121.0, 132.6), (8, 126.8, 140.1)],
    8: [(11, 2.9, 0.0), (11, 18.6, 13.4), (11, 26.3, 19.0), (11, 37.2, 28.8), (11, 38.2, 29.9),
        (11, 41.3, 32.2), (11, 43.7, 34.1), (11, 47.4, 38.2), (11, 50.1, 40.0), (11, 55.6, 45.1)],
    11: [(12, 3.1, 1.1), (12, 5.2, 5.7), (12, 13.9, 14.2), (12, 16.0, 16.3), (12, 26.2, 30.1), (12, 29.8, 34.3),
         (12, 74.1, 84.2), (12, 83.6, 91.8), (12, 86.8, 96.1), (12, 96.9, 103.7), (12, 103.5, 109.6),
         (12, 108.7, 114.9), (12, 111.2, 117.5), (12, 118.4, 126.2), (12, 121.1, 128.9), (12, 124.6, 131.2),
         (12, 127.8, 135.9), (12, 132.7, 142.3), (12, 136.3, 146.5), (12, 140.4, 152.7), (12, 150.9, 160.2),
         (12, 156.6, 165.6), (12, 159.8, 170.1), (12, 161.8, 172.1), (12, 164.1, 174.4), (12, 165.5, 176.3),
         (12, 167.6, 179.1), (12, 172.5, 187.8),
         (12, 222.9, 240.0), (12, 226.2, 243.2), (12, 228.1, 246.1), (12, 231.6, 253.3)],   # Harry's death
    12: [(13, 8.0, 6.5), (13, 14.7, 10.9), (13, 16.7, 12.8), (13, 25.2, 17.2), (13, 32.9, 25.1),
         (13, 39.7, 30.3), (13, 44.6, 39.2), (13, 51.1, 48.9), (13, 60.6, 61.9), (13, 77.1, 78.6),
         (13, 83.6, 89.1), (13, 91.1, 100.7), (13, 94.2, 103.3), (13, 97.7, 108.0), (13, 100.8, 112.2),
         (13, 105.1, 114.8)],
    14: [(15, 1.7, 1.2), (15, 3.6, 2.3), (15, 4.8, 3.2), (15, 6.8, 4.4), (15, 9.1, 6.4), (15, 11.0, 7.1),
         (15, 16.4, 14.5), (15, 45.6, 45.2), (15, 60.5, 59.1), (15, 61.8, 60.4), (15, 63.7, 61.7), (15, 69.8, 70.5)],
    16: [(19, 30.0, 75.5)],      # "Metal?" answers the Japanese 「お前メタルか?」 after the kept stretch
    19: [(4, 223.6, 143.7), (4, 258.5, 178.6)],   # Gillian's file: the cockpit shot is on screen 148.8-184.3 s,
                                 # then the Junker HQ tower. Unpinned, the English (40 s against the Japanese
                                 # 31 s) ran on over the tower (hardware, 26 Sep: "the audio should end with the video");
                                 # at natural speed ("do not speed it up"), so it starts in the flash before the
                                 # cockpit and ends half a second before the cut
}

# Where the picture the speech belongs to is cut away (s, measured in the emulator). The English has to be
# over by then; render() refuses a track that is not, so a re-pairing cannot quietly push it over again.
SHOT_END = {
    19: 183.8,                   # cockpit -> Junker HQ tower at 184.3, less half a second (hardware, 26 Sep)
}

# Source times (Sega CD track -> seconds) where an utterance must be cut in two: Whisper sometimes
# runs two speakers into one segment, and they then need separate places.
SPLITS = {
    7: [36.3],                   # Metal's "...with the authorities." | Gillian's "You said your name's Random"
}


def track_file(cue, folder, want):
    f = None
    for ln in open(cue, encoding="latin1"):
        m = re.match(r'\s*FILE "(.+)" BINARY', ln)
        if m:
            f = m.group(1)
        m2 = re.match(r"\s*TRACK (\d+)", ln)
        if m2 and f and int(m2.group(1)) == want:
            return os.path.join(folder, f), f
    raise SystemExit(f"track {want} not found in {cue}")


def scd_cue():
    cues = [f for f in os.listdir(SCD_DIR) if f.endswith(".cue")]
    return os.path.join(SCD_DIR, cues[0])


def read_bin(path):
    return np.frombuffer(open(path, "rb").read(), "<i2").reshape(-1, 2).astype(np.float32) / 32768


def stems(name, path):
    """-> (vocals, accompaniment) as float32 stereo arrays at 44.1 kHz, cached."""
    d = os.path.join(WORK, "sep", "htdemucs", name)
    if not os.path.exists(os.path.join(d, "vocals.wav")):
        os.makedirs(WORK, exist_ok=True)
        wav = os.path.join(WORK, name + ".wav")
        sf.write(wav, read_bin(path), RATE, subtype="PCM_16")
        subprocess.run([sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs", "-d", DEVICE,
                        "-o", os.path.join(WORK, "sep"), wav], check=True, capture_output=True)
        os.unlink(wav)
    v, _ = sf.read(os.path.join(d, "vocals.wav"), dtype="float32")
    a, _ = sf.read(os.path.join(d, "no_vocals.wav"), dtype="float32")
    return v, a


def regions(vocals, gap=0.8, most=24.0):
    """Stretches of the voice stem with speech in them, split at pauses, each at most `most` seconds."""
    env = np.sqrt(np.convolve(vocals.mean(1) ** 2, np.ones(2205) / 2205, "same"))[::441]   # 10 ms
    on = env > max(1e-4, np.percentile(env, 99) * 0.04)
    out, k, n = [], 0, len(on)
    while k < n:
        if not on[k]:
            k += 1
            continue
        s0, quiet, e = k, 0, k
        while k < n and quiet < gap * 100 and (k - s0) < most * 100:
            quiet = 0 if on[k] else quiet + 1
            e = k if on[k] else e
            k += 1
        out.append((max(0, s0 / 100 - 0.3), e / 100 + 0.3))
    return out


def transcribe(name, vocals, lang):
    """Line list [{t0, t1, text}] of a voice stem, cached.

    Whisper is run on each speech region of the stem on its own rather than on the whole track: over a
    stretch of music it fills a 30-second window with a stock phrase ("The End", "Thank you.") and loses
    the lines inside it, which dropped the opening lines of several Sega CD cutscenes. Short regions
    also give tighter timestamps. Word timestamps give the line edges.
    """
    path = os.path.join(TRANSCRIPTS, name + f".{lang}.json")
    if os.path.exists(path):
        return json.load(open(path))
    import mlx_whisper
    mono = vocals.mean(1)
    lines = []
    for r0, r1 in regions(vocals):
        seg = mono[int(r0 * RATE):int(r1 * RATE)]
        n = int(len(seg) * 16000 / RATE)
        x = np.interp(np.arange(n) * RATE / 16000, np.arange(len(seg)), seg).astype(np.float32)
        r = mlx_whisper.transcribe(x, path_or_hf_repo=WHISPER, language=lang, word_timestamps=True,
                                   condition_on_previous_text=False)
        for s in r["segments"]:
            words = [w for w in (s.get("words") or []) if w["end"] > w["start"]]
            if s["no_speech_prob"] > 0.6 or not words or STOCK.search(s["text"]):
                continue
            lines.append({"t0": round(r0 + words[0]["start"], 2), "t1": round(r0 + words[-1]["end"], 2),
                          "text": s["text"].strip()})
    lines = speech_only(lines, vocals)
    json.dump(lines, open(path, "w"), ensure_ascii=False, indent=0)
    return lines


# What Whisper writes over music or silence instead of admitting there is no speech.
STOCK = re.compile(r"^\s*(The End\.?|Thank you\.?|We'll be right back\.?|To be continued\.*|I love you\.?|"
                   r"ご視聴ありがとうございました|音楽|BGM)\s*$", re.I)


def speech_only(lines, vocals):
    """Drop Whisper's hallucinations: a 'line' over a stretch where the voice stem is near silent."""
    env = np.sqrt(np.convolve((vocals.mean(1) ** 2), np.ones(2205) / 2205, "same"))
    floor = max(1e-4, np.percentile(env, 99) * 0.05)
    keep = []
    for ln in lines:
        seg = env[int(ln["t0"] * RATE):int(ln["t1"] * RATE)]
        words = ln["text"].split()
        junk = len(words) >= 2 and len(set(w.lower().strip(".,!?") for w in words)) <= max(1, len(words) // 3)
        junk |= not re.search(r"[A-Za-z]{2}|[\u3040-\u30ff\u4e00-\u9fff]", ln["text"])   # "ós", "..."
        if len(seg) and (seg > floor).mean() > 0.25 and ln["t1"] - ln["t0"] < 25 and not junk:
            keep.append(ln)
    return keep


def analyse(pce):
    pce_path, _ = track_file(PCE_CUE, PCE_DIR, pce)
    pv, pa = stems(f"pce{pce:02d}", pce_path)
    jp = transcribe(f"pce{pce:02d}", pv, "ja")
    en = []
    for t, a, b in PAIRS[pce]:
        sv, _ = stems(f"scd{t:02d}", track_file(scd_cue(), SCD_DIR, t)[0])
        for ln in transcribe(f"scd{t:02d}", sv, "en"):
            if (a is None or ln["t0"] >= a) and (b is None or ln["t0"] < b):
                en.append(dict(ln, src=t))
    return pv, pa, jp, en


STEP = 0.1                                           # warp resolution, seconds


# Words that survive translation: names, places, numbers. A Japanese and an English line that share
# one are very probably the same line, which is what keeps the warp from sliding a block of dialogue
# past its partner where the speech rhythm alone is ambiguous.
ANCHORS = {
    "random": ["ランダム"], "gibson": ["ギブスン", "ギブソン"], "gillian": ["ギリアン", "ギリア", "イリアン"],
    "metal": ["メタル", "メダル"], "harry": ["ハリー", "親父"], "jamie": ["ジェミ", "ジェミー"],
    "mika": ["ミカ"], "cunningham": ["カニンガム"], "chief": ["局長"], "freddy": ["フレディ"],
    "lisa": ["リサ"], "ivan": ["イワン"], "isabella": ["イザベラ"], "jordan": ["ガウディ"],
    "snatcher": ["スナッチャー"], "junker": ["ジャンカー"], "bounty": ["バウンティー", "バウンディー"],
    "hospital": ["病院"], "queen": ["クイーン"], "kremlin": ["クレムリン"], "summit": ["サミット"],
    "kyoto": ["京都"], "lorraine": ["ロレイン", "ロレン"], "modnar": ["マッドナー", "マッドな"],
    "chin": ["陳", "ジン"], "qin": ["陳", "ジン"], "skin": ["皮膚"], "ultraviolet": ["紫外線"], "christmas": ["クリスマス"],
    "memory": ["記憶"], "fireworks": ["花火"], "seed": ["シード"], "little john": ["リトルジョン"],
    "outer heaven": ["アウターヘブン"], "phase": ["第二段階", "レベル2"], "blaster": ["ブラスター"],
    "dinner": ["食事"], "moscow": ["モスクワ"], "lucifer": ["ルシファー"],
}


def terms(ln):
    """Anchor words in a line (English or Japanese), plus any number written in digits."""
    t = ln["text"]
    low = t.lower()
    out = {k for k, jps in ANCHORS.items() if k in low or any(j in t for j in jps)}
    out |= {n.lstrip("0") for n in re.findall(r"\d{2,}", t.replace("-", ""))}
    return out


def frames(lines, length):
    """Per STEP: index of the line speaking, or -1."""
    x = np.full(int(length / STEP) + 1, -1, np.int32)
    for k, ln in enumerate(lines):
        x[int(ln["t0"] / STEP):int(ln["t1"] / STEP) + 1] = k
    return x


def warp(jp, en, jp_len, en_len, band=15.0):
    """Map English time -> PC Engine time: DTW over the two speech patterns, steered by anchor words.

    The pictures are the same in both versions, so the pauses between exchanges fall in the same
    places even where the sentences inside them differ in length. Speech against silence costs 1;
    speech against speech costs nothing when the two lines share an anchor word, 0.8 when both have
    anchors but none in common (almost certainly different lines), 0.3 otherwise. The path stays inside
    a band around the straight line from start to end, and runs that hold one side still cost extra so
    the warp stays close to real time.
    """
    J, E = frames(jp, jp_len), frames(en, en_len)
    jt, et = [terms(x) for x in jp], [terms(x) for x in en]
    sim = np.full((len(jp) + 1, len(en) + 1), 0.3, np.float32)
    for a, ta in enumerate(jt):
        for b, tb in enumerate(et):
            if ta and tb:
                sim[a, b] = 0.0 if ta & tb else 0.8
    n, m = len(J), len(E)
    w = int(band / STEP)
    INF = 1e18
    D = np.full((n + 1, m + 1), INF)
    D[0, 0] = 0
    step = np.zeros((n + 1, m + 1), np.int8)
    # centre line of the band: the Japanese speech span mapped linearly onto the English one, so a
    # cutscene whose speech starts late in one version (a long music intro) is still searched sensibly
    ja, jb = jp[0]["t0"] / STEP, max(x["t1"] for x in jp) / STEP
    ea, eb = en[0]["t0"] / STEP, max(x["t1"] for x in en) / STEP
    scale = (eb - ea) / max(1.0, jb - ja)
    for i in range(1, n + 1):
        c = ea + (i - ja) * scale
        lo, hi = max(1, int(c - w)), min(m, int(c + w))
        if lo > hi:                                   # outside the band on this row: allow the edge
            lo, hi = (1, 1) if c < 1 else (m, m)
        ji = J[i - 1]
        for j in range(lo, hi + 1):
            ej = E[j - 1]
            d = 0.0 if ji < 0 and ej < 0 else 1.0 if (ji < 0) != (ej < 0) else sim[ji, ej]
            opts = (D[i - 1, j - 1], D[i - 1, j] + 0.15, D[i, j - 1] + 0.15)
            k = int(np.argmin(opts))
            D[i, j] = d + opts[k]
            step[i, j] = k
    i, j, path = n, m, []
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        k = step[i, j]
        i, j = (i - 1, j - 1) if k == 0 else (i - 1, j) if k == 1 else (i, j - 1)
    path.reverse()
    en_to_jp = np.zeros(m)
    for pi, pj in path:
        en_to_jp[pj] = pi * STEP                      # last (latest) PC Engine point wins
    return lambda t: float(en_to_jp[min(m - 1, max(0, int(t / STEP)))])


def utterances(lines):
    """Clean up a transcript for cutting: no line may start before the previous one ended (chunk edges
    overlap, and Whisper then hears a word twice), and lines that run on without a real pause are one
    utterance -- cutting between them would only lose the speaker's own timing."""
    out = []
    for ln in lines:
        ln = dict(ln)
        if out and ln["t0"] < out[-1]["t1"]:
            ln["t0"] = out[-1]["t1"]
        if ln["t1"] - ln["t0"] < 0.15:
            continue
        if out and ln["t0"] - out[-1]["t1"] < 0.3:
            out[-1]["t1"], out[-1]["text"] = ln["t1"], out[-1]["text"] + " " + ln["text"]
        else:
            out.append(ln)
    return out


def en_timeline(pce):
    """Concatenate the Sega CD source ranges into one English timeline -> (lines, length, [(src, from, to, at)])."""
    lines, parts, at = [], [], 0.0
    for t, a, b in PAIRS[pce]:
        allen = utterances(json.load(open(os.path.join(TRANSCRIPTS, f"scd{t:02d}.en.json"))))
        a = a or 0.0
        b = b or stems(f"scd{t:02d}", track_file(scd_cue(), SCD_DIR, t)[0])[0].shape[0] / RATE
        for cut_at in SPLITS.get(t, []):
            for k, ln in enumerate(allen):
                if ln["t0"] + 0.3 < cut_at < ln["t1"] - 0.3:
                    allen[k:k + 1] = [dict(ln, t1=cut_at - 0.05, text=ln["text"] + " |1"),
                                     dict(ln, t0=cut_at, text=ln["text"] + " |2")]
                    break
        for ln in allen:
            if a <= ln["t0"] < b:
                lines.append(dict(ln, src=t, st0=ln["t0"], t0=ln["t0"] - a + at, t1=ln["t1"] - a + at))
        parts.append((t, a, b, at))
        at += b - a
    return lines, at, parts


MAX_SPEED = 1.2                                      # fastest an English line may be played to fit
MAX_SPEED_FOR = {19: 1.0}                            # Gillian's file: never faster (Thomas, 26 Sep)


def schedule(pce, jp, jp_len):
    """-> [(en_line, place_at_s, speed)].

    Each English line goes where its moment maps to (warp, corrected between pins); a pinned line goes
    exactly to its pin. Pins are fixed: the lines from one pin up to the next are laid out one after
    another, and if they do not fit before the next pin (or the end of the track) they are played
    faster, up to MAX_SPEED, time-stretched without changing pitch. Only beyond that do they overlap.
    Stretches that stay Japanese (KEEP_JP) are stepped over.
    """
    en, en_len, _ = en_timeline(pce)
    keep = KEEP_JP.get(pce, [])
    inside = lambda t0, t1: next(((a, b) for a, b in keep if t0 < b and t1 > a), None)
    jp = [x for x in jp if not inside(x["t0"], x["t1"])]        # those lines stay Japanese
    f = warp(jp, en, jp_len, en_len)
    GAP, TAIL = 0.12, 0.3
    pins = {}
    for src, st, to in PINS.get(pce, []):
        k = min((k for k, ln in enumerate(en) if ln["src"] == src), key=lambda k: abs(en[k]["st0"] - st))
        pins[k] = to
    px = sorted(pins)
    # Between pins the warp is corrected by the pins' own offsets, interpolated along the English
    # timeline; outside the first and last pin the warp stands as it is.
    fix = (lambda t: float(np.interp(t, [en[k]["t0"] for k in px], [pins[k] - f(en[k]["t0"]) for k in px],
                                     left=0.0, right=0.0))) if px else (lambda t: 0.0)
    want = [pins[k] if k in pins else f(ln["t0"]) + fix(ln["t0"]) for k, ln in enumerate(en)]
    bounds = sorted(set([0] + px + [len(en)]))
    at, speed = [0.0] * len(en), [1.0] * len(en)
    for s0, s1 in zip(bounds, bounds[1:]):
        limit = (pins[s1] if s1 in pins else jp_len + TAIL) - TAIL + (TAIL - GAP if s1 in pins else 0)
        start = want[s0]
        for r in np.arange(1.0, MAX_SPEED_FOR.get(pce, MAX_SPEED) + 1e-9, 0.02):
            free, pos = -1.0, []
            for k in range(s0, s1):
                dur = (en[k]["t1"] - en[k]["t0"]) / r
                t = start if k == s0 and k in pins else max(start + (want[k] - start) / r, free + GAP)
                while inside(t, t + dur):
                    t = inside(t, t + dur)[1] + GAP
                pos.append(t)
                free = t + dur
            if free <= limit:
                break
        for i, k in enumerate(range(s0, s1)):
            at[k], speed[k] = max(0.0, pos[i]), float(r)
    return [(ln, at[k], speed[k]) for k, ln in enumerate(en)]


def stretch(x, rate):
    """Play stereo speech `rate` times faster without changing its pitch (WSOLA: 40 ms grains,
    overlap-added at the position within +-10 ms that best continues the output)."""
    if abs(rate - 1) < 0.01:
        return x
    n, hop = int(0.04 * RATE), int(0.02 * RATE)
    tol = int(0.01 * RATE)
    win = np.hanning(n).astype(np.float32)[:, None]
    out_len = int(len(x) / rate)
    out = np.zeros((out_len + n, x.shape[1]), np.float32)
    norm = np.zeros((out_len + n, 1), np.float32)
    prev = None
    for o in range(0, out_len, hop):
        c = int(o * rate)
        if prev is not None:
            ref = x[prev + hop:prev + hop + n].mean(1)
            best, bi = -1e9, 0
            for d in range(-tol, tol + 1, 4):
                s = c + d
                if 0 <= s and s + n <= len(x) and len(ref) == n:
                    v = float(np.dot(ref, x[s:s + n].mean(1)))
                    if v > best:
                        best, bi = v, d
            c += bi
        c = min(max(0, c), max(0, len(x) - n))
        g = x[c:c + n]
        out[o:o + len(g)] += g * win[:len(g)]
        norm[o:o + len(g)] += win[:len(g)]
        prev = c
    return out[:out_len] / np.maximum(norm[:out_len], 1e-3)


def cut(stem, t0, t1, pad=0.12):
    a, b = max(0, int((t0 - pad) * RATE)), min(len(stem), int((t1 + pad) * RATE))
    x = stem[a:b].copy()
    f = min(int(0.03 * RATE), len(x) // 2)
    ramp = np.linspace(0, 1, f, dtype=np.float32)[:, None]
    x[:f] *= ramp
    x[len(x) - f:] *= ramp[::-1]
    return x


def render(pce):
    pv, pa, jp, _ = analyse(pce)
    jp_len = len(pa) / RATE
    sched = schedule(pce, jp, jp_len)
    src = {t: stems(f"scd{t:02d}", track_file(scd_cue(), SCD_DIR, t)[0])[0] for t, _, _ in PAIRS[pce]}
    out = pa.copy()
    for k0, k1 in KEEP_JP.get(pce, []):
        a, b = int(k0 * RATE), int(k1 * RATE)
        out[a:b] += pv[a:b]
    gain = rms_speech(pv) / max(1e-6, rms_speech(np.concatenate(list(src.values()))))
    late = []
    for ln, at, sp in sched:
        clip = stretch(cut(src[ln["src"]], ln["st0"], ln["st0"] + ln["t1"] - ln["t0"]), sp) * gain
        a = int((at - 0.12) * RATE)
        if a < 0:
            clip, a = clip[-a:], 0
        b = min(len(out), a + len(clip))
        out[a:b] += clip[:b - a]
        if a + len(clip) > len(out):
            late.append(ln["text"])
    peak = np.abs(out).max()
    if peak > 0.99:
        out *= 0.99 / peak
    os.makedirs(os.path.join(WORK, "out"), exist_ok=True)
    sf.write(os.path.join(WORK, "out", f"pce{pce:02d}.wav"), out, RATE, subtype="PCM_16")
    ends = [at + (ln["t1"] - ln["t0"]) / sp for ln, at, sp in sched]
    if pce in SHOT_END and max(ends) > SHOT_END[pce]:
        raise SystemExit(f"PCE {pce}: the English runs to {max(ends):.1f} s, past the cut at {SHOT_END[pce]} s")
    overlaps = [round(ends[k] - sched[k + 1][1], 1) for k in range(len(sched) - 1) if ends[k] > sched[k + 1][1] + 0.05]
    fast = [sp for _, _, sp in sched if sp > 1.001]
    print(f"PCE {pce:2d}: {len(jp):3d} JP / {len(sched):3d} EN lines, {len(PINS.get(pce, []))} pins; "
          f"{len(fast)} sped up (max x{max(fast or [1]):.2f}); overlaps {overlaps or 'none'}"
          + (f"; {len(late)} RUN PAST THE END" if late else ""))
    return out


def rms_speech(v):
    m = v.mean(1)
    env = np.sqrt(np.convolve(m ** 2, np.ones(4410) / 4410, "same"))
    loud = env[env > np.percentile(env, 99) * 0.2]
    return float(np.sqrt((loud ** 2).mean())) if len(loud) else 1e-6


def show(pce):
    """Both languages on the PC Engine timeline: Japanese where it was, English where it will go."""
    _, pa, jp, _ = analyse(pce)
    rows = [(x["t0"], x["t1"], "JP", x["text"]) for x in jp]
    rows += [(at, at + (ln["t1"] - ln["t0"]) / sp, f"EN [{ln['src']}:{ln['st0']:.1f}]" + (f" x{sp:.2f}" if sp > 1 else ""), ln["text"])
             for ln, at, sp in schedule(pce, jp, len(pa) / RATE)]
    for t0, t1, k, text in sorted(rows):
        print(f"{t0:6.1f}-{t1:6.1f} {k} {text[:90]}")


def build(pce):
    out = render(pce)
    pce_path, pce_name = track_file(PCE_CUE, PCE_DIR, pce)
    n = os.path.getsize(pce_path) // 4
    pcm = (np.clip(out[:n], -1, 1) * 32767).astype("<i2").tobytes().ljust(n * 4, b"\0")
    assert len(pcm) % SECTOR == 0
    dst = os.path.join(OUT, pce_name)
    if os.path.islink(dst):
        os.unlink(dst)
    open(dst, "wb").write(pcm)
    print(f"  wrote {dst}")


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    cmd, which = argv[0], [int(a) for a in argv[1:]] or sorted(PAIRS)
    for p in which:
        {"analyse": analyse, "show": show, "render": render, "build": build}[cmd](p)


if __name__ == "__main__":
    main(sys.argv[1:])
