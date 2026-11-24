# -*- coding: utf-8 -*-
"""整曲设计方向 (directions.json) 与落地追溯 (landing.json) 的判据.

换番名检查是机械的: 一套方向的母题里, 有效专属 (unique>=2) 的少于 2 个或不到一半,
或高潮段没用专属母题, 就判 "换掉番名仍成立" = 不专属. 自评 swap_test.holds 与机械结果矛盾判 FAIL.
落地追溯也是机械的: 符号 -> fx 函数在生成器源码里存在 -> 函数体里有 marker -> 设计表或 manifest
把这个 fx 绑到了所写的句 -> (可选) out.ass 在该句时间内出现 ass_marker.
"""
import json, os, re

from judge.bible_io import HEX_RE, nonempty

MIN_MOTIFS = 3
MIN_LANDED = 3        # 每首歌至少 3 条专属符号落进特效 (验收 "若干条")
MAX_OVERLAP = 0.6     # 两套方向母题 Jaccard 上限


def swap_holds(bible, d):
    """返回 (换番名后仍成立?, 说明)."""
    ms = [m for m in d.get("motifs") or [] if m in bible.symbols]
    ex = [m for m in ms if bible.exclusive(m)]
    cl = [m for m in (d.get("climax") or {}).get("motifs") or [] if bible.exclusive(m)]
    why = "专属母题 %d/%d, 高潮专属母题 %d" % (len(ex), len(ms), len(cl))
    return (len(ex) < 2 or len(ex) * 2 < len(ms) or not cl), why


def check_directions(bible, song, res):
    d = bible.data.get("directions.json") or {}
    if "directions.json" in bible.errors:
        res.bad("bible/directions.json", "缺失" if bible.errors["directions.json"] == "missing" else bible.errors["directions.json"])
        return None
    ds = d.get("directions") or []
    res.check(2 <= len(ds) <= 3, "directions 数量", "要 2-3 套整曲方向 (现在 %d)" % len(ds))
    chosen = [x for x in ds if x.get("chosen")]
    res.check(len(chosen) == 1, "directions 选定", "要正好选定 1 套 (现在 %d)" % len(chosen))
    names = set(bible.char_names())
    for x in ds:
        _one(bible, song, x, names, res)
    for i, a in enumerate(ds):
        for b in ds[i + 1:]:
            sa, sb = set(a.get("motifs") or []), set(b.get("motifs") or [])
            j = len(sa & sb) / max(1, len(sa | sb))
            res.check(j <= MAX_OVERLAP and a.get("motion") != b.get("motion"), "directions[%s~%s] 差异" % (a.get("id"), b.get("id")),
                      "两套方向母题重合 %.0f%% (上限 %.0f%%) 或运动语言相同, 只换参数不算另一套" % (j * 100, MAX_OVERLAP * 100))
    return chosen[0] if len(chosen) == 1 else None


def _one(bible, song, x, names, res):
    tag = "direction[%s]" % x.get("id")
    for k in ("name", "motion", "type_mood"):
        res.check(nonempty(x.get(k)), "%s %s" % (tag, k), "要写 %s" % k)
    ms = x.get("motifs") or []
    miss = [m for m in ms if m not in bible.symbols]
    res.check(len(ms) >= MIN_MOTIFS and not miss, tag + " 母题", "motifs 要 >=%d 个且都在符号词典里. 不存在: %s" % (MIN_MOTIFS, miss))
    pal = x.get("palette") or []
    bad = [p for p in pal if not (isinstance(p, dict) and HEX_RE.match(str(p.get("hex", "")))
                                  and (p.get("from") in bible.symbols or p.get("from") in names))]
    res.check(len(pal) >= 2 and not bad, tag + " 色彩", "palette >=2 色, 每色 from 要指向角色名或符号 id: %s" % bad[:2])
    cl = x.get("climax") or {}
    lines = cl.get("lines") or []
    res.check(lines and all(isinstance(i, int) and 0 <= i < song.n for i in lines) and nonempty(cl.get("treatment")),
              tag + " 高潮", "climax 要有有效 lines 与 treatment")
    holds, why = swap_holds(bible, x)
    st = x.get("swap_test") or {}
    res.check(nonempty(st.get("swap_to")) and isinstance(st.get("holds"), bool) and nonempty(st.get("why")),
              tag + " 换番名自评", "swap_test 要写 swap_to (换成哪部), holds, why")
    if isinstance(st.get("holds"), bool):
        res.check(st["holds"] == holds, tag + " 自评一致", "自评 holds=%s, 机械检查 holds=%s (%s)" % (st["holds"], holds, why))
    if x.get("chosen"):
        res.check(not holds, tag + " 专属", "选定方向换掉番名仍成立 (%s), 不专属" % why)
    else:
        res.check(nonempty(x.get("reject_reason")), tag + " 落选理由", "落选方向要写理由")


# ---------------------------------------------------------------- 落地追溯
def _gen_sources(proj, files):
    out = {}
    for f in files or []:
        p = os.path.join(proj, f)
        if os.path.isfile(p):
            out[f] = open(p, encoding="utf-8").read()
    return out


def _func_body(src, fx):
    m = re.search(r"^def %s\(.*?(?=^\S|\Z)" % re.escape(fx), src, re.M | re.S)
    return m.group(0) if m else None


