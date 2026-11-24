# 49 生成 ASS

## 只做这一件事

把前面九步(40~48)的结论写进设计稿 `proj/design.md`, 用 kfx 跑出 `proj/out.kfx.ass`

## 命令

唯一做法: 写 `proj/design.md`, 用 kfx 出片. 格式, 动作表, 踩过的坑见 `scripts/kfx/kfx_README.md`

```bash
hx-karaoke kfx/kfx_build.py proj                       # -> proj/out.kfx.ass
hx-karaoke kfx/kfx_check.py proj/out.kfx.ass --fonts <字体目录>
```

不许另写生成器. 下面「五层的调度」以后的内容是旧逐句 fx 流程 (`make_ass.py`) 的说明, 只在维护旧工程时读

## 五层的调度(本步的核心)

五个层**各有各的时钟**, 不要写成"一个循环里依次画五遍"

| 层 | 时钟 | 在哪调度 |
|---|---|---|
| 主文本 / 副文本 | 人声音拍, 逐句 | `Generator.render()` 的逐句循环里 |
| **卡点** | 音乐事件网格 | **独立循环**, 按 `music-events.json` 的 grid 走, 不跟句 |
| **背景** | 镜头切换 | **独立循环**, 跨句连续铺 |
| 图片 | 卡点时刻 | 在卡点循环里插点 |

卡点与背景**不能用 `k.t_in / k.t_end` 当区间**  那等于又跟着句子走了. 它们要按自己的时间轴遍历全曲

```python
# 卡点层: 按音乐段落遍历, 不按句子
for (t0, t1, lv) in music_sections(ME):          # 由 ME.section / ME.level() 切
    beat_scatter(fx_for_section, ME, t0, t1, level=lv, colors=palette_for(t0))
```

## 库负责什么, 你负责什么

- `assfx.layer.gen.Generator` 负责**逐句出入场窗口规划**、`band()` 登记、`card()` 卡片
- 你只写 `fx_xxx(f, ph, k)` 函数, **只通过** `f.shape / f.text / f.burst / f.drift / f.pulse / f.glow / f.floor_spin` 发射
- 合いの手行**不放进 PHRASES**, 在所属句的 fx 函数里用 `TM` 中 `call` 音拍时间触发
- **句内多色**走 `Karaoke` 的 `hl_color` 回调(库早就支持, 见 `assfx/text/color.py` 的 `make_hl_color`)
- **句间承接**是跨句状态: 生成器里维护一个 `carry` 对象, 逐句把"留在右缘的颜色/位置/动量"传下去  现在 `Generator.plan()` 只规划"别叠字", 不传任何状态, 所以每句都从零重起(见 `../48-thread/index.md`)

```python
G = Generator(doc, L, lines, TM)      # lead=0.8：最早提前 0.8s 入场
G.render(PHRASES, FXMAP)              # 打印每句 in/out/band/clamp
G.card("title", 1.0, 6.0, items, fx)  # 卡片 band 自动 = 文字墨迹 + 5%
```

## 接入清单 (给 12 验收台的单元定位与参数层)

`Generator.render()` 会在 `out.ass` 旁写 `out.manifest.json`: 每句一个单元, 带参数, 默认值与 schema. 验收台 (`accept.py`, `scripts/studio`) 据此按单元定位与核对, 不再整首重跑. 生成器侧再做几处:

- 主题写成有名字的色组: `register_theme("SUN", TH(...), why="...")`. skill 自带一批起点 (`scripts/assfx/presets/themes.json`)
- 配方加 `@recipe(why=..., knobs=[knob(...)])`, 配方里的内容量用 `f.opt("名", 默认)` 读
- 卡点/背景/图片按段取参数: `p = G.segment("beat", t0, t1, BAND_ALL, level=lv, family=fam)`, 种子用 `seed_parts(..., salt=p["salt"])`, 旋钮用 `f.set_knobs(p["knobs"])`
- `G.inputs(HERE, "timing.json", "lyrics.txt", "calib.json", "fixes.json")`: 上游变了能标过期
- PHRASES 每项写 `label="画面时间点: 内容"`, `accept.py units` 与验收台检查器显示它

