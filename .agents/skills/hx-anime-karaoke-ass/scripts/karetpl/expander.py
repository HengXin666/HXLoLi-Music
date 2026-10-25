# -*- coding: utf-8 -*-
"""Expander  执行 Program，产出 Event。

职责边界（见 CONTRACT.md）：
  做：执行 code 行、按修饰符决定展开单元、拼模板求值环境、算时间窗、替换 `!expr!`
  不做：选图形、选配色、决定何时爆发  那些写在**被执行的程序**里

三条硬约束：
  1. 不猜不静默：任何求值失败都进 `warnings`，不伪造成功
  2. 单位只在一处转：毫秒<->秒的换算集中在 directives 与本文件的 `_env` 里
  3. 层数由 Lua 函数决定，不用 len() 猜（`meteor={128×13}` 是 1664 层，不是 13）
"""
import re

from karetpl import directives
from karetpl.evaluator import Evaluator, tostring
from karetpl.metrics import Metrics
from karetpl.model import Event, Program, SourceLine

# 修饰符：决定"一个模板跑几次"
_SYLLABIC = ("syl", "furi", "char")
_NUMBER_TAGS = re.compile(r"\\(pos|move|org)\(([-\d.,]+)\)")
# `\t(a,b,<tags>)` 的前两个时间参数取整；其后的数值项去浮点噪声（-238.80000000000007 -> -238.8）
_TIME_TAGS = re.compile(r"\\t\(([^)]*)\)")


