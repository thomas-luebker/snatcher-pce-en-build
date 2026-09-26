#!/usr/bin/env python3
"""Refuse to let a built image reach the card with a fault we have already met.

  verify_build.py [--emu]        exit 0 = clean, 1 = something below failed (each failure is printed)

Every check here is a regression that was found by playing the game on the PC Engine -- an hour or
more of someone's evening per find. The point of this file is that none of them has to be found twice.
Static checks read the built data tracks; --emu adds a cold boot in the emulator (about a minute).

  build report    build-en/report.txt (build.sh writes it): no scene or copy over budget, no copy left
                  Japanese, no menu word cut off, no untypeable answer, no untranslated scene, and the
                  voice step ran -- a bare build_all once shipped every spoken line Japanese
  audio tracks    tracks 03-20 are real files, not links back to the Japanese originals
  both tracks     every table-named scene is patched identically on track 02 and track 24
  scene copies    every real copy of every scene carries English menu words, not the Japanese ones
                  (Outer Heaven's entrance, the J-Division street)
  menu words      no scene's word list still holds its Japanese word, except data (digits, ★, ☆) and
                  the fallback of a typed-answer tree, which must stay Japanese
  typed answers   every word field is ten, every fallback selects a keyboard, every entry is stored
                  as full-width Latin (Napoleon's "Way off!")
  keypad          the digit keypad grid is byte-identical to Konami's; the letter grid has walls where
                  the original has walls, A-Z, and nothing typable that is not a letter or a function key
  title           the hook and the stub are in place and the patterns are in the title's load
  door quiz       the digit answers are untouched
  text            tools/verify_text.py: every message decodes and terminates (the hang)
"""
import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import answers        # noqa: E402
import cdsector as C  # noqa: E402
import keyboard       # noqa: E402
import sncells        # noqa: E402
import title_patch    # noqa: E402

N = "Snatcher CD-ROMantic (Japan)"
VOICES_AT_LEAST = 1106                        # what the pairing reaches today; it may only go up
fails = []
skips = []


def skip(what):
    """A stage build.sh left out because its input is missing (no Sega CD rip, no Demucs). Never silent: the
    image is worse than it could be, and every skip is printed again at the end."""
    skips.append(what)
    print("SKIP:", what)


def fail(what):
    fails.append(what)
    print("FAIL:", what)


def bin2iso(path):
    """The proper converter: slicing the raw track by hand assumes an alignment it does not have, and
    anything straddling a sector boundary then looks changed or missing."""
    return C.bin2iso(open(path, "rb").read())


def locate(built, orig, sc):
    """A scene sits where the table says, in the original and the build alike; the build changes what is
    in the slot, never where the slot is. (Searching the built track for the scene's first bytes fails:
    a menu word moved to slack re-points an F1 reference, and that can be inside those bytes.)"""
    return sc["base"]


def check_report():
    p = "build-en/report.txt"
    if not os.path.exists(p):
        return fail("no build-en/report.txt -- build with ./build.sh, which keeps the build's own report")
    r = open(p).read()
    for bad in ("OVER BUDGET", "STAYS JAPANESE", "CUT OFF", "UNTYPEABLE", "no translation for", "NOT A SCENE"):
        if bad in r:
            fail(f"build report says {bad!r}")
    m = re.search(r"voices: (\d+) table entries", r)
    if not m and "voices: SKIPPED" in r:
        skip("voices -- no Sega CD data files, every spoken line is Japanese")
    elif not m:
        fail("the voice step did not run (VOICE=0?) -- every spoken line would be Japanese")
    elif int(m.group(1)) < VOICES_AT_LEAST:
        fail(f"only {m.group(1)} voice entries; {VOICES_AT_LEAST} is the floor")


def check_audio_tracks():
    r = open("build-en/report.txt").read() if os.path.exists("build-en/report.txt") else ""
    left = set()
    if "intro: SKIPPED" in r:
        skip("intro narration -- track 17 stays Japanese"); left.add(17)
    if "cutscenes: SKIPPED" in r:
        skip("cutscene dub -- the 15 voiced cutscenes stay Japanese"); left |= set(range(3, 21)) - {15, 17, 18}
    for t in range(3, 21):
        if t in left:
            continue
        p = f"build-en/{N} (Track {t:02d}).bin"
        if not os.path.exists(p):
            fail(f"track {t:02d} missing")
        elif os.path.islink(p) and t not in (15, 18):     # the two voiced tracks with no Sega CD counterpart
            fail(f"track {t:02d} is a link to the Japanese original -- intro_audio / cutscene_dub did not run")


