#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests",
# ]
# ///
"""多源搜番剧歌曲 MV，按「像不像真完整版」打分排序。

为什么不用 yt-dlp 的 ytsearch 当唯一来源: 它默认只搜 YouTube（实测 ytsearch10
返回的 10 条全是 YouTube id），而番剧 MV 的 1080p 源大量在 B 站。漏掉 B 站 =
拿 720p 凑合，还会误判成「找不到完整版」。

所以：B 站走官方搜索 API（要 cookie，否则 412），YouTube 走 yt-dlp，两个源都跑。

关键纪律: 这个脚本只出候选表 + 打分，不做最终决定。全部不达标就反问用户要链接，
不许自己挑一个凑合 —— 素材不行，后面 11 步全白做。
"""

import argparse, json, os, re, subprocess, sys, urllib.parse

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
BILI_COOKIE = "/tmp/bili_cookie.txt"


def _curl(args, timeout=40):
    return subprocess.run(["curl", "-s", "--max-time", str(timeout)] + args,
                          capture_output=True).stdout.decode("utf-8", "replace")


def bili_session():
    if not os.path.exists(BILI_COOKIE):
        _curl(["-c", BILI_COOKIE, "-o", "/dev/null", "https://www.bilibili.com/", "-H", "User-Agent: " + UA])
    return ["-b", BILI_COOKIE, "-H", "User-Agent: " + UA, "-H", "Referer: https://www.bilibili.com/"]


def _dur(s):
    if not s:
        return None
    try:
        p = [int(x) for x in str(s).split(":")]
        return p[-1] + p[-2] * 60 + (p[-3] * 3600 if len(p) > 2 else 0)
    except Exception:
        return None


def search_bilibili(query, limit=12):
    url = ("https://api.bilibili.com/x/web-interface/search/type?search_type=video&page=1&keyword="
           + urllib.parse.quote(query))
    out = _curl(bili_session() + [url])
    try:
        j = json.loads(out)
    except Exception:
        return []
    if j.get("code") != 0:
        print("[warn] bilibili: code=%s %s" % (j.get("code"), j.get("message")), file=sys.stderr)
        return []
    res = []
    for v in (j.get("data") or {}).get("result", [])[:limit]:
        bvid = v.get("bvid")
        if not bvid:
            continue
        res.append(dict(source="bilibili", id=bvid,
                        url="https://www.bilibili.com/video/" + bvid + "/",
                        title=re.sub(r"<[^>]+>", "", v.get("title") or ""),
                        dur=_dur(v.get("duration")), author=v.get("author") or ""))
    return res


def search_youtube(query, limit=10):
    try:
        out = subprocess.run(["yt-dlp", "--flat-playlist", "--no-warnings",
                              "--print", "%(id)s\t%(duration)s\t%(title)s",
                              "ytsearch" + str(limit) + ":" + query],
                             capture_output=True, timeout=150).stdout.decode("utf-8", "replace")
    except Exception:
        return []
    res = []
    for line in out.strip().splitlines():
        p = line.split("\t")
        if len(p) < 3 or not p[0].strip():
            continue
        try:
            d = int(float(p[1])) if p[1] not in ("NA", "None", "") else None
        except Exception:
            d = None
        res.append(dict(source="youtube", id=p[0],
                        url="https://www.youtube.com/watch?v=" + p[0],
                        title=p[2], dur=d, author=""))
    return res


def probe(url):
    out = subprocess.run(["yt-dlp", "--no-warnings", "--print",
                          "%(duration)s\t%(width)s\t%(height)s", url],
                         capture_output=True, timeout=180).stdout.decode("utf-8", "replace").strip()
    p = out.split("\t")
    if len(p) < 3:
        return None
    try:
        return dict(dur=float(p[0]) if p[0] not in ("NA", "") else None,
                    w=int(p[1] or 0), h=int(p[2] or 0))
    except Exception:
        return None


def score(c, target):
    if not c.get("dur"):
        return -100, "无时长"
    d = c["dur"]; dt = abs(d - target)
    s, why = 0, []
    if dt <= 3:
        s += 50; why.append("时长吻合(差%.0fs)" % dt)
    elif dt <= 10:
        s += 25; why.append("时长接近(差%.0fs)" % dt)
    elif d < target * 0.6:
        s -= 60; why.append("太短(%.0fs) 疑似 TV size/片段" % d)
    else:
        s -= 20; why.append("时长偏差%.0fs" % dt)
    h = c.get("h") or 0
    if h >= 1080:
        s += 40; why.append("%dp" % h)
    elif h >= 720:
        s += 10; why.append("%dp(偏低)" % h)
    elif h:
        s -= 30; why.append("%dp 过低" % h)
    t = c.get("title") or ""
    for kw, pen in (("钢琴", -40), ("翻弹", -40), ("Synthesia", -40), ("扒谱", -40),
                    ("架子鼓", -40), ("drum", -40), ("cover", -25), ("翻唱", -35),
                    ("MAD", -20), ("AMV", -20), ("reaction", -50)):
        if kw.lower() in t.lower():
            s += pen; why.append("疑似" + kw)
    for kw, bonus in (("完整版", 15), ("full", 10), ("无字幕", 10), ("creditless", 15),
                     ("ノンクレジット", 15)):
        if kw.lower() in t.lower():
            s += bonus; why.append(kw + "+")
    return s, ", ".join(why)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--target", type=float, required=True, help="官方完整版时长(秒)")
    ap.add_argument("--extra", action="append", default=[], help="追加搜索词，可重复")
    ap.add_argument("--probe", action="store_true", help="probe 每个候选的真实分辨率(慢)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    seen, cands = set(), []
    for qy in [a.query] + a.extra:
        for c in search_bilibili(qy) + search_youtube(qy):
            if c["url"] in seen:
                continue
            seen.add(c["url"]); cands.append(c)

    if a.probe:
        for c in cands:
            pr = probe(c["url"])
            if pr:
                c.update({k: v for k, v in pr.items() if v is not None})

    scored = []
    for c in cands:
        s, why = score(c, a.target)
        scored.append((s, why, c))
    scored.sort(key=lambda x: -x[0])

    if a.json:
        print(json.dumps([dict(score=s, why=w, **c) for s, w, c in scored], ensure_ascii=False, indent=1))
        return 0

    print("查询: %s   目标时长: %ss   候选 %d 条" % (a.query, a.target, len(scored)))
    print("")
    for s, why, c in scored:
        res = "%sx%s" % (c.get("w"), c.get("h")) if c.get("h") else "分辨率未测"
        flag = "OK " if s >= 40 else ("?? " if s >= 0 else "XX ")
        print("%s%5d  %-8s %7ss  %-11s %s" % (flag, s, c["source"], str(c.get("dur")), res, c["url"]))
        print("         " + c["title"][:70])
        if why:
            print("         理由: " + why)
    best = scored[0][0] if scored else -999
    if best < 40:
        print("")
        print(">>> 没有候选达标（最高分 <40）。不要凑合，反问用户要链接或确认用哪个。")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())