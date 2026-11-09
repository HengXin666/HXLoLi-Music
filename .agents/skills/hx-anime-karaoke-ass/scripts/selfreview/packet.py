# -*- coding: utf-8 -*-
"""一轮自审的准备: 定要审的句, 增量抽帧, 写两份盲审包和答案.

rN/
  intent/packet.json   给意图盲审: 每句的歌词 + 截图. 不给剧本
  intent/*.png
  unique/packet.json   给专属性盲审: 高光句截图 + 5 个作品卡 (A-E). 不给歌词文件, 不给标题
  unique/*.png
  key.json             答案, 本轮句指纹, 每帧亮像素 (frames). 两个盲审都不许读
"""
import json, os, random, re, shutil, subprocess, sys

from selfreview.rv import SCRIPTS

ELEM_RE = re.compile(r"\|\s*\*\*([^|*]+)\*\*\s*\|")
N_CARDS = 5


def world_card(proj, k=8):
    """作品卡: anime.elements.md 里的元素名 (前 k 个). 没有就返回 None."""
    p = os.path.join(proj, "anime.elements.md")
    if not os.path.exists(p):
        return None
    names = [m.group(1).strip() for m in ELEM_RE.finditer(open(p, encoding="utf-8").read())]
    return names[:k] or None


def decoys(proj, roots):
    """干扰项: roots 下其他带 anime.elements.md 的工程. 按路径排序, 不随机挑."""
    me, mine, out = os.path.realpath(proj), world_card(proj), []
    for r in roots:
        for d, subs, files in os.walk(r):
            subs[:] = sorted(s for s in subs if not s.startswith((".", "__")) and s not in ("review", "judge", "out"))
            if "anime.elements.md" in files and os.path.realpath(d) != me:
                c = world_card(d)
                if c and c != mine and c not in out:      # 与本作相同的卡不能当干扰项
                    out.append(c)
    return out


def render(ass, times, out_dir, renderer, fontsdir=None):
    """真渲染器出帧. 返回 {t: png}. renderer=octopus (默认, 观众看到的) / ffmpeg (没有扩展标签时可用)."""
    os.makedirs(out_dir, exist_ok=True)
    got = {}
    if renderer == "octopus":
        cmd = [sys.executable, os.path.join(SCRIPTS, "render", "render_octopus.py"), ass, "--out", out_dir + "/",
               "--times", ",".join("%.2f" % t for t in times)]
        if fontsdir:
            cmd += ["--fontsdir", fontsdir]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("render_octopus 失败: %s" % (r.stderr.strip().splitlines()[-1:] or "?"))
        for t in times:
            f = os.path.join(out_dir, "%08.2f.png" % t)
            if os.path.exists(f):
                got[t] = f
        return got
    for t in times:
        f = os.path.join(out_dir, "%08.2f.png" % t)
        # 只造 1 帧, 把它的时间戳挪到 t: 不用从 0 解到 t
        vf = "setpts=PTS+%.3f/TB,subtitles=%s" % (t, ass.replace(":", "\\:")) + (":fontsdir=%s" % fontsdir if fontsdir else "")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=0x000000:s=1920x1080:d=0.04:r=25",
                        "-vf", vf, "-frames:v", "1", "-update", "1", f], check=True)
        got[t] = f
    return got


def lit_pixels(png):
    """亮像素: 黑底上 R+G+B > 20 的像素数 (与 render_octopus 打印的口径相同)."""
    from PIL import Image
    im = Image.open(png).convert("RGB").convert("L", (1, 1, 1, 0))   # L = min(255, R+G+B)
    return int(sum(im.histogram()[21:]))


def bar_moments(C, i):
    refs = {r.get("id"): r for r in C.bar.get("refs", [])}
    out = []
    for h in C.bar.get("highlights", []):
        if i in h.get("lines", []):
            for rid in h.get("refs", []):
                for m in (refs.get(rid) or {}).get("moments", []):
                    out.append("%s %s: %s" % (refs[rid].get("title", rid), m.get("t"), m.get("what")))
    return out


