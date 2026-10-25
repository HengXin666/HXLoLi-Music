# PyonFX 调研报告（架构决策用）

调研时间 2026-10-06 | 上游 commit `c342624e`（= v0.11.0，2025-07-19）| 本机 Python 3.14.7 + ffmpeg n9.0.2（libass）

**证据分级**：本报告每条事实标注来源。`[代码]` = 上游源码行号（已核对 GitHub master 与 v0.11.0 tag 一致）；
`[实测]` = 本机隔离 venv 安装 `pyonfx==0.11.0` 后跑的脚本；`[渲染]` = 把生成的 ASS 交给本机 ffmpeg/libass 渲染后量像素。

---

## 1. 基本信息

| 项 | 值 | 来源 |
|---|---|---|
| 仓库 | https://github.com/CoffeeStraw/PyonFX | `[API]` gh api repos/CoffeeStraw/PyonFX |
| 作者 | Antonio Strippoli（CoffeeStraw，clarationio98@gmail.com） | `pyproject.toml` authors + `pyonfx/ass_core.py:2` 版权头 |
| License | **LGPL-3.0-or-later** | `pyproject.toml:9`；GitHub API `license.spdx_id = LGPL-3.0`；`LICENSE` 全文为 LGPLv3 |
| 当前版本 | **0.11.0** | `pyproject.toml:4` + PyPI `version=0.11.0` |
| master 最后提交 | **2025-07-19T12:25:12Z** `c342624e` "Merge pull request #65 from CoffeeStraw/0.11.0" | `[API]` commits?sha=master |
| repo `pushed_at` | 2025-08-31T11:02:39Z  **这是 gh-pages 文档部署，不是代码** | 分支 `gh-pages` `17519c61` "Deployed bbc49ac with MkDocs 1.6.1" |
| 近一年提交数 | **0**（since=2025-07-19 起） | `[API]` commits?since=2025-07-19 |
| 历史提交 | 367 条；年份分布 2019×89 / 2020×52 / 2021×57 / 2022×5 / 2024×17 / 2025×147 | `[实测]` git log |
| star / fork / open issues | **187 / 15 / 8** | `[API]` repo 元数据 |
| contributors | CoffeeStraw 292、Funami580 25、moi15moi 21、Doko-Demo-Doa 11、cN3rd 8、Ichunjo 5、LightArrowsEXE 4 | `[API]` contributors |
| 发布节奏 | 0.9.9(2021-04-11) 0.9.10 … 0.9.13(2022-03-03) **停更 3 年** 0.9.16(2025-06-07) 0.10.0(2025-06-22) 0.10.1(2025-07-10) 0.11.0(2025-07-19) | `[API]` PyPI JSON releases |
| 文档站（两个都活） | README 主推 https://pyonfx.rtfd.io/（Sphinx，HTTP 200）；另有 https://coffeestraw.github.io/PyonFX/（MkDocs Material，2025-08-31 建站） | `README.md:12`、`.readthedocs.yaml`、`[API]` pages |
| Python 要求 | `>=3.10`（已在 0.11.0 移除 `from __future__ import annotations`） | `pyproject.toml:12`、commit `74ea7c9b` 系列 |
| CI | 4 个 Python 版本 × {windows-latest lint} + {ubuntu/macos/windows test}，pytest 1209 行测试 | `.github/workflows/ci.yml`、`tests/` 行数统计 |

**活跃度判定：低活跃但未死。** 2019–2021 高速迭代 → 2022–2024 近停 → 2025 年 6–7 月一波大重构（Shape/Pixel 模块化、0.10/0.11）→ 此后 14 个月零代码提交。issue 队列有 8 个开放项（#9 示例、#8 音频解码、#29 LBYL→EAFP、#66 OKLab、#67 粒子系统、#68 文档更新、#69 Shape 不可变、#70 retime）。

---

## 2. 模块架构

`pyonfx/` 只有 **7 个模块、6114 行**（`[实测]` wc -l）：

```text
pyonfx/
├── __init__.py      8 行   re-export 全部公开符号
├── ass_core.py   1643 行   Meta / Style / Char / Syllable / Word / Line / Ass
├── convert.py     772 行   Convert（时间・颜色・文本→Shape/Clip/Pixel） + ColorModel 枚举
├── font.py        322 行   Font（平台字体度量 + 字形轮廓→Shape）
├── pixel.py       322 行   Pixel / PixelCollection（0.11.0 新增）
├── shape.py      2131 行   ShapeElement / Shape（几何运算、布尔、morph）
└── utils.py       916 行   Utils / FrameUtility / ColorUtility
```

`[代码]` 与 `__init__.py` 的导出面一致。

### 2.1 数据结构（`ass_core.py`）这是它的真正内核

```python
Meta            wrap_style, scaled_border_and_shadow, play_res_x, play_res_y,
                audio, video, timestamps            # ass_core.py:46-118
Style           24 字段，与 ASS V4+ Style 行一一对应（含 name 字段）  # ass_core.py:120-274
Char            i, word_i, syl_i, syl_char_i, start/end/duration, styleref,
                text, inline_fx, width, height, x/y,
                left/center/right/top/middle/bottom                  # ass_core.py:276-321
Syllable        i, word_i, start/end/duration, styleref, text, tags,
                inline_fx, prespace, postspace, width/height, x/y, LCRTMB  # ass_core.py:325-372
Word            i, start/end/duration, styleref, text, prespace, postspace, …  # ass_core.py:376-417
Line            comment, layer, start/end_time, style, styleref, actor,
                margin_l/r/v, effect, raw_text, text, i, duration,
                leadin, leadout, width, height, ascent, descent,
                internal_leading, external_leading, x/y, LCRTMB,
                words[], syls[], chars[]                             # ass_core.py:421-494
```

全部是 `@dataclass(slots=True)`。`Line.copy()` 是深拷贝（`ass_core.py:496`）**这是全库性能瓶颈的源头**。

### 2.2 Ass 类（输入输出门面，`ass_core.py:589-1583`）

```python
Ass(path_input, path_output="output.ass", keep_original=True,
    extended=True, vertical_kanji=False)
get_data()  -> (meta, styles, lines)        # ass_core.py:1313
add_style(name, style)                       # ass_core.py:1321  插进 [V4+ Styles]
write_line(line)                             # ass_core.py:1346  只 append 字符串
save(quiet=False)                            # ass_core.py:1358  真正落盘
open_aegisub() / open_mpv()                  # ass_core.py:1423 / 1448
@io.track 装饰器                              # ass_core.py:1555  计时/统计
Ass.PIXEL_STYLE                              # ass_core.py:620   给像素用的轻量样式
```

### 2.3 Convert（`convert.py`）

`time` / `alpha_ass_to_dec` / `alpha_dec_to_ass` / `color` / `color_ass_to_rgb` / `color_ass_to_hsv` / `color_rgb_to_ass` / `color_rgb_to_hsv` / `color_hsv_to_ass` / `color_hsv_to_rgb`（`convert.py:49-450`）；`text_to_shape`(452) / `text_to_clip`(503) / `text_to_pixels`(577) / `shape_to_pixels`(618) / `image_to_pixels`(708)。
`ColorModel` 枚举 7 种：`ASS/ASS_STYLE/RGB/RGB_STR/RGBA/RGBA_STR/HSV`（`convert.py:39-46`）。实测 `Convert.color("&H0000FF&", ColorModel.ASS, ColorModel.RGB)` 正常；**第二个参数必须是 ColorModel 枚举，传字符串 `'H'` 会 ValueError**（`[实测]`）。

### 2.4 Shape（`shape.py`，2131 行，全库最重）

