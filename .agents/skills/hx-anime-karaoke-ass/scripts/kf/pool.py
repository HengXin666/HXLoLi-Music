# -*- coding: utf-8 -*-
"""整曲字符池兜底: 逐行匹配失败时, 在全局字符序里定位本行.

为什么需要: lyrics.txt 的分句不必与歌词站一致(实测有工程把一句拆成两行), 逐行文本匹配
就全落空. 但两边的**字符序**是同一个, 所以在整曲尺度上做一次字符级对齐, 再按每个音拍落在
哪个字符上取时间  分句差异就不再是障碍.

决策与实测依据: 
"""
import bisect

from difflib import SequenceMatcher

from kf.shape import _to_morae, lddc_char_stream, mora_char_map


def build_global_pool(kf):
    """把 kf 的全部逐字按时间铺成一条**全局**序列，用于行级匹配失败时兜底。

    为什么需要：`lyrics.txt` 的分句**不必**与歌词站一致  实测有工程把
    「錆びて消えない孤独の寂しさを抱いた不器用な微笑み」拆成了两行，逐行文本匹配就全落空。
    但两边的**字符序**是同一个，所以可以在整曲尺度上做一次字符级对齐，
    再按每个音拍落在哪个字符上取时间。这样分句差异就不再是障碍。
    """
    chars, times = [], []
    for l in kf["lines"]:
        c, t = lddc_char_stream(l["words"])
        chars.append(c)
        times.extend(t)
    return "".join(chars), times


# Agent Notes: hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开
# 
def shape_from_pool(ln, pool_chars, pool_times, win=12.0):
    """
    .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
    .agents/notes/implemented/process/2026-10-05-karaoke-scripts-grouping.md
行级匹配失败时的兜底：在全局字符池里定位本行，返回相对首音拍的时间。

    判据用**最长公共块占本行字符数的比例**（默认 0.5）。太低说明不是同一句，
    宁可不给也别给错的  返回 None 后调用方会把这行记入 `miss` 让人看见。
    """
    a, starts, n_mora = mora_char_map(ln)
    if not a or not n_mora:
        return None
    # 用**锚定窗口**取匹配块，而不是全曲自由匹配：
    # 本行常跨 LDDC 的行边界（实测「寂しさを抱いた不器用な微笑み」被歌词站拆在相邻两行），
    # 所以要允许非单块；但全曲自由匹配会被**副歌重复**骗到远处的同文句 
    # 实测因此出现跨度 145s 的 shape（本地只有 6.98s），夹取 54 个音拍才救回来。
    # 解法：先用最长块定位一个时间中心，只在该中心 ±win 秒的池区间里取全部匹配块。
    blk0 = SequenceMatcher(None, a, pool_chars, autojunk=False).find_longest_match(
        0, len(a), 0, len(pool_chars))
    if blk0.size < max(3, len(a) * 0.35):
        return None
    center = pool_times[blk0.b + blk0.size // 2]
    lo = bisect.bisect_left(pool_times, center - win)
    hi = bisect.bisect_right(pool_times, center + win)
    if hi - lo < 4:
        return None
    sub_pool = pool_chars[lo:hi]
    # 池路径只用于"这句在逐行匹配里落空"的情况，它的头尾靠外推，精度天然低于行匹配。
    # 所以把外推限制在一拍以内，宁可让句首/句尾各留一拍在原地，也不要甩出去几秒
    # （实测未限制时出现过 145s 的 shape，本地只有 6.98s）。
    vals = [None] * len(a)
    n_hit = 0
    for blk in SequenceMatcher(None, a, sub_pool, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            if blk.b + k < len(sub_pool):
                vals[blk.a + k] = pool_times[lo + blk.b + k]
                n_hit += 1
    if n_hit < max(3, len(a) * 0.5):
        return None
    # Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
    # 
    known = [(i, t) for i, t in enumerate(vals) if t is not None]
    if len(known) < 2:
        return None
    # 头尾外推：用**已匹配段内部**的中位字符耗时，而不是硬编码 0.18s/字。
    # 硬编码在慢歌上会把句首/句尾推出去很远（实测某工程外推量大到需要夹取 54 个音拍）。
    ivs = []
    prev = None
    for i, t in known:
        if prev is not None and t > prev[1] and i > prev[0]:
            ivs.append((t - prev[1]) / (i - prev[0]))
        prev = (i, t)
    step = float(sorted(ivs)[len(ivs) // 2]) if ivs else 0.18
    step = max(0.06, min(0.45, step))
    # 外推上限：最多 3 个字符的时长（约一拍）。超出部分直接平移，不再继续拉长跨度。
    first_i, first_t = known[0]
    for i in range(first_i):
        vals[i] = first_t - min(first_i - i, 3) * step
    last_i, last_t = known[-1]
    for i in range(last_i + 1, len(a)):
        vals[i] = last_t + min(i - last_i, 3) * step
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
    for i in range(1, len(vals)):
        if vals[i] < vals[i - 1]:
            vals[i] = vals[i - 1]
    return _to_morae(vals, starts, n_mora)