def lines_to_review(C, st, prev_hash, cur_hash):
    """要审的句: 预算里没过也没转人的句, 加上指纹变了的已过句 (改动波及, 要复审)."""
    from selfreview import budget as B
    want = set(B.todo(st))
    for k, L in st["lines"].items():
        i = int(k)
        if L["status"] == "pass" and prev_hash and prev_hash.get(str(i)) != cur_hash.get(i):
            want.add(i)
            L["status"] = "pending"
    return sorted(want)


def build(C, n, lines, renderer, roots, fontsdir=None, cur_hash=None):
    rd = C.rdir(n)
    if os.path.exists(rd):
        shutil.rmtree(rd)
    tmp = os.path.join(rd, "_frames")
    times = sorted({t for i in lines for t in C.times(i)})
    frames = render(C.ass, times, tmp, renderer, fontsdir) if times else {}
    miss = [t for t in times if t not in frames]
    if miss:
        raise SystemExit("这些时刻没出帧: %s" % miss)
    # 意图包: 帧名只带句号与时刻, 不带任何剧本信息
    os.makedirs(os.path.join(rd, "intent"))
    rows = []
    for i in lines:
        fs = []
        for t in C.times(i):
            name = "L%02d_%08.2f.png" % (i, t)
            shutil.copy(frames[t], os.path.join(rd, "intent", name))
            fs.append(name)
        row = dict(line=i, text=C.song.texts[i], frames=fs)
        if i in C.hl:              # 高光句给参照时刻, 盲审判是否到参照水平. 只给参照, 不给剧本
            row["bar"] = bar_moments(C, i)
        rows.append(row)
    json.dump(dict(format="self-review-intent", version=1, lines=rows), open(os.path.join(rd, "intent", "packet.json"), "w",
              encoding="utf-8"), ensure_ascii=False, indent=1)
    # 专属性包: 只审本轮里的高光句. 作品卡乱序, 帧名不带句号
    lit = {t: lit_pixels(f) for t, f in frames.items()}
    key = dict(round=n, lines=lines, hash={str(i): (cur_hash or {}).get(i) for i in lines}, unique={},
               frames=[dict(line=i, t=t, lit=lit[t]) for i in lines for t in C.times(i)])
    hls = [h for h in C.bar.get("highlights", []) if set(h.get("lines", [])) & set(lines)]
    me = world_card(C.proj)
    pool = decoys(C.proj, roots)
    if hls and (not me or len(pool) < N_CARDS - 1):
        raise SystemExit("专属性测试要本工程与至少 %d 个其他工程的 anime.elements.md (现有 %d 个). 用 --decoy-root 加目录"
                         % (N_CARDS - 1, len(pool)))
    items = []
    os.makedirs(os.path.join(rd, "unique"))
    for h in hls:
        R = random.Random("%s/%d" % (h["id"], n))
        cards = [me] + R.sample(pool, N_CARDS - 1)
        order = list(range(N_CARDS))
        R.shuffle(order)
        letters = "ABCDE"
        fs = []
        for j, t in enumerate(t for i in h["lines"] if i in lines for t in C.times(i)):
            name = "Q%d_%d.png" % (len(items) + 1, j)
            shutil.copy(frames[t], os.path.join(rd, "unique", name))
            fs.append(name)
        items.append(dict(q="Q%d" % (len(items) + 1), frames=fs,
                          cards={letters[k]: cards[order[k]] for k in range(N_CARDS)}))
        key["unique"]["Q%d" % len(items)] = dict(hl=h["id"], lines=h["lines"], answer=letters[order.index(0)])
    json.dump(dict(format="self-review-unique", version=1, questions=items), open(os.path.join(rd, "unique", "packet.json"), "w",
              encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(key, open(os.path.join(rd, "key.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    shutil.rmtree(tmp, ignore_errors=True)
    return rows, items