```python
构造：Shape(drawing_cmds) / from_ass_drawing_cmd / from_multipolygon
工厂：polygon(edges, side) / ellipse(w, h) / ring(out, in) / heart(size[,offset])
      / star(edges, inner, outer) / glance(...)
变换：move / scale / rotate / shear / align(an[,anchor]) / map
几何：bounding(exact=False) / flatten(tol) / split / buffer / to_multipolygon
集合：boolean(other, op)      # 依赖 shapely
动画：morph(target, t) / morph_multi(dict_a, dict_b, t)   # 0.10 新增
属性：drawing_cmds（str(rise) 返回 ASS 绘图串）
```

绘图命令解析支持 **`m n l p b s c` 全集**（`shape.py:64-127`），`b` 按 3 点分组、`s` 需 ≥3 点、`p` 1 点、`c` 0 点  实测 `Shape("m 0 0 b 10 0 20 10 30 10 s 40 10 50 0 60 0 70 10 p 80 10 c")` 解析为 `[('m',1),('b',3),('s',4),('p',1),('c',0)]`（`[实测]`）。

### 2.5 Font（`font.py`）

**平台分叉，这是最重要的环境事实**：Windows 走 `win32gui/win32ui` GDI（`font.py:71-98`）；Linux/macOS 走 **cairo + Pango(PangoCairo)**（`font.py:99-127`）。`FONT_PRECISION=64`、`LIBASS_FONTHACK=True`、`PANGO_SCALE=1024`（`font.py:41-43`）。依赖里 `pywin32; platform_system=='Windows'` 对 `pycairo; Linux or Darwin`（`pyproject.toml:14-25`）。

### 2.6 Utils / FrameUtility / ColorUtility（`utils.py`）

```python
Utils.progress_bar / all_non_empty / accelerate(pct, acc) / interpolate(pct, v1, v2[, acc])
FrameUtility(start_ms, end_ms, timestamps, n_fr=1)   # 帧迭代器，返回 (start, end, i, n)
ColorUtility(lines, offset=0)  -> get_color_change(l) / get_fr_color_change(l)
```

`Utils.accelerate` 走 **Penner 缓动**：`acc` 可传 float（幂）、字符串（`in_back/out_cubic/in_out_elastic/…`，实际由 `rpeasings` 库提供）、可调用对象（`utils.py:137-207`）。实测 `accelerate(0.5,'out_cubic')=0.875`、`accelerate(0.5,2.0)=0.25`（`[实测]`）。

---

## 3. 如何发出 ASS：**没有中间表示，纯 `str` 拼接 + 逐行追加**

### 3.1 三条链路（全部在 `ass_core.py`）

**A. 输出头 = 输入文件的原文行**（不是模板）。解析器把每一行原样存进 `self._output`：

```python
# ass_core.py:685-722
current_section = ""
for line in file:
    if section_match:                       # 行首 [XXX]
        current_section = section_match.group(1)
        if current_section != "Aegisub Extradata":
            self._output.append(line)       # ← 原样保留
        continue
    if line.startswith("Format") or not line.strip():
        self._output.append(line)
    elif current_section in ("Script Info", "Aegisub Project Garbage"):
        line = self.meta.parse_line(line, self.path_input)
        self._output.append(line)           # ← 只把 Audio/Video File 换成绝对路径
    elif current_section == "V4+ Styles":
        self.styles[style.name] = Style.from_ass_line(line)
        self._output.append(line)
    elif current_section == "Events":
        self.lines.append(Line.from_ass_line(line, line_index, self.styles))
        if keep_original:
            self._output.append(re.sub(r"^(Dialogue|Comment):", "Comment:", line, count=1))
```

`[实测]` 验证：
- 输入**没有** `[Script Info]` 时，输出文件第一行直接是 `[V4+ Styles]`  头完全继承自输入。
- `[Aegisub Extradata]` 段被摘出，在 `save()` 时**追加到文件末尾**（`ass_core.py:1368-1370`），实测原在第 7 行、输出落在第 15 行（总 16 行）。
- `keep_original=True`（默认！）时原文行被改写成 `Comment:` 一起输出。

**B. 事件 = `Line.serialize()` 的 f-string**：

```python
# ass_core.py:574-586
def serialize(self) -> str:
    return (f"{'Comment' if self.comment else 'Dialogue'}: {self.layer},"
            f"{Convert.time(max(0, int(self.start_time)))},"
            f"{Convert.time(max(0, int(self.end_time)))},{self.style},{self.actor},"
            f"{self.margin_l:04d},{self.margin_r:04d},{self.margin_v:04d},{self.effect},"
            f"{self.text}\n")
```

注意 **`self.text` 原样吐出，不做任何转义/校验**（`[实测]`：把 VSFilterMod 全套标签塞进 `l.text` 后逐字节出现在输出里）。

**C. `write_line` 只 append 字符串**，`save()` 才 `open(path, "w", encoding="utf-8-sig")` 写盘（`ass_core.py:1355/1366`）。BOM 是硬编码的。

### 3.2 没有的东西

- ❌ **没有 IR**：`Shape` 是唯一的结构化产物，但它 `__repr__` 直接返回 `drawing_cmds` 字符串（`shape.py:174-176`），塞进 f-string 即用。
- ❌ **没有 tag 构造器 / tag 对象 / 校验器**：全仓 `grep -E "def .*tag|override_tag|validate_tag"` 零命中。用 AST 剔除 docstring 后，**运行期真正拼出 override tag 的只有 `utils.py` 的 12 行**，且全是 `\1c \3c \4c \t(` 这四类（见 §4.3）。
- ❌ **没有模板引擎**：没有 header 模板、没有事件模板。官方推荐的"模板"做法是**手写 Python 函数的 f-string**（`examples/1 - Basics/4 - Organizing the code.py` 就是空函数骨架）。
- ✅ **唯一的结构化入口**是 `Ass.add_style()`：它扫描 `self._output` 找 `[V4+ Styles]` 段尾插一行 `Style.serialize()`（`ass_core.py:1321-1344`）。`[实测]` 落盘得到 `Style: VSM,Arial,50,&H00FFFFFF,…`  注意 `border_style` 是 `bool`，`True→"3"` / `False→"1"`（`ass_core.py:226`），**无法表达 ASS 里其它 BorderStyle 值**。

### 3.3 结论

**PyonFX 是「带测量能力的 ASS 文本生成器」，不是「ASS 编译器」。** 它负责把 ASS 解析成对象、算好每个字的位置时间、提供几何与颜色工具，然后把 `Line.text` 这个字符串原样吐出去。**标签的正确性、语义、兼容性全部由使用者负责。**

---

## 4. 标签覆盖度（逐个核对）

### 4.1 判定口径

PyonFX 对标签只有三种态度，**没有第四种**：

1. **专用 API** — 库里有函数会**代替你**生成该标签；
2. **写 raw tag** — `l.text = "{\\xxx}"`，库原样透传，**不做任何校验**；
3. **不支持** — 库既没有 API，透传出去后目标渲染器也认不了。

关键事实：**即使第 1 类，也不是"你用 API 它就自动加标签"**只有 `Convert.text_to_shape` 的 docstring 示例里写死了 `\an7\pos(...)\p1`，而那是文档，不是运行时代码。例子见 `convert.py:473` / `convert.py:529`（都在 docstring 内）。

### 4.2 对照表

