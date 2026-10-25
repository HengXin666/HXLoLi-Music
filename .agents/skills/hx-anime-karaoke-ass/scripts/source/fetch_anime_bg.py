#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""抓番剧设定（原作背景）落成结构化证据，供逐句特效设计引用。

为什么必须做: 只看 MV 画面 + 简单搜索就下结论，特效只能做到"好看但空洞"  同一部番的
OP/ED，懂设定的人能画出角色专属的符号(魔女帽 / 缺一只就飞不动的单翼)，不懂的人只能画通用星星。
skill 把"读原作设定"定成第 1 步的必做项，产物就是本脚本写的 anime.background.json。

数据源（都是实测可用的公开端点，无需 key；不给 key 时只列角色名，有 key 时输出中文简介）:
  bgm.tv   api.bgm.tv/v0/subjects/{id}/characters  角色 + 人物简介（BGM 是中文条目，最全）
  bgm.tv   api.bgm.tv/v0/search/subjects          按番名搜条目 id（POST）
  实测 (2026-10-01): 无需 token 即可拿到条目 summary + 26 个角色的中文简介；token 只是提高限额。
  萌娘百科 zh.moegirl.org.cn/<条目>                媒体API 实测 403（只允许白名单 UA），
                                                   改抓 HTML 正文并用 ../steps/3-anime-bg/10-anime-bg/impl/background-research.md（萌娘百科正文用 argo_fetch 读）
                                                   里的做法抽正文  即"必须由人/AI 读一遍"。

用法:
  hx-karaoke fetch_anime_bg.py --project proj --anime "<番名>" --bgm-id <id>
  hx-karaoke fetch_anime_bg.py --project proj --anime "<番名>" --bgm-token "$BGM_TOKEN"
  hx-karaoke fetch_anime_bg.py --project proj --register --why "..." --url "https://zh.moegirl.org.cn/..."
"""
import argparse, hashlib, json, os, re, sys, time, urllib.parse, urllib.request

UA = "HXLoLi-assfx/1.0 (karaoke ass skill)"
API = "https://api.bgm.tv/v0"


def http(url, data=None, token="", timeout=30):
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": UA, "Accept": "application/json"})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def retry(fn, n=3, what=""):
    last = None
    for i in range(n):
        try:
            return fn()
        except Exception as exc:
            last = exc
            time.sleep(2 * (i + 1))
    print("[warn] %s 失败(%d 次): %s" % (what, n, last), file=sys.stderr)
    return None


def search_subject(name, token):
    body = json.dumps({"keyword": name, "filter": {"type": [2]}}).encode()
    raw = retry(lambda: http(API + "/search/subjects?limit=5", data=body, token=token), what="bgm 搜索")
    if not raw:
        return []
    try:
        arr = (json.loads(raw) or {}).get("data") or []
    except Exception:
        return []
    out = []
    for s in arr:
        out.append(dict(id=s.get("id"), name=s.get("name"), name_cn=s.get("name_cn"),
                        date=s.get("date"), platform=s.get("platform"), summary=(s.get("summary") or "").strip()))
    return out


def subject(sid, token):
    raw = retry(lambda: http("%s/subjects/%s" % (API, sid), token=token), what="bgm 条目")
    return json.loads(raw) if raw else None


def characters(sid, token):
    raw = retry(lambda: http("%s/subjects/%s/characters" % (API, sid), token=token), what="bgm 角色")
    return json.loads(raw) if raw else []


def pick_summary(c):
    """中文简介优先（production/career 字段与设定无关，不取）。"""
    for k in ("summary", "name_cn", "name"):
        v = (c.get(k) or "").strip()
        if v:
            return v
    return ""


def main():
    """Agent Notes
    .agents/notes/implemented/process/2026-10-01-karaoke-anime-background-required.md
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--anime", required=True, help="番剧名（日文原名最好）")
    ap.add_argument("--song", default="", help="曲名，便于证据里写清是为哪首歌查的")
    ap.add_argument("--bgm-id", type=int, default=0)
    ap.add_argument("--bgm-token", default=os.environ.get("BGM_TOKEN", ""),
                    help="bgm.tv 个人令牌；可选，实测匿名请求同样返回角色中文简介")
    ap.add_argument("--moegirl", default="", help="萌娘百科条目 URL（人读正文后写进 notes 的出处）")
    ap.add_argument("--register", action="store_true", help="不联网，登记已由人读过的资料")
    ap.add_argument("--why", default="", help="--register 时必给：读了哪几处、得出什么")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.project, exist_ok=True)
    # Agent Notes: 番剧设定考据成为特效设计的前置步骤
    # 
    path = os.path.join(a.project, "anime.background.json")
    if os.path.exists(path) and not a.force:
        print("[skip] %s 已存在（重抓加 --force）" % path)
        return 0

    evi = dict(anime=a.anime, song=a.song or None, schema=1,
               generated_by="scripts/fetch_anime_bg.py",
               fetched_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    if a.register:
        if not a.why:
            sys.exit("--register 必须给 --why：写清读了哪几处资料、结论是什么，否则门禁不认。")
        evi.update(source="manual", why=a.why, url=a.moegirl or None, subjects=[], characters=[])
        json.dump(evi, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("[manual] -> %s" % path)
        return 0

    sid = a.bgm_id
    subs = []
    if not sid:
        subs = search_subject(a.anime, a.bgm_token) or []
        if not subs:
            sys.exit("bgm 搜不到「%s」。带 --bgm-id 指定条目，或 --register 手工登记。"
                     "萌娘百科正文另外用 argo_fetch 读（见 ../steps/3-anime-bg/10-anime-bg/impl/background-research.md）。" % a.anime)
        print("bgm 候选:")
        for s in subs[:5]:
            print("  %8s  %-28s %-8s %s" % (s["id"], (s["name_cn"] or s["name"])[:28], s["date"], s["platform"]))
        sid = subs[0]["id"]
        print("[bgm] 采用 id=%s（不确定就加 --bgm-id 指定）" % sid)

    sub = subject(sid, a.bgm_token) or {}
    evi.update(source="bgm.tv", bgm_id=sid, url="https://bgm.tv/subject/%s" % sid,
               name=sub.get("name"), name_cn=sub.get("name_cn"), date=sub.get("date"),
               platform=sub.get("platform"), summary=(sub.get("summary") or "").strip())
    chars = characters(sid, a.bgm_token) or []
    evi["characters"] = [dict(name=c.get("name"), name_cn=c.get("name_cn"), relation=c.get("relation"),
                              summary=pick_summary(c), id=c.get("id")) for c in chars]
    if sum(1 for c in evi["characters"] if c["summary"]) == 0:
        evi["note"] = ("角色简介全为空  实测 bgm.tv 匿名请求也给简介，出现这种情况通常是条目错了或接口降级。"
                       "按 ../steps/3-anime-bg/10-anime-bg/impl/background-research.md 用萌娘百科正文补，并设 BGM_TOKEN 重跑对照。")
    evi["moegirl_url"] = a.moegirl or None
    evi["body_sha256"] = hashlib.sha256(json.dumps(evi["characters"], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    subs_keep = [s for s in subs if s["id"] == sid]
    if subs_keep:
        evi["search_hit"] = subs_keep[0]
    json.dump(evi, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("-> %s  (角色 %d 个, 简介 %d 条)" % (path, len(evi["characters"]),
                                            sum(1 for c in evi["characters"] if c["summary"])))
    print("下一步: 按 ../steps/3-anime-bg/10-anime-bg/impl/background-research.md 把「主题/符号/角色→视觉母题」写成 notes.md，"
          "design.md 的母题速查必须与它对齐。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
