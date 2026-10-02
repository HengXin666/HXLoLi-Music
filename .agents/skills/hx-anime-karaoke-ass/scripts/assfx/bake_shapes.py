# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "scikit-image", "cairosvg"]
# ///

r"""把网络图标渲染成**实心**ASS 绘图路径并缓存。

为什么必须走"位图 → 加粗 → 取轮廓"这一步（实测 2026-10-02）：
  MDI/Bootstrap 图标是**线稿**，直接喂给 assfx.svg2ass 得到的是细线折线，
  \p1 填充后只有一条 1~2px 的线 —— 实测本工程 2831 个绘图事件里墨迹宽中位 **5px**，
  整帧看上去"什么都没画"。用户的原话是"我没有看到任何的特效"。

  做法：cairosvg 把 SVG 栅格化 → alpha 阈值 → 形态学膨胀（细线变实心）→ 填洞
  → 取轮廓 → 多边形简化 → ASS 坐标。全程自动化，图形仍然是**网络真实素材**的形状，
  没有一处是我手画的。

产物：**写进调用者指定的工程目录**，不是 skill 目录。
    hx-karaoke bake_shapes.py --out proj/assets/shapes.json [--video proj/base.mp4]
没有 --out 时只烧网络图标、不碰 MV 帧（也就不会去猜某份 base.mp4 在哪）。
"""
import argparse
import io, json, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import measure
import cairosvg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from assfx.props import ICONS

SIZE = 256          # 栅格化边长
CANON = 200.0       # 输出坐标的规范尺寸（make_ass 用 \fscx 缩放）

# MV 帧抠图：**必须由 --video 指定**。坐标是"某个工程某一帧"的事实，
# 换一份片源就不成立 —— 所以它只能跟着工程走，不能写死在 skill 里。
MV_CROPS = {
    "mv_eye":    (24.5, (600, 340, 660, 660), "reddeep"),   # 巨眼虹膜
    "mv_eye2":   (137.0, (250, 150, 700, 600), "reddeep"),  # 延珠红眼
    "mv_white":  (89.0, (700, 100, 1500, 700), "white"),    # 巨石碑/白花
    "mv_flame":  (110.0, (700, 500, 1300, 950), "warm"),    # 火光
}


def icon_path(url, thick=2, tol=1.2):
    png = cairosvg.svg2png(url=url, output_width=SIZE, output_height=SIZE)
    im = np.array(Image.open(io.BytesIO(png)).convert("RGBA"))
    m = im[:, :, 3] > 96
    if not m.any():
        return None
    m = ndimage.binary_dilation(m, iterations=thick)
    m = ndimage.binary_closing(m, iterations=2)
    m = ndimage.binary_fill_holes(m)
    lab, k = ndimage.label(m)
    if k == 0:
        return None
    sizes = ndimage.sum(m, lab, range(1, k + 1))
    keep = [i + 1 for i, s in enumerate(sizes) if s > m.size * 0.0015]
    parts, xs_all, ys_all = [], [], []
    for i in keep:
        sub = (lab == i)
        for c in measure.find_contours(sub.astype(float), 0.5):
            ap = measure.approximate_polygon(c, tolerance=tol)
            if len(ap) < 4:
                continue
            ys, xs = ap[:, 0], ap[:, 1]
            parts.append((xs, ys))
            xs_all += list(xs); ys_all += list(ys)
    if not parts:
        return None
    cx, cy = (min(xs_all) + max(xs_all)) / 2, (min(ys_all) + max(ys_all)) / 2
    span = max(max(xs_all) - min(xs_all), max(ys_all) - min(ys_all), 1)
    k2 = CANON / span
    out = []
    for xs, ys in parts:
        pts = [((x - cx) * k2, -(y - cy) * k2) for x, y in zip(xs, ys)]
        # **必须逐点带 l**：libass 的 \p1 里 `m x y a b c d` 会被解释成
        # 「m(0,0) 是起点，之后每个点对都是一条新的单点路径」→ 填充面积为 0，图形退化成 1px 点。
        # 实测（最小复现）：手写 `m 0 0 l 200 0 l 200 200 l 0 200` 是实心正方形，
        # 而我原来的 `m 0 0 200 0 200 200 0 200` 什么都不显示。
        seq = "m %.1f %.1f" % pts[0] + "".join(" l %.1f %.1f" % p for p in pts[1:])
        out.append(seq + " l %.1f %.1f" % pts[0])
    return " ".join(out)


