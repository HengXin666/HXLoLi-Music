# -*- coding: utf-8 -*-
"""代码依赖追踪: 生成每个单元期间执行了工程内哪些函数. 验收台的 G2 靠它在改代码前预测影响集.

为什么要动态追踪: 静态分析看不出 FXMAP 字典派发, getattr, 闭包. 跑一遍就知道.

规则见 steps/5-verify/12-station/impl/deps-code.md. 要点: 工程代码 = 生成器目录下的 .py (不含库);
单元范围 = TR.scope(key) 内; 范围外的工程函数记为 entry; 函数哈希 = 顶层语句 AST + 引用的模块常量 AST.
ASSFX_TRACE=0 关闭. 追踪不改输出 (ASS 逐字节不变).
"""
import ast
import contextlib
import hashlib
import json
import os
import sys

LIB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # skill 的 scripts/


def _h(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


class Tracer:
    def __init__(self):
        self.on = False
        self.root = None
        self.stack = []                    # [(key, 边界帧)]
        self.units, self.entry, self.emit, self.data = {}, set(), {}, {}
        self.data_ids = set()
        self.under = {}                    # 工程函数 code -> 它在栈上时登记的单元 (entry 函数的影响面)
        self._proj = {}                    # code -> bool
        self._mods = {}

    # ------------------------------------------------------------ 安装
    def install(self):
        if self.on or os.environ.get("ASSFX_TRACE") == "0":
            return
        main = sys.modules.get("__main__")
        f = getattr(main, "__file__", None)
        if not f:
            return
        self.root = os.path.dirname(os.path.abspath(f)) + os.sep
        self.on = True
        if hasattr(sys, "monitoring"):     # 3.12+: 非工程代码只付一次代价
            M = sys.monitoring
            try:
                M.use_tool_id(5, "assfx-trace")
            except ValueError:
                pass
            M.register_callback(5, M.events.PY_START, self._mon)
            M.set_events(5, M.events.PY_START)
        else:
            sys.settrace(self._tr)
        f = sys._getframe(1)               # 装上时已在栈上的工程函数 (如在 main 里建 Generator) 也是 entry
        while f is not None:
            if self.is_proj(f.f_code):
                self.entry.add(f.f_code)
            f = f.f_back

    def is_proj(self, code):
        v = self._proj.get(code)
        if v is None:
            fn = os.path.abspath(code.co_filename)
            v = (fn.startswith(self.root) and not fn.startswith(LIB + os.sep) and code.co_name != "<module>"
                 and fn.endswith(".py") and os.path.isfile(fn))
            self._proj[code] = v
        return v

    def _hit(self, code):
        (self.units.setdefault(self.stack[-1][0], set()) if self.stack else self.entry).add(code)

    def _mon(self, code, off):
        if not self.is_proj(code):
            return sys.monitoring.DISABLE
        self._hit(code)

    def _tr(self, frame, ev, arg):
        if ev == "call" and self.is_proj(frame.f_code):
            self._hit(frame.f_code)
        return None

    # ------------------------------------------------------------ 范围
    @contextlib.contextmanager
    def scope(self, key, data=None):
        """单元范围. data: 这个单元的输入数据 (如 PHRASES 的一项), 记哈希到 deps.data."""
        if not self.on:
            yield
            return
        if data is not None:
            self.data[key] = _h(json.dumps(data, sort_keys=True, ensure_ascii=False, default=_dflt))
        stop = sys._getframe(2)
        self.stack.append((key, stop))
        if self.is_proj(stop.f_code):      # G.scope 开在工程函数里: 这个函数本身也是依赖
            self._hit(stop.f_code)
        try:
            yield
        finally:
            self.stack.pop()

    def mark_unit(self, key):
        """Registry.add 调: 栈上每个工程函数都记下 "我在栈上时登记了 key".
        entry 函数 (如 cards.title) 因此只影响它名下的单元; 名下没有单元的 entry 函数改了按全局算."""
        if not self.on:
            return
        f = sys._getframe(1)
        while f is not None:
            if self.is_proj(f.f_code):
                self.under.setdefault(f.f_code, set()).add(key)
            f = f.f_back

    def data_const(self, obj):
        """obj 是按单元登记的数据 (如 PHRASES): 函数哈希不含它."""
        self.data_ids.add(id(obj))

    def on_event(self, layer, s, e, name):
        """Doc.ev 调: 记发出事件的最内层工程函数. 只看到边界帧为止 (边界之上是 main, 不算)."""
        if not self.on or not self.stack:
            return
        key, stop = self.stack[-1]
        f, fn = sys._getframe(2), None
        while f is not None:
            if self.is_proj(f.f_code):
                fn = f.f_code
                break
            if f is stop:
                break
            f = f.f_back
        k = self.fn_key(fn) if fn else "<lib>"
        d = self.emit.setdefault(key, {}).setdefault(k, dict(n=0, layers=set(), t=[s, e]))
        d["n"] += 1
        d["layers"].add(layer)
        d["t"] = [min(d["t"][0], s), max(d["t"][1], e)]

    # ------------------------------------------------------------ 哈希
    def _mod(self, path):
        m = self._mods.get(path)
        if m is None:
            tree = ast.parse(open(path, encoding="utf-8").read())
            consts, imps = {}, []
            for st in tree.body:
                if isinstance(st, ast.ImportFrom) and st.level == 0 and st.module:
                    f = os.path.join(os.path.dirname(path), *st.module.split(".")) + ".py"
                    if os.path.isfile(f):      # 同目录工程模块: from scene import * / from fx_common import X
                        imps.append((f, None if any(a.name == "*" for a in st.names) else {a.asname or a.name: a.name for a in st.names}))
                if isinstance(st, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    for t in (st.targets if isinstance(st, ast.Assign) else [st.target]):
                        for n in ast.walk(t):
                            if isinstance(n, ast.Name):
                                consts.setdefault(n.id, []).append(st)
            m = self._mods[path] = dict(tree=tree, consts=consts, imps=imps)
        return m

    def _top(self, code):
        """code 所在的顶层语句, 类里再下钻到方法. 返回 (名字, 节点)."""
        tree = self._mod(os.path.abspath(code.co_filename))["tree"]
        line, body, names = code.co_firstlineno, tree.body, []
        node = None
        while body:
            hit = next((s for s in body if s.lineno <= line <= (s.end_lineno or s.lineno)
                        or any(d.lineno == line for d in getattr(s, "decorator_list", []))), None)
            if hit is None:
                break
            node = hit
            names.append(_name(hit))
            body = hit.body if isinstance(hit, ast.ClassDef) else None
        return ".".join(names) or "L%d" % line, node

    def fn_key(self, code):
        rel = os.path.relpath(os.path.abspath(code.co_filename), self.root).replace(os.sep, "/")
        return "%s:%s" % (rel, self._top(code)[0])

    def fn_hash(self, path, node, glb_of):
        """glb_of(path) -> 该模块的全局名字典 (判断哪些常量是单元数据)."""
        parts = [ast.dump(_strip(node))]
        used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} - _bound(node)
        for nm in sorted(used):
            parts += self._const(path, nm, glb_of, 0)
        return _h("\n".join(parts))

    def _const(self, path, nm, glb_of, depth):
        """名字 nm 在模块 path 里的常量定义 (AST dump); 本模块没有就顺着同目录的 from-import 找, 最多两层."""
        m = self._mod(path)
        if nm in m["consts"]:
            if id(glb_of(path).get(nm, _Marker())) in self.data_ids:
                return []
            return [nm + "=" + ast.dump(s) for s in m["consts"][nm]]
        if depth >= 2:
            return []
        for f, names in m["imps"]:
            if names is None or nm in names:
                got = self._const(f, nm if names is None else names[nm], glb_of, depth + 1)
                if got:
                    return got
        return []

    def doc(self):
        """清单里的追踪块. units 值是函数 key 的列表."""
        if not self.on:
            return None
        fns, keyed = {}, {}
        glbs = {os.path.abspath(getattr(m, "__file__", "") or ""): vars(m) for m in list(sys.modules.values())
                if getattr(m, "__file__", None)}
        for code in set().union(self.entry, *self.units.values()):
            k = self.fn_key(code)
            keyed[code] = k
            if k not in fns:
                name, node = self._top(code)
                path = os.path.abspath(code.co_filename)
                fns[k] = dict(file=k.split(":")[0], line=node.lineno if node else code.co_firstlineno,
                              h=self.fn_hash(path, node, lambda p: glbs.get(p, {})) if node else None)
        emit = {u: {k: dict(n=d["n"], layers=sorted(d["layers"]), t=[round(v, 3) for v in d["t"]])
                    for k, d in sorted(e.items())} for u, e in self.emit.items()}
        dn = {}
        for path, g in glbs.items():
            if path.startswith(self.root) and not path.startswith(LIB + os.sep):
                names = sorted(n for n, v in g.items() if id(v) in self.data_ids)
                if names:
                    dn[os.path.relpath(path, self.root).replace(os.sep, "/")] = names
        eu = {}
        for c in self.entry:
            eu.setdefault(keyed[c], set()).update(self.under.get(c, ()))
        return dict(fns=fns, data_names=dn, entry={k: sorted(v) for k, v in sorted(eu.items())},
                    units={u: sorted({keyed[c] for c in cs}) for u, cs in self.units.items()},
                    data=dict(self.data), emit=emit)


def _name(st):
    """顶层语句的名字: def/class 用名字, 赋值用第一个目标名, 其余用 L<行号>."""
    if hasattr(st, "name"):
        return st.name
    for t in getattr(st, "targets", None) or [getattr(st, "target", None)]:
        if isinstance(t, ast.Name):
            return t.id
    return "L%d" % st.lineno


def _dflt(o):
    return o.__dict__ if hasattr(o, "__dict__") else str(type(o).__name__)


def _strip(node):
    """去掉 docstring 的拷贝 (改注释不算改代码)."""
    node = ast.parse(ast.unparse(node)).body[0]
    for n in ast.walk(node):
        b = getattr(n, "body", None)
        if isinstance(b, list) and b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant) \
                and isinstance(b[0].value.value, str):
            n.body = b[1:] or [ast.Pass()]
    return node


