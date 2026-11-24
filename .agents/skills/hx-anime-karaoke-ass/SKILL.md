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
| `scripts/gate/` | 硬门禁, 歌词覆盖审计, 步骤契约体检 (`check_steps.py`) | `scripts/gate/check_gates.py` |
| `scripts/qa/` | 注音定位、越界校验、抽帧目检、频谱复核 | `scripts/qa/validate_ass.py` |
| `scripts/judge/` | 判断档与剧本产物 (镜头/歌词视觉化/定标/风格/剧本/发散) 的判据, 格式见 `shared/judge-formats.md` | `scripts/judge/check_judge.py` |
| `scripts/accept/` | 验收台后端: "好" 的冻结, G2 改代码核对 (deps.code), issues. 规则见 `steps/5-verify/12-station/impl/` | `scripts/accept/accept.py` |
| `scripts/selfreview/` | 自审: 增量抽帧, 意图盲审与专属性盲审, 重写预算. 规则见 `steps/5-verify/16-blind-review/impl/self-review.md` | `scripts/selfreview/selfreview.py` |
| `scripts/kfx/` | **唯一生成器 kfx**: 设计稿 `design.md` -> `out.kfx.ass`, 门禁, 金样自测; 另有音乐事件表、声部配色. 见 `scripts/kfx/kfx_README.md` | `scripts/kfx/kfx_build.py` |
| `scripts/render/` | 真渲染器抽帧与出片 | `scripts/render/render_octopus.py` |
| `scripts/studio/` | **验收台** (浏览器): 监视器 + 歌词面板选字 + 右键标注 (不行/好/换一个/批注 -> 工程 `review.jsonl`) + 检查器 + 时间线 (FX 0-8 语义轨, 标注轨) + 与参考对比, 见 `steps/5-verify/12-station/index.md` | `scripts/studio/server/app.py` |
| `scripts/assdoc/` | ASS 最小读写 (`assdoc.py`) 与单元清单/参数层 (`spec.py`), `accept/` `selfreview/` 共用 | `scripts/assdoc/spec.py` |
| `scripts/assfx/` | 旧逐句 fx 流程 (`make_ass.py`) 与验收台用的库(绘图/排版/层/素材); 新歌出片不用它, 用 kfx. 见 `steps/4-kfx/49-generate/impl/library.md` | `scripts/assfx/draw/shapes.py` |
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

契约骨架由脚本核对, 不靠自觉. 改了任何步骤契约后跑一次

```bash
hx-karaoke check_steps.py                  # 每步的四节, 产物, 脚本, 步骤引用都在
hx-karaoke check_steps.py --project proj   # 列出每步产物在不在, 报下一步
```

| 组 | 关心什么 | 组内步骤 |
|----|---------|---------|
| `1-source` | **素材筛选**: 环境与设备; 找完整版 1080p, 水印干净 | `00-env` `01-source` |
| `2-lyrics` | **歌词校准**: 来源定级 → 读音 → 偏移 → 人声分离 → 音拍对齐 → 逐字时间 → 节拍网格 → 人工校时 → 排版校准 | `02-lyrics` `03-offset` `04-vocals` `05-align` `06-kf-timing` `07-grid` `08-review-timing` `09-ruby` |
| `3-anime-bg` | **番剧背景调研**: 原作内涵考据 + 番剧元素表(带来源计数) + 作品设计圣经(符号专属度, 角色, 名场面, 逐句对位) | `10-anime-bg` `11-design-bible` |
| `4-kfx` | **字幕特效设计制作**: 全链路的重心, 十一个子步骤; 见 `steps/4-kfx/index.md` | `39-directions` `40-music-events` `41-channels` `42-text-main` `43-text-sub` `44-beat` `45-bg` `46-image` `47-color` `48-thread` `49-generate`; 旁路 `50-reverse` |
| `5-verify` | **验收台** + **门禁检验**: 浏览器标注 / 冻结 / 改代码核对 + 硬门禁 + 自动校验 + 真渲染器抽帧目检 + **子代理盲审** + 封装出片 | `12-station` `13-validate` `14-inspect` `15-render` `16-blind-review` |

