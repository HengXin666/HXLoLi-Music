"""The lyric itself: kanji row, furigana, translation.

Per unit, five layers:
  1 halo   dark blurred border -> readable on any frame (snow, sky, white-out)
  2 base   unsung colour, enters before the singer reaches it
  3 sung   sung colour, wiped in left->right by \\clip over the unit's own duration
  4 pop    glow ring that flares on the onset and dies in ~0.5 s
Exit is a separate event per layer so the entrance \\move and the exit \\move never fight.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from kfx_assw import Event, alpha, col, f1, ms

ENTER_DUR = 0.42


@dataclass
class Slot:
    """Where and when one line lives on screen."""
    tin: float
    tout: float       # exit starts
    xd: float         # exit duration


def _enter_tags(kind: str, x: float, y: float, d: float, dur: float) -> tuple[str, str]:
    """(position tags, transform tags) for an entrance starting d s after the event start."""
    a, b = ms(d), ms(d + dur)
    if kind == "drift":
        return (f"\\move({f1(x)},{f1(y + 16)},{f1(x)},{f1(y)},{a},{b})",
                f"\\blur4\\t({a},{b},\\blur0.6)")
    if kind == "drop":
        return (f"\\move({f1(x)},{f1(y - 24)},{f1(x)},{f1(y)},{a},{b})",
                f"\\blur3\\t({a},{b},\\blur0.6)")
    if kind == "wind":
        return (f"\\move({f1(x - 46)},{f1(y)},{f1(x)},{f1(y)},{a},{b})",
                f"\\blur5\\fax-0.12\\t({a},{b},\\blur0.6\\fax0)")
    if kind == "flash":
        return (f"\\pos({f1(x)},{f1(y)})",
                f"\\fscx140\\fscy140\\blur6\\t({a},{a + 180},0.6,\\fscx100\\fscy100\\blur0.6)")
    # ink: blot settles from soft to sharp
    return (f"\\pos({f1(x)},{f1(y)})",
            f"\\fscx92\\fscy92\\blur10\\t({a},{b},0.7,\\fscx100\\fscy100\\blur0.6)")


def _fade_in(d: float, dur: float, full: str = "&H00&") -> str:
    return f"\\alpha&HFF&\\t({ms(d)},{ms(d + dur * 0.8)},\\alpha{full})"


def exit_tags(kind: str, x: float, y: float, dur: float, rnd: random.Random,
              x0: float = 0, x1: float = 0, yt: float = 0, yb: float = 0) -> str:
    D = ms(dur)
    if kind == "rise":
        return (f"\\move({f1(x)},{f1(y)},{f1(x)},{f1(y - 22)},0,{D})"
                f"\\t(0,{D},0.8,\\alpha&HFF&\\blur5)")
    if kind == "dissolve":
        return f"\\pos({f1(x)},{f1(y)})\\t(0,{D},0.7,\\alpha&HFF&\\blur9\\fscx118\\fscy118)"
    if kind == "shatter":
        dx, dy = rnd.uniform(-70, 70), rnd.uniform(40, 95)
        return (f"\\move({f1(x)},{f1(y)},{f1(x + dx)},{f1(y + dy)},0,{D})"
                f"\\t(0,{D},1.6,\\frz{f1(rnd.uniform(-55, 55))}\\blur2)"
                f"\\t(0,{int(D * 0.7)},0.7,\\alpha&HFF&)")
    if kind == "wind":
        return (f"\\move({f1(x)},{f1(y)},{f1(x + 70)},{f1(y - 10)},0,{D})"
                f"\\t(0,{D},\\alpha&HFF&\\blur6\\fax0.2)")
    if kind == "erase":
        return (f"\\pos({f1(x)},{f1(y)})\\iclip({f1(x0)},{f1(yt)},{f1(x0)},{f1(yb)})"
                f"\\t(0,{D},\\iclip({f1(x0)},{f1(yt)},{f1(x1)},{f1(yb)}))")
    if kind == "white":
        h = D // 2
        return (f"\\pos({f1(x)},{f1(y)})\\t(0,{h},\\1c&HFFFFFF&\\3c&HFFFFFF&\\blur3)"
                f"\\t({h},{D},\\alpha&HFF&\\blur12\\fscx112\\fscy112)")
    if kind == "veil":
        return (f"\\move({f1(x)},{f1(y)},{f1(x)},{f1(y + 8)},0,{D})"
                f"\\t(0,{D},0.6,\\alpha&HFF&\\blur12)")
    raise ValueError(kind)


class TextFx:
    def __init__(self, ctx):
        self.c = ctx

    # ---- one glyph group (unit or ruby piece) -------------------------------------------
    def glyph(self, *, style: str, text: str, x: float, y: float, slot: Slot, appear: float,
              sing_s: float, sing_e: float, pal: dict, enter: str, exit_kind: str,
              exit_at: float, rnd: random.Random, bord: float, halo_bord: float,
              sung_col: str, glow_col: str, wipe_w: float, pop: float = 1.12,
              extra_sung: str = "", tag: str = "") -> None:
        E = self.c.events
        sc = col(pal["outline"])
        halo = col(pal["halo"])
        ed = min(ENTER_DUR, max(0.12, sing_s - appear))
        xl, xr = x - wipe_w / 2 - 6, x + wipe_w / 2 + 6
        yt, yb = y - 70, y + 70
        on = sing_s - appear                       # onset relative to the main event start
        popt = (f"\\t({ms(on)},{ms(on + 0.07)},\\fscx{f1(pop * 100)}\\fscy{f1(pop * 100)})"
                f"\\t({ms(on + 0.07)},{ms(on + 0.36)},0.8,\\fscx100\\fscy100)")
        pos, ent = _enter_tags(enter, x, y, 0, ed)
        # halo
        E.append(Event(1, appear, exit_at, style,
                       f"{{\\an5{pos}\\bord{f1(halo_bord)}\\shad0\\1a&HFF&\\3c{halo}\\3a&HFF&{ent}"
                       f"\\t(0,{ms(ed)},\\3a&H68&){popt}}}{text}", tag + "halo"))
        # base (unsung)
        E.append(Event(2, appear, exit_at, style,
                       f"{{\\an5{pos}\\bord{f1(bord)}\\shad0\\1c{col(pal['base'])}\\3c{sc}{ent}"
                       f"{_fade_in(0, ed)}{popt}}}{text}", tag + "base"))
        # sung wipe
        dur = max(0.05, sing_e - sing_s)
        popr = (f"\\fscx{f1(pop * 100)}\\fscy{f1(pop * 100)}"
                f"\\t(70,{ms(0.36)},0.8,\\fscx100\\fscy100)")
        if exit_at > sing_s:
            E.append(Event(3, sing_s, exit_at, style,
                           f"{{\\an5\\pos({f1(x)},{f1(y)})\\bord{f1(bord + 0.8)}\\shad0\\blur1.2"
                           f"\\1c{col(sung_col)}\\3c{col(glow_col)}{popr}"
                           f"\\clip({f1(xl)},{f1(yt)},{f1(xl)},{f1(yb)})"
                           f"\\t(0,{ms(dur)},\\clip({f1(xl)},{f1(yt)},{f1(xr)},{f1(yb)})){extra_sung}}}{text}",
                           tag + "sung"))
            # onset flare
            E.append(Event(4, sing_s, min(exit_at, sing_s + 0.6), style,
                           f"{{\\an5\\pos({f1(x)},{f1(y)})\\bord{f1(bord + 3)}\\shad0\\blur7"
                           f"\\1a&HFF&\\3c{col(glow_col)}\\3a&H30&\\fscx{f1(pop * 100)}\\fscy{f1(pop * 100)}"
                           f"\\t(0,{ms(0.55)},0.7,\\3a&HFF&\\fscx{f1(pop * 112)}\\fscy{f1(pop * 112)})}}{text}",
                           tag + "pop"))
        # exit: halo + sung state leave together
        end = exit_at + slot.xd
        st = rnd.getstate()
        ex = exit_tags(exit_kind, x, y, slot.xd, rnd, self.c.line_x0, self.c.line_x1, yt, yb)
        rnd.setstate(st)
        ex_h = exit_tags(exit_kind, x, y, slot.xd, rnd, self.c.line_x0, self.c.line_x1, yt, yb)
        E.append(Event(1, exit_at, end, style,
                       f"{{\\an5\\bord{f1(halo_bord)}\\shad0\\1a&HFF&\\3c{halo}\\3a&H68&{ex_h}}}{text}",
                       tag + "halo-out"))
        E.append(Event(3, exit_at, end, style,
                       f"{{\\an5\\bord{f1(bord + 0.8)}\\shad0\\blur1.2\\1c{col(sung_col)}\\3c{col(glow_col)}{ex}}}{text}",
                       tag + "out"))

    # ---- translation ---------------------------------------------------------------------
    def zh_line(self, line, slot: Slot, pal: dict, enter: str, exit_kind: str, words: list[dict],
                rnd: random.Random) -> None:
        g, E = self.c.geo, self.c.events
        y = g.jp_y + g.zh_gap
        x = g.cx
        text_base = self._zh_markup(line.zh, words, pal["zh"])
        text_sung = self._zh_markup(line.zh, words, pal["zh_sung"], bright=True)
        halo = col(pal["halo"])
        sc = col(pal["outline"])
        appear = slot.tin + 0.12
        ed = 0.55
        w = self.c.zh_w
        x0, x1 = x - w / 2 - 4, x + w / 2 + 4
        yt, yb = y - 40, y + 40
        common = f"\\an5\\pos({f1(x)},{f1(y)})\\shad0"
        ent = f"\\fsp12\\blur5\\t(0,{ms(ed)},0.6,\\fsp2\\blur0.5)"
        E.append(Event(1, appear, slot.tout, "CN",
                       f"{{{common}\\bord6\\1a&HFF&\\3c{halo}\\3a&HFF&{ent}\\t(0,{ms(ed)},\\3a&H70&)}}{line.zh}",
                       f"L{line.idx:02d}:zh-halo"))
        E.append(Event(2, appear, slot.tout, "CN",
                       f"{{{common}\\bord1.6\\3c{sc}\\1c{col(pal['zh'])}{ent}{_fade_in(0, ed)}}}{text_base}",
                       f"L{line.idx:02d}:zh-base"))
        # sung highlight follows the singer, unit by unit, proportionally to glyph count
        n = len(line.units)
        steps = [f"\\clip({f1(x0)},{f1(yt)},{f1(x0)},{f1(yb)})"]
        for k, u in enumerate(line.units):
            xe = x0 + (x1 - x0) * (k + 1) / n
            steps.append(f"\\t({ms(u.s - line.s)},{ms(u.e - line.s)},\\clip({f1(x0)},{f1(yt)},{f1(xe)},{f1(yb)}))")
        E.append(Event(3, line.s, slot.tout, "CN",
                       f"{{{common}\\bord1.6\\blur0.5\\fsp2\\3c{sc}\\1c{col(pal['zh_sung'])}{''.join(steps)}}}"
                       f"{text_sung}", f"L{line.idx:02d}:zh-sung"))
        ex = exit_tags(exit_kind if exit_kind != "shatter" else "rise", x, y, slot.xd, rnd, x0, x1, yt, yb)
        E.append(Event(1, slot.tout, slot.tout + slot.xd, "CN",
                       f"{{\\an5\\shad0\\bord6\\1a&HFF&\\3c{halo}\\3a&H70&\\fsp2{ex}}}{line.zh}", f"L{line.idx:02d}:zh-halo-out"))
        E.append(Event(3, slot.tout, slot.tout + slot.xd, "CN",
                       f"{{\\an5\\shad0\\bord1.6\\fsp2\\3c{sc}\\1c{col(pal['zh_sung'])}{ex}}}{text_sung}",
                       f"L{line.idx:02d}:zh-out"))

    @staticmethod
    def _zh_markup(zh: str, words: list[dict], default: str, bright: bool = False) -> str:
        """colour the translation words that pair with accented japanese words."""
        spans = []
        for w in words:
            z = w.get("zh")
            if not z:
                continue
            start = 0
            while (i := zh.find(z, start)) >= 0:
                spans.append((i, i + len(z), w["color"]))
                start = i + len(z)
        spans.sort()
        out, pos = [], 0
        for a, b, c in spans:
            if a < pos:
                continue
            out.append(zh[pos:a])
            out.append(f"{{\\1c{col(c)}}}{zh[a:b]}{{\\1c{col(default)}}}")
            pos = b
        out.append(zh[pos:])
        return "".join(out)
