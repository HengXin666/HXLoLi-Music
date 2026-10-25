# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Karaoke Templater `code` 行的执行器  Lua 语句的一个足够子集。

原版的 15 行 code 定义了决定成品外观的全部状态：
  code once     AutoTags / multiloop / Shippo_particle / frame_fad /char_counter
  code syl all  应援色 c / cp（按 actor 与 inline_fx 选）
  code line all ci（逐字计数器）与 cn（字数）
  code syl      RR_pos / RS_pos（贝塞尔的等速采样点，逐字不同）
  code line     meteor / star（随机的星尘，逐行不同）

这些是"效果之所以是那个效果"的部分：模板只是模具，code 行决定里面的数值。
本模块只实现这些行用到的语法：表构造、多返回值赋值、if/elseif、for 数值与 pairs、
function 定义、a[i]=、字符串连接 `..`。
"""
import math
import random
import re



class LuaError(Exception):
    pass


# ------------------------------------------------------------------ 词素
TOKEN_RE = re.compile(r"""
      (?P<ws>\s+)
    | (?P<num>\d+\.\d+|\d+)
    | (?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
    | (?P<name>[A-Za-z_]\w*)
    | (?P<op>\.\.|==|~=|<=|>=|\.\.\.|[+\-*/%^#<>=()\[\]{},;.:])
""", re.X)


def lex(src):
    out, i = [], 0
    while i < len(src):
        m = TOKEN_RE.match(src, i)
        if not m:
            raise LuaError(f"无法词法分析: {src[i:i + 30]!r}")
        i = m.end()
        if m.lastgroup != "ws":
            out.append((m.lastgroup, m.group(0)))
    out.append(("eof", ""))
    return out


class Parser:
    """递归下降解析器：只产出我们支持的语句与表达式的 AST。"""

    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self, k=0):
        return self.t[min(self.i + k, len(self.t) - 1)]

    def take(self, val=None):
        kind, v = self.t[self.i]
        if val is not None and v != val:
            raise LuaError(f"期望 {val!r}, 得到 {v!r}")
        self.i += 1
        return kind, v

    def at(self, val):
        return self.t[self.i][1] == val

    # ---- 语句
    def block(self, stops):
        stmts = []
        while True:
            kind, v = self.peek()
            if kind == "eof" or v in stops:
                break
            if v == ";":
                self.take()
                continue
            stmts.append(self.stmt())
        return stmts

    def stmt(self):
        kind, v = self.peek()
        if v == "local":
            self.take()
            return self.local_stmt()
        if v == "if":
            return self.if_stmt()
        if v == "for":
            return self.for_stmt()
        if v == "function":
            return self.func_stmt()
        if v == "return":
            self.take()
            if self.peek()[1] in ("end", ";", "eof"):
                return ("return", None)
            vals = [self.expr()]
            while self.at(","):
                self.take()
                vals.append(self.expr())
            self.take(";") if self.at(";") else None
            return ("return", vals)
        # 赋值
        target = self.suffixed()
        if self.at(","):
            targets = [target]
            while self.at(","):
                self.take()
                targets.append(self.suffixed())
            self.take("=")
            vals = [self.expr()]
            while self.at(","):
                self.take()
                vals.append(self.expr())
            self.take(";") if self.at(";") else None
            return ("assign", targets, vals)
        if self.at("="):
            self.take()
            val = self.expr()
            self.take(";") if self.at(";") else None
            return ("assign", [target], [val])
        # 函数调用语句
        self.take(";") if self.at(";") else None
        return ("call", target)

    def local_stmt(self):
        names = []
        while True:
            _, n = self.take()
            names.append(n)
            if self.at(","):
                self.take()
                continue
            break
        vals = []
        if self.at("="):
            self.take()
            vals.append(self.expr())
            while self.at(","):
                self.take()
                vals.append(self.expr())
        self.take(";") if self.at(";") else None
        return ("local", names, vals)

    def if_stmt(self):
        self.take("if")
        arms = []
        cond = self.expr()
        self.take("then")
        body = self.block({"elseif", "else", "end"})
        arms.append((cond, body))
        while self.at("elseif"):
            self.take()
            c = self.expr()
            self.take("then")
            arms.append((c, self.block({"elseif", "else", "end"})))
        els = []
        if self.at("else"):
            self.take()
            els = self.block({"end"})
        self.take("end")
        return ("if", arms, els)

    def for_stmt(self):
        self.take("for")
        names = []
        while True:
            _, n = self.take()
            names.append(n)
            if self.at(","):
                self.take()
                continue
            break
        if self.at("="):
            self.take()
            a = self.expr()
            self.take(",")
            b = self.expr()
            step = None
            if self.at(","):
                self.take()
                step = self.expr()
            self.take("do")
            body = self.block({"end"})
            self.take("end")
            return ("fornum", names[0], a, b, step, body)
        self.take("in")
        it = self.expr()
        self.take("do")
        body = self.block({"end"})
        self.take("end")
        return ("forin", names, it, body)

    def func_stmt(self):
        self.take("function")
        path = [self.take()[1]]
        while self.at("."):
            self.take()
            path.append(self.take()[1])
        self.take("(")
        args = []
        while not self.at(")"):
            args.append(self.take()[1])
            if self.at(","):
                self.take()
        self.take(")")
        body = self.block({"end"})
        self.take("end")
        return ("func", path, args, body)

    # ---- 表达式
    def expr(self):
        return self.or_expr()

    def or_expr(self):
        e = self.and_expr()
        while self.at("or"):
            self.take()
            e = ("or", e, self.and_expr())
        return e

    def and_expr(self):
        e = self.cmp_expr()
        while self.at("and"):
            self.take()
            e = ("and", e, self.cmp_expr())
        return e

    def cmp_expr(self):
        e = self.concat()
        while self.peek()[1] in ("==", "~=", "<", ">", "<=", ">="):
            op = self.take()[1]
            e = ("bin", op, e, self.concat())
        return e

    def concat(self):
        e = self.add()
        while self.at(".."):
            self.take()
            e = ("concat", e, self.add())
        return e

    def add(self):
        e = self.mul()
        while self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            e = ("bin", op, e, self.mul())
        return e

    def mul(self):
        e = self.pow()
        while self.peek()[1] in ("*", "/", "%"):
            op = self.take()[1]
            e = ("bin", op, e, self.pow())
        return e

    def pow(self):
        # 左操作数不能用 suffixed：它会把 `(a+b)` 后面的 `(` 当成函数调用
        # （`(1-t)^(n-i+1)` 会解析成 `(1-t)(...)`）。幂的左操作数只需 primary。
        if self.at("-"):
            self.take()
            return ("neg", self.pow())
        if self.at("#"):
            self.take()
            return ("len", self.pow())
        if self.at("not"):
            self.take()
            return ("not", self.pow())
        e = self.suffixed()
        if self.at("^"):
            self.take()
            e = ("bin", "^", e, self.pow())
        return e

    def unary(self):
        if self.at("-"):
            self.take()
            return ("neg", self.unary())
        if self.at("#"):
            self.take()
            return ("len", self.unary())
        if self.at("not"):
            self.take()
            return ("not", self.unary())
        return self.suffixed()

    def suffixed(self):
        """Agent Notes
        .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
        """
        e = self.primary()
        # 括号表达式（主元是 '('）后面不接调用：`(1-t)^2` 里的 `^2` 不是调用，
        # 而 `f(1)` 的 `(1)` 才是。用标记区分，别靠前瞻猜。
        parenthesized = e[0] == "group"
        while True:
            if parenthesized:
                break
            if self.at("."):
                self.take()
                # Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
                # 
                e = ("index", e, ("lit", self.take()[1]))
            elif self.at("["):
                self.take()
                k = self.expr()
                self.take("]")
                e = ("index", e, k)
            elif self.at(":"):
                self.take()
                meth = ("lit", self.take()[1])
                self.take("(")
                args = []
                while not self.at(")"):
                    args.append(self.expr())
                    if self.at(","):
                        self.take()
                self.take(")")
                fn = ("index", e, meth)
                e = ("call", fn, [e] + args)      # 冒号调用把自身作为第一个参数
            elif self.at("("):
                self.take()
                args = []
                while not self.at(")"):
                    args.append(self.expr())
                    if self.at(","):
                        self.take()
                self.take(")")
                e = ("call", e, args)
            else:
                break
        return e

    def primary(self):
        kind, v = self.take()
        if kind == "num":
            return ("lit", float(v) if "." in v else int(v))
        if kind == "str":
            return ("lit", unescape(v[1:-1]))
        if v == "true":
            return ("lit", True)
        if v == "false":
            return ("lit", False)
        if v == "nil":
            return ("lit", None)
        if v == "(":
            e = self.expr()
            self.take(")")
            return ("group", e)
        if v == "{":
            items, keys = [], []
            while not self.at("}"):
                if self.at("["):
                    self.take()
                    k = self.expr()
                    self.take("]")
                    self.take("=")
                    keys.append((k, self.expr()))
                elif self.peek()[0] == "name" and self.peek(1)[1] == "=":
                    k = self.take()[1]                 # {x=1} 的键名形式
                    self.take("=")
                    keys.append((("lit", k), self.expr()))
                else:
                    items.append(self.expr())
                if self.at(",") or self.at(";"):
                    self.take()
                else:
                    break
            self.take("}")
            return ("table", items, keys)
        if kind == "name" and v == "function":
            self.take("(")
            args = []
            while not self.at(")"):
                args.append(self.take()[1])
                if self.at(","):
                    self.take()
            self.take(")")
            body = self.block({"end"})
            self.take("end")
            return ("func", None, args, body)
        if kind == "name":
            return ("name", v)
        raise LuaError(f"意外的记号 {v!r}")


def unescape(s):
    return s.replace('\\"', '"').replace("\\'", "'").replace("\\n", "\n").replace("\\\\", "\\")


# ------------------------------------------------------------------ 运行时
class LuaTable(dict):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)

    def __getattr__(self, k):
        if k.startswith("_"):
            raise AttributeError(k)
        return self.get(k)


class Scope:
    def __init__(self, parent=None):
        self.v = {}
        self.parent = parent

    def get(self, k):
        s = self
        while s:
            if k in s.v:
                return s.v[k]
            s = s.parent
        return None

    def has(self, k):
        s = self
        while s:
            if k in s.v:
                return True
            s = s.parent
        return False

    def set(self, k, v):
        s = self
        while s:
            if k in s.v:
                s.v[k] = v
                return
            s = s.parent
        self.v[k] = v

    def declare(self, k, v):
        self.v[k] = v


def truthy(v):
    return not (v is None or v is False)


def lua_num(v):
    return v if isinstance(v, (int, float)) else 0


def to_str(v):
    if v is None:
        return "nil"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


class Interp:
    def __init__(self, builtins=None, rng=None):
        self.rng = rng or random.Random()
        self.globals = Scope()
        self.globals.declare("math", LuaTable(
            # math.random(m,n)：m>n 时 Lua 的 math.random 会抛错，但原版程序里
            # 用了 math.random(line.bottom+10, line.top-10)（bottom>top，逆序），
            # 说明 Aegisub 运行时容忍它。这里按 [min,max] 处理，保住随机分布。
            random=lambda *a: self.rng.random() if not a else
            (self.rng.randint(1, max(1, int(a[0]))) if len(a) == 1 else
             self.rng.randint(min(int(a[0]), int(a[1])), max(int(a[0]), int(a[1])))),
            ceil=lambda x: int(math.ceil(x)), floor=lambda x: int(math.floor(x)),
            fmod=lambda a, b: int(a) % int(b) if int(b) else 0,
            abs=abs, sqrt=math.sqrt, min=min, max=max, pi=math.pi,
            sqrt2=math.sqrt(2)))
        self.globals.declare("unicode", LuaTable(
            len=lambda x: len(str(x)),
            sub=lambda x, a, b=None: str(x)[int(a) - 1:int(b)] if b else str(x)[int(a) - 1:]))
        self.globals.declare("string", LuaTable(
            gsub=lambda s, a, b="": str(s).replace(str(a), str(b)),
            gmatch=lambda s, pat: _gmatch(s, pat),
            format=lambda f, *a: (f % a) if a else f,
            len=lambda s: len(s), sub=lambda s, a, b=None: s[int(a) - 1:int(b)] if b else s[int(a) - 1:],
            rep=lambda s, n: s * int(n),
            find=lambda s, p: (s.find(str(p)) + 1) or None))
        self.globals.declare("table", LuaTable(
            insert=lambda t, v: t.setdefault("__arr__", t).__setitem__(len(t) + 1, v),
            concat=lambda t, sep="": sep.join(to_str(t[k]) for k in sorted(k for k in t if isinstance(k, int))),
            remove=lambda t, i=None: t.pop(i or len(t), None)))
        self.globals.declare("_G", self.globals.v)
        for k, v in (builtins or {}).items():
            self.globals.declare(k, v)
        self.uni = LuaTable(
            len=lambda s: len(str(s)),
            sub=lambda s, a, b=None: str(s)[int(a) - 1:int(b)] if b else str(s)[int(a) - 1:])

    # ---- 执行
    def run(self, src, scope=None, ctx=None):
        src = re.sub(r"--[^\n]*", "", src)
        sc = scope or self.globals
        stmts = Parser(lex(src)).block({"eof"})
        return self.exec_block(stmts, sc, ctx)

    def exec_block(self, stmts, sc, ctx):
        for st in stmts:
            r = self.exec_stmt(st, sc, ctx)
            if r is not None:
                return r
        return None

    def exec_stmt(self, st, sc, ctx):
        k = st[0]
        if k == "local":
            _, names, vals = st
            vs = [self.eval(e, sc, ctx) for e in vals]
            for i, n in enumerate(names):
                sc.declare(n, vs[i] if i < len(vs) else None)
            return None
        if k == "assign":
            _, targets, vals = st
            vs = [self.eval(e, sc, ctx) for e in vals]
            for i, t in enumerate(targets):
                self.assign(t, vs[i] if i < len(vs) else None, sc, ctx)
            return None
        if k == "call":
            self.eval(st[1], sc, ctx)
            return None
        if k == "if":
            _, arms, els = st
            for cond, body in arms:
                if truthy(self.eval(cond, sc, ctx)):
                    return self.exec_block(body, sc, ctx)
            return self.exec_block(els, sc, ctx)
        if k == "fornum":
            _, name, a, b, step, body = st
            a = lua_num(self.eval(a, sc, ctx))
            b = lua_num(self.eval(b, sc, ctx))
            step = lua_num(self.eval(step, sc, ctx)) if step else 1
            i = a
            while (step > 0 and i <= b) or (step < 0 and i >= b):
                inner = Scope(sc)
                inner.declare(name, i)
                r = self.exec_block(body, inner, ctx)
                if r is not None:
                    return r
                i += step
            return None
        if k == "forin":
            _, names, it, body = st
            obj = self.eval(it, sc, ctx)
            pairs = sorted(obj.items(), key=lambda kv: (isinstance(kv[0], str), kv[0])) \
                if isinstance(obj, dict) else []
            for kk, vv in pairs:
                inner = Scope(sc)
                for i, n in enumerate(names):
                    inner.declare(n, kk if i == 0 else vv)
                r = self.exec_block(body, inner, ctx)
                if r is not None:
                    return r
            return None
        if k == "func":
            _, path, args, body = st
            fn = ("userfn", args, body, sc, self)
            if path[0] == "function" or len(path) == 1:
                sc.set(path[0], fn)
            else:
                obj = sc.get(path[0])
                if isinstance(obj, dict):
                    obj[path[-1]] = fn
            return None
        if k == "return":
            if st[1] is None:
                return ("ret", None)
            vs = [self.eval(e, sc, ctx) for e in st[1]]
            return ("ret", vs[0] if len(vs) == 1 else tuple(vs))
        raise LuaError(f"未实现的语句 {k}")

    def assign(self, t, v, sc, ctx):
        if t[0] == "name":
            sc.set(t[1], v)
            return
        if t[0] == "index":
            obj = self.eval(t[1], sc, ctx)
            key = self.eval(t[2], sc, ctx)
            if isinstance(obj, dict):
                obj[key] = v
            return
        raise LuaError("不支持的赋值目标")

    # ---- 求值
    def eval(self, e, sc, ctx):
        k = e[0]
        if k == "group":
            return self.eval(e[1], sc, ctx)
        if k == "lit":
            return e[1]
        if k == "name":
            n = e[1]
            if sc.has(n):
                return sc.get(n)
            return None
        if k == "table":
            _, items, keys = e
            t = LuaTable()
            for i, it in enumerate(items):
                t[i + 1] = self.eval(it, sc, ctx)
            for kk, vv in keys:
                t[self.eval(kk, sc, ctx)] = self.eval(vv, sc, ctx)
            return t
        if k == "index":
            obj = self.eval(e[1], sc, ctx)
            key = self.eval(e[2], sc, ctx)
            if isinstance(obj, dict):
                return obj.get(key)
            if isinstance(obj, (list, tuple)):
                try:
                    i = int(key)
                except (TypeError, ValueError):
                    return None
                return obj[i - 1] if 1 <= i <= len(obj) else None
            if isinstance(obj, str):
                # Lua 里字符串也能调 string 库：`s:gsub(...)` 等价 `string.gsub(s, ...)`。
                # 非数字键（方法名）要回落到 string 表，而不是 int(key) 崩掉。
                if isinstance(key, str) and not key.lstrip("-").isdigit():
                    lib = self.globals.get("string") or {}
                    return lib.get(key)
                try:
                    i = int(key)
                except (TypeError, ValueError):
                    return None
                return obj[i - 1] if 1 <= i <= len(obj) else None
            return None
        if k == "bin":
            _, op, a, b = e
            if op == "..":
                return None
            x, y = self.eval(a, sc, ctx), self.eval(b, sc, ctx)
            try:
                if op == "+":
                    return lua_num(x) + lua_num(y)
                if op == "-":
                    return lua_num(x) - lua_num(y)
                if op == "*":
                    return lua_num(x) * lua_num(y)
                if op == "/":
                    return lua_num(x) / lua_num(y) if lua_num(y) else 0
                if op == "%":
                    return lua_num(x) % lua_num(y) if lua_num(y) else 0
                if op == "^":
                    return lua_num(x) ** lua_num(y)
                if op == "==":
                    return x == y
                if op == "~=":
                    return x != y
                if op == "<":
                    return x < y
                if op == ">":
                    return x > y
                if op == "<=":
                    return x <= y
                if op == ">=":
                    return x >= y
            except TypeError:
                return False
            return None
        if k == "concat":
            a, b = self.eval(e[1], sc, ctx), self.eval(e[2], sc, ctx)
            if a is None and b is None:
                return None
            return to_str(a) + to_str(b)
        if k == "and":
            a = self.eval(e[1], sc, ctx)
            return self.eval(e[2], sc, ctx) if truthy(a) else a
        if k == "or":
            a = self.eval(e[1], sc, ctx)
            return a if truthy(a) else self.eval(e[2], sc, ctx)
        if k == "not":
            return not truthy(self.eval(e[1], sc, ctx))
        if k == "neg":
            return -lua_num(self.eval(e[1], sc, ctx))
        if k == "len":
            v = self.eval(e[1], sc, ctx)
            if isinstance(v, str):
                return len(v)
            if isinstance(v, (list, tuple)):
                # 宿主函数（如 bezier_n_uniform_speed）返回的是 Python list，
                # Lua 的 `#` 对它也要给长度。不处理会让 `meteor[i]=#pos[i]` 全为 0
                # （实测 meteor={1:0,...,7:0}），爆发段因此不展开。
                return len(v)
            if isinstance(v, dict):
                if not v:
                    return 0
                ints = [k2 for k2 in v if isinstance(k2, int)]
                return max(ints) if ints else len(v)
            return 0
        if k == "func":
            return ("userfn", e[2], e[3], sc, self)
        if k == "call":
            fn = self.eval(e[1], sc, ctx)
            args = [self.eval(a, sc, ctx) for a in e[2]]
            return self.call(fn, args, sc, ctx)
        raise LuaError(f"未实现的表达式 {k}")

    def call(self, fn, args, sc, ctx):
        if callable(fn):
            return fn(*args)
        if isinstance(fn, tuple) and fn[0] == "userfn":
            _, params, body, closure, interp = fn
            inner = Scope(closure)
            for i, p in enumerate(params):
                inner.declare(p, args[i] if i < len(args) else None)
            r = self.exec_block(body, inner, ctx)
            if r is not None and r[0] == "ret":
                return r[1]
            return None
        return None


def _gmatch(s, pat):
    """
    .agents/notes/implemented/process/2026-10-05-karaoke-scripts-grouping.md
极简 string.gmatch：只支持 '[m] [^m]+' 这类字符类切分。"""
    s = str(s)
    if pat in ("[m] [^m]+", "[^m]+"):
        out = []
        for part in re.split(r"(?=m )", s):
            if part.strip():
                out.append(part)
        return iter(out)
    # Agent Notes: hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开
    # 
    m = re.findall(r"(%s)" % pat.replace("%d", r"\d+").replace("%a", "[A-Za-z]")
                   .replace("%s", r"\s").replace("%w", r"\w"), s)
    return iter(m or [])
