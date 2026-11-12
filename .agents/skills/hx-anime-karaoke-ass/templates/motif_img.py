# -*- coding: utf-8 -*-
"""图片母题接入层 (2026-11-10, 占位口径).

代码只按 slot 名取图; 文件/裁切/缩放/锚点/旋转/翻转/透明度/调色都在 assets/motif.json, 素材换了不改代码.
slot 不存在 / enabled=false / 文件缺失 -> place() 返回 False, 调用方继续画原来的矢量.
缺件回退必须有声音 (2026-11-12 用户定): motif.json 缺失、slot 的 file 缺失、整帧未抠图 三种回退记进 FALLBACK,
  生成器在 doc.write 之后调 report(out): 终端打一行汇总 (哪几个 slot、缺什么), 并在 out 旁写 <out 名>.motif_fallback.json 旁证;
  没有回退时删掉旧旁证, 所以"没有旁证文件" = 这次是完整版. 不抛异常: 缺图也要能跑完.
  slot 不在 motif.json 里 / enabled=false 是有意不用图 (例 p31_orb), 不算缺件.

素材可能是从 MV 帧里抠出来的元素 (不正对镜头, 朝向和尺寸都不规整, 主体不在画布中心), 所以 slot 支持:
  file     相对 out.ass 目录的 PNG (RGBA; 背景必须已抠掉, 这里不做抠图; 没有 alpha 通道的整帧会被拒, 回退矢量)
  crop     [x0,y0,x1,y1] 源图像素裁切 (整帧抠图时只取元素那块), 可省
  trim     true -> 按 alpha>8 收紧到主体包围盒, 再留 pad px 透明边 (默认 true, pad 12)
  flip     "x" / "y" / "xy" 镜像, 可省
  fit      {"h": px} / {"w": px} / {"scale": k}  成片尺寸 (按裁切+收紧之后的图算)
  anchor   [u, v] 0~1, 图内哪一点落在 (x, y) 上, 也是旋转中心 (手腕/剑柄/辫根); 默认 [0.5, 0.5]
  frz      平面旋转 (度, 逆时针为正, 绕 anchor, 由位置换算实现, 不用 \\org); frx / fry 透视倾斜 (度, 锚点近似), 可省
  rot      "bake" (默认, 静态旋转用 PIL BICUBIC 烘进派生图) 或 "tag" (写 \\frz, 要做旋转动画时用; libass 最近邻, 有锯齿)
  a_peak   alpha 峰值 (0 = 不透明, 255 = 全透明), 默认 8
  dx, dy   在调用方给的坐标上再偏移 (px)
  scale    "prescale" (默认, PIL LANCZOS 预缩, 矩形 = 缩后尺寸) 或 "fscx" (矩形 = 原尺寸, libass 缩;
           实测会出锯齿/暗点, 贴边图还会在矩形对边出接缝, 只留作对照; 下面三个融合字段只在 prescale 下生效)

融合字段 (2026-11-10 老板批准; 每个都能单独关, 三个都关时派生图/文件名/ASS 与加字段前逐字节相同).
颜色可写 "#RRGGBB", 也可写句色角色名 dark/glow/pale/base, 从调用方 place(..., hue=k.th) 取 (k.th 来自 judge/hue.json 本句);
写了角色名却没给 hue 时, 该字段跳过 (等于关).
  duotone  双色调: 按亮度把图映射到句色. 默认开 = {"stops": ["dark","glow","pale"], "gamma": 0.85, "mix": 1.0}
           stops 2~3 个色 (亮度 0 / 0.5 / 1); gamma 0.4~2.0 (小于 1 偏亮); mix 0~1 (与原色混合, 0 = 原色).
           关: false 或 mix 0.
  fade     断口渐隐 (实物被画框切开的那一边). 默认开 = {"h": 0.28, "edge": "auto"}
           h 0~0.6 = 渐隐长度占主体该方向尺寸的比例, 0 = 不渐隐. edge "auto" 按图判: 包围盒哪条边贴着最长一段
           实心像素就是断口 (抠图被画框切开的切口); 四边都不到 12% 视为整件实物, 不渐隐. 也可写 "anchor"
           (旧口径: 离锚点最近的边) 或 "bottom"/"top"/"left"/"right". 在旋转之前做, 跟着图一起转. 关: false 或 h 0.
  glow     外发光: 句色光晕垫在图下面, 让图和字/阵/球一样 "会发光". 默认开、强度低 = {"r": 4, "a": 0.35, "color": "glow"}
           r 0~20 成片像素 (在缩放之后做, 小图上也按成片尺寸算); a 0~1 光晕峰值不透明度; 0 = 关.
           画布四边对称外扩 ceil(2.5r), 中心不变, 锚点换算不受影响. 关: false 或 a 0 或 r 0.

时间变换: place(..., init="\\fscx30\\fscy30", anim=[(0, 4.6, "\\fscx100\\fscy100"), ...]).
  anim 每项 (s0, s1, tags) 或 (s0, s1, accel, tags), s 是相对 t0 的秒; 写成 \\t(ms0,ms1[,accel],tags).
  prescale 下基准缩放是 100 (派生图已是成片尺寸). 旋转动画要把 slot 的 rot 设成 "tag", 否则静态角度已烘进图里;
  \\an5 下 \\t 的 \\frz / \\fscx 绕矩形中心变, 不绕 anchor (anchor 只钉静态姿态).
多个 slot 同句 (2026-11-10 p31 手 + 水球实测): slot 之间不共享 band 余量. 每张图各自对 band 四边夹取、各自对字量间隙,
  互不挤占 (FX.shape 只看 band, 不看别的图), 所以不存在"先贴的占位、后贴的被挤"; 图与图的重叠 (水球坐在掌心) 不查, 是构图本身.
自动缩管什么、不管什么 (2026-11-10 定, 分工写死在这里, 别以为生成器管全了):
  自动缩只按派生图满尺寸 (100%, 即 prescale 的基准) 量, 只保证"满尺寸时在 band 内且离字 >= MOTIF_GAP".
  init/anim 把图放大到 100% 以上 (如 \\t(\\fscx130)), 或用 \\org 加旋转把图甩近字, 这里**拦不住**,
  由门禁 validate_ass.py 的 [E] 母题压字兜底 (motif_gap.image_scale 取显示期内最大缩放, image_rotation 绕 \\org).
  所以调用方要放大过 100% 时, 应把 fit 设成最大那一刻的尺寸、anim 只做 <=100 的生长.
派生图写 assets/_scaled/<stem>-<参数哈希>.png, 源图或参数 (含解析后的句色) 变了哈希就变.
"""
import hashlib, json, math, os, re

