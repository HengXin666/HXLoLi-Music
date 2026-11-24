# -*- coding: utf-8 -*-
"""设计圣经前四份的判据: symbols / characters / scenes / lyric-map. 只查能机械证伪的项.

格式见 steps/3-anime-bg/11-design-bible/impl/formats.md. 阈值来源见同目录 index.md 的 "阈值" 一节.
"""
from judge.bible_io import FIRST_HAND, HEX_RE, SRC_TYPES, background_names, name_hit, nonempty

MIN_EXCL = 4          # 专属符号 (有效 unique >= 2) 的下限
MIN_CHARS = 2         # 角色卡下限
MIN_SCENES = 2        # 名场面下限
BASIS = ("direct", "inferred", "none")


# Agent Notes: 作品设计圣经: 来源分型 + 专属度 + 逐句对位 + 整曲方向 + 落地追溯
# .agents/notes/implemented/feature/2026-11-17-karaoke-design-bible.md
def check(bible, song, res):
    """bible: judge.bible_io.Bible; song: judge.common.Song. 结果写进 res."""
    for f in ("symbols.json", "characters.json", "scenes.json", "lyric-map.json"):
        if f in bible.errors:
            res.bad("bible/" + f, "缺失" if bible.errors[f] == "missing" else bible.errors[f])
    _sources(bible, res)
    _symbols(bible, res)
    _characters(bible, song, res)
    _scenes(bible, song, res)
    _lyric_map(bible, song, res)


def _refs_ok(bible, refs, tag, res):
    """每条引用要指向来源表, 且带原文摘句. 返回有效来源数."""
    bad = [r for r in refs or [] if not (isinstance(r, dict) and r.get("src") in bible.sources and nonempty(r.get("quote")))]
    res.check(not bad, tag + " 引用", "引用要有 src (来源表 id) 与 quote (原文摘句): %s" % bad[:2])
    return len(bible.ref_sources(refs))


def _sources(bible, res):
    if not bible.sources:
        res.bad("sources", "来源表为空")
        return
    bad = [k for k, s in bible.sources.items() if s.get("type") not in SRC_TYPES or not nonempty(s.get("name"))]
    res.check(not bad, "sources 类型", "来源要有 name, type 只能是 %s: %s" % ("/".join(SRC_TYPES), bad))
    nourl = [k for k, s in bible.sources.items() if s.get("type") != "screen" and not nonempty(s.get("url"))]
    if nourl:
        res.warn("sources 出处", "这些来源没有 url, 复核不了: %s" % nourl)
    kinds = {s.get("type") for s in bible.sources.values()}
    if not kinds & set(FIRST_HAND):
        res.warn("sources 一手", "没有官方设定或原作原文来源, 全靠社区共识, 误传风险高")


def _symbols(bible, res):
    if not bible.symbols:
        res.bad("symbols", "符号词典为空")
        return
    n_excl = 0
    for sid, s in bible.symbols.items():
        tag = "symbol[%s]" % sid
        u = s.get("unique")
        if not res.check(isinstance(u, int) and 0 <= u <= 3, tag + " unique", "unique 要是 0..3 的整数"):
            continue
        res.check(nonempty(s.get("name")) and nonempty(s.get("form")), tag + " 名与形",
                  "要写 name 与 form (可画的形态)")
        n = _refs_ok(bible, s.get("refs"), tag, res)
        res.check(n >= 1, tag + " 来源", "至少 1 个来源 (只有画面也要登记一个 screen 来源)")
        types = bible.types_of(s.get("refs"))
        if u >= 2:
            res.check(nonempty(s.get("unique_why")), tag + " 专属理由", "unique>=2 要写 unique_why: 换番名为什么说不通")
            first = bool(types & set(FIRST_HAND))
            res.check(first or n >= 3, tag + " 防误传",
                      "unique>=2 要有官方设定或原作原文来源, 否则至少 3 个社区来源 (现在 %d 个, 类型 %s)" % (n, sorted(types)))
        if u == 3:
            res.check(n >= 3, tag + " A 级", "unique=3 要 >=3 个互不相关来源 (现在 %d). 不够就降到 2" % n)
        if u >= 2 and bible.screen_only(s):
            res.bad(tag + " 仅画面", "只有画面证据的符号只学形状, unique 不能 >=2")
        n_excl += bible.exclusive(sid)
    res.check(n_excl >= MIN_EXCL, "symbols 专属数", "有效专属 (unique>=2) 符号 %d 个, 要 >=%d" % (n_excl, MIN_EXCL))


