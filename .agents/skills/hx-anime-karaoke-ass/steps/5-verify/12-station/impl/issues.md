# issues.json (验收台 v3)

位置: `review/accept/issues.json`. 由 `accept.py issue` 写, `accept.py resolve` 回写. 用户只指出哪里不对, 不描述需求

## 一条问题

```json
{"id": "I3", "sel": {"unit": "3f2a9c1d0b#0", "chars": [2, 5], "t": null, "layer": null},
 "action": "bad", "tag": "看不清", "say": "字糊", "frame": 83.2, "choice": null, "of": null,
 "status": "open", "tries": 0, "history": [], "at": "2026-11-08 18:40:00"}
```

- `sel`: 单元 key (清单) + 字下标半开区间 (命令行写闭区间 `--chars 2-4`) + 可选时间框 + 可选层 (事件 Name 前缀: `ly` 字层, `fx` 特效, `card` 卡片)
- `sels`: 只在多段选区时有 (台子上 Ctrl 加段). `sel` = 第一段. 读的时候用 `Issues.sels(it)`
- `action`: `bad` 不行, `good` 好 (同时冻结), `another` 换一个, `pick` 选 A/B/C (`choice`), `accept` 收下, `reject` 再驳回. 后三个用 `of` 指向被回应的问题
- `tag`: 只有 `bad` 能带. 描述症状, 不写做法
- `status`: `open` `fixing` `proposed` (等用户收下或驳回) `done` `need-human` `dropped`. 有 `review` (标注 id) 的问题, 状态与 history 由 accept 回写到 `review.jsonl` 那一行的 `status` / `changes` (见 `../index.md` "标注记到哪里")
- `review`: 来自哪条标注 (`accept.py intake` 写); `picked`: 选中的候选 (`accept.py pick` 写, 流程见 `cands.md`)
- `history`: 每次 resolve 一项: 诊断一句, 改了什么一句, 候选, 是否分叉, 声明的全局影响集

## 标签 -> 根因层

| 标签 | 根因层 | 先看 | 做法 |
|---|---|---|---|
| 看不清 | 生成 | - | 同构想内调对比/尺寸/层序 |
| 太吵 / 太素 | 剧本 | judge/arc.json | 改该句强度预算; 太素可升为高光 |
| 和画面冲突 | 视频元素 | judge/shots.json | 复核该时段镜头表, 再改 |
| 和词义不搭 | 歌词视觉化 | judge/lines.visual.json | 重做该句分析, 再出新构想 |
| 时机早 / 时机晚 | 生成 | - | 对齐卡点或起音 |
| 重复了 | 剧本 | judge/arc.json | 查手法重复, 换手法 |
| 出戏 | 风格表 | judge/style.json | 查风格表, 必要时修风格表 |
| 字错/音错 | 机械档 | fixes.json | 改 fixes.json 重跑机械档, 不进设计 |
| 无标签 / 换一个 | 剧本 | judge/arc.json | 换锚点出 2 个新构想 |

`accept.py where I3` 打印根因层, 发出事件的函数与源文件行号, 剧本条目, 同单元与下一句的 "好"

## 候选与前后对比的文件

台子要能播放候选, 所以候选是文件, 不是一句描述:
- `review/accept/cands/<问题 id>/A.ass`, `B.ass` (C 可选): 每个都是完整的 out. `resolve --candidates A,B` 在文件不全时拒收
- `review/accept/cands/<问题 id>/before.ass`: 改前的 out. proposed 条目有它时, 台子显示 "看改前"
- 需人判 (自审 gate --handoff 写入) 要配 2 个候选. 没有文件时台子标 "缺候选", 不让选
- `pick` 只能选最近一次 resolve 列出的候选

## 约束

- 每条最多自动改 2 次. 第 3 次 resolve 要带 `--candidates` 回给用户, 或标 `need-human`
- 同一标签在 3 处以上未关闭: 按全局问题处理, 改风格表或剧本, 不逐句修 (`issues` 会提示)
- 改代码走 deps-code.md 的 begin / predict / verify