from assfx.draw.image import put_image
from assfx.draw.motif_gap import MOTIF_GAP, text_ink_boxes, image_points, min_gap, estimated_fonts

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.environ.get("HX_MOTIF_CFG", os.path.join(HERE, "assets", "motif.json"))

DEF_DUOTONE = {"stops": ["dark", "glow", "pale"], "gamma": 0.85, "mix": 1.0}
DEF_FADE = {"h": 0.28, "edge": "auto"}
DEF_GLOW = {"r": 4, "a": 0.35, "color": "glow"}


FALLBACK = []      # [(slot, 原因)], 缺件回退记录; report() 汇总


def _miss(slot, why):
    FALLBACK.append((slot, why))
    return False


def report(out):
    """生成结束时调用: 汇总缺件回退. 返回回退的 slot 数. 旁证: <out 去扩展名>.motif_fallback.json (仅有回退时存在)."""
    side = os.path.splitext(out)[0] + ".motif_fallback.json"
    agg = {}
    for slot, why in FALLBACK:
        agg.setdefault(slot, {"slot": slot, "why": why, "n": 0})["n"] += 1
    if not agg:
        if os.path.exists(side):
            os.remove(side)
        return 0
    print("[motif_img] 注意: 这次不是完整版, %d 个 slot 回退成矢量: %s" % (len(agg), "; ".join(
        "%s (%s, %d 次)" % (v["slot"], v["why"], v["n"]) for v in agg.values())))
    print("[motif_img] 旁证: %s; 自备 assets 下的文件后重跑即为完整版 (见示例 README)" % side)
    with open(side, "w", encoding="utf-8") as fh:
        json.dump({"out": os.path.basename(out), "complete": False, "n_slots": len(agg), "fallback": list(agg.values()),
                   "cfg": os.path.relpath(CFG, HERE) if CFG.startswith(HERE) else CFG}, fh, ensure_ascii=False, indent=1)
    return len(agg)


def slots():
    if not os.path.exists(CFG):
        return {}
    return json.load(open(CFG, encoding="utf-8")).get("slots", {})


