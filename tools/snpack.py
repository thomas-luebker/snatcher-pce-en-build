#!/usr/bin/env python3
"""Snatcher (PC Engine) packed script text: decoder.

The script stores text as a nibble stream (after buranko-kun's disassembly of
decode_next_pair at $7272; verified here against RAM, see docs/FINDINGS.md):

  12-bit code = lead nibble L, trail byte T
    T >= $40            SJIS kanji pair: lead byte $88-$98 rebuilt from L
                        (L<8 -> $90+L; L=8 -> $98 if T<$9F else $88; L>8 -> $80+L)
    T <  $40, L = 0     end of text (mid-byte only)
    whole byte $00      end of text when the stream is on a byte boundary (2 nibbles, not 3)
    T <  $40, L = 1/2   run of T single-byte characters follows (8 bits each):
                        b <  $40 -> $81,b+$40 (punctuation)
                        b >= $9F -> $82,b      (hiragana)
                        else     -> $83,b if L=1 (katakana) / $82,b if L=2 (fullwidth alnum)
    T <  $40, L = 3..F  one character: lead $81+(L&3), trail ((L&$C)<<4)|T
"""


class Nibbles:
    def __init__(self, data, pos, half=0):
        self.d, self.n = data, pos * 2 + half

    def nib(self):
        b = self.d[self.n >> 1]
        v = (b >> 4) if self.n % 2 == 0 else (b & 15)
        self.n += 1
        return v

    def byte(self):
        return (self.nib() << 4) | self.nib()


def decode(data, pos, half=0, limit=400):
    """Return (list of SJIS pairs as bytes, nibble position after the end code or None)."""
    s, out = Nibbles(data, pos, half), []
    try:
        while len(out) < limit:
            if s.n % 2 == 0 and s.d[s.n >> 1] == 0:        # aligned: a zero byte ends the sentence
                return out, s.n + 2
            lead, trail = s.nib(), s.byte()
            if trail >= 0x40:
                if lead < 8 or (lead == 8 and trail < 0x9F):
                    lead |= 0x10
                out.append(bytes([lead | 0x80, trail]))
            elif lead == 0:
                return out, s.n
            elif lead < 3:
                for _ in range(trail):
                    b = s.byte()
                    if b < 0x40:
                        out.append(bytes([0x81, b + 0x40]))
                    elif b >= 0x9F or lead == 2:
                        out.append(bytes([0x82, b]))
                    else:
                        out.append(bytes([0x83, b]))
            else:
                out.append(bytes([0x81 + (lead & 3), ((lead & 0xC) << 4) | trail]))
    except IndexError:
        pass
    return out, None


def text(pairs):
    return b"".join(pairs).decode("shift_jis", "replace")


# ---------------------------------------------------------------------------------------------
# Encoder for English in the game's own format, no code changes: fullwidth Latin letters, digits
# and punctuation are single-byte members of a "run" (mode 2), so English costs 8 bits per
# character plus 12 bits per run header (max 63 characters per run). <82F2> (run byte $F2) is
# the game's line break.
PUNCT = {" ": 0x40, ",": 0x43, ".": 0x44, ":": 0x46, ";": 0x47, "?": 0x48, "!": 0x49, "-": 0x5D, "/": 0x5E,
         "~": 0x60, "'": 0x66, '"': 0x68, "(": 0x69, ")": 0x6A, "[": 0x6D, "]": 0x6E, "+": 0x7B, "=": 0x81 - 0x100,
         "*": 0x96 - 0x100, "&": 0x95 - 0x100, "%": 0x93 - 0x100, "#": 0x94 - 0x100}


def _run_byte(ch):
    if ch == "\n":
        return 0xF2
    if "A" <= ch <= "Z":
        return 0x60 + ord(ch) - 65
    if "a" <= ch <= "z":
        return 0x81 + ord(ch) - 97
    if "0" <= ch <= "9":
        return 0x4F + ord(ch) - 48
    t = PUNCT.get(ch)
    if t is None or t < 0x40:
        return 0x48 - 0x40            # unknown -> "?"
    return t - 0x40                   # $81,t  is stored as t-$40


def encode_english(text):
    """ASCII text with \\n line breaks -> packed bytes (byte aligned, zero-byte terminated)."""
    nibs = []
    for i in range(0, len(text), 63):
        part = text[i:i + 63]
        nibs += [2, len(part) >> 4, len(part) & 15]
        for ch in part:
            b = _run_byte(ch)
            nibs += [b >> 4, b & 15]
    if len(nibs) % 2:
        nibs += [0, 0, 0]             # mid-byte end code  0,T<$40
    else:
        nibs += [0, 0]                # aligned: zero byte
    return bytes((nibs[i] << 4) | nibs[i + 1] for i in range(0, len(nibs), 2))
