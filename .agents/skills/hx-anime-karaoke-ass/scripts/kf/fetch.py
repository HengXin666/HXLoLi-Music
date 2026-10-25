# -*- coding: utf-8 -*-
"""`fetch` 阶段: 用 LDDC 抓网络逐字歌词 -> kf.json (可多源投票).

LDDC 的 g2p_en 需要 nltk 语料, 离线会被拦; 纯日语歌曲直接 stub 掉即可(见 _setup_lddc).
"""
import json
import os
import sys

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
    # 所以 --source 指定失败时自动往其它源退，而不是直接放弃  把「某个源抽风」和
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
        sys.exit("[fetch] 四个源（%s）都没拿到。核对曲名/艺人，或该曲确实没有逐字歌词  "
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