class Expander:
    def __init__(self, program: Program, metrics=None, seed=None, builtins=None):
        self.prog = program
        self.metrics = metrics or Metrics()
        self._rng = __import__("random").Random(seed) if seed is not None else None
        self.ev = Evaluator(rng=self._rng)
        self.warnings = self.ev.warnings
        self._register(builtins or {})
        self._run_once()

    # ---------------------------------------------------------------- 宿主接口
    def _register(self, builtins):
        """注册宿主函数。

        内置两个：贝塞尔等速采样（原程序用它把曲线采样成粒子串）与 Aegisub 的帧时间。
        **用户可以覆盖任意一个**  传 builtins={"bezier_n_uniform_speed": my_impl} 即可。
        """
        from karetpl.bezier import bezier_n_uniform_speed
        self.ev.define("bezier_n_uniform_speed", bezier_n_uniform_speed)
        self.ev.define("aegisub", _Aegisub(33))
        # Aegisub 的 ass_alpha：0..255 的 **alpha 值** -> `&HXX&` 字符串。
        # 原程序的 frame_fad() 靠它产出逐帧淡入淡出（缺失会让 `\alpha` 变空标签）。
        self.ev.define("ass_alpha", lambda a: "&H%02X&" % max(0, min(255, int(round(a)))))
        for name, fn in builtins.items():
            self.ev.define(name, fn)

    _frame_ms = None

    def _run_once(self):
        """执行 `code once`：定义函数、常量。按出现顺序，失败只记录不中断。"""
        for c in self.prog.code:
            if c.when == "once":
                try:
                    self.ev.run(c.text)
                except Exception as ex:
                    self.warnings.append(f"code once 失败 ({type(ex).__name__}): {c.text[:40]}")

    # ---------------------------------------------------------------- 对外
    def expand(self) -> list:
        out, prev = [], None
        for i, ln in enumerate(self.prog.karaoke):
            evs = self.expand_line(ln, prev)
            for e in evs:
                e.source_line = i
            out += evs
            prev = ln
        return out

    def expand_line(self, line: SourceLine, prev: SourceLine | None = None) -> list:
        self._layout(line)
        env = self._env(line, prev)
        out = []
        for tpl in self.prog.templates_for(line):
            out += self._expand_template(tpl, line, env)
        return out

    # ---------------------------------------------------------------- 行几何
    def _layout(self, line: SourceLine):
        st = self.prog.styles.get(line.style)
        if st is None:
            self.warnings.append(f"样式缺失: {line.style}")
            return
        box = self.metrics.line_box(line.surface, st, self.prog.res_x, self.prog.res_y)
        line.left, line.width, line.middle = box["left"], box["width"], box["middle"]
        line.bottom, line.height = box["bottom"], box["height"]
        box2 = self.metrics.center_advance_of(st.size, st.spacing)
        acc = 0.0
        for s in line.syllables:
            s.left = line.left + acc
            s.width = self.metrics.width(s.surface, st.size, st.spacing)
            # $scenter 用**字体真实 advance**：与 line.width 是不同基准（实测 75.14 vs 75）
            s.center = line.left + box2 * (s.index - 1) + box2 / 2
            acc += s.width

    def _env(self, line: SourceLine, prev: SourceLine | None) -> dict:
        st = self.prog.styles.get(line.style)
        size = st.size if st else 20.0
        return {
            # 秒（供 Python 侧用）
            "lstart_s": line.start, "lend_s": line.end,
            # 毫秒（Aegisub 的 $lstart/$lend 是这个单位，模板里写 $lstart+$sstart-500）
            "lstart": line.start * 1000, "lend": line.end * 1000,
            # `ldur` 分两阶段（实测）：
            #   阶段1 算 maxloop/multiloop 时 -> **源句时长**：`maxloop(ceil((ldur+500)/ms))`
            #         得 60 层（原版 9 音节 × 60 = 540，用 +600 会得 702）
            #   阶段2 求值正文时 -> **本模板 retime 后的窗口**：`\t(0,1990)` / `\t(0,500)`
            # 阶段2 的值在 _emit 里按 t0/t1 回填。
            "ldur": line.dur * 1000,
            "lleft": line.left, "lwidth": line.width, "lright": line.left + line.width,
            "lcenter": line.left + line.width / 2,
            "lmiddle": line.middle, "lbottom": line.bottom,
            "ltop": line.bottom - size, "lheight": size,
            "actor": line.actor,
            "prev_lstart": (prev.start if prev else line.start) * 1000,
            "prev_lend": (prev.end if prev else line.end) * 1000,
        }

    # ---------------------------------------------------------------- 模板展开
    def _expand_template(self, tpl, line: SourceLine, env: dict) -> list:
        mods = tpl.modifiers
        per_syllable = any(m in mods for m in _SYLLABIC) and "firstsyl" not in mods
        pool = self._pool(tpl, line)

        # `code line` 先跑：meteor / star / Rabbit 这些**表**在这里构造，而
        # `multiloop(meteor)` 的层数就是它们决定的（实测 1664 层 vs 13 层）。
        # 它必须在算循环之前执行，且只执行一次（与音节、与第几次循环都无关）。
        line_state = self._run_code(tpl, line, line.syllables[0], phase="line")
        env = dict(env)
        env.update(line_state)

        out = []
        for syl in (pool if per_syllable else line.syllables[:1]):
            # `code syl` 会把 RR_pos / RS_pos 这些**逐音节**的量写进作用域，
            # 而 `maxloop(#RR_pos)` 的层数依赖它  所以循环必须在音节状态之后算，
            # 且每个音节各算一次（用第一个音节的层数会让 28 层退化成 1 层）。
            env2 = dict(env)
            env2.update(self._run_code(tpl, line, syl, phase="syl"))
            for loop in directives.loops(tpl, env2, self.ev):
                out.append(self._emit(tpl, line, syl, env2, {}, loop))
        return [e for e in out if e is not None]

    def _pool(self, tpl, line):
        """决定展开单元。

        三道筛选，顺序与 kara-templater 一致：
          1. `fx CA`/`fx CB` 选择器 -> 只留 inline_fx 匹配的音节
          2. `furi` -> 只留带注音的音节；`char` -> 逐字；其余 -> 逐音节
        """
        mods = tpl.modifiers
        pool = line.syllables
        if tpl.fx:
            pool = [s for s in pool if s.inline_fx == tpl.fx]
        if not pool:
            return []
        if "furi" in mods:
            return [s for s in pool if s.ruby] or pool[:1]
        if "char" in mods:
            chars = []
            for s in pool:
                for i, ch in enumerate(s.surface):
                    chars.append(_CharSyl(s, ch, i, len(s.surface)))
            return chars
        return pool

    def _run_code(self, tpl, line: SourceLine, syl, phase="syl"):
        """执行 `code syl` 或 `code line`，返回它们设的变量。

        phase="line" 时只跑 `code line`（构造 meteor/star 等行级表）；
        phase="syl" 时只跑 `code syl` / `code syl all`（算 c/cp/RR_pos 等音节级量）。
        """
        sc = self.ev.scope()
        sc.declare("syl", _lua_syl(syl))
        sc.declare("line", _lua_line(line, self.prog, self.metrics))
        sc.declare("orgline", _lua_orgline(line))
        sc.declare("fxgroup", _lua_fxgroup())
        want = ("line",) if phase == "line" else ("syl", "char", "furi")
        for c in self.prog.code:
            if c.when not in want:
                continue
            try:
                self.ev.interp.run(c.text, sc, None)
            except Exception as ex:
                self.warnings.append(f"code {c.when} 失败 ({type(ex).__name__}): {c.text[:40]}")
        keys = (("line", "meteor", "star", "star_color", "pos", "Rabbit", "stars", "ms")
                if phase == "line" else
                ("c", "cp", "ci", "cn", "RR_pos", "RS_pos", "syl", "line", "fxgroup"))
        return {k: sc.get(k) for k in keys if sc.has(k)}

    def _emit(self, tpl, line: SourceLine, syl, env: dict, state: dict, loop):
        e = dict(env)
        e.update(state)
        e.update(loop.as_env())
        e = _syllable_env(e, line, syl, self.prog, self.metrics)

        # 顺序要紧：**先算 retime 窗口，再求值正文**。
        # `!line.duration!` 是**本事件的窗口长度**（JP_FX_A 的 1990 = 行 1390 + 600、
        # JP_FX_C 的 500 = presyl 的窗口），不是源句时长  先求值会拿到错的值。
        t0, t1 = directives.window(tpl, e, self.ev)
        e["ldur"] = (t1 - t0) * 1000
        # `line` 对象在音节/循环间共享，必须**复制后回填**，否则上一层污染的
        # duration 会传给下一层（实测 JP_FX_A 从 23 条掉到 12 条）。
        from karetpl.lua import LuaTable
        base_line = e.get("line")
        if isinstance(base_line, dict):
            base_line = LuaTable(base_line)
            base_line["duration"] = e["ldur"]
            base_line["end_time"] = t1
            e["line"] = base_line

        # 删指令再替换：指令里也有 `!...!`，先替换会把 `!retime(...)!` 与正文连成一个表达式
        text = self.ev.substitute(directives.strip(tpl.text), e)
        text = _round_coords(text)
        # 追加字面。三条例外：
        #   1. `notext` 修饰符
        #   2. 正文进入绘图模式（`\pN` N>0） 绘图事件不该再挂文本
        #      （原版 `}m` + `\p1`，追加会变成 `}見m`）
        #   3. `furi` 用注音而不是字面
        # 结论（实测）：**绘图模式也照样追加字面**  原版的绘图事件末尾确实带着
        # 音节字（`...23 -9見`）。所以只有 `notext` 才跳过。
        if "furi" in tpl.modifiers:
            if not text.endswith(syl.ruby or ""):
                text += syl.ruby or ""
        elif "notext" not in tpl.modifiers:
            text += syl.surface
        style = tpl.style + "-furigana" if "furi" in tpl.modifiers else tpl.style
        return Event(layer=tpl.layer, start=t0, end=t1, style=style,
                     actor=line.actor, text=text)


