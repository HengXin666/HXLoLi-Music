# -*- coding: utf-8 -*-
"""
图片层: 把抠好的 PNG 用 `\\1img` 贴进 ASS, 在卡点/特定位置出现.

决策与实测依据: 图片层决策见本文件的 beat-layer 锚点

## 两个实测规格 (踩过才知道)

1. **纹理按绘制矩形平铺.** `\\1img(f)` 是**填充纹理**, 不是"贴一张图".
   矩形 = 图片尺寸时正好显示一次; 矩形更大就会铺成 N x M 张
   (实测: 300x240 矩形 + 105x84 图 -> 铺了 9 张兔子).
   所以这里生成矩形时**强制读图片真实尺寸**.
2. **图片路径相对 ass 文件所在目录, 且必须先写进 worker 虚拟 FS.**
   没写进去时控制台报 `[vsfiltermod] Failed to load image: X (can't fopen)`,
   画面空白但**渲染不失败**  是静默失败.

## 渲染器差异 (决定了能不能用这一层)

| 渲染器 | `\\1img` |
|---|---|
| 系统 libass (ffmpeg 的 subtitles 滤镜) | **不支持**, 静默退化成纯色填充 |
| HXLoLi 定制版 (SubtitlesOctopus WASM) | 支持, 另含 `\\2img \\3img \\4img \\distort \\fsvp` 等 |

所以图片层的验证**必须**用 `render_octopus.py`, 用 ffmpeg 截图会得到"白块"这种假结论.

## 用法要点 (用户 2026-10-03 定的量)

「图片它本身占用是比较大的, 也不需要特别多, 它可能只需要几张在某些位置」
「有些地方是这样子, 但是有些地方, 比如吉祥物那种, 确实又可以这么用」

参考成品的实际用量:
  * 共 11 张图: 提比全身 105x84, 提比小表情 5 张 51x44, 人物大图 3 张 375x296
  * 出现位置: 句间/卡点, 每次 1~2 张, 全曲 <8 处
  * 做法: 吉祥物小图随字飞出; 人物大图只在特定句出现
"""
import os, re

from assfx.draw import shapes as S

_IMG_RE = re.compile(r"\\[1-4]img\(([^)]+)\)")


def image_rect(draw_w, draw_h):
    """生成正好等于图片尺寸的矩形绘图代码.

    **必须用图片真实尺寸**, 否则纹理平铺成多张  见模块头的规格 1.
    """
    return f"m 0 0 l {int(draw_w)} 0 l {int(draw_w)} {int(draw_h)} l 0 {int(draw_h)}"


def img_size(path):
    from PIL import Image
    with Image.open(path) as im:
        return im.size


def collect_images(ass_path):
    """从 ass 里收集 `\\1img` 引用的相对路径(去重, 过滤 Lua 动态路径)"""
    txt = open(ass_path, encoding="utf-8-sig", errors="replace").read()
    out = []
    for m in _IMG_RE.finditer(txt):
        rel = m.group(1).strip()
        if rel.startswith("data:") or "!" in rel or "$" in rel:
            continue
        if rel not in out:
            out.append(rel)
    return out


# Agent Notes: hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开
# 
def check_images(ass_path):
    """
    .agents/notes/implemented/process/2026-10-05-karaoke-scripts-grouping.md
体检: 每个 `\\1img` 引用的图是否存在 / 是否已抠干净.

    返回 (ok, 报告列表). 贴边的图在这里就该被拦下  它在成片里就是"被切平的头发".
    """
    d = os.path.dirname(os.path.abspath(ass_path))
    rep, ok = [], True
    for rel in collect_images(ass_path):
        p = os.path.join(d, rel)
        if not os.path.exists(p):
            rep.append((False, rel, "缺失"))
            ok = False
            continue
        try:
            from PIL import Image
            import numpy as np
            a = np.asarray(Image.open(p).convert("RGBA"))[:, :, 3]
            # Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
            # 
            bad = [k for k, v in (("top", a[0, :]), ("bottom", a[-1, :]),
                                  ("left", a[:, 0]), ("right", a[:, -1]))
                   if (v > 8).mean() > 0.01]
            if bad:
                rep.append((False, rel, "边缘贴边: " + ",".join(bad)))
                ok = False
            else:
                rep.append((True, rel, f"{Image.open(p).size}"))
        except Exception as exc:
            rep.append((False, rel, "读不了: %s" % exc))
            ok = False
    return ok, rep


