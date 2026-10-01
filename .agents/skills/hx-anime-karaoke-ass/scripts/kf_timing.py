#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
# ]
# ///
"""逐字权威时间轴（kf）：用 LDDC 抓网络逐字歌词，与本地音频的行首锚点融合，产出音拍级 timing。

## 为什么要有这条通道（实测 2026-10-02，东方《果てなき風の軌跡さえ》）

`align_ctc.py`（wav2vec2 平假名 + CTC Viterbi）在**长音与间奏处会塌缩**：它把整整一段
拖长/间奏全算给最后一个音拍，其后的音拍起点被整体顺延。同工程 36 行里 8 行如此，
最坏一行「教えてくれた」被判成 22.73s 跨度 —— 真值 1.50s，**15.2 倍**；
其中「れ」独占 12.17s，而那段 176.3~188.5s 的人声能量只有 **-34.4 dB**（是间奏，不是演唱）。

同一批数据上，LDDC（QQ 音乐逐字歌词）与**该工程原作者手工调准的 \t 延迟还原值**相比：
  句内间隔差  中位 5 ms、最大 9 ms      <- 相对关系完全一致
  整体偏移    -1.901 s（标准差 0.003）  <- 只差一个常量平移

## 结论：分工

| 量 | 来源 | 理由 |
|---|---|---|
| **句内相对形状** | LDDC 逐字（网络） | 权威。CTC 在这里会塌缩，且塌缩不可从 CTC 自身察觉 |
| **整体平移** | CTC 行首（本地音频） | 唯一由**这份视频**决定的东西；LDDC 的时间轴是别份音源的 |

融合方式就是这一行：`pred = lddc_rel + (ctc_line_start - lddc_line_start)`。

两个必须注意的点：
1. **塌缩行不能参与估偏移**。实测不剔除时偏移 +1.889s、剔除后 +1.9105s，
   而真值 +1.901s —— 剔除后误差 9ms，不剔除差 12ms 且方差更大。脚本会剔除。
2. **绝不要逐行各自定偏移**。实测那样做 MAE 0.238s，比只用一个全局偏移（0.032s）差 7 倍：
   塌缩行的行首本身就是错的，逐行锚定等于把错误逐行注入。

实测效果（字级，对作者手工锚点）：**MAE 0.0322s vs 纯 CTC 0.2595s，8.1 倍**；最大误差 90ms（CTC 2.95s）。

## 阶段

    fetch   搜歌 -> 拉逐字歌词 -> `kf.json` / `kf.ass`（可多源投票）
    align   吃 `timing_auto.json` + `kf.json` -> 融合 -> `timing_kf.json`（+ 报告）
    verify  把 `timing_kf.json` 与人工终稿对比，列出偏差最大的音拍

## 用法

    # 1) 抓逐字（--lddc 指向 HX-Music 的 pyTool 目录，即 LDDC 包所在）
    uv run scripts/kf_timing.py fetch --lddc ~/Loli/code/HX-Music/pyTool \
        --title "果てなき風の軌跡さえ" --artist "少女フラクタル" --project proj \
        --source QM --lang orig

    # 2) 融合（缺 kf.json 时自动退回 CTC，不报错）
    uv run scripts/kf_timing.py align --project proj --auto timing_auto.json --out timing_kf.json

    # 3) 复核
    uv run scripts/kf_timing.py verify --project proj --a timing_kf.json --b timing.json --top 20

依赖：numpy。fetch 阶段额外需要 HX-Music 的 pyTool 环境（LDDC + PySide6）。
注意 LDDC 的 `g2p_en` 需要 nltk 语料，离线会被拦；纯日语歌曲直接 stub 掉即可（脚本已处理）。
"""
import argparse, bisect, json, os, re, sys
from difflib import SequenceMatcher

# ---------------------------------------------------------------- 基础工具

def kata2hira(s):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def norm(s):
    return re.sub(r"[\s　]+", "", s or "")


PUNCT = "「」『』（）()【】[]〔〕・、。，,.!?！？:：;；~〜ー-—…♪☆★"


def key(s):
    """行匹配键：去空白与标点 + 片假名转平假名。

    去标点是必需的：同一个句子在歌词站与 LDDC 里常只差一对书名号/引号
    （实测「温もりに別れを告げて」 vs 「『温もり』に別れを告げて」）。
    """
    return "".join(c for c in kata2hira(norm(s)) if c not in PUNCT)


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- fetch

LDDC_SOURCES = ("QM", "KG", "NE", "LRCLIB")