# ==================================================================== 辅助
class _Aegisub:
    """Aegisub 的帧时间接口（原程序用它算每帧 alpha）。"""

    def __init__(self, ms=33):
        self.ms = ms

    def ms_from_frame(self, n):
        return int(n) * self.ms

    def frame_from_ms(self, t):
        return int(t) // self.ms


class _CharSyl:
    """char 模式下的一个字：借用宿主音节的时间与位置，按时长均分。"""

    def __init__(self, syl, ch, i, n):
        self._s, self.surface, self.ruby, self.inline_fx = syl, ch, None, syl.inline_fx
        self.index = syl.index
        self._n, self._i = n, i
        span = syl.dur / max(1, n)
        self.start = syl.start + i * span
        self.end = self.start + span
        self.left = syl.left + i * (syl.width / max(1, n))
        self.width = syl.width / max(1, n)
        self.center = self.left + self.width / 2

    @property
    def dur(self):
        return self.end - self.start


def _lua_syl(syl):
    from karetpl.lua import LuaTable
    return LuaTable(i=syl.index, center=syl.center, width=syl.width, left=syl.left,
                    start_time=syl.start * 1000, end_time=syl.end * 1000,
                    duration=syl.dur * 1000, inline_fx=syl.inline_fx, text=syl.surface)


