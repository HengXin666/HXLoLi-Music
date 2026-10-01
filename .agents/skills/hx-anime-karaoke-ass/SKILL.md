---
name: hx-anime-karaoke-ass
disable-model-invocation: true
description: >-
  为番剧 OP/ED/插曲 MV 制作"字幕组/PV 级"卡拉OK 特效字幕（ASS）：日文逐拍高亮 + 振假名 + 中文翻译，
  特效用 \p 矢量绘图按画面与歌词含义逐句设计，并严格限制在字幕附近（歌词块包围盒外扩 5%）。
  流程按 steps/ 编号推进：找完整版 MV 与去水印、歌词来源定级（一律网络，禁止从画面识别）、
  语音时间轴校准、读音基准（CTC 听音优先于词典）、人声分离、CTC 音拍级强制对齐、
  网络逐字歌词融合、节拍网格、频谱人工校时与时间轴体检、振假名实测定位、
  原作内涵考据（bgm.tv + 萌娘百科 + 六类检索）与番剧元素表、逐句特效设计、生成、
  强制门禁与自动校验、抽帧目检、渲染出片。
  当用户要做"卡拉OK字幕/特效歌词/K轴/ASS特效/歌词MV/番剧OP/ED字幕"时使用。
---

# 番剧卡拉OK 特效字幕（ASS）制作手册

目标：一条完整 MV + 一份 ASS，歌词**卡得准**（每个音拍落在音符起音上）、**排得稳**（注音贴字、中文不抢画面）、
**特效有意义**（每句特效都能说出"对应哪个镜头/哪句词义/番剧的哪个设定"）、**不越界**（只在字幕附近 5%）。

所有脚本在 `scripts/`，工程在工程目录（`proj/`）。**一律用 `uv run`，不要裸 `python`**：
uv 按脚本的 inline 依赖元数据自建环境。**先读 `shared/hard-rules.md`** —— 十条跨步骤铁律，违反任一条都要返工。

## 步骤表（按顺序做，每个 `index.md` 是那一步的契约）

| # | 步骤 | 关心什么 | 契约 | 产物 |
|---|------|---------|------|------|
| 00 | setup | 字体与算力设备 | `steps/00-setup/index.md` | `<skill>/fonts/`、设备等价性结论 |
| 01 | source | 完整版 1080p、水印干净 | `steps/01-source/index.md` | `base.mp4` |
| 02 | lyrics | 来源定级 + 标注 + 读音基准 | `steps/02-lyrics/index.md` | `lyrics.txt`、`lyrics.source.json` |
| 03 | offset | 网络时间轴与这份视频差多少 | `steps/03-offset/index.md` | `offset.json` |
| 04 | vocals | 分出人声与伴奏 | `steps/04-vocals/index.md` | `stems/vocals16k.wav`、`inst.wav` |
| 05 | align | CTC 音拍级强制对齐 | `steps/05-align/index.md` | `timing_auto.json` |
| 06 | kf-timing | 网络逐字定形状 + 本地定平移 | `steps/06-kf-timing/index.md` | `timing_kf.json`、`review/kf-report.md` |
| 07 | grid | 节拍网格与吸附（可选 07b 重对齐） | `steps/07-grid/index.md` | `grid.json`、`timing_snap.json` |
| 08 | review-timing | 人工校时 + 时间轴体检（会非零退出） | `steps/08-review-timing/index.md` | `timing.json`、`fixes.json`、`review/health.txt` |
| 09 | ruby | 注音高度实测 | `steps/09-ruby/index.md` | `calib.json` |
| 10 | anime-bg | 原作内涵 + 番剧元素表 | `steps/10-anime-bg/index.md` | `anime.background.json`、`anime.notes.md`、`anime.elements.md` |
| 11 | design | 逐句特效设计 | `steps/11-design/index.md` | `design-table.md` |
| 12 | generate | 把设计表翻译成生成器 | `steps/12-generate/index.md` | `out.ass` |
| 13 | validate | 门禁 + 自动校验 + 可见性 | `steps/13-validate/index.md` | `check_gates` / `validate` / `fx_visible` 报告 |
| 14 | inspect | 抽帧目检（校验通过不等于看得下去） | `steps/14-inspect/index.md` | `review/*.jpg` 拼图 |
| 15 | render | 封装出片 | `steps/15-render/index.md` | 成片 mkv |

步骤内可插拔的做法（多种写法/多套判据）放在那一步的 `impl/` 下，`index.md` 会点名什么时候读哪个。

## 三条贯穿全程的机器判据

1. **`steps/13-validate/index.md` 的门禁表**：每个"不许跳"的步骤都对应一个**会失败**的检查，
   而不是"看起来做了"。`check_gates.py --stage render` 退出码非 0 = 不许渲染。
2. **`shared/hard-rules.md` 第 5 条（band 铁律）**：任何跑出 band 的内容都是垃圾，一律不许交。
   这条被"为了效果更好看"说服过很多次，每次都是错的。
3. **`shared/hard-rules.md` 第 10 条**：skill 目录不带任何一次运行的痕迹。
   工程产物（lyrics/timing/烧好的图形/SVG 缓存/成片）一律在工程目录，不进 skill。

## 库与脚本

