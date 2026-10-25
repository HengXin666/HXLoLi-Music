# karetpl  执行 ASS 内嵌模板程序

## 这个包解决什么

有些 ASS 成品不是手写出来的，而是**一份程序跑出来的**：

```
71462 行 Dialogue  ←  134 行 Comment（8 行 code + 35 行 template + 73 行 karaoke）
```

`Comment` 里写的是 Karaoke Templater 的模板语言：`code` 定义函数与状态、`template`
写模具与循环（`maxloop` / `multiloop` / `retime`）、`karaoke` 行带 `\k` 逐字时间。

**karetpl 就是那份程序的运行时**：读进来，执行，吐出 Dialogue。它不发明特效，
只把作者写好的程序跑出结果  所以"像不像"由**程序**决定，不由本包决定。

## 接口（外部只需要这四个名字）

```python
from karetpl import Program, Expander, Metrics, AssWriter

prog = Program.from_file("some.ass")        # 读程序
doc  = Expander(prog).expand()              # 执行 -> 事件
AssWriter.write(doc, "out.ass")             # 落盘
```

### Program  把 ASS 拆成"程序"与"数据"

```python
@dataclass
class Program:
    styles:    dict[str, Style]      # 样式表（字体/字号/边距/对齐）
    code:      list[Stmt]            # code once / code line / code syl  [按出现顺序]
    templates: list[Template]        # template 行
    karaoke:   list[SourceLine]      # karaoke 源行（带 \k 的歌词）

    @classmethod
    def from_file(cls, path) -> "Program": ...
    @classmethod
    def from_text(cls, text) -> "Program": ...
```

### Expander  执行

```python
class Expander:
    def __init__(self, prog, metrics=None, seed=None): ...
    def expand(self) -> list[Event]: ...            # 全部源行
    def expand_line(self, line) -> list[Event]: ... # 单句（调试用）
```

**为什么要 `metrics` 参数**：字宽来自字体度量，而字体可能不在本机。默认实现
按"每字 fs+spacing"整数进位；换字体时注入自己的实现即可，**不必改本包**。

### Metrics  可注入的度量（这是唯一需要外部数值的地方）

```python
class Metrics:
    def advance(self, ch, fs, spacing) -> float: ...   # 单字推进量
    def width(self, text, fs, spacing) -> float: ...   # 整串宽度
```

**默认实现的两个基准**（实测反推，两者不同，不能合并）：
- `line.width` 用整数进位：全角 = `fs + spacing`
- `$scenter` 用字体真实 advance：某成品实测 75.14（= fs 70 + spacing 5 + 0.14 的字体余量）

### AssWriter

```python
class AssWriter:
    @staticmethod
    def write(events, path, styles=None, info=None) -> int: ...  # 返回事件数
```

## 设计约束（不可协商）

### 1. 库只承担机械劳动，绝不封装审美决策

**能封装的**：读文件、执行循环、替换 `!expr!`、算时间、算坐标、写文件。

**不许封装的**：选哪个图形、用哪组颜色、什么时候爆发、母题怎么对应词义。

理由（实测教训）：一旦把"可爱系配色""高潮段加星星"这类做成 `theme="cute"` 之类的开关，
用它的人就只会填参数  **产出全是同一个味道**。这个包的价值在于**把作者程序里的
东西原样跑出来**，不替作者做选择。

判断标准：**同一个调用，换一份 Program 应当得到完全不同的结果**。如果本包里出现
任何"效果名"（如 `star_burst`），说明越界了。

### 2. 不猜，不静默

- 表达式求值失败 → 返回 `None`/`""` 并**记录**（`Expander.warnings`），不伪造
- `maxloop` / `multiloop` 求值失败 → 退回 1 层并**记录**，不抛给上层也不假装成功
- 未知 `retime` 模式 → 记录并使用 `line` 兜底

理由（实测教训）：静默退化会让"应该 1664 层"变成"1 层"，而产物看上去**依然有内容**，
于是错误被当成效果。

