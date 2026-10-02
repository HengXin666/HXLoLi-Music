# 02 歌词: 来源定级 + 标注 + 读音基准

三件事必须在同一步做完, 因为它们的错误会互相掩盖: **来源**错了行数就错, **标注**错了音拍数就错,
**读音**错了对齐会把错误均摊到整句. 这三样都错了的时候, 字幕看起来仍然"很正常".

## 2a 来源定级(一律从网络取)

```bash
hx-karaoke find_lyrics.py --project proj --title "<曲名>" --artist "<艺人>" --duration <完整版秒数>
```

产物 `lyrics.source.json`(来源级别 + URL + 行数 + 正文 sha256 + 时间列 sha256)= 门禁要查的证据.
**人工来源必须 `--why`**: 门禁区分不出"查过没有"和"懒得查", 所以缺 why 判 FAIL.

定序不许颠倒: **网络同步歌词 > 歌词站文本+时间轴 > 纯人工听写**.

**禁止从视频画面识别字幕**(截图 OCR / 看帧抄词)——抄到的是「这一份剪辑剩下的字」,
且小字混淆(し↔つ、は↔ば、促音脱落)出的错不会自己暴露. 门禁只接受 `network` / `manual` 两种级别.

## 2b 标注

按 `impl/format.md` 补逐字振假名与中文翻译. **振假名按汉字逐字标**, 不要整词标.

## 2c 读音基准: CTC 听音优先于词典

高风险词(熟字训 / 当て字 / 番剧专属词 / 长度 >3 的和语词)不能照抄词典读音 —— 歌手唱的是实际读音.
用 `ctc_read.py` 读"模型听到了什么"来定, 判据与实测案例见 `impl/reading-basis.md`.

```bash
hx-karaoke ctc_read.py stems/vocals16k.wav stems/ctc_lp.npz 71.5-76.0
```

(依赖第 04 步的人声与 ctc_lp; 顺序上先做 04 再回来做 2c 也可以. )

## 产物与过关条件

- `proj/lyrics.txt`(格式见 `impl/format.md`), `proj/lyrics.source.json`.
- 带 `[漢|よみ]` 的行占比 ≥ `--min-ruby`(默认 80%); `check_gates.py --stage design` 查这一条.
- 高风险词做过 CTC 读音响度核对; 未核对的词在交付说明里列出.

## 这一步要用的脚本

- `<skill>/scripts/find_lyrics.py` - 歌词来源 (lrclib 同步歌词打分 + 本地 lrc 配对 + 人工来源登记), 写 `lyrics.source.json`
- `<skill>/scripts/ctc_read.py` - 读模型听到了什么 (贪心假名 + 时间) 用来定读音; 本步只读不写
- `<skill>/scripts/check_lyrics_coverage.py` - 拿网络完整歌词反查本地漏句/空档处是否有人声, 写 `review/coverage.txt` (第 13 步门禁要它)

## 具体做法

- `impl/source-ladder.md` —— **定序、禁止画面识别、各源实测可用性、`source` 字段的坑**. 第 2a 步读.
- `impl/format.md` —— `lyrics.txt` 标注语法全表(振假名 / 熟字训 / 合いの手 / 英文和声). **写 lyrics.txt 之前读**.
- `impl/reading-basis.md` —— **读音基准**: 为什么词典不行、`ctc_read` 的判据与边界、三方互证顺序. 第 2c 步读.
