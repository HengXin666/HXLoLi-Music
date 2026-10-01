# Agent Note: skill 只保留一份可复现示例，模板只留一个

Status: implemented

- 影响: `.agents/skills/hx-anime-karaoke-ass/examples/`（5 个工程 → 只留 `mushoku_ed1`）、
  `templates/`（`lyrics_example.txt` 删除 → 只留 `make_ass_template.py`）、
  `SKILL.md` 的「示例与模板」节
- 决策依据: 用户原话「示例仅保留 templates/make_ass_template.py，删除其他示例，仅留下 examples/mushoku_ed1」
- 相关: [karaoke-runtime-artifacts-out-of-skill](./2026-10-02-karaoke-runtime-artifacts-out-of-skill.md)
  （工程往哪搬、缓存怎么改）；[karaoke-steps-restructure](./2026-10-02-karaoke-steps-restructure.md)

## Problem

旧版 `examples/` 下有 5 个工程：`mushoku_ed1`(1.7MB) / `yosuga_op`(156K) / `yosuga_ed`(176K) /
`one_line`(112K) / `blackbullet_ed`(**726MB**)。`templates/` 下有 2 个文件。

两个具体问题：

1. **体量最大的那个恰好是最没有示例价值的。** `blackbullet_ed` 的 726MB 里，
   172 个文件是 `review/` 下的抽帧 PNG/JPG、`stems/` 的 wav、`out/` 的成片 ——
   它们记录的是"当时那个人看到了什么"，不是"这个 skill 怎么用"。
   真正有示例价值的是 `make_ass.py` + `lyrics.txt` + `timing.json` + `anime.notes.md`，
   合计不到 100KB。
2. **`templates/lyrics_example.txt` 与 `examples/mushoku_ed1/lyrics.txt` 逐字节相同。**
   它是被 `cp` 出来当"模板"的，而真正的模板价值（标注语法怎么写的说明）已经在
   `steps/02-lyrics/impl/format.md` 里 —— 于是这份副本只带来一个问题：
   两者会各自漂移，读者不知道哪份是权威（`SKILL.md` 只引用了它，没有任何脚本或流程引用）。

## Decision

- `examples/` **只保留 `mushoku_ed1`**（無職転生 ED1「オンリー」）：它是唯一同时具备
  30 句逐句设计、71 处人工校时 fixes、标题/片尾卡、以及**合格的 `anime.notes.md`**的工程。
  其余四个搬到 `static/music/` 下的工程区（见相关 note）。
- `templates/` **只保留 `make_ass_template.py`**；删掉 `lyrics_example.txt`（与示例重复，
  且语法说明以 `steps/02-lyrics/impl/format.md` 为唯一权威）。
- `SKILL.md` 的「示例与模板」节写明：`examples/mushoku_ed1` 是**唯一保留的示例**，
  其余历史工程在 `static/music/<番名>/` 下，**属工程不属 skill**。

## Alternatives considered

- **什么都不做，五个示例都留着**：最强理由是「示例多，模型能见到更多写法差异」
  （`yosuga_ed` 有 180BPM 齐唱 + `grid_align --parity`，`mushoku_ed1` 没有）。
  否决：那点差异已经在 `steps/07-grid/index.md`（网格重对齐）与
  `steps/11-design/impl/motif-catalog.md` §4b（两种风格对照表）里被**写成判据**了 ——
  判据比示例更容易被读到，也不会随示例一起被删。而保留它们的代价是 726MB 里
  99% 是噪声，且它们全在 git 里（165 个文件）。
- **只删 `blackbullet_ed`，其余四个都留**：最强理由是「小的四个加起来才 450KB」。
  否决（实测）：`one_line` 是**一次调试的中间态**（`DESIGN.md` 写的是"控制变量，
  不碰其它 32 句"），把它摆进示例目录会让人以为"逐句攻坚"是流程的一部分；
  `yosuga_op/ed` 与 `mushoku_ed1` 讲的是同一件事（Generator 用法），三份里留一份够。
  判据不是体积，是**"这一份是不是它自己那句话的唯一出处"**。
- **保留 `lyrics_example.txt` 作为"最小歌词样例"**：最强理由是「模板目录里放一份最小输入很自然」。
  否决：它与 `examples/mushoku_ed1/lyrics.txt` 逐字节相同，不构成"最小样例"；
  真正的最小样例应该在 `format.md` 的语法表里。留着它只会让"改一处忘一处"。
- **把示例整体移到 `static/music/`，examples 目录删掉**：最强理由是「工程就该在工程区」。
  否决：`examples/mushoku_ed1` 的价值是**给模型看**，它必须留在 skill 的引用范围内
  （`SKILL.md` 要能指到它、`steps/10-anime-bg` 的"先查同番工程"要用它）。
  工程区里的东西不进 git，也不该被 skill 的巡检依赖。

## Consequences

- `examples/` 从 728MB → 1.7MB，11 个文件全部进 git 且无二进制（唯一一张
  `review_spectrogram_example.png` 1.5MB 是"频谱图长什么样"的样本，保留）。
- `templates/` 从 2 个 → 1 个，与 `SKILL.md` 的引用一一对应。
- 实跑验证：`ASSFX_FONTS=<skill>/fonts uv run examples/mushoku_ed1/make_ass.py /tmp/out.ass`
  → 打印 30 句的 in/out/band/clamp，末行 `events: 9155`（搬运后仍可直接跑）。
- 已知边界：历史工程搬走后，`steps/10-anime-bg` 的"先查同番工程"在 skill 内只剩
  `mushoku_ed1` 一份可命中；ヨスガノソラ 的两份要靠 `static/music/` 才找得到。
  该步的 `index.md` 已把搜索范围写成"skill 的 `examples/` + 工程区 `static/music/<番名>/`"，
  不会因为搬家而漏查。
