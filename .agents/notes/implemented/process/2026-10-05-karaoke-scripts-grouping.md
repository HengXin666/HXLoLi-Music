# Agent Note: hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开

Status: implemented

Decision-ID: karaoke-scripts-grouping

- 决策依据: `hx-make-skill` 的 `references/code-quality.md`（C1 一个目录 ≤6 文件 / C2 单文件 ≤300 行 /
  C4 连续注释 ≤10 行）；用户指令「把 skill 改到满足代码质量门禁，并同步所有调用方」
- 相关: [karaoke-steps-restructure](2026-10-02-karaoke-steps-restructure.md)（按步骤切文档）、
  [karaoke-kf-line-pairing](2026-10-02-karaoke-kf-line-pairing.md)（`kf_timing.py` 的融合算法本身）

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/align/check_sync.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/asset/props.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/base/core.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/deco/line.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/draw/image.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/draw/kit/prims.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/layer/fx.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/layer/music/bg.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/text/anim.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/ctc/emis.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/gate/gates_meta.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/grid/beat_grid.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/karetpl/lua.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/kf/pool.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/kfx/voices.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/kfx/score/score_ass.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/qa/check_lag.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/render/octo_probe.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/reverse/gen_opcn.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/setup/env.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/source/cutout.py`

## Problem

门禁实测 21 条违规，根因是两件事：**目录平铺** 与 **单文件过长**。

1. `scripts/` 顶层 37 个文件、`scripts/assfx/` 20 个文件、`steps/4-kfx/42-text-main/impl/` 9 个文件，
   都超过「一个目录 ≤6 文件」。37 个脚本平铺时，`hx-karaoke --help 的可用列表` 本身就无法一眼看完，
   而且**时间轴类**（`align_ctc` / `kf_timing` / `grid_align` / `snap_timing`）与**校验类**
   （`check_*` / `validate_*`）混在一起，找"这一步该跑哪个"只能靠文档点名。
2. 9 个文件超 300 行，最大 `kf_timing.py` 848 行、`assfx/shapes.py` 753 行。
   它们不是"注释太多" 而是各自装了两三件不相关的事（`kf_timing.py` 里有 CLI、
   形状计算、全局池兜底；`shapes.py` 里有几何基础、自然物、战斗物、道具）。

## Decision

**先按职责归组，再按职责拆模块**，并用一个入口层吸收路径变化：

- `scripts/` 分 11 组：`setup/` `source/` `ctc/` `align/` `kf/` `grid/` `gate/` `qa/` `kfx/` `render/`
  `assfx/`。`ctc/` 与 `align/` 的分界是「跑模型 vs 校准与体检」`align_ctc` /`ctc_read`
  依赖 torch+transformers，其余不依赖，分开放后"读时间轴不需要模型环境"这件事在目录上看得见。
- `assfx/` 分 6 子包：`base/`(核心/几何/歌词解析/svg2ass) `draw/`(绘图) `deco/`(母题/丝带/线)
  `text/`(动画/排版/配色) `layer/`(发射器/生成器) `asset/`(图标库)。`draw/` 再分
  `kit/`(基本形/自然物/战斗物/道具) 与 `image.py`，并在 `draw/shapes.py` 保留一个
  **聚合入口**：`from assfx.draw import shapes as S` 这一行所有调用方都没改。
- 拆文件沿用"一个模块一件事"：`kf_timing.py` → `kf/{fetch,shape,pool,align,verify}` + 99 行 CLI；
  `score_kfx.py` → `kfx/score/{score_ass,score_meta,score_render}` + 116 行 CLI；
  `check_gates.py` → `gates_meta` / `gates_render`；`check_lyrics_coverage.py` →
  `coverage_sources`；`beat.py` → `beat_events` / `beat_shapes`；`shapes.py` →
  `kit/{prims,nature,battle,props2}`；`render_octopus.py` → `octo_browser` / `octo_probe`；
  `setup_env.py` → `env` / `fonts_check`。**压注释来凑行数被明确拒绝**：
  8 处超 10 行的连续注释块只把「来龙去脉」压成一句 + 指向本仓的 note 路径。
- `bin/hx-karaoke` 的 `resolve()` 增加一条 `find` 兜底：`hx-karaoke kf_timing.py` 与
  `hx-karaoke scripts/kf/kf_timing.py` 仍然等价。这是**必要**的一步
  否则每次归组都会把文档里 60 多处 `hx-karaoke <脚本名>` 全部打破。
- 两处目录保留多文件，用目录自带的 `layout.json` 声明预算与理由：
  `steps/4-kfx/42-text-main/impl/`（9 份 = 9 个正交设计维度的契约）与
  `examples/mushoku_ed1/`（`maxLines: 900`  示例成品一次运行一份、不跨工程复用，
  拆开反而读不出"一句长什么样"）。

## Alternatives considered

- **什么都不做，只把 `scripts/` 拆成子目录**：最强理由是「拆文件会动到 7 个工程的可运行性，
  风险最大收益最小」。否决（实测）：`check_layout.py` 会继续报 9 条超行，
  而它们的成因确实是"一个文件装多件事"；只搬目录不拆文件等于让门禁一直红。
- **给 `scripts/` 放一个 `layout.json` 声明 `maxFiles: 37`**：最强理由是「预算机制本来就是为这种
  大目录准备的，改一处比搬 37 个文件安全」。否决：`layout.json` 的语义是**例外**，
  而 37 个平铺脚本不是例外它们是"没归过类"。真正需要预算的是两处结构性多文件
  （9 个设计维度、1 份示例成品），那两处才配写理由。
- **把 `assfx/` 拆成 6 个顶层包（`assfx_base/` `assfx_draw/` …）**：最强理由是「import 路径更短」。
  否决：那会让 7 个外部工程与 20 个内部调用点的每一行都改，而它换来的只是少一层点号。
  保留 `assfx.<组>.<模块>` 后，`assfx.draw.shapes` 这种"组名即用途"的读法反而更好。
- **`examples/mushoku_ed1/make_ass.py` 拆成模块**：最强理由是「879 行确实超限」。
  否决：它的 879 行里 90% 是 `PHRASES` 表与 `fx_<句名>` 函数**一次运行一份、不跨工程复用**，
  拆开后读者要在多个文件之间对照同一句的「词义/画面/图形」，反而读不出参考价值。
  真正该被复用的部分已经在 `templates/` 与 `assfx/` 里。这条用 `layout.json` 显式声明，
  而不是默默放着。
- **`kf_timing.py` 只压注释、不拆模块**：最强理由是「848 行里有 300 行是实测记录，压掉就够」。
  否决：那些实测数字（MAE 0.0307s / 塌缩 15.2 倍 / 中位滤波窗 5）是判据的唯一出处，
  压掉等于把"为什么这么写"一起压掉；而模块边界本身（抓取 / 形状 / 兜底 / 融合 / 复核）
  在 848 行里是清楚存在的，拆开才是对的修法。

## Consequences

- 门禁：`check_layout.py` PASS（0 违规，改前 21）、`prose_rules.py --check` exit 0、
  `validate_skill.py` PASS（0 errors；warnings 从 40 降到 3，剩下的 3 条是 description 措辞与
  `assets/octopus/` 的软链目录，都与本次改动无关）。
- 行为未变，用**逐字节**证明：7 个 `dev/` 工程各跑一次 `make_ass.py`，
  新代码产物与用备份脚本（`/tmp/karaoke-backup/scripts` + 旧式 import shim）产物 `cmp` **完全相同**
  （罪恶王冠 `9187c85c26ff710be6cc1a25946d9170`、漆黑子弹 / 东方 / 比翼の羽根 / ピンキージョーンズ /
  ツナグキズナ / ろりこんでよかった~ 全部 `IDENTICAL`）。
- `check_gates.py --stage render` 在罪恶王冠上 `PASSED: 19 项通过, 0 项失败`；
  `check_lyrics_coverage.py` 输出 `PASSED：歌词覆盖完整`；`score_kfx.py` 总分 9.3 与改动前一致；
  55 → 77 个模块全量 import 冒烟的失败集合与基线**同一批**（都是入口脚本无参数时的
  `SystemExit`/读 argv 的 import 期副作用）。
- 代价：`scripts/` 下多了一层目录，`hx-karaoke <名>` 的解析多一次 `find` 调用（实测无感）；
  外部工程的 `from assfx.X import Y` 需要跟着改一次（7 个工程已改，含注释里的路径引用）。
- 已知边界：`check_layout.py` 的 C3（源码只允许 `.ts`）在本 skill 下对 `.py` 不生效
  本 skill 是 Python 工具链，`references/code-quality.md` 的 `SOURCE_SUFFIXES` 本身就认 `.py`。
  这次没有 `.js`/`.mjs`/`.cjs` 需要处理。
