# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
#   "fonttools",
# ]
# ///

"""
ASS 特效字幕自动校验。

用法:
  uv run validate_ass.py subs.ass --fontsdir fonts [--timing timing.json] [--max-overlap 1.2] [--density-warn 900] [--report out.txt]

检查项:
  [E] band 越界      Name=fx:/ly:/card:<band> 的事件包围盒（含缩放/旋转/边框/模糊）必须在该 band 矩形内
  [E] band 未登记    Name 指向不存在的 band
  [E] band 超出画面  band 矩形必须在 PlayRes 内
  [E] 字体缺失      Style 与 \\fn 使用的字体族名必须能在 fontsdir 中找到（否则 libass 回退，效果全变）
  [E] 时间非法      end <= start
  [W] 未标注事件    没有 Name 的事件无法做区域校验
  [W] 歌词重叠      两个歌词 band 在空间上相交且同时显示超过 --max-overlap 秒
  [W] 同步缺失      timing.json 中音拍起点在高亮层(Layer 3, ly:)找不到对应事件（±20ms）
  [W] 事件密度      任一时刻同时存在的事件数 > --density-warn（渲染会变慢，播放器可能掉帧）
退出码: 有 [E] 则为 1
"""
import argparse, bisect, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from assfx.geom import event_extent


TAG_RE = re.compile(r"\{[^}]*\}")


def pt(s):
    h, m, r = s.split(":"); return int(h) * 3600 + int(m) * 60 + float(r)


def load_ass(path):
    info, styles, events, bands = {}, {}, [], {}
    sec = None; sfmt = efmt = None
    for ln, raw in enumerate(open(path, encoding="utf-8-sig"), 1):
        line = raw.rstrip("\n")
        if line.startswith("["):
            sec = line.strip(); continue
        if sec == "[Script Info]":
            m = re.match(r";\s*assfx-band:\s*(\S+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", line)
            if m:
                bands[m.group(1)] = tuple(float(v) for v in m.groups()[1:])
            elif ":" in line and not line.startswith(";"):
                k, v = line.split(":", 1); info[k.strip()] = v.strip()
        elif sec == "[V4+ Styles]":
            if line.startswith("Format:"):
                sfmt = [x.strip() for x in line[7:].split(",")]
            elif line.startswith("Style:"):
                v = [x.strip() for x in line[6:].split(",")]
                d = dict(zip(sfmt, v)); styles[d["Name"]] = d
        elif sec == "[Events]":
            if line.startswith("Format:"):
                efmt = [x.strip() for x in line[7:].split(",")]
            elif line.startswith("Dialogue:"):
                v = line[9:].split(",", len(efmt) - 1)
                d = dict(zip(efmt, [x.strip() if i < len(efmt) - 1 else x for i, x in enumerate(v)]))
                d["_ln"] = ln; d["s"] = pt(d["Start"]); d["e"] = pt(d["End"])
                events.append(d)
    return info, styles, events, bands


class FontBook:
    """字体族名 -> 字宽度量（libass 缩放：fs / (winAscent+winDescent)）"""
    def __init__(self, fontsdir):
        from fontTools.ttLib import TTFont
        self.fonts = {}
        for p in sorted(glob.glob(os.path.join(fontsdir, "*.[ot]t[fc]"))):
            try:
                f = TTFont(p, fontNumber=0)
                os2 = f["OS/2"]; data = (f.getBestCmap(), f["hmtx"], os2.usWinAscent + os2.usWinDescent)
                for rec in f["name"].names:
                    if rec.nameID in (1, 4, 16):
                        self.fonts.setdefault(rec.toUnicode().strip().lower(), data)
            except Exception:
                pass

    def width(self, text, fs, font):
        d = self.fonts.get((font or "").strip().lower())
        if not d:
            return None
        cmap, hmtx, h = d
        return sum(hmtx[cmap[ord(c)]][0] if ord(c) in cmap else h * 0.6 for c in text) * fs / h