| 标签 | PyonFX 侧 | 结论 | 证据 |
|---|---|---|---|
| `\pos` | 无 API；算好 `syl.center/middle`、`line.left/top` 等供你填 | **需要手写** | `ass_core.py:781-816`（位置计算）、`examples/2 - Beginner/2 - Utilities.py` |
| `\move` | 无 API | **需要手写** | `examples/2 - Beginner/3 - Variants.py`（手写 `\move(...)`） |
| `\org` | 无 API | **需要手写** | 全仓 0 命中 |
| `\frx / \fry / \frz` | 无 API | **需要手写** | 全仓 0 命中（`Shape.rotate` 是几何旋转，产出坐标不是标签） |
| `\fscx / \fscy` | 无 API；`Convert.text_to_shape(obj, fscx, fscy)` 用它们**改度量**而非写标签 | **需要手写** | `convert.py:452-501` |
| `\fsp` | 无 API；`Style.spacing` 参与度量 | **需要手写** | `font.py:158-193` |
| `\fad` | 无 API | **需要手写** | 示例里手写 `\fad(%d,0)` |
| `\fade`（4 参 3 段版本） | 无 API | **需要手写** | 全仓 0 命中 |
| `\clip`（矩形） | **半支持**：`Convert.text_to_clip` 产出矢量 clip 串 | **矩形需手写；矢量有 API 生成 Shape 但仍需手写 `\clip(...)` 包裹** | `convert.py:503-575`，示例 `{\an5\pos(..)\clip(%s)}` |
| `\clip`（矢量绘图） | 同上，返回 `Shape`（`__repr__` = 绘图串） | **需要手写包裹** | `convert.py:503` |
| `\iclip` | 无 API | **需要手写** | 全仓 0 命中 |
| `\t`（含 accel） | **半支持**：`ColorUtility.get_color_change()` 生成 `\t(t1,t2,accel,\1c…)` 串 | **颜色类可自动；其余需手写** | `utils.py:755-775`，`[实测]` 输出 `\t(1,1000,2.0\1c&H0000FF&…)` |
| `\blur` | 无 API | **需要手写** | 全仓 0 命中 |
| `\be` | 无 API | **需要手写** | 全仓 0 命中 |
| `\bord / \xbord / \ybord` | 无 API（`Style.outline` 是样式级） | **需要手写** | 全仓 0 命中 |
| `\shad / \xshad / \yshad` | 无 API（`Style.shadow` 是样式级） | **需要手写** | 全仓 0 命中 |
| `\1c \2c \3c \4c` | **有 API**：`ColorUtility` 只识别生成 `\1c \3c \4c`；`Convert.color*` 做格式转换 | **1c/3c/4c 可自动（取值受限），2c 需手写** | `utils.py:600-602`（正则只覆盖 1c/3c/4c）、`[实测]` |
| `\1a \2a \3a \4a` | 无 API（`Convert.alpha_dec_to_ass` 只做数值转换） | **需要手写** | 全仓 0 命中 |
| `\alpha` | 无 API | **需要手写** | 示例手写 `\alpha%s` |
| `\an` | 无 API（`Style.alignment` 是样式级） | **需要手写** | 全仓命中全是 docstring/示例 |
| `\a`（legacy 对齐） | 无 API | **需要手写** | 全仓 0 命中 |
| `\p`（含 `\p b` / `\p bo`） | **无 API**；`Shape` 产出的绘图串需要你手写 `\p1` 包裹 | **需要手写**。**`\p b` / `\p bo` 本身在两个引擎里都无效**（见 §4.4） | `shape.py:129-133` 只在 docstring 提到 `{\p}` |
| `\r` | 无 API | **需要手写** | 示例 `examples/` 里出现 1 次 |
| `\fn` | 无 API（`Style.fontname` 是样式级） | **需要手写** | 全仓 0 命中 |
| `\fs` | 无 API（`Style.fontsize` 是样式级） | **需要手写** | 全仓 0 命中 |
| `\b \i \u \s` | 无 API（`Style.bold/italic/underline/strikeout` 是样式级） | **需要手写** | 全仓 0 命中 |
| `\k \kf \ko \K` | **解析侧完整支持**（建 `Syllable` 对象）；**生成侧无 API** | **解析：原生支持；写出：需要手写** | `ass_core.py:923` 正则 `\\[kK][fot]?(\d+)?` |
| `\kt` | **解析侧被当成 `\k` 处理，语义错误** | **需要手写；且解析结果不可信** | 见 §4.5 |

### 4.3 `ColorUtility` 是唯一会替你写标签的地方，边界很窄

```python
# utils.py:596-602
tag_all  = re.compile(r"{.*?}")
tag_t    = re.compile(r"\\t\( *?(-?\d+?) *?, *?(-?\d+?) *?, *(.+?) *?\)")
tag_c1   = re.compile(r"\\1c(&H.{6}&)")
tag_c3   = re.compile(r"\\3c(&H.{6}&)")
tag_c4   = re.compile(r"\\4c(&H.{6}&)")
```

`[实测]` 输入含 `\1c&\3c\4c` + `\t(0,1000,2.0,\1c…)` 的两行，输出：

```text
Dialogue: 5,0:00:00.00,0:00:02.00,SUB,,0000,0000,0000,,{\an5\pos(640.0,680.0)\1c&HFF0000&\3c&H00FF00&\4c&H000000&\t(1,1000,2.0\1c&H0000FF&\3c&HFFFFFF&)\t(2000,2000,\4c&H123456&)\t(2000,2500,\4c&HABCDEF&)}line onetail
```

**注意两点**：
- 生成的是 `\t(1,1000,2.0\1c…)`  **accel 与 `\1c` 之间没有逗号**（`utils.py:760-761`，`transform += "\\t(%d,%d," % (…); if acc!=1: transform += str(acc)`）。`[渲染]` 实测：这条写法下 libass 的 `cnt == 1` 分支把 `accel` 也吞成参数的一部分（`ass_parse.c:685-688`），**accel 实际不生效**（t=1.0s 时该写法 RGB=(241,181,182) 与"无 accel"完全相同，而正确写法的 `\t(0,2000,2.0,…)` 在 t=0.5s 时是 (241,181,182)、t=2.0s 才到 (241,2,2)）。
- `start_time/end_time` 被 `if == 0: = 1` 硬改过（`utils.py:756-757`），**落在 0ms 的跳变会被推后 1ms**。

### 4.4 关于 `\p b` 与 `\p bo`：**这两个写法都不存在，两个引擎里都无效**

任务里点名要确认这两个。结论给死：**不是"PyonFX 不支持"，是 ASS 本身没有这种语法**。

- 正确写法是 `\p<scale>` 与 `\pbo<value>` 两个**独立**标签：`{\p1\pbo50}m 0 0 l 200 0 …`。Aegisub 官方文档把它们列为两条（`\p<0/1/..>` Toggle drawing mode；`\pbo` Baseline offset）。
- libass 侧：`else if (tag("p")) { int32_t val = argtoi32(*args); val = (val<0)?0:val; state->drawing_scale = val; }`（`libass/libass/ass_parse.c:901-904`）。`tag()` 是纯前缀匹配、**不跳空格**（`ac_parse.c:68-78`），所以 `\p b` 里 tag 匹配到 `p`、参数文本是 `" b"`，`mystrtoi32` 解析整数失败 → **0 → 关闭绘图模式**。
- VSFilterMod 侧：tag 名切分是 `for(WCHAR c = str[++j]; c && c != '(' && c != '\\'; cmd += c, c = str[++j]); cmd.Trim();`（`src/subtitles/RTS.cpp:1876-1880`），所以 `\p bo` 得到 `cmd = "p bo"`，走 `else if(!cmd.Find(L"p")) params.Add(cmd.Mid(1)), cmd = cmd.Left(1);`（`RTS.cpp:2012`）→ 参数 `" bo"` → `wcstol(" bo")` = 0 → `m_nPolygon = 0`（`RTS.cpp:2837-2840`）→ **同样关闭绘图**。
- `[渲染]` 本机 libass 实测（1920×1080 黑底，`\pos(960,540)` 画 200×200 方块）：

