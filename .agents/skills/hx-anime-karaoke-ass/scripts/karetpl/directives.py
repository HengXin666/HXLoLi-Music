# -*- coding: utf-8 -*-
"""模板指令：maxloop / multiloop / retime。

三者都是"把一行模板变成若干 (时间窗, 循环变量) 组合"。抽出来是为了：
  * 单位只在这里转换（ASS 混用秒与毫秒，实测踩过多次）
  * 新模式可注册，不必改 Expander
"""
import re

_MS = 1000.0
# 指令的参数里可能带括号（`retime(...)` 的表达式、`maxloop(math.ceil(x))`），
# 所以不能简单用 `[^)]*`  那样 `!retime("line",-300,300)!` 会被截断成
# `!retime("line",-300,`，strip 后残留 `!ad(150` 让后续 `!...!` 全部配对错乱。
_DIRHEAD = re.compile(r"!(maxloop|multiloop|retime)\(")


def _scan_dirs(text):
    """扫出全部 `!名字(...)!`。括号按深度配对（参数里常有嵌套括号）。

    yield (起, 止, 名字, 参数字符串)。
    """
    n = len(text)
    for m in _DIRHEAD.finditer(text):
        k = m.end() - 1                    # 指向 "("
        depth, p2 = 0, k
        while p2 < n:
            if text[p2] == "(":
                depth += 1
            elif text[p2] == ")":
                depth -= 1
                if depth == 0:
                    break
            p2 += 1
        if p2 + 1 < n and text[p2 + 1] == "!":
            yield (m.start(), p2 + 2, m.group(1), text[k + 1:p2])




class Loop:
    """一次展开的循环变量。"""

    __slots__ = ("j", "j1", "j2", "maxj", "maxj1", "maxj2")

    def __init__(self, j=1, j1=1, j2=1, maxj=1, maxj1=1, maxj2=1):
        self.j, self.j1, self.j2 = j, j1, j2
        self.maxj, self.maxj1, self.maxj2 = maxj, maxj1, maxj2

    def as_env(self) -> dict:
        return dict(j=self.j, j1=self.j1, j2=self.j2,
                    maxj=self.maxj, maxj1=self.maxj1, maxj2=self.maxj2)


ONLY = [Loop()]        # 无循环指令时的唯一组合


def find(text: str, name: str):
    """取 `!name(...)!` 的参数文本；没有则 None。"""
    for _a, _b, nm, arg in _scan_dirs(text):
        if nm == name:
            return arg
    return None


def strip(text: str) -> str:
    """去掉全部指令（它们不参与正文）。"""
    out, last = [], 0
    for a, b, _n, _arg in _scan_dirs(text):
        out.append(text[last:a])
        last = b
    out.append(text[last:])
    return "".join(out)


def loops(template, env, ev) -> list:
    """算出该模板要跑几次，以及每次的 (j, j1, j2, maxj*)。

    multiloop 的参数可能是**表**（如 `meteor`），它的长度由 code line 在运行时决定；
    而原版的 multiloop 是自定义 Lua 函数（sum(Σtbl[i]) 层），**不能**用 len() 猜 
    实测 `meteor={128×13}` 应展开 1664 层，用 len 只得 13，让爆发段少两个数量级。
    """
    ml = find(template.text, "maxloop")
    if ml is not None:
        n = _int(ev.eval(ml, env, raw=True), ev, f"maxloop({ml})")
        n = max(1, min(n, 5000))
        return [Loop(j=j, maxj=n, j1=j, maxj1=n) for j in range(1, n + 1)]

    mm = find(template.text, "multiloop")
    if mm is not None:
        parts = [x.strip() for x in mm.split(",") if x.strip()]
        args = [ev.eval(x, env, raw=True) for x in parts] or [None]
        fn = ev.globals.get("multiloop")
        if fn is not None:
            try:
                if len(args) == 1:
                    args.append(1)
                r = ev.interp.call(fn, args, ev.globals, None)
                tbl = r[0] if isinstance(r, tuple) else r
                if isinstance(tbl, dict) and tbl:
                    return _from_table(tbl)
                # 数值形式 multiloop(N, multi)：原版 Lua 的实现在**函数外**读 maxj1/maxj2/j1/j2，
                # 它只调 maxloop(N) 并把这些量设成全局  所以这里自己按同一公式算。
                n = _int(args[0], ev, f"multiloop({mm})")
                multi = _int(args[1], ev, f"multiloop({mm})")
                return _from_numbers(n, multi)
            except Exception as ex:
                ev.warnings.append(f"multiloop 调用失败 ({type(ex).__name__}): {mm[:40]}")
        n = max(1, _int(args[0] if args else 1, ev, f"multiloop({mm})"))
        return [Loop(j=j, maxj=n, j1=j, maxj1=n) for j in range(1, n + 1)]

    return ONLY


