# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow"]
# ///
"""still 对照: 原版与本产物的同刻帧并排 + 分区读数.

用法:
  hx-karaoke still_compare.py --ref review/still/ref --new review/still/new --out review/still/cmp
  hx-karaoke still_compare.py ... --bands "disc:935:1040:560:1360,ruby:898:972:560:1360"
  hx-karaoke still_compare.py ... --bbox

判据见 steps/5-verify/14-inspect/impl/still-compare.md。
两边的 --times 必须相同, 否则比的是不同时刻。
"""
import argparse
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def split_by_draw(src, outdir):
    r"""按"是否绘图"拆成两份：draw（含 \pN 且 N>0）与 text（其余）。

    为什么不能按 Name 分层：对照用的成品往往不用本项目的 `fx:`/`ly:` 约定
    （实测某成品 Name 是角色名 chino/maya/空），按 Name 拆会把它的全部事件
    归到一侧，于是"装饰 vs 文字"的对比完全失真。

    **`\p` 是 ASS 本身的事实**，两边都成立：绘图事件用 `\pN`（N>0）进入绘图模式，
    文字事件不用或显式 `\p0` 关掉。按它分层，任何两份 ASS 都可比。

    返回 (draw_ass, text_ass) 路径。
    """
    os.makedirs(outdir, exist_ok=True)
    head, draw, text = [], [], []
    seen_events = False
    # 事件文本里可能出现多个 {\\...} 块；只要其中任一块把绘图模式打开过就算绘图
    for line in open(src, encoding="utf-8-sig", errors="replace"):
        s = line.rstrip("\n")
        if s.startswith("[Events]"):
            seen_events = True
            head.append(s)
            continue
        if not seen_events or not s.startswith(("Dialogue:", "Comment:")):
            head.append(s)
            continue
        f = s.split(",", 9)
        if len(f) < 10:
            head.append(s)
            continue
        body = f[9]
        is_draw = False
        for blk in re.findall(r"\{([^}]*)\}", body):
            for m in re.finditer(r"\\p(\d+)", blk):
                if int(m.group(1)) > 0:
                    is_draw = True
        (draw if is_draw else text).append(s)
    out = []
    for tag, rows in (("draw", draw), ("text", text)):
        p = os.path.join(outdir, f"_{tag}.ass")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("\n".join(head) + "\n" + "\n".join(rows) + "\n")
        out.append(p)
    return out[0], out[1]


def split_ass(src, outdir):
    r"""按事件 Name 前缀把一份 ASS 拆成两份：只留 fx: 与只留 ly:/其他。

    **只适用于本项目自产的 ASS**：Name 用 fx:/ly:/card: 三分是 core.py 的约定。
    对照用的成品往往不用这套（实测某成品 Name 是角色名 chino/maya/megu 或空），
    对它分层会把全部事件归进 ly，读数因此失真  那种情况改成按 Style 分层。

    为什么需要它：直接按 y 带统计会被跨层污染。实测（2026-10-06）一份产物的
    "注音带"里 92.7~98.4% 的墨迹其实来自 FX 层（盘画到了 y926），于是报出
    "注音 2.49 倍"这个**反向结论**  真相是注音偏少。分层之后再量，读数才对应到层。

    返回 (fx_ass, ly_ass) 路径。
    """
    os.makedirs(outdir, exist_ok=True)
    head, fx, ly = [], [], []
    seen_events = False
    for line in open(src, encoding="utf-8-sig", errors="replace"):
        s = line.rstrip("\n")
        if s.startswith("[Events]"):
            seen_events = True
            head.append(s)
            continue
        if not seen_events or not s.startswith(("Dialogue:", "Comment:")):
            head.append(s)
            continue
        f = s.split(",", 9)
        if len(f) < 10:
            head.append(s)
            continue
        name = f[4]
        (fx if name.startswith("fx:") else ly).append(s)
    out = []
    for tag, rows in (("fx", fx), ("ly", ly)):
        p = os.path.join(outdir, f"_{tag}.ass")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("\n".join(head) + "\n")
            fh.write("\n".join(rows) + "\n")
        out.append(p)
    return out[0], out[1]


def load(path):
    return np.asarray(Image.open(path).convert("L")).astype(np.int16)


def bbox(im, thr):
    m = im > thr
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def region(im, spec):
    """spec = (y0, y1, x0, x1)"""
    y0, y1, x0, x1 = spec
    return im[y0:y1, x0:x1]