`4-kfx` 是唯一被细分的组  前面三组产出的都是**输入**, 后面一组只做**拦截**, **观众能看到的东西全部产在 `4-kfx` 里**

## 出片: kfx, 本 skill 唯一的生成器 (2026-11-22 定, 蓝本 オンリー kfx3 v2.1)

**先读 `scripts/kfx/kfx_README.md` 的「已经踩过的坑」.** 不许另写生成器 (kara2-13, pvfx, kfx3 v4/v5 都因为这个被删了: 每次换一套, 用户认可过的版本反而重现不出来). 效果不够就给 kfx 加一个动作.

一首歌 = `lyrics.txt` + `timing.json` + `design.md`. 设计稿原文就是歌词, 每行在词上打补丁 `[词]{动作 动作}`, 写清色 / 意境 / 出场 / 为什么. 渲染器只照设计稿做, 设计稿没写的不出现; 改效果先改设计稿.

```bash
hx-karaoke kfx/kfx_build.py dev/<番>/<歌>                    # design.md -> out.kfx.ass; 设计稿不过校验退出码 2
hx-karaoke kfx/kfx_check.py dev/<番>/<歌>/out.kfx.ass --fonts static/music/<番>/fonts   # K1 标签 K2 越界(实渲染) K3 事件名
hx-karaoke kfx/kfx_test.py                                   # 改了 scripts/kfx/kfx_*.py 必须跑: オンリー 金样逐字节重现
python3 scripts/studio/server/app.py --port 5390              # 验收台: 一个服务挂 dev/ 下全部歌, 首页选歌, 每首一个标签页 /s/<番>/<歌>/
```

- 金样 `examples/mushoku_ed1/kfx/` = 用户认可的 オンリー v2.1. 金样变了就是用户认可的歌变了: 先给用户看, 同意后才 `kfx_test.py --bless`
- 验收台设计稿面板 (侧栏 "设计稿"): 跟随播放头显示当前行, 编辑一节保存 -> 服务端校验 -> 约 1-2 s 重建 `out.kfx.ass` -> 监视器热更新. 校验不过不重建, 错误显示在面板顶上
- 验收台的解析与重建在子进程里跑, 用的是磁盘上最新的 kfx 代码: 改了动作表不用重启台子. 有人在看的歌, 设计稿一改 (面板或文件) 就自动重建; 只改了 kfx 代码时首页标「待重建」, 点一下用新代码重建 (几首歌共用 kfx, 不悄悄改别的歌的成品; 工程 `studio.json` 写 `"auto_rebuild": "all"` 可让代码一改也自动重建)
- 只用标准 libass 标签, 系统 ffmpeg 抽帧就是观众所见

## 做一首新歌的方法 (2026-11-23 沉淀, 蓝本 ときめき v11)

skill 是方法, 不是模板. 下一首歌学的是下面的顺序与判据, 不抄上一首的动作与数值.

0. **先读 `shared/reference-library.md`.** 本地二十多份特效 ASS 的来源分类 (人做 / 人做再拓写 / 照搬别歌 / AI 第一代 / kfx / 草稿), 人做的好在哪, AI 做坏过哪里. 人做的共同点: 一个贯穿全曲的主题物件框在句子上, 分段换一套颜色与动作, 按演唱者或段落配色, 词级意象只给少数词, 动的只有正在唱的字.