def check_tracks_agree(built, orig, scenes):
    for lba, sc in scenes.items():
        a = locate(built[2], orig[2], sc); b = locate(built[24], orig[24], sc)
        if a < 0 or b < 0:
            fail(f"scene {lba:#05x} not found on {'track 02' if a < 0 else 'track 24'}")
            continue
        n = sc["loaded"]
        if built[2][a:a + n] != built[24][b:b + n]:
            fail(f"scene {lba:#05x} differs between track 02 and track 24")


def word_ok(data, base, w, jp, keep, typed):
    """A word slot as built: the original Japanese may remain only for data and fallbacks."""
    off, size = w["off"], w["size"]
    got = bytes(data[base + off:base + off + size + 1])
    orig = jp.encode("cp932", "replace") + b"\xff"
    if answers.is_data(jp) or off in keep:
        return got[:len(orig)] == orig
    if got.startswith(orig):
        return False                          # still Japanese
    if off in typed:                          # an answer: full-width Latin, or a relocated pointer
        return True
    return True


def check_words(built, orig, scenes):
    for lba, sc in scenes.items():
        base_o = sc["base"]
        keep = answers.fallbacks(orig[2], sc); typed = answers.entries(orig[2], sc)
        for t in (2, 24):
            copies = []
            head = orig[t][base_o:base_o + 48]; i = -1
            while True:
                i = orig[t].find(head, i + 1)
                if i < 0:
                    break
                if orig[t][i:i + sc["text_start"]] == orig[t][base_o:base_o + sc["text_start"]]:
                    copies.append(i)
            for co in copies:
                cb = co
                # A word whose English did not fit its slot is moved to slack and its F1 references are
                # re-pointed; the Japanese stays in the old slot, unreferenced. So a slot still holding
                # its Japanese is a fault only while the script still points at it.
                script = bytes(built[t][cb:cb + sc["text_start"]])
                jap = [w["jp"] for w in sc["words"]
                       if not answers.is_data(w["jp"]) and w["off"] not in keep
                       and bytes(built[t][cb + w["off"]:cb + w["off"] + w["size"]]) == w["jp"].encode("cp932", "replace")
                       and bytes([0xF1, w["off"] & 0xFF, w["off"] >> 8]) in script]
                if jap:
                    fail(f"scene {lba:#05x} at track {t} sector {co // 0x800}: {len(jap)} menu words still Japanese, e.g. {jap[:4]}")


def check_answers(built, orig, scenes):
    for lba, sc in scenes.items():
        b2 = locate(built[2], orig[2], sc)
        for at, n, offs in answers.fields(orig[2], sc):
            if n in answers.WORD and built[2][b2 + at] != answers.MAX:
                fail(f"scene {lba:#05x}: word field is {built[2][b2 + at]}, not {answers.MAX}")
            jp = {w["off"]: w for w in sc["words"]}
            fb = built[2][b2 + offs[0]]
            if (fb & 3) not in (answers.GRID, answers.KEYPAD):
                fail(f"scene {lba:#05x}: fallback byte {fb:#04x} selects no keyboard (menu instead)")
            if n in answers.WORD:
                for off in offs[1:]:
                    w = jp.get(off)
                    if w and not answers.is_data(w["jp"]):
                        # the entry may have been relocated: follow its F1 reference in the built script
                        d = built[2][b2:b2 + sc["text_start"]]
                        k = d.find(bytes([0xF1, off & 0xFF, off >> 8]))
                        ptr = off if k < 0 else off   # in place, or the reference was re-pointed: read it
                        first = built[2][b2 + ptr]
                        if first not in (0x82, 0x81):
                            # relocated: find the reference and read where it points now
                            refs = [m.start() for m in re.finditer(re.escape(bytes([0xF1])), d)]
                            ok = any(built[2][b2 + (d[r + 1] | d[r + 2] << 8)] in (0x82, 0x81) for r in refs)
                            if not ok:
                                fail(f"scene {lba:#05x}: answer {w['jp']!r} is not stored as full-width Latin")
                            break


