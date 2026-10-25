#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""歌词多源获取：**一律从网络取文本**，并把"这份歌词从哪来"落成可校验的证据文件。

为什么必须走这一步、而不能直接照 MV 抄：MV 里的硬字幕常被裁切/水印遮挡/本身就是
TV size 删减版；从画面截图识别的文本会引入识别噪声（假名混淆、振假名被当成正文），
而且它抄的是"这一份剪辑里剩下的字"，不是作品本身。网络上（lrclib / 歌词站）拿到的是
**带时间轴的完整版**，逐字标注的读音切分也通常能照抄。
所以定序是: 网络同步歌词 > 网络纯文本 + 时间轴 > 纯人工听写（必须写 why）。
**画面截图识别不在这条链里**  见 SKILL.md 硬性规则：不从视频里提字幕。
时间轴的本地校准走语音（align_ctc / snap_timing / grid_align），不是看画面。

产物:
  <proj>/lyrics.source.json   来源、URL、抓取时间、行、sha256（门禁要读它）
  <proj>/lyrics.txt           待人工补振假名与中文的骨架（不覆盖已有文件）

用法:
  # 1) 自动：lrclib 同步歌词（推荐起点）
  hx-karaoke find_lyrics.py --project proj --title "<曲名>" --artist "<艺人>" --duration <秒>
  # 2) 指定本地 lrc + 从歌词站复制的纯文本（文本来自网络，时间轴可另配）
  hx-karaoke find_lyrics.py --project proj --title "<曲名>" --lrc proj/utaten.lrc --text proj/utaten.txt
  # 3) 只是登记已有的 lyrics.txt 来源（人工听写）
  hx-karaoke find_lyrics.py --project proj --register-manual --why "lrclib 无此曲，按官方 PV 听写"