def _bound(node):
    """函数内自己绑定的名字 (参数, 局部赋值): 不是模块常量."""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            out.add(n.id)
    return out


def source_hashes(root, keys, data_names=None):
    """不跑生成器, 按当前源码重算一组函数 key 的哈希 (改前预测用). 返回 {key: hash 或 None(已删)}.
    data_names: {文件: [常量名]}, 登记为单元数据的常量 (清单 trace.data_names), 不算进函数哈希."""
    t = Tracer()
    t.root = os.path.abspath(root) + os.sep
    out = {}
    for k in keys:
        rel, name = k.split(":", 1)
        path = os.path.join(t.root, rel)
        if not os.path.exists(path):
            out[k] = None
            continue
        try:
            m = t._mod(path)
        except SyntaxError:
            out[k] = "syntax-error"
            continue
        node, body = None, m["tree"].body
        for part in name.split("."):
            node = next((s for s in (body or []) if _name(s) == part), None)
            if node is None:
                break
            body = getattr(node, "body", None) if isinstance(node, ast.ClassDef) else None
        t.data_ids = {id(_Marker)}
        glb_of = lambda p: {nm: _Marker for nm in (data_names or {}).get(  # noqa: E731
            os.path.relpath(p, t.root).replace(os.sep, "/"), ())}
        out[k] = t.fn_hash(path, node, glb_of) if node is not None else None
    return out


class _Marker:
    pass


TR = Tracer()
