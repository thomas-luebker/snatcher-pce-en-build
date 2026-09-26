#!/usr/bin/env python3
"""The computer name search (scene 0x0FE) in English, in the game's own alphabet.

  namesearch.py           -> print the tree as it will be built, and check it

The screen Gillian uses to look up a name is a two-level table in the scene's script, and the
videophone's keypad (scene 0x0AE) is the same thing with digits:

    20 <next group>  F1 <key word>            a group; its key holds the characters of the keyboard
      20 <next entry>  F1 <word>  <action>    an entry; the action is its record
      ...                                     the last entry of a group has no `20`
    ...                                       the last group has no `20`

The player types with the keys, and what is typed is matched against the entries of the group whose
key holds the first character; the first entry of every group is the fallback ("No matching names on
file."). That is why translating this screen broke it twice: the entries are not read, they are
compared with what the player typed, and the keys are not labels, they are the keyboard.

So nothing here is encoded as letter-pair cells. Names are written in the game's own full-width
Latin (SJIS $82 60..79), one character per cell, exactly as the videophone's numbers are written in
full-width digits -- which is the part of this screen that already works on hardware. Typed bytes
and stored bytes are then the same by construction, and the System Card's font draws them.

The kana rows the keys came from already group the names by their first sound, and those sounds map
onto Latin initials almost one to one (カ行 = K, ガ行 = G, サ行 = S, マ行 = M ...), so the tree keeps
its shape: only the text changes, plus the order of the groups, which is a pointer each. Letters no
name starts with are put on the two empty groups, so the whole alphabet is on the keyboard and typing
a name that is not on file reaches a fallback.
"""
import json
import os
import sys

TSV = "translations/namesearch.tsv"
TREE_START = 0x0011
FIELD = 10                                   # characters the input field holds (measured in the emulator)
# The engine picks the keyboard from the first character of the first key word: a katakana one gives
# the name grid (which tools/keyboard.py has turned into A-Z), anything in the $82 row gives the
# videophone's digit pad -- which is what English keys alone produced: no keys drawn and digits typed.
# So the first key keeps a katakana character in front of its letters. Nothing types it, and the
# letters after it are what the search matches on.
MODE_KANA = "\u30a2"
FW = {chr(c): bytes([0x82, 0x60 + c - ord("A")]) for c in range(ord("A"), ord("Z") + 1)}

# Which letters each group's key carries. The letters a name starts with have to be on its own
# group's key -- that is what the engine matches on -- and the rest of the alphabet goes on the two
# groups no name is under (ダヂヅデド, パピプペポ), so every letter can be typed.
KEYS = {
    "ア": "A",            # Alice, Adachi
    "バビブベボ": "B",     # Benson, Bobo
    "カキクケコ": "CK",    # Chief (局長), Katrina, Kojima, Konami ...
    "ダヂヅデド": "DE",    # no names: takes two of the spare letters
    "ハヒフヘホ": "FH",    # Freddie, Furukawa / Harry, Hayasaka, Hashimoto
    "ガギグゲゴ": "G",     # Gillian, Gibson
    "イウエオ": "IOU",     # Isabella, Ivan, Inoue ... / Ota, Oyama
    "ザジズゼゾ": "J",     # Jean, Jack, Jamie
    "ラリルレロ": "LR",    # Lisa, Little John / Random
    "マミムメモ": "M",     # Mika, Metal Gear, Matsui ...
    "ナニヌネノ": "N",     # Napoleon, Nagata
    "パピプペポ": "PQ",    # no names: the rest of the spare letters
    "サシスセソ": "S",     # Saikachi, Shinohara ...
    "タチツテト": "T",     # Tamura, Tateishi, Tominaga ...
    "ヤユヨワン": "VWXYZ",  # Yara, Yamane, Yoshioka, and the last of the spares
}
# The order the groups are shown in, which is the order the keyboard reads. The last group cannot
# move: it is the one with no `20 <next>` field, and giving it one would shift the whole tree.
ORDER = ["ア", "バビブベボ", "カキクケコ", "ダヂヅデド", "ハヒフヘホ", "ガギグゲゴ", "イウエオ",
         "ザジズゼゾ", "ラリルレロ", "マミムメモ", "ナニヌネノ", "パピプペポ", "サシスセソ",
         "タチツテト", "ヤユヨワン"]


