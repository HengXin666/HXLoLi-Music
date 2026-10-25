---
name: hx-anime-karaoke-ass
disable-model-invocation: true
description: >-
  为番剧 OP/ED/插曲 MV 制作字幕组级的卡拉OK 特效字幕 (ASS): 日文逐拍高亮 + 振假名 + 中文翻译,
  特效分五层 (主文本 / 副文本 / 卡点 / 背景 / 图片) 按画面与歌词含义逐句设计,
  并严格限制在字幕附近 (歌词块包围盒外扩 5%).
  覆盖: 找完整版 MV 与去水印, 歌词来源定级 (禁止从画面识别), 时间轴校准, 读音基准,
  人声分离, 音拍级强制对齐, 逐字歌词融合, 节拍网格, 频谱人工校时, 注音实测定位,
  原作内涵考据与元素表, 伴奏卡点表, 副文本通道清点, 五层特效设计, 抠图与图片嵌入,
  色彩系统, 句间关联, 门禁与自动校验, 真渲染器抽帧目检, 渲染出片.
  当用户要做卡拉OK字幕 / 特效歌词 / K轴 / ASS特效 / 歌词MV / 番剧OP/ED字幕 / 卡点特效 / 逐字特效时使用.
---

# 番剧卡拉OK 特效字幕 (ASS)

目标: 一条非常用心的字幕组做的, 堪比 PV 的特效歌词 ASS

歌词卡得准(每个音拍落在音符起音上), 排得稳(注音贴字, 中文不抢画面), 特效有意义(每句都能说出对应哪个镜头 / 哪句词义 / 番剧的哪个设定), 不越界(只在字幕附近 5%)

**交付物是 `out.ass` 这一个文件. ** MV 只是设计素材: 它告诉你"这一段画面在放什么", 用来定配色与时机; 成品字幕要被单独拿去用, 不跟 MV 绑定. 所以特效不许依赖 MV 里的元素存活  它得在任意底片上成立

先读 `shared/hard-rules.md`  跨步骤铁律, 违反任一条都要返工

**动手做任何设计之前, 先填 `proj/song-brief.md`**(番剧背景 / 歌曲纯歌词意境分析 / 歌曲在番剧背景下的分析 / 歌词特效), 并在进入 `4-kfx` 每一步时重读它. 它记的是**这首歌与作品的关系**  决定绘图元素与风格该取谁的. 判据见 `shared/hard-rules.md` 第 4b 条

写作一律遵守 `shared/hard-rules.md` 第 4c 条(STE 受控写作: 单句 ≤35/45 汉字, 每段 ≤6 句, **只用英文标点, 禁表情符号**), 单文件 ≤300 行(第 4d 条)

跑任何脚本一律 `hx-karaoke <脚本>`, 禁止裸 `python` 与 `uv run`

```bash
hx-karaoke --check            # 体检环境/字体, 缺什么会列出来
hx-karaoke scripts/setup/setup_env.py   # 缺什么补什么 (幂等)
```

工程一律放 `dev/<番名>/<歌曲名>/`, 做完搬到 `static/music/<番名>/` 并跑一次 `bash make.sh`; 详见 `steps/1-source/00-env/index.md` 的「工作区」与「发布」两节

脚本按职责分组在 `scripts/` 下, 每步契约点名要跑哪一个

| 目录 | 职责 | 代表脚本 |
|---|---|---|
| `scripts/setup/` | 环境、字体、算力设备 | `scripts/setup/setup_env.py` |
| `scripts/source/` | 找源、找歌词、番剧设定、镜头时间线、抠图 | `scripts/source/find_source.py` |
| `scripts/ctc/` | 音拍级 CTC 对齐与「模型听到什么」的读取 | `scripts/ctc/align_ctc.py` |
| `scripts/align/` | 偏移校准、人工修正、同步体检、人声分离 | `scripts/align/calibrate_offset.py` |
| `scripts/kf/` | 网络逐字歌词与本地行首锚点融合 | `scripts/kf/kf_timing.py` |
| `scripts/grid/` | 节拍网格、吸附、重复段对比、时间轴体检 | `scripts/grid/beat_grid.py` |
| `scripts/gate/` | 硬门禁与歌词覆盖审计 | `scripts/gate/check_gates.py` |
| `scripts/qa/` | 注音定位、越界校验、抽帧目检、频谱复核 | `scripts/qa/validate_ass.py` |
| `scripts/kfx/` | 音乐事件表、声部配色、KFX 自检打分 | `scripts/kfx/music_events.py` |
| `scripts/render/` | 真渲染器抽帧与出片 | `scripts/render/render_octopus.py` |
| `scripts/assfx/` | 生成器用的库(绘图/排版/层/素材), 见 `steps/4-kfx/49-generate/impl/library.md` | `scripts/assfx/draw/shapes.py` |
| `scripts/karetpl/` | **执行别人成品里的模板程序**(有 Comment 的 `code`/`template`/`karaoke` 行时用它), 见 `steps/4-kfx/50-reverse/impl/karetpl.md` | `scripts/karetpl/verify.py` |
| `scripts/reverse/` | **从无生成器的成品反推规格**(只有 Dialogue 时用), 见 `steps/4-kfx/50-reverse/impl/reverse-spec.md` | `scripts/reverse/reverse_opcn.py` |

