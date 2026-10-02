# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fonttools",
# ]
# ///

"""
排版：逐字 \\an5\\pos 坐标（fontTools 读取 advance，按 libass 缩放规则 fs/(winAscent+winDescent)）、
振假名逐拍排布、中文行、以及“歌词块墨迹包围盒 + 5% 画面边距”的特效允许区域 band。

垂直位置全部来自 calibrate_ruby.py 的实测结果（calib.json），不要凭 fs 猜。
"""
from fontTools.ttLib import TTFont


class Metric:
    def __init__(self, path):
        f = TTFont(path)
        os2 = f["OS/2"]
        self.h = os2.usWinAscent + os2.usWinDescent
        self.upm = f["head"].unitsPerEm
        self.cmap = f.getBestCmap(); self.hmtx = f["hmtx"]

    def adv(self, ch, fs):
        g = self.cmap.get(ord(ch))
        if g is None:
            return fs * self.upm / self.h
        return self.hmtx[g][0] * fs / self.h

    def width(self, s, fs, sp=0):
        return sum(self.adv(c, fs) + sp for c in s) - (sp if s else 0)

    def em(self, fs):
        return fs * self.upm / self.h


class Layout:
    """
    cfg 关键字段:
      jp_font, cn_font, latin_font  (字体文件路径)
      jp_fs, rb_fs, cn_fs, latin_fs
      jp_y, calib (calibrate_ruby.py 输出 dict)
      jp_sp, rb_sp, cn_sp, gap_em (空格宽，按 jp em)
      rb_pad  注音比汉字宽时，汉字占位至少 = 注音宽 + rb_pad（逐字注音不重叠）
      pad_x, pad_y  (band 外扩；默认 5% 画面 = 96 / 54)
    """

    def __init__(self, **cfg):
        self.c = dict(jp_sp=2, rb_sp=1, cn_sp=2, gap_em=0.5, cx=960, pad_x=96, pad_y=54, latin_fs=None, rb_pad=6)
        self.c.update(cfg)
        c = self.c
        self.MJ = Metric(c["jp_font"]); self.MC = Metric(c["cn_font"])
        self.ML = Metric(c["latin_font"]) if c.get("latin_font") else self.MJ
        cal = c["calib"]
        self.jp_y = c["jp_y"]
        self.rb_y = c["jp_y"] + cal["ruby_offset"]
        self.cn_y = c["jp_y"] + cal["cn_offset"]
        self.cal = cal
        c["latin_fs"] = c["latin_fs"] or c["jp_fs"]

    # ------------------------------------------------------------ 日文
    def phrase(self, lines, line_ids, TM, zh, cx=None):
        c = self.c; cx = cx or c["cx"]
        chars, rubies, items = [], [], []
        gap = self.MJ.em(c["jp_fs"]) * c["gap_em"]
        for k, li in enumerate(line_ids):
            ln = lines[li]
            if k > 0:
                items.append(dict(gap=True, w=gap))
            for ui, u in enumerate(ln["units"]):
                if u["kind"] == "space":
                    items.append(dict(gap=True, w=gap)); continue
                # timing.json 的 unit 索引保持原始 lyrics 索引（space 等无音拍单元自然跳过）
                # 因此直接用 ui 查询，对于无音拍单元会自然 miss
                mts = [TM.get((li, ui, mi)) for mi in range(len(u["morae"]))]
                mts = [m for m in mts if m is not None]  # 过滤掉 None（无音拍或缺失）
                if not mts:          # 孤立标点：跟随前一个字
                    prev = chars[-1] if chars else None
                    mts = prev["morae"] if prev else []
                if u["kind"] == "latin":
                    w = self.ML.width(u["surf"], c["latin_fs"], 1)
                    ch = dict(ch=u["surf"], w=w + c["jp_sp"] * 3, s=mts[0]["s"], e=mts[-1]["e"], kind="latin",
                              line=li, unit=ui, morae=mts, style="LAT")
                    chars.append(ch); items.append(ch)
                    continue
                n = len(u["surf"])
                per = [[] for _ in range(n)]
                if u.get("part_morae"):                 # 按字切分的读音：每个汉字拿到自己的音拍
                    k0 = 0
                    for ci, cnt in enumerate(u["part_morae"]):
                        per[ci] = mts[k0:k0 + cnt]; k0 += cnt
                else:
                    for mi, m in enumerate(mts):
                        per[min(n - 1, mi * n // len(mts))].append(m)
                grp = []
                for ci, s in enumerate(u["surf"]):
                    mm = per[ci] or mts
                    if not mm:  # 完全无音拍数据（如孤立标点在 timing 中被跳过）
                        mm = chars[-1]["morae"] if chars else []
                    if not mm:  # 仍无数据则跳过该字符
                        continue
                    kind = u["kind"] if s not in "？！?!、。…" else "punct"
                    ch = dict(ch=s, w=self.MJ.adv(s, c["jp_fs"]) + c["jp_sp"], s=mm[0]["s"], e=mm[-1]["e"], kind=kind,
                              line=li, unit=ui, morae=mm, style="JP")
                    chars.append(ch); items.append(ch); grp.append(ch)
                if u["kind"] == "kanji" and u.get("ruby"):
                    kg = [g for g in grp if g["kind"] == "kanji"] or grp
                    if u.get("part_morae"):
                        for g, mm in zip(kg, per):      # 逐字注音
                            rubies.append(dict(grp=[g], morae=mm))
                    else:                               # 熟字训：整组
                        rubies.append(dict(grp=kg, morae=mts))
        # 注音比汉字宽 → 加宽汉字的占位（左右均分），保证相邻注音不相撞、注音始终在自己的汉字正上方
        for r in rubies:
            rw = self.ruby_width(r["morae"])
            gw = sum(g["w"] for g in r["grp"])
            need = rw + c["rb_pad"] - gw
            if need > 0:
                for g in r["grp"]:
                    g["w"] += need / len(r["grp"])
        total = sum(it["w"] for it in items)
        x = cx - total / 2
        for it in items:
            it["x"] = x + it["w"] / 2
            x += it["w"]
        for i, ch in enumerate(chars):
            ch["i"] = i; ch["y"] = self.jp_y
        rb = []
        for r in rubies:
            gx = (r["grp"][0]["x"] + r["grp"][-1]["x"]) / 2
            flat = [(s, m) for m in r["morae"] for s in m["text"]]
            adv = self.ruby_advs(flat)
            tw = sum(adv) - c["rb_sp"]
            xx = gx - tw / 2
            for (s, m), a in zip(flat, adv):
                rb.append(dict(ch=s, x=xx + (a - c["rb_sp"]) / 2, y=self.rb_y, s=m["s"], e=m["e"], host=r["grp"][0]))
                xx += a
        cn = self.cn_line(zh, cx)
        return Phrase(self, chars, rb, cn)

    def ruby_advs(self, flat):
        c = self.c
        return [self.MJ.adv(s, c["rb_fs"]) * (0.7 if s in "ゃゅょぁぃぅぇぉっ" else 1.0) + c["rb_sp"] for s, _ in flat]

    def ruby_width(self, morae_):
        flat = [(s, m) for m in morae_ for s in m["text"]]
        return sum(self.ruby_advs(flat)) - self.c["rb_sp"] if flat else 0

    # ------------------------------------------------------------ 中文
    def cn_line(self, zh, cx=None):
        c = self.c; cx = cx or c["cx"]
        if not zh:
            return []
        cw = [self.MC.adv(ch, c["cn_fs"]) + c["cn_sp"] if ch != " " else self.MC.em(c["cn_fs"]) * 0.6 for ch in zh]
        x = cx - (sum(cw) - c["cn_sp"]) / 2
        out = []
        for ch, w in zip(zh, cw):
            if ch != " ":
                out.append(dict(ch=ch, x=x + (w - c["cn_sp"]) / 2, y=self.cn_y, w=w))
            x += w
        return out


class Phrase:
    def __init__(self, L, chars, rb, cn):
        self.L = L; self.chars = chars; self.rb = rb; self.cn = cn
        c = L.c; cal = L.cal
        xs0 = [ch["x"] - ch["w"] / 2 for ch in chars] + [ch["x"] - ch["w"] / 2 for ch in cn]
        xs1 = [ch["x"] + ch["w"] / 2 for ch in chars] + [ch["x"] + ch["w"] / 2 for ch in cn]
        top = L.jp_y + (cal["ruby_offset"] + cal["ruby_kana"]["top_p10"] if rb else cal["jp_kanji"]["top_p10"])
        bot = (L.cn_y + cal["cn"]["bottom_p90"]) if cn else L.jp_y + cal["jp_kanji"]["bottom_p90"]
        self.ink = (min(xs0), top, max(xs1), bot)
        self.band = (self.ink[0] - c["pad_x"], self.ink[1] - c["pad_y"], self.ink[2] + c["pad_x"], self.ink[3] + c["pad_y"])
        self.s = chars[0]["s"]; self.e = chars[-1]["e"]