def _bindings(proj, srcs):
    """fx 名 -> 绑定的句集合. 优先 out.manifest.json (params.fx 与 deps.code), 否则扫设计表 dict(lines=[..] .. fx="..")."""
    out = {}
    mp = os.path.join(proj, "out.manifest.json")
    if os.path.isfile(mp):
        for u in json.load(open(mp, encoding="utf-8")).get("units") or []:
            names = {(u.get("params") or {}).get("fx")}
            names |= {c.split(":", 1)[1] for c in (u.get("deps") or {}).get("code") or [] if ":" in c}
            for n in names - {None}:
                out.setdefault(n, set()).update(u.get("lines") or [])
        return out, "manifest"
    pat = re.compile(r"lines=\[([\d,\s]+)\][^\n]*?fx=\"(\w+)\"")
    for src in srcs.values():
        for m in pat.finditer(src):
            ls = {int(v) for v in m.group(1).split(",") if v.strip()}
            out.setdefault(m.group(2), set()).update(ls)
            out.setdefault("fx_" + m.group(2), set()).update(ls)
    return out, "design-table"


def _via(srcs, bind, fx):
    """一层间接: 绑定过的函数在函数体里调用了 fx (例 fx_echo_reach 里调 fx_main.p32), 返回这些函数绑定的句."""
    out = set()
    call = re.compile(r"(?<![\w])(?:\w+\.)?%s\(" % re.escape(fx or ""))
    for name, ls in bind.items():
        body = next((b for b in (_func_body(s, name) for s in srcs.values()) if b), None)
        if body and call.search(body.split("\n", 1)[-1]):
            out |= ls
    return out


def _ass_hits(proj, ass, marker, spans, pad=1.0):
    p = os.path.join(proj, ass or "out.ass")
    if not os.path.isfile(p):
        return None
    hit = 0
    for ln in open(p, encoding="utf-8"):
        if not ln.startswith("Dialogue:") or marker not in ln:
            continue
        f = ln.split(",", 3)
        t0, t1 = _sec(f[1]), _sec(f[2])
        hit += any(t0 < e + pad and t1 > s - pad for s, e in spans)
    return hit


def _sec(t):
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def check_landing(bible, song, res, chosen=None):
    """返回落地追溯链 [(symbol, fx, lines, 来源名列表, ass 命中数)]."""
    if "landing.json" in bible.errors:
        res.bad("bible/landing.json", "缺失" if bible.errors["landing.json"] == "missing" else bible.errors["landing.json"])
        return []
    d = bible.data["landing.json"]
    srcs = _gen_sources(song.proj, d.get("gen"))
    res.check(srcs, "landing gen", "gen 要列生成器源码文件 (相对工程目录), 且文件存在")
    bind, how = _bindings(song.proj, srcs)
    motifs = set((chosen or {}).get("motifs") or [])
    chain, landed = [], set()
    for it in d.get("items") or []:
        sid, fx, ls = it.get("symbol"), it.get("fx"), it.get("lines") or []
        tag = "landing[%s@%s]" % (sid, fx)
        if not res.check(sid in bible.symbols, tag + " 符号", "符号不在词典里"):
            continue
        body = next((b for b in (_func_body(s, fx) for s in srcs.values()) if b), None) if nonempty(fx) else None
        ok = res.check(body is not None, tag + " 函数", "生成器源码里找不到 def %s" % fx)
        mk = it.get("marker")
        ok &= res.check(bool(body) and nonempty(mk) and mk in body, tag + " marker",
                        "函数体里没有 marker %r (marker 要是画这个符号的那段代码里的字面量)" % mk)
        bad = [i for i in ls if i not in bind.get(fx, set()) | _via(srcs, bind, fx)]
        ok &= res.check(ls and not bad, tag + " 绑定",
                        "%s 没把 %s (或直接调用它的函数) 绑到句 %s" % (how, fx, bad or "(空)"))
        ok &= _asset_ok(song.proj, it, tag, res)
        if motifs and sid not in motifs:
            res.warn(tag + " 方向", "这个符号不在选定方向的母题里")
        hits = None
        if nonempty(it.get("ass_marker")):
            hits = _ass_hits(song.proj, d.get("ass"), it["ass_marker"], [song.spans[i] for i in ls if i in song.spans])
            if not hits:
                res.warn(tag + " 成品", "out.ass 在这些句的时间里没找到 %r (%s)" % (it["ass_marker"], "没有 out.ass" if hits is None else "0 条"))
        if ok:
            chain.append((sid, fx, ls, [bible.sources[s].get("name") for s in bible.ref_sources(bible.symbols[sid].get("refs"))], hits))
            if bible.exclusive(sid):
                landed.add(sid)
    res.check(len(landed) >= MIN_LANDED, "landing 专属落地",
              "真正落进特效且可追溯的专属符号 %d 个 (%s), 要 >=%d" % (len(landed), sorted(landed), MIN_LANDED))
    return chain


def _asset_ok(proj, it, tag, res):
    a = it.get("asset")
    if not a:
        return True
    p = os.path.join(proj, a.get("file", ""))
    have = os.path.isfile(p) and (not a.get("key") or a["key"] in json.load(open(p, encoding="utf-8")))
    return res.check(have, tag + " 素材", "素材 %s 里没有 %r" % (a.get("file"), a.get("key")))