```text
{\p1}m 0 0 l 200 0 l 200 200 l 0 200     → 非黑像素 40000, bbox=(860,440,1060,640)  ← 方块
{\p}m 0 0 l 200 0 l 200 200 l 0 200      → 非黑像素 33449, bbox=(170,497,1752,578)  ← 变成文字了
{\p b}m 0 0 l 200 0 l 200 200 l 0 200    → 非黑像素 33449, bbox=(170,497,1752,578)  ← 同样是文字
{\p4}m 0 0 l 200 0 l 200 200 l 0 200     → 非黑像素  676, bbox=(947,527,973,553)    ← 缩小 8 倍（2^(4-1)）
```

顺带把 `\pbo` 单独测干净（**纯 libass 行为，与 PyonFX 无关**）：

```text
\pbo0   → bbox=(860,440,1060,640)
\pbo50  → bbox=(860,440,1060,640)     ← 不生效
\pbo200 → bbox=(860,440,1060,640)     ← 不生效
\pbo-50 → bbox=(860,415,1060,615)     ← 上移 25px
\pbo-200→ bbox=(860,340,1060,540)     ← 上移 100px
```

libass 源码里 `pbo` 的用法是 `desc = 64 * info->drawing_pbo; asc = val->asc - desc; offset.y = -asc * scale.y;`（`libass/libass/ass_render.c:1188-1195`），所以**正值被竖直度量抵消，只有负值才是可见的 Y 偏移**。VSFilterMod 定义是"决定绘制时的基线偏移，偏移发生在 Y 方向"，语义不完全一致  想双引擎一致，**只用负值**。

### 4.5 `\kt` 的解析语义是错的（这是本报告发现的第一个真缺陷）

`libass/libass/ass_parse.c:837-844`：

```c
} else if (tag("kt")) {
    double val = 0;
    if (nargs) val = argtod(*args) * 10;
    state->effect_skip_timing = dtoi32(val);
    state->effect_timing = 0;
    state->reset_effect = true;
}
```

`\kt<time>` 是**绝对时刻**（从行首起算），且会把该时刻之后的卡拉OK计时**重置**。`\k/\kf/\ko/\K` 才是相对累加（`ass_parse.c:845-868` 里 `effect_skip_timing += effect_timing`）。

PyonFX 的解析器只用一个正则 `re.compile(r"\\[kK][fot]?(\d+)?")`（`ass_core.py:923`），必然匹配 `\kt20`，并把捕获的 `20` 当**时长**用：`duration = k_dur * 10`、`start_time = last_time`（累加）（`ass_core.py:1022-1033`）。

`[实测]` 同一份文件里 `{\kt20}あ{\kt100}い{\kt200}う`：

```text
syl 0 'あ' start=0    end=200   dur=200
syl 1 'い' start=200  end=1200  dur=1000     ← 应为 start≈1000（\kt100 是绝对 1000ms）
syl 2 'う' start=1200 end=3200  dur=2000
```

`[渲染]` 交叉验证：`\K/\k/\kf/\ko` 版在 0.1s/0.7s/1.5s 三个时刻分别有 0/1/2 个字点亮（正确）；`\kt` 版在 0.1→2.5s 全程 3 个字都没点亮（因为 `effect_timing` 恒为 0，libass 认为永远不到换色时刻）。**两个引擎对 `\kt` 的行为与 PyonFX 算出的时间轴完全对不上。**

**结论：用 `\kt` 的输入不要喂给 PyonFX 的 `line.syls` 做特效。**

### 4.6 覆盖率汇总（回答"哪些有专用方法 / 只能 raw / 根本不支持"）

| 类别 | 清单 |
|---|---|
| **有专用 API（但仅限颜色与颜色动画）** | `\1c` `\3c` `\4c` + `\t(t1,t2[,accel],\1c…\3c…\4c…)`  由 `ColorUtility` 生成 |
| **有几何/度量 API，输出需自己包标签** | 矢量 `\clip`（`Convert.text_to_clip`）、`\p` 绘图体（`Shape` / `Convert.text_to_shape`） **标签本身仍要手写** |
| **解析原生、写出需手写** | `\k` `\K` `\kf` `\ko`（正确）；`\kt`（**解析错误**） |
| **只能写 raw tag（库完全不碰）** | `\pos` `\move` `\org` `\frx/\fry/\frz` `\fscx/\fscy` `\fsp` `\fad` `\fade` `\iclip` `\blur` `\be` `\bord/\xbord/\ybord` `\shad/\xshad/\yshad` `\2c` `\1a-\4a` `\alpha` `\an` `\a` `\p` `\pbo` `\r` `\fn` `\fs` `\b/\i/\u/\s` `\q` |
| **根本不支持（透传也无用）** | `\p b` `\p bo`（ASS 无此语法，见 §4.4） |

---

## 5. VSFilterMod 扩展标签：**全部不支持，只能手写 raw tag；没有任何 patch 机制**

### 5.1 逐项结论

| 扩展标签 | PyonFX 能发吗 | 社区怎么绕 | 证据 |
|---|---|---|---|
| `\1img`~`\4img`（图片纹理） | **不能（无 API）；手写 raw 可透传** | raw tag 或改用像素方案 | 全仓 grep `1img\|2img\|3img\|4img` **0 命中**；`[实测]` 手写 `\1img(logo.png)` 逐字节落盘 |
| `\fsvp`（纵向偏移） | **不能；手写 raw** | raw tag | 全仓 0 命中 |
| `\distort`（扭曲） | **不能；手写 raw** | raw tag | 全仓 0 命中 |
| `\moves3` / `\moves4`（曲线移动） | **不能；手写 raw** | raw tag | 全仓 0 命中 |
| `\fsc`（整体缩放） | **不能；手写 raw** | raw tag | 全仓 0 命中；**注意双引擎语义不同**，见 §5.3 |
| `\pbo` | **不能；手写 raw** | raw tag | 全仓 0 命中 |
| `\rnd` / `\rndx` / `\rndy` / `\rndz` | **不能；手写 raw** | raw tag | 全仓 0 命中 |
| `\frs`（基线倾斜） | **不能；手写 raw** | raw tag | 全仓 0 命中 |
| `\kt` | **解析有、语义错**（§4.5）；写出靠 raw | raw tag（且时间轴要自己算） | `ass_core.py:923` |
| 其它 MOD 扩展 | 同上：`\jitter` `\mover` `\movevc` `\1va`~`\4va` `\1vc`~`\4vc` `\z` `\rnds` `\be` 图片变体 | raw tag | 全仓 0 命中 |

**这是一条硬事实：`grep -rn "1img\|fsvp\|distort\|moves3\|pbo\|rnd" pyonfx/` → 0 命中。** PyonFX 对 VSFilterMod 一无所知，它既不知道这些标签存在，也不会拦你写。

### 5.2 社区的实际做法：**就是 raw tag，没有别的**

我拉了三个真实社区仓 + 本机素材做统计：

- 30★ 合集 `kakashi1987/aegisub-lua-pyonfx-karaoke-fx-collection`（`pyonfx/discord-community/` 下 40+ 个 PyonFX 脚本）：`grep -rn "1img\|fsvp\|distort\|moves3\|pbo\|rndx" --include=*.py` → **0 命中**。
- 同仓 `TexT_Fill_With_Image.py`：要做"图片填充文字"，作者的解法是**逐像素**  `Convert.text_to_pixels(syl)` 遍历像素，从 PIL 读到的 numpy 图里取色，然后 `l.text = f"{{\\p1\\an7\\1c{color_bgr}\\move({x},{y},{x2},{y2}){alpha}}}{p_sh}"`，**一个像素一条事件**。这是绕开 `\1img` 的典型手法（代价是行数爆炸）。
- 本机 `~/下载/Seekladoom-ASS-Effect-master/PyonFX/` 三个成品（公主连结 OP / 雨滴 / text_to_pixels）：所有手写标签统计只有 `\an5 \pos \move \fad \blur \bord \shad \p1 \t \1c \1a \fs \frz \fscy \fscx`  **零个 MOD 标签**。