def check_keyboard(built, orig):
    o, b = orig[2], built[2]
    OV = 0x3B000
    def cpu(a): return OV + (a - 0xA000)
    for kind, at, stride, rows, name in ((2, 0xBB9D, 6, 12, "keypad"), (3, 0xBB9F, 24, 7, "letter grid")):
        base = o[cpu(at)] | o[cpu(at + 1)] << 8; g = cpu(base)
        gb = b.find(o[g:g + 18]) if kind == 2 else b.find(bytes([0x06, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0x01])) - 24
        if gb < 0:
            fail(f"{name} not found in the built overlay"); continue
        for r in range(rows):
            ro, rb = o[g + r * stride:g + (r + 1) * stride], b[gb + r * stride:gb + (r + 1) * stride]
            if kind == 2 and ro != rb:
                fail(f"keypad grid row {r} changed: {ro.hex(' ')} -> {rb.hex(' ')}"); break
            if any((x == 0) != (y == 0) for x, y in zip(ro, rb)):
                fail(f"{name} row {r}: a wall became a key or a key a wall"); break
            if kind == 3:
                stray = [y for y in rb if y >= 0x40 and not (0xA0 <= y < 0xA0 + 26)]
                if stray:
                    fail(f"letter grid row {r} has typable non-letters {[hex(x) for x in stray]} (invisible kana keys)"); break
        if kind == 3:
            letters = set(x for r in range(rows) for x in b[gb + r * stride:gb + (r + 1) * stride] if 0xA0 <= x < 0xA0 + 26)
            if len(letters) != 26:
                fail(f"letter grid has {len(letters)} of 26 letters")


def check_title(built):
    b = built[2]
    if b[title_patch.HOOK_ISO:title_patch.HOOK_ISO + 3] != bytes([0x20, title_patch.STUB_ORG & 0xFF, title_patch.STUB_ORG >> 8]):
        fail("title: scene_01_handler hook is not in place")
    if b[title_patch.STUB_ISO:title_patch.STUB_ISO + 3] != bytes([0x20, 0x06, 0x80]):
        fail("title: stub is not in place")
    code_at = title_patch.BLOCK_ISO + title_patch.CODE_ORG - title_patch.BLOCK_ORG
    if b[code_at:code_at + 4] == b"\xff\xff\xff\xff":
        fail("title: routine is not in the title's load")


def check_digits(built, orig, scenes):
    for lba, sc in scenes.items():
        b2 = locate(built[2], orig[2], sc)
        for w in sc["words"]:
            if answers.is_data(w["jp"]):
                o = orig[2][sc["base"] + w["off"]:sc["base"] + w["off"] + w["size"]]
                if built[2][b2 + w["off"]:b2 + w["off"] + w["size"]] != o:
                    fail(f"scene {lba:#05x}: data word {w['jp']!r} was changed")
                    break


def check_says(built, scenes):
    """Every say command in a built script must point at English text -- not at Japanese the scene
    list never knew about (「店の外に出ました」), and not into the middle of repacked text."""
    import snhuff, verify_text
    coding = snhuff.Coding("translations/coding.json")
    layout = {int(k, 16): v for k, v in json.load(open("work/scene_layout.json")).items()} if os.path.exists("work/scene_layout.json") else {}
    for lba, sc in scenes.items():
        base = sc["base"]; loaded = layout.get(lba, sc["loaded"])
        d = built[2][base:base + sc["text_start"]]
        jp = {m["ptr"]: m["jp"] for m in sc["messages"]}
        bad = nowait = 0
        for m in re.finditer(rb"\x63\x12[\x00-\x4a]\x00(.)(.)", d, re.S):
            ptr = m.group(1)[0] | m.group(2)[0] << 8
            if not (sc["text_start"] <= ptr < loaded):
                continue
            syms, end, why = verify_text.walk(built[2], base + ptr, base + loaded, coding)
            if syms is None or why:
                bad += 1
            elif jp.get(ptr, "").rstrip().endswith("<82F5>") and snhuff.NOWAIT not in syms:
                nowait += 1
        if bad:
            fail(f"scene {lba:#05x}: {bad} say commands point at text that is not English (an unlisted message)")
        if nowait:
            fail(f"scene {lba:#05x}: {nowait} lines lost the <82F5> close-without-waiting code (a shootout would stall)")