### 3. 单位在边界处钉死

Aegisub 的约定是**混用**的，实测踩过：
- `$lstart` / `$lend` / `syl.start_time` / `line.duration`  **毫秒**
- `syls` 内部的时间  **秒**
- `\t(a,b,...)` 的时间参数  **毫秒**
- `\pos` 的坐标  取整到整数像素（`697.5` → `697`）

转换只允许发生在**一处**（`Time` 值对象），别处一律不加 `*1000`。

## 与 assfx 的分工

| 包 | 方向 | 输入 → 输出 |
|---|---|---|
| **karetpl** | 上游（读别人的程序） | ASS(含模板) → 事件 |
| `assfx` | 下游（自己造事件） | 意图 → 事件 |

两者产出同一种东西（ASS 事件），可以互相接：`karetpl` 展开出来的事件，
能直接交给 `assfx` 的校验器、渲染器、门禁。**但不要互相 import** 
展开器不该依赖发射器的 API，反之亦然。

## 不做什么

- 不做渲染、不做抽帧、不做像素比对（那些是 `qa/` 与 `render/` 的职责）
- 不做歌词对齐、不做节拍检测（上游已经产出带 `\k` 的源行）
- 不解析 `\p` 绘图内容（绘图路径是数据，原样透传给 libass）

## 验收（唯一有意义的判据）

```bash
hx-karaoke verify.py <成品.ass> --line <句首秒> --adv <scenter 推进量>
```

它比对**执行同一份程序**得到的事件与原文件里的事件是否**逐字节相同**。

实测（2026-10-06，点兔 OP 钟表段）：

    源行 6.67-8.06s  JP_FX_A
      原文件同段事件 23 条 / 展开 23 条
      逐字节相同 23

「看起来像」不算  颜色差一位、时间差 10ms 都会被它抓出来。

## 已知边界

**能**：
- 执行 `code once/line/syl`、`template`、`maxloop`、`multiloop`、`retime`（10 种模式）
- 数值形式与表形式的 `multiloop`（后者按原版 Lua 的 `sum(tbl[i])` 展开成 1664 层这类量级）
- 注入字体度量（`Metrics`）与宿主函数（`Expander(prog, builtins={...})`）

**不能 / 未验证**：
- 只支持 Lua 子集（词法 / 语法 / 求值）。原程序若用了 `require`、协程、元表，会记进 `warnings`
- 不实现 `\p` 绘图的内容计算（绘图路径是数据，原样透传给 libass）
- **含 `math.random` 的段不能逐字节比对**。实测某成品 `JP_FX_B` 展开 1696 条、
  原版同段 2092 条，两边 `pos` 差 6~21px  全部来自粒子位置与 `tipi/N.png` 的随机选择。
  这类段应当**对分布**（条数量级、位置直方图、α 曲线），而不是对值
- `preline` / `postline` 依赖"上一句"，首句无上一句时退回自身（与原版一致，未逐字验证）

## 逐样式的实测状态（2026-10-06，点兔 OP）

| 样式 | 我展开 | 原版同段 | 逐字节相同 | 说明 |
|---|---|---|---|---|
| `JP_FX_A` | 23 | 43 | **23** | ✅ 全中（钟表段，无随机） |
| `JP_FX_CS` | 12 | 12 | 5 | 条数一致，差在 `line.duration` 的时序 |
| `JP_FX_C` | 33 | 51 | 1 | 同上 |
| `JP_FX_AS` | 38 | 515 | 28 | 少：`preline` 的行窗裁剪未实现 |
| `JP_FX_B` | 1371 | 2092 | 0 | 全员差 6~21px = `math.random` |
| `JP_FX_D` | 22 | 133 | 8 | 少 |

**结论**：**无随机的段已能逐字节复现**（`JP_FX_A` 23/23）。
差异集中在两类  随机的粒子（不可逐字节）与 `preline` 的行窗裁剪（待实现）。


