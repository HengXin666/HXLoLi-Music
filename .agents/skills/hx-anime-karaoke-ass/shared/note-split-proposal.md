# 提案: "一篇笔记管多个目录"的拆分

状态: 提案, 未实施. 写于 2026-11-09, 供下一轮接手. 数据来自当时 HEAD (50da45c) 的 `.agents/notes/` 全量扫描 (41 篇有 `## Code`). 本文件目前未跟踪; 入库时会报 1 条 resource-review.

## 背景

本轮第 11 项门禁上限 + `test_out_bad_9` 修复想入库, verify 报 6 条待审: 4 条 note-only-diff (`accept`、`assfx/layer`、`judge`、`selfreview`, 都指向 `2026-11-09-karaoke-fx-gate-studio.md`) + 2 条 resource-review (`known-gaps.md`、`13-validate/index.md`). 只提测试文件也报 1 条 code-only-diff. 根因: 门禁笔记一篇管 6 个目录、装了 3 个决策, 改其中一个决策就得让其他 5 个目录"陪审". 已用 4 次 `--no-verify` (commit a/b/c/d), 用户决定不再往这个方向叠豁免.

## 1. 管超过 3 个目录的笔记 (8 篇)

| 笔记 | 目录数 | 决策条目数 |
|---|---|---|
| `implemented/process/2026-10-04-karaoke-skill-genericize.md` | 23 | 7 |
| `implemented/process/2026-10-05-karaoke-scripts-grouping.md` | 21 | 1 |
| `implemented/process/2026-10-02-karaoke-steps-restructure.md` | 8 | 1 |
| `implemented/feature/2026-11-09-karaoke-fx-gate-studio.md` | 6 | 3 |
| `implemented/feature/2026-11-09-karaoke-studio.md` | 6 | 1 |
| `archived/process/2026-10-07-agent-notes-ast-redline.md` | 5 | 1 |
| `implemented/feature/2026-10-03-karaoke-beat-layer.md` | 4 | 2 |
| `implemented/process/2026-10-01-karaoke-gpu-default-auto.md` | 4 | 1 |

8 篇合计覆盖 40 个不重复目录. 下面逐篇列目录, 括号里是同目录的其他所有者 (笔记文件名, 改该目录代码时它们都会被拉进配对).

### `implemented/process/2026-10-04-karaoke-skill-genericize.md` (23 个)