def _from_table(tbl):
    """multiloop(表, multi)：表里每项自带 j1/j2/maxj1/maxj2。"""
    out = []
    for i in range(len(tbl)):
        d = tbl.get(i + 1) or {}
        out.append(Loop(j=i + 1, j1=d.get("j1", 1), j2=d.get("j2", 1),
                        maxj=len(tbl), maxj1=d.get("maxj1", 1),
                        maxj2=d.get("maxj2", len(tbl))))
    return out


def _from_numbers(n, multi):
    """multiloop(N, multi)：照原版 Lua 的公式。

        maxj1 = N / multi ;  maxj2 = multi
        j1 = (j-1) % maxj1 + 1 ;  j2 = floor((j-1)/maxj1) + 1
    （实测 `multiloop(2*2, 2)` = (2, 2) -> 4 层，j1/j2 为 (1,1)(2,1)(1,2)(2,2)）
    """
    n, multi = max(1, n), max(1, multi)
    maxj1 = max(1, n // multi)
    out = []
    for j in range(1, n + 1):
        out.append(Loop(j=j, maxj=n, j1=(j - 1) % maxj1 + 1,
                        j2=(j - 1) // maxj1 + 1, maxj1=maxj1, maxj2=multi))
    return out


def _int(v, ev, what):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        ev.warnings.append(f"{what} 求值不是数（{v!r}），退回 1 层")
        return 1


# ---- retime：语义照 Karaoke Templater。l0/l1 与 s0/s1 一律**毫秒**，返回值**秒**
RETIMES = {
    "line":      lambda l0, l1, s0, s1, pre, post: ((l0 + pre) / _MS, (l1 + post) / _MS),
    "abs":       lambda l0, l1, s0, s1, pre, post: (pre / _MS, post / _MS),
    # preline/postline 的 pre/post 相对**本行**的行首 / 行尾（实测两个独立证据）：
    #   `preline(-800,-300)` on 9.50 那句 -> 原版 8.70 = l0-800 ; 不是 "上一行"
    #   `preline(-200+..., ...)`       -> 原版 9.30 = l0-200
    "preline":   lambda l0, l1, s0, s1, pre, post: ((l0 + pre) / _MS, (l0 + post) / _MS),
    "postline":  lambda l0, l1, s0, s1, pre, post: ((l1 + pre) / _MS, (l1 + post) / _MS),
    # pre/post 是**带符号偏移**（ = 音节首前 500ms），一律用 。
    # 写成  会把窗口反向（实测 \t(0,-500) 而原版是 \t(0,500)）。
    "syl":       lambda l0, l1, s0, s1, pre, post: ((l0 + s0 + pre) / _MS, (l0 + s1 + post) / _MS),
    "presyl":    lambda l0, l1, s0, s1, pre, post: ((l0 + s0 + pre) / _MS, (l0 + s0 + post) / _MS),
    "postsyl":   lambda l0, l1, s0, s1, pre, post: ((l0 + s1 + pre) / _MS, (l0 + s1 + post) / _MS),
    "start2syl": lambda l0, l1, s0, s1, pre, post: ((l0 + pre) / _MS, (l0 + s0 + post) / _MS),
    "syl2end":   lambda l0, l1, s0, s1, pre, post: ((l0 + s0 + pre) / _MS, (l1 + post) / _MS),
    "set":       lambda l0, l1, s0, s1, pre, post: (pre / _MS, post / _MS),
}


def window(template, env, ev) -> tuple:
    """算出该模板这次的 (start, end) 秒。"""
    raw = find(template.text, "retime")
    if raw is None:
        return (env["lstart_s"], env["lend_s"])
    # `"line",-300,300` -> mode 与剩余两个参数
    q = re.match(r'\s*"([^"]*)"\s*,(.*)$', raw, re.S)
    if not q:
        return (env["lstart_s"], env["lend_s"])
    mode, rest = q.group(1), q.group(2)
    fn = RETIMES.get(mode)
    if fn is None:
        ev.warnings.append(f"未知 retime 模式 {mode!r}，按 line 处理")
        fn = RETIMES["line"]
    args = _split2(rest)
    pre = ev.eval(args[0], env) if args[0].strip() else 0.0
    post = ev.eval(args[1], env) if len(args) > 1 and args[1].strip() else 0.0
    pre, post = _num(pre), _num(post)
    l0, l1 = env["lstart"], env["lend"]                       # 毫秒（本行）
    s0, s1 = env.get("sstart", 0.0), env.get("send", 0.0)     # 毫秒（相对行首）
    return fn(l0, l1, s0, s1, pre, post)


def _split2(s: str):
    """按**顶层**逗号切成两段（表达式里可能有逗号，如 `ci[2]*50`）。"""
    depth, q, cur, out = 0, None, [], []
    for ch in s:
        if q:
            cur.append(ch)
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
            cur.append(ch)
        elif ch in "([":
            depth += 1
            cur.append(ch)
        elif ch in ")]":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0
