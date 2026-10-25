# 10 原作内涵考据 + 番剧元素表(必做)

## 只做这一件事

把"这部作品在讲什么"变成两份可查的证据: `anime.background.json`(机器证据)+ `anime.notes.md`(人读的结论), 再把"哪些符号有大众共识"整理成 `anime.elements.md`(带来源计数)

**这一步决定后面所有配色的方向**. 跳过它, 13 步全做完也只能出一份"技术正确、但不对味"的字幕

## 一句话分工

**MV 画面告诉你"这一段在放什么", 原作内涵告诉你"这一段该是什么情绪". ** 只查角色表 = 只看得到"是谁", 决定不了"这一句该亮还是该暗". 实测教训: 某作的动画把原作"治愈的夏"改成了"寂寥的夏"  只查角色表会让配色方向从头就错

## 10a 先看邻居, 再动手搜

```bash
grep -l "<番名>" $SKILL_ROOT/examples/*/anime.notes.md
```

命中就**必读**, 并在自己的 notes 里写一行**继承声明**: 继承了哪几条母题、为什么这次不同. (当前 skill 只保留一份 `examples/mushoku_ed1`; **除它以外不许去读任何历史工程**, 见 `shared/hard-rules.md` 第 10 条.)

## 10b 抓结构化条目(bgm.tv)

```bash
hx-karaoke fetch_anime_bg.py --project proj --anime "<番名>" --song "<曲名>"
hx-karaoke fetch_anime_bg.py --project proj --anime "<番名>" --bgm-id <id>
```

产物里要用的是三样: `summary`(故事前提)、`characters[].summary`(每角色设定细节 → 可画的视觉母题)、`name_cn`(写卡片文案用). `--bgm-token` 只是提高限额, **不是**跳过这一步的理由

## 10c 六类必查检索 + 落成 notes

`fetch_anime_bg.py` 只回答"角色是谁". "**作品在讲什么**"要另外查六类(考察文 / 官方访谈 / 改编差异 / 题名考据 / 舞台原型 / 乐谱转调), 检索词与写法见 `impl/background-research.md` §2.5. **读了但没记出处 = 等于没读. **

## 10d 番剧元素表

角色象征物 / 能力 / 事件信物 / 世界观符号, **多源计数**: **A(≥3 来源)可当主母题, B(1–2)只能辅助, C(仅画面证据)只学形状不编语义**. 计数的筛子作用见 `impl/elements-table.md`

## 产物与过关条件(`check_gates.py --stage design` 会查)

| 文件 | 判据 |
|---|---|
| `anime.background.json` | `summary` 非空且角色 ≥6(少于此说明抓错了条目) |
| `anime.notes.md` | **存在**且 ≥500 字(占位即 FAIL); 缺"内核/主题"或"与原作的关系"、或没写出处 → WARN |
| `anime.elements.md` | **带来源计数的条目 ≥4**(门禁按表形状数: 元素名用 `**粗体**`、来源数紧随其后; 写法见 `impl/elements-table.md`) |

语义质量不做机械 FAIL(判"答得好不好"不可证伪, 硬设只会催生空标题)
**答得对不对由第 11 步设计表反向追责**: 设计表里每句配色若指不到 notes 的情绪曲线, 就是 notes 没写到位.

## 10e 接着填 `song-brief.md`(本步的第二件产物)

`anime.notes.md` 记的是**作品**. 这一步还要交**这首歌**那一份: `proj/song-brief.md`.

模板在 `templates/song-brief.md`, 四节:

| 节 | 回答什么 |
|---|---|
| 番剧背景 | 指向 `anime.notes.md` 的结论 |
| 歌曲纯歌词意境分析 | **不看画面不看番剧**, 只读歌词: 在说什么、情绪怎么走、哪句是转折 |
| 歌曲在番剧背景下的分析 | 这首歌**对应谁、对应哪段经历**; **必须点名角色**, 该名字要能在 `anime.background.json` 里找到 |
| 歌词特效 | 策略 + 指向 `anime.elements.md` 条目与 `design-table.md` 的句 |

两件事的差就是判断"这首歌是不是围绕某个角色写的"  它决定绘图元素与风格取谁的.
门禁 `check_gates.py --stage design` 的 `song-brief.md` 一项强制这一节必须点名真实角色.