- `hx-anime-karaoke-ass/examples/mushoku_ed1` (共管: 2026-10-02-karaoke-dev-workspace, 2026-10-02-karaoke-layout-consolidation, 2026-10-02-karaoke-steps-restructure)
- `hx-anime-karaoke-ass/scripts/align` (共管: 2026-10-01-karaoke-gpu-default-auto, 2026-10-01-karaoke-lyrics-source-ladder, 2026-10-02-karaoke-offset-verdict, 2026-10-02-karaoke-steps-restructure, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/assfx/asset` (共管: 2026-10-02-karaoke-elements-table-gate, 2026-10-02-karaoke-runtime-artifacts-out-of-skill, 2026-10-02-karaoke-steps-restructure, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/assfx/base` (共管: 2026-10-02-karaoke-runtime-artifacts-out-of-skill, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/assfx/deco` (共管: 2026-10-02-karaoke-steps-restructure, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/assfx/draw` (共管: 2026-10-03-karaoke-beat-layer, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/assfx/draw/kit` (共管: 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/assfx/layer` (共管: 2026-10-03-karaoke-shape-size-baseline, 2026-10-03-karaoke-carry, 2026-11-09-karaoke-fx-gate-studio, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/assfx/layer/music` (共管: 2026-10-03-karaoke-shape-size-baseline, 2026-10-03-karaoke-beat-layer, 2026-10-03-karaoke-bg-from-scene, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/assfx/text` (共管: 2026-10-03-karaoke-ruby-silent-loss, 2026-10-03-karaoke-shape-size-baseline, 2026-10-03-karaoke-voice-color, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/ctc` (共管: 2026-10-01-karaoke-gpu-default-auto, 2026-10-05-karaoke-scripts-grouping, 2026-10-02-milikara-not-adopted)
- `hx-anime-karaoke-ass/scripts/gate` (共管: 2026-10-03-karaoke-gate-criteria-decoupled, 2026-10-01-karaoke-hard-gates-script, 2026-10-01-karaoke-lyrics-source-ladder, 2026-10-02-karaoke-coverage-report, 2026-10-02-karaoke-elements-table-gate, 2026-10-02-karaoke-lyrics-timing-authority, 2026-10-02-karaoke-offset-verdict, 2026-10-02-karaoke-steps-restructure, 2026-10-03-karaoke-design-15-cells, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/grid` (共管: 2026-10-01-karaoke-gpu-default-auto, 2026-10-02-karaoke-lyrics-timing-authority, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/karetpl` (共管: 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/kf` (共管: 2026-10-02-karaoke-kf-line-pairing, 2026-10-02-karaoke-lyrics-timing-authority, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/kfx` (共管: 2026-10-03-karaoke-beat-layer, 2026-10-03-karaoke-voice-color, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/kfx/score` (共管: 2026-10-03-karaoke-blind-review-gate, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/qa` (共管: 2026-10-03-karaoke-gate-criteria-decoupled, 2026-10-02-karaoke-runtime-artifacts-out-of-skill, 2026-10-02-karaoke-steps-restructure, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/render` (共管: 2026-10-03-karaoke-custom-libass-renderer, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/reverse` (共管: 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/setup` (共管: 2026-10-01-karaoke-gpu-default-auto, 2026-10-02-karaoke-env-single-command, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/source` (共管: 2026-10-03-karaoke-beat-layer, 2026-10-03-karaoke-bg-from-scene, 2026-10-01-karaoke-anime-background-required, 2026-10-01-karaoke-lyrics-source-ladder, 2026-10-02-karaoke-steps-restructure, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/templates` (共管: 2026-10-02-karaoke-layout-consolidation)

### `implemented/process/2026-10-05-karaoke-scripts-grouping.md` (21 个)

- `hx-anime-karaoke-ass/scripts/align` (共管: 2026-10-01-karaoke-gpu-default-auto, 2026-10-01-karaoke-lyrics-source-ladder, 2026-10-02-karaoke-offset-verdict, 2026-10-02-karaoke-steps-restructure, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/assfx/asset` (共管: 2026-10-02-karaoke-elements-table-gate, 2026-10-02-karaoke-runtime-artifacts-out-of-skill, 2026-10-02-karaoke-steps-restructure, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/assfx/base` (共管: 2026-10-02-karaoke-runtime-artifacts-out-of-skill, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/assfx/deco` (共管: 2026-10-02-karaoke-steps-restructure, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/assfx/draw` (共管: 2026-10-03-karaoke-beat-layer, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/assfx/draw/kit` (共管: 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/assfx/layer` (共管: 2026-10-03-karaoke-shape-size-baseline, 2026-10-03-karaoke-carry, 2026-11-09-karaoke-fx-gate-studio, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/assfx/layer/music` (共管: 2026-10-03-karaoke-shape-size-baseline, 2026-10-03-karaoke-beat-layer, 2026-10-03-karaoke-bg-from-scene, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/assfx/text` (共管: 2026-10-03-karaoke-ruby-silent-loss, 2026-10-03-karaoke-shape-size-baseline, 2026-10-03-karaoke-voice-color, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/ctc` (共管: 2026-10-01-karaoke-gpu-default-auto, 2026-10-04-karaoke-skill-genericize, 2026-10-02-milikara-not-adopted)
- `hx-anime-karaoke-ass/scripts/gate` (共管: 2026-10-03-karaoke-gate-criteria-decoupled, 2026-10-01-karaoke-hard-gates-script, 2026-10-01-karaoke-lyrics-source-ladder, 2026-10-02-karaoke-coverage-report, 2026-10-02-karaoke-elements-table-gate, 2026-10-02-karaoke-lyrics-timing-authority, 2026-10-02-karaoke-offset-verdict, 2026-10-02-karaoke-steps-restructure, 2026-10-03-karaoke-design-15-cells, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/grid` (共管: 2026-10-01-karaoke-gpu-default-auto, 2026-10-02-karaoke-lyrics-timing-authority, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/karetpl` (共管: 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/kf` (共管: 2026-10-02-karaoke-kf-line-pairing, 2026-10-02-karaoke-lyrics-timing-authority, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/kfx` (共管: 2026-10-03-karaoke-beat-layer, 2026-10-03-karaoke-voice-color, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/kfx/score` (共管: 2026-10-03-karaoke-blind-review-gate, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/qa` (共管: 2026-10-03-karaoke-gate-criteria-decoupled, 2026-10-02-karaoke-runtime-artifacts-out-of-skill, 2026-10-02-karaoke-steps-restructure, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/render` (共管: 2026-10-03-karaoke-custom-libass-renderer, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/reverse` (共管: 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/setup` (共管: 2026-10-01-karaoke-gpu-default-auto, 2026-10-02-karaoke-env-single-command, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/source` (共管: 2026-10-03-karaoke-beat-layer, 2026-10-03-karaoke-bg-from-scene, 2026-10-01-karaoke-anime-background-required, 2026-10-01-karaoke-lyrics-source-ladder, 2026-10-02-karaoke-steps-restructure, 2026-10-04-karaoke-skill-genericize)

### `implemented/process/2026-10-02-karaoke-steps-restructure.md` (8 个)

- `hx-anime-karaoke-ass/examples/mushoku_ed1` (共管: 2026-10-02-karaoke-dev-workspace, 2026-10-02-karaoke-layout-consolidation, 2026-10-04-karaoke-skill-genericize)
- `hx-anime-karaoke-ass/scripts/align` (共管: 2026-10-01-karaoke-gpu-default-auto, 2026-10-01-karaoke-lyrics-source-ladder, 2026-10-02-karaoke-offset-verdict, 2026-10-04-karaoke-skill-genericize, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/assfx/asset` (共管: 2026-10-02-karaoke-elements-table-gate, 2026-10-02-karaoke-runtime-artifacts-out-of-skill, 2026-10-04-karaoke-skill-genericize, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/assfx/deco` (共管: 2026-10-04-karaoke-skill-genericize, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/gate` (共管: 2026-10-03-karaoke-gate-criteria-decoupled, 2026-10-01-karaoke-hard-gates-script, 2026-10-01-karaoke-lyrics-source-ladder, 2026-10-02-karaoke-coverage-report, 2026-10-02-karaoke-elements-table-gate, 2026-10-02-karaoke-lyrics-timing-authority, 2026-10-02-karaoke-offset-verdict, 2026-10-03-karaoke-design-15-cells, 2026-10-04-karaoke-skill-genericize, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/qa` (共管: 2026-10-03-karaoke-gate-criteria-decoupled, 2026-10-02-karaoke-runtime-artifacts-out-of-skill, 2026-10-04-karaoke-skill-genericize, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/source` (共管: 2026-10-03-karaoke-beat-layer, 2026-10-03-karaoke-bg-from-scene, 2026-10-01-karaoke-anime-background-required, 2026-10-01-karaoke-lyrics-source-ladder, 2026-10-04-karaoke-skill-genericize, 2026-10-05-karaoke-scripts-grouping)
- `hx-kfx/scripts/tools` (共管: 2026-09-28-kfx-normalized-safe-area, 2026-09-29-kfx-mv-driven-safe-area, 2026-09-29-mv-source-not-in-git)

### `implemented/feature/2026-11-09-karaoke-fx-gate-studio.md` (6 个)

- `hx-anime-karaoke-ass/scripts/accept` (独占)
- `hx-anime-karaoke-ass/scripts/assfx` (独占)
- `hx-anime-karaoke-ass/scripts/assfx/layer` (共管: 2026-10-03-karaoke-shape-size-baseline, 2026-10-03-karaoke-carry, 2026-10-04-karaoke-skill-genericize, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/assfx/tests` (独占)
- `hx-anime-karaoke-ass/scripts/judge` (独占)
- `hx-anime-karaoke-ass/scripts/selfreview` (独占)

### `implemented/feature/2026-11-09-karaoke-studio.md` (6 个)

- `hx-anime-karaoke-ass/scripts/studio/server` (独占)
- `hx-anime-karaoke-ass/scripts/studio/web` (独占)
- `hx-anime-karaoke-ass/scripts/studio/web/src` (独占)
- `hx-anime-karaoke-ass/scripts/studio/web/src/components` (独占)
- `hx-anime-karaoke-ass/scripts/studio/web/src/hooks` (独占)
- `hx-anime-karaoke-ass/scripts/studio/web/src/lib` (独占)

### `archived/process/2026-10-07-agent-notes-ast-redline.md` (5 个)

- `hx-agent-notes/scripts/authoring` (独占)
- `hx-agent-notes/scripts/cli` (独占)
- `hx-agent-notes/scripts/redline` (共管: 2026-10-08-agent-notes-v2-migration-boundaries)
- `hx-agent-notes/scripts/setup` (共管: 2026-10-08-agent-notes-v2-migration-boundaries)
- `hx-agent-notes/scripts/tests` (共管: 2026-10-08-agent-notes-advisory-comments)

### `implemented/feature/2026-10-03-karaoke-beat-layer.md` (4 个)

- `hx-anime-karaoke-ass/scripts/assfx/draw` (共管: 2026-10-04-karaoke-skill-genericize, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/assfx/layer/music` (共管: 2026-10-03-karaoke-shape-size-baseline, 2026-10-03-karaoke-bg-from-scene, 2026-10-04-karaoke-skill-genericize, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/kfx` (共管: 2026-10-03-karaoke-voice-color, 2026-10-04-karaoke-skill-genericize, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/source` (共管: 2026-10-03-karaoke-bg-from-scene, 2026-10-01-karaoke-anime-background-required, 2026-10-01-karaoke-lyrics-source-ladder, 2026-10-02-karaoke-steps-restructure, 2026-10-04-karaoke-skill-genericize, 2026-10-05-karaoke-scripts-grouping)

### `implemented/process/2026-10-01-karaoke-gpu-default-auto.md` (4 个)

- `hx-anime-karaoke-ass/scripts/align` (共管: 2026-10-01-karaoke-lyrics-source-ladder, 2026-10-02-karaoke-offset-verdict, 2026-10-02-karaoke-steps-restructure, 2026-10-04-karaoke-skill-genericize, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/ctc` (共管: 2026-10-04-karaoke-skill-genericize, 2026-10-05-karaoke-scripts-grouping, 2026-10-02-milikara-not-adopted)
- `hx-anime-karaoke-ass/scripts/grid` (共管: 2026-10-02-karaoke-lyrics-timing-authority, 2026-10-04-karaoke-skill-genericize, 2026-10-05-karaoke-scripts-grouping)
- `hx-anime-karaoke-ass/scripts/setup` (共管: 2026-10-02-karaoke-env-single-command, 2026-10-04-karaoke-skill-genericize, 2026-10-05-karaoke-scripts-grouping)

## 2. 该拆 / 不该拆 (判据: 笔记 `## Decision` 里的决策条目数, 不是目录数)

| 笔记 | 决策 | 结论 |
|---|---|---|
| `2026-10-04-karaoke-skill-genericize.md` | 7: 道具/形状抽象化; MV_CROPS 改工程传入; score_kfx 产物发现改"最近修改的 .ass"; 单样本阈值改量法; 删 200 行清单式铺陈; 软化"照抄"类措辞; SKILL.md 增"是什么/不是什么"一节 | 该拆 (7 个互相独立的决策), 但本轮不拆: 牵动 scripts/kfx、kfx/score 锚点 (红线), 且 23 个目录几乎都与 scripts-grouping 共管 |
| `2026-10-05-karaoke-scripts-grouping.md` | 1: scripts/ 按职责分组并拆超 300 行模块, 用入口层吸收路径变化 (各子弹点是同一决策的展开) | 不该拆: 一个决策, 只是目录多 |
| `2026-10-02-karaoke-steps-restructure.md` | 1: skill 按步骤切成 steps/NN-<key>/ 契约 + impl | 不该拆; 且红线要求动它前先问用户, 并含 hx-kfx/scripts/tools |
| `2026-11-09-karaoke-fx-gate-studio.md` | 3: 特效门禁 (check_fx_profile + tests); 生成器参数层 (layer/manifest、overrides、trace); v3 判断链 (judge/accept/selfreview) | 该拆, 本轮阻塞的来源 |
| `2026-11-09-karaoke-studio.md` | 1: studio 前端 (server + web), 6 个目录都在 scripts/studio/ 下 | 不该拆 |
| `2026-10-03-karaoke-beat-layer.md` | 2: 卡点层 (40+44); 图片层 (46) | 按条目数该拆, 但含 scripts/kfx 锚点 (红线不许动), 排除 |
| `2026-10-01-karaoke-gpu-default-auto.md` | 1: 字幕链默认设备改 auto, 可复现性降为 device_check 开关 | 不该拆 |
| `2026-10-07-agent-notes-ast-redline.md` | 1: Agent Notes v2 以 AST 双向图执行红线 (各段是同一设计的展开) | 不该拆; 已归档, 属 hx-agent-notes, 不碰 |

小结: 只讲一个决策、目录多是合理的有 5 篇 (scripts-grouping、steps-restructure、studio、gpu-default-auto、ast-redline). 塞了多个决策的有 3 篇 (fx-gate-studio、skill-genericize、beat-layer), 其中只有 fx-gate-studio 能在红线内低成本拆.

## 3. 规则原意: paired_changes 的并集配对

实现 (`.agents/skills/hx-agent-notes/scripts/redline/graph.py` 第 183-203 行):

- `by_note` 以笔记路径为键, 把同一路径在**旧图和新图**里的目录取并集.
- 每个改动的受保护源码, 其直接父目录的所有所有者里, 本次没改的各报一条 `code-only-diff`.
- 每篇改动的笔记, 其并集目录里本次没有任何代码改动的, 各报一条 `note-only-diff`.
- 新路径的笔记只有新图里的目录.

规则原文:

- AGENTS.md: "代码或 note 改动必须在同一 diff 配对, 同目录兄弟代码也算该决策的代码端. 单边改动必须 review, 不可用无关 note 或豁免文本放行."
- `hx-agent-notes/assets/notes-contract.md`: "以同一 diff 的旧图和新图核对关系. 任一端变化另一端没有变化即要求 review, 多目录决策每个目录分别核对. 修改同目录兄弟代码也触发配对. 删除和改名不能消除旧关系的责任"
- `hx-agent-notes/references/verify.md`: "文件增加, 修改, 删除和改名按旧图与新图并集核对."

"删除和改名不能消除旧关系的责任"防的是: 在同一个 diff 里一边改某目录的代码, 一边把该目录从笔记 `## Code` 里删掉 (或删除、改名整篇笔记、删掉代码文件), 让新图里这个目录"没人管", 从而不经 review 就让代码与决策脱钩. 有了并集, 旧图里的关系在这次 diff 里照样算数.

拆笔记**不违反**这条. 拆分正是它要管的场景: 它不禁止拆, 只要求拆的那次 diff 把每个旧目录交代一次. 搬到新笔记的目录必须改代表文件顶部的反向锚点, 这本身就是代码改动, 会自动配对. 留在原笔记、本次又没改代码的目录各报一次 note-only. 这是一次性成本, 不是永久成本. 副作用: 改锚点算该目录的代码改动, 若该目录还被别的笔记共管, 那些笔记各报一条 code-only.

## 4. 三个方案 (以"第 11 项 + 第 9 条修复 + 拆分"同一提交估算)

### A. 不拆, 只豁免

- 本次: 4 条 note-only + 2 条 resource-review, 共 6 条, 需第 5 次 `--no-verify`.
- 以后每次改门禁 (assfx) 都会再带出 accept / assfx/layer / judge / selfreview 4 条, 改判断链也会反过来拖上门禁. 成本永久.
- 不推荐: 用户已否决继续往这个方向叠豁免.

### B. 按决策拆 (推荐)

动作:

1. `2026-11-09-karaoke-fx-gate-studio.md` 只保留"特效门禁"决策, `## Code` 留 `scripts/assfx/check_fx_profile.py`、`scripts/assfx/tests/test_fx_profile.py`, 以及暂留的 `scripts/assfx/layer` 代表文件 (见 3).
2. 新建 `implemented/feature/2026-11-09-karaoke-judge-chain.md`, 承接"v3 判断链": `scripts/judge/check_judge.py`、`scripts/accept/accept.py`、`scripts/selfreview/selfreview.py`. 把这三个文件顶部的反向锚点从门禁笔记改指新笔记.
3. "生成器参数层" (`scripts/assfx/layer`) 本次**先留在门禁笔记**. 若搬走, 要改该目录代表文件的锚点, 而这个目录还被 shape-size-baseline、carry、skill-genericize、scripts-grouping 共管, 会多出 4 条 code-only. 留下只需 1 条 note-only. 等以后真改参数层代码时再顺带拆出去, 届时那 4 篇本来就要配对.
4. 第 11 项代码、测试、13-validate 文档、known-gaps.md、门禁笔记 Consequences 同一提交.

预期阻塞: 由 6 条降到 3 条, 即 1 条 note-only (`assfx/layer`) + 2 条 resource-review (`known-gaps.md`、`13-validate/index.md`; 本提案文件若同提再 +1).

- `accept/`、`judge/`、`selfreview/` 有锚点改动, 新旧笔记两边都配上; 这三个目录没有其他所有者, 不产生 code-only.
- `assfx`、`assfx/tests` 有第 11 项与测试改动, 配上.

resource-review 与拆不拆无关: 受保护的非 AST 资源 (skill 里的 md) 一改就报, 由人工核对. 它算不算"豁免"要用户定口径.

推荐 B 的理由:

- 唯一同时满足三条红线的方案: 不改 graph.py / 钩子 / AGENTS.md, 不动 kfx 锚点, 不再叠"一篇笔记管多目录"方向的豁免.
- 按决策条目切, 符合 AGENTS.md "每条决策只保留一篇 note".
- 成本一次性: 拆完后改门禁只牵涉 `assfx`、`assfx/tests` (若只改代码不改测试, `assfx/tests` 仍会报 1 条, 这是同一决策内部的正常配对). 判断链和门禁互不拖累.
- 动作最小: 改 2 篇笔记 + 3 处锚点注释, 不碰任何逻辑代码.
- 剩下的 note-only 与 resource-review 都能在 commit message 和笔记里说清, 不属于结构性根因.

会不会牵动 kfx 锚点: **不会**.

- B 只改 `scripts/judge`、`scripts/accept`、`scripts/selfreview` 三个代表文件的锚点, 外加两篇笔记.
- 不碰 `scripts/kfx`、`scripts/kfx/score`, 也不碰 `hx-kfx/`.
- 避免方法是**刻意不拆**会碰 kfx 的三篇: beat-layer (含 `scripts/kfx`)、skill-genericize (含 `scripts/kfx`、`scripts/kfx/score`)、steps-restructure (含 `hx-kfx/scripts/tools`, 且动前需问用户).
- `assfx/layer` 暂不搬, 也顺带避开 fx_motion.py (该文件顶部还挂着 skill-genericize 的锚点).
- 实施前用 `uv run scripts/redlines/agent_notes.py --staged` 确认诊断里没有任何 `scripts/kfx` 或 `hx-kfx` 路径, 有就停下来问.

### C. 改 graph.py (不可行)

例如只看新图、取消并集, 或把逐目录核对改成逐笔记核对. 不可行的确切理由:

1. 红线: 用户明确"不改钩子、AGENTS.md、graph.py".
2. 并集就是 notes-contract "删除和改名不能消除旧关系的责任"与 verify.md "按旧图与新图并集核对"的实现. 去掉它, 就重新打开"删 Code 行或改名笔记绕过 review"的口子.
3. "多目录决策每个目录分别核对"是契约原文. 改实现等于改规则, 不是修 bug.
4. AGENTS.md 明确"单边改动必须 review, 不可用无关 note 或豁免文本放行". 改校验器来让单边改动不报, 等于在实现层放行, 违背这条的本意.
5. graph.py 属 vendored 的 hx-agent-notes skill, 改它会触发 policy-review, 也超出本项目范围.

## 5. 不在本提案内 (留后续)

- skill-genericize 按 7 个决策拆: 本轮不做. 一次会报出几十条 code-only, 且碰 kfx 锚点.
- beat-layer 拆卡点层 / 图片层: 碰 `scripts/kfx` 锚点, 需先解除红线.
- steps-restructure: 红线要求先问用户.

## 6. 2026-11-10 实测: 方案 B 实测失败, 原因是并集规则

- 规则: `graph.py` 的 `paired_changes` 对同一篇笔记取 HEAD 版与工作区版 `## Code` 目录的并集. 笔记只要被动 (补行 / 删行 / 删除), 并集里每个目录都必须有代码改动, 否则报 note-only; 反过来, 改了代码的目录, 其新旧两版的每篇 owner 笔记都必须同步, 否则报 code-only.
- 宽笔记: `process/2026-10-04-karaoke-skill-genericize.md` 管 23 个目录, `process/2026-10-05-karaoke-scripts-grouping.md` 管 21 个. 位置预设本轮只改了其中 `assfx/text`、`assfx/layer` 两个.
- 最小实验 (位置预设工作区, `verify --diff`): 只从 skill-genericize 的 Code 删掉 `scripts/assfx/text/anim.py` 一行, 阻塞从 **33** (code-only 30 + note-only 3) 涨到 **50** (code-only 26 + note-only 24, 其中 genericize 21 条), 另多 **1 个 reverse-edge 错误**. 已逐字节恢复.
- 结论: 在同一个提交里拆宽笔记必然带出旧目录的全部 note-only; 先单独提一个只拆笔记的提交也一样 (那时没有任何代码改动, 全部目录都报). 不改 graph.py、不动无关代码, 方案 B 走不通.
- 实际做法: 只同步代价小的 5 篇 (ruby-silent-loss、karaoke-carry、shape-size-baseline、voice-color、karaoke-studio), 阻塞 33 -> 16; genericize / grouping 不动, 剩余保底按单次授权 `--no-verify` 提交, 诊断见 `.agents/reports/redline/2026-11-10-commit-placement.json` 与 `2026-11-10-commit-gate-cap.json`.