## 这套 skill 是什么, 不是什么

**是**: 一条**可验证的流程骨架**  每一步有明确的输入、产物、判据与过关条件,
以及一批"踩过的坑"(每条都附实测数字). 判据告诉你**下限在哪**, 不告诉你上限长什么样

**不是**: 一份可以照抄的模板库. 步骤里的数字是**量级参照**, 不是目标值.
每一首歌的 BPM、段落结构、画面、母题都不同, **参数要从这首歌自己量出来**

所以每一步的做法都是: **先量 → 再决定 → 记下为什么**. 门禁只拦"没做"与"明显不合格", 不拦"你选了另一种做法". 觉得某条判据不适合这首歌时, 可以在产物里写明理由  但**不许因为"不好过"就把它删掉**

## 五组步骤

按顺序做. 每组一个目录 `steps/<组>/`, 组内每步一个子目录 `steps/<组>/<key>/`; `index.md` 是那一步的契约(只做什么 / 命令 / 判据 / 产物 / 过关条件), 同级 `impl/` 放本步可插拔的做法, 契约会点名何时读它

| 组 | 关心什么 | 组内步骤 |
|----|---------|---------|
| `1-source` | **素材筛选**: 环境与设备; 找完整版 1080p, 水印干净 | `00-env` `01-source` |
| `2-lyrics` | **歌词校准**: 来源定级 → 读音 → 偏移 → 人声分离 → 音拍对齐 → 逐字时间 → 节拍网格 → 人工校时 → 排版校准 | `02-lyrics` `03-offset` `04-vocals` `05-align` `06-kf-timing` `07-grid` `08-review-timing` `09-ruby` |
| `3-anime-bg` | **番剧背景调研**: 原作内涵考据 + 番剧元素表(带来源计数) | `10-anime-bg` |
| `4-kfx` | **字幕特效设计制作**: 全链路的重心, 十个子步骤; 见 `steps/4-kfx/index.md` | `40-music-events` `41-channels` `42-text-main` `43-text-sub` `44-beat` `45-bg` `46-image` `47-color` `48-thread` `49-generate` |
| `5-verify` | **门禁检验**: 硬门禁 + 自动校验 + 真渲染器抽帧目检 + **子代理盲审** + 封装出片 | `13-validate` `14-inspect` `15-render` `16-blind-review` |

`4-kfx` 是唯一被细分的组  前面三组产出的都是**输入**, 后面一组只做**拦截**, **观众能看到的东西全部产在 `4-kfx` 里**

## 一条关于渲染器的硬事实

本仓库的 ASS 由 **HXLoLi 定制版 libass** (SubtitlesOctopus WASM, 本 skill 内的副本在 `assets/octopus/`, 软链到 HX-Ass-Skill) 渲染, 原生支持VSFilterMod 扩展标签(`\1img` 图片纹理 / `\fsvp` / `\distort` / `\moves3` 等); **系统 ffmpeg 的 libass 不支持**, 遇到这些标签会**静默退化成纯色**, 不报错

所以抽帧目检与图片层验证**必须**走

```bash
hx-karaoke render_octopus.py proj/out.ass --probe               # 先体检
hx-karaoke render_octopus.py proj/out.ass --times 60,120,195 --out proj/review/shots/
```

用 `ffmpeg -vf subtitles=` 截图会得到与观众实际所见**不一致**的结论
