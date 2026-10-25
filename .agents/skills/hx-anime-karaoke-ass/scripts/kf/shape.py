# -*- coding: utf-8 -*-
"""句内形状: 把 LDDC 的**字级**逐字时间摊到本地歌词的**音拍**上, 得到相对首音拍的时间.

这一层是 kf 通道的精度来源: 整体平移由本地 CTC 的行首决定(见 kf/align.py), 而句内
每个音拍的相对位置必须来自网络逐字  CTC 在长音/间奏处会塌缩, 且塌缩不能从 CTC 自身察觉.

决策与实测依据: 
"""
import bisect

from difflib import SequenceMatcher

import json
import re


# ---------------------------------------------------------------- 形状与锚点

def lddc_char_stream(words):
    """LDDC 逐字 -> (显示字符流, 每字符时间)。

    **关键：这里必须用显示文本（`surf` 所指的原文，含汉字），不能转成假名。**
    因为 `lyrics.txt` 里对应位置是**汉字**（`[錆|さ]` 的 surf 是「錆」），
    拿注音「さ」去比原文「錆」会天然不匹配  实测因此把 4 行整句丢掉。
    """
    chars, times = [], []
    for w in words:
        if w["s"] is None:
            continue
        for c in str(w["t"]):
            chars.append(c)
            times.append(w["s"])
    return "".join(chars), times


def mora_char_map(ln):
    """音拍序列 -> (显示字符流, 每音拍所属的字符下标, 音拍数)。

    显示字符流**必须就是 `u["surf"]` 本身**，与 LDDC 的字符流同一坐标系  这是整条链路的关键。

    踩过的坑（务必别改回去）：曾经在「音拍数 > 字符数」时用假名占位
    （「人」= ひ+と 就写成 "ひと"），以为能靠插入对齐。结果坐标系从假名换成了汉字，
    跟 LDDC 的「人」对不上，**整行从第二个 unit 起全部错位**（实测 MAE 0.244s，
    而正确写法是 0.023s）。正确做法是让一字多拍的几个音拍**共享同一个字符下标**，
    对齐后再按"下一个字符的时间 − 这个字符的时间"在字内均分。
    """
    ms = [(ui, mi, m) for ui, u in enumerate(ln["units"]) if u["kind"] != "space"
          for mi, m in enumerate(u["morae"])]
    if not ms:
        return "", [], 0
    chars, starts = [], []
    for u in ln["units"]:
        if u["kind"] == "space":
            continue
        n, nm = len(u["surf"]), len(u["morae"])
        if nm == 0:
            continue
        base = len(chars)
        chars.extend(u["surf"])
        for mi in range(nm):
            # 音拍 mi 落在该 unit 的第 round(mi*n/nm) 个字符上；
            # 字少拍多时多个音拍共享同一字符（后续做字内均分）。
            starts.append(base + min(n - 1, round(mi * n / nm)) if n else base)
    return "".join(chars), starts, len(ms)


def _align_chars(a, a_times_anchor, b, b_times):
    """把 A 串（待求时间）对齐到 B 串（有时间），返回 A 每个字符的时间。

    a_times_anchor: A 里已知时间的字符下标 -> 时间（通常为空，靠 B 推）
    b_times: B 每字符的时间
    """
    idx = [-1] * len(a)
    for blk in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            if blk.b + k < len(b_times):
                idx[blk.a + k] = blk.b + k
    known = [(i, b_times[j]) for i, j in enumerate(idx) if j >= 0]
    if len(known) < 2:
        return None
    vals = [None] * len(a)
    for i, t in known:
        vals[i] = t
    first_i, first_t = known[0]
    for i in range(first_i):
        vals[i] = first_t - (first_i - i) * 0.18
    last_i, last_t = known[-1]
    for i in range(last_i + 1, len(a)):
        vals[i] = last_t + (i - last_i) * 0.18
    k = 0
    for i in range(len(a)):
        if vals[i] is not None:
            k = i
            continue
        j = i
        while j < len(a) and vals[j] is None:
            j += 1
        vj = vals[j] if j < len(a) else vals[k]
        span = j - k
        vals[i] = vals[k] + (vj - vals[k]) * (i - k) / span if span else vals[k]
    for i in range(1, len(a)):
        if vals[i] < vals[i - 1]:
            vals[i] = vals[i - 1]
    return vals


