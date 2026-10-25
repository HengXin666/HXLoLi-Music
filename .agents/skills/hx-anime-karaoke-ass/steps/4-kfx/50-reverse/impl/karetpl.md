# karetpl: 执行成品里的模板程序

## 什么时候用

成品 ASS 里有 `Comment:` 行带 `code` / `template` / `karaoke`  说明它的**生成器还在**，
可以直接执行，不必反推。

```bash
hx-karaoke scripts/karetpl/verify.py <成品.ass> --line <句首秒> --adv <scenter 推进量>
```

实测（点兔 OP 钟表段）：

```
源行 6.67-8.06s  JP_FX_A
  原文件同段事件 23 条 / 展开 23 条
  逐字节相同 23          <- 退出码 0
```

`--adv` 是 `$scenter` 用的字体推进量（那首歌实测 75.14 = fs70 + spacing5 + 0.14 余量）。
不给就按"每字 = fs + spacing"的整数进位算。

## 四个对外名字

```python
from karetpl import Program, Expander, Metrics, AssWriter

prog = Program.from_file("some.ass")          # 读程序
evs  = Expander(prog, metrics=MyFont()).expand()   # 执行
AssWriter.write(evs, "out.ass", styles=prog.styles,
                res=(prog.res_x, prog.res_y))
```

完整契约在 `scripts/karetpl/CONTRACT.md`。三条要记住的：

### 1. 库只承担机械劳动，不封装审美决策

```python
# 对：同一个调用，换一份 Program 得到完全不同的结果
evs = Expander(Program.from_file(src)).expand()

# 错：任何形如 "effect=star_burst" 的开关
```

实测同一接口对不同源行：`JP_FX_A` 23 条 / `JP_FX_AS` 569 条 / `JP_FX_B` 1696 条 
差异全来自**被执行的程序**。这是刻意的：一旦把"效果"做成参数，用它的人就只会填空。

### 2. 字体度量可注入，但只此一处

```python
class MyFont(Metrics):
    """换字体只改这里，不改 karetpl。"""
    def advance(self, ch, fs, spacing):
        return read_from_ttf(ch, fs) + spacing
```

`line.width` 与 `$scenter` 是**两个不同基准**（实测某成品 75 vs 75.14），
`Metrics.center_advance` 是给后者用的。

### 3. 不猜、不静默

求值失败会记进 `Expander.warnings`，不伪造成功。实测教训：静默退化会让
"应该 1664 层"变成"1 层"，而产物**看上去依然有内容**，于是错误被当成效果。

## 单位在边界处钉死

Aegisub 的约定是**混用**的，实测踩过：

| 量 | 单位 |
|---|---|
`$lstart` / `$lend` / `syl.start_time` / `line.duration` | **毫秒** |
`syls` 内部的时间 | **秒** |
`\t(a,b,...)` 的时间参数 | **毫秒** |
`$si` | **0-based**（不是 1-based） |
`\pos` 的坐标 | 取整到整数像素（`697.5` → `697`） |

转换只发生在 `directives.py` 一处，别处不加 `*1000`。

## 包结构

| 文件 | 职责 |
|---|---|
`model.py` | 值对象：`Program` / `SourceLine` / `Syllable` / `Template` / `Event` |
`parse.py` | `Program.from_file`  把 ASS 拆成"程序"与"数据" |
`evaluator.py` | `!expr!` 与 `$name` 的求值门面（AST 缓存） |
`lua.py` | Lua 子集解释器 |
`directives.py` | `maxloop` / `multiloop` / `retime`（含单位换算） |
`metrics.py` | 🔌 度量注入点 |
`expander.py` | 执行器 |
`bezier.py` | 贝塞尔等速采样（原程序依赖它把曲线采样成粒子串） |
`writer.py` | 落盘 |
`verify.py` | 逐字节自检 |

## 已知边界

- 只支持 Lua 子集。原程序若用 `require` / 协程 / 元表，会记进 `warnings`
- 不解析 `\p` 绘图内容（绘图路径是数据，原样透传给 libass）
- 含 `math.random` 的段不能逐字节比对（见 `index.md` 的「随机量怎么办」）
