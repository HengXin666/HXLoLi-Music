"""Minimal ASS writer: colours, times, styles, events."""
from __future__ import annotations

from dataclasses import dataclass


def t_ass(sec: float) -> str:
    cs = max(0, int(round(sec * 100)))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def col(hexrgb: str) -> str:
    """'#RRGGBB' -> '&HBBGGRR&'"""
    h = hexrgb.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"bad colour {hexrgb!r}")
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def alpha(a: int) -> str:
    return f"&H{max(0, min(255, int(a))):02X}&"


def mix(c1: str, c2: str, k: float) -> str:
    a = [int(c1.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * k):02X}" for x, y in zip(a, b))


def ms(x: float) -> int:
    return int(round(x * 1000))


def f1(x: float) -> str:
    s = f"{x:.1f}"
    return s[:-2] if s.endswith(".0") else s


@dataclass
class Event:
    layer: int
    start: float
    end: float
    style: str
    text: str
    name: str = ""

    def line(self) -> str:
        return (f"Dialogue: {self.layer},{t_ass(self.start)},{t_ass(self.end)},{self.style},"
                f"{self.name},0,0,0,,{self.text}")


STYLE_FMT = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
             "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
             "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")


def style(name: str, font: str, fs: float, bold=False, italic=False, spacing=0.0) -> str:
    return (f"Style: {name},{font},{f1(fs)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
            f"{-1 if bold else 0},{-1 if italic else 0},0,0,100,100,{f1(spacing)},0,1,0,0,5,0,0,0,1")


def document(title: str, styles: list[str], events: list[Event], comments: list[str]) -> str:
    events = sorted(events, key=lambda e: (e.start, e.layer))
    out = ["[Script Info]", f"Title: {title}", "ScriptType: v4.00+", "WrapStyle: 2",
           "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "PlayResX: 1920",
           "PlayResY: 1080"]
    out += [f"; {c}" for c in comments]
    out += ["", "[V4+ Styles]", STYLE_FMT, *styles, "", "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    out += [e.line() for e in events if e.end - e.start >= 0.01]
    return "\ufeff" + "\n".join(out) + "\n"
