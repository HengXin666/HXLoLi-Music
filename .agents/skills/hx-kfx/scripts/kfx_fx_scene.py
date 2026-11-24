"""Particles that answer the MV's weather, and the few named moments of the song.

Particles: born at a syllable onset next to its glyph (they belong to the voice),
plus optional slow ambient pieces behind the text (they belong to the scene).
All end points are clamped to the lyric band so nothing wanders into the picture.
"""
from __future__ import annotations

import math
import random

import kfx_shapes as shapes
from kfx_assw import Event, alpha, col, f1, mix, ms

BAND_TOP, BAND_BOT = 690.0, 1010.0


def _clamp(v, a, b):
    return max(a, min(b, v))


class SceneFx:
    def __init__(self, ctx):
        self.c = ctx

    # ---- particles ------------------------------------------------------------------------
    def _piece(self, layer, t0, life, x, y, flow, motif, size, color, rnd, a_peak=0x10, blur=0.8):
        g = self.c
        if flow == "fall":
            ex, ey = x + rnd.uniform(-50, 50), y + rnd.uniform(60, 130)
        elif flow == "rise":
            ex, ey = x + rnd.uniform(-35, 35), y - rnd.uniform(60, 130)
        elif flow == "wind":
            ex, ey = x + rnd.uniform(110, 230), y + rnd.uniform(-40, 25)
        else:  # burst
            a = rnd.uniform(0, 2 * math.pi)
            d = rnd.uniform(40, 95)
            ex, ey = x + d * math.cos(a), y + d * math.sin(a) * 0.7
        ex = _clamp(ex, g.line_x0 - 160, g.line_x1 + 160)
        ey = _clamp(ey, BAND_TOP, BAND_BOT)
        rot0 = rnd.uniform(0, 360)
        spin = rnd.uniform(-220, 220) if motif not in ("mote", "droplet", "ember") else 0
        path = shapes.MOTIFS[motif](size, rnd.randint(0, 9999))
        L = ms(life)
        fin = min(160, L // 4)
        accel = 1.0 if flow != "burst" else 0.5
        sway = f"\\fry{f1(rnd.uniform(-60, 60))}\\t(0,{L},\\fry{f1(rnd.uniform(-180, 180))})" \
            if motif in ("leaf", "petal", "snow") else ""
        g.events.append(Event(
            layer, t0, t0 + life, "FX",
            f"{{\\an5\\move({f1(x)},{f1(y)},{f1(ex)},{f1(ey)})\\bord0\\shad0\\blur{f1(blur)}"
            f"\\1c{col(color)}\\frz{f1(rot0)}{sway}\\alpha&HFF&"
            f"\\t(0,{fin},\\alpha{alpha(a_peak)})\\t({L - L // 2},{L},{f1(accel)},\\alpha&HFF&)"
            f"\\t(0,{L},\\frz{f1(rot0 + spin)})\\p1}}{path}", "fx-particle"))

    def onset_particles(self, line, sec, rnd: random.Random):
        p = sec.particles
        if p.per_unit <= 0:
            return
        colors = p.colors or [sec.palette["glow"]]
        # density compensation: fast syllables get fewer pieces, held notes get more
        for u in line.units:
            d = u.e - u.s
            n = p.per_unit * _clamp(d / 0.3, 0.5, 2.2)
            k = int(n) + (1 if rnd.random() < n - int(n) else 0)
            for _ in range(k):
                x = u.x + rnd.uniform(-u.w / 2, u.w / 2)
                y = self.c.geo.jp_y + rnd.uniform(-34, 30)
                self._piece(5, u.s + rnd.uniform(0, min(0.2, d)), rnd.uniform(0.9, 1.6), x, y, p.flow,
                            p.motif, rnd.uniform(*p.size), rnd.choice(colors), rnd)

    def ambient(self, line, sec, slot, rnd: random.Random):
        p = sec.particles
        if p.ambient <= 0:
            return
        colors = p.colors or [sec.palette["glow"]]
        span = slot.tout - slot.tin
        for _ in range(int(p.ambient * span)):
            t0 = slot.tin + rnd.uniform(0, max(0.1, span - 1.0))
            x = rnd.uniform(self.c.line_x0 - 140, self.c.line_x1 + 140)
            y = rnd.uniform(BAND_TOP + 10, BAND_BOT - 40) if p.flow != "rise" else rnd.uniform(900, BAND_BOT)
            if p.flow == "fall":
                y = rnd.uniform(BAND_TOP, 820)
            self._piece(0, t0, rnd.uniform(2.4, 3.6), x, y, p.flow, p.motif,
                        rnd.uniform(*p.size) * 0.8, rnd.choice(colors), rnd, a_peak=0x70, blur=1.6)

    # ---- named moments ------------------------------------------------------------------------
    def moment(self, m, line, sec, slot, rnd: random.Random):
        getattr(self, "_m_" + m.kind)(m, line, sec, slot, rnd)

    def _units(self, m, line):
        return [line.units[i] for i in m.units] if m.units else line.units

    def _m_cracks(self, m, line, sec, slot, rnd):
        """壊: the screen-glass cracks behind the glyph on the onset, then the line shatters."""
        c = m.color or sec.palette["glow"]
        y = self.c.geo.jp_y
        for u in self._units(m, line):
            for side in (-1, 1):
                path, w, h = shapes.crack(rnd.uniform(150, 230), rnd.randint(0, 999))
                cx = u.x + side * w / 2
                x0 = u.x if side > 0 else u.x - w
                reveal = (f"\\clip({f1(u.x)},{f1(y - 60)},{f1(u.x)},{f1(y + 60)})"
                          f"\\t(0,140,\\clip({f1(x0)},{f1(y - 60)},{f1(x0 + w)},{f1(y + 60)}))")
                if side < 0:
                    reveal = (f"\\clip({f1(u.x)},{f1(y - 60)},{f1(u.x)},{f1(y + 60)})"
                              f"\\t(0,140,\\clip({f1(x0)},{f1(y - 60)},{f1(u.x)},{f1(y + 60)}))")
                rot = rnd.uniform(-14, 14) + (180 if side < 0 else 0)
                life = slot.tout + slot.xd - u.s
                for blur, a, bord in ((5, 0x40, 0), (0.6, 0x00, 0)):
                    self.c.events.append(Event(
                        0, u.s, u.s + life, "FX",
                        f"{{\\an5\\pos({f1(cx)},{f1(y + rnd.uniform(-8, 8))})\\bord{bord}\\shad0\\blur{blur}"
                        f"\\1c{col(c if blur > 1 else mix(c, '#FFFFFF', 0.45))}\\alpha{alpha(a)}{reveal}"
                        f"\\frz{f1(rot if side > 0 else rot - 180)}"
                        f"\\t({ms(life - slot.xd)},{ms(life)},\\alpha&HFF&)\\p1}}{path}", "fx-crack"))
            # white impact flash + shards
            self.c.events.append(Event(
                4, u.s, u.s + 0.32, "FX",
                f"{{\\an5\\pos({f1(u.x)},{f1(y)})\\bord0\\shad0\\blur3\\1c&HFFFFFF&\\alpha&H20&"
                f"\\fscx40\\fscy40\\t(0,320,0.6,\\fscx220\\fscy220\\alpha&HFF&)\\p1}}{shapes.sparkle(26)}",
                "fx-impact"))
            for _ in range(6):
                self._piece(5, u.s, rnd.uniform(0.6, 1.0), u.x, y, "burst", "shard",
                            rnd.uniform(5, 10), rnd.choice([c, "#FFFFFF"]), rnd)

    def _m_magic_circle(self, m, line, sec, slot, rnd):
        """守: Roxy's water-magic circle on the ground under the line, slowly turning."""
        c = m.color or sec.palette["glow"]
        r = _clamp((self.c.line_x1 - self.c.line_x0) * 0.32, 150, 190)
        path = shapes.ring(r, 2.6, 36, 12)
        inner = shapes.ring(r * 0.55, 2.0, 18, 8, 0.7)
        t0, t1 = slot.tin, slot.tout + slot.xd
        L = ms(t1 - t0)
        # libass perspective pushes a tilted disc's visual centre down by ~0.42 r: compensate
        y = self.c.geo.jp_y + 30 - 0.42 * r
        for p, rr, spin, a in ((path, r, 40, 0x58), (inner, r * 0.55, -70, 0x70)):
            for blur, aa in ((6, a - 0x18), (0.7, a)):
                self.c.events.append(Event(
                    0, t0, t1, "FX",
                    f"{{\\an5\\pos({f1(self.c.geo.cx)},{f1(y)})\\org({f1(self.c.geo.cx)},{f1(y)})"
                    f"\\bord0\\shad0\\blur{blur}\\1c{col(c)}\\frx66\\frz0\\alpha&HFF&"
                    f"\\fscx60\\fscy60\\t(0,700,0.5,\\alpha{alpha(aa)}\\fscx100\\fscy100)"
                    f"\\t(0,{L},\\frz{spin})\\t({L - ms(slot.xd) - 200},{L},\\alpha&HFF&)\\p1}}{p}",
                    "fx-circle"))

    def _m_red_thread(self, m, line, sec, slot, rnd):
        """貴方: the one red string tying the whole song together, drawn as she sings."""
        c = m.color or "#E2384A"
        g = self.c.geo
        w = self.c.line_x1 - self.c.line_x0 + 360
        path, pw, ph = shapes.thread(w, 5, 1.5, 1.5)
        x0 = g.cx - w / 2
        y = g.jp_y + g.zh_gap * 0.5 + 2
        s, e = line.s, line.e
        t1 = slot.tout + slot.xd
        for blur, a in ((5, 0x50), (0.5, 0x00)):
            self.c.events.append(Event(
                0, s, t1, "FX",
                f"{{\\an5\\pos({f1(g.cx)},{f1(y)})\\bord0\\shad0\\blur{blur}\\1c{col(c)}\\alpha{alpha(a)}"
                f"\\clip({f1(x0)},{f1(y - 40)},{f1(x0)},{f1(y + 40)})"
                f"\\t(0,{ms(e - s + 0.4)},0.8,\\clip({f1(x0)},{f1(y - 40)},{f1(x0 + w)},{f1(y + 40)}))"
                f"\\t({ms(t1 - s - slot.xd)},{ms(t1 - s)},\\alpha&HFF&)\\p1}}{path}", "fx-thread"))

    def _m_rays(self, m, line, sec, slot, rnd):
        """sunlight through the sky shots: soft shafts falling onto the line."""
        c = m.color or sec.palette["glow"]
        t0, t1 = slot.tin, slot.tout + slot.xd
        L = ms(t1 - t0)
        for i in range(5):
            path, w, h = shapes.ray(rnd.uniform(380, 520), 8, rnd.uniform(60, 120))
            x = self.c.line_x0 + (self.c.line_x1 - self.c.line_x0) * (i + 0.5) / 5 + rnd.uniform(-40, 40)
            a0 = rnd.uniform(-22, -10)
            self.c.events.append(Event(
                0, t0, t1, "FX",
                f"{{\\an8\\pos({f1(x)},{f1(BAND_TOP - 20)})\\bord0\\shad0\\blur14\\1c{col(c)}"
                f"\\frz{f1(a0)}\\alpha&HFF&\\t(0,900,\\alpha&HB4&)\\t(0,{L},\\frz{f1(a0 + rnd.uniform(4, 9))})"
                f"\\t({L - 700},{L},\\alpha&HFF&)\\p1}}{path}", "fx-ray"))

    def _m_flip(self, m, line, sec, slot, rnd):
        """裏側: the glyph turns over to show its back side while sung (sung layer gets \\fry)."""
        for u in self._units(m, line):
            self.c.sung_extra[id(u)] = f"\\t(0,{ms(max(0.5, u.e - u.s))},0.7,\\fry360)"

    def _m_tilt(self, m, line, sec, slot, rnd):
        """？: the question hangs; the last glyph leans like a head tilting."""
        for u in self._units(m, line):
            self.c.sung_extra[id(u)] = f"\\t(0,420,0.5,\\frz-9)\\t(900,1500,\\frz0)"

    def _m_tear(self, m, line, sec, slot, rnd):
        """涙: three drops leave the glyph after it is sung."""
        c = m.color or "#BFE6FF"
        for u in self._units(m, line):
            for i in range(3):
                t0 = u.e + i * 0.28
                x = u.x + rnd.uniform(-u.w * 0.3, u.w * 0.3)
                y = self.c.geo.jp_y + 30
                self.c.events.append(Event(
                    5, t0, t0 + 1.1, "FX",
                    f"{{\\an5\\move({f1(x)},{f1(y)},{f1(x)},{f1(y + 110)},0,1100)\\bord0\\shad0\\blur0.8"
                    f"\\1c{col(c)}\\alpha&H20&\\fscx60\\fscy60\\t(0,200,\\fscx100\\fscy100)"
                    f"\\t(700,1100,\\alpha&HFF&)\\p1}}{shapes.droplet(7)}", "fx-tear"))

    def _m_veil(self, m, line, sec, slot, rnd):
        """隠: a mist curtain passes over the line once it has been sung."""
        c = m.color or sec.palette["halo"]
        g = self.c.geo
        w = self.c.line_x1 - self.c.line_x0 + 200
        t0 = line.s + (line.e - line.s) * 0.45
        t1 = slot.tout + slot.xd
        L = ms(t1 - t0)
        self.c.events.append(Event(
            6, t0, t1, "FX",
            f"{{\\an5\\move({f1(self.c.line_x0 - 400)},{f1(g.jp_y)},{f1(self.c.line_x1 + 400)},{f1(g.jp_y)})"
            f"\\bord0\\shad0\\blur30\\1c{col(c)}\\alpha&HFF&\\t(0,600,\\alpha&HA0&)"
            f"\\t({L - 500},{L},\\alpha&HFF&)\\p1}}{shapes.rect(w * 0.45, 120)}", "fx-veil"))

    def _m_whiteout(self, m, line, sec, slot, rnd):
        """the final white: a soft bloom behind the last line, like the MV's white frame."""
        c = m.color or "#FFFFFF"
        g = self.c.geo
        t0, t1 = line.s, slot.tout + slot.xd
        L = ms(t1 - t0)
        self.c.events.append(Event(
            0, t0, t1, "FX",
            f"{{\\an5\\pos({f1(g.cx)},{f1(g.jp_y + 20)})\\bord0\\shad0\\blur40\\1c{col(c)}\\alpha&HFF&"
            f"\\fscx40\\fscy40\\t(0,{ms(line.e - line.s)},0.6,\\alpha&HC8&\\fscx100\\fscy100)"
            f"\\t({L - 1200},{L},\\alpha&HFF&)\\p1}}{shapes.circle(260)}", "fx-bloom"))