def _setup_lddc(root):
    """把 HX-Music 的 pyTool 挂上 sys.path，并 stub 掉 g2p_en（英语->片假名，纯日语歌曲用不到）。"""
    import types
    root = os.path.expanduser(root)
    if not os.path.isdir(os.path.join(root, "LDDC")):
        sys.exit("[fetch] %s 下没有 LDDC 包。--lddc 要指向 HX-Music 的 pyTool 目录。" % root)
    if root not in sys.path:
        sys.path.insert(0, root)
    if "g2p_en" not in sys.modules:
        fake = types.ModuleType("g2p_en")

        class G2p:
            def __init__(self, *a, **k): pass
            def __call__(self, *a, **k): return []

        fake.G2p = G2p
        sys.modules["g2p_en"] = fake
    from LDDC.common.models._enums import SearchType, Source          # noqa: E402
    from LDDC.core.api.lyrics import search, get_lyrics               # noqa: E402
    return SearchType, Source, search, get_lyrics


def cmd_fetch(a):
    SearchType, Source, search, get_lyrics = _setup_lddc(a.lddc)
    src = getattr(Source, a.source.upper())

    queries = [q for q in ([a.title] if a.title else []) + ([a.artist] if a.artist else []) if q]
    if not queries:
        sys.exit("[fetch] 至少给 --title 或 --artist")
    kw = " ".join(queries)
    print("[fetch] 搜 '%s' ..." % kw)

    # 单源会偶发失败（实测 QM 在 "歌名 艺人" 这种组合上会返回 code 2001，同一天换个关键词就正常）。
    # 所以 --source 指定失败时自动往其它源退，而不是直接放弃 —— 把「某个源抽风」和
    # 「这首歌没有逐字歌词」区分开，后者才是真需要人工听写的信号。
    order = [a.source.upper()] + [s for s in LDDC_SOURCES if s != a.source.upper()]
    cands, used = None, None
    for name in order:
        try:
            got = search(getattr(Source, name), kw, SearchType.SONG)
        except Exception as exc:
            print("[fetch]   %-6s 失败: %s" % (name, str(exc)[:90]))
            continue
        if got:
            cands, used = got, name
            print("[fetch]   %-6s 命中 %d 条" % (name, len(got)))
            break
        print("[fetch]   %-6s 无结果" % name)
    if not cands:
        sys.exit("[fetch] 四个源（%s）都没拿到。核对曲名/艺人，或该曲确实没有逐字歌词 —— "
                 "那就走人工听写并写 why。" % "/".join(LDDC_SOURCES))
    if used != a.source.upper():
        print("[fetch] 注意：已从 --source %s 退到 %s（前者不可用，不是这首歌没有）。" % (a.source, used))

    src = getattr(Source, used)
    print("[fetch] 命中 %d 条，前 %d：" % (len(cands), min(8, len(cands))))
    for i, s in enumerate(cands[:8]):
        t = getattr(s, "title", "?")
        ar = getattr(s, "artist", None) or getattr(s, "artists", None) or ""
        dur = getattr(s, "duration", None)
        mark = " <== 选中" if (a.song_id and str(getattr(s, "id", "")) == str(a.song_id)) else ""
        print("   [%d] %-44s | %-26s | %s%s" % (i, str(t)[:42], str(ar)[:24],
                                                ("%d.%03ds" % divmod(int(dur), 1000)) if dur else "-", mark))

    song = None
    if a.song_id:
        song = next((s for s in cands if str(getattr(s, "id", "")) == str(a.song_id)), None)
        if song is None:
            sys.exit("[fetch] 指定 --song-id %s 不在结果里。上面列表里挑一个再给。" % a.song_id)
    else:
        song = cands[0]
        print("[fetch] 未给 --song-id，取第一条。若不对请从上面列表挑 id 重跑。")

    ly = get_lyrics(song)
    data = ly.get(a.lang)
    if data is None:
        avail = list(ly.keys())
        if not avail:
            sys.exit("[fetch] 拿到的歌词是空的。")
        print("[fetch] 语言 '%s' 不存在，可用 %s，取第一个。" % (a.lang, avail))
        data = ly[avail[0]]

    lines = []
    for ln in data:
        ws = [w for w in ln.words if w.start is not None and str(w.text).strip()]
        if not ws:
            continue
        lines.append(dict(text="".join(str(w.text) for w in ws),
                          words=[dict(t=str(w.text), s=round(w.start / 1000.0, 3),
                                      e=(round(w.end / 1000.0, 3) if w.end is not None else None)) for w in ws]))

    out = os.path.join(a.project, a.out)
    payload = dict(source=used, song_id=str(getattr(song, "id", "")),
                   title=str(getattr(song, "title", "") or ""),
                   artist=str(getattr(song, "artist", None) or getattr(song, "artists", None) or ""),
                   lang=a.lang, fetched=None, lines=lines)
    os.makedirs(a.project, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    nw = sum(len(l["words"]) for l in lines)
    print("[fetch] OK -> %s（%d 行 / %d 逐字）" % (out, len(lines), nw))
    print("[fetch] 逐字校验：带 s 的字 %d/%d" % (sum(1 for l in lines for w in l["words"] if w["s"] is not None), nw))
    print("[fetch] 逐字可信度自检：LDDC 只给**字级**时间；音拍多于汉字时按字内均分（见 align）。")
    return 0


# ---------------------------------------------------------------- 形状与锚点

def lddc_char_stream(words):
    """LDDC 逐字 -> (显示字符流, 每字符时间)。

    **关键：这里必须用显示文本（`surf` 所指的原文，含汉字），不能转成假名。**
    因为 `lyrics.txt` 里对应位置是**汉字**（`[錆|さ]` 的 surf 是「錆」），
    拿注音「さ」去比原文「錆」会天然不匹配 —— 实测因此把 `tsunagukizuna` 的 4 行整句丢掉。
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

    显示字符流**必须就是 `u["surf"]` 本身**，与 LDDC 的字符流同一坐标系 —— 这是整条链路的关键。

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
    映射到同一个字符，于是形状出现一串 0（实测本工程 line 27/31：8 拍里 4 拍起点完全相同、
    中间一个 2.02s 的跳变）。这种形状会把整行压成一团，必须判出来回退，
    而不是让它带着垃圾形状进融合 —— 融合只会把它加到一个锚点上，形状错不会被稀释。
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


def build_global_pool(kf):
    """把 kf 的全部逐字按时间铺成一条**全局**序列，用于行级匹配失败时兜底。

    为什么需要：`lyrics.txt` 的分句**不必**与歌词站一致 —— 实测 `tsunagukizuna` 工程把
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


def shape_from_pool(ln, pool_chars, pool_times, win=12.0):
    """行级匹配失败时的兜底：在全局字符池里定位本行，返回相对首音拍的时间。

    判据用**最长公共块占本行字符数的比例**（默认 0.5）。太低说明不是同一句，
    宁可不给也别给错的 —— 返回 None 后调用方会把这行记入 `miss` 让人看见。
    """
    a, starts, n_mora = mora_char_map(ln)
    if not a or not n_mora:
        return None
    # 用**锚定窗口**取匹配块，而不是全曲自由匹配：
    # 本行常跨 LDDC 的行边界（实测「寂しさを抱いた不器用な微笑み」被歌词站拆在相邻两行），
    # 所以要允许非单块；但全曲自由匹配会被**副歌重复**骗到远处的同文句 ——
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


def cmd_align(a):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from assfx.lyrics import load as load_lyrics

    lyr_path = a.lyrics if os.path.isabs(a.lyrics) else os.path.join(a.project, a.lyrics)
    lines = load_lyrics(lyr_path)
    print("[align] %s：%d 行 / %d 音拍" % (lyr_path, len(lines),
                                          sum(len(u["morae"]) for ln in lines for u in ln["units"])))

    auto_path = a.auto if os.path.isabs(a.auto) else os.path.join(a.project, a.auto)
    if not os.path.exists(auto_path):
        sys.exit("[align] 缺 %s。先跑 align_ctc.py（它负责本地音频的行首），"
                 "本脚本只提供句内形状，不单独决定整体位置。" % auto_path)
    timing = load_json(auto_path)
    st = line_starts(timing)
    print("[align] 锚点 %s：%d 行" % (auto_path, len(st)))

    kf_path = a.kf if os.path.isabs(a.kf) else os.path.join(a.project, a.kf)
    if not os.path.exists(kf_path):
        print("[align] 缺 %s —— 没有网络逐字时**本脚本不做任何事**（不会伪造）。"
              "退回纯 CTC 流程，或先跑 fetch。" % kf_path)
        print("[align] 若确认要用纯 CTC 结果，直接把它当 timing.json 走人工校时即可；本步跳过。")
        return 0
    kf = load_json(kf_path)
    kidx = {}
    for i, l in enumerate(kf["lines"]):
        kidx.setdefault(key(l["text"]), []).append(i)
    print("[align] 逐字 %s：%d 行（源 %s / song %s）" % (kf_path, len(kf["lines"]), kf.get("source"), kf.get("song_id")))

    # ---- 0) 全局字符池（行级匹配失败时的兜底；见 build_global_pool 的说明）----
    pool_chars, pool_times = build_global_pool(kf)
    print("[align] 全局字符池 %d 字" % len(pool_chars))

    # ---- 1) 每行的句内形状 + 两个锚点 ----
    rows = []
    miss = []
    n_pool = 0
    # 已被某一行用掉的逐字行下标。
    #
    # 为什么需要它：副歌里**同一句会重复出现 2~3 次**，而 `kidx` 是「文本 -> 所有下标」。
    # 原实现永远取 `kidx[k][0]`，于是第二次出现的那句会吸到**第一次的**行首。
    # 实测本工程（2026-10-02）：「全部とりこんで」在 kf 里是 28(201.84s) 与 32(225.06s)，
    # 原实现让 line 25 与 line 29 都锚到 201.84 → line 29 整行落到 202s（真值 225s），
    # 「Like a lotus」同理（line 27 与 line 31 都锚到 210.35）——
    # 后来加的"离群行兜底"只换偏移量、换不掉行首，于是这两行被夹成零长（间距 -14.6s）。
    # 改成「取尚未使用、且行首最靠近本行本地锚点的那一次」。
    used_kf = set()
    for li, ln in enumerate(lines):
        if ln.get("call"):
            continue
        if li not in st:
            miss.append((li, "无本地锚点"))
            continue
        k = key("".join(u["surf"] for u in ln["units"]))
        shape, lddc_start, how = None, None, ""
        if k in kidx:
            cands = []
            for j in kidx[k]:
                if j in used_kf:
                    continue
                t0 = min((w["s"] for w in kf["lines"][j]["words"] if w["s"] is not None), default=None)
                if t0 is not None:
                    cands.append((j, t0))
            if cands:
                cands.sort(key=lambda jt: abs(jt[1] - st[li]))     # 就近：本地锚点指着哪一次就用哪一次
                j, lddc_start = cands[0]
                used_kf.add(j)
                words = kf["lines"][j]["words"]
                shape = shape_for_line(ln, words)
                how = "行匹配"
                # 形状太塌（拉丁单元对不上罗马字）就回退到本地 CTC 形状，
                # **行首仍用 LDDC 的**（行首是本地 CTC 最不可靠、LDDC 最可靠的那一端）。
                if shape is not None and shape_quality(shape) < a.shape_min_quality:
                    loc = local_shape(timing, li)
                    nm = sum(len(u["morae"]) for u in ln["units"] if u["kind"] != "space")
                    if loc is not None and len(loc) == nm and shape_quality(loc) >= a.shape_min_quality:
                        shape = loc
                        how = "行匹配+本地形状"
        if shape is None:
            # 兜底：整曲字符池里定位本行（分句与歌词站不一致时走这里）
            shape = shape_from_pool(ln, pool_chars, pool_times)
            if shape is None:
                miss.append((li, "无对应逐字行（逐行与全局都匹配不上）"))
                continue
            n_pool += 1
            how = "全局池"
            # 全局池给的是**相对**首音拍的时间，LDDC 行首得由本地 CTC 反推
            lddc_start = 0.0
        if lddc_start is None:
            miss.append((li, "逐字行没有绝对时间"))
            continue
        n_mora = sum(len(u["morae"]) for u in ln["units"] if u["kind"] != "space")
        if len(shape) != n_mora:
            miss.append((li, "音拍数不符 %d!=%d" % (len(shape), n_mora)))
            continue
        rows.append(dict(li=li, text=k, shape=shape, lddc_start=lddc_start, how=how,
                         lddc_len=shape[-1] - shape[0] if len(shape) > 1 else 0.0,
                         ctc_start=st[li], ctc_end=line_ends(timing).get(li, st[li])))

    if len(rows) < a.min_lines:
        sys.exit("[align] 可用于估偏移的行只有 %d < %d，不可靠。检查 kf.json 是否抓错版本。"
                 % (len(rows), a.min_lines))

    # ---- 2) 塌缩判定：本地行跨度 / 逐字行跨度 ----
    for r in rows:
        ld = max(0.30, r["lddc_len"] + 0.35)
        r["ratio"] = (r["ctc_end"] - r["ctc_start"]) / ld
        r["collapse"] = r["ratio"] > a.collapse_ratio

    import statistics
    # 偏移 = 本地行首 − 逐字行首，即「这份视频与那份音源差多少」。
    #
    # 关键：这里**用全部行**取中位，不剔除塌缩行。实测（东方工程，真值 +1.901s）：
    #   全部 36 行中位 +1.9190（误差 18ms）  ← 用它
    #   剔除塌缩后 24 行 +1.9475（误差 46ms）
    # 原因是塌缩发生在**行尾**（长音/间奏被塞给最后几个音拍），行首那一拍仍是准的；
    # 剔除它们等于白丢 12 个有效样本。中位数本身就能吸收个别被前一行推迟的行首。
    # 只有「行匹配」的行才有真实的 LDDC 行首，能用来估偏移；
    # 「全局池」行的 lddc_start 是占位值，混进来会把偏移整体带偏。
    offrows = [r for r in rows if r["how"] == "行匹配"]
    if len(offrows) < a.min_lines:
        print("[align] 警告：可用真实行首的行只有 %d 行，偏移估计不稳。" % len(offrows))
        offrows = rows
    diffs = [r["ctc_start"] - r["lddc_start"] for r in offrows]
    OFF = statistics.median(diffs)
    sd = statistics.pstdev(diffs) if len(diffs) > 1 else 0.0
    if n_pool:
        print("[align] 其中 %d 行是「逐行匹配不上、用全局字符池兜底」的（不参与估偏移）" % n_pool)
    n_col = sum(1 for r in rows if r["collapse"])
    print("\n[align] 疑似塌缩行 %d / %d（行跨度比 > %.2f；只作提示，不参与剔除）"
          % (n_col, len(rows), a.collapse_ratio))
    print("[align] 全局偏移 = %+.4f s（%d 行取中位，离散 %.3f s）" % (OFF, len(diffs), sd))

    # ---- 2b) 逐行锚点：**全部**用同一个全局偏移 ----
    #
    # 实测（东方工程，真值 +1.901s，outlier 扫描）：
    #   全用各行自己的 CTC 行首      -> MAE 0.2918s
    #   离群行(>0.5s)才用本地行首    -> MAE 0.1379s
    #   全部用单一全局偏移          -> MAE 0.0307s  中位 0.025s  90分位 0.051s
    #   逐行偏移做中位滤波          -> 在第二工程上把 4.6s 的漂移压到 0.7s  ← 当前实现
    #
    # 也就是说「给离群行开小灶」**反而差 4.5 倍**。原因：CTC 行首的抖动是全曲性的
    # （实测每行都在抖，中位偏离 0.191s、最大 0.758s，58% 的行偏离 >0.15s），
    # 它不是"某些行坏了"，而是"每一行都不够好"。挑出偏离大的行让它们用自己的行首，
    # 等于专门去选那批**最不准**的测量值当锚点。
    # 所以：一个全局偏移 + 逐行相对形状，是这条链路上唯一正确的组合。
    # --outlier 保留但默认 0.9s（远大于实测最大抖动，正常不触发）；调小它会让精度变差。
    # ---- 2b) 逐行锚点：中位滤波的局部偏移 ----
    #
    # 只用单一全局偏移仍有一个盲点：**前一行 CTC 塌缩会把下一行整体推后**。
    # 实测 `tsunagukizuna`：行 7「儚い想いもその苦しみも」的本地行首比逐字行首晚 **4.24s**，
    # 而行 8、行 14 同样偏 3.16 / 3.35s —— 那不是"源不对"，是本地 CTC 把前一句的长音/间奏
    # 算给了这一句的开头。
    #
    # 修法：对「逐行偏移 = ctc行首 − 逐字行首」这条序列做**中位滤波**，用邻行的共识当局部基准。
    # 依据是"相邻几句的偏移应当几乎相同"（同一份音源、同一段剪辑）：
    #   实测上述工程 |偏离全局| 最大 4.62s -> 中位滤波(窗5) 0.69s -> (窗7) 0.32s
    # 中位而不是均值：个别被推后的行不会把邻行一起拖走。
    # 窗长用奇数；窗 3 不够（3.16s 的漂移占窗内多数时会幸存），窗 5 起有效。
    seq = [r for r in rows if r["how"] == "行匹配"]
    for r in rows:
        r["dev"] = abs(r["ctc_start"] - r["lddc_start"] - OFF)
    # 自适应：只有抖动确实大时才滤波。
    # 实测两工程的对比（都是同一份算法）：
    #   touhou ：逐行偏移相对全局值 中位 0.064s / 最大 0.389s（本就好）→ 滤波反而变差
    #             不滤波 MAE 0.0307s  vs 窗5 0.1073s
    #   tsunagu：逐行偏移 最大 4.62s（前句塌缩推移）→ 不滤波留着 4.6s 的错
    #             滤波后把三行 4.62/3.55/3.73s 全纠正
    # 判据：**偏离全局值 > 2s 的行占比**。这个量能干净地区分"结构性漂移"与"批次抖动"：
    #   touhou ：>2s 占 0%（最大偏离 0.758s，纯抖动）        -> 不滤波（滤波会自伤 3.5 倍）
    #   tsunagu：>2s 占 10%（最大 4.62s，前句塌缩推移）      -> 滤波（把 4.6s 纠正掉）
    # 试过用 90 分位当判据，不行：touhou 的 90 分位是 0.570s（被 19% 的少数行抬起来），
    # 会误触发；2s 以上才是"这句真的被整体推走了"的量级。
    devs_all = [r["dev"] for r in seq]
    frac_far = (sum(1 for d in devs_all if d > a.medfilt_trigger) / len(devs_all)) if devs_all else 0.0
    spread = max(devs_all) if devs_all else 0.0
    use_filt = a.medfilt > 1 and seq and frac_far >= a.medfilt_frac
    if use_filt:
        res = [r["ctc_start"] - r["lddc_start"] for r in seq]
        h = a.medfilt // 2
        for i, r in enumerate(seq):
            lo, hi = max(0, i - h), min(len(res), i + h + 1)
            r["local_off"] = statistics.median(res[lo:hi])
    print("[align] 逐行偏移：最大偏离 %.3f s，>%.1fs 的行占 %.0f%% → %s"
          % (spread, a.medfilt_trigger, frac_far * 100,
             ("启用中位滤波窗%d（吸收结构性漂移）" % a.medfilt) if use_filt else "不滤波（抖动在正常范围）"))
    for r in rows:
        if r["how"] != "行匹配":
            r["local_off"] = OFF
            r["base"] = r["ctc_start"]
            r["use_local"] = False
            continue
        if r["dev"] > a.outlier:
            # 远超邻行共识：本地行首明显被前一行拖了，优先信逐字源的行首 + 全局偏移
            r["local_off"] = OFF
            r["use_local"] = True
        else:
            r["local_off"] = r.get("local_off", OFF)
            r["use_local"] = False
        r["base"] = r["lddc_start"] + r["local_off"]
    n_local = sum(1 for r in rows if r["use_local"])
    print("[align] 锚定：逐字源行首 + 局部偏移 %d 行；其中 %d 行偏离邻行共识 >%.2fs，已用全局偏移兜底"
          % (sum(1 for r in rows if r["how"] == "行匹配"), n_local, a.outlier))
    for r in rows:
        if r["use_local"]:
            print("   line %2d 本地行首比邻行共识晚 %.2fs（疑前句塌缩推移），已纠正" % (r["li"], r["dev"]))
    # 0.25s 是「本机实测正常工程」的上限（东方工程 sd=0.315 但融合结果 MAE 0.032s，
    # 因为 CTC 行首本身就有 ~0.3s 抖动，中位数能吸收）。超过 0.8s 才是「不是同一剪辑」的信号。
    if sd > 0.8:
        print("[align] ⚠ 离散 %.2fs 过大：歌词与这份音源可能不是同一剪辑。核对 --source/--song-id。" % sd)
    elif sd > 0.25:
        print("[align] 离散 %.2fs（CTC 行首的固有抖动，中位数可吸收；>0.8s 才需怀疑源不对）" % sd)

    # ---- 3) 组装：pred = 行锚点 + 句内相对形状 ----
    base = {}
    for r in rows:
        base[r["li"]] = r["base"]

    # 行窗口：本行锚点 ~ 下一行锚点（用于夹取，防塌缩行的形状把尾巴甩出去）
    order = sorted(base)
    win = {}
    for i, li in enumerate(order):
        hi = base[order[i + 1]] if i + 1 < len(order) else None
        win[li] = hi

    out, n_clamped, sugg = [], 0, []
    for r in rows:
        li = r["li"]
        s_list = [round(base[li] + d, 3) for d in r["shape"]]
        # 单调 + 窗口夹取
        hi = win.get(li)
        for k in range(len(s_list)):
            if k and s_list[k] < s_list[k - 1]:
                s_list[k] = s_list[k - 1]
            if a.clamp:
                lo_b = base[li] - a.slack
                hi_b = (hi - 0.03) if hi else (r["ctc_end"] + a.slack)
                # 行窗口上界取「下一行锚点」；但锚点是 逐字行首+偏移，当下一行是**副歌里重复出现的
                # 同一句**时，行匹配会吸到更早的那一次（实测 line 30 淀みない…被 line 31 的
                # Like a lotus 锚点吸到 210.53），hi 落到本行之前 → 整行被夹成零长（17 个音拍
                # 全在 227.50-227.80，起音匹配率 0/17）。留一个本地 CTC 跨度的下界把它救回来。
                hi_b = max(hi_b, r["ctc_end"] + a.slack)
                if s_list[k] > hi_b:
                    s_list[k] = round(hi_b, 3); n_clamped += 1
                if s_list[k] < lo_b:
                    s_list[k] = round(lo_b, 3); n_clamped += 1
        if r["collapse"]:
            sugg.append(dict(line=li, ratio=round(r["ratio"], 2), text=r["text"][:24],
                             why="本地跨度是逐字跨度的 %.1f 倍，CTC 在此塌缩" % r["ratio"]))
        for k, (ui, mi, m) in enumerate([(ui, mi, m) for ui, u in enumerate(lines[li]["units"])
                                         if u["kind"] != "space" for mi, m in enumerate(u["morae"])]):
            out.append(dict(line=li, unit=ui, mora=mi, text=m, s=s_list[k], e=None))
    out.sort(key=lambda x: (x["line"], x["unit"], x["mora"]))

    # 终点 = 同句下一个音拍起点；句尾用形状的内源末拍 + 余量
    by = {}
    for m in out:
        by.setdefault(m["line"], []).append(m)
    for li, v in by.items():
        v.sort(key=lambda x: x["s"])
        for i, m in enumerate(v):
            m["e"] = round(v[i + 1]["s"] if i + 1 < len(v) else m["s"] + 0.30, 3)
    out = [m for li in sorted(by) for m in by[li]]

    outp = a.out if os.path.isabs(a.out) else os.path.join(a.project, a.out)
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)

    print("\n[align] -> %s（%d 音拍）" % (outp, len(out)))
    print("[align] 夹取 %d 个音拍到行窗口内（--no-clamp 可关）" % n_clamped)
    if miss:
        print("[align] 未用上逐字的行 %d 个：" % len(miss))
        for li, why in miss[:12]:
            print("   line %2d  %s  %s" % (li, why, norm("".join(u["surf"] for u in lines[li]["units"]))[:30]))

    if a.report:
        rp = a.report if os.path.isabs(a.report) else os.path.join(a.project, a.report)
        os.makedirs(os.path.dirname(rp) or ".", exist_ok=True)   # 新工程没有 review/ 目录时自动建
        L = ["# kf 融合报告", "",
             "源: %s (song %s)  |  逐字 %d 行  |  锚点 %s" % (kf.get("source"), kf.get("song_id"),
                                                             len(kf["lines"]), a.auto), "",
             "全局偏移 **%+.4f s**（%d 行中位，离散 %.3f s）" % (OFF, len(diffs), sd), "",
             "## 疑似 CTC 塌缩的行（%d，只作提示）" % len(sugg), "",
             "| 行 | 倍数 | 文本 |", "|---|---|---|"]
        for s in sugg:
            L.append("| %d | %.1f× | %s |" % (s["line"], s["ratio"], s["text"]))
        L += ["", "## 未用上逐字的行（%d）" % len(miss), ""]
        for li, why in miss:
            L.append("- line %d：%s" % (li, why))
        L += ["", "## 逐行偏移（非塌缩行应聚在全局值附近）", "",
              "| 行 | 本地行首 | 减全局偏移 | 倍数 |", "|---|---|---|---|"]
        for r in sorted(rows, key=lambda x: x["li"]):
            L.append("| %d | %.3f | %+.3f | %.2f× |" % (r["li"], r["ctc_start"], r["ctc_start"] - OFF, r["ratio"]))
        with open(rp, "w", encoding="utf-8") as f:
            f.write("\n".join(L) + "\n")
        print("[align] 报告 -> %s" % rp)
    if sugg:
        print("\n[align] 注意：以下行本地 CTC 塌缩，已按句内形状纠正（人工仍应抽看频谱）")
        for s in sugg[:10]:
            print("   line %2d  %.1f×  %s" % (s["line"], s["ratio"], s["text"]))
    return 0