### 5.3 两个必须写进架构决策的引擎侧坑

**(a) `\fsc` 在两套引擎里语义相反。**
- libass（`ass_parse.c:454-456`）：`tag("fsc")` → `state->scale_x = state->style->ScaleX; state->scale_y = style->ScaleY;`  **数字参数被静默丢弃，只保留"重置"含义**。`[渲染]` 实测：`\fscx300` → 宽 631px；`\fscx300\fsc180` → 宽 **211px**（= 样式 100%，不是 180% 也不是 300%）；`\fscx300\fscx100` → 宽 211px。
- VSFilterMod：`\fsc<scale>` 等价于同时 `\fscx\fscy`。
- **对策：生成端一律展开成 `\fscx` + `\fscy` 两条。**

**(b) `\moves3` 在打击面板（Mod 分支）里被 `\move` 吃掉。** VSFilterMod 的 tag 名切分按**含空格**收集（`cmd.Trim()` 后才比较，`RTS.cpp:1876-1880`），`moves3` 是独立 cmd；但参数个数判据 `params.GetCount() == 4/6` 会让 6 参数的 `\moves3(x1,y1,x2,y2,x3,y3)` 命中 `\move` 分支。本机技能库 `hx-kfx/references/engine-compat.md` 记录过这一条（素材里 279 处 `\moves3` 参数个数 100% 为 6，因此从未按本意跑过），与我在 `RTS.cpp` 里读到的分支顺序一致。

**(c) `\1img` 在标准 libass 里渲染为空。** `[渲染]` 实测：`{\pos(960,540)\1img(logo.png)}AAA` 的非黑像素 = 5605，与纯 `AAA` 基线**完全相同** → 标签被忽略，只剩文字。

---

## 6. 模块化与自动注册：**完全没有插件机制，纯手工 import + 手工调用**

### 6.1 事实

`grep -rniE "register|plugin|entry_point|importlib|discover|autoload" pyonfx/*.py` → **0 命中**。

官方推荐的"项目组织方式"就是**普通 Python 模块拆分**，主文件显式 `import` 并逐个调用。示例 `examples/1 - Basics/4 - Organizing the code.py` 给出的骨架是：

```python
from pyonfx import *

io = Ass("in.ass")
meta, styles, lines = io.get_data()

def romaji(line, l):   # 你要自己写
    pass
def kanji(line, l):
    pass
def sub(line, l):
    pass

for line in lines:
    if line.styleref.alignment >= 7:
        romaji(line, line.copy())      # ← 手工调用，没有注册表
    elif line.styleref.alignment >= 4:
        kanji(line, line.copy())
    else:
        sub(line, line.copy())

io.save()
io.open_aegisub()
```

唯一的"机制"是 `@io.track`（`ass_core.py:1555`），它**只做计时统计**，不注册、不派发。

### 6.2 官方唯一的多文件示例：Dangos（3 文件）

`[代码]` `find "examples/4 - Community" -type f`：

```text
examples/4 - Community/1 - Dangos/
├── main.py          941 行   主文件
├── dango_config.py  117 行   形状 + 配色 + 变体表
└── in.ass                    输入
```

`dango_config.py` 是**纯数据模块**（`_DANGO_BODY` `_BASE_EYES` `_CUTE_EYES` … 一堆绘图串常量 + `_make_shape/_make_shapes/_make_config` 工具函数 + 导出 `RENDER_ORDER` / `VARIANT_LOOKUP` / `VARIANT_BASE_CONFIGS` / `DANGO_ALTERNATIVES`，见该文件头 8 行 docstring 的自我说明）。

`main.py` 的组装方式是**单向 import 数据、集中派发逻辑**：

```python
from dango_config import (DANGO_ALTERNATIVES, RENDER_ORDER,
                          VARIANT_BASE_CONFIGS, VARIANT_LOOKUP)
from pyonfx import *

io = Ass("in.ass")
meta, styles, lines = io.get_data()

class Dango:                       # 一个 dango = 一个状态机（shape/style/x/y/frz/fscx/fscy/alpha + 时间游标）
    def idle(...)                 # 动画 API，全部 self-return 以支持链式
    def move_to(...)
    def morph_from_shapes(...)    # @io.track
    def exit_jump_down_fall(...)  # @io.track
    def exit_furious_dash(...)    # @io.track
    def exit_slow_steps(...)
    def exit_heart_spiral(...)
    def piggyback_onto(...)
    def tug_away(...)

exit_effects = {                   # ← 所谓"注册"就是这个 dict
    "angry":  "exit_furious_dash",
    "cute":   "exit_heart_spiral",
    "grandpa":"exit_slow_steps",
    "granny": "exit_slow_steps",
}
...
exit_method = getattr(dango, exit_effects.get(dango.name, "exit_jump_down_fall"))
exit_method()
```

**要点：官方示例里"注册新的出场动画"分两步  在类里加方法 + 在 `exit_effects` 这个手写 dict 里加一行。没有装饰器自动注册。**

### 6.3 社区真实项目：三种规模，逐级演进

**(1) 2 文件最小项目**  `naru19/skrip-karafx-pyonfx`（每部动画一个目录，`xxx.ass` + 同名 `kfx-xxx.py`）：

```text
Idoly Pride/Opening/
├── idoly-pride-op.ass      7.0 KB   带 \kf 的输入
└── idoly-pride-op.py       7.8 KB   主脚本
Isekai Yakkyoku/Ending/
├── EDyakyou.ass            5.0 KB
└── kfx-ed-iy.py            4.6 KB
```

**(2) 4 文件项目**  `Clip-sub/pyonfx-scripts`：只有 `doraeiga-2022-ed-universe.py` 一个脚本 + README + LICENSE。说明**社区绝大多数项目根本不拆文件**，单文件 5k–80k 字节。

**(3) 官方之外的"真的工程化"样板**  `bamboo-111/pyonfx-example`（1★，2026-04 建，2026-07 最后推）的 `redline` 效果，这是我在生态里找到的唯一有分层架构的项目：

```text
effects/redline/
├── redline.py                     80.8 KB   渲染管线 + CLI 入口
├── README.md                       5.8 KB
├── butterfly/output/butterfly.10frames.0.2s.ass
└── word/
    ├── word_fx_adapter.py          4.4 KB   桥接层（推荐 redline.py 只 import 这个）
    ├── stroke_word_test.py         0.6 KB   测试夹具
    └── stroke_fx/                           可复用包
        ├── __init__.py     api.py        config.py     models.py
        ├── assets.py       input.py      render.py     timing.py
        ├── diagnostics.py  integration.py utils.py
        └── INTEGRATION.md
effects/spike/
├── spike.py                       69.8 KB
├── spike_inverse.py               58.8 KB
├── README.md / MODIFICATIONS.md
```

它的 `INTEGRATION.md` 明确写了**手工组装契约**（`bamboo-111/pyonfx-example/effects/redline/word/stroke_fx/INTEGRATION.md`）：

```text
1. Build one session per render pass.
2. Warm assets for the target lines before event emission.
3. For each target line, call session.render_line(io, line, line_index, options=...).
4. Keep test harness and diagnostics in word/, not in redline.py.
5. If you want a thinner bridge, use word/word_fx_adapter.py instead of importing low-level modules directly.

Minimal adapter example:
    from word.word_fx_adapter import create_word_fx_bridge, select_word_fx_target_lines
    bridge = create_word_fx_bridge()
    target_lines = select_word_fx_target_lines(lines)
    debug_rows = bridge.render_target_lines(io, target_lines)
```

