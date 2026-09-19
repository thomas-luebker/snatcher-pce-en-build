#!/usr/bin/env python3
"""Speaker names (dialogue bank $6D47-$6F27, pointer table $6F28) rewritten as letter-pair cells."""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sncells  # noqa: E402

DIALOGUE_ISO, NAMES, PTRS, PTRS_END = 0xF000, 0x6D47, 0x6F28, 0x6FBC
EN = {"ギリアン": "Gillian", "受付嬢": "Reception", "ミカ": "Mika", "局長": "Chief", "ハリー": "Harry",
      "メタルギア": "Metal Gear", "カトリーヌ": "Katrina", "ナポレオン": "Napoleon", "男": "Man", "女": "Woman",
      "通行人": "Passerby", "店員": "Clerk", "アナウンス": "Announcer", "呼び込み": "Barker", "マスター": "Barman",
      "イザベラ": "Isabella", "お面ライダー": "Masked Rider", "コウネリヤッサン": "Cornelius", "エイリヤン": "Alien",
      "おかねさん": "Okane", "Ｈ２Ｏ": "H2O", "ガリバー": "Gulliver", "客": "Patron", "イワン": "Ivan", "リサ": "Lisa",
      "ランダム": "Random", "オウム": "Parrot", "ジェミー": "Jamie", "ドライバー": "Driver", "リカ": "Rika",
      "早坂": "Hayasaka", "技研": "Giken", "井上": "Inoue", "小島": "Kojima", "篠原": "Shinohara",
      "フクイ２世": "Fukui II", "吉岡": "Yoshioka", "松花": "Matsuhana", "フリーマン": "Freeman", "ガウディ": "Jordan",
      "りゅう": "Ryu", "ゆうじ": "Yuji", "ふさこ": "Fusako", "村岡": "Muraoka", "べん": "Ben", "ヒロモト": "Hiromoto",
      "べんてん": "Benten", "朋子": "Tomoko", "留守電": "Voicemail", "矢内": "Yanai", "和田": "Wada", "カンチ": "Kanchi",
      "千恵": "Chie", "ＴＶ": "TV", "コナミ": "Konami"}


def apply(iso):
    iso = bytearray(iso)
    base = DIALOGUE_ISO - 0x6000
    n = (PTRS_END - PTRS) // 2
    blob, new_ptr, cache = bytearray(), [], {}
    for i in range(n):
        p = iso[base + PTRS + 2 * i] | (iso[base + PTRS + 2 * i + 1] << 8)
        raw = bytes(iso[base + p:iso.index(0xFF, base + p)])
        if raw not in cache:
            cache[raw] = NAMES + len(blob)
            if raw:
                jp = raw[1:].decode("cp932")
                blob += raw[:1] + sncells.sjis_plain(EN[jp]) + b"\xff"
            else:
                blob += b"\xff"
        new_ptr.append(cache[raw])
    assert NAMES + len(blob) <= PTRS, f"names need {len(blob)} bytes, {PTRS - NAMES} available"
    iso[base + NAMES:base + PTRS] = blob.ljust(PTRS - NAMES, b"\xff")
    for i, p in enumerate(new_ptr):
        iso[base + PTRS + 2 * i:base + PTRS + 2 * i + 2] = p.to_bytes(2, "little")
    return bytes(iso), len(blob)


if __name__ == "__main__":
    data, n = apply(open(sys.argv[1], "rb").read())
    open(sys.argv[2], "wb").write(data)
    print(f"names table: {n} of {PTRS - NAMES} bytes")