def _characters(bible, song, res):
    pool = background_names(song.proj)
    res.check(len(bible.chars) >= MIN_CHARS, "characters 数量", "角色卡 %d 张, 要 >=%d" % (len(bible.chars), MIN_CHARS))
    for c in bible.chars:
        tag = "character[%s]" % c.get("name")
        names = [c.get("name")] + list(c.get("aliases") or [])
        res.check(any(name_hit(n, pool) for n in names), tag + " 实名",
                  "角色名或别名要能在 anime.background.json 的 characters 里找到")
        res.check(bool(c.get("temperament")) and nonempty(c.get("motion")) and nonempty(c.get("type_mood")),
                  tag + " 气质", "要写 temperament (词表), motion (运动语言), type_mood (字体气质)")
        cols = c.get("colors") or []
        bad = [k for k in cols if not (isinstance(k, dict) and HEX_RE.match(str(k.get("hex", ""))) and k.get("symbol") in bible.symbols)]
        res.check(cols and not bad, tag + " 色彩", "colors 每项要有 hex 与 symbol (指向符号词典, 说明颜色从哪来): %s" % bad[:2])


def _scenes(bible, song, res):
    res.check(len(bible.scenes) >= MIN_SCENES, "scenes 数量", "名场面 %d 个, 要 >=%d" % (len(bible.scenes), MIN_SCENES))
    for sid, s in bible.scenes.items():
        tag = "scene[%s]" % sid
        res.check(nonempty(s.get("what")) and nonempty(s.get("where")), tag + " 内容", "要写 what 与 where (话数或时间)")
        _refs_ok(bible, s.get("refs"), tag, res)
        res.check(bible.ref_sources(s.get("refs")), tag + " 来源", "名场面要有来源")
        miss = [x for x in s.get("symbols") or [] if x not in bible.symbols]
        res.check(not miss, tag + " 符号", "symbols 指向不存在的符号: %s" % miss)
    if not bible.quotes:
        res.warn("quotes", "没有台词呼应. 歌词确实不呼应任何台词时可以为空, 但要在 lyric-map 里写明")
    for qid, q in bible.quotes.items():
        tag = "quote[%s]" % qid
        res.check(nonempty(q.get("text")) and nonempty(q.get("speaker")), tag + " 内容", "要写台词原文 text 与 speaker")
        _refs_ok(bible, q.get("refs"), tag, res)
        res.check(bible.ref_sources(q.get("refs")), tag + " 来源", "台词要有来源, 记不清原文的不许写")
        for e in q.get("echo") or []:
            i = e.get("line") if isinstance(e, dict) else None
            res.check(isinstance(i, int) and 0 <= i < song.n and nonempty(e.get("how")), tag + " 呼应",
                      "echo 要有有效 line 与 how: %r" % e)


def _lyric_map(bible, song, res):
    rows = bible.data["lyric-map.json"].get("lines") or []
    seen, anchored, excl_lines = set(), 0, 0
    for r in rows:
        err = song.line_ok(r)
        if err:
            res.bad("lyric-map", err)
            continue
        i = r["line"]
        seen.add(i)
        tag = "lyric-map[%d]" % i
        b = r.get("basis")
        if not res.check(b in BASIS, tag + " basis", "basis 只能是 %s" % "/".join(BASIS)):
            continue
        if b == "none":
            res.check(nonempty(r.get("why")), tag + " 无对位", "basis=none 要写 why (为什么这句不对位)")
            continue
        refs = r.get("refs") or []
        miss = [x for x in refs if not bible.known_id(x)]
        res.check(nonempty(r.get("plot")) and refs and not miss, tag + " 对位",
                  "要写 plot (对应的剧情) 与 refs (符号/名场面/台词 id). 不存在的 id: %s" % miss)
        anchored += 1
        excl_lines += any(bible.exclusive(x) or _scene_excl(bible, x) for x in refs)
    miss = sorted(set(range(song.n)) - seen)
    res.check(not miss, "lyric-map 覆盖", "这些句没有对位行 (不对位也要写 basis=none): %s" % miss)
    if song.n:
        ratio = anchored / song.n
        # 0.5 只在两首成品上看过 (见 index.md 阈值一节), 未在反例上标定, 只报 WARN.
        if ratio < 0.5:
            res.warn("lyric-map 对位率", "%.0f%% 的句对上了剧情, 低于 50%%" % (ratio * 100))
        res.check(excl_lines >= 1, "lyric-map 专属对位", "没有一句对到专属符号或名场面, 等于没对位")


def _scene_excl(bible, x):
    s = bible.scenes.get(x) or bible.quotes.get(x)
    return bool(s) and any(bible.exclusive(y) for y in s.get("symbols") or [])