def font_families(fontsdir):
    from fontTools.ttLib import TTFont
    fams = set()
    for p in glob.glob(os.path.join(fontsdir, "*.[ot]t[fc]")):
        try:
            f = TTFont(p, fontNumber=0)
            for rec in f["name"].names:
                if rec.nameID in (1, 4, 16):
                    try:
                        fams.add(rec.toUnicode().strip().lower())
                    except Exception:
                        pass
        except Exception as ex:
            print(f"[W] 无法读取字体 {p}: {ex}")
    return fams


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ass"); ap.add_argument("--fontsdir"); ap.add_argument("--timing")
    ap.add_argument("--max-overlap", type=float, default=1.2); ap.add_argument("--density-warn", type=int, default=900)
    ap.add_argument("--tol", type=float, default=1.0); ap.add_argument("--report")
    a = ap.parse_args()
    info, styles, events, bands = load_ass(a.ass)
    W, H = float(info.get("PlayResX", 1920)), float(info.get("PlayResY", 1080))
    E, Wn = [], []

    for n, b in bands.items():
        if b[0] < 0 or b[1] < 0 or b[2] > W or b[3] > H:
            E.append(f"band {n} 超出画面: {b[:4]}")

    book = FontBook(a.fontsdir) if a.fontsdir else None
    # ---- 区域
    per_band = {}
    worst = {}
    untagged = 0
    for ev in events:
        if ev["e"] <= ev["s"]:
            E.append(f"L{ev['_ln']} 时间非法 {ev['Start']} -> {ev['End']}")
        name = ev.get("Name", "")
        m = re.match(r"(fx|ly|card):(\S+)", name)
        if not m:
            untagged += 1; continue
        kind, bn = m.groups()
        if bn not in bands:
            E.append(f"L{ev['_ln']} Name={name} 指向未登记的 band"); continue
        st = styles.get(ev["Style"], {})
        sp = float(st.get("Spacing", 0))
        meas = (lambda t, fs, fn, sp=sp: (book.width(t, fs, fn) + sp * len(t)) if book.width(t, fs, fn) else None) if book else None
        ext = event_extent(ev["Text"], float(st.get("Fontsize", 40)), float(st.get("Outline", 0)), int(st.get("Alignment", 5)),
                           scale_x=float(st.get("ScaleX", 100)), scale_y=float(st.get("ScaleY", 100)),
                           measure=meas, style_font=st.get("Fontname"))
        per_band.setdefault(bn, dict(fx=0, ly=0, card=0))[kind] += 1
        if ext is None:
            Wn.append(f"L{ev['_ln']} {name} 无 \\pos/\\move，无法定位"); continue
        b = bands[bn]
        over = max(b[0] - ext[0], b[1] - ext[1], ext[2] - b[2], ext[3] - b[3])
        if over > a.tol:
            key = (bn, kind)
            if key not in worst or over > worst[key][0]:
                worst[key] = (over, ev["_ln"], ext)
            per_band[bn].setdefault("viol", 0)
            per_band[bn]["viol"] += 1
    for (bn, kind), (over, ln, ext) in sorted(worst.items()):
        E.append(f"band {bn} [{kind}] 越界 {per_band[bn]['viol']} 条，最严重 L{ln} 超出 {over:.1f}px  ext=({ext[0]:.0f},{ext[1]:.0f},{ext[2]:.0f},{ext[3]:.0f}) band={bands[bn][:4]}")
    if untagged:
        Wn.append(f"{untagged} 条事件没有 Name 标注（无法做区域校验）")

    # ---- 字体
    if a.fontsdir:
        fams = font_families(a.fontsdir)
        # 只统计真正渲染文字的样式（纯 \\p 绘图事件不需要字体）
        is_text = lambda ev: TAG_RE.sub("", ev["Text"]).strip() != "" and not re.search(r"\\p[1-9]", ev["Text"])
        used = {styles[ev["Style"]]["Fontname"] for ev in events if ev["Style"] in styles and is_text(ev)}
        for ev in events:
            used.update(re.findall(r"\\fn([^\\}]+)", ev["Text"]))
        for fn in sorted(used):
            if fn.lower() not in fams:
                E.append(f"字体缺失: '{fn}' 不在 {a.fontsdir}（libass 会回退到其它字体）")

    # ---- 歌词重叠
    lyb = {}
    for ev in events:
        m = re.match(r"ly:(\S+)", ev.get("Name", ""))
        if m and ev["Layer"] in ("2",):
            r = lyb.setdefault(m.group(1), [1e9, -1e9]); r[0] = min(r[0], ev["s"]); r[1] = max(r[1], ev["e"])
    names = sorted(lyb, key=lambda n: lyb[n][0])
    for i, n1 in enumerate(names):
        for n2 in names[i + 1:]:
            ov = min(lyb[n1][1], lyb[n2][1]) - max(lyb[n1][0], lyb[n2][0])
            if ov <= 0:
                continue
            b1, b2 = bands[n1], bands[n2]
            # 用墨迹区域（去掉外扩）判断空间相交：粗略收缩 band 高度的 1/3
            iy = min(b1[3], b2[3]) - max(b1[1], b2[1]); ix = min(b1[2], b2[2]) - max(b1[0], b2[0])
            if ix > 0 and iy > 0 and ov > a.max_overlap:
                Wn.append(f"歌词 {n1} 与 {n2} 同屏重叠 {ov:.2f}s（>{a.max_overlap}s）")

    # ---- 同步
    if a.timing:
        tm = json.load(open(a.timing))
        hlev = [ev for ev in events if ev["Layer"] == "3" and ev.get("Name", "").startswith("ly:")]
        hl = sorted(ev["s"] for ev in hlev)
        # 分段擦亮（一个事件内多个 \\t(\\clip) 对应多个音拍）也算覆盖
        seg = []
        for ev in hlev:
            for m_ in re.finditer(r"\\t\((\d+),\d+,\\clip", ev["Text"]):
                seg.append(ev["s"] + int(m_.group(1)) / 1000)
        seg.sort()
        miss = []
        for m in tm:
            j = bisect.bisect_left(hl, m["s"] - 0.02); j2 = bisect.bisect_left(seg, m["s"] - 0.02)
            ok = (j < len(hl) and hl[j] <= m["s"] + 0.02) or (j2 < len(seg) and seg[j2] <= m["s"] + 0.02)
            if not ok:
                miss.append(f"{m['line']},{m['unit']},{m['mora']}「{m['text']}」@{m['s']:.2f}")
        if miss:
            Wn.append(f"{len(miss)} 个音拍在高亮层没有对应起点（英文/合并单元可忽略）: " + " ".join(miss[:12]) + (" ..." if len(miss) > 12 else ""))

    # ---- 密度
    t_end = max(ev["e"] for ev in events)
    starts = sorted(ev["s"] for ev in events); ends = sorted(ev["e"] for ev in events)
    peak, pt_ = 0, 0
    t = 0.0; hot = []
    while t < t_end:
        n = bisect.bisect_right(starts, t) - bisect.bisect_right(ends, t)
        if n > peak:
            peak, pt_ = n, t
        if n > a.density_warn:
            hot.append(t)
        t += 0.1
    if hot:
        Wn.append(f"事件密度过高（>{a.density_warn}）的时刻 {len(hot)} 个，起于 {hot[0]:.1f}s")

    out = []
    out.append(f"文件: {a.ass}")
    out.append(f"事件 {len(events)} 条 / band {len(bands)} 个 / 峰值同时事件 {peak} @ {pt_:.1f}s")
    out.append("band 统计: " + "  ".join(f"{n}(fx{v['fx']}/ly{v['ly']}" + (f"/越界{v['viol']}" if v.get('viol') else "") + ")" for n, v in per_band.items()))
    for e in E:
        out.append("[E] " + e)
    for w in Wn:
        out.append("[W] " + w)
    out.append("结果: " + ("通过" if not E else f"未通过（{len(E)} 个错误）"))
    txt = "\n".join(out)
    print(txt)
    if a.report:
        open(a.report, "w").write(txt + "\n")
    sys.exit(1 if E else 0)


if __name__ == "__main__":
    main()