def parse_bands(s, h, w):
    if not s:
        return {"all": (0, h, 0, w)}
    out = {}
    for item in s.split(","):
        name, spec = item.split(":", 1)
        out[name] = tuple(int(v) for v in spec.split(":"))
    return out


def load_font(size=34):
    for cand in (
        os.environ.get("ASSFX_FONTS", ""),
        os.path.expanduser("~/.local/share/fonts"),
        "/usr/share/fonts",
    ):
        if not cand or not os.path.isdir(cand):
            continue
        for f in sorted(os.listdir(cand)):
            if f.lower().endswith((".ttf", ".otf", ".ttc")):
                try:
                    return ImageFont.truetype(os.path.join(cand, f), size)
                except Exception:
                    continue
    return ImageFont.load_default()


def _render(ass, times, outdir, fontsdir):
    """调 render_octopus.py 渲一组时刻；返回落盘的 PNG 数。"""
    import subprocess
    cmd = ["hx-karaoke", "render_octopus.py", ass, "--times", times, "--out", outdir]
    if fontsdir:
        cmd += ["--fontsdir", fontsdir]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[split] 渲染失败 {ass}: {(r.stderr or r.stdout).strip().splitlines()[-1:] }")
        return 0
    return len([f for f in os.listdir(outdir) if f.endswith(".png")])


