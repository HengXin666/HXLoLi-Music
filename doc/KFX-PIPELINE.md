# KFX 制作链路

从「一首歌的音频」到「带日语注音的双行卡拉OK ASS」的完整步骤。
这条链路**不是自研**，是复用 `~/Loli/code/HX-Music/pyTool` 已有的实现
（HX-Music 项目，作者 Heng_Xin），本仓库只补充**对齐检测**与**可读性门禁**。

---

## 全流程

| 步 | 做什么 | 用什么 | 产出 |
|---|---|---|---|
| 1 | 抓歌词 | LDDC (`pyTool/LDDC`) 搜 QQ音乐 | 带逐字 `\kf` 时间的 ASS |
| 2 | **对齐检测** | `py/ass/check_align.py`（本项目新增） | 偏移量 / 尾部余量 |
| 3 | 日语注音 | `pyTool/src/mark/jpMark.py` (pykakasi) | 汉字→假名对照 |
| 4 | 注音嵌入 k 帧 | `pyTool/src/mark/AssMark.py` | 带注音的 k 帧行 |
| 5 | 双行卡拉OK样式 | `set-karaoke-style.lua` | 样式表 |
| 6 | 应用卡拉OK模板 | `kara-templater.lua` + aegisub-cli | 成品 ASS |
| 7 | **可读性门禁** | `py/ass/check_contrast.py`（本项目新增） | 对比度是否达标 |

第 2 与第 7 步是本项目加的，其余复用现成实现。

---

## 第 1 步：抓歌词

LDDC 已内嵌在 `pyTool/LDDC`，不需另装。**注意它依赖 PySide6**（原本是 GUI 程序）。

```python
from LDDC.common.models._enums import SearchType, Source, LyricsFormat
from LDDC.core.converter import convert2
from LDDC.core.api.lyrics import search, get_lyrics

lst = search(Source.QM, "果てなき風の軌跡さえ", SearchType.SONG)
song = next(s for s in lst if s.id == 108986347)
lyric = get_lyrics(song)
assText = convert2(lyric, ["orig"], LyricsFormat.ASS)
```

**它给的是逐字时间**，形如：

```
Dialogue: 0,00:00:01.17,00:00:06.59,orig,,0,0,0,,{\kf130}人{\kf65}の{\kf52}儚{\kf96}さ...
```

**校验方式**：LDDC 给出的 `人の儚さを断つため` = 1.17–6.59，
与从本地源文件反解出的时间**逐字一致** → 时间轴可信。

**已知坑**：`g2p_en` 需要 nltk 语料（`cmudict` 等），下载可能被网络策略拦截
（`SSRF attempt to restricted IP`）。它只服务「英语词→片假名」，
纯日语歌曲可以先 stub 掉：

```python
import sys, types
fake = types.ModuleType("g2p_en")
class G2p:
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return []
fake.G2p = G2p
sys.modules["g2p_en"] = fake
```

---

## 第 2 步：对齐检测（本项目新增）

**为什么要这一步**：抓来的歌词时间是「那份音源」的时间，
本地音频可能不是同一份  常见的三种偏差：

1. **整体偏移**：音频开头多了前奏/空白，所有时间要整体加减
2. **尾部多余**：音频末尾多了静音或附加内容，歌词本身没错
3. **音源不同**：翻录/不同编曲，歌词根本对不上

靠耳朵听不出来，必须量。`py/ass/check_align.py` 做这件事：

```bash
.venv/bin/python py/ass/check_align.py --ass lyrics.ass --audio song.mp3
```

实测样例（东方这首歌）：

```
音频首次有声      110 ms
整体偏移 = -110 ms   -> 对齐良好
音频最后有声   259890 ms
歌词末句结束   240120 ms
尾部余量 27230 ms    -> 音频末尾多出 27.2 秒
结论: 音频 267.4 秒 vs 歌词跨度 240.1 秒, 差 27.2 秒
```

**判读规则**：

| 判据 | 阈值 | 结论 |
|---|---|---|
| \|整体偏移\| | < 300 ms | 对齐良好 |
| \|整体偏移\| | 300 ms ~ 2 s | 轻微偏移，整体平移校正 |
| \|整体偏移\| | > 2 s | 明显偏移，需人工确认是否同一音源 |
| 尾部余量 | > 1 s 且最后有声 < 歌词末句 | 音频带静音尾巴，**不用改歌词** |
| 尾部余量 | > 1 s 但最后有声 > 歌词末句 | 音频有额外内容，需裁剪或补歌词 |

**关键区分**：尾部余量大 **不等于** 歌词错。
要看「音频最后有声」和「歌词末句」谁更靠后  只有当有声内容超出歌词时才是真问题。

---

## 第 3–4 步：日语注音

`JpMark.convert(text)` 返回 `[(原文块, 假名)]`：

```
人の儚さを断つため -> 人[にん] の[の] 儚[ぼう] さを[さを] 断つ[たつ] ため[ため]
```

`AssMark.mark(带k帧的行)` 把注音切分并按时间嵌入：

```
输入: {\kf25}人{\kf25}の{\kf14}儚...
输出: {\k12}人|<に{\k13}#|<ん{\k25}の{\k7}儚|<ぼ{\k7}#|<う...
```

**符号含义**：`|< ` 是注音分隔符，`#` 表示假名延续（同一汉字的后续音节）。
`_markKanJi` 用 `_distributeEvenly` 把该字的时间平均分给它的各个假名。

**已知问题（原作者也承认）**：`pykakasi` 是词法分析器，会误读。
例：`あの日` 会读成 `にち` 而非 `ひ`。作者用 `JpMark._fixReadings` 打补丁，
但那是**特化修复**，不是通用解。遇到错误读音需要在 `_fixReadings` 里加规则。

---

## 第 5–6 步：双行样式 + 应用模板

两者都走 `aegisub-cli`（`pyTool/src/utils/callLua.py` 已封装）：

```python
callSetKaraokeStyleLua(assPath, outPath, "orig")        # 双行样式
callApplyKaraokeTemplateLua(assPath, outPath)           # 应用模板
```

**注意**：`callLua` 强制加载 `src/data/empty.mp4` 作为 `--video`，
注释写着「必须要加载视频, 否则有bug」。

---

## 第 7 步：可读性门禁（本项目新增）

配色见 `doc/KFX-RULES.md`，检查器 `py/ass/check_contrast.py`。

**参考实现的做法**（`pyTool/main.py` 的 `_addSy01`）：
主填充 `&H00FFFFFF`（白）+ 描边 `&H00000000`（黑），
符合"描边必须比中灰更暗"这条规则。

---

## 附录：pyTool 的样式体系

它在 `_addSy01` 里预置了 10 个样式，成对出现（正文 + 注音）：

| 正文样式 | 注音样式 | 对齐 | 用途 |
|---|---|---|---|
| K1 | K1-furigana | 1 | 上方第一行 |
| K2 | K2-furigana | 3 | 上方第二行 |
| K3 | K3-furigana | 5 | 上方第三行 |
| K4 | K4-furigana | 7 | 上方第四行 |
| noK | noK-furigana | 2 | 非卡拉OK（下中） |

正文 80px，注音 40px。对齐值 1/3/5/7 分别是左下/左中/左上/左上偏  靠 `set-karaoke-style.lua` 再调整。
