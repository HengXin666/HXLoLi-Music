# 候选 (换一个构想 -> 挑选 -> 冻结)

代码: `scripts/accept/cands.py` (生成与构想记录), `scripts/accept/accept.py` (`cands` / `pick` / `ideas`), `scripts/studio/server/loop.py` (台上入口).

## 文件 (都在工程 `review/accept/`)

| 文件 | 内容 |
|---|---|
| `picks.json` | 选中的参数, assfx-overrides v1: `units[<单元 key>] = {params, fp, label, issue, cand, why, at}`. accept 每次重跑生成器都经 `ASSFX_OVERRIDES` 喂它 |
| `cands/<I>/cands.json` | 本轮候选: `items[] = {id A/B/C, params, why, n, sha, secs, fx}`, `skipped[]` (提案与失败原因), `base_params`, `base_sha`, `siblings` (重复歌词的兄弟单元), `only_unit: true` |
| `cands/<I>/<X>.unit.ass` | 候选 X 只重跑本单元得到的本单元事件 (隔离核对的比较对象) |
| `cands/<I>/<X>.ass` | 台子预览: 当前 out.ass 把本单元换成候选 X |
| `cands/<I>/before.ass` | 生成候选时的 out.ass |
| `ideas.jsonl` + `ideas/<I>-<X>.unit.ass` | 构想记录: 未选中的候选 (参数, 说明, 单元快照, 选中的是谁, 来自哪条标注) |
| `prev.ass` | 上一版 out.ass (accept build 覆盖前留下), 台子无参考时的对比对象 |

## 生成 (`accept.py cands PROJ I3 [--n 3]`)

- 只对句单元. n 取 2-3. 只重跑本单元: 生成器带 `ASSFX_ONLY=<key>` 跑, 其它句不跑特效函数、不出事件; 出入场规划仍按全部句算, 种子按单元 key 派生, 所以本单元输出与整首跑逐行相同 (自测 "ASSFX_ONLY" 一条核对). 比翼の羽根 实测每个候选约 0.7s (整首 1.1s); 慢的工程差距更大
- 提案顺序: 换特效配方 (清单 presets.recipes 里别的配方, 别句没用过的优先, 按 key + 本条已试次数定序) 两个, 同配方换 salt (同构想重抽) 一个, 交错. 跳过: 当前参数、构想记录里出现过的参数、上一轮没选的候选. 参数先按清单 schema 校验 (`overrides.check`). 生成器报错 (配方与本句不兼容) 或输出与当前 / 已有候选相同的提案记进 skipped, 换下一个, 最多试 8 个
- 凑不到 2 个: 报错退出, 不降级成 1 个
- 成功后 issue `resolve` 为 `proposed` 并带 `candidates`; 标注状态回写

## 挑选冻结 (`accept.py pick PROJ I3 --choice B`)

1. 本单元已有 "好": 拒绝 (G2 的 A 条不能豁免), 先 `unfreeze`
2. 候选生成后本句输入变了 (清单 fp 不同): 拒绝, 重新生成
3. `begin` 存基准 (raw + 清单 + 工程 .py + picks.json) -> 写 picks.json -> `verify --scope <本单元>`: 预测影响集含 picks.json 的变化 (g2.picks_changes) -> 整首重跑 -> G2 三条 -> 隔离核对 (整首输出的本单元 == `<X>.unit.ass`, 逐行)
4. 都过: 冻结本单元为 "好" (issue = I3), 构建, 新基准; 未选进构想记录; issue `done`, history 记 `picked / good / ideas / g2`
5. 不过: raw / 清单 / picks.json 恢复为基准, issue `need-human`, 原因进 history

## 重复歌词

单元 key = `sha1(句子文字)[:10] + "#" + 同文字出现次序` (`gen.phrase_keys`). 同一句歌词出现两次是两个单元 (`#0` `#1`), 种子不同, 候选只改被标的那一处; cands.json 的 `siblings` 列出兄弟单元, 面板写 "重复歌词: 只改这一处". picks.json 记 `fp` 与 `label`: 歌词增删让 `#n` 挪位时 fp 对不上, `accept build` 报 "pick 过期", 不会静默套到另一句上. 要两处一起换, 分别标两条.