模板已按这几处写好. 不接入也能出片, 只是验收台没法按单元定位与做隔离核对. 字段与开放范围见 `../../5-verify/12-station/impl/manifest.md`

**生成器必须确定**: 同样的输入与覆盖, 两次输出逐字节相同. 不许用 `random` 的全局状态, 不许读时间, 句与句之间不许藏可变的全局状态. `accept/selftest_accept.py` 的 "追踪开/关输出逐字节相同" 验这一条; 不确定时 `accept.py verify` 的隔离核对也过不了

## 读出生成器的打印

每句会打印 `in / out / dout / band / fx / clamp`. **clamp 很多说明特效设计尺寸超出 band  应主动缩小, 而不是依赖夹取. ** band 只是上限不是目标尺寸: 实测某工程 clamp 仅 10 次(看着很守规矩), 但图形尺寸只有同款的 1/10, FX 层单独渲染时整帧只有 35~1144 个亮像素, **特效等于不存在**

## 卡片

只做【开头】与【片尾】两张, 利用黑场与长前奏/尾奏. **除这两张之外不要在歌词之间插任何文字**  尤其"间奏卡""序章卡", 本质是在歌词停顿时塞旁白, 且极易与相邻歌词行的时间窗互撞(实测撞出 6.8s 重叠). 卡片时段必须**从"无歌词区间"反解出来**, 不要手填, 见 `../../5-verify/13-validate/impl/overlap.md`

字体上, 卡片是唯一**鼓励多字体**的地方(曲名/制作名单/片尾): 用户 2026-10-03 「副头的, 就是说这个歌名啊, 谁制作的呀…这个你可以用很多种字体不同的大小」. 正文则相反: **一般不要一行一个不同字体**

## 产物与过关条件

`proj/out.ass` 与 `proj/out.manifest.json`; 每句的 band 已登记、事件 Name 标注 `ly:<band>` / `fx:<band>` / `card:<name>`; `clamp` 计数逐句过一眼

生成器写完后登记 `proj/bible/landing.json`: 每个专属符号落在哪个 fx 函数, 哪几句, 函数体里哪段字面量画它. 至少 3 个专属符号要走通追溯链 (格式见 `../../3-anime-bg/11-design-bible/impl/formats.md`):

```bash
hx-karaoke judge/check_bible.py --project proj --stage landing   # 追溯链 + 盲审认出率
hx-karaoke judge/check_bible.py --project proj --trace           # 打印 符号 -> 来源 -> fx -> 句
```

## 模板与参考工程

- `<skill>/templates/make_ass_template.py`  最小可运行生成器, 本步的起点. 它的 docstring 写了要改的三处
- `<skill>/examples/mushoku_ed1/`  唯一保留的完整工程(33 句逐句设计 + 人工校时 `fixes.json` + 标题/片尾卡 + 合格的 `anime.notes.md`; 2026-11-12 换成 オンリー 定稿快照). **卡住时读它的 `make_ass.py`** (逐句设计表 `PHRASES`、字层预设 `P()`、高光集合 `HIGH`、氛围床包装 `_bedded`; 公共场景在 `scene.py`, 承载与留白句在 `fx_carry.py`, 高光句在 `fx_high.py`, 逐句主母题 `pNN` 在 `fx_main.py`, 氛围床与逐字命中在 `fx_bed.py`, 图片母题在 `motif_img.py` + `assets/motif.json`, 色相与角色色在 `judge/hue.json` / `judge/style.json`, 卡片在 `cards.py`), 不要重新发明写法. 它按 `examples/<曲目>/` 上两级定位本 skill 的 `scripts/`, 直接跑即可; **在工程区(dev/)里的生成器不要抄这个相对层数**  工程会在 dev/ 与 static/ 之间搬家, 层数会变; 统一用 `ASSFX` (hx-karaoke 会导出) 取 scripts、`$(hx-karaoke --fonts)` 取字体, 见 `../../1-source/00-env/index.md` 的「工作区」一节. **除这一份示例之外, skill 内不再有可参照的工程**; 别的目录(含 `dev/` 下的历史工程) **一律不许去读**  见 `shared/hard-rules.md` 第 10 条
