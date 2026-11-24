# Agent Note: 卡拉OK 特效门禁 + 生成器补量 + v3 判断链

Status: implemented

Decision-ID: karaoke-fx-gate-studio

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/layer/fx_motion.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/check_fx_profile.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/tests/test_fx_profile.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/accept/accept.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/judge/check_judge.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/selfreview/selfreview.py`

## Problem

用户 2026-11-06 至 2026-11-09 的一轮制作反馈集中在三处: 特效量与参考差距大却没有门禁拦住 (成品比参考稀); 判断"哪句好哪句不行"靠人工口述, 没有可复跑的判据; 预览台 (`scripts/station/`) 只能锁区间, 不能按轨看层、标注、对比参考.

## Decision

- **特效门禁**: `scripts/assfx/check_fx_profile.py` 把成品的 FX 画像 (每层条数, 每句密度, 形态轮转) 对照参考 ASS 量; 结果不到就改生成器, 尺子不动. 自测在 `scripts/assfx/tests/`.
- **生成器参数层** (给预览台与验收台的接口, 不是新特效手法): `layer/manifest.py` 让生成器在 ASS 旁写 `<out>.manifest.json` 单元清单; `layer/overrides.py` 经 `ASSFX_OVERRIDES` 读回预览台改的参数; `layer/trace.py` 记录每个单元执行了哪些工程函数 (accept 的 G2 用); FX 加统一旋钮 density/size/alpha 与 `opt()`/`reseed()`, 默认值时输出逐字节不变; 种子按 key 派生 (`base/seeding.py`), 与句序解耦; `base/core.py` 的 `TEXT_LIFT` 可按工程设置 (缺省 20 不变); `text/anim.py` 高亮描边色可由主题 `hl_out` 覆盖 (缺省 glow); swoop/flutter/orbit 拆到 `layer/fx_motion.py` 守单文件 300 行; 起点色组与运动预设放 `scripts/assfx/presets/`. 逐帧步进、氛围床等补量手法写在 `dev/` 工程目录, 不在本提交.
- **v3 判断链**: `scripts/judge/` (六组判据), `scripts/accept/` (逐单元验收), `scripts/selfreview/` (自审打分); 共用 `scripts/assdoc/` 的事件读写.
- **studio 前端**: 拆到 `.agents/notes/implemented/feature/2026-11-09-karaoke-studio.md`, 本记录不再管 `scripts/studio/`.

## Alternatives considered

- 什么都不做 / 继续用 station: 最强理由是已有 75/75 的 e2e. 否决: station 不能按轨看层和对比参考, 用户验收的交互问题 (滚轮缩放, 标注轨, 轨名) 在旧结构里改不动.
- 门禁放宽到"人看着行就过": 否决. 用户明确要求尺子不动, 结果不到就改被测.
- 判断链做成单脚本: 否决. 六组判据、逐单元验收和自审是三个阶段, 输入输出不同, 合成一个会让任一段无法单独复跑.

## Consequences

- 2026-11-18: 清单多了 `meta.text_lift` (gen.py 写, revision 不含它), 验收台按它认字身层; accept 新增 `intake` / `cands` / `pick` / `ideas` / `sync`, picks.json 经 `ASSFX_OVERRIDES` 喂回生成器, `gen.py` 的 `ASSFX_ONLY` 只渲染指定单元. 决策见 `.agents/notes/implemented/feature/2026-11-17-karaoke-station-loop.md`.
- 2026-11-09: `check_fx_profile.py` 加第 11 项**上限** (每句中位 / 同时存活中位 不超过参考 x `CAP_RATIO` 1.5), **只报 WARN, 不进结论, 退出码不变**; 前 10 项的阈值与定义没动 (口径冻结仍成立). 起因: オンリー 门禁 10/10 OK 时每句中位 77 / 存活 21, 是参考 40 / 7 的 1.9 / 3 倍, 下限挡不住"过重". 阈值是拿参考 x1.25 / x1.5 拍的, 只在 オンリー 一首上验证过 (收缩后 50 / 13 报 WARN, 1.25x / 1.86x), 等 比翼の羽根 或另一首跑过再决定是否转 BAD; 记在 `shared/known-gaps.md` 第 7 条. 自测加 `test_cap_warn_only`. 已知: `test_out_bad_9` 指向 dev 工作文件, 该文件已收紧到全 OK, 断言失败, 与本改动无关, 记在 `shared/known-gaps.md` 第 9 条.

- 2026-11-09 实测: accept 自测 32/32, selfreview 25/25 (studio 实测见拆出的记录).
- 示例工程 `examples/mushoku_ed1/` 的拆分 (scene.py + fx_*.py) 不在本次提交内, 留待单独提交.
- 2026-11-09 本提交用 `git commit --no-verify` 绕过本地 pre-commit, 由用户授权, 不是校验通过. 红线诊断: 0 项错误, 58 项待审核 = note-only-diff 42 + resource-review 16 (后者是 advisory, 本来不拦). 完整 JSON 存在 `.agents/reports/redline/2026-11-09-commit-a.json`.
- 豁免的 42 条 note-only-diff, 均为同一根因: 8 篇旧记录各管多个目录 (skill-genericize 19 个, scripts-grouping 18 个), 本次只为记下 `assfx/base`, `layer`, `text`, `templates` 的真实改动各加一条 Consequences, 配对规则按记录的全部目录 (含旧版并集) 要求每个目录都有代码改动, 于是把本次没有改的目录也拉进来. 这些目录本次确实无代码改动, 新增的那条记录也写明了"本次未改". 明细:
  - `process/2026-10-04-karaoke-skill-genericize.md` 19 条: `examples/mushoku_ed1`, `scripts/align`, `scripts/assfx/asset`, `scripts/assfx/deco`, `scripts/assfx/draw`, `scripts/assfx/draw/kit`, `scripts/assfx/layer/music`, `scripts/ctc`, `scripts/gate`, `scripts/grid`, `scripts/karetpl`, `scripts/kf`, `scripts/kfx`, `scripts/kfx/score`, `scripts/qa`, `scripts/render`, `scripts/reverse`, `scripts/setup`, `scripts/source`.
  - `process/2026-10-05-karaoke-scripts-grouping.md` 18 条: 同上去掉 `examples/mushoku_ed1`.
  - `process/2026-10-02-karaoke-runtime-artifacts-out-of-skill.md` 2 条: `scripts/assfx/asset`, `scripts/qa`.
  - `bug-fix/2026-10-03-karaoke-shape-size-baseline.md` 1 条: `scripts/assfx/layer/music`.
  - `feature/2026-10-03-karaoke-voice-color.md` 1 条: `scripts/kfx`.
  - `process/2026-10-02-karaoke-layout-consolidation.md` 1 条: `examples/mushoku_ed1`.
  (目录前缀均为 `.agents/skills/hx-anime-karaoke-ass/`.)
- 没有走的路: 拆分这些旧记录同样过不了 (改动或删除的记录仍按新旧并集配对, AGENTS.md 也规定删除和改名不消除旧关系的责任); 改 `graph.py` 或改 `scripts/kfx` 锚点都在本轮红线之外. 本地 verify.py 没有"已审核"放行通路. 长期解法是把多目录旧记录逐步按决策收窄, 需要另行决定.
