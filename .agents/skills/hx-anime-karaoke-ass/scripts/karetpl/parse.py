# -*- coding: utf-8 -*-
"""把 ASS 文本解析成 Program。

只认三种 `Effect` 前缀（code / template / karaoke） 其余 Dialogue 是产物，不是程序。
"""
import re

from karetpl.model import CodeBlock, Program, SourceLine, Style, Syllable, Template

K_RE = re.compile(r"\\k[fFoO]?(\d+)")
TAG_RE = re.compile(r"\{([^}]*)\}")
BLOCK_RE = re.compile(r"\{([^}]*)\}([^{]*)")


def _ts(s: str) -> float:
    """ASS 时间戳 -> 绝对秒。"""
    h, m, rest = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def parse_modifiers(effect: str) -> frozenset:
    """`template syl noblank notext fxgroup firstsyl` -> {"syl","noblank",...}"""
    parts = effect.split()
    return frozenset(parts[1:]) if parts else frozenset()


def code_when(effect: str) -> tuple:
    """`code syl all` -> ("syl", ("all",))；`code once` -> ("once", ())"""
    parts = effect.split()[1:]
    if not parts:
        return ("once", ())
    when, rest = parts[0], tuple(parts[1:])
    return (when, rest)


def split_syllables(text: str) -> tuple:
    """从 karaoke 行拆出音节与整句字面。

    字面里 `漢|よみ` 表示注音；`<` 前缀表示逐字注音（`知|<し`）。
    返回 (syllables, surface)。
    """
    syls, t = [], 0.0
    for m in BLOCK_RE.finditer(text):
        k = K_RE.search(m.group(1))
        if not k:
            continue
        dur = int(k.group(1)) / 100.0
        raw = m.group(2).strip()
        # **空 \k 段不产音节**：源行里常有 `{\k15}{\k13}飛|<と` 这种
        # 时间预留段，它们没有字面。当成音节会让 char/syl 的序号整体错位
        # （实测中心偏一个字，且首尾各多一个空音节）。
        # 但时长要累计，否则后续音节的起点会整体前移。
        if raw:
            mm = re.match(r"^(.*?)\|<?(.*)$", raw)
            surf, rd = (mm.group(1), mm.group(2)) if mm else (raw, None)
            fx = re.search(r"\\-(\w+)", m.group(1))
            syls.append(Syllable(index=len(syls) + 1, surface=surf, ruby=rd or None,
                                 start=t, end=t + dur, inline_fx=fx.group(1) if fx else ""))
        t += dur
    # surface **不能**先删标签再删 "|..."：那样会把注音之后整句吃掉（实测 lwidth 算成 225 而非 600）
    surface = "".join(s.surface for s in syls) or re.sub(r"\{[^}]*\}", "", text)
    return syls, surface


def parse(text: str, source: str = "") -> Program:
    prog = Program()
    sect = ""
    body = text.lstrip("\ufeff")
    m = re.search(r"^Title:\s*(.*)$", body, re.M)
    if m:
        prog.title = m.group(1).strip()
    m = re.search(r"^PlayResX:\s*(\d+)", body, re.M)
    if m:
        prog.res_x = int(m.group(1))
    m = re.search(r"^PlayResY:\s*(\d+)", body, re.M)
    if m:
        prog.res_y = int(m.group(1))

    for n, raw in enumerate(body.splitlines(), 1):
        line = raw.rstrip("\n")
        if line.startswith("["):
            sect = line.strip("[]")
            continue
        if sect == "V4+ Styles" and line.startswith("Style:"):
            st = Style.parse(line)
            prog.styles[st.name] = st
            continue
        if sect != "Events" or not line.startswith(("Dialogue:", "Comment:")):
            continue
        f = line.split(",", 9)
        if len(f) < 10:
            continue
        rec = dict(layer=int(f[0].split(":")[1]), start=_ts(f[1]), end=_ts(f[2]),
                   style=f[3], actor=f[4], effect=f[8].strip(), text=f[9], no=n)
        if rec["effect"].startswith("code"):
            when, scopes = code_when(rec["effect"])
            prog.code.append(CodeBlock(when=when, scopes=scopes, text=rec["text"], line_no=n))
        elif rec["effect"].startswith("template"):
            prog.templates.append(Template(
                layer=rec["layer"], style=rec["style"], actor=rec["actor"],
                modifiers=parse_modifiers(rec["effect"]), text=rec["text"],
                name=rec["effect"], line_no=n))
        elif rec["effect"].startswith("karaoke"):
            syls, surface = split_syllables(rec["text"])
            prog.karaoke.append(SourceLine(
                start=rec["start"], end=rec["end"], style=rec["style"],
                actor=rec["actor"], text=rec["text"], syllables=syls, surface=surface))
    return prog


def from_file(path: str) -> Program:
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return parse(fh.read(), source=path)
