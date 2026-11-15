# -*- coding: utf-8 -*-
"""参考 ASS / 音频的选择. 不做优劣判断 (不比条数, 不比新旧), 只认明确来源, 按顺序:

  1. manual   工程目录 ref.json 里的 {"ass": "static/music/..."} (或 "audio"). 指的文件不存在或不在候选集里 -> error, 不回退.
              (和 playlist / choose() 同一条边界: 手写 ref.json 也不能绕过候选集.)
  2. playlist 仓库根 playlist.json 里 assUrl (audioUrl) 文件名含歌名的条目, 即网站实际发布的那份.
              多条 -> ambiguous; 有但不在候选集里 (跨目录 / 文件不存在) -> error, 不静默跳过.
  3. unique   static/music/<番名>/ 下文件名含歌名的只有一份.
  4. 多份候选且前三步都没结果 -> ambiguous, 不选. 一份都没有 -> none.

返回 dict(path, source, error, err_kind, set_at, candidates). path 只在 manual/playlist/unique 时非空.
err_kind (error 非空时): ref_json = 工程 ref.json 的问题 (界面可清除) / playlist = playlist.json 的问题 / candidates = 多份候选未定. 前端按它判断, 不看 error 文字.
"""
import json, os, time
from urllib.parse import unquote

FILE = "ref.json"
EXT = {"ass": (".ass",), "audio": (".mp3", ".flac", ".m4a", ".ogg")}
URL = {"ass": "assUrl", "audio": "audioUrl"}


def candidates(root, anime, song, kind):
    d = os.path.join(root, "static", "music", anime)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d)
                  if song in f and f.lower().endswith(EXT[kind]) and os.path.isfile(os.path.join(d, f)))


def resolve(root, anime, song, pdir, kind="ass"):
    cands = candidates(root, anime, song, kind)
    res = dict(path=None, source=None, error=None, err_kind=None, set_at=None, candidates=cands)
    rel = lambda p: os.path.relpath(p, root)

    mf = os.path.join(pdir, FILE)
    if os.path.exists(mf):
        try:
            m = json.load(open(mf, encoding="utf-8"))
        except ValueError as e:
            return dict(res, source="error", err_kind="ref_json", error="%s 不是合法 JSON: %s" % (FILE, e))
        v = m.get(kind) if isinstance(m, dict) else None
        if v is not None:
            f = os.path.normpath(os.path.join(root, str(v)))
            if not os.path.isfile(f):
                return dict(res, source="error", err_kind="ref_json", error="%s 指定的文件不存在: %s" % (FILE, v))
            if f not in cands:
                return dict(res, source="error", err_kind="ref_json", error="%s 指定的文件不在 static/music/%s/ 的候选里 (文件名不含「%s」或跨目录): %s" % (FILE, anime, song, v))
            return dict(res, path=f, source="manual", set_at=m.get(kind + "_set_at"))

    pl = os.path.join(root, "playlist.json")
    if os.path.exists(pl):
        try:
            items = json.load(open(pl, encoding="utf-8"))
        except ValueError as e:
            return dict(res, source="error", err_kind="playlist", error="playlist.json 不是合法 JSON: %s" % e)
        hits = set()
        for it in items if isinstance(items, list) else []:
            u = it.get(URL[kind]) if isinstance(it, dict) else None
            if isinstance(u, str) and song in os.path.basename(unquote(u)):
                hits.add(os.path.normpath(os.path.join(root, unquote(u).lstrip("/"))))
        hits = sorted(hits)
        if len(hits) > 1:
            return dict(res, source="ambiguous", err_kind="playlist", error="playlist.json 有 %d 条 %s 含「%s」: %s" % (len(hits), URL[kind], song, ", ".join(rel(h) for h in hits)))
        if hits:
            if hits[0] not in cands:
                return dict(res, source="error", err_kind="playlist", error="playlist.json 的 %s 不在 static/music/%s/ 的候选里 (跨目录或文件不存在): %s" % (URL[kind], anime, rel(hits[0])))
            return dict(res, path=hits[0], source="playlist")

    if len(cands) == 1:
        return dict(res, path=cands[0], source="unique")
    if not cands:
        return dict(res, source="none")
    return dict(res, source="ambiguous", err_kind="candidates", error="%d 份候选, 没有明确来源 (%s / playlist.json), 未指定" % (len(cands), FILE))


def choose(root, anime, song, pdir, kind, rel_path):
    """界面里点「用这份」: 只接受候选集里的文件; rel_path=None 清除手动指定. 写入时间留痕."""
    mf = os.path.join(pdir, FILE)
    m = {}
    if os.path.exists(mf):
        try:
            m = json.load(open(mf, encoding="utf-8"))
        except ValueError:
            m = {}
        if not isinstance(m, dict):
            m = {}
    if rel_path is None:
        m.pop(kind, None)
        m.pop(kind + "_set_at", None)
    else:
        f = os.path.normpath(os.path.join(root, rel_path))
        if f not in candidates(root, anime, song, kind):
            raise ValueError("不是候选文件: %s" % rel_path)
        m[kind] = os.path.relpath(f, root)
        m[kind + "_set_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    tmp = mf + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(m, fp, ensure_ascii=False, indent=2)
    os.replace(tmp, mf)
    if not m:
        os.remove(mf)


if __name__ == "__main__":
    # 全仓库体检: 按 playlist.json 每首歌 (歌名取 title 括号前) + static/music 下不在 playlist 的目录, 统计各来源数量
    import re, sys
    from collections import Counter
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    pl = json.load(open(os.path.join(root, "playlist.json"), encoding="utf-8"))
    keys = [(unquote(it["audioUrl"]).split("/")[3], re.split(r" \(|（", it["title"])[0].strip()) for it in pl]
    seen = {a for a, _ in keys}
    music = os.path.join(root, "static", "music")
    for a in sorted(os.listdir(music)):
        if a not in seen and a != "fonts" and os.path.isdir(os.path.join(music, a)):
            for f in sorted(os.listdir(os.path.join(music, a))):
                if f.endswith(".ass"):
                    keys.append((a, os.path.splitext(f)[0].split(" - ", 1)[-1].strip()))
    for kind in ("ass", "audio"):
        c = Counter()
        for a, s in keys:
            r = resolve(root, a, s, os.devnull, kind)
            c[r["source"]] += 1
            print("%-5s %-8s %-10s %s | %s" % (kind, r["source"], a, s, os.path.basename(r["path"] or "") or r["error"] or "-"))
        print("%s 合计 %d 首: %s" % (kind, len(keys), dict(c)))