def _col(v, hue):
    """'#RRGGBB' 或角色名 -> (r,g,b); 解析不了返回 None."""
    if isinstance(v, str) and not v.startswith("#"):
        v = (hue or {}).get(v)
    if not isinstance(v, str) or not v.startswith("#") or len(v) != 7:
        return None
    return tuple(int(v[i:i + 2], 16) for i in (1, 3, 5))


def _fx(s, hue):
    """解析三个融合字段 -> 生效的参数 dict (关掉的不出现). 结果进哈希."""
    out = {}
    d = s.get("duotone", True)
    if d is not False:
        d = dict(DEF_DUOTONE, **(d if isinstance(d, dict) else {}))
        cols = [_col(c, hue) for c in d["stops"]]
        if float(d["mix"]) > 0 and 2 <= len(cols) <= 3 and all(cols):
            out["duotone"] = dict(stops=cols, gamma=float(d["gamma"]), mix=min(1.0, float(d["mix"])))
    fd = s.get("fade", True)
    if fd is not False:
        fd = dict(DEF_FADE, **(fd if isinstance(fd, dict) else {}))
        if float(fd["h"]) > 0:
            out["fade"] = dict(h=min(0.6, float(fd["h"])), edge=fd["edge"])   # auto 在 _derive 里按图判
    g = s.get("glow", True)
    if g is not False:
        g = dict(DEF_GLOW, **(g if isinstance(g, dict) else {}))
        c = _col(g["color"], hue)
        if float(g["a"]) > 0 and float(g["r"]) > 0 and c:
            out["glow"] = dict(r=min(20.0, float(g["r"])), a=min(1.0, float(g["a"])), color=c)
    return out


def _cut_edge(im, edge, anchor):
    """断口方向. edge 明写就用它. auto: 看主体包围盒四条边上贴着多少实心像素 (alpha>200, 最外 2 行/列),
    断口 = 贴得最长的那条边 (抠图时实物被画框切开, 切口是一整段实心直边; 指尖/发梢只贴几个像素).
    最长的也不到该边长度 12% -> 没有断口 (整件实物), 返回 None 不渐隐. "anchor": 旧口径, 取离锚点最近的边."""
    if edge not in ("auto", "anchor"):
        return edge
    if edge == "anchor":
        u, v = anchor
        return min((("left", u), ("right", 1 - u), ("top", v), ("bottom", 1 - v)), key=lambda p: p[1])[0]
    import numpy as np
    al = np.asarray(im.getchannel("A"))
    ys, xs = np.nonzero(al > 8)
    if not len(ys):
        return None
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    sub = al[y0:y1 + 1, x0:x1 + 1] > 200
    run = {"top": sub[:2].any(0).mean(), "bottom": sub[-2:].any(0).mean(),
           "left": sub[:, :2].any(1).mean(), "right": sub[:, -2:].any(1).mean()}
    e = max(run, key=run.get)
    return e if run[e] >= 0.12 else None


def _duotone(im, p):
    import numpy as np
    from PIL import Image
    a = np.asarray(im).astype(float)
    lum = ((0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]) / 255) ** p["gamma"]
    st = [np.array(c, float) for c in p["stops"]]
    if len(st) == 2:
        rgb = st[0] + (st[1] - st[0]) * lum[..., None]
    else:
        lo = np.clip(lum * 2, 0, 1)[..., None]
        hi = np.clip(lum * 2 - 1, 0, 1)[..., None]
        rgb = np.where(lum[..., None] < 0.5, st[0] + (st[1] - st[0]) * lo, st[1] + (st[2] - st[1]) * hi)
    rgb = a[..., :3] * (1 - p["mix"]) + rgb * p["mix"]
    return Image.fromarray(np.dstack([rgb, a[..., 3]]).clip(0, 255).round().astype(np.uint8), "RGBA")


def _fade(im, p):
    import numpy as np
    from PIL import Image
    a = np.asarray(im).copy()
    al = a[..., 3].astype(float)
    vert = p["edge"] in ("top", "bottom")
    prof = al.max(1) if vert else al.max(0)
    idx = np.nonzero(prof > 8)[0]
    if not len(idx):
        return im
    i0, i1 = idx.min(), idx.max()
    L = max(1.0, p["h"] * (i1 - i0 + 1))
    n = al.shape[0] if vert else al.shape[1]
    pos = np.arange(n, dtype=float)
    dist = (i1 - pos) if p["edge"] in ("bottom", "right") else (pos - i0)
    t = np.clip(dist / L, 0, 1)
    w = t * t * (3 - 2 * t)                               # smoothstep, 断口处为 0
    al = al * (w[:, None] if vert else w[None, :])
    a[..., 3] = al.round().clip(0, 255).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def _glow(im, p):
    from PIL import Image, ImageFilter, ImageOps
    pad = int(math.ceil(2.5 * p["r"]))
    body = ImageOps.expand(im, border=pad, fill=(0, 0, 0, 0))
    al = body.getchannel("A").filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(p["r"]))
    al = al.point(lambda v: int(round(min(255, v * 1.6) * p["a"])))
    halo = Image.new("RGBA", body.size, tuple(p["color"]) + (0,))
    halo.putalpha(al)
    return Image.alpha_composite(halo, body)


