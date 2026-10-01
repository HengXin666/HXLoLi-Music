# Agent Note: 卡拉OK skill 按步骤重构成 steps/NN-<key>/ 的契约 + impl 结构

Status: implemented

- 影响: `.agents/skills/hx-anime-karaoke-ass/SKILL.md`（重写为步骤表 + 索引）、
  `steps/00-setup/` … `steps/15-render/`（16 个步骤目录，各含 `index.md` 契约与可选 `impl/`）、
  `shared/hard-rules.md`（新增：十条跨步骤铁律）、`references/` 整个目录被拆解并删除
- 决策依据: `hx-make-skill` 的两条硬约定（索引写裸路径+一句描述；一个步骤=一个文件夹=`index.md`+`impl/`），
  以及用户对旧版的原话「现在 skill 太垃圾了。文本也没有转化」「ref/ 下的 md 可以按照步骤分到 01_xxx 这种文件夹里」

## Problem

旧版把 12 份文档平铺在 `references/` 下，是一堆**按主题切**的长文：`workflow.md`（每步命令）、
`design.md`（设计方法）、`kfx-tuning.md`（四类缺陷）、`per-line-design.md`、`three-layers.md`、
`precise-shapes.md`、`anime-background.md`、`qa-checklist.md`、`timing-lag.md`、`lyrics-source.md`……

失败模式有三条，都能实测：

1. **同一件事散在三份文件里。** "长音塌缩"这个判据在 `workflow.md` 第 5c 步、`kfx-tuning.md` §2、
   `SKILL.md` 硬性规则 5 各有一份措辞不同的版本；改一处不会改另两处，于是三份互相矛盾。
2. **读者没有"我该做什么"的落点。** `SKILL.md` 的流程表列 13 步，每步只写"产物/检查点"，
   而"具体怎么做"要靠读者自己从 12 份长文里拼 —— 没有一步有**明确边界**（这一步不做什么、
   什么条件算过）。结果是跳过一步不会有任何后果，直到成片不对味。
3. **超长文件按主题切，切不出"什么时候读"。** `kfx-tuning.md` 346 行里塞了四类互不相干的缺陷，
   做密度的时候要读它、做时间轴的时候也要读它，但两者需要的段落完全不同 ——
   索引写不出"什么时候读这个文件的哪一段"，只能整个读。

## Decision

**按步骤（流程的阶段）切，不按主题切**，采用 `hx-make-skill` 的模板方法模式：

- 每个步骤一个目录 `steps/NN-<key>/`，里面的 `index.md` 是**契约**：只做这一件事 / 命令 /
  判据 / 产物 / 过关条件 / 具体做法指向哪个 `impl/`。
- 主题型长文降级为**那一步的 `impl/`**：`kfx-tuning.md` 拆成
  `steps/06-kf-timing/impl/collapse.md`（长音塌缩）+ `…/impl/pairing.md`（配对失手）、
  `steps/11-design/impl/density.md`（密度）、`steps/13-validate/impl/overlap.md`（卡片重叠）、
  `steps/02-lyrics/impl/reading-basis.md`（读音基准）、`steps/03-offset/impl/verdict.md`（离散度判定）。
- **每个 impl 文件都归属唯一一步**，加一种做法 = 加一个文件，契约不用改。
- `SKILL.md` 只留**步骤表**（编号 / 步骤 / 关心什么 / 契约在哪 / 产物）与脚本索引；
  每条路径后面跟一句"什么时候读"，不写 `[a](a)` 形式的链接。
- 跨步骤的铁律（band、素材、来源定级……）抽到 `shared/hard-rules.md`，SKILL.md 只点它一次。

编号从 **00** 开始，两位十六进制对齐（`steps/00-setup` … `steps/15-render`），
这样按字典序排就是流程顺序，且以后在中间插一步不用全体改名。

## Alternatives considered

- **什么都不做，继续用 `references/` 平铺长文**：最强理由是「内容已经写全了，结构是外观问题」。
  否决（实测）：上面第 1、2 条不是外观问题 —— 同一判据三处不一致**已经造成了交付事故**
  （`proj-touhou` 带着 2 处 CTC 塌缩交付，报告里写了"应为 0"却没人读它，成片慢了 20 秒）。
  修法不是再写一份文档，是让判据有**唯一的归处**。
- **保留 `references/` 目录名，只在它下面建 `01_xxx` 子目录**：最强理由是「用户的字面表述是
  `ref/ 下的 md 分到 01_xxx 文件夹里」。
  否决：`hx-make-skill` 的范式是 `steps/<N>-<key>/index.md` + `impl/`，本仓已有两个 skill
  （`hx-note`、`hx-ui-system`）按它落地；用 `references/01_xxx/` 会让同一个仓库里出现两套步骤结构，
  且 `references/` 这个根名暗示"按需查阅的文档"，与"步骤契约"不是一回事。
  （用户在这一轮确认选 `steps/01-<key>/index.md + impl/`。）
- **把步骤平铺进 `references/`，不建 `impl/` 子目录**：最强理由是「少一层目录，路径更短」。
  否决：`impl/` 承载的是"这一步的多种做法"，没有它就只能把不同做法塞进同一个 `index.md`，
  又回到"一份文件什么都讲"。实测这一步的 `impl/` 里有 5 份互斥场景的实现
  （逐句设计的 four 个角度 + 图形精度），拆开之后每份都能独立改。
- **保留 `examples/` 下全部 5 个工程**：最强理由是「示例越多，模型越容易照着做」。
  否决：见 [karaoke-layout-consolidation](./2026-10-02-karaoke-layout-consolidation.md) ——
  其中 `blackbullet_ed` 一个工程占 726MB（含 169MB 的 `base.mp4`、96MB 的 stems、356MB 成片），
  且它是**一次具体制作的产物**，不是 skill 的一部分。

## Consequences

- 文档从 12 份平铺长文（1774 行）变成 16 个契约 + 16 份 `impl`（约 1750 行），
  **总量没变，但每份都可独立定位**：`SKILL.md` 105 行（原 206 行），正文预算降到 L2 之内。
- 新增文件不产生新的心智负担：`steps/NN-xxx/index.md` 的第三节固定是"产物与过关条件"，
  找"这一步怎么算过"永远在同一个位置。
- 脚本内部指向文档的引用一并改到 `steps/`（`check_gates.py` / `fetch_anime_bg.py` /
  `find_lyrics.py` / `calibrate_offset.py` / `check_lag.py` / `assfx/props.py` / `assfx/motifs.py`），
  否则报错信息会指着已经不存在的 `references/*.md`。
- `hx-make-skill` 的校验器现在全绿（0 error / 0 warning）：
  它在 `--strict` 下要求"索引写裸路径 + 每个路径一句描述 + 每个 L3 文件都被 SKILL.md 引用"，
  这三条正好是旧版 `references/` 结构做不到的。
- 已知边界：步骤目录仍是**软约定**，DSH 的 loader 只强制 `SKILL.md` 存在且 frontmatter 可解析；
  步骤结构的收益来自"读的时候知道该读哪一份"，不是来自任何机器强制。

## Verification

- `uv run <hx-make-skill>/scripts/validate_skill.py .agents/skills/hx-anime-karaoke-ass` → `PASS (0 errors, 0 warnings)`。
- 保留示例实跑：`uv run examples/mushoku_ed1/make_ass.py /tmp/mushoku_out.ass` → `events: 9155`。
- `python3 -W error::SyntaxWarning -m compileall scripts/` → 无警告（顺手修掉了三处 `\p1` 非法转义 docstring）。
