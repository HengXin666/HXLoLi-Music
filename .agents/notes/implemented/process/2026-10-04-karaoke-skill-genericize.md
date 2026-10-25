# Agent Note: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈

Status: implemented

Decision-ID: karaoke-skill-genericize

- 决策依据: 用户原话「把这些都删掉，去掉这些引用，将这个 skill 让它通用化，
  然后去掉一些大段陈铺列表，列出文件的那种东西…渐进式加载 skill 是用于规范流程以及启发 ai 的，
  不是写死流程，还是需要 ai 能发挥想象力，基于事实进行动态决策设计特效的」
- 相关: [karaoke-runtime-artifacts-out-of-skill](2026-10-02-karaoke-runtime-artifacts-out-of-skill.md)
  （同一个判据的前半段：产物移出 skill。这次是后半段：**事实与署名也要移出**）

## Code

- `.agents/skills/hx-anime-karaoke-ass/examples/mushoku_ed1/make_ass.py`
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
- `.agents/skills/hx-anime-karaoke-ass/templates/make_ass_template.py`

## Problem

`2026-10-02-karaoke-runtime-artifacts-out-of-skill` 把**文件**移出了 skill，但**知识**没移。
审计发现 skill 里嵌着一份具体制作的完整指纹，且分三类：

**一、作品名与专属道具（读者会以为这是 skill 的一部分）**

| 位置 | 内容 |
|---|---|
| `scripts/assfx/asset/props.py` | 41 个图标的 docstring 直接写角色名：`受诅之子/ガストレア`、`蒂娜`、`木更`、`布施翠`、`常花`、`原肠动物病毒` |
| `scripts/assfx/asset/bake_shapes.py:37` | `MV_CROPS` 硬编码某部 MV 的四帧坐标（24.5s / 137s / 89s / 110s），**而它自己的注释写着"不能写死在 skill 里"** |
| `scripts/assfx/draw/shapes.py:480,640` | 两个分节标题带作品名；两个 docstring 写角色（"穹的兔子"、"天女目神社"） |
| `steps/3-anime-bg/10-anime-bg/impl/elements-table.md` | 整份文件是某部番的元素表实例 |
| `steps/4-kfx/42-text-main/impl/motif-catalog.md` 等 20+ 处 | 表格列名写成 `Charlotte OP` / `天使の3P` / `点兔` / `东方` |
| `scripts/kfx/score/score_kfx.py:240` | `for c in ("out_v5.ass", "out.ass")`  把某工程的产物名写死进通用打分器 |

**二、以"本工程"匿名、实际仍指向同一份制作**：47 处。最典型的是
`scripts/qa/validate_ass.py:201` 的 `Layer 21/22 各 3651 条`、`scripts/kfx/voices.py:219` 的
`0.2% -> 30%+`  复算这两个数**都对不上**（实测 2733 条 / 13.9% 与 92.7%），
即引用在数字漂移后没有同步，读者无法察觉它已经过期。

**三、大段铺陈的文件清单**：26 个 `index.md` 末尾各有 `## 这一步要用的脚本` 与 `## 具体做法`
两节，共 200 行，形式是"这个脚本干什么 / 那个脚本干什么"。这些信息
(a) 与 `scripts/` 里的 docstring 重复，(b) 把"读到哪一步该做什么"变成"照着清单跑"。

判据一句话：**skill 里的每个数字都该能指到"怎么量的"，而不是"某个工程是多少"。**

## Decision

1. **作品名与专属道具全部抽象化**。`props.py` 的 41 个图标保留（它们是通用物件：眼/剑/盾/花/雪…），
   只改 docstring 与分组注释；`shapes.py` 的 32 个函数**保留**（翅膀/音符/彩旗/漫画爆炸框都是通用语汇），
   只去掉分节标题里的作品名与 docstring 里的角色名。
2. **`MV_CROPS` 改为工程传入**：`bake_shapes.py` 新增 `--crops <json>`，
   skill 里的默认值清空。坐标是"某个工程某一帧的事实"，只能跟着工程走。
3. **`score_kfx.py` 的产物发现改为"工程根下最近修改的 `.ass`"**，不写死文件名。
4. **写死的单样本阈值改成"量法"**。三处：
   - `beat.py` 头部由"某成品的参数表"改为"参数区间 + 怎么从这首歌量出来"；
   - `score_kfx.py` 的 C2 由绝对条数 `>=6` 改为相对口径 `中位>=4 且 最小>=2`，
     并在 `three-layers.md` / `thread.md` 同步（原文自己就承认"本工程中位 4 没过自己写的判据"）；
   - `density.md` 的"实测某工程 = 19"改为"先量基线，再判高低"。