def _lua_line(line, prog, metrics):
    from karetpl.lua import LuaTable
    st = prog.styles.get(line.style)
    size = st.size if st else 20.0
    return LuaTable(actor=line.actor, duration=(line.dur + 0.6) * 1000,
                    start_time=line.start, end_time=line.end,
                    left=line.left, width=line.width, right=line.left + line.width,
                    center=line.left + line.width / 2, middle=line.middle,
                    bottom=line.bottom, top=line.bottom - size, height=size,
                    i=1, text=line.surface)


def _lua_orgline(line):
    from karetpl.lua import LuaTable
    return LuaTable(text=line.surface, text_stripped=line.surface)


def _lua_fxgroup():
    from karetpl.lua import LuaTable
    return LuaTable(firstsyl=False, DP=False, all=True)


def _syllable_env(e: dict, line, syl, prog, metrics) -> dict:
    """把音节级量补进求值环境（模板里的 `$scenter` / `$sstart` 等）。"""
    st = prog.styles.get(line.style)
    size = st.size if st else 20.0
    e["scenter"] = syl.center
    e["smiddle"] = line.middle          # 音节基线 = 行 middle（\pos(!$scenter!,$smiddle!) 常用）
    e["swidth"] = syl.width
    e["sleft"] = syl.left
    # Aegisub 的 `$si` 是 **0-based**（实测原版 8.70 = lstart-800 + 0/9*500）
    e["si"] = syl.index - 1
    e["syln"] = len(line.syllables)
    e["ss"], e["se"] = syl.start, syl.end
    # sstart/send/sdur 是**毫秒**（模板里 \t(!$sstart!,...) 原版得 0/175）
    e["sstart"], e["send"] = syl.start * 1000, syl.end * 1000
    e["sdur"] = syl.dur * 1000
    e["sstart_s"], e["send_s"] = syl.start, syl.end
    # template furi 的 $center/$middle 是**注音自身**的位置（原版实测在宿主上方 52px）
    e["center"] = syl.center
    e["middle"] = line.middle - 52
    e["sheight"] = size
    # 这一组是 Aegisub 的**行级**预置变量（不带 s 前缀）：`$bottom` / `$top` 等
    e["bottom"] = line.bottom
    e["top"] = line.bottom - size
    e["right"] = line.left + line.width
    # 音节级的底边：`$sbottom` 在模板里与 `$smiddle` 配对使用
    e["sbottom"] = line.bottom
    return e


def _round_coords(text: str) -> str:
    """`\\pos` / `\\move` / `\\org` 的坐标取整（Aegisub 行为）。

    只在这一小段做：`\\frz-238.8` 这类参数必须保留小数。
    """
    def f(m):
        nums = []
        for x in m.group(2).split(","):
            try:
                nums.append(str(int(float(x))) if "." in x else x)
            except ValueError:
                nums.append(x)
        return "\\" + m.group(1) + "(" + ",".join(nums) + ")"
    text = _NUMBER_TAGS.sub(f, text)

    def g(m):
        parts = _split_top(m.group(1))
        # 前两个是时间（毫秒，取整）；其余是标签串，只清理其中的浮点噪声
        if len(parts) >= 2:
            parts[0] = _fmt(parts[0])
            parts[1] = _fmt(parts[1])
        for i in range(2, len(parts)):
            parts[i] = _clean_float(parts[i])
        return "\\t(" + ",".join(parts) + ")"

    return _TIME_TAGS.sub(g, text)


_FLOAT_RE = re.compile(r"-?\d+\.\d{4,}")


def _clean_float(s: str) -> str:
    """把 `-238.80000000000007` 这类浮点噪声截到一位小数。"""
    return _FLOAT_RE.sub(lambda m: f"{round(float(m.group(0)), 1):g}", s)


def _split_top(s: str):
    """按顶层逗号切（`\t` 的参数里可能嵌 `\t(0,150,...)`）。"""
    depth, cur, out = 0, [], []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def _fmt(x: str) -> str:
    """数值的 ASS 写法：能整除就去掉小数，否则保留一位（`1990.0000000000007` -> `1990`）。"""
    try:
        v = float(x)
    except ValueError:
        return x
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{round(v, 1):g}"
