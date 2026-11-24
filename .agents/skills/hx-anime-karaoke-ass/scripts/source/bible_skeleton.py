#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从已有考据产物起一份设计圣经的骨架, 省去手抄. 只搬运, 不判断.

  hx-karaoke bible_skeleton.py --project proj [--force]

读 anime.elements.md (元素表的粗体行与文末编号来源) 与 lyrics.txt / timing.json, 写:
  bible/symbols.json    每行元素一条符号, refs 按证据里的 [n] 对上来源编号; unique 留 null 待填
  bible/lyric-map.json  每句一行, basis 留空待填
其余四份 (characters / scenes / directions / landing) 从 templates/bible/ 复制空模板.
已存在的文件不覆盖, 除非 --force. 填写口径见 steps/3-anime-bg/11-design-bible/index.md.
"""
import argparse, json, os, re, shutil, sys

SKILL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(SKILL, "scripts"))

ROW_RE = re.compile(r"^\|\s*\*\*([^*|]+)\*\*\s*\|\s*(\d+)\s*\|(.*)$", re.M)
SRC_RE = re.compile(r"^\s*(\d+)\.\s+(https?://\S+)", re.M)
CITE_RE = re.compile(r"\[(\d+)\]")
QUOTE_RE = re.compile(r"\[(\d+)\][^\[\"「]*?[\"「]([^\"」]+)[\"」]")
OFFICIAL_HINT = ("official", "公式", "jp/character", "/news/", "lisani", "thetv", "-anime", "anime.jp")


def slug(name, used):
    base = re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_").lower()
    if not base[:1].isalpha():
        base = "s%d" % (len(used) + 1)
    s, k = base, 2
    while s in used:
        s, k = "%s_%d" % (base, k), k + 1
    used.add(s)
    return s


def guess_type(url):
    """只给初值: 官网与主创访谈记 official, 其余 community. 原作原文要人工改成 original."""
    return "official" if any(h in url for h in OFFICIAL_HINT) else "community"


def symbols_from_elements(text):
    srcs = [{"id": "S%s" % n, "type": guess_type(u), "name": u.split("/")[2], "url": u} for n, u in SRC_RE.findall(text)]
    known = {s["id"] for s in srcs}
    used, out = set(), []
    for name, count, rest in ROW_RE.findall(text):
        cells = [c.strip() for c in rest.split("|")]
        ev = cells[0] if cells else ""
        quotes = {}
        for n, q in QUOTE_RE.findall(ev):
            quotes.setdefault(n, q)
        refs = [{"src": "S" + n, "quote": quotes.get(n, "TODO 摘原文")}
                for n in dict.fromkeys(CITE_RE.findall(ev)) if "S" + n in known]
        out.append({"id": slug(name, used), "name": name.strip(), "kind": "TODO", "unique": None, "unique_why": "",
                    "form": cells[-2] if len(cells) >= 3 else "", "refs": refs, "elements_count": int(count),
                    "evidence": ev})
    return srcs, out


def lyric_rows(proj):
    from judge.common import Song
    song = Song(proj)
    return [{"line": i, "text": t, "plot": "", "refs": [], "basis": ""} for i, t in enumerate(song.texts)]


def write(path, obj, force):
    if os.path.exists(path) and not force:
        print("跳过 (已存在): %s" % path)
        return
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("写出 %s" % path)


def main():
    """Agent Notes
    .agents/notes/implemented/feature/2026-11-17-karaoke-design-bible.md
    """
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    bdir = os.path.join(a.project, "bible")
    os.makedirs(bdir, exist_ok=True)
    ep = os.path.join(a.project, "anime.elements.md")
    if not os.path.isfile(ep):
        print("缺 anime.elements.md: 先做第 10 步", file=sys.stderr)
        return 2
    srcs, syms = symbols_from_elements(open(ep, encoding="utf-8").read())
    write(os.path.join(bdir, "symbols.json"),
          {"version": 1, "work": {"title": "TODO", "aliases": [], "redact": []}, "sources": srcs, "symbols": syms}, a.force)
    write(os.path.join(bdir, "lyric-map.json"), {"version": 1, "lines": lyric_rows(a.project)}, a.force)
    tdir = os.path.join(SKILL, "templates", "bible")
    for f in ("characters.json", "scenes.json", "directions.json", "landing.json"):
        dst = os.path.join(bdir, f)
        if os.path.exists(dst) and not a.force:
            print("跳过 (已存在): %s" % dst)
            continue
        shutil.copyfile(os.path.join(tdir, f), dst)
        print("写出 %s (空模板)" % dst)
    print("\n%d 个来源, %d 个符号. unique / kind / quote 都要人工填, 填完跑 check_bible.py" % (len(srcs), len(syms)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