def _derive(s, prescale=True, hue=None):
    """按 slot 参数产出派生图, 返回 (rel, w, h, k, ow, oh, baked): k 是还要交给 \\fscx 的倍数 (prescale 时为 1)."""
    from PIL import Image, ImageOps
    src = os.path.join(HERE, s["file"])
    keys = ("crop", "trim", "pad", "flip", "fit", "frz", "anchor", "rot")
    fx = _fx(s, hue) if prescale else {}
    blob = json.dumps({k: s.get(k) for k in keys}, sort_keys=True).encode() + (b"p" if prescale else b"f")
    if fx:                                                # 三个都关时不进哈希 -> 文件名与加字段前相同
        blob += json.dumps(fx, sort_keys=True).encode()
    sig = hashlib.sha256(open(src, "rb").read() + blob).hexdigest()[:10]
    stem = os.path.splitext(os.path.basename(s["file"]))[0]
    rel = "assets/_scaled/%s-%s.png" % (stem, sig)
    dst = os.path.join(HERE, rel)
    im = Image.open(src)
    if "A" not in im.getbands():
        raise ValueError("motif_img: %s 没有 alpha 通道 (还是整帧?), 背景要先抠掉" % s["file"])
    im = im.convert("RGBA")
    if s.get("crop"):
        im = im.crop(tuple(int(v) for v in s["crop"]))
    if s.get("trim", True):
        bb = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        if bb:
            im = im.crop(bb)
        p = int(s.get("pad", 12))
        im = ImageOps.expand(im, border=p, fill=(0, 0, 0, 0))
    fl = s.get("flip") or ""
    if "x" in fl:
        im = ImageOps.mirror(im)
    if "y" in fl:
        im = ImageOps.flip(im)
    fit = s.get("fit") or {"h": s.get("h", im.size[1])}
    k = fit["h"] / im.size[1] if "h" in fit else fit["w"] / im.size[0] if "w" in fit else float(fit.get("scale", 1))
    if prescale:
        im = im.resize((max(1, round(im.size[0] * k)), max(1, round(im.size[1] * k))), Image.LANCZOS)
        k = 1.0
    if "duotone" in fx:
        im = _duotone(im, fx["duotone"])
    if "fade" in fx:                                      # 旋转前做, 断口跟着图转
        fx["fade"]["edge"] = _cut_edge(im, fx["fade"]["edge"], s.get("anchor", [0.5, 0.5]))
        if fx["fade"]["edge"]:
            im = _fade(im, fx["fade"])
    # 锚点相对图中心的向量 (成片像素); 外发光对称外扩, 不改这个向量
    u, v = s.get("anchor", [0.5, 0.5])
    ow, oh = (u - 0.5) * im.size[0] * k, (v - 0.5) * im.size[1] * k
    frz = float(s.get("frz", 0) or 0)
    baked = prescale and frz and s.get("rot", "bake") == "bake"
    if baked:
        # 静态旋转烘进图里 (BICUBIC, expand 绕中心). 实测 libass 对 \1img 纹理的 \frz 是最近邻采样,
        # 斜边出明显锯齿 (2026-11-10, f205c 对照); 烘焙后 ASS 里不再写 \frz.
        im = im.rotate(frz, resample=Image.BICUBIC, expand=True)
    if "glow" in fx:                                      # 旋转后做, 光晕不被裁角
        im = _glow(im, fx["glow"])
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        im.save(dst)
    return rel, im.size[0], im.size[1], k, ow, oh, baked


def _anim(t0, init, anim):
    ex = init or ""
    for a in anim or ():
        s0, s1, tags = (a[0], a[1], a[-1])
        acc = (",%g" % a[2]) if len(a) == 4 else ""
        ex += "\\t(%d,%d%s,%s)" % (round(s0 * 1000), round(s1 * 1000), acc, tags)
    return ex


