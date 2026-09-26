# Konami's command-debug menu (scene 0x09E)

Konami left their own test menu on the disc: scene bank 0x09E ("コマンドデバッグ用のファイル", *This file is
Command Debug*), a chapter-and-shootout select that reaches every part of the game in a few presses. The
retail game never shows it. We reach it by pointing one scene-table entry at it, and it is now the standard
way to put the emulator anywhere in the story without a save. Measured 2026-09-23 on the original disc.

## Reaching it

The scene loader (`scene_loader_main`, $5451 in bank $68) takes the scene table entry `6 + scene number`
(`$351D` holds the number; 0x09E is scene 0, the reception 0x13E scene 10, and so on up the 16-sector grid).
Pointing the reception's entry (#16, ISO 0xC585, bytes `00 3e 01 04 16 00 0e 00`) at LBA 0x9E makes the debug
menu the first scene after the intro:

    python3 tools/debug_menu.py image build-en work/debug_en     # from the English build
    python3 tools/debug_menu.py image disc     work/debug_jp     # from the original disc
    python3 tools/debug_menu.py boot  work/debug_en              # intro, title, two Starts -> work/debug_en/menu.state
    python3 tools/debug_menu.py go    work/debug_en "Shooting/With Ivan" 3000 work/shots/ivan
    python3 tools/debug_menu.py list                             # every entry, its path and where it lands

The research images are never for the card: their first scene is the menu. Scenes 0x10E, 0x11E and 0x12E are
byte-for-byte copies of 0x09E (the table names them; nothing in the game reaches them either).

**Input.** The menu polls the pad with a cooldown: a one-frame press lands about two times in three, a press
held four frames lands every time, and a direction right after a different direction is swallowed. `debug_menu.py`
holds each press four frames and reads the highlighted entry (the one boxed in cyan) off a screenshot before the
next move, so a walk is verified rather than counted.

## Layout

Top level, two columns of four:

| col 0 | col 1 |
| --- | --- |
| ａｃｔ１前半 Act 1 first half | ａｃｔ３ Act 3 |
| ａｃｔ１後半 Act 1 second half | シューティング Shooting |
| ａｃｔ２前半 Act 2 first half | ＶＲＡＭアニメ VRAM animation |
| ａｃｔ２後半 Act 2 second half | |

Each act entry opens a submenu of chapter starts in story order; Shooting lists the eight shootouts. Submenus fill
column 0 top to bottom, then column 1. `debug_menu.py go` addresses entries as `"Act 1 second half/Ivan"` or by
`(column,row)` pairs (`"0,1;1,1"`).

## Every entry, and where it lands

Scene numbers are `$351D` after the jump; the LBA is `0x9E + 16 × scene`. "Flags" is the chain of flag routines
the entry calls first (see below), so a chapter starts with the story state it would have in play.