**这是生态里对"多人协作大项目怎么组织 PyonFX"最成熟的一份答案**，且它是 2026 年的新代码  说明这个结论不是历史遗留，而是当前共识：**框架不提供机制，你自己造约定。**

### 6.4 决策含义

如果我们的 KFX 工程要复用 PyonFX：**effect 分发、变体选择、参数配置全部得自己写**。可选的自建形态与官方 Dangos 同构：`effects/<name>/` 一个目录，`config.py`（纯数据）+ `fx.py`（effect 函数）+ `run.py`（派发循环），用一个 dict 做"注册表"。

---

## 7. 批量化与复用：**没有工厂、没有配置驱动，全部靠 Python 循环 + 你自己写的函数签名**

### 7.1 PyonFX 提供的原语（只有三个）

**(a) 行级循环**  主文件末尾 invariably 是：

```python
for line in lines:
    if line.styleref.alignment >= 7:      # 用对齐值区分 romaji / 汉字 / 译文
        romaji(line, line.copy())
    elif line.styleref.alignment >= 4:
        kanji(line, line.copy())
    else:
        sub(line, line.copy())
```

**(b) 音节级循环**  `Utils.all_non_empty(line.syls)`（`utils.py:84`）。它做三件事：过滤空白/零时长、**重编号 `i`/`word_i`/`syl_i`**、包一层进度条。`[实测]` 进度条会往 stderr 打 `🎤 Processed syllables`。

**(c) 变体选择 = 读输入文件里的自带字段**。PyonFX 从输入行里抽两个"变体通道"（`ass_core.py:1004`）：

```python
inline_fx = re.search(r"\\-([^\s\\}]+)", tags)        # {\k50\-m1}あ  → inline_fx = "m1"
```

外加 `line.actor`（Name 列）和 `line.effect`（Effect 列）。官方 `examples/2 - Beginner/3 - Variants.py` 的 docstring 把这三条列为标准做法：

```text
"Inline effects is a method to define exclusive effects for syllables.
 Fields 'Actor' and 'Effect' can also be used to define exclusive effects,
 but you will define them for the whole line."
```

`[实测]` `{\k50\-m1}あ{\k50\-m2}い` → `syl 0 inline_fx='m1'`、`syl 1 inline_fx='m2'`（原样保留，注意 `tags` 里连 `\-m1` 一起存着）。

**(d) 颜色批量**：`ColorUtility(lines)` 一次性扫全部行，把散在各处的 `\1c\3c\4c\t` 抽成时间线，之后每生成一条事件调 `CU.get_color_change(l)` 取插值结果  这是唯一"配置驱动"的东西。

### 7.2 真实项目的批量做法（本机解压的两个成品）

`~/下载/…/PyonFX/【PyonFX 特效】公主连结_OP/公主连结_OP.py`（144 行） 用 `line.actor` 当变体开关：

```python
def Princess_OPJP(line, l):
    if line.actor == "phase 1":
        shape = ("m 0 0 l 2 0 l 2 50 l 0 50 l 0 0",
                 "m 100 0 b 100 -55 55 -100 0 -100 b …",   # 三个形状存成 tuple，用下标取
                 "m -5 0 l -5 0 l 5 0 l 5 22 l -5 22")
        for j in range(3):                       # 循环批量喷圆点
            l.layer = 1
            l.start_time = _lstart + _sstart + (-j-1)*100
            l.end_time   = _lstart + _send + 1000
            l.text = "{\\an5\\move(…)…\\p%.f}%s" % (…, shape[1])
            io.write_line(l)
    if line.actor == "phase 2":
        eye_color = ["00AF50","E1E100","AF69E1"]     # 变体 = 数组下标取模
        …
        l.text = "{\\an5\\pos(…)…\\3c&H%s&…}" % (eye_color[_si%3])

for line in lines:
    _lstart, _lend = line.start_time, line.end_time
    for syl in line.syls:
        _center, _middle, _text = syl.center, syl.middle, syl.text   # 把变量抬成全局，减少缩进
        if line.styleref.alignment == 8:
            Princess_OPJP(line, line.copy())
```

`【PyonFX：雨滴特效】…/for_loop_time_rain.py`（47 行） 用 `temp` dict 做"临时变量表"：

```python
temp = {}
def set_temp(ref, val):
    temp[ref] = val
    return val
…
l.start_time = _lstart + set_temp("雨水生成时间", l.dur/(len(line.syls)+1)*randint(1,len(line.syls)+1)/10 + j*雨水下落时间)
```

作者自己在注释里写明了 PyonFX 的缺口：

```python
#20220418：PyonFX缺乏类似Aegisub的syln这样的功能，导致当前行无法直接使用类似的功能
#生成相应的随机数（syl.word_i计算的是当前词的音节序数，不是总音节数。）
#解决方法：syln在PyonFX中用 len(line.syls) 实现
```

### 7.3 批量的三个真实代价

**(a) 行数爆炸**：每个"逐帧"或"逐像素"效果都是**一条事件一行 Dialogue**。社区 `TexT_Fill_With_Image.py` 是**每像素一条**。

**(b) `Line.copy()` 是全库最贵的操作**。它是 `copy.deepcopy`（`ass_core.py:496-501`），而 `Line` 里挂了 `words[] / syls[] / chars[]` 三个对象数组。`[实测]` 20000 条事件（每条 copy 一次 + write_line）耗时 **1.59 s = 12575 行/s**，输出 1.9 MB，单进程纯 Python。

**(c) 单脚本无法并行**：PyonFX 没有批处理 API，`Ass` 对象内是单一 `_output` list，没有分片机制。

### 7.4 有一个民间 fork 正面解决了批量/性能

`bamboo-111/PyonFX`（fork，2026-07-10 推了两个 PR 到上游但**被关闭**：#71 `[codex] Optimize PyonFX core workflows`、#72 `Codex/contributing compliance`，均 CLOSED）。它的 `benchmarks/optimization-decisions.md` 给了可复用的数字：

| 改动 | 效果 |
|---|---|
| 新增 `Event` / `write_event` / `write_events`（绕过 `Line.deepcopy` 写输出） | 100 条事件 58.90 ms → **0.208 ms（282.9×）**；tracemalloc 峰值 170.7 KB → 41.9 KB，**输出逐字节等价** |
| 新增 `save_events()` 批量流式写 | 100k 事件 1019 ms → 1042 ms（+2.3%），但 tracemalloc 峰值 13.69 MB → **0.70 MB（-94.9%）**、工作集峰值 -20% |
| `extended_features` 选择性解析 | 相对全量 7.15 ms：仅行 2.10 ms(-70.7%)、含词 2.77 ms(-61.3%)、含音节 3.94 ms(-44.9%) |
| 绘图→MultiPolygon LRU 缓存（128 条） | 温热场景 **-94.4% ~ -95.0%**；代价 +2.59 MB 工作集 |
| 被否决：Font 实例复用 / 单字宽度缓存 / 全局字形缓存 / 新数字格式化器 | 均为实测更慢或收益不可靠 |

**⚠️ 这些 API 上游 `master` 里都没有**（`grep -n "extended_features\|class Event\|write_event\|save_events" pyonfx/*.py` → 0 命中）。要用就得 fork。

---

## 8. 可读性与局限

### 8.1 官方自陈（README / 贡献指南 / issue）

