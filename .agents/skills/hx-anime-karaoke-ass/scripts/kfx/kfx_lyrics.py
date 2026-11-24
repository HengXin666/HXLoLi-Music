"""hx-kara 4 lyrics model: lyrics.txt + timing.json -> Line / Glyph / Ruby.

lyrics.txt row:  `mm:ss.xxx | JP with marks | 中文`
JP marks (same grammar as the rest of the skill):
  [漢字|かな]     ruby group. [世界|せ.かい] gives each kanji its own reading
  [今日|=きょう]  jukujikun. One reading over the whole group
  {(Latin)|かな}  latin group. The kana only carry the timing
  other char      one unit (kana, space, punctuation)
timing.json rows: {line, unit, mora, text, s, e} in song seconds. A unit is one token above.
Every glyph gets its own sung window, so a kanji lights only while its own kana are sung."""
import json
import re
from dataclasses import dataclass, field

TOKEN = re.compile(r"\[([^|\]]+)\|([^\]]+)\]|\{([^|}]+)\|([^}]+)\}|(.)")
SPACE = (" ", "\u3000")


@dataclass
class Glyph:
    ch: str
    kind: str              # kanji | kana | latin | space | punct
    a: float = 0.0         # onset (song clock + av offset)
    b: float = 0.0         # end of its sung window
    unit: int = 0
    group: int = 0         # index of the space separated JP group
    rubies: list = field(default_factory=list)
    kw: str = ""           # keyword id when the glyph belongs to a keyword


@dataclass
class Ruby:
    ch: str
    a: float
    b: float
    parent: int            # glyph index


@dataclass
class Line:
    idx: int
    t_ref: float
    jp_raw: str
    cn: str
    glyphs: list
    s: float = 0.0
    e: float = 0.0

    @property
    def text(self):
        return "".join(g.ch for g in self.glyphs)

    def sung(self):
        return [g for g in self.glyphs if g.kind not in ("space",)]


def _split_morae(morae, parts):
    """Give each ruby part its own run of morae. morae: [(s, e, text)]."""
    out, i = [], 0
    for k, part in enumerate(parts):
        need, got, run = len(part), 0, []
        while i < len(morae) and (got < need or k == len(parts) - 1):
            run.append(morae[i])
            got += len(morae[i][2])
            i += 1
        out.append(run or [morae[min(i, len(morae)) - 1]])
    return out


def parse_rows(path):
    rows = []
    for raw in open(path, encoding="utf-8"):
        raw = raw.rstrip("\n")
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        parts = [p.strip() for p in raw.split("|", 1)]
        if len(parts) < 2 or not re.match(r"^\d+:\d+(\.\d+)?$", parts[0]):
            continue
        body = parts[1]
        jp, cn = body.rsplit(" | ", 1) if " | " in body else (body, "")
        mm, ss = parts[0].split(":")
        rows.append((int(mm) * 60 + float(ss), jp.strip(), cn.strip()))
    return rows


def load(lyrics, timing, av_offset=0.0, hold_cap=1.8):
    rows = parse_rows(lyrics)
    T = {}
    for r in json.load(open(timing, encoding="utf-8")):
        T.setdefault((r["line"], r["unit"]), []).append((r["s"] + av_offset, r["e"] + av_offset, r["text"]))
    lines = []
    for li, (t_ref, jp, cn) in enumerate(rows):
        glyphs, group = [], 0
        for ui, m in enumerate(TOKEN.finditer(jp)):
            morae = sorted(T.get((li, ui), []))
            if m.group(1):
                text, ruby = m.group(1), m.group(2)
                if ruby.startswith("="):
                    readings, chars = [ruby[1:]], [text]
                else:
                    readings = ruby.split(".")
                    chars = list(text) if len(readings) == len(text) else [text]
                    readings = readings if len(chars) > 1 else [ruby.replace(".", "")]
                runs = _split_morae(morae, readings) if morae else [[] for _ in chars]
                for ch, rd, run in zip(chars, readings, runs):
                    g = Glyph(ch, "kanji", unit=ui, group=group)
                    if run:
                        g.a, g.b = run[0][0], run[-1][1]
                    kana = _split_morae(run, list(rd)) if run else [[] for _ in rd]
                    for kc, kr in zip(rd, kana):
                        if kr:
                            g.rubies.append(Ruby(kc, kr[0][0], kr[-1][1], len(glyphs)))
                    glyphs.append(g)
            elif m.group(3):
                g = Glyph(m.group(3).strip("()"), "latin", unit=ui, group=group)
                if morae:
                    g.a, g.b = morae[0][0], morae[-1][1]
                glyphs.append(g)
            else:
                ch = m.group(5)
                if ch in SPACE:
                    group += 1
                    glyphs.append(Glyph(" ", "space", unit=ui, group=group))
                    continue
                kind = "punct" if ch in "?？!！、。…" else "kana"
                g = Glyph(ch, kind, unit=ui, group=group)
                if morae:
                    g.a, g.b = morae[0][0], morae[-1][1]
                glyphs.append(g)
        _fill_untimed(glyphs)
        timed = [g for g in glyphs if g.kind != "space"]
        ln = Line(li, t_ref, jp, cn, glyphs, timed[0].a, timed[-1].b)
        for g in timed:                       # cap very long tails for the wipe
            g.b = min(g.b, g.a + hold_cap)
        lines.append(ln)
    return lines


def _fill_untimed(glyphs):
    """Punctuation without its own mora rides on the previous glyph."""
    last = None
    for g in glyphs:
        if g.kind == "space":
            continue
        if g.a == 0.0 and g.b == 0.0 and last is not None:
            g.a = g.b = last.b
            g.b = last.b + 0.2
        last = g
    first = next((g for g in glyphs if g.kind != "space" and (g.a or g.b)), None)
    for g in glyphs:                          # leading marks (「 before the first sung glyph) take its start
        if g.kind == "space":
            continue
        if g is first or first is None:
            break
        if g.a == 0.0 and g.b == 0.0:
            g.a, g.b = first.a, first.a + 0.12
    for g in glyphs:
        if g.kind == "space":
            continue
        if g.b <= g.a:
            g.b = g.a + 0.12