`steps/12-generate/impl/library.md` 是 `scripts/assfx/` 的逐模块说明，**写生成器之前读它**。
下面按步骤列脚本；每个脚本的完整参数在它自己的 docstring 顶部。

- `scripts/find_source.py` —— 第 01 步多源搜 MV（B 站 API + YouTube），按时长/分辨率/翻弹打分。
- `scripts/find_lyrics.py` —— 第 02 步歌词来源（lrclib 同步歌词打分 + 本地 lrc 配对 + 人工来源登记）。
- `scripts/ctc_read.py` —— 第 02c/07b 步读「模型听到了什么」（贪心假名 + 时间），定读音与查对齐。
- `scripts/calibrate_offset.py` —— 第 03 步语音校准（能量起音法 / `--ctc`），产出 `offset.json`。
- `scripts/separate_vocals.py` —— 第 04 步人声分离（demucs htdemucs_ft）。
- `scripts/align_ctc.py` —— 第 05 步音拍级强制对齐，产出 `timing_auto.json` 与 `ctc_lp.npz`。
- `scripts/kf_timing.py` —— 第 06 步逐字准确率第一手段：`fetch` / `align` / `verify`。
- `scripts/beat_grid.py` —— 第 07 步从伴奏测节拍网格。
- `scripts/snap_timing.py` —— 第 07 步音拍起点吸附到网格（`--lag` 补偿 CTC 延迟）。
- `scripts/grid_align.py` —— 第 07b 步快歌/齐唱网格约束重对齐（`--parity` 副歌联合）。
- `scripts/parity_cmp.py` —— 第 07b 步对比重复段相对节奏（差 >0.12s 标 `<<`）。
- `scripts/review_spectrogram.py` —— 第 08a 步渲频谱图逐句核对音拍起点。
- `scripts/apply_fixes.py` —— 第 08a 步把 `fixes.json` 应用成终稿 `timing.json`。
- `scripts/check_sync.py` —— 第 08b 步同步体检（A 字幕早了 / B 起音晚 / C 有音无拍）。
- `scripts/check_lag.py` —— 第 08b 步量"字幕比人声慢多少"；**判据见 `steps/08-review-timing/impl/lag-verdict.md`**。
- `scripts/check_timing_health.py` —— 第 08c 步时间轴体检，**退出码非 0 就是拦路**。
- `scripts/check_lyrics_coverage.py` —— 第 02 步之后查漏句/空档是否有人声，报告落到 `review/coverage.txt`。
- `scripts/calibrate_ruby.py` —— 第 09 步实测注音/中文的墨迹位置，产出 `calib.json`。
- `scripts/fetch_anime_bg.py` —— 第 10 步抓 bgm.tv 条目 summary 与角色中文简介。
- `scripts/check_gates.py` —— 第 13a 步强制门禁；受保护步骤没做就直接 FAIL 退出。
- `scripts/validate_ass.py` —— 第 13b 步自动校验（越界/字体/时间/重叠/密度）。
- `scripts/check_fx_visible.py` —— 第 13b 步单独渲染 FX 层数亮像素，太淡就失败。
- `scripts/snapshots.py` —— 第 14 步抽帧目检拼图（`--bands` 画出 band 框）。
- `scripts/fetch_fonts.py` —— 第 00 步装字体（OFL，不进 git）。
- `scripts/device.py` —— 第 00 步 torch 设备选择（默认 auto：有卡用 GPU，OOM 退回 CPU）。
- `scripts/device_check.py` —— 第 00 步实测 GPU/CPU 的对齐差异，决定终稿用哪台设备。
- `scripts/render.sh` —— 第 15 步封装成 MKV（视频原样封装 + ASS 外挂轨 + 字体附件）。默认走这条。
- `scripts/render_burn.sh` —— 第 15 步出烧录 mp4（目标场景不支持外挂字幕时用）。
- `scripts/shape_gallery.py` —— 想先看图形库长什么样时跑它，重新生成 `steps/11-design/shape_gallery.png`。
- `scripts/assfx/bake_shapes.py` —— 把网络图标烧成实心路径；**`--out` 必须指向工程目录**。

## 示例与模板

- `templates/make_ass_template.py` —— 最小可运行生成器（两句示例特效 + 自动衔接窗口）。复制到工程后改三处：
  `ASSFX` 路径、`PHRASES`、`fx_xxx` 函数。
- `examples/mushoku_ed1/` —— 無職転生 ED1「オンリー」完整工程（30 句逐句设计、71 处人工校时 fixes、
  标题/片尾卡、`anime.notes.md` 与 `anime.elements.md` 的合格样本）。**这是唯一保留的示例**，
  其余历史工程在 `static/music/<番名>/` 下（属工程，不属 skill）。

## 交付物

成片 **mkv**（视频原样封装 + ASS 外挂轨 + 字体附件）、`out.ass`、
工程（`lyrics.txt` + `lyrics.source.json` + `anime.background.json` / `anime.notes.md` / `anime.elements.md`
+ timing / fixes / calib / `make_ass.py` / `design-table.md`）、
`check_gates.py` 与 `validate_ass.py` 的报告、目检拼图。
需要烧录版时用 `scripts/render_burn.sh` 另出一份 mp4。
