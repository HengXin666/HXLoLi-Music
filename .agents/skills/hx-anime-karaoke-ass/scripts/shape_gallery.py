# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""把 assfx.shapes 里的图形平铺渲染成一张图，检查造型（hx-karaoke shape_gallery.py out.png [--ffmpeg ffmpeg]）"""
import os, random, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from assfx import shapes as S
from assfx.core import Doc

R = random.Random(1)
items = [("circle", S.circle(40)), ("ring", S.ring(40, 5)), ("arc", S.arc(40, -150, 60, 6)), ("star5", S.star(5, 42, 18)),
         ("sparkle", S.sparkle(44)), ("streak", S.streak(100, 8)), ("heart", S.heart(46)), ("petal", S.petal(40)),
         ("sakura", S.sakura(44)), ("flower", S.flower(44)), ("leaf", S.leaf(40)), ("maple", S.maple(44)),
         ("teardrop", S.teardrop(44)), ("flame", S.flame(44, 0.2)), ("feather", S.feather(46)), ("snowflake", S.snowflake(42)),
         ("wheat", S.wheat(46)), ("bird", S.bird(44, 0.3)), ("cloud", S.cloud(40)), ("shard", S.shard(R, 40)),
         ("crack", S.crack(R, 110, 5)), ("bolt", S.bolt(R, 100, 7)), ("slash", S.slash(110, 18)), ("sword", S.sword(100)),
         ("chain", S.chain(4, 16)), ("shield", S.shield(42)), ("magic", S.magic_circle(46)), ("rune", S.rune_ring(44)),
         ("heal+", S.healing_cross(36)), ("witch_hat", S.witch_hat(48)), ("book", S.book(48)), ("page", S.page(40)),
         ("candle", S.candle_flame(40)), ("thread", S.thread((-50, 0), (50, 0), 25, 4)), ("ripple", S.ripple(50, 4)),
         ("veil", S.veil(110, 36)), ("gear", S.gear_ring(42)), ("eye", S.eye_ring(48)), ("compass", S.compass(44)),
         # 田园/夏日/羁绊
         ("wing", S.wing(50)), ("wing_pair", S.wing_pair(44, gap=8)), ("rabbit", S.rabbit(46)), ("note", S.music_note(44)),
         ("notes", S.music_note(40, True)), ("violin", S.violin(80)), ("torii", S.torii(80)), ("wheel", S.wheel(42)),
         ("ramune", S.ramune(70)), ("firework", S.firework(18, 44)), ("dandelion", S.dandelion(48)), ("big_cloud", S.big_cloud(60)),
         ("sunflower", S.sunflower(44)), ("curtain", S.curtain(70, 80, sway=0.3)), ("lantern", S.lantern(56)), ("window", S.window_frame(90, 64)),
         ("raindrop", S.raindrop(50)),
         # 运动会/部落/元气
         ("tipi", S.tipi(70)), ("cactus", S.cactus(76)), ("gong", S.gong(72)), ("hurdle", S.hurdle(76)), ("vault_box", S.vault_box(74)),
         ("bread", S.bread(64)), ("bunting", "".join(d for d, _ in S.bunting(120, 5))), ("comic_burst", S.comic_burst(46, rng=R)),
         ("arrow", S.arrow(100, 2.5)), ("medal", S.medal(64)), ("door", S.door(76)), ("umbrella", S.umbrella(66)),
         ("bookmark", S.bookmark(60)), ("puff", S.puff(56)), ("pepper", S.pepper(60))]
d = Doc("gallery")
d.add_style("LB", "Arial", 18)
cols = 10
for i, (n, dr) in enumerate(items):
    x = 100 + (i % cols) * 190; y = 70 + (i // cols) * 150
    d.ev(1, 0, 5, f"{{\\an5\\pos({x},{y})\\bord0\\shad0\\1c&HF0E8FF&\\fscx85\\fscy85\\p1}}{S.norm(dr)}{{\\p0}}")
    d.ev(1, 0, 5, f"{{\\an5\\pos({x},{y+58})\\bord0\\1c&H80C0FF&}}{n}", "LB")
tmp = tempfile.mkdtemp(); p = os.path.join(tmp, "g.ass"); d.write(p)
ff = sys.argv[sys.argv.index("--ffmpeg") + 1] if "--ffmpeg" in sys.argv else "ffmpeg"
subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "color=0x202838:s=1920x1080:d=1", "-vf", f"subtitles={p}",
                "-frames:v", "1", sys.argv[1]], check=True)
print("saved", sys.argv[1])