def shape_quality(sh):
    """句内形状的可信度：相邻音拍起点的差分里，>40ms 的占比。

    为什么需要这个量：LDDC 是**字级**的，而拉丁单元（`{Like a lotus|らいくあろーたす}`）
    与 LDDC 的罗马字原词（"Like "/"a "/"lotus"）对不上，SequenceMatcher 会把多个音拍
    映射到同一个字符，于是形状出现一串 0（实测某工程 line 27/31：8 拍里 4 拍起点完全相同、
    中间一个 2.02s 的跳变）。这种形状会把整行压成一团，必须判出来回退，
    而不是让它带着垃圾形状进融合  融合只会把它加到一个锚点上，形状错不会被稀释。
    """
    if not sh or len(sh) < 2:
        return 0.0
    d = [sh[i + 1] - sh[i] for i in range(len(sh) - 1)]
    return sum(1 for x in d if x > 0.04) / len(d)


def local_shape(timing, li):
    """本地 CTC 的句内形状（该行音拍起点相对首拍）。仅作形状质量不足时的回退。"""
    ms = sorted([m for m in timing if m["line"] == li], key=lambda m: (m["unit"], m["mora"]))
    if not ms:
        return None
    s0 = ms[0]["s"]
    return [round(m["s"] - s0, 3) for m in ms]


def shape_for_line(ln, words):
    """把一行的 LDDC 逐字时间摊到该行的每个音拍上，返回**相对**首音拍的偏移（秒）。"""
    a, starts, n_mora = mora_char_map(ln)
    if not a or not n_mora:
        return None
    b, b_times = lddc_char_stream(words)
    if not a or not b:
        return None
    vals = _align_chars(a, {}, b, b_times)
    if vals is None:
        return None
    return _to_morae(vals, starts, n_mora)





def line_starts(timing):
    """从本地 timing（timing_auto/snap/json）拿每行的首拍起点。"""
    d = {}
    for m in timing:
        if m.get("call"):
            continue
        li = m["line"]
        if li not in d or m["s"] < d[li]:
            d[li] = m["s"]
    return d


def line_ends(timing):
    d = {}
    for m in timing:
        if m.get("call"):
            continue
        li = m["line"]
        if li not in d or m["e"] > d[li]:
            d[li] = m["e"]
    return d


def _to_morae(vals, starts, n_mora):
    """字符级时间 -> 音拍级：同字符上的多个音拍按「到下个字符的间隔」在字内均分。"""
    cnt = {}
    for k in range(n_mora):
        cnt[starts[k]] = cnt.get(starts[k], 0) + 1
    seen, last_iv, per_mora = {}, 0.25, []
    for k in range(n_mora):
        c = starts[k]
        t, m = vals[c], cnt[c]
        if m > 1:
            nxt = vals[c + 1] if c + 1 < len(vals) else t + last_iv * m
            iv = max(0.05, (nxt - t) / m)
            last_iv = iv
            j = seen.get(c, 0)
            seen[c] = j + 1
            t = t + iv * j
        per_mora.append(t)
    for k in range(1, n_mora):
        if per_mora[k] < per_mora[k - 1]:
            per_mora[k] = per_mora[k - 1]
    base = per_mora[0]
    return [round(v - base, 4) for v in per_mora]


def kata2hira(s):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def norm(s):
    return re.sub(r"[\s　]+", "", s or "")


PUNCT = "「」『』（）()【】[]〔〕・、。，,.!?！？:：;；~〜ー-—…♪☆★"


def key(s):
    """行匹配键：去空白与标点 + 片假名转平假名."""
    return "".join(c for c in kata2hira(norm(s)) if c not in PUNCT)


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)
