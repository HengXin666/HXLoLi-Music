# 12 生成 ASS

## 只做这一件事

把设计表翻译成生成器, 跑出 `out.ass`. 出入场规划、band 登记、卡片都由库负责.

## 命令

```bash
cp <skill>/templates/make_ass_template.py proj/make_ass.py
# 改：ASSFX 路径、字体、JP_Y、PHRASES、fx_xxx 函数
uv run proj/make_ass.py proj/out.ass
```

这一步要用的脚本: `<skill>/scripts/assfx/gen.py`(`Generator` / `card()` 的实现在这里).
它和 `scripts/` 下其它脚本一样, 用 uv 的 inline 依赖自建环境; 直接跑工程里的 `make_ass.py` 即可.

## 库负责什么, 你负责什么

- `assfx.gen.Generator` 负责**逐句出入场窗口规划**、`band()` 登记、`card()` 卡片.
- 你只写 `fx_xxx(f, ph, k)` 函数, **只通过** `f.shape / f.text / f.burst / f.drift / f.pulse / f.glow / f.floor_spin` 发射.
- 合いの手行**不放进 PHRASES**, 在所属句的 fx 函数里用 `TM` 中 `call` 音拍时间触发.

```python
G = Generator(doc, L, lines, TM)      # lead=0.8：最早提前 0.8s 入场
G.render(PHRASES, FXMAP)              # 打印每句 in/out/band/clamp
G.card("title", 1.0, 6.0, items, fx)  # 卡片 band 自动 = 文字墨迹 + 5%
```

## 读出生成器的打印

每句会打印 `in / out / dout / band / fx / clamp`.
**clamp 很多说明特效设计尺寸超出 band —— 应主动缩小, 而不是依赖夹取. **
band 只是上限不是目标尺寸: 实测某工程 clamp 仅 10 次(看着很守规矩),
但图形尺寸只有同款的 1/10, FX 层单独渲染时整帧只有 35~1144 个亮像素, **特效等于不存在**.

## 卡片

只做【开头】与【片尾】两张, 利用黑场与长前奏/尾奏.
**除这两张之外不要在歌词之间插任何文字** —— 尤其"间奏卡""序章卡", 本质是在歌词停顿时塞旁白,
且极易与相邻歌词行的时间窗互撞(实测撞出 6.8s 重叠).
卡片时段必须**从"无歌词区间"反解出来**, 不要手填, 见 `steps/13-validate/impl/overlap.md`.

## 产物与过关条件

`proj/out.ass`; 每句的 band 已登记、事件 Name 标注 `ly:<band>` / `fx:<band>` / `card:<name>`;
`clamp` 计数逐句过一眼.

## 模板与参考工程

- `<skill>/templates/make_ass_template.py` —— 最小可运行生成器, 本步的起点. 它的 docstring 写了要改的三处.
- `<skill>/examples/mushoku_ed1/` —— 唯一保留的完整工程(30 句逐句设计 + 71 处人工校时 fixes +
  标题/片尾卡 + 合格的 `anime.notes.md`). **卡住时读它的 `make_ass.py`**, 不要重新发明写法.
  它按 `examples/<曲目>/` 上两级定位本 skill 的 `scripts/`, 直接跑即可;
  拷到别处时用 `ASSFX` 覆盖 scripts 路径、`ASSFX_FONTS` 覆盖字体目录.
  其余历史工程在 `static/music/<番名>/` 下(属工程, 不属 skill).

## 这一步要用的脚本

- `<skill>/scripts/assfx/gen.py` - `Generator`: 逐句出入场窗口规划, band 登记, `card()` 卡片; `find/seq/span/mid` 等查字工具
- `<skill>/scripts/assfx/` - 整套 ASS 生成库, 逐模块说明见 `impl/library.md`

## 具体做法

- `impl/library.md` —— `scripts/assfx/` 逐模块说明(含 `gen.py` 的 `Generator` / `card()` 契约).
  **写生成器之前读. **
- `steps/11-design/impl/motif-catalog.md` —— 母题 → 图形速查表与动画语汇清单.
- `steps/11-design/impl/density.md` —— 给完特效觉得"差口气"时读(密度下限与分层).
