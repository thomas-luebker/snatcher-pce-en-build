#!/usr/bin/env python3
"""Reach any shootout or chapter in the emulator through the game's own debug menu.

  debug_menu.py image  build-en work/debug_en       -> research image whose first scene is the debug menu
  debug_menu.py image  disc     work/debug_jp       -> the same from the original disc, for comparison
  debug_menu.py boot   work/debug_en                -> boots it (intro, title, two Starts), saves <dir>/menu.state
  debug_menu.py go     work/debug_en "Shooting/With Ivan" 3000 work/shots/ivan [PRESS_UNTIL]
                                                    -> walks the menus to that entry (or to "1,1;0,3" by
                                                       column,row), then runs
  debug_menu.py list                                -> every entry, its path and the scene it lands in

Reference: docs/DEBUG_MENU.md (layout, every entry's landing scene, the script forms, the flag routines).

Scene 0x09E is Konami's "command debug" scene: a menu of every chapter start and, under シューティング
(column 1, row 1), every shooting sequence -- 局長その１/２, リサと, イ＠ワンと, フレディ首締め, ＱＵＥＥＮ病院,
地下道, タクシー. The game never shows it, but the scene loader takes its target from the scene table in
bank $68 (entry = 6 + scene number, `scene_loader_main` at $5451), so pointing the reception's entry
(#16, ISO 0xC585) at LBA 0x9E boots straight into it. That is how the <82F5> stall was reproduced
without a save from the card (docs/FINDINGS.md, 23 Sep).

Menu input is polled with a cooldown: a one-frame press lands about two times in three, so every press
here is held four frames and each move is checked on a screenshot (the highlighted entry is the one
boxed in cyan) before the next.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdsector as C  # noqa: E402

N = "Snatcher CD-ROMantic (Japan)"

# menu -> (top-level column,row), then the entries in submenu order (column 0 top to bottom, then column 1).
# A "parent/child" entry opens a nested list. Scene = $351D after the jump (0 = the shootout runs in-scene).
MENUS = {
    "Act 1 first half": ((0, 0), [("From the start", 10), ("Harry's mecha room", 10), ("Factory ruins", 11),
                                  ("Back from the ruins", 12)]),
    "Act 1 second half": ((0, 1), [("Gibson's", 14), ("Gillian's", 13), ("Meet Napoleon", 15), ("JD", 16),
                                   ("Outer Heaven", 16), ("Investigate Ivan", 18), ("Investigate Freddy", 19)]),
    "Act 2 first half": ((0, 2), [("Act 2 start", 5), ("Meet Napoleon", 21), ("Oleen Hospital", 22),
                                  ("Find Katrina", 2), ("Katrina at home", 26), ("Queen's Hospital 1", 24)]),
    "Act 2 second half": ((0, 3), [("Napoleon at OH", 25), ("Runaway scene", 22), ("Hospital with Random", 24),
                                   ("Basement/Corridor", 27), ("Basement/Morgue", 27), ("Body reconstruction", 27),
                                   ("Underpass and taxi", 28), ("Last HQ", 29)]),
    "Act 3": ((1, 0), [("Act 3 start", 30), ("Riddle solved", 30), ("To the church", 31), ("Jamie", 32),
                       ("Random revived", 32)]),
    "Shooting": ((1, 1), [("Chief 1", 0), ("Chief 2", 0), ("With Lisa", 19), ("With Ivan", 0), ("Freddy", 19),
                          ("Queen's Hospital", 0), ("Underpass", 0), ("Taxi", 0)]),
    "VRAM animation": ((1, 2), []),
}


def path_of(name):
    """'Shooting/With Ivan' -> [(1,1), (0,3)]; 'Act 2 second half/Basement/Morgue' -> three steps."""
    menu, _, rest = name.partition("/")
    top, entries = MENUS[menu]
    if not rest:
        return [top]
    rc = lambda i: (i // 4, i % 4)
    row, group_row, leaves = -1, {}, {}
    for label, _ in entries:                           # a nested group takes one row; its leaves a sub-list
        group, _, leaf = label.partition("/")
        if leaf:
            if group not in group_row:
                row += 1; group_row[group] = row; leaves[group] = []
            leaves[group].append(leaf)
            if label == rest:
                return [top, rc(group_row[group]), rc(leaves[group].index(leaf))]
        else:
            row += 1
            if label == rest:
                return [top, rc(row)]
    raise SystemExit(f"no debug entry {name!r}; see `debug_menu.py list`")


def list_entries():
    for menu, (top, entries) in MENUS.items():
        print(f"{menu}  {top}")
        for label, scene in entries:
            print(f"    {menu}/{label:<22} -> {path_of(menu + '/' + label)}  scene {scene} ({0x9e + 16 * scene:#x})"
                  if scene else f"    {menu}/{label:<22} -> {path_of(menu + '/' + label)}  in-scene shootout")
ENTRY16 = 0xC505 + 16 * 8                     # scene table entry of the first scene after the intro


def image(src, out):
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(src):
        if f.startswith(N) and f.endswith(".bin") and "Track 02" not in f and not os.path.exists(os.path.join(out, f)):
            os.symlink(os.path.abspath(os.path.join(src, f)), os.path.join(out, f))
    open(os.path.join(out, N + ".cue"), "w").write(open(os.path.join(src, N + ".cue")).read())
    raw = open(os.path.join(src, f"{N} (Track 02).bin"), "rb").read()
    iso = bytearray(C.bin2iso(raw))
    assert iso[ENTRY16:ENTRY16 + 8] == bytes.fromhex("003e010416000e00"), iso[ENTRY16:ENTRY16 + 8].hex()
    iso[ENTRY16 + 1], iso[ENTRY16 + 2] = 0x9E, 0x00
    open(os.path.join(out, f"{N} (Track 02).bin"), "wb").write(C.iso2bin(bytes(iso), raw))
    print(out, "ready (never for the card: its first scene is the debug menu)")


def emu_for(d):
    import retro
    e = retro.Emu(os.path.abspath("emu/mednafen_pce_libretro.dylib"), os.path.expanduser("~/.mednafen/firmware"))
    e.load(os.path.abspath(os.path.join(d, N + ".cue")))
    e.run()
    return e


def boot(d):
    import retro
    e = emu_for(d)
    for f in range(9000):
        e.run([retro.BUTTONS["start"]] if f in range(400, 460) or f in range(2500, 2520) or f in range(4000, 4020) else [])
    e.save_state(os.path.join(d, "menu.state"))
    print("saved", os.path.join(d, "menu.state"))


def cursor(e, shot):
    from PIL import Image
    e.screenshot(shot)
    im = Image.open(shot).convert("RGB")
    cyan = lambda p: p[2] > 150 and p[0] < 100
    for col, (x0, x1) in enumerate(((8, 130), (134, 250))):
        for k in range(4):
            y = 165 + 16 * k
            box = sum(1 for x in range(x0, x1) if cyan(im.getpixel((x, y - 7))))
            txt = sum(1 for x in range(x0, x1) if cyan(im.getpixel((x, y))))
            if box > 60 and txt < 12:
                return (col, k)
    return None


def go(d, targets, frames, out, until=0):
    import retro
    e = emu_for(d)
    e.load_state(os.path.join(d, "menu.state"))
    os.makedirs(out, exist_ok=True)
    steps = path_of(targets) if "/" in targets or targets in MENUS else \
        [tuple(int(v) for v in s.split(",")) for s in targets.split(";")]

    def run(n, btn=None):
        for i in range(n):
            e.run([retro.BUTTONS[btn]] if btn and i < 4 else [])
    run(30, "a"); run(60)                                     # Metal's line
    for t in steps:
        for _ in range(14):
            if cursor(e, out + "/_cur.png") == t:
                break
            run(45, "down")
        print("target", t, "cursor", cursor(e, out + "/_cur.png"))
        run(30, "a"); run(90)
    for f in range(frames):
        e.run([retro.BUTTONS["a"]] if until and f and f % 100 == 0 and f < until else [])
        if f and f % 100 == 0:
            e.screenshot(f"{out}/f{f:06d}.png")
    e.save_state(out + "/end.state")
    print("done; scene", e.peek(0x351D), "state", out + "/end.state")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a = sys.argv[1:]
    if a[0] == "image":
        image(a[1], a[2])
    elif a[0] == "boot":
        boot(a[1])
    elif a[0] == "list":
        list_entries()
    elif a[0] == "go":
        go(a[1], a[2], int(a[3]), a[4], int(a[5]) if len(a) > 5 else 0)