def check_voice_copies(built, orig):
    """No paired clip may survive in Japanese anywhere on either track: the EverDrive serves the last data
    track, and track 24 carries 244 clips at offsets other than the table's (24 Sep, Queen's Hospital)."""
    if any(w.startswith("voices") for w in skips):
        return
    import voices
    d = json.load(open(voices.ALIGN))
    voices.fixups(d)
    partner = {i for i, j in d["pairs"] if i is not None and j is not None}
    left = 0
    for i, c in enumerate(d["pce"]):
        if i not in partner:
            continue
        size, off = c["sectors"] * 2048, c["lba"] * 2048
        old = orig[2][off:off + size]
        for t in (2, 24):
            src, at = built[t], 0
            while True:
                at = src.find(old[:64], at)
                if at < 0:
                    break
                if src[at:at + size] == old:
                    left += 1
                at += 1
    print(f"voice copies: {len(partner)} paired clips, {left} Japanese copies left on the tracks")
    if left:
        fail(f"{left} copies of paired voice clips are still Japanese on the built tracks")


def check_credits(built, orig):
    """The ending roll's image, wherever it sits on either track, must carry the English lines (the staff roll
    drew kanji names as letter salad on the console, 24 Sep). The opening roll is deliberately untouched."""
    import credits
    t = credits.table()
    lo, hi = credits.IMAGE
    image = orig[2][lo:hi]
    places = []
    for k in (2, 24):
        at = 0
        while True:
            at = orig[k].find(image[:256], at)
            if at < 0:
                break
            if orig[k][at:at + len(image)] == image:
                places.append((k, at))
            at += 1
    wrong = 0
    n = 0
    for off, raw, text in credits.lines(orig[2]):
        if text not in t:
            continue
        n += 1
        want = credits.render(t[text], len(raw))
        for k, at in places:
            p = at + (off - lo)
            if built[k][p:p + len(raw)] != want:
                wrong += 1
    print(f"credits: {n} translated lines in {len(places)} copies of the ending roll, {wrong} not English")
    if wrong:
        fail(f"{wrong} credit lines are not English in the built tracks")


def check_text():
    r = subprocess.run([sys.executable, "tools/verify_text.py", "build-en"], capture_output=True, text=True)
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    print("verify_text:", tail)
    if r.returncode != 0 or "hang" in r.stdout.lower() and "0 " not in tail:
        fail("verify_text.py reports a message that would hang")


def check_emu():
    """A cold boot: the title must carry our lettering, and the reception must speak English."""
    import retro, mdfnstate
    cue = os.path.abspath(f"build-en/{N}.cue")
    emu = retro.Emu(os.path.abspath("emu/mednafen_pce_libretro.dylib"), os.path.expanduser("~/.mednafen/firmware"))
    emu.load(cue)
    for _ in range(1300):
        emu.run()
    emu.save_state("work/_verify_title.state")
    vram = mdfnstate.parse("work/_verify_title.state")["VDC.VRAM"]
    w = vram[0x6780 * 2] | vram[0x6780 * 2 + 1] << 8
    if w == 0x0253:
        fail("emulator: the title still shows 初 -- the runtime lettering did not run")
    for f in range(1300, 9000):
        emu.run([retro.BUTTONS["start"]] if f in (1310, 2600, 4100) else [])
    emu.save_state("work/_verify_reception.state")
    ram = mdfnstate.parse("work/_verify_reception.state")["HuC.SysCardRAM"]
    if sncells.sjis_plain("Enter") not in ram or "中に入る".encode("cp932") in ram:
        fail("emulator: the reception's menu is not English in RAM after a cold boot")


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    scenes = {}
    for f in sorted(glob.glob("work/scenes/*.json")):
        sc = json.load(open(f)); scenes[sc["lba"]] = sc
    orig = {2: open("disc/track02.iso", "rb").read(), 24: open("disc/track24.iso", "rb").read()}
    built = {2: bin2iso(f"build-en/{N} (Track 02).bin"), 24: bin2iso(f"build-en/{N} (Track 24).bin")}
    check_report(); check_audio_tracks(); check_tracks_agree(built, orig, scenes); check_words(built, orig, scenes)
    check_answers(built, orig, scenes); check_keyboard(built, orig); check_title(built); check_digits(built, orig, scenes)
    check_says(built, scenes)
    check_voice_copies(built, orig)
    check_credits(built, orig)
    check_text()
    if "--emu" in sys.argv:
        check_emu()
    if fails:
        print(f"\n{len(fails)} check(s) failed -- do not put this image on the card")
        sys.exit(1)
    if skips:
        print(f"\nall checks passed; {len(skips)} stage(s) skipped for missing input: " + "; ".join(skips))
        return
    print("\nall checks passed")


if __name__ == "__main__":
    main()
