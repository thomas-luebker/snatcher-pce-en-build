#!/usr/bin/env python3
"""Typed-answer screens: the right keyboard, and a field long enough for the English.

  answers.py               -> every typed-answer screen on the disc, its keyboard, field and answers

A typed-answer screen is a tree in the scene script -- `f8 2c 06 00 2b b9 34 <n> 00`, then
`20 <next> f1 <word> <action>` entries -- and two things about it are decided by bytes that look like
ordinary data:

**Which keyboard, or no keyboard at all, comes from the first byte of the first word.** Bank $7C at
$928B: `jsr $5341 ; and #$03 ; sta $351F`, then `cmp #$02 ; bcc` -- below 2 the tree is drawn as a plain
two-column *menu*, 2 is the digit keypad, 3 the letter grid. $5341 reads that byte out of the first
entry, which is the group's fallback (ハズレ "wrong", ベンソン以外 "besides Benson"): katakana `$83` gives
3, a full-width digit `$82` gives 2. Written as letter-pair cells the lead byte is whatever the first
two letters happen to produce -- "Miss" is `$9B` (3, the grid), "Wrong" and "WRONG" `$98` (0, a menu),
"Besides Benson" `$9E` (2, a *digit keypad* for typing a name). That is what put Napoleon's answers on
screen as a menu on 22 Sep, and what would have handed Outer Heaven a keypad. So the fallback is never
translated: it is matched when nothing else matched and never displayed on a typed screen.

**The field width is `<n>` in $34B9.** Four for カクメイ, hopeless for REVOLUTION. Every word field
becomes ten, which is what the name-entry code itself loads for the Jordan search (`a9 0a 8d b9 34`),
so a width the engine is known to draw at, on the same code path. Digit fields (2 and 3, the door quiz)
keep their width -- there the player types a number against numbers and the width is part of the puzzle.

Every copy on the track is patched, not just the one the scene table names; these screens have twins a
few sectors away, and patching the named copy alone is how the name search stayed Japanese for a day.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import namesearch  # noqa: E402

CMD = re.compile(rb"\xf8\x2c\x06\x00\x2b\xb9\x34(.)\x00", re.S)
MAX = 10                                     # what the name search loads into $34B9 itself
WORD = (4, 5)                                # fields where a word is typed; 2 and 3 are the door's digits
GRID, KEYPAD = 3, 2                          # $351F: the letter grid, the digit keypad; below 2 = a menu


def is_word(n):
    """A field where a word is typed. WORD is what they start as; apply() runs before the scenes are
    built, so by then they read MAX -- testing WORD alone made entries() and check() see nothing."""
    return n in WORD or n == MAX


def fields(iso, sc):
    """-> [(offset of the count byte, current field, [word offsets: fallback first])] for one scene."""
    d = iso[sc["base"]:sc["base"] + sc["loaded"]]
    out = []
    for m in CMD.finditer(d, 0, sc["text_start"]):
        offs, p = [], m.end()
        while True:
            r = namesearch.node(d, p)
            if r is None:
                break
            nxt, word, _ = r
            offs.append(word)
            if nxt is None:
                break
            p = nxt
        if offs:
            out.append((m.start() + 7, m.group(1)[0], offs))
    return out


def fallbacks(iso, sc):
    """The word offsets that must stay exactly as Konami wrote them: the first entry of every tree."""
    return {offs[0] for _, _, offs in fields(iso, sc)}


def entries(iso, sc):
    """The word offsets the player's typing is compared against: every entry after the fallback."""
    return {o for _, n, offs in fields(iso, sc) if is_word(n) for o in offs[1:]}


# What the keyboard types. A key produces one byte, $A0-$B9 for A-Z (tools/keyboard.py), and the
# matcher expands that to full-width Latin -- $8260 for Ａ -- before comparing it with the entries. So
# an entry has to be stored the same way, one full-width character per typed key: written as
# letter-pair cells like a menu word it can never be equal to anything the player can type, which is
# what "Way off!" to a correctly spelled ENDED was. Upper case, because that is what the keys are.
FW = {chr(c): bytes([0x82, 0x60 + c - ord("A")]) for c in range(ord("A"), ord("Z") + 1)}
FW.update({chr(c): bytes([0x82, 0x4F + c - ord("0")]) for c in range(ord("0"), ord("9") + 1)})
FW[" "] = bytes([0x81, 0x40])


def latin(text):
    """An answer as the matcher will see it typed."""
    try:
        return b"".join(FW[c] for c in text.upper())
    except KeyError as e:
        raise SystemExit(f"{text!r}: {e.args[0]!r} cannot be typed on the keyboard")


def is_data(jp):
    """★ and ☆ stand for what has not been typed yet, and digits are the keypads: never translated."""
    return bool(jp) and all("０" <= c <= "９" or c in "★☆" for c in jp)


def check(iso, sc, words_en):
    """-> problems: an answer longer than the field it will get, or a fallback that would pick the
    wrong keyboard. Either one is a puzzle that cannot be solved."""
    jp = {w["off"]: w["jp"] for w in sc["words"]}
    out = []
    for _, n, offs in fields(iso, sc):
        kind = jp[offs[0]].encode("cp932")[0] & 3 if offs[0] in jp else None
        if kind not in (GRID, KEYPAD):
            out.append(f"fallback {jp.get(offs[0])!r} selects no keyboard")
        width = MAX if is_word(n) else n
        for off in offs[1:]:
            en = words_en.get(off)
            if en and not is_data(jp.get(off, "")) and len(en) > width:
                out.append(f"{en!r} ({len(en)}>{width})")
    return out


def apply(iso):
    """Widen every word field on the whole track, in every copy of every screen."""
    grown = []
    for m in CMD.finditer(bytes(iso)):
        if m.group(1)[0] in WORD:
            iso[m.start() + 7] = MAX
            grown.append(m.start() // 0x800)
    return grown


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    iso = open("disc/track02.iso", "rb").read()
    for f in sorted(glob.glob("work/scenes/*.json")):
        sc = json.load(open(f))
        words = {w["off"]: w["jp"] for w in sc["words"]}
        for _, n, offs in fields(iso, sc):
            kind = words[offs[0]].encode("cp932")[0] & 3
            print(f"scene {sc['lba']:#05x}: field {n}, keyboard {kind} <- "
                  + ", ".join(words.get(o, "?") for o in offs))


if __name__ == "__main__":
    main()