- **状态是 beta**：`pyproject.toml` classifier `Development Status :: 4 - Beta`；CONTRIBUTING 里明文「`0` stands for "beta stage" and `1` for "release stage"」→ **0.x 系列永远是 beta，作者从未发过 1.0**（`v1.0.0` 这个 tag 实际指向文档站提交 `bbc49ac`，不是库版本）。
- **"需要先懂 ASS 和 Python"**：quick start 第一段就要求使用者「必须已经熟悉 Libass 支持的标签及其行为」，PyonFX 只教你 Python 变量/函数/循环/格式化/列表/字典。
- **文档过时**（issue #68，2025-07-18，OPEN）：「PyonFX documentation is starting to be a bit dated: inconsistent docstrings, poor explanations and lack of examples are an obstacle for new users.」计划换 ruff + MkDocs + Diátaxis  **MkDocs 站已上线（2025-08-31），docstring 一致性未完成**。
- **示例永远不够**（issue #9，2020-02-01，至今 OPEN）。
- **性能自陈**（issue #29，2021-04-10，至今 OPEN）：「a lot of PyonFX's code use LBYL approach… a lot of type checking is done and **slow down the whole process**」，主张改 EAFP。**5 年未动。**
- **Shape 会就地改自己**（issue #69，2025-07-20，OPEN）：帧循环里想每帧从原始形状重新变换时，必须手动 `Shape(other.drawing_cmds)` 复制（**连 `copy()` 都没有**），作者明确否决了加 `in_place` flag。
- **没有粒子系统 / 没有音频解码 / 没有 OKLab**（#67 / #8 / #66，全 OPEN）。音频解码从 2020-02-01 挂到现在。

### 8.2 使用者抱怨过的具体场景（issue 实例）

| issue | 症状 | 性质 |
|---|---|---|
| #39（2022-03-07） | `ValueError: Unexpected section in the input file: [V4 Styles]` | **旧版 SSA（V4，非 V4+）直接解析失败** |
| #41（2022-03-07） | 「line.syls is empty」 | 输入不是 PyonFX 认的 `\k` 格式时静默给空音节表 |
| #40（2022-03-07） | 「append new line to file does not work」 | `write_line` 语义被误解 |
| #52（2025-05-18） | `syl.center` 位置不对（附截图 + 复现包） | **宽度/位置度量与渲染器不一致**；维护者查看后归因为 libass 已知问题 |
| #53（2025-05-18） | `Convert.text_to_pixels` 忽略 style 的 spacing | 度量保真度 |
| #31（2021-05-29） | `an 4/5/6` 时 `line.left/right/top/bottom` 边界错 | 竖排边界 |
| #45（2022-04-19） | 用户想用 `_lstart/_sstart/_sdur/_si` 这类缩写变量减少代码长度 | 作者回复「**不建议**这么缩写，会让代码更难读更易错；重复代码请包成参数化函数」 |

### 8.3 本机实测的两条硬限制

**(a) 文本度量与渲染器有系统性偏差。**
样式 `Noto Sans / 60px / spacing 0`、`PlayResX 1280`、5 个全角假名，PyonFX 度量 vs libass 实测：

```text
PyonFX  get_text_extents("あいうえお") = 220.226 × 44.045
        line.left/right              = 529.887 / 750.113
libass  实测整行 bbox                = (498, 12, 787, 67)  宽 289  高 55
        左边界差 -31.89px，右边界差 +36.89px
```

换 `DejaVu Sans`（PyonFX 那侧度量变成 227.264）后**libass 侧数字完全不变**（还是 498/787） 说明偏差主要来自**字体解析路径不同**（Linux 走 PangoCairo，`font.py:99-127`），而不是字体本身。官方 quick start 为此专门写了一条：

> "If you experience output not rendered correctly, you might need to change the PangoCairo backend to fontconfig: `PANGOCAIRO_BACKEND=fc python3 namefile.py`"

在 Windows 上走 GDI 分支，度量同样与 libass 不同源。**结论：`line.center/left/top` 只能当"近似初值"，像素级对齐必须自己渲染回测**（这正好对上我们现有 KFX 链路里"渲染回看 + 门禁"的做法）。

**(b) 输入格式校验是"严进"的，且失败模式不友好。**
`[实测]`：

```text
输入无 [Script Info]                       → 静默通过（输出头直接是 [V4+ Styles]）
输入用 [V4 Styles]（旧 SSA）                → ValueError: Unexpected section in the input file: [V4 Styles]
输入含任意未知 section（如 [Custom]）        → ValueError: Unexpected section in the input file: [Custom]
Dialogue 引用了不存在的 Style               → ValueError: Unknown style 'A' at line 0
路径不存在                                  → FileNotFoundError: Invalid path for the Subtitle file: …
```

`[代码]` `ass_core.py:717-722`：

```python
elif current_section and line.strip():   # Non-empty line in unknown section
    raise ValueError(f"Unexpected section in the input file: [{current_section}]")
```

**任何带自定义 section 的 ASS（某些工具会写私有段）都会直接炸。**

**(c) 关于 `extended=False`**：`[实测]` 同一份文件 `extended=False` 时 `lines` 长度从 2 变回 1（**`\N` 不再拆行**）、`chars=[]`、`syls=[]`、`width=nan`  即**放弃全部测量，只剩纯文本搬运**。这是唯一的"性能模式"档位。

### 8.4 它不适合的场景（明确结论）

1. **需要 VSFilterMod 扩展标签的项目**  库零支持，且这些标签在标准 libass 上无效，验收环境会被锁死。
2. **需要像素级/帧级精确对位的项目**  度量与渲染器不同源，必须自己回测收敛。
3. **超大文件/超长素材**  每事件一个 `Line` 对象 + `deepcopy` 一次；没有任何流式/分片写入（除非用民间 fork）。
4. **多人协作但没有自建约定的大项目**  框架不提供 effect 注册、目录约定、参数校验，全部靠团队自律（社区现状就是单文件 5k–80k 字节）。
5. **输入是旧 SSA(V4) 或含自定义 section 的 ASS**  直接抛异常。
6. **依赖 `\kt` 绝对时间轴的输入**  解析语义错误。

---

## 9. 对比 Aegisub 的 karaskel / Lua 自动化

### 9.1 定位差异

| | karaskel + Kara-Templater（Lua，Aegisub 内嵌） | PyonFX（Python，独立进程） |
|---|---|---|
| 运行环境 | **Aegisub 内部**，`aegisub.text_extents` 调的是 Aegisub 自己的字体引擎  **与 Aegisub 预览所见即所得** | 独立 Python 进程 + 自建字体栈（Windows GDI / Linux PangoCairo） **与 Aegisub 有系统性偏差**（§8.3a） |
| 输入/输出 | 直接在 Aegisub 的 subtitle 对象上改，可 undo | 读 .ass → 写 .ass，不可交互 |
| 语言能力 | Lua 5.1/5.2（无 numpy/scipy/PIL/包生态） | **Python3 全家桶**：numpy、scipy、shapely（布尔运算/几何）、Pillow（图像）、pyquaternion |
| 几何运算 | 无。只有 `utils.text_extents` + 手工算 | `Shape` 2131 行：`boolean`（依赖 shapely）、`morph`/`morph_multi`、`buffer`、`flatten`、`split`、`bounding(exact)` |
| 逐像素 | 不可能 | `Convert.text_to_pixels` / `shape_to_pixels` / `image_to_pixels` + `PixelCollection` |
| 视频帧率感知 | 无 | `FrameUtility(start, end, meta.timestamps, n_fr)`，用 `VideoTimestamps` 支持 CFR **和 VFR**，中点对齐避免闪烁（`utils.py:337-443`） |
| 缓动 | `retime` 只处理时间；无缓动数学 | `Utils.accelerate` 走 Penner 全套（rpeasings） |
| 预览 | Aegisub 实时预览 | `open_mpv()` + 热重载（`ass_core.py:1448+`） |
| 分发 | 把 .lua 丢进 Aegisub autoload | `pip install pyonfx` |
| 依赖 | 零（Aegisub 自带） | numpy/scipy/shapely/Pillow/tqdm/tabulate + 平台字体栈（Linux 要装 cairo/gobject/gtk3） |