_SFMT = ["Name", "Fontname", "Fontsize", "PrimaryColour", "SecondaryColour", "OutlineColour", "BackColour", "Bold",
         "Italic", "Underline", "StrikeOut", "ScaleX", "ScaleY", "Spacing", "Angle", "BorderStyle", "Outline", "Shadow",
         "Alignment"]


def _styles(doc):
    out = {}
    for line in doc.styles:
        v = [x.strip() for x in str(line).split(":", 1)[-1].split(",")]
        out[v[0]] = dict(zip(_SFMT, v))
    return out


def _text_evs(f):
    """本 band 已经下发的歌词事件 (gen.render 先 k.render 出字, 再调 fx, 所以这里拿得到)."""
    st = _styles(f.doc)
    return [(e[1], e[2], st.get(e[3], {}), e[5]) for e in f.doc.events if e[4] == "ly:" + f.name]


def _scaled_fit(s, r):
    fit = dict(s.get("fit") or {})
    for kk in ("w", "h", "scale"):
        if kk in fit:
            fit[kk] = fit[kk] * r
    return dict(s, fit=fit)


def _fit_label(s):
    fit = s.get("fit") or {}
    for kk, name in (("w", "宽"), ("h", "高"), ("scale", "倍率")):
        if kk in fit:
            return name, fit[kk]
    return "倍率", 1.0


def _layout(s, x, y, prescale, hue):
    """派生图 + 锚点换算 -> (rel, w, h, k, baked, cx, cy): cx/cy 是下发时 \\pos 的请求值 (夹取前)."""
    rel, w, h, k, ow, oh, baked = _derive(s, prescale, hue)
    th = math.radians(s.get("frz", 0) or 0)
    rx = ow * math.cos(th) + oh * math.sin(th)          # 屏幕坐标 y 朝下, frz 正 = 逆时针
    ry = -ow * math.sin(th) + oh * math.cos(th)
    return rel, w, h, k, baked, x + s.get("dx", 0) - rx, y + s.get("dy", 0) - ry


def _gap_at(f, s, rel, w, h, k, baked, cx, cy, boxes):
    """模拟 FX.shape 的 band 夹取 (\\an5 矩形, 无描边无模糊), 再用门禁同一把尺子量图到字的间隙."""
    import numpy as np
    from PIL import Image
    bx0, by0, bx1, by1 = f.b[:4]
    hw, hh = w * k / 2, h * k / 2
    cl = lambda v, lo, hi: min(max(v, lo), hi) if lo <= hi else (lo + hi) / 2  # noqa: E731
    qx, qy = cl(cx, bx0 + hw + 1, bx1 - hw - 1), cl(cy, by0 + hh + 1, by1 - hh - 1)
    al = np.asarray(Image.open(os.path.join(HERE, rel)).convert("RGBA"))[:, :, 3]
    frz = 0 if baked else float(s.get("frz", 0) or 0)
    px, py = image_points(al, qx, qy, k, k, frz)
    g, b = min_gap(px, py, boxes)
    return g, b, (qx - cx, qy - cy)


def _room(f, boxes, cx):
    """图所在一侧, 字到 band 边还剩多少 px (只用于打印)."""
    if not boxes:
        return f.b[2] - f.b[0]
    xs0 = [b[0] for b in boxes]; xs1 = [b[2] for b in boxes]
    right = [b[2] for b in boxes if b[2] <= cx]
    left = [b[0] for b in boxes if b[0] >= cx]
    if right and (not left or cx - max(right) <= min(left) - cx):
        return f.b[2] - max(right)
    if left:
        return min(left) - f.b[0]
    return min(f.b[2] - max(xs1), min(xs0) - f.b[0])


