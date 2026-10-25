# -*- coding: utf-8 -*-
"""歌词覆盖审计的**证据读取**: 网络歌词、本地歌词、跨源边界、CTC 假名密度、人声能量.

为什么单独一个模块: 这些函数只回答"能不能读到、读到了什么", 与"判据多少分"分开 
改读取口径(源、缓存格式)不必翻判据逻辑.
"""
import difflib
import json
import os
import re
import sys
import wave


def norm(s):
    return re.sub(r"[\s　]+", "", str(s or ""))


def load_local(path):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from assfx.base.lyrics import load as load_lyrics
    lines = load_lyrics(path)
    return [norm("".join(u["surf"] for u in ln["units"])) for ln in lines]

def cross_source_edges(kf_path):
    """第二源(LDDC 逐字歌词)的句首/句尾时刻  用来交叉裁决空档是不是漏句。

    为什么需要它: 「空档能量 vs 演唱段能量」这条判据在**带人声分离残留**的工程上会稳定误报。
    实测(2026-10-03): demucs 在纯器乐段仍从伴奏漏出 -18~-21 dB 的信号,
    与演唱段的 -18.6 dB 同量级, 差 0~3 dB 正好落在 --db-tol 里, 于是 7 处器乐持音段全被
    报成"疑似漏句"(22.8/45.7/134.4/157.1/202.4/260.3/282.9 秒各一处)。
    那些段实测 F0 在 0.4s 窗内相对标准差 ≤1.05%(人声段 0.56~18.4%、真实长音 3.9~4.8%),
    即合成器/弦乐持音, 不是声带振动  但脚本只看能量, 看不见这个区别。

    第二源能看见: 它是**独立标注者**给的逐字时间。若两个源都把"这句在此结束/开始"
    标在空档的同一端(±tol), 那空档就不可能是漏句  漏句会让第二源在别处多出一句。
    """
    if not os.path.exists(kf_path):
        return None
    try:
        kf = json.load(open(kf_path, encoding="utf-8"))
    except Exception:
        return None
    heads, tails = [], []
    for ln in kf.get("lines", []):
        w = [x for x in ln.get("words", []) if str(x.get("t", "")).strip()]
        if not w:
            continue
        heads.append(float(w[0]["s"]))
        tails.append(float(w[-1]["e"]))
    return heads, tails


def ctc_kana_density(cache, spans, sung_spans):
    """第三判据: 空档段「模型吐了几个假名」。

    为什么需要它: 前两条判据都看不见"这段到底有没有词"。
    - 能量判据会被人声分离残留骗过（见 cross_source_edges 的 docstring）。
    - 第二源交叉裁决要空档**两端**都被贴住；长音句的尾巴会把一端推开，
      于是它管不住"副歌尾长音之后那一段器乐"（实测 202.39-206.50 就是这么漏的）。

    这条判据是物理的: 真在唱词 -> 模型必然连续吐假名; 只有器乐/长音持续 -> 输出稀疏。
    实测（2026-10-03）: 演唱段 2.80~5.75 个/秒; 7 处空档 0.46~2.48 个/秒;
    纯器乐段 0.00~1.50 个/秒。分离清晰，且它不依赖能量、不依赖第二源。

    阈值取**本曲演唱段密度的 p20**（自适应）: 固定阈值在不同编曲密度下会失准。
    没有 ctc_lp.npz 时返回 None  由调用方显式说明"跳过"，不静默当通过。
    """
    if not os.path.exists(cache):
        return None
    try:
        import numpy as np
        z = np.load(cache, allow_pickle=True)
        lp, fd, vocab = z["lp"], float(z["fd"]), list(z["vocab"])
    except Exception:
        return None
    blank = vocab.index("[PAD]") if "[PAD]" in vocab else 0
    sep = vocab.index("|") if "|" in vocab else -1

    def dens(a, b):
        n, prev = 0, -1
        for k in range(int(a / fd), int(b / fd)):
            j = int(lp[k].argmax())
            if j not in (blank, sep) and j != prev:
                n += 1
            prev = j
        return n / max(b - a, 1e-6)

    sung = [dens(s, t) for s, t in sung_spans if t - s >= 1.0]
    if len(sung) < 5:
        return None
    thr = float(sorted(sung)[max(0, int(len(sung) * 0.2) - 1)])
    return thr, [(s, t, dens(s, t)) for s, t in spans]


def vocal_db(a, sr, t0, t1):
    """int16 采样 -> RMS 分贝（先归一化到 [-1,1]，否则数值会是正几十 dB，阈值无意义）"""
    i0, i1 = int(t0 * sr), int(t1 * sr)
    seg = a[i0:i1]
    if not len(seg):
        return -99.0
    import math
    rms = math.sqrt(sum(float(x) * float(x) for x in seg) / len(seg)) / 32768.0
    return 20 * math.log10(rms + 1e-9)


def fetch_net(title, artist, song_id, source="QM"):
    """用 LDDC 取网络歌词。缺 LDDC 时返回 None（不报错，退化为只查空档）。"""
    root = os.path.expanduser(os.environ.get("HX_LDDC_PATH", "~/Loli/code/HX-Music/pyTool"))
    if not os.path.isdir(os.path.join(root, "LDDC")):
        return None, "找不到 LDDC（HX_LDDC_PATH 未指向 HX-Music/pyTool）"
    import types
    if root not in sys.path:
        sys.path.insert(0, root)
    if "g2p_en" not in sys.modules:
        fake = types.ModuleType("g2p_en")

        class G2p:
            def __init__(self, *a, **k): pass
            def __call__(self, *a, **k): return []

        fake.G2p = G2p
        sys.modules["g2p_en"] = fake
    try:
        from LDDC.common.models._enums import SearchType, Source
        from LDDC.core.api.lyrics import search, get_lyrics
    except Exception as exc:
        return None, "LDDC 导入失败: %s" % exc
    try:
        cands = search(getattr(Source, source), " ".join(x for x in (title, artist) if x), SearchType.SONG)
    except Exception as exc:
        return None, "搜索失败: %s" % exc
    if not cands:
        return None, "网络无结果"
    song = next((s for s in cands if str(getattr(s, "id", "")) == str(song_id)), cands[0]) if song_id else cands[0]
    ly = get_lyrics(song)
    data = ly.get("orig") or ly[list(ly.keys())[0]]
    out = []
    for ln in data:
        ws = [w for w in ln.words if str(w.text).strip()]
        if ws:
            out.append(norm("".join(str(w.text) for w in ws)))
    return out, "OK(song_id=%s)" % getattr(song, "id", "?")


def cover_ok(net_line, local_lines):
    """网络的一行是否被本地覆盖（允许本地拆成多行）"""
    if not net_line:
        return True
    joined = "".join(local_lines)
    if net_line in joined:
        return True
    for lo in local_lines:
        if difflib.SequenceMatcher(None, net_line, lo).ratio() > 0.85:
            return True
    return False

from gate.coverage_sources import (cross_source_edges, ctc_kana_density,   # noqa: F401
                                 load_local, vocal_db)