### 9.2 API 面逐项对照

**karaskel 提供**（`Aegisub/Aegisub:automation/include/karaskel-auto4.lua`，690 行）：

```lua
karaskel.collect_head(subs, generate_furigana)   -- 收集 meta/styles
karaskel.preproc_line_text(meta, styles, line)   -- 拆 text/syl/furi
karaskel.preproc_line_size(meta, styles, line)   -- 度量：line.width/height/descent/extlead
karaskel.preproc_line_pos(meta, styles, line)    -- 定位：line.left/center/right/top/middle/bottom/x/y
karaskel.preproc_line(subs, meta, styles, line)  -- 上面三步的门面
karaskel.use_fx_library(macrotoo)                -- 注册 fx_ 库宏（Effect 字段派发）
karaskel.use_classic_adv(use_furigana, macrotoo) -- 经典 adv 宏
```

`preproc_line_pos` 的定位实现与 PyonFX **几乎逐行同构**（`karaskel-auto4.lua:329-362` vs `ass_core.py:781-816`）：

```lua
-- karaskel: align 左/中/右
line.left = line.eff_margin_l
line.center = line.left + line.width / 2          -- PyonFX: line.center = line.left + line.width/2
line.x = line.left                                 -- PyonFX: line.x = (left, center, right)[h_group]
```

**唯一的实现级差异**：`karaskel` 用 `aegisub.text_extents(...)`（引擎内），PyonFX 用自建 `Font`。

**Kara-Templater 有而 PyonFX 完全没有的东西**（`automation/autoload/kara-templater.lua`，861 行）：

**(a) `retime` 的 10 个时间轴模式**（`kara-templater.lua:305-341`）：

```lua
syl | presyl | postsyl | line | preline | postline
| start2syl | syl2end | set/abs | sylpct
```

**(b) 模板语言 + 环境变量**：`template syl`, `template line`, `template char`, `fxgroup`、`relayer`、`restyle`、`syln`、`j`/`jmax`、`$syl`/`$line` 变量族  在**字幕文件里**写模板，Aegisub 一键应用。PyonFX 对应物是**手写 Python 函数**。

**(c) 帧循环靠逐帧复制事件**：Kara-Templater 的 `retime` 只改时间，逐帧动画仍要自己循环；PyonFX 用 `FrameUtility` 把这件事标准化了。

**PyonFX 有而 karaskel + Kara-Templater 完全没有**：`Shape`（布尔/morph/buffer）、像素、`ColorUtility` 颜色时间线抽取、`interpolate`/`accelerate` 数学、VFR 帧、mpv 热重载、Python 生态。

### 9.3 分工结论

**两者不是替代关系，各自锁死了对方的短板。**

| 场景 | 该用谁 | 原因 |
|---|---|---|
| 要所见即所得、要 Aegisub 内即时调参 | **karaskel + Kara-Templater** | 度量同源，改完立刻看 |
| 要形状布尔运算 / morph 补间 / 逐像素 / 图像处理 | **PyonFX** | Lua 侧不存在这些能力 |
| 要把特效接进 CI/自动出片/批量跑 | **PyonFX**（或 Aegisub 的 `aegisub-cli` + 模板） | 独立进程、可脚本化 |
| 需要像素级对位 | **karaskel**（同源度量）或 **PyonFX + 渲染回测闭环** | PyonFX 单靠自身算不准 |
| 逐字时间轴要对（`\k` 系列，含 `\kt`） | **karaskel** | PyonFX 的 `\kt` 解析错误 |

**我们这条链路（§现有 KFX-PIPELINE.md 第 6 步用 `kara-templater.lua` + `aegisub-cli`）恰好落在 karaskel 的优势区（时间轴与同源度量）。引入 PyonFX 的收益集中在形状/像素/几何这一侧，而这正是当前链路最缺的（`hx-kfx` 技能库里"粒子沿轨迹飞要靠逐点打印"这类限制就是几何能力不足的症状）。**

---

## 10. 一页结论（决策用）

1. **能力边界**：PyonFX = 「ASS 解析 + 文本度量/定位 + 几何 + 颜色工具 + 帧与像素迭代」，**不是标签抽象层**。标签正确性 100% 由使用者负责。
2. **标签覆盖**：原生 API 只覆盖 `\1c \3c \4c` 与颜色类 `\t`（且 accel 输出有缺失逗号的 bug）。`\pos \move \fscx/\fscy \blur \bord \shad \k` 等**全部需要手写**。`\p b` / `\p bo` 这两个写法在 ASS 里根本不存在，两个引擎都判为"关闭绘图"。
3. **VSFilterMod**：**零支持、零拦截、零 patch 机制**，只能 raw tag 透传；社区绕法就是裸写标签（或改用逐像素方案）。而标准 libass 对这些标签一律忽略，验收环境必须锁定 Mod 分支。
4. **扩展性**：无插件/注册机制，官方示范是「`config.py` 数据 + 主文件 dict 派发」。要工程化就得自己定约定（参考 `bamboo-111/pyonfx-example` 的 `INTEGRATION.md`）。
5. **两个必须先解决的工程风险**：① 度量与渲染器不同源（实测行宽差 ~30px），**任何像素级对位必须自带渲染回测**；② `Line.copy()` 是 `deepcopy`，20k 事件/1.6 s  大批量要自建轻量写入或采纳民间 fork 的 `Event`/`save_events`。
6. **维护风险**：2025-07-19 后零提交、8 个开放 issue 里含 2020 年的音频解码与 2021 年的性能重构、版本永远是 0.x beta。**可以依赖，但不要指望它替你补功能**；需要的东西（性能、扩展标签、`\kt`）得自己在 fork 或包装层解决。

---

### 复现材料

- 上游源码（= master = v0.11.0）：`/tmp/pyonfx_evidence/repo/`
- 隔离环境：`/tmp/pfxvenv`（`pyonfx==0.11.0`，Python 3.14.7）
- 本报告所有渲染实验脚本与产物：`/tmp/pfx_test/`（PyonFX 侧）、`/tmp/rtest/`（纯 ASS + libass 侧）
- VSFilterMod 官方中文文档（本机）：`/tmp/vsfm.txt`（源自 `~/下载/Seekladoom-ASS-Effect-master/其他/ASS特效标签合集（常规+MOD）+手册+相关插件/`）

### 来源清单

- https://github.com/CoffeeStraw/PyonFX · https://pyonfx.rtfd.io/ · https://coffeestraw.github.io/PyonFX/
- https://pypi.org/pypi/pyonfx/json
- https://github.com/CoffeeStraw/PyonFX/issues/{8,9,29,31,39,40,41,45,52,53,66,67,68,69,70} · pull/{71,72}
- https://github.com/libass/libass/blob/master/libass/ass_parse.c · ass_render.c
- https://github.com/sorayuki/VSFilterMod/blob/master/src/subtitles/RTS.cpp
- https://aegisub.org/docs/latest/ass_tags/
- https://github.com/Aegisub/Aegisub/blob/master/automation/include/karaskel-auto4.lua · automation/autoload/kara-templater.lua
- https://github.com/kakashi1987/aegisub-lua-pyonfx-karaoke-fx-collection · naru19/skrip-karafx-pyonfx · Clip-sub/pyonfx-scripts · bamboo-111/pyonfx-example（含 fork 的 `benchmarks/optimization-decisions.md`）
