#!/usr/bin/env python3
"""Menu / topic words of a scene (plain SJIS, $FF-separated, right before the packed text) as letter-pair cells.

A word keeps its place when the English fits in the Japanese byte count (cells cost one byte per letter,
rounded up to 2). Otherwise it is moved to free space and every `F1 <lo> <hi>` reference to it in the
scene script is re-pointed.
"""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sncells  # noqa: E402

SCENE1 = {
    "その他": "Other", "もう一度聞く": "Ask again", "Ｂ・ハンターとは": "Bounty Hunters?", "ＪＫのスタッフ": "Junker staff",
    "ＪＫの特殊権限": "Junker rights", "ＪＫの任務": "Junker job", "ＪＵＮＫＥＲの事": "About Junkers", "ＪＵＮＫＥＲ証": "Junker ID",
    "メカニック室": "Engineering", "メタルギア使う": "Use Metal Gear", "メタルギア": "Metal Gear", "モニター": "Monitor",
    "カメラ": "Camera", "カトリーヌのこと": "About Katrina", "ガウディとは": "About Jordan", "ガウディ使う": "Use Jordan",
    "ギリアン家": "Gillian's", "ギブスンについて": "About Gibson", "ギブスンのこと": "On Gibson", "コンピュータ室": "Computer room",
    "コンピュータ": "Computer", "スナッチャーとは": "Snatchers?", "スナッチャー": "Snatcher", "セーブしない": "Don't save",
    "セーブする": "Save", "セーブ１": "Save 1", "セーブ２": "Save 2", "セーブ３": "Save 3", "セーブ４": "Save 4", "ソファ": "Sofa",
    "タイヤ": "Tire", "デカ部屋": "Detectives", "ナビゲーターとは": "Navigators?", "ナビゲーター": "Navigator",
    "ネオコウベの事": "Neo Kobe", "ハリーについて": "About Harry", "ハリーのこと": "On Harry", "ハリー": "Harry",
    "ビデオフォン": "Videophone", "フロント・ポッド": "Front pod", "ブラスター": "Blaster", "プレート": "Plate",
    "ポスター": "Poster", "ミカについて": "About Mika", "ミカの３サイズ": "Mika's sizes", "ミカの顔": "Her face",
    "ミカの胸": "Her bust", "ミカの事": "On Mika", "ミカ": "Mika", "奥の机": "Rear desk", "絵": "Picture", "外に出る": "Go out",
    "外へ出る": "Leave", "局長室": "Office", "局長": "Chief", "見せる": "Show", "見る": "Look", "訓練する": "Train",
    "訓練の仕方": "Training?", "工場跡": "Factory", "持ち金": "Money", "持物": "Things", "写真": "Photo", "射撃場": "Range",
    "車に乗る": "Get in", "車を降りる": "Get out", "車体": "Body", "手前の机": "Near desk", "受付嬢": "Reception",
    "使い方": "Usage", "窓": "Window", "中に入る": "Enter", "調べる": "Examine", "買った": "Bought", "買ってない": "Not bought",
    "扉": "Door", "聞く": "Ask", "壁の写真": "Wall photo", "壁": "Wall", "話す": "Talk",
}


def word_list(iso, base, text_start):
    """Walk back from the start of the packed text over the $FF-separated SJIS words."""
    words, i = [], text_start
    while iso[base + i - 1] == 0xFF:
        k = i - 2
        while iso[base + k] != 0xFF:
            k -= 1
        raw = bytes(iso[base + k + 1:base + i - 1])
        try:
            t = raw.decode("cp932")
        except UnicodeDecodeError:
            break
        if not raw or len(raw) > 40:
            break
        words.append((k + 1, t, len(raw)))
        i = k + 1
    # the first word follows the script directly, without a separator in front of it
    j = i - 1
    while j >= 2 and (0x81 <= iso[base + j - 2] <= 0x9F or 0xE0 <= iso[base + j - 2] <= 0xEA) and iso[base + j - 1] >= 0x40:
        j -= 2
    if j < i - 1 and iso[base + i - 1] == 0xFF:
        try:
            words.append((j, bytes(iso[base + j:base + i - 1]).decode("cp932"), i - 1 - j))
        except UnicodeDecodeError:
            pass
    return words[::-1]


def apply(iso, base, text_start, table, cursor, limit):
    """iso: bytearray. Returns (new cursor, in place, moved, untranslated)."""
    words = word_list(iso, base, text_start)
    script_end = words[0][0]
    inplace = moved = missing = 0
    for off, jp, size in words:
        en = table.get(jp)
        if en is None:
            missing += 1
            continue
        data = sncells.sjis_plain(en)
        if len(data) <= size:
            iso[base + off:base + off + size + 1] = (data + b"\xff").ljust(size + 1, b"\xff")
            inplace += 1
            continue
        if cursor + len(data) + 1 > limit:
            missing += 1
            continue
        refs, pat, p = [], bytes([0xF1, off & 0xFF, off >> 8]), -1
        while True:
            p = iso.find(pat, base + p + 1, base + script_end)
            if p < 0:
                break
            p -= base
            refs.append(p)
        if not refs:
            missing += 1
            continue
        iso[base + cursor:base + cursor + len(data) + 1] = data + b"\xff"
        for r in refs:
            iso[base + r + 1:base + r + 3] = cursor.to_bytes(2, "little")
        cursor += len(data) + 1
        moved += 1
    return cursor, inplace, moved, missing