def split_report(a):
    """分层读数：把两侧各拆成 fx 层与 ly 层，各渲一遍、各量一次。

    这样"某层的墨迹量"不会被另一层污染；直接按 y 带切会把装饰算进注音带。
    """
    if not (a.ref_ass and a.new_ass):
        sys.exit("--split 需要同时给 --ref-ass 与 --new-ass")
    refs = sorted(f for f in os.listdir(a.ref) if f.endswith(".png"))
    if not refs:
        sys.exit("--ref 目录里没有 PNG")
    times = ",".join(f[:-4] for f in refs)
    base = a.split
    out = {}
    for side, ass in (("ref", a.ref_ass), ("new", a.new_ass)):
        # 按 \p 有无分层（ASS 本身的事实, 两边同口径）; --split-by-name 才用 Name 约定
        splitter = split_ass if a.split_by_name else split_by_draw
        fx_ass, ly_ass = splitter(ass, os.path.join(base, f"_{side}"))
        for layer, p in (("draw", fx_ass), ("text", ly_ass)):
            d = os.path.join(base, f"{side}_{layer}")
            n = _render(p, times, d, a.fontsdir)
            out[(side, layer)] = d
            print(f"[split] {side}/{layer}: {n} 帧 -> {d}")

    im0 = load(os.path.join(out[("ref", "draw")], refs[0])) if os.path.isdir(out[("ref", "draw")]) else None
    bands = parse_bands(a.bands, im0.shape[0] if im0 is not None else 1080,
                        im0.shape[1] if im0 is not None else 1920)
    print()
    print("分层分区读数（ref -> new，比值）")
    bad = 0
    for layer in ("draw", "text"):
        for k, sp in bands.items():
            ra = rb = 0
            for f in refs:
                pa, pb = os.path.join(out[("ref", layer)], f), os.path.join(out[("new", layer)], f)
                if os.path.exists(pa):
                    ra += int((region(load(pa), sp) > a.thr).sum())
                if os.path.exists(pb):
                    rb += int((region(load(pb), sp) > a.thr).sum())
            r = rb / max(ra, 1)
            ok = 1 / a.ratio <= r <= a.ratio
            bad += not ok
            print(f"  {layer:>3} {k:>8}: ref={ra:>9d} new={rb:>9d} 比={r:5.3f} {'OK' if ok else 'FAIL'}")
    return 0 if bad == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="原版帧目录")
    ap.add_argument("--new", required=True, help="本产物帧目录")
    ap.add_argument("--out", help="并排图输出目录")
    ap.add_argument("--bands", default="", help='分区: "名:y0:y1:x0:x1,名2:..."')
    ap.add_argument("--bbox", action="store_true", help="只打印包围盒对照")
    ap.add_argument("--crop", default="", help="并排前裁剪 x0,y0,x1,y1")
    ap.add_argument("--label", default="ORIGINAL")
    ap.add_argument("--label2", default="MINE")
    ap.add_argument("--thr", type=int, default=28, help="非背景阈值")
    ap.add_argument("--ratio", type=float, default=1.15, help="分区比值上限")
    ap.add_argument("--ref-ass", default="", help="原版 ASS（--split 时需要）")
    ap.add_argument("--new-ass", default="", help="本产物 ASS（--split 时需要）")
    ap.add_argument("--fontsdir", default="", help="分层渲染用的字体目录（缺省用 hx-karaoke --fonts）")
    ap.add_argument("--split-by-name", action="store_true",
                    help="分层用 Name 前缀 fx:/ly:（本项目自产 ASS 才行；对照成品往往没有该约定）")
    ap.add_argument("--split", default="", metavar="OUTDIR",
                    help="按 Name 前缀分层后再量: 把 --ref/--new 各自拆成 fx 层与 ly 层, "
                         "分别渲染到 OUTDIR, 再报每层的分区读数. 消除跨层污染(见 split_ass 说明).")
    a = ap.parse_args()

    ref = sorted(f for f in os.listdir(a.ref) if f.endswith(".png"))
    new = sorted(f for f in os.listdir(a.new) if f.endswith(".png"))
    if not ref or not new:
        sys.exit("两侧都要有 PNG 帧")
    if len(ref) != len(new):
        print(f"[warn] 帧数不等 ref={len(ref)} new={len(new)}, 只比前 {min(len(ref), len(new))} 帧")
    n = min(len(ref), len(new))

    if a.split:
        return split_report(a)

    im0 = load(os.path.join(a.ref, ref[0]))
    bands = parse_bands(a.bands, im0.shape[0], im0.shape[1])

    if a.bbox:
        print(f"{'frame':>12} | {'ref bbox':>26} | {'new bbox':>26} | d")
        bad = 0
        for i in range(n):
            A = load(os.path.join(a.ref, ref[i]))
            B = load(os.path.join(a.new, new[i]))
            ba, bb = bbox(A, a.thr), bbox(B, a.thr)
            if ba is None or bb is None:
                print(f"{ref[i]:>12} | {str(ba):>26} | {str(bb):>26} | -")
                continue
            d = max(abs(ba[k] - bb[k]) for k in range(4))
            flag = "" if d <= 2 else "  <-- 几何基准不同"
            bad += d > 2
            print(f"{ref[i]:>12} | {str(ba):>26} | {str(bb):>26} | {d}{flag}")
        print(f"\n包围盒偏差 >2px 的帧: {bad}/{n}")
        return 0 if bad == 0 else 1

    print(f"{'frame':>12} | " + " | ".join(f"{k:>18}" for k in bands))
    fails = 0
    totals = {k: [0, 0] for k in bands}
    for i in range(n):
        A = load(os.path.join(a.ref, ref[i]))
        B = load(os.path.join(a.new, new[i]))
        cells = []
        for k, sp in bands.items():
            ra = int((region(A, sp) > a.thr).sum())
            rb = int((region(B, sp) > a.thr).sum())
            totals[k][0] += ra
            totals[k][1] += rb
            r = rb / max(ra, 1)
            mark = "" if 1 / a.ratio <= r <= a.ratio else " !"
            if mark:
                fails += 1
            cells.append(f"{ra:>7d}->{rb:>7d} {r:4.2f}{mark}")
        print(f"{ref[i]:>12} | " + " | ".join(cells))
    print()
    for k, (ra, rb) in totals.items():
        r = rb / max(ra, 1)
        ok = 1 / a.ratio <= r <= a.ratio
        print(f"  {k:>8}: ref={ra:>9d} new={rb:>9d} 比={r:5.3f} {'OK' if ok else 'FAIL'}")

    if a.out:
        os.makedirs(a.out, exist_ok=True)
        f = load_font()
        crop = tuple(int(v) for v in a.crop.split(",")) if a.crop else None
        for i in range(n):
            A = Image.open(os.path.join(a.ref, ref[i])).convert("RGB")
            B = Image.open(os.path.join(a.new, new[i])).convert("RGB")
            if crop:
                A, B = A.crop(crop), B.crop(crop)
            W, H = A.size
            o = Image.new("RGB", (W * 2 + 8, H + 52), (10, 10, 14))
            o.paste(A, (0, 52))
            o.paste(B, (W + 8, 52))
            d = ImageDraw.Draw(o)
            d.text((6, 10), f"{a.label}  {ref[i]}", fill=(255, 215, 110), font=f)
            d.text((W + 14, 10), f"{a.label2}  {new[i]}", fill=(120, 240, 200), font=f)
            d.line([(W + 4, 0), (W + 4, H + 52)], fill=(90, 90, 100), width=2)
            o.save(os.path.join(a.out, f"{i:03d}.png"))
        print(f"\n并排图 {n} 张 -> {a.out}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())