def mv_shape(video, t, box, cond, thick=2, tol=1.2):
    """从 MV 某一帧抠出颜色/亮度条件命中的区域，做成实心路径。"""
    import subprocess, tempfile
    o = tempfile.mktemp(suffix=".png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", video,
                    "-frames:v", "1", "-vf", "crop=%d:%d:%d:%d,scale=%d:%d" % (*box, SIZE, SIZE), o], check=True)
    im = np.array(Image.open(o).convert("RGB")).astype(np.int32)
    m = cond(im)
    if m.sum() < 200:
        return None
    m = ndimage.binary_dilation(m, iterations=thick)
    m = ndimage.binary_closing(m, iterations=3)
    m = ndimage.binary_fill_holes(m)
    lab, k = ndimage.label(m)
    sizes = ndimage.sum(m, lab, range(1, k + 1))
    keep = [i + 1 for i, s in enumerate(sizes) if s > m.size * 0.004]
    parts, xs_all, ys_all = [], [], []
    for i in keep:
        for c in measure.find_contours((lab == i).astype(float), 0.5):
            ap = measure.approximate_polygon(c, tolerance=tol)
            if len(ap) < 4: continue
            ys, xs = ap[:, 0], ap[:, 1]
            parts.append((xs, ys)); xs_all += list(xs); ys_all += list(ys)
    if not parts: return None
    cx, cy = (min(xs_all)+max(xs_all))/2, (min(ys_all)+max(ys_all))/2
    span = max(max(xs_all)-min(xs_all), max(ys_all)-min(ys_all), 1)
    k2 = CANON / span
    out = []
    for xs, ys in parts:
        pts = [((x-cx)*k2, -(y-cy)*k2) for x, y in zip(xs, ys)]
        seq = "m %.1f %.1f" % pts[0] + "".join(" l %.1f %.1f" % p for p in pts[1:])   # 逐点带 l，理由同上
        out.append(seq + " l %.1f %.1f" % pts[0])
    return " ".join(out)


def _conds():
    def red(im):
        r, g, b = im[:, :, 0], im[:, :, 1], im[:, :, 2]
        return (r - np.maximum(g, b)) > 45
    def reddeep(im):        # 深红（红眼虹膜）
        r, g, b = im[:, :, 0], im[:, :, 1], im[:, :, 2]
        return (r > 110) & (r - np.maximum(g, b) > 70)
    def white(im):          # 近白（白衣/白花/碑体）
        return (im.min(axis=2) > 175)
    def warm(im):           # 暖橙（火光）
        r, g, b = im[:, :, 0], im[:, :, 1], im[:, :, 2]
        return (r > 150) & (r - b > 80) & (g > 80)
    return {"red": red, "reddeep": reddeep, "white": white, "warm": warm}


def main() -> int:
    ap = argparse.ArgumentParser(description="把网络图标/MV 帧烧成实心 ASS 绘图路径，写进工程目录。")
    ap.add_argument("--out", required=True, help="产物路径，例如 proj/assets/shapes.json（**必须指向工程，不许指进 skill**）")
    ap.add_argument("--video", help="MV 路径；给了才烧 MV 帧抠图（不给则只烧网络图标）")
    ap.add_argument("--only", nargs="*", help="只烧这几个图标名")
    a = ap.parse_args()

    out = os.path.abspath(a.out)
    skill = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.commonpath([out, skill]) == skill:
        sys.exit("--out 落在 skill 目录里（%s）。skill 是只读的代码与契约，产物属于工程 —— "
                 "把它指到 proj/assets/ 下面。" % skill)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    res = {}
    names = a.only or list(ICONS)
    for name in names:
        try:
            d = icon_path(ICONS[name])
            if d:
                res[name] = {"d": d}
                print("%-14s %6d 字符" % (name, len(d)))
        except Exception as e:
            print("%-14s FAIL %s" % (name, str(e)[:50]))

    if a.video:
        conds = _conds()
        for name, (t, box, cname) in MV_CROPS.items():
            try:
                d = mv_shape(a.video, t, box, conds[cname])
                if d:
                    res[name] = {"d": d}
                    print("%-14s %6d 字符 (MV 掩膜 %s)" % (name, len(d), a.video))
                else:
                    print("%-14s 掩膜为空" % name)
            except Exception as e:
                print("%-14s FAIL %s" % (name, str(e)[:60]))

    json.dump(res, open(out, "w"), ensure_ascii=False)
    print("-> %s（%d 个实心图形）" % (out, len(res)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
