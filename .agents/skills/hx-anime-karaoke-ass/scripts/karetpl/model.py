# -*- coding: utf-8 -*-
"""karetpl 的数据模型  ASS 被拆成"程序"与"数据"两层。

只放**值对象**：不带行为、不依赖解释器，方便单独测与序列化。
"""
from dataclasses import dataclass, field


@dataclass
class Style:
    """样式表一行。字段名照 ASS 的 Format 顺序，只保留运行时会用到的。"""
    name: str
    font: str = "Arial"
    size: float = 20.0
    spacing: float = 0.0
    outline: float = 0.0
    align: int = 2
    margin_l: float = 0.0
    margin_r: float = 0.0
    margin_v: float = 0.0
    bold: bool = False

    @classmethod
    def parse(cls, line: str) -> "Style":
        f = [x.strip() for x in line[6:].split(",")]
        g = lambda i, d: f[i] if i < len(f) and f[i] != "" else d
        return cls(name=g(0, "Default"), font=g(1, "Arial"), size=float(g(2, 20)),
                   spacing=float(g(13, 0)), outline=float(g(16, 0)),
                   align=int(g(18, 2) or 2), margin_l=float(g(19, 0)),
                   margin_r=float(g(20, 0)), margin_v=float(g(21, 0)),
                   bold=g(7, "0") not in ("0", ""))


@dataclass
class CodeBlock:
    """一行 `code`  一段要执行的 Lua 语句。"""
    when: str          # once | line | syl | furi | char
    scopes: tuple      # () | ("all",) | ("pre",)
    text: str
    line_no: int = 0


@dataclass
class Template:
    """一行 `template`  模具 + 展开指令。

    layer/style/actor 决定它作用于哪些源行；modifiers 决定"跑几次"；
    text 里的 `!expr!` 在展开时求值。
    """
    layer: int
    style: str
    actor: str
    modifiers: frozenset
    text: str
    name: str = ""
    line_no: int = 0

    def has(self, *mods) -> bool:
        return all(m in self.modifiers for m in mods)

    @property
    def fx(self):
        """`fx CA` / `fx CB`  **音节级**的内联特效选择器。

        原程序用它在源行的 `\-CA` / `\-CB` 标记上挂不同效果（实测点兔 OP 里
        CA 12 个音节、CB 6 个）。忽略它会让带 CB 的模板套到全部音节上，
        条数爆两个数量级（实测 8272 vs 原版 56）。
        """
        parts = self.name.split()
        for i, w in enumerate(parts):
            if w == "fx" and i + 1 < len(parts):
                return parts[i + 1]
        return None


@dataclass
class Syllable:
    """一个音节（一个 \\k 段）。时间是**相对行首的秒**。"""
    index: int
    surface: str            # 字面（去掉 |-注音 部分）
    ruby: str | None        # 注音，没有则 None
    start: float
    end: float
    left: float = 0.0
    width: float = 0.0
    center: float = 0.0
    inline_fx: str = ""

    @property
    def dur(self) -> float:
        return self.end - self.start


@dataclass
class SourceLine:
    """一行 `karaoke` 源歌词。"""
    start: float            # 绝对秒
    end: float
    style: str
    actor: str
    text: str
    syllables: list = field(default_factory=list)
    surface: str = ""       # 全句字面（含注音位置的信息已剥离）
    left: float = 0.0       # 行左边界（由 Metrics 算出）
    width: float = 0.0
    middle: float = 0.0
    bottom: float = 0.0
    height: float = 0.0

    @property
    def dur(self) -> float:
        return self.end - self.start


@dataclass
class Event:
    """一条产出的 Dialogue。"""
    layer: int
    start: float
    end: float
    style: str
    actor: str
    text: str
    source_line: int = 0    # 来自第几个 karaoke 源行（便于溯源）


@dataclass
class Program:
    """一份可执行的 ASS。"""
    styles: dict = field(default_factory=dict)
    code: list = field(default_factory=list)
    templates: list = field(default_factory=list)
    karaoke: list = field(default_factory=list)
    title: str = ""
    res_x: int = 1920
    res_y: int = 1080

    @classmethod
    def from_file(cls, path: str) -> "Program":
        """读一份带 Comment 模板的 ASS。"""
        from karetpl.parse import from_file
        return from_file(path)

    @classmethod
    def from_text(cls, text: str) -> "Program":
        from karetpl.parse import parse
        return parse(text)

    def templates_for(self, line: "SourceLine") -> list:
        """作用于该源行的模板。**样式必须精确相等**  实测用 `in` 会把
        JP_FX_A 配到 JP_FX_AS 的句上（子串命中），产出错时间的事件。"""
        return [t for t in self.templates if t.style == line.style]
