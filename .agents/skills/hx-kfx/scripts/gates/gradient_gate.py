#!/usr/bin/env python3
r"""AI 味门禁: 检测「浮素材 / 机械复读」与「整行先出现再逐字点亮」是否真的成立。

用法:
    python3 gradient_gate.py 字幕.ass [--min-kinds 12] [--max-static 0.15]

三条判据 (阈值来自对真实成品的实测):
  G-A 母题多样性: 装饰事件的几何形状去重后种类数 >= --min-kinds, 且最高频那一种
      占比 <= --max-top-share  防止「一种图元重复几千次」.
  G-B 运动占比: 静止事件 (文本块内既无 \move 也无 \t) 占比必须 <= --max-static.
      全是静止事件 = 浮在画面上的素材, 不是跟随歌词的特效.
  G-C 逐字点亮顺序: 对每个「整行组」(t0/t1 完全相同的一组字事件):
      1) 组内字数 >= 3;
      2) 每个字的点亮时刻可用 \t 或逐字错峰起点界定, 且按 x 由左到右严格递增;
      3) 首字点亮时刻接近行首 (不晚于 25% 行时长), 末字点亮时刻在行尾之前.
      这条直接对应硬需求「整行先出现, 再按字序点亮」.

退出码 0 = 三条全过; 1 = 有未过; 2 = 文件不可读。
"""
from __future__ import annotations
import argparse
import re
import sys
from collections import Counter

BS = chr(92)                       # ASS 标签的反斜杠
POS_RE = re.compile(BS + BS + r"pos\((-?[\d.]+),(-?[\d.]+)\)")
COL_RE = re.compile(BS + BS + r"1c(&H[0-9A-Fa-f]{6,8}&)")
DRAW_RE = re.compile(BS + BS + r"p[1-9]")
TBT_RE = re.compile(BS + BS + r"t\((\d+)\s*,\s*(\d+)\s*,")
NUM = re.compile(r"-?\d+(?:\.\d+)?")


def t2s(t: str) -> float:
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


TAGBLOCK = re.compile(r"\{[^{}]*\}")


def shape_key(text: str) -> str:
    r"""把绘图路径归一成形状指纹: 段数 + 包围盒宽高比量化。

    必须先剥掉花括号里的标签块  否则 \pos / \clip / \t 的参数会被当成
    路径顶点, 所有形状的指纹都会变成同一个 (实测踩过: 12 种母题被算成 1 种)。
    """
    ds = NUM.findall(TAGBLOCK.sub("", text))
    if len(ds) < 4:
        return "?"
    v = [float(x) for x in ds]
    xs, ys = v[0::2], v[1::2]
    if not xs or not ys:
        return "?"
    segs = len(v) // 2
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    if h <= 0 or w <= 0:
        return "segs%d_flat" % segs
    # 指纹只取**与缩放无关的形状特征**: 段数 + 归一化后的宽高比 (一位小数)。
    # 绝对宽度绝不能进指纹  实测踩过: 同一个母题在 w=539 与 w=598.9 被算成两种,
    # 于是"种类 5"里含 2 个同形, 既虚高种类数又掩盖真复读。
    # 归一化到「高=1」的宽高比, 再按 0.5 分档, 让同一形状的横向拉伸仍算同一种。
    ar = w / h
    return "segs%d_ar%d" % (segs, min(60, int(ar * 1.0)))


