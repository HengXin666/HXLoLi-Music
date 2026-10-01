# 12 生成 ASS

## 只做这一件事

把设计表翻译成生成器，跑出 `out.ass`。出入场规划、band 登记、卡片都由库负责。

## 命令

```bash
cp <skill>/templates/make_ass_template.py proj/make_ass.py
# 改：ASSFX 路径、字体、JP_Y、PHRASES、fx_xxx 函数
uv run proj/make_ass.py proj/out.ass
```

## 库负责什么，你负责什么

- `assfx.gen.Generator` 负责**逐句出入场窗口规划**、`band()` 登记、`card()` 卡片。
- 你只写 `fx_xxx(f, ph, k)` 函数，**只通过** `f.shape / f.text / f.burst / f.drift / f.pulse / f.glow / f.floor_spin` 发射。
- 合いの手行**不放进 PHRASES**，在所属句的 fx 函数里用 `TM` 中 `call` 音拍时间触发。

```python
G = Generator(doc, L, lines, TM)      # lead=0.8：最早提前 0.8s 入场
G.render(PHRASES, FXMAP)              # 打印每句 in/out/band/clamp
G.card("title", 1.0, 6.0, items, fx)  # 卡片 band 自动 = 文字墨迹 + 5%
```

## 读出生成器的打印

每句会打印 `in / out / dout / band / fx / clamp`。
**clamp 很多说明特效设计尺寸超出 band —— 应主动缩小，而不是依赖夹取。**
band 只是上限不是目标尺寸：实测某工程 clamp 仅 10 次（看着很守规矩），
但图形尺寸只有同款的 1/10，FX 层单独渲染时整帧只有 35~1144 个亮像素，**特效等于不存在**。

## 卡片

只做【开头】与【片尾】两张，利用黑场与长前奏/尾奏。
**除这两张之外不要在歌词之间插任何文字** —— 尤其"间奏卡""序章卡"，本质是在歌词停顿时塞旁白，
且极易与相邻歌词行的时间窗互撞（实测撞出 6.8s 重叠）。
卡片时段必须**从"无歌词区间"反解出来**，不要手填，见 `steps/13-validate/impl/overlap.md`。

## 产物与过关条件

`proj/out.ass`；每句的 band 已登记、事件 Name 标注 `ly:<band>` / `fx:<band>` / `card:<name>`；
`clamp` 计数逐句过一眼。

## 具体做法

- `impl/library.md` —— `scripts/assfx/` 逐模块说明。**写生成器之前读。**
