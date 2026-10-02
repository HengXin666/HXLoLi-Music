# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
#   "pillow",
#   "fonttools",
# ]
# ///

"""
用 libass 实测字形“墨迹”位置，计算振假名 / 中文行的精确 y 坐标。

为什么需要：\\an5 的垂直中心是字体行框(ascent+descent)的中心，而不是字形墨迹中心。
不同字体的 ascent/descent 差异很大，凭 fs 估算注音高度往往偏高 10~20px（第一版 ED2 的问题）。
做法：把样本字逐个用 \\an5\\pos(x,y) 渲染到黑底，量出墨迹上下沿相对 y 的偏移，取中位数。

用法:
  hx-karaoke calibrate_ruby.py --fontsdir fonts --jp "Shippori Mincho B1" --jp-fs 66 --jp-bold 1 \\
         --rb "Shippori Mincho B1" --rb-fs 27 --rb-bold 1 --cn "LXGW WenKai Medium" --cn-fs 42 \\
         --jp-y 930 --ruby-gap 5 --cn-gap 16 [--ffmpeg ffmpeg] [--out calib.json]
输出: 各字体墨迹偏移 + 建议 RB_Y / CN_Y（JSON）
"""
import argparse, json, os, subprocess, tempfile
import numpy as np
from PIL import Image

KANJI = "愛学手入戦疲果貴方欲怖背中任壊純矛盾見境守全教目歯尖伝悲顔負素直失未来端隠決涙世界自分感情裏側戻尚強抱離優消去溢出思逃"
KANA = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
HAN = "纵然学会了爱的入门却怎么也无法握在手中我渴望着你无论面对什么都不再害怕"


def render(fontsdir, rows, ffmpeg):
    """rows: [(font, fs, bold, text)] -> 灰度图 + 每个字的 (x, y, fs)"""
    ev, spots = [], []
    y = 90
    for font, fs, bold, text in rows:
        step = int(fs * 1.3)
        x = 80
        for ch in text:
            if x > 1920 - 80:
                x = 80; y += int(fs * 2.2)
            ev.append(f"Dialogue: 0,0:00:00.00,0:00:05.00,S,,0,0,0,,{{\\an5\\pos({x},{y})\\fn{font}\\fs{fs}\\b{bold}}}{ch}")
            spots.append((x, y, fs, font))
            x += step
        y += int(fs * 1.9)
    assert y < 1080, "样本太多，换行溢出画面"
    ass = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nScaledBorderAndShadow: yes\n\n"
           "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
           "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
           "Style: S,Arial,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1\n\n"
           "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" + "\n".join(ev) + "\n")
    d = tempfile.mkdtemp()
    p = os.path.join(d, "c.ass"); png = os.path.join(d, "c.png")
    open(p, "w", encoding="utf-8").write(ass)
    subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=1920x1080:d=1",
                    "-vf", f"subtitles={p}:fontsdir={fontsdir}", "-frames:v", "1", png], check=True)
    return np.asarray(Image.open(png).convert("L")).astype(float), spots


def ink(img, spots, thr=60):
    tops, bots, lefts, rights = [], [], [], []
    for x, y, fs, _ in spots:
        h = int(fs * 0.9); w = int(fs * 0.7)
        win = img[y - h:y + h, x - w:x + w] > thr
        rs = np.where(win.any(1))[0]; cs = np.where(win.any(0))[0]
        if len(rs) == 0:
            continue
        tops.append(rs[0] - h); bots.append(rs[-1] - h); lefts.append(cs[0] - w); rights.append(cs[-1] - w)
    f = lambda a: float(np.median(a))
    return dict(top=f(tops), bottom=f(bots), top_p10=float(np.percentile(tops, 10)), bottom_p90=float(np.percentile(bots, 90)),
                half_w=f([(r - l) / 2 for l, r in zip(lefts, rights)]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fontsdir", required=True); ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--jp", required=True); ap.add_argument("--jp-fs", type=float, default=66); ap.add_argument("--jp-bold", type=int, default=1)
    ap.add_argument("--rb", default=None); ap.add_argument("--rb-fs", type=float, default=27); ap.add_argument("--rb-bold", type=int, default=1)
    ap.add_argument("--cn", default=None); ap.add_argument("--cn-fs", type=float, default=42); ap.add_argument("--cn-bold", type=int, default=0)
    ap.add_argument("--jp-y", type=float, default=930)
    ap.add_argument("--ruby-gap", type=float, default=5, help="注音墨迹底 与 汉字墨迹顶 的间距(px)，建议 3~6")
    ap.add_argument("--cn-gap", type=float, default=16, help="日文墨迹底 与 中文墨迹顶 的间距(px)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    rb = a.rb or a.jp
    rows = [(a.jp, a.jp_fs, a.jp_bold, KANJI[:16]), (a.jp, a.jp_fs, a.jp_bold, KANA[:16]),
            (rb, a.rb_fs, a.rb_bold, KANA[:32])]
    if a.cn:
        rows.append((a.cn, a.cn_fs, a.cn_bold, HAN[:16]))
    img, spots = render(a.fontsdir, rows, a.ffmpeg)
    n1 = 16; n2 = n1 + 16; n3 = n2 + 32
    K = ink(img, spots[:n1]); KA = ink(img, spots[n1:n2]); R = ink(img, spots[n2:n3])
    res = dict(jp_kanji=K, jp_kana=KA, ruby_kana=R)
    # 汉字顶（取偏高的 10 分位，避免高个汉字被注音压住）- 间距 - 注音墨迹底（取偏低的 90 分位）
    rb_off = K["top_p10"] - a.ruby_gap - R["bottom_p90"]
    res["ruby_offset"] = round(rb_off, 1)
    res["RB_Y"] = round(a.jp_y + rb_off, 1)
    if a.cn:
        C = ink(img, spots[n3:]); res["cn"] = C
        cn_off = max(K["bottom_p90"], KA["bottom_p90"]) + a.cn_gap - C["top_p10"]
        res["cn_offset"] = round(cn_off, 1); res["CN_Y"] = round(a.jp_y + cn_off, 1)
    # 整个歌词块（注音顶 ~ 中文底）相对 JP_Y 的墨迹范围，用于计算特效允许区域(band)
    top = rb_off + R["top_p10"]
    bot = (res.get("cn_offset", 0) + res["cn"]["bottom_p90"]) if a.cn else max(K["bottom_p90"], KA["bottom_p90"])
    res["block_ink"] = dict(top=round(top, 1), bottom=round(bot, 1))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if a.out:
        json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