def names():
    out = {}
    for line in open(TSV, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        jp, en = line.rstrip("\n").split("\t")
        out[jp] = en
    return out


def latin(text):
    return b"".join(FW[c] for c in text)


def node(d, p):
    """-> (next sibling or None, word offset, offset after the word ref), or None if p is not a node."""
    nxt = None
    if d[p] == 0x20:
        nxt = d[p + 1] | d[p + 2] << 8
        p += 3
    if d[p] != 0xF1:
        return None
    return nxt, d[p + 1] | d[p + 2] << 8, p + 3


def tree(d, words):
    """-> [(group node offset, key word offset, [(entry offset, word offset), ...]), ...]"""
    groups, g = [], TREE_START
    while True:
        gn, gw, p = node(d, g)
        kids, c = [], p
        while True:
            r = node(d, c)
            if r is None:
                break
            cn, cw, cp = r
            kids.append((c, cw))
            if cn is None:
                break
            c = cn
        groups.append((g, gw, kids))
        if gn is None:
            return groups
        g = gn


def plan(iso, sc):
    """-> ({word offset: replacement bytes}, {group node offset: next group node offset or None}).

    Checked here rather than in the game: every name has to start with a letter its group's key
    carries, or the search would not find it, and every letter has to be on exactly one key, or the
    keyboard would have it twice.
    """
    base = sc["base"]
    d = iso[base:base + sc["loaded"]]
    words = {w["off"]: w["jp"] for w in sc["words"]}
    en = names()
    groups = tree(d, words)
    assert len(groups) == len(KEYS), f"{len(groups)} groups, {len(KEYS)} keys"

    seen = ""
    repl, by_key = {}, {}
    for g, gw, kids in groups:
        key = words[gw]
        assert key in KEYS, f"unknown group key {key}"
        letters = KEYS[key]
        for c in letters:
            assert c not in seen, f"letter {c} is on two keys"
        seen += letters
        repl[gw] = (MODE_KANA.encode("cp932") if key == ORDER[0] else b"") + latin(letters)
        by_key[key] = g
        for c, cw in kids:
            name = en.get(words[cw])
            assert name, f"no English for {words[cw]}"
            assert name[0] in letters or words[cw] == "ガイトウシャナシ", \
                f"{name} is under key {letters} but starts with {name[0]}"
            repl[cw] = latin(name)
    assert sorted(seen) == [chr(c) for c in range(ord("A"), ord("Z") + 1)], f"keyboard is {sorted(seen)}"

    # The input field holds ten characters, so a longer name cannot be typed at all. That is fine for
    # the compound forms -- KATRINAGIBSON leads to the same record as KATRINA -- but every record has
    # to stay reachable by something that fits, so each one is checked for a short enough way in.
    reach = {}
    for g, gw, kids in groups:
        for c, cw in kids:
            a = c + (3 if d[c] == 0x20 else 0) + 3           # the action after the word reference
            act = bytes(d[a:a + (3 if d[a] == 0x4E else 6)])   # `4e <record>` or a say command
            reach.setdefault(act, []).append(en[words[cw]])
    for act, forms in reach.items():
        assert min(len(f) for f in forms) <= FIELD, \
            f"none of {forms} fits the {FIELD}-character field, so that record cannot be reached"

    chain = {}
    for i, key in enumerate(ORDER):
        chain[by_key[key]] = by_key[ORDER[i + 1]] if i + 1 < len(ORDER) else None
    last = [g for g, gw, k in groups if node(d, g)[0] is None]
    assert chain[last[0]] is None, "the group that cannot move has to stay last"
    return repl, chain


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sc = json.load(open("work/scenes/0fe.json"))
    iso = open("disc/track02.iso", "rb").read()
    d = iso[sc["base"]:sc["base"] + sc["loaded"]]
    words = {w["off"]: w["jp"] for w in sc["words"]}
    repl, chain = plan(iso, sc)
    order = {g: i for i, g in enumerate(ORDER)}
    groups = sorted(tree(d, words), key=lambda t: order[words[t[1]]])
    board = ""
    for g, gw, kids in groups:
        key = repl[gw].decode("cp932")
        board += key
        print(f"[{key}]  " + ", ".join(repl[cw].decode("cp932") for _, cw in kids))
    long = sorted({n.decode("cp932") for n in repl.values() if len(n) // 2 > FIELD})
    print(f"\nkeyboard: {board}  ({len(board)} keys)")
    if long:
        print(f"longer than the {FIELD}-character field, so typed by their short form: {', '.join(long)}")
    print(f"{sum(len(k) for _, _, k in groups)} entries, {len(groups)} groups")


if __name__ == "__main__":
    main()