"""
import argparse, csv, difflib, hashlib, io, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request

UA = "HXLoLi-assfx/1.0 (karaoke ass skill; contact: local)"
LRCLIB = "https://lrclib.net/api"


def http(url, data=None, timeout=30):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": "application/json"})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def norm(s):
    """曲名/艺人归一：全角转半角、去空格与常见修饰、小写。"""
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"[\s　]+", "", s)
    s = re.sub(r"[\(（\[【].*?[\)）\]】]", "", s)
    s = re.sub(r"(完整版|tvsize|tv-size|tvver|official|mv|pv|full|-)\b", "", s)
    return s.strip("-_ ")


def parse_lrc(text):
    """-> [(秒, 文本)]，忽略元信息行与空行。"""
    out = []
    for line in text.splitlines():
        m = re.match(r"^\[(\d+):(\d+(?:\.\d+)?)\](.*)$", line.strip())
        if not m:
            continue
        t = int(m.group(1)) * 60 + float(m.group(2))
        body = m.group(3).strip()
        if body:
            out.append((round(t, 3), body))
    return out


def fmt(t):
    return "%02d:%06.3f" % (int(t // 60), t % 60)


def score(cand, title, artist, dur):
    s, why = 0, []
    cn, ct = norm(cand.get("trackName") or cand.get("name")), norm(title)
    if ct and cn == ct:
        s += 40; why.append("曲名完全一致")
    elif ct and (ct in cn or cn in ct):
        s += 22; why.append("曲名近似")
    else:
        why.append("曲名不符")
    ca, ar = norm(cand.get("artistName")), norm(artist)
    if ar:
        if ca == ar:
            s += 20; why.append("艺人一致")
        elif ar in ca or ca in ar:
            s += 10; why.append("艺人近似")
        else:
            s -= 12; why.append("艺人不同(%s)" % (cand.get("artistName") or "?"))
    d = cand.get("duration")
    if dur and d:
        dd = abs(float(d) - float(dur))
        if dd <= 2:
            s += 25; why.append("时长吻合")
        elif dd <= 8:
            s += 12; why.append("时长接近(%.0fs)" % dd)
        elif dd > 30:
            s -= 20; why.append("时长差 %.0fs" % dd)
    if cand.get("syncedLyrics"):
        s += 15; why.append("带时间轴")
    if cand.get("instrumental"):
        s -= 60; why.append("标记为伴奏")
    # lrclib 的 instrumental 字段偶有缺失，标题里的字样才可靠
    for kw in ("instrumental", "off vocal", "offvocal", "カラオケ", "伴奏", "inst."):
        if kw in cn or kw in (cand.get("trackName") or "").lower():
            s -= 60; why.append("标题含 %s" % kw); break
    return s, ", ".join(why)


def lrclib_search(title, artist, dur):
    q = " ".join(x for x in (title, artist) if x)
    arr, err = None, None
    for attempt in range(3):            # 实测 lrclib 会偶发 503，重试即可，不要因此判它"没有这首"
        try:
            arr = json.loads(http(LRCLIB + "/search?" + urllib.parse.urlencode({"q": q})))
            break
        except Exception as exc:
            err = exc
            time.sleep(3 * (attempt + 1))
    if arr is None:
        print("[warn] lrclib 搜索失败(3 次): %s" % err, file=sys.stderr)
        return []
    out = []
    for c in arr:
        s, why = score(c, title, artist, dur)
        out.append(dict(source="lrclib", score=s, why=why,
                        url="https://lrclib.net/api/get/%s" % c.get("id"),
                        id=c.get("id"), trackName=c.get("trackName"), artistName=c.get("artistName"),
                        duration=c.get("duration"), synced=bool(c.get("syncedLyrics")),
                        lines=parse_lrc(c.get("syncedLyrics") or ""),
                        plain=(c.get("plainLyrics") or "").strip()))
    out.sort(key=lambda x: -x["score"])
    return out


def pair_lines(times, texts):
    """时间轴与歌词文本按行配对；行数不等时给出差异而不是静默截断。"""
    if len(times) != len(texts):
        sm = difflib.SequenceMatcher(a=[t for _, t in times], b=texts)
        diff = [op for op in sm.get_opcodes() if op[0] != "equal"]
        msg = "时间轴 %d 行 vs 文本 %d 行 对不上:\n" % (len(times), len(texts))
        for tag, i1, i2, j1, j2 in diff[:8]:
            msg += "  %s 轴[%d:%d]=%s  文本[%d:%d]=%s\n" % (tag, i1, i2, [x[1] for x in times[i1:i2]][:3],
                                                          j1, j2, texts[j1:j2][:3])
        sys.exit(msg + "  → 先对齐行数（删掉演奏段落/旁白行）再重跑，不要让它自动凑。")
    return [(times[i][0], texts[i]) for i in range(len(texts))]


def main():
    """Agent Notes
    .agents/notes/implemented/process/2026-10-01-karaoke-lyrics-source-ladder.md
    .agents/notes/implemented/process/2026-10-02-karaoke-steps-restructure.md
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--title", default=""); ap.add_argument("--artist", default="")
    ap.add_argument("--duration", type=float, default=0, help="官方完整版秒数（用于挑版本）")
    ap.add_argument("--lrc", help="本地 lrc 文件（时间轴来源）")
    ap.add_argument("--text", help="歌词文本文件（网络歌词站复制来的纯文本，按行与 --lrc 配对）")
    ap.add_argument("--lrc-url", default="", help="歌词站页面 URL，登记进证据（如 utaten 页面）")
    ap.add_argument("--min-score", type=float, default=40)
    ap.add_argument("--register-manual", action="store_true", help="放弃网络源，把人工听写登记为来源")
    ap.add_argument("--adopt", action="store_true",
                    help="把已存在的 lyrics.txt 反登记成证据（用于已有工程补证据，不改动歌词）")
    ap.add_argument("--source-kind", default="network", choices=["network", "manual"],
                    help="--adopt 时标明这份歌词的来源级别：network=来自网络（lrclib/歌词站），manual=人工听写")
    ap.add_argument("--url", default="", help="--adopt 时的来源 URL")
    ap.add_argument("--why", default="", help="--register-manual / --adopt 时必须给理由")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的 lyrics.txt")
    ap.add_argument("--no-write", action="store_true", help="只出证据文件，不写 lyrics.txt")
    a = ap.parse_args()
    os.makedirs(a.project, exist_ok=True)
    # Agent Notes: 卡拉OK skill 按步骤重构成 steps/NN-<key>/ 的契约 + impl 结构
    # 
    src_path = os.path.join(a.project, "lyrics.source.json")
    lyr_path = os.path.join(a.project, "lyrics.txt")

    lines, evi = [], {}
    if a.adopt:
        if not a.why:
            sys.exit("--adopt 必须给 --why：写清时间轴/文本/读音各来自哪里，否则门禁不认。")
        if not os.path.exists(lyr_path):
            sys.exit("--adopt 需要已存在的 %s" % lyr_path)
        for raw in open(lyr_path, encoding="utf-8"):
            if raw.strip().startswith("#") or " | " not in raw:
                continue
            p = [x.strip() for x in raw.split(" | ")]
            if not p[0] or p[0] == "-":
                continue
            m = re.match(r"^(\d+):(\d+(?:\.\d+)?)$", p[0])
            if m:
                lines.append((int(m.group(1)) * 60 + float(m.group(2)), p[1]))
        if not lines:
            sys.exit("从 %s 里没解析出带时间的行，检查格式（见 ../steps/2-lyrics/02-lyrics/impl/format.md）" % lyr_path)
        evi = dict(source=a.source_kind, engine="adopt", score=0, why=a.why, url=a.url or None, synced=True,
                   adopted_from=os.path.abspath(lyr_path),
                   registered_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        print("[adopt] 登记 %d 行，来源级别=%s" % (len(lines), a.source_kind))
    elif a.register_manual:
        if not a.why:
            sys.exit("--register-manual 必须给 --why（说明为什么网络源不可用），否则门禁不认。")
        if not os.path.exists(lyr_path):
            sys.exit("人工登记模式需要已存在的 %s" % lyr_path)
        for raw in open(lyr_path, encoding="utf-8"):
            if raw.strip().startswith("#") or " | " not in raw:
                continue
            p = [x.strip() for x in raw.split(" | ")]
            if not p[0] or p[0] == "-":
                continue
            m = re.match(r"^(\d+):(\d+(?:\.\d+)?)$", p[0])
            if m:
                lines.append((int(m.group(1)) * 60 + float(m.group(2)), p[1]))
        if not lines:
            sys.exit("从 %s 里没解析出带时间的行，检查格式（见 ../steps/2-lyrics/02-lyrics/impl/format.md）" % lyr_path)
        evi = dict(source="manual", engine="manual", score=0, why=a.why, url=a.lrc_url or None, synced=True,
                   registered_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        print("[manual] 已登记人工来源: %s（%d 行）" % (a.why, len(lines)))
    else:
        if a.lrc:
            times = parse_lrc(open(a.lrc, encoding="utf-8").read())
            texts = [x.strip() for x in open(a.text, encoding="utf-8").read().splitlines() if x.strip()] if a.text else [t for _, t in times]
            if a.text:
                lines = pair_lines(times, texts)
            else:
                lines = times
            # Agent Notes: 歌词来源定级  一律从网络取，时间轴校准走语音
            # 
            evi = dict(source="network", engine="local-lrc", score=60, why="本地时间轴" + ("+网络文本" if a.text else ""),
                       url=a.lrc_url or os.path.abspath(a.lrc), synced=True,
                       registered_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
            print("[local] %d 行 <- %s%s" % (len(lines), a.lrc, " + " + a.text if a.text else ""))
        else:
            cands = lrclib_search(a.title, a.artist, a.duration)
            if not cands:
                sys.exit("lrclib 没有候选。下一步：用 argo_search 找歌词站页面（后述），把纯文本存成 txt，"
                         "再配一份 lrc 后跑 --lrc/--text；实在没有就 --register-manual --why '...'。")
            print("候选:")
            for c in cands[:6]:
                print("  %5d  %-7s %6ss synced=%-5s %s  | %s" % (c["score"], c["source"], c["duration"],
                                                                 c["synced"], c["why"], c["trackName"]))
            best = cands[0]
            if best["score"] < a.min_score:
                sys.exit("最高分 %.0f < %.0f：不要凑合。改用歌词站文本(--text/--lrc-url) 或 --register-manual --why。"
                         % (best["score"], a.min_score))
            if not best["synced"]:
                print("[warn] 最佳候选无时间轴；需要另一份 lrc 或人工定时间轴。", file=sys.stderr)
            lines = best["lines"] if best["synced"] else [(float(i * 4), t) for i, t in enumerate(best["plain"].splitlines())]
            evi = dict(source="network", engine="lrclib", score=best["score"], why=best["why"], url=best["url"], id=best["id"],
                       trackName=best["trackName"], artistName=best["artistName"], duration=best["duration"],
                       synced=best["synced"], fetched_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
            print("[lrclib] 采用 id=%s %s（%s）" % (best["id"], best["trackName"], best["why"]))

    body = "".join("%s\n" % t for _, t in lines)
    # 两条指纹分开记：正文一定会被人工补注音改掉，时间列不该被改。
    # 门禁比对的是时间列指纹  这样"补注音"不会被误报成"换了来源"，
    # 而"偷偷把某句时间挪了"会被抓住。
    timeline = "".join("%s\n" % fmt(t) for t, _ in lines)
    evi.update(dict(title=a.title, artist=a.artist, duration=a.duration or None,
                    line_count=len(lines),
                    sha256=hashlib.sha256(body.encode()).hexdigest(),
                    timeline_sha256=hashlib.sha256(timeline.encode()).hexdigest(),
                    generated_by="scripts/find_lyrics.py", schema=1))
    json.dump(dict(evidence=evi, lines=[{"t": t, "jp": s} for t, s in lines]),
              open(src_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("证据 -> %s  (%d 行, sha256=%s)" % (src_path, len(lines), evi["sha256"][:12]))

    if a.no_write or a.adopt:
        return 0
    if os.path.exists(lyr_path) and not a.force:
        print("[skip] %s 已存在（要重建加 --force）。请人工核对它是否与证据 sha256 一致。" % lyr_path)
        return 0
    if os.path.exists(lyr_path) and not a.force:
        print("[skip] %s 已存在（要重建加 --force）" % lyr_path)
        return 0
    with open(lyr_path, "w", encoding="utf-8") as f:
        f.write("# 来源: %s %s\n" % (evi.get("engine", evi["source"]), evi.get("url", "")))
        f.write("# 待办: 补振假名逐字标注 [漢|よみ] 与中文翻译；读音以实际演唱为准\n")
        for t, s in lines:
            f.write("%s | %s | \n" % (fmt(t), s))
    print("骨架 -> %s（下一步：按 ../steps/2-lyrics/02-lyrics/impl/format.md 补注音与翻译）" % lyr_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
