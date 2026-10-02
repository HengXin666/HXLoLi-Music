# 13 强制门禁与自动校验

## 只做这一件事

在出片之前, 用**会失败的检查**把"最容易被绕过"的步骤逐条确认一遍. 退出码非 0 = 不许进第 14 步.

## 13a 强制门禁(`--stage render`)

```bash
hx-karaoke check_gates.py --project proj --stage design                  # 进第 11 步设计之前
hx-karaoke check_gates.py --project proj --stage design --strict-design  # 新工程: 15 格缺项也 FAIL
hx-karaoke check_gates.py --project proj --stage render                  # 出片之前（追加时间轴/排版）
```

它查的是**文件在不在 + 内容够不够硬**, 不是"有没有做过样子":

| 强制项 | 缺了意味着 | 判据 |
|--------|-----------|------|
| `lyrics.source.json` | 不知道歌词是从哪来的, 网络源没查 | 来源级别只能是 `network`/`manual`(**画面截图识别不合法**); `manual` 必须带 `why` |
| `anime.background.json` | 没读番剧设定, 特效会退化成通用图形 | summary 非空且角色 ≥6 |
| `anime.notes.md` | 只交了角色表 = 没读作品在讲什么, 配色会从头就错 | **存在**且 ≥500 字(占位即 FAIL); 缺"内核/主题"或"与原作的关系"、或没写出处 → WARN |
| `anime.elements.md` + 设计表 | 母题没有白名单, 特效会退化成**通用图形** | 元素表**带来源计数**的条目 ≥4; 每句主母题必须指到表里条目, 否则须标「氛围句」, 且**氛围句占比 ≤35%** |
| 设计表 15 格 | 维度缺列: 副文本(注音/中文)从没被设计、句间没有任何量承接 | 列齐全且每格**要么填要么写 `—`**; `主·逐字`/`副·出现` 取值 ≥3 种; `副·逐字` 填写率 ≥50%; `承上` 与上一行 `启下` 同名 ≥60%; `背景·场景` 填写率 ≥70%. 默认 WARN, 新工程加 `--strict-design` 升 FAIL(见 `steps/4-kfx/42-text-main/impl/design-table.md`) |
| `lyrics.txt` 注音率 | 振假名没做完 | 带 `[漢\|よみ]` 的行 ≥ `--min-ruby`(默认 80%) |
| `offset.json` | 没测过网络歌词时间轴与这份视频的差量 | 中位差 + 离散度; verdict 写明通过的是哪条通道 |
| `timing.json` | 人工校时(第 08 步)没做 | 音拍数必须等于 `lyrics.txt` 的音拍数; 且相对 `timing_auto.json` **必须发生过修正** |
| `fixes.json` | 没看频谱 | 存在; 0 条修正也要写 `_why` 说明"这轮结论是没问题" |
| `calib.json` | 注音高度凭感觉 | 存在 |
| `review/health.txt` | 长音/间奏被算进了歌词, 字幕会慢几秒 | **判定行**里 CTC塌缩 = 0 且 句内间奏 = 0(不是"文件在就行") |
| `review/coverage.txt` | 歌词漏句(在成片里只是一段空白, 所有别的门禁都照常通过) | 由 `check_lyrics_coverage.py` 写; 退出码非 0 = 先补齐歌词 |

`check_lyrics_coverage.py` 单独跑法(第 02 步之后、设计之前):

```bash
hx-karaoke check_lyrics_coverage.py --project proj --vocals proj/stems/vocals16k.wav \
    --lyrics proj/lyrics.txt --timing proj/timing.json
```

**拿网络完整歌词反查本地有没有漏句**, 并检查歌词空档处是否有人声在唱.
这份报告必须落盘 —— 不落盘时"跑过且通过"和"没跑"在门禁眼里一样.

## 13b 自动校验

```bash
hx-karaoke validate_ass.py proj/out.ass --fontsdir fonts --timing proj/timing.json --report proj/validate.txt
hx-karaoke check_fx_visible.py proj/out.ass --fontsdir fonts --times 61,181,232    # 校验通过 != 看得见
```

`validate_ass.py`(必须"通过", 警告逐条过):

- [E] band 越界: fx/ly/card 事件包围盒(含缩放、旋转透视、边框、模糊、clip)超出 band
- [E] band 未登记 / 超出画面; [E] 字体缺失(只统计真正渲染文字的样式); [E] 时间非法
- [W] 歌词同屏重叠 >1.2s; [W] 音拍在高亮层无对应起点; [W] 事件密度过高(>900 同时事件); [W] 未标注 Name 的事件

`check_fx_visible.py`: validate_ass 只管越界、不管「画没画出来」.
实测踩过 clamp 仅 10 次(看着很守规矩)但整帧只有 35~1144 个亮像素的工程 —— **特效等于不存在, 而 validate 照样判通过**.
判据: 整帧 <2000 亮像素 = 太淡太小. 尺寸参照与透明度量级见 `impl/checklist.md`.

## 出片

烧好字幕的 MP4 走 `render_video.py`(见 `../15-render/index.md`), **不要用 ffmpeg 渲字幕** ——
它不支持 VSFilterMod 标签, `\1img` 会变成白块。

## 产物与过关条件

- `check_gates.py --stage render` 退出码 0(输出里是 `PASSED`, 不是"看着都做了").
- `validate_ass.py` 报"通过", 每条 WARN 有结论.
- `check_fx_visible.py` 所有采样时刻 ≥2000 亮像素.

## 这一步要用的脚本

- `<skill>/scripts/check_gates.py` - 强制门禁; 受保护步骤没做就直接 FAIL 退出 (`--stage design` / `render`)
- `<skill>/scripts/validate_ass.py` - 自动校验: band 越界 / 字体缺失 / 时间非法 / 重叠 / 密度
- `<skill>/scripts/check_fx_visible.py` - 单独渲染 FX 层数亮像素 - validate 只管越界, 不管画没画出来
- `<skill>/scripts/check_lyrics_coverage.py` - 与 02 步同一个脚本; 这里读它落盘的 `review/coverage.txt` 作为门禁证据

## 具体做法

- `impl/checklist.md` —— 自动校验项 + 人工目检项 + **20 条踩坑的「现象/原因/解决」**. 第 13~15 步随时查.
- `impl/overlap.md` —— **卡片/装饰与歌词重叠**的判据与修法(含"卡片时段怎么从无歌词区间反解"). 做卡片前后读.