1. **先调研, 再设计.** 读这首歌和作品: ED/PV 逐段画面 (`kfx_art.py scenes` 出接触表), 歌词词义, 角色, 官方评论. 写进 `design.md` 的「立场」与「意象」, 每个意象写出处. 换到别的歌也成立的意象 (心, 花瓣, 星光, 茶杯) 不算意象.
2. **定一道主菜.** 每首歌只有一个全曲高潮的大事 (オンリー = 大斩, ときめき = 齐舞 + 魔晶板框). 先看那一刻的画面再定. 抖动, 蹦, 亮只是配菜. 主菜要大, 要一眼看懂, 但不照搬别人的歌 (用户: 像点兔那样有大事, 但不抄).
3. **歌词首先是要读的.** 字序永远不变 (门禁 `order_errors`); 不压字, 不盖字; 唱的时候读得清. 被否决过: 换位 (逆序吓人), 双行版式, 跟着单字伸缩的框.
4. **默认不放字外物象.** 物象 (粒子, 道具, 小图) 只在用户要时加, 少, 小, 番里认得出, 全部踩拍. 过路物象和背景重复, 用户说生硬, 乱 (2026-11-23 全部撤掉). 要放时学人做的: 一个主题物件固定在句子两端或句首, 随句子出入 (ファティマ 的齿轮, ポポロン 的钟表), 不在画面里飘.
5. **全部卡点.** 先 `kfx_sync.py beats` 出拍网格, 出场, 换形, 收尾都落在拍上 (重拍更重). `kfx_sync.py lag` 自查哪句字慢, 自己判断自己修, 不把 "慢在哪" 抛给用户.
6. **框, 盒子, 底板照市面做法.** 学下三分之一标题框: 框 = 字的墨迹 (`kfx_ink.py` 从字体文件量, 含注音与合成斜体) + 四边留白, 竖向 = 横向 x 0.7. 框是播一句的屏幕, 唱时不动, 换句在开唱拍 ease-out 换形. 进场是级联 (先角, 再边, 最后点缀), 出场比进场快 (ease-in). 华丽靠拍上的光扫与小幅点头, 不靠闪烁与旋转.
7. **动手前先写清 "这个东西是什么".** 一句话定义 (例: 框 = 播这一句的屏幕). 定义说不清就别写代码. 定义写进动作的 docstring, 再写成自审断言 (违反就报错, 不出片).
8. **交付前自己看图.** 每次改完用真渲染出带时间戳的拼图 (进场, 唱中, 换句, 收尾, 每个高潮各一组), 自己逐帧看过, 回复里写看了哪几处, 还剩什么拿不准. 截图没看过不交付.
9. **门禁不降.** 改 `scripts/kfx/` 必须过 `kfx_test.py` (金样逐字节) 与 `kfx_check.py` (越界 5%); 坑写进 `kfx_README.md` 并写为什么. 验收台保持开着 (一个服务挂全部歌), 用户随时能实时看.
10. **重做旧歌先备份.** 原 ASS 与旧生成器拷到工程 `backup-<日期>-<旧流程名>/`, 发布目录 `static/` 只在用户认可后覆盖.

## 改成品用验收台, 不要整首重跑碰运气

随机数按单元 key (句子文字哈希) 取种子, 只换一句的随机本来就成立. 用户在验收台上看成品、标问题, agent 按单元改生成器:

```bash
python3 scripts/studio/server/app.py --port 5390                   # 浏览器验收台 (全部工程), 标注写进各工程 review.jsonl
python3 scripts/studio/server/app.py --project <工程> --port 5199   # 只看一首 (旧用法, 仍可用)
hx-karaoke accept/accept.py init .                                 # v3: "好" 的冻结 + 改代码核对 (G2)
```

不行就改这一句对应的 fx 函数 (`accept.py where` 指到函数与源文件), 好就冻结, 改完 `accept.py verify` 核对没有波及别的单元. 详见 `steps/5-verify/12-station/index.md`

## 一条关于渲染器的硬事实

本仓库的 ASS 由 **HXLoLi 定制版 libass** (SubtitlesOctopus WASM, 本 skill 内的副本在 `assets/octopus/`, 软链到 HX-Ass-Skill) 渲染, 原生支持VSFilterMod 扩展标签(`\1img` 图片纹理 / `\fsvp` / `\distort` / `\moves3` 等); **系统 ffmpeg 的 libass 不支持**, 遇到这些标签会**静默退化成纯色**, 不报错

所以抽帧目检与图片层验证**必须**走

```bash
hx-karaoke render_octopus.py proj/out.ass --probe               # 先体检
hx-karaoke render_octopus.py proj/out.ass --times 60,120,195 --out proj/review/shots/
```

用 `ffmpeg -vf subtitles=` 截图会得到与观众实际所见**不一致**的结论