| Menu | Entry | Jumps to | Landing screen (emulator) | Flags |
| --- | --- | --- | --- | --- |
| Act 1 first half | 最初から From the start | scene 10 (0x13E) +$0004 | Junker HQ reception | — |
| | ハリーのいるメカ室へ行く To Harry's mecha room | scene 10 +$0D60 | HQ, Harry's room | — |
| | 工場跡へ行く To the factory ruins | scene 11 (0x14E) +$0004 | Turbocycle: "We're at the factory ruins" | — |
| | 工場跡からの帰還 Back from the ruins | scene 12 (0x15E) +$0010 | Junker HQ | A |
| Act 1 second half | ギブスン家へ直行 Straight to Gibson's | scene 14 (0x17E) +$0004 | Gibson's house | A B C |
| | ギリアン宅へ直行 Straight to Gillian's | scene 13 (0x16E) +$0004 | Gillian's apartment building | A B C |
| | ナポレオンに会う Meet Napoleon | scene 15 (0x18E) +$0004 | Alton Plaza | A B C D, flag $0520 |
| | ＪＤへ直行 Straight to JD (Plato's Cavern) | scene 16 (0x19E) +$0004 | J-Division street | A B C D E |
| | ＯＨへ直行 Straight to Outer Heaven | scene 16 +$14E1 | Outer Heaven's door | A B C D E F |
| | イワン捜査 Investigate Ivan | scene 18 (0x1BE) +$0018 | Ivan's neighbourhood | A B C D E F G |
| | フレディ捜査 Investigate Freddy | scene 19 (0x1CE) +$0004 | Freddy Nielsen's apartment | A–G, flag $0640 |
| Act 2 first half | ａｃｔ２開始 Act 2 start | scene 5 (0x0EE) +$0004 | Gillian's apartment building | — |
| | ナポレオンに会う Meet Napoleon | scene 21 (0x1EE) +$0010 | Alton Plaza | H, flag $0520 |
| | オウリン病院 Oleen Hospital | scene 22 (0x1FE) +$0004 | Oleen Hospital | H I |
| | カトリーヌを探せ Find Katrina | scene 2 (0x0BE) +$0004 | Turbocycle | H J (+ a flag test) |
| | 自宅カトリーヌ Katrina at home | scene 26 (0x23E) +$0004 | Gillian's apartment building | H J, flag $0670 |
| | クィーン病院１ Queen's Hospital 1 | scene 24 (0x21E) +$0000 | Queen's Hospital | H K |
| Act 2 second half | ＯＨナポレオン Napoleon at OH | scene 25 (0x22E) +$0004 | Outer Heaven | H L M |
| | 暴走シーン Runaway scene | scene 22 +$0B17 | Videophone (Mika) | H M |
| | 病院ランダム同行 Hospital with Random | scene 24 +$0008 | Queen's Hospital | H M |
| | クィーン病院地下 › 地下の廊下 Basement corridor | scene 27 (0x24E) +$0020 | Basement corridor, Mika and Gillian | H M, var 1←$32 |
| | クィーン病院地下 › 地下モルグ Basement morgue | scene 27 +$0004 | The morgue | H M |
| | 遺体復元 Body reconstruction | scene 27 +$115C | Reconstruction on the videophone | H M |
| | 地下道とタクシー Underpass and taxi | scene 28 (0x25E) +$0008 | The taxi (Chin Shu Oh) | H M |
| | ラスト本部 Last HQ | scene 29 (0x26E) +$0004 | Junker HQ: "Are Mika and Harry safe?" | H M |
| Act 3 | ａｃｔ３開始 Act 3 start | scene 30 (0x27E) +$0004 | "ACT 3 JUNK" title card | — |
| | 謎が解けた The riddle solved | scene 30 +$003F | Act 3, Junker HQ | — |
| | 教会へ向かう To the church | scene 31 (0x28E) +$0004 | The taxi to the church | — |
| | ジェミーと再会 Reunion with Jamie | scene 32 (0x29E) +$0004 | Jamie's ward | var 1←$52 |
| | ランダム復活 Random revived | scene 32 +$0010 | Random | — |
| Shooting | 局長その１ Chief 1 | in-scene | Chief's office: "Cu...Cunningham!!", the ceiling | var 2←$07 |
| | 局長その２ Chief 2 | in-scene | "Gillian, it's a trap!" | var 0←$12 |
| | リサと With Lisa | scene 19 +$0008 | Gillian's bathroom, Lisa | var 0←$3F |
| | イ＠ワンと With Ivan | in-scene | Ivan's door, the RG-11 | var 0←$2D |
| | フレディ首締め Freddy's chokehold | scene 19 +$1753 | Freddy's apartment | — |
| | ＱＵＥＥＮ病院 Queen's Hospital | in-scene | The Snatcher's skull | var 2←$35 |
| | 地下道 Underpass | in-scene | The underpass, insects | var 5←$3D |
| | タクシー Taxi | in-scene | The taxi: "Where you're headed is already decided" | var 0←$45 |
| VRAM animation | ＶＲＡＭアニメ | in-scene | A green plasma test pattern | var 3←$58, var 0←$64 |

"In-scene" entries run the shootout inside the debug scene itself (`$351D` stays 0): a shootout is an action
sequence any scene can start, not a scene of its own. The With Ivan entry is therefore the shootout without the
door dialogue that precedes it in the story — the door scene proper is `Act 1 second half/Investigate Ivan`
plus the walk to Room 301 (Look › Area, Look › Freeman, Ask › About Ivan, Possessions › Show › Photo › Montage
photo, Ask › About Ivan again, Move › Room 301), and Ivan answers only after the Freddy visit.

## What the actions are made of

The script forms below were read off the tree and confirmed by what `$351D` did; the interpreter (bank $7C) is
not in the disassembly, so the names are ours.

| Bytes | Meaning | Evidence |
| --- | --- | --- |
| `20 lo hi f1 wlo whi …` | Menu node: next node at `lo hi`, word `wlo whi`, then the action | The tree above |
| `f9 2d nn 00 lo hi` | Go to scene `nn` at script offset `lo hi` | Every entry's `$351D` matched `nn` |
| `1c 4e lo hi` | Call the routine at `lo hi` in this scene | The 13 flag routines at +$048D–+$0519 |
| `54 lo hi` | Set story flag `lo hi` | Only thing the flag routines do |
| `1c 6b nn xx` | Set game variable `nn` to `xx` (the shootout number, the act state) | Precedes every in-scene shootout |
| `1c 69 2e nn 00 00 00` / `1c 6a nn 00` | Load picture `nn` / show it | Between the say and the shootout |
| `1c 67 xx 00` | Music: `fe` off, `12` the shootout theme | |
| `63 12 ss 00 lo hi` | Say message `lo hi` as speaker `ss` | Known from the scene builder |
| `f8 2e 04 00 xx 00` | Store `xx` at a fixed address (the shootout's parameter block) | Same form as the answer-field write |
| `4c` / `57` / `58 lo hi` | Return / end / jump within the script | |

The thirteen flag routines (A = +$048D … M = +$0519) each set two to five flags: A sets $0130, $0150, $0160; B
$01C0, $01D0, $0230, $01B0; C $0400, $0250; D $02B0, $0290, $0170, $0500, $04F0; E $0280, $01F0, $0560, $0540;
F $02A0, $0580; G $02C0, $0620, $0630, $0490; H $0550, $0440, $0460; I $0690; J $0680, $0880; K $08B0, $06A0,
$0660; L $0A60, $0760; M $0480, $04C0, $04D0. Which flag means what has not been mapped; the point of the
chain is that a chapter's entry calls every earlier routine, so the story state is what play would have left.

## What it is good for

- Any shootout or chapter in the emulator in about a minute, on the build and on the original side by side;
  this is how the `<82F5>` stall was reproduced and how the Ivan door path was walked (`docs/FINDINGS.md`,
  23 Sep).
- Checking a scene's English without playing to it: the landing screens above show Metal's arrival lines.
- Not a substitute for the story path: an in-scene shootout skips the scene's own transition, and a chapter
  entry sets the flags of the chapters before it but not the state inside the scene (Ivan is not home until
  the Freddy visit; the Shooting entries do not run the door dialogue).

## Two other things the scene holds

The debug scene also carries the game's memory-error and save dialogue (「メモリ不足です」, 「フォーマットエラー発生！」,
「セーブ、終了しました」, 「このままゲームを続けますか？」) and a two-entry menu ゲームを続ける / 終了する that the
retail game does reach — the save/quit path is served from here, which is why the scene is loaded at all and
why its English matters.
