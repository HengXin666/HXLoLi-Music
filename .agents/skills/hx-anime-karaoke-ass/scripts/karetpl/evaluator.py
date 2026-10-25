# -*- coding: utf-8 -*-
"""Evaluator  模板里 `!expr!` 与 `$name` 的求值门面。

包住 Lua 解释器，负责三件事：
  1. AST 缓存（同一表达式一句里要算上千次，不缓存会慢 100 倍）
  2. `$name` -> `name` 的改写（Aegisub 的预置变量记号不是合法 Lua）
  3. 数值的 Lua 化输出（整数不带小数点）

**保留类型**还是**转字符串**由 raw 参数决定：`multiloop(meteor)` 需要表本身，
而模板正文需要文本。两者共用一个实现，避免两份 80% 重复的代码。
"""
import re

from karetpl.lua import Interp, lex, Parser

_DOLLAR = re.compile(r"\$([A-Za-z_]\w*)")


class Evaluator:
    """Lua 子集的求值器（带 AST 缓存）。"""

    def __init__(self, rng=None):
        self.interp = Interp(rng=rng)
        self._ast = {}
        self.warnings = []

    # ---- 全局环境
    @property
    def globals(self):
        return self.interp.globals

    def define(self, name, value):
        """注册一个宿主函数/常量（`_G` 也是同一份，所以 Lua 里能看见）。"""
        self.globals.v[name] = value
        g = self.globals.v.get("_G")
        if isinstance(g, dict):
            g[name] = value

    def run(self, source, scope=None):
        """执行一段 Lua 语句。"""
        return self.interp.run(source, scope or self.globals, None)

    def scope(self, parent=None):
        """新建作用域（`code` 行之间互不污染）。"""
        from karetpl.lua import Scope
        return Scope(parent or self.globals)

    # ---- 表达式
    def _compile(self, expr: str):
        src = _DOLLAR.sub(r"\1", expr.strip())
        node = self._ast.get(src)
        if node is None:
            try:
                node = Parser(lex("__r = " + src)).block({"eof"})
            except Exception:
                node = False
            self._ast[src] = node
        return node

    def eval(self, expr: str, env: dict, raw: bool = False):
        """求值 `!...!` 的表达式。

        raw=False（默认）返回**文本**（模板正文要拼字符串）；
        raw=True 返回**原值**（表 / 数 / bool，供 loop_spec 这类判断用）。
        """
        if expr is None or not expr.strip():
            return None if raw else ""
        for k, v in env.items():
            self.globals.set(k, v)
        node = self._compile(expr)
        if node is False:
            self.warnings.append(f"表达式解析失败: {expr[:48]}")
            return None if raw else ""
        try:
            self.interp.exec_block(node, self.globals, None)
            v = self.globals.get("__r")
        except Exception as ex:
            self.warnings.append(f"表达式求值失败 ({type(ex).__name__}): {expr[:48]}")
            return None if raw else ""
        if raw:
            return v
        return tostring(v)

    def substitute(self, text: str, env: dict) -> str:
        """替换正文里的 `!expr!`，再替换 `$name`（预置变量在 `!...!` 之外）。

        正文里不应再有指令（调用方先 strip）；这里只处理真正的表达式。
        """
        out = re.sub(r"!([^!]+)!", lambda m: self.eval(m.group(1), env), text)
        out = re.sub(r"\$([A-Za-z_]\w*)",
                     lambda m: tostring(env[m.group(1)]) if m.group(1) in env else m.group(0),
                     out)
        return out


def tostring(v) -> str:
    """Lua 的 tostring：整数值不带小数点（`620.0` -> `620`）。

    `\\pos` 的取整不在这里做  那要按标签区分（`\\frz-238.8` 要保留小数），
    由 Expander 在生成后统一处理。
    """
    if v is None:
        return ""
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)