5. **删除 200 行清单式铺陈**（26 个 `index.md` 的 `## 这一步要用的脚本` / `## 具体做法`）。
   需要时改由 `steps/4-kfx/49-generate/impl/library.md` 的**任务导向表**回答
   （"你想做 X → 去哪个模块"），而不是"哪个文件存在"。
6. **软化"照抄"类指令**：`读到此处即止, 不要重新推导` → `直接用它, 不用重新推导`；
   `照抄即可` → `起点, 不是终点`；`不许改` → `这几个词不能改`。
7. **SKILL.md 增写一节「这套 skill 是什么, 不是什么」**，明确"判据告诉你下限，不告诉你上限；
   参数要从这首歌自己量出来；门禁只拦没做与明显不合格，不拦你选了另一种做法"。

## Alternatives considered

- **什么都不做，只删 `props.py` 里几个 docstring**：最强理由是「作品名只是注释，不影响行为」。
  否决：`score_kfx.py` 的 `("out_v5.ass", "out.ass")` 与 `bake_shapes.py` 的 `MV_CROPS`
  是**行为**，不是注释  前者让别的工程评到错的文件，后者把某帧坐标当成 skill 的默认值。
  只改注释等于承认"其它地方也一样，但懒得查"。
- **把 32 个"作品分节"函数整体删除**：最强理由是「它们既然归在某作品节下，就是过拟合」。
  否决：逐个读过后发现绝大多数是**通用语汇**（翅膀、音符、彩旗、漫画爆炸框、帐篷、仙人掌、
  跨栏、铜锣），只是**被归错了组**。删掉会损失能力，而问题（读者以为它们属于某作品）
  改分节标题就能解决。实测确认：`shape_gallery.py` 全部引用它们，示例工程一个都没用到。
- **保留清单但压缩成表格**：最强理由是「信息量没丢，只是排版更紧」。否决：清单的价值是
  "不用读代码就知道有什么脚本"，但**这个价值本身就是问题**  它让 agent 跳过读代码。
  真正需要的是"我想做 X，该去哪"，这由 `library.md` 的任务表回答。
- **把过期数字直接删掉**：最强理由是「错的不如没有」。否决：数字是"踩过坑"的证据，
  删掉会让读者重犯。改为**抽象化保留**（`0.2% -> 30%+` → `0.2% -> 30%+`，但去掉"本工程"），
  并在 SKILL.md 里说明"步骤里的数字是量级参照，不是目标值"。

## Consequences

- 全库 `漆黑子弹|トコハナ|ヨスガ|無職|ピンキー|ツナグキズナ|东方|点兔|Charlotte|天使の3P|罪恶王冠`
  等作品名 **grep 为 0**（`examples/` 除外，那里是示例工程本体）。
- 脚本层 `本工程` grep 为 0；`scripts/` 22 个文件 `ast.parse` 全通过。
- `steps/**/*.md` 减少 200 行；`library.md` 由 40 行铺陈改为 36 行任务表。
- 实跑验证：`score_kfx.py` 对 4 个工程仍正常出分（罪恶王冠 9.3、漆黑子弹 3.0、东方 1.5），
  fallback 改动未改变既有行为（这些工程根下都只有一个 `.ass`）。
- `beat.py` 删掉两处重复/死代码（`_hex` 定义两次、`_RngShim` 从未实例化、
  `_size_tag` 从未被调用），并把"未绑素材"从 `ZeroDivisionError` 改为明确报错：
  实测 `beat_scatter` 在 `BEAT_SHAPES` 为空时打印
  `卡点层没绑素材: 先调 beat.bind_baked(...) 再发卡点`。
- 已知边界：`validate_skill.py` 仍报 38 个 WARN，全部是"脚本没被 SKILL.md 引用" 
  这是**有意**的（脚本由 `steps/*/index.md` 引用，不该塞进 SKILL.md 凑引用）。
- 已知未做：`examples/mushoku_ed1` 的 `anime.notes.md` 里仍有 2 处作品名 
  那是**示例工程自己的内容**，不是 skill 的契约，保留是正确的。
