# Agent Note: 步骤契约骨架由脚本核对, 不靠自觉

Status: implemented

Decision-ID: karaoke-step-contract-check

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/gate/check_steps.py`

## Problem

`.hark/plan.md` 2.1 写: 流程骨架完整, 1-source 到 5-verify 每步有契约, 判据, 产物. 逐份读 27 个 `index.md` 后, 这句话不成立.

实测 (2026-11-16): 新脚本首跑报 20 项, 人工清点另有 5 处旧编号与 1 处死引用:

- 13 步缺固定小节. 02 缺 "只做这一件事". 40, 42-47, 16, 50 缺 "产物". 41, 42, 43, 48 缺 "命令".
- `review/coverage.txt` 是 render 门禁的必查项, 但没有任何一步把它列为产物.
- `50-reverse` 目录在, 但 SKILL.md 与 `steps/4-kfx/index.md` 的步骤表都没有它. "十个子步骤" 与目录数 11 对不上.
- 旧编号残留: "第 11 步" (2 处), "第 11-12 步", "第 15 步卡片", "第 8b 步", "人工校时 (第 6 步)", "第 1 步的必做项". 现行编号里 11 不存在, 其余指错了步.
- `check_gates.py` 失败时让人去看 "SKILL.md 的强制门禁一节". SKILL.md 没有这一节.

根因写在 `2026-10-02-karaoke-steps-restructure.md` 的 Consequences: 步骤目录仍是软约定, 没有机器强制. 软约定在 6 周的改动里逐步漂移.

## Decision

新增 `scripts/gate/check_steps.py`, 两种模式:

1. 无参数: 核对骨架. 每步 `index.md` 必须有四节 (只做这一件事 / 命令 / 产物 / 过关条件). 无脚本的步骤写 "本步无专用脚本" 代替命令节. 脚本内 `STEPS` 表登记的产物必须出现在该步契约正文里. `hx-karaoke` 后的脚本名必须存在. "第 NN 步" 必须指向现存步骤. 每步必须进 SKILL.md 的步骤表与组 index. 目录在而 `STEPS` 未登记也报. 有失败退出码 1.
2. `--project proj`: 按主线顺序报每步产物在不在, 给出第一个缺产物的步骤. 只报不拦, 退出码 0. 产物在不等于判据过, 判据仍归 `check_gates.py` 与各步命令.

同一 diff 补齐上面全部缺口, 使首跑结果为 PASSED. `50-reverse` 定为旁路: 写进两张步骤表, 但不计入 "十个子步骤". `coverage.txt` 归到 `08-review-timing`, 因为它要读 `timing.json` 终稿.

## Alternatives considered

- 什么都不做, 继续靠人读文档. 最强理由: 契约内容大体都写了, 缺的多是小标题. 否决: 缺的不只是标题. `coverage.txt` 无主, 门禁报错指向不存在的章节, 都会让执行者走错. 软约定已经漂移过一次.
- 复用 `check_gates.py`, 加一个 `--stage skeleton`. 最强理由: 门禁只有一个入口. 否决: `check_gates.py` 查的是工程产物的质量, 输入是 `--project`. 骨架检查查的是 skill 自身文档, 两者的输入与失败含义不同. 混在一起会让 `--stage` 的语义变成两类.
- 复用 `hx-make-skill` 的 `validate_skill.py`. 最强理由: 已有通用 skill 校验器. 否决: 它只懂 SKILL.md 与引用可达, 不知道本 skill 的四节约定与产物表.
- 产物表从文档正文自动解析, 不在脚本里写. 最强理由: 只有一处真源. 否决: 各步产物写法不统一 (表格, 列表, 代码块), 解析规则会比表本身更难维护. 改为脚本登记, 再反查正文含不含该路径, 两端配对.
- `--project` 模式缺产物时退出码 1. 最强理由: 与门禁一致. 否决: 进行中的工程必然缺后续产物, 非零退出会让它在每个中途都报错. 拦截仍归 `check_gates.py`.

## Consequences

- 加一步或改契约时, 要同时改 `STEPS` 表. 漏改会被本脚本报出.
- `--project` 的输出是 plan T5 "每步产物即状态" 的最小形态. 它只报存在性, 不做编排.
- 已知边界: 不判断小节内容写得好不好. "第 NN 步" 只能查编号存在, 查不出编号存在但指错步, 如原 "第 6 步". 这类靠本次人工清点修正.
- 编号保持现状 (00-10, 40-50, 12-16). 重新编号会改 27 个目录与全部引用, 收益只是好看, 本次不做.

## Verification

- 改动前首跑: `FAILED: 27 步 (主线 26, 旁路 1), 20 项失败`.
- 改动后: `PASSED: 27 步 (主线 26, 旁路 1), 0 项失败`.