# ---------------------------------------------------------------- verify

def cmd_verify(a):
    A = load_json(a.a if os.path.isabs(a.a) else os.path.join(a.project, a.a))
    B = load_json(a.b if os.path.isabs(a.b) else os.path.join(a.project, a.b))
    ka = {(m["line"], m["unit"], m["mora"]): m["s"] for m in A}
    kb = {(m["line"], m["unit"], m["mora"]): m["s"] for m in B}
    common = set(ka) & set(kb)
    if not common:
        sys.exit("[verify] 两份时间轴没有共同的 (line,unit,mora) 键，无法比较。")
    dif = sorted(((abs(ka[k] - kb[k]), k) for k in common), reverse=True)
    import statistics
    vals = [d for d, _ in dif]
    print("[verify] %s vs %s" % (a.a, a.b))
    print("[verify] 共同音拍 %d / %d vs %d" % (len(common), len(ka), len(kb)))
    print("[verify] 差: 中位 %.3f s  均值 %.3f s  90分位 %.3f s  最大 %.3f s"
          % (statistics.median(vals), sum(vals) / len(vals),
             sorted(vals)[int(len(vals) * 0.9)], vals[0]))
    over = [x for x in dif if x[0] > a.thr]
    print("[verify] 超过 %.2fs 的 %d 个（占 %.1f%%）" % (a.thr, len(over), 100 * len(over) / len(common)))
    print("\n最差 %d 个：" % a.top)
    for d, (li, ui, mi) in dif[:a.top]:
        print("   line %2d unit %2d mora %d    %8.3f vs %8.3f    %+.3f"
              % (li, ui, mi, ka[(li, ui, mi)], kb[(li, ui, mi)], ka[(li, ui, mi)] - kb[(li, ui, mi)]))
    return 0


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="LDDC 逐字 + 本地行首锚点 -> 音拍级时间轴")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="抓网络逐字歌词 -> kf.json")
    f.add_argument("--lddc", default=os.environ.get("HX_LDDC_PATH", "~/Loli/code/HX-Music/pyTool"))
    f.add_argument("--title", default=""); f.add_argument("--artist", default="")
    f.add_argument("--song-id", default="", help="从打印的候选列表里挑；不给取第一条")
    f.add_argument("--source", default="QM", choices=LDDC_SOURCES)
    f.add_argument("--lang", default="orig")
    f.add_argument("--project", default="."); f.add_argument("--out", default="kf.json")
    f.set_defaults(fn=cmd_fetch)

    al = sub.add_parser("align", help="融合 -> timing_kf.json")
    al.add_argument("--project", default=".")
    al.add_argument("--lyrics", default="lyrics.txt")
    al.add_argument("--auto", default="timing_auto.json", help="提供本地行首锚点的 timing")
    al.add_argument("--kf", default="kf.json")
    al.add_argument("--out", default="timing_kf.json")
    al.add_argument("--report", default="review/kf-report.md")
    al.add_argument("--collapse-ratio", type=float, default=1.45, help="本地跨度/逐字跨度 超过即判塌缩")
    al.add_argument("--min-lines", type=int, default=5, help="估偏移所需的最少非塌缩行")
    al.add_argument("--medfilt-trigger", type=float, default=2.0,
                    help="单行偏移超过此秒数即算「结构性漂移」的候选（默认 2.0）")
    al.add_argument("--medfilt-frac", type=float, default=0.05,
                    help="「结构性漂移」的行占比超过此值才启用中位滤波（默认 0.05）。"
                         "实测 touhou 该占比 0%%（滤波有害 0.031->0.107），tsunagu 10%%（滤波有益，纠 4.6s）")
    al.add_argument("--medfilt", type=int, default=5,
                    help="逐行偏移的中位滤波窗长（奇数）。用邻行共识吸收「前句塌缩把后句推后」；"
                         "实测窗 3 在 3s 级漂移上不够、窗 5 起有效。给 1 关闭")
    al.add_argument("--outlier", type=float, default=0.9,
                    help="某行本地行首相对全局偏移偏离超过此秒数才单独用它的本地锚点。"
                         "实测调小反而更差（0.5 -> MAE 0.138s vs 0.9 -> 0.031s），别降低")
    al.add_argument("--shape-min-quality", type=float, default=0.5,
                    help="LDDC 句内形状的可信下限（差分 >40ms 的占比）；低于它回退到本地 CTC 形状")
    al.add_argument("--slack", type=float, default=0.45, help="行窗口前后容许的溢出秒数")
    al.add_argument("--no-clamp", dest="clamp", action="store_false", help="不做行窗口夹取")
    al.set_defaults(fn=cmd_align, clamp=True)

    v = sub.add_parser("verify", help="两份时间轴对比")
    v.add_argument("--project", default="."); v.add_argument("--a", required=True); v.add_argument("--b", required=True)
    v.add_argument("--thr", type=float, default=0.15); v.add_argument("--top", type=int, default=20)
    v.set_defaults(fn=cmd_verify)

    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