# Agent Notes: 卡点层与图片层  第五、第六层特效的实测规格
# 
def put_image(f, layer, t0, t1, x, y, rel, size=None, extra="", a_peak=8,
              c1="#FFFFFF", c3="#000000", bord=0, blur=0.0, fade_in=0.12, fade_out=0.25,
              x1=None, y1=None, path_dir=None):
    """
    .agents/notes/implemented/feature/2026-10-03-karaoke-beat-layer.md
    .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
把一张图作为纹理发射到 band 内.

    f        FX 实例
    rel      `\\1img` 用的相对路径(相对于 ass 所在目录)
    size     (w,h); 不给就从文件读. **必须与图片真实尺寸一致**, 否则平铺成多张
    extra    追加标签(\\fscx/\\fscy/\\t 等)

    注意: 这里**不做缩放**去改变矩形尺寸  缩放要用 `\\fscx/\\fscy`, 让矩形跟着一起缩,
    而不是改矩形数值(那会改变平铺次数).
    """
    if size is None:
        if not path_dir:
            raise ValueError("put_image: 要么给 size, 要么给 path_dir 以便读图片尺寸")
        size = img_size(os.path.join(path_dir, rel))
    w, h = size
    # 矩形按原始尺寸画; 缩放交给 fscx/fscy, 这样平铺次数恒为 1
    w = max(1, int(round(w)))
    h = max(1, int(round(h)))
    # \1img 必须在 \p1 之前; 纹理要显式给 bord=0 否则描边会糊住图
    ex = f"\\1img({rel})\\p1" + extra
    f.shape(layer, t0, t1, x, y, x1 if x1 is not None else x, y1 if y1 is not None else y,
            draw=image_rect(w, h), c1=c1, c3=c3, bord=bord, blur=blur,
            a_peak=a_peak, fade_in=fade_in, fade_out=fade_out, extra=ex)


def pop_image(f, layer, t, x, y, rel, size=None, path_dir=None, life=1.2,
              scale=(60, 100), spin=0, drift=(0, 0), a_peak=8, extra=""):
    """卡点处弹出一张图: 起手缩小 -> 涨到满 -> 漂走. 用于"左右元素在卡点出现".

    与 beat_scatter 的配合: 卡点群发的时刻调用它, 图从那个位置弹出.
    """
    ex = (f"\\fscx{scale[0]}\\fscy{scale[0]}"
          f"\\t(0,220,0.7,\\fscx{scale[1]}\\fscy{scale[1]})")
    if spin:
        ex += f"\\t(0,{int(life*1000)},\\frz{spin})"
    put_image(f, layer, t, t + life, x, y, rel, size=size, path_dir=path_dir,
              extra=ex + extra, a_peak=a_peak, fade_in=0.06, fade_out=life * 0.4,
              x1=x + drift[0], y1=y + drift[1])


def side_slots(f, t, rels, size=None, path_dir=None, edge="both", y=None,
               inset=1.12, layer=3, life=1.4, extra=""):
    """在 band 的左右两侧各弹一张图("左右元素").

    inset: 相对 band 半宽的外扩倍数. 1.0 = 刚好在 band 边缘, >1 = 往外一点
           (band 铁律: 图本身仍要落在 band 内, FX.shape 会夹取)
    """
    b = f.b
    cx = (b[0] + b[2]) / 2
    if y is None:
        y = (b[1] + b[3]) / 2
    n = 0
    xs = []
    if edge in ("both", "left"):
        xs.append(b[0] + (b[2] - b[0]) * 0.10)
    if edge in ("both", "right"):
        xs.append(b[0] + (b[2] - b[0]) * 0.90)
    for i, x in enumerate(xs):
        rel = rels[i % len(rels)]
        pop_image(f, layer, t + i * 0.06, x, y, rel, size=size, path_dir=path_dir,
                  life=life, scale=(55, 100), spin=(18 if i % 2 == 0 else -18), extra=extra)
        n += 1
    return n