def place(f, slot, layer, t0, t1, x, y, fade_in=0.6, fade_out=0.6, extra="", x1=None, y1=None,
          hue=None, init="", anim=None, t_move=None):
    if not os.path.exists(CFG):
        return _miss(slot, "缺配置 assets/motif.json" if CFG.startswith(HERE) else "缺配置 " + CFG)
    s = slots().get(slot)
    if not s or not s.get("enabled", True):                # 有意不用图, 不算缺件
        return False
    if not os.path.exists(os.path.join(HERE, s["file"])):
        return _miss(slot, "缺文件 " + s["file"])
    prescale = s.get("scale", "prescale") == "prescale"
    try:
        rel, w, h, k, baked, cx, cy = _layout(s, x, y, prescale, hue)
    except ValueError as exc:                             # 没抠背景的整帧: 不贴, 回退矢量, 并在终端喊出来
        print("[motif_img] slot %s 回退矢量: %s" % (slot, exc))
        return _miss(slot, "整帧未抠图")
    # ---- 提前算空间再定尺寸 (2026-11-10 用户定): 图边缘到字 >= MOTIF_GAP, 放不下就按比例缩.
    # 尺子与 validate_ass.py 的 [E] 母题压字 同一套 (assfx/draw/motif_gap.py),
    # 夹取也按 FX.shape 同一公式模拟, 所以这里放得下 = 门禁过. \\move (x1/y1) 与动画缩放不在此量, 留给门禁.
    if s.get("autofit", True) and x1 is None and y1 is None:
        boxes = text_ink_boxes(_text_evs(f), t0, t1, os.environ.get("ASSFX_FONTS"))
        est = estimated_fonts(boxes)
        if est:
            print("[motif_img] WARN slot %s 字体 %s 不在 ASSFX_FONTS, 字框按 0.72em 估宽, 自动缩的尺寸可能不准"
                  % (slot, "/".join(est)))
        g, b, _ = _gap_at(f, s, rel, w, h, k, baked, cx, cy, boxes)
        if g < MOTIF_GAP:
            name, v0 = _fit_label(s)
            lo, hi = 0.25, 1.0                               # 二分最大缩放比 r: gap(r) >= MOTIF_GAP
            ok = None
            for _ in range(12):
                r = (lo + hi) / 2
                lay = _layout(_scaled_fit(s, r), x, y, prescale, hue)
                if _gap_at(f, s, *lay[:5], lay[5], lay[6], boxes)[0] >= MOTIF_GAP:
                    lo, ok = r, lay
                else:
                    hi = r
            if ok is None:
                print("[motif_img] ERROR slot %s 缩到 %d%% 仍压字 (到「%s」%.1fpx), 照原尺寸下发, 交给门禁拦"
                      % (slot, round(lo * 100), b[4] if b else "?", g))
            else:
                r = int(lo * v0) / v0 if name != "倍率" else lo     # 宽/高取整到 px, 往小取
                ok = _layout(_scaled_fit(s, r), x, y, prescale, hue)
                rel, w, h, k, baked, cx, cy = ok
                print("[motif_img] slot %s %s %g→%g (band 余 %.0fpx)" % (slot, name, v0, round(v0 * r, 2), _room(f, boxes, cx)))
    ex = ("\\fscx%.2f\\fscy%.2f" % (100 * k, 100 * k)) if k != 1.0 else ""
    for t in ("frz", "frx", "fry"):                      # frx/fry 透视时锚点只近似钉住
        if s.get(t) and not (t == "frz" and baked):
            ex += "\\%s%g" % (t, s[t])
    ex += _anim(t0, init, anim)
    ox, oy = cx - x - s.get("dx", 0), cy - y - s.get("dy", 0)
    mx = None if x1 is None else x1 + s.get("dx", 0) + ox
    my = None if y1 is None else y1 + s.get("dy", 0) + oy
    # ---- 夹取必须报警: 静默夹取会把图偷偷推到压字 (2026-11-10 p31 实测: dx+12 被夹回, 拇指压「た」).
    n0, i0 = f.n_clamped, len(f.doc.events)
    put_image(f, layer, t0, t1, cx, cy, rel, size=(w, h), path_dir=HERE, extra=ex + extra,
              a_peak=s.get("a_peak", 8), fade_in=fade_in, fade_out=fade_out, x1=mx, y1=my,
              **({} if t_move is None else {"t_move": t_move}))  # t_move: \move 的 (t1,t2) 毫秒; 不传时输出逐字节不变
    if f.n_clamped > n0:
        got = None
        if len(f.doc.events) > i0:
            m = re.search(r"\\(?:pos|move)\(\s*([-\d.]+)\s*,\s*([-\d.]+)", f.doc.events[-1][5])
            got = m and (float(m.group(1)) - cx, float(m.group(2)) - cy)
        sc = re.findall(r"\\fscx([\d.]+)", f.doc.events[-1][5]) if len(f.doc.events) > i0 else []
        shrink = (" 缩放 %s%%" % sc[0]) if sc and abs(float(sc[0]) - 100 * k) > 0.01 else ""
        print("[motif_img] WARN slot %s 被 band 夹取 %d 次: 位移 %s px%s" % (
            slot, f.n_clamped - n0, "(%+.1f, %+.1f)" % got if got else "?", shrink))
    return True