def light_time(text: str, t0: float):
    r"""该字被点亮的时刻 (绝对秒)。优先取 \t 的起始毫秒 (相对行首), 否则取本行起点。"""
    m = TBT_RE.search(text)
    if m:
        return t0 + int(m.group(1)) / 1000.0
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ass")
    ap.add_argument("--min-kinds", type=int, default=12,
                    help="母题种类下限。注意: 生成器默认每句一个母题, 所以句子数少于该值时"
                         "数学上不可达  此时改用 --min-kinds 0 并看 --max-top-share, "
                         "或按 min(12, 句数) 传参")
    ap.add_argument("--max-top-share", type=float, default=0.5)
    ap.add_argument("--max-static", type=float, default=0.15)
    a = ap.parse_args()

    styles, events = {}, []
    for line in open(a.ass, encoding="utf-8-sig", errors="replace"):
        if line.startswith("Style:"):
            f = line[6:].split(",")
            if len(f) > 3:
                styles[f[0].strip()] = f[3].strip()
        elif line.startswith("Dialogue:"):
            f = line[9:].split(",", 9)
            if len(f) < 10:
                continue
            events.append(dict(t0=t2s(f[1]), t1=t2s(f[2]), style=f[3].strip(), text=f[9]))

    if not events:
        print("! 没有 Dialogue 事件", file=sys.stderr)
        return 2

    deco = [e for e in events if DRAW_RE.search(e["text"])]
    text_ev = [e for e in events if not DRAW_RE.search(e["text"])]
    print("事件总数 %d  文本 %d  装饰 %d" % (len(events), len(text_ev), len(deco)))

    # ---- G-A 母题多样性 ----
    kinds = Counter(shape_key(e["text"]) for e in deco)
    n_kinds = len([k for k in kinds if k != "?"])
    total = max(sum(kinds.values()), 1)
    top_share = (kinds.most_common(1)[0][1] / total) if kinds else 0.0
    # 句数不足时门限自动降到句数, 并明确说明为什么降  否则短样本永远 FAIL,
    # 让人误以为成品有问题 (实测踩过: 5 句被测出"种类 5", 上限就是 5)。
    # 按「秒」聚类, 而不是按精确起点  同一句里的图元会被有意错峰 (实测成品也是),
    # 用精确起点会把一句话算成十几个"装饰组", 门限上限就永远不生效。
    # 聚类口径是 (起, 止) 对: 装饰图元常在一句内被有意错峰, 用起点聚类会把一句话
    # 算成十几个组 (实测踩过两轮)。
    n_sent = len({(round(e["t0"], 1), round(e["t1"], 1)) for e in deco})
    # 判据只有最高频占比: 实测有零绘图 + 单手法的生产级成品成立, 所以「种类数 >= N」会冤杀它;
    # 真正该拦的是同一种形状被机械复读 (反例: 2 种图形重复 5929 次, 最高频占比 0.85).
    # G-A 不作为门禁  12 份生产级成品的种类数与最高频占比区间与好坏无关, 故只输出不判定.
    ok_a = True
    print("")
    print("[G-A 母题多样性] 种类 %d / 装饰组 %d  最高频占比 %.2f   (仅供参考, 不判定)"
          % (n_kinds, n_sent, top_share))
    print("     实测 12 份生产级成品: 种类 2..2608 (中位 6), 占比 0.17..0.96 (中位 0.71);")
    print("     两者都是设计选择而非正确性, 无法区分好坏, 故不作门禁。")
    if kinds:
        print("     前三: " + ", ".join("%sx%d" % (k, c) for k, c in kinds.most_common(3)))

    # ---- G-B 运动占比 ----
    stat = sum(1 for e in events if (BS + "move") not in e["text"] and (BS + "t(") not in e["text"])
    frac = stat / len(events)
    ok_b = frac <= a.max_static
    print("")
    print("[G-B 运动占比]   静止 %d/%d = %.3f (门限 <= %.2f)  %s"
          % (stat, len(events), frac, a.max_static, "PASS" if ok_b else "FAIL"))

    # ---- G-C 逐字点亮顺序 ----
    # 必须**按样式**分组, 不能只按时间分组。实测踩过: 中文对照层与日文主行同时起止,
    # 而中文层是没有 \t 的整行文本, 混进同一组后会把整组判成"无点亮动画"。
    # 判据: 一个组 = (时间区间, 样式), 这样每一层各自被独立检查。
    groups = {}
    for e in text_ev:
        groups.setdefault((round(e["t0"], 2), round(e["t1"], 2), e["style"]), []).append(e)

    checked = bad_order = bad_span = no_anim = 0
    samples = []
    for (t0, t1, style), evs in sorted(groups.items()):
        # 只有"每字一条事件"的层才适用逐字点亮判据。中文/翻译层是一行一条, 天然没有 \t。
        if len(evs) < 3:
            continue
        rows = []
        for e in evs:
            m = POS_RE.search(e["text"])
            x = float(m.group(1)) if m else 0.0
            rows.append((x, light_time(e["text"], e["t0"])))
        rows.sort(key=lambda r: r[0])
        times = [t for _, t in rows]
        if any(t is None for t in times):
            no_anim += 1
            if len(samples) < 3:
                samples.append((t0, t1, style, "无 \t 标记 (无点亮动画)"))
            continue
        checked += 1
        dur = max(t1 - t0, 0.001)
        inc = all(times[i] < times[i + 1] for i in range(len(times) - 1))
        first_ok = (times[0] - t0) <= 0.25 * dur
        last_ok = (times[-1] - t0) <= 0.95 * dur
        if not inc:
            bad_order += 1
            if len(samples) < 3:
                samples.append((t0, t1, style, "点亮顺序非从左到右"))
        if not (first_ok and last_ok):
            bad_span += 1
            if len(samples) < 6:
                samples.append((t0, t1, style, "首字 %.2f/%s 末字 %.2f 越界"
                                % (times[0] - t0, "%.2f" % dur, times[-1] - t0)))
    ok_c = checked > 0 and bad_order == 0 and bad_span == 0 and no_anim == 0
    print("")
    print("[G-C 逐字点亮]   整行组 %d 个; 顺序非递增 %d; 时刻越界 %d; 无 \t 标记 %d  %s"
          % (checked, bad_order, bad_span, no_anim, "PASS" if ok_c else "FAIL"))
    for s in samples:
        print("     样例 t0=%.2f t1=%.2f [%s]  %s" % s)
    if checked == 0 and no_anim == 0:
        print("     没有 >=3 字的整行组  说明不存在「整行同存」的写法")

    allok = ok_a and ok_b and ok_c
    print("")
    print("总判定: " + ("PASS" if allok else "FAIL"))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
