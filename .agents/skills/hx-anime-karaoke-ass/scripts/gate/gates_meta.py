# -*- coding: utf-8 -*-
"""设计前门禁(source / background / notes / elements / design): 只读工程文件, 不碰 ass.

判据与理由见 gate/check_gates.py 的模块头.
"""
import json
import os
import re
import sys

OK, BAD, WARN = "PASS", "FAIL", "WARN"
RUBY = re.compile(r"\[[^\]|]+\|")


def load(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def parse_lines(path):
    """-> (行数, 带注音的行数, 音拍数). 音拍数用 skill 自己的解析器保证一致."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from assfx.base.lyrics import load as load_lyrics
    rows = [x for x in open(path, encoding="utf-8") if x.strip() and not x.lstrip().startswith("#")]
    ruby = sum(1 for x in rows if RUBY.search(x))
    try:
        lines = load_lyrics(path)
    except Exception as exc:
        return len(rows), ruby, None, "解析失败: %s" % exc
    mora = sum(len(u["morae"]) for ln in lines for u in ln["units"])
    return len(rows), ruby, mora, None


def check_source(proj, res):
    p = os.path.join(proj, "lyrics.source.json")
    d = load(p)
    if not d:
        res.append((BAD, "lyrics.source.json", "缺失  先跑 scripts/find_lyrics.py（一律从网络取文本；人工听写要 --why）"))
        return
    e = d.get("evidence", d)
    kind = e.get("source")
    if kind not in ("network", "manual"):
        res.append((BAD, "lyrics.source.json", "来源级别 %r 不合法（应为 network 或 manual） 歌词不许来自画面截图识别。"
                    "若是旧文件把引擎名写进了 source，用 --adopt --source-kind network --why '...' 重登记" % kind))
        return
    if kind == "manual" and not e.get("why"):
        res.append((BAD, "lyrics.source.json", "人工来源没有 why  无法区分'查过没有'与'懒得查'"))
        return
    if not e.get("sha256"):
        res.append((BAD, "lyrics.source.json", "没有 sha256/行数，证据不可校验"))
        return
    res.append((OK, "lyrics.source.json", "%s（%s, %d 行）" % (kind, e.get("why", "")[:40], int(e.get("line_count") or 0))))


def check_background(proj, res, min_chars):
    # Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
    # 
    """Agent Notes
    .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
    """
    p = os.path.join(proj, "anime.background.json")
    d = load(p)
    if not d:
        res.append((BAD, "anime.background.json", "缺失  先跑 scripts/fetch_anime_bg.py（bgm.tv + 萌娘百科），不得只凭 MV 画面下结论"))
        return
    n = len(d.get("characters") or [])
    subs = (d.get("summary") or "")
    if not n and not subs:
        res.append((BAD, "anime.background.json", "条目与角色都为空  等于没查"))
        return
    if n < min_chars:
        res.append((WARN, "anime.background.json", "角色数 %d < %d：可能抓错了条目" % (n, min_chars)))
    res.append((OK, "anime.background.json", "%s，角色 %d，摘要 %d 字" % (d.get("name_cn") or d.get("name"), n, len(subs))))


def check_notes(proj, res):
    """anime.notes.md 的存在性与实质内容  光有角色表不算考据。

    为什么加这一项：实测（2026-10-01）跑完 fetch_anime_bg 拿到 26 个角色、
    填满"角色→视觉母题"表、**门禁全绿**，但完全没读作品在讲什么  把"寂寥的夏"设计成了"温暖的夏"，
    配色方向从头就错。原判据只有 `角色数 >= 6`，拦不住这种失败：它数的是"查了多少人"，不是"懂没懂"。

    设计取舍：**语义质量不做 FAIL 判据**。判"内核/主题/与原作的关系答得好不好"要么靠人读、
    要么靠模型判，都不是可证伪的机械检查；硬设成 FAIL 只会催生"为了过门禁而写的空标题"。
    所以这里只查**能机械证伪的三件事**：文件在不在、是不是占位、有没有留出处。
    缺哪一节用 WARN 点名，交给人工与第 8b 步设计去追。
    """
    p = os.path.join(proj, "anime.notes.md")
    if not os.path.exists(p):
        res.append((BAD, "anime.notes.md", "缺失  只有 anime.background.json 等于只查了角色表，"
                    "没读作品在讲什么（做法见 ../steps/3-anime-bg/10-anime-bg/impl/background-research.md）"))
        return
    try:
        txt = open(p, encoding="utf-8").read()
    except Exception as exc:
        res.append((BAD, "anime.notes.md", "读不了: %s" % exc))
        return
    n = len(txt.strip())
    if n < 500:
        res.append((BAD, "anime.notes.md", "只有 %d 字  是占位文件，不是考据结果" % n))
        return

    missing = []
    if not re.search(r"内核|主題|主题|テーマ|反差点", txt):
        missing.append("内核/主题")
    if not re.search(r"与原作|改编|原作との|アニメとの|原作.*違", txt):
        missing.append("与原作的关系")
    has_src = bool(re.search(r"来源|出处|https?://|参考文献", txt))
    if missing:
        res.append((WARN, "anime.notes.md", "缺 %s  这两条决定配色方向（亮/暗、暖/冷），"
                    "见 ../steps/3-anime-bg/10-anime-bg/impl/background-research.md §3" % "、".join(missing)))
    if not has_src:
        res.append((WARN, "anime.notes.md", "没有来源/出处  结论无法回溯，等于没读"))
    if not missing and has_src:
        res.append((OK, "anime.notes.md", "%d 字，必答问题与出处齐全" % n))


def check_elements(proj, res, min_ambient_ratio=0.35):
    """番剧元素表：每句的特效母题必须指向表里带**来源计数**的条目。

    为什么要有它（2026-10-02，漆黑的子弹 ED）：第一版 33 句全部"按词义具象化"
    「盾」画圆弧、「薬莢」画黄铜小圆柱、「糧」画麦穗。这些图形**换到任何一部番的 ED 都成立**，
    所以它们等于什么都没说；而同一批 MV 帧里明明有作品专属的地标物与角色特征，一个都没被画进去。
    原门禁只查 anime.notes.md「在不在、够不够 500 字」，拦不住"母题与这部番无关"。

    判据（只查能机械证伪的）：
      1. anime.elements.md 必须存在，且**每一行元素都带来源数**（形如 | 4 | 或 "来源数 4"）；
      2. design-table.md 每句的「主母题」列必须能在 elements.md 里找到对应条目，
         否则该句必须显式标注「氛围句」；
      3. 氛围句占比不得超过 min_ambient_ratio  否则又是"全是氛围句"蒙混过关。

    语义质量（这个母题选得对不对）仍不做 FAIL：它要靠人读，机械判只会逼出空标题。
    这里保证的是"每个母题都能指到一个有出处的番剧元素"。
    """
    ep = os.path.join(proj, "anime.elements.md")
    dp = os.path.join(proj, "review", "design-table.md")
    if not os.path.exists(ep):
        res.append((BAD, "anime.elements.md", "缺失  母题没有白名单，特效会退化成通用图形"
                    "（「盾」画个圆弧换到任何番都成立，等于什么都没说）"))
        return
    etxt = open(ep, encoding="utf-8").read()
    n_el = len(re.findall(r"\|\s*\*\*[^|]+\*\*\s*\|\s*(\d+)\s*\|", etxt))
    low = re.findall(r"\|\s*\*\*[^|]+\*\*\s*\|\s*1\s*\|", etxt)
    if n_el < 4:
        res.append((BAD, "anime.elements.md", "带来源计数的元素只有 %d 条  少于 4 条说明没真查" % n_el))
    elif len(low) == n_el:
        res.append((WARN, "anime.elements.md", "%d 条元素全部只有 1 个来源  未做多源交叉验证" % n_el))
    else:
        res.append((OK, "anime.elements.md", "%d 条元素带来源计数（其中 %d 条为多源）" % (n_el, n_el - len(low))))

    if not os.path.exists(dp):
        res.append((WARN, "review/design-table.md", "缺失  无法核对每句母题是否指向元素表"))
        return
    dtxt = open(dp, encoding="utf-8").read()
    rows = [l for l in dtxt.splitlines() if l.startswith("| ") and l.count("|") >= 8
            and not re.match(r"^\|\s*[-#]|^\|\s*#|^\|\s*句", l)]
    if not rows:
        res.append((WARN, "review/design-table.md", "解析不出设计表行（应每句一行、含母题列）"))
        return
    amb = sum(1 for r in rows if "氛围句" in r or "母题组" in r)
    ratio = amb / len(rows)
    if ratio > min_ambient_ratio:
        res.append((BAD, "review/design-table.md",
                    "氛围句 %d/%d = %.0f%% 超过上限 %.0f%%  母题指不到番剧元素时不许用「氛围句」兜底"
                    % (amb, len(rows), ratio * 100, min_ambient_ratio * 100)))
    else:
        res.append((OK, "review/design-table.md", "%d 句，其中氛围句 %d 句（%.0f%%，上限 %.0f%%）"
                    % (len(rows), amb, ratio * 100, min_ambient_ratio * 100)))


def check_brief(proj, res):
    """song-brief.md: 这首歌与作品的关系  决定绘图元素与风格取谁的.

    为什么要有它(实测): agent 跑着跑着就忘了这首歌在讲什么, 从第 5 句起退化成
    "按词义画图形", 与番剧无关. anime.notes.md 记的是**作品**, 这份记的是**这首歌**.
    两者之差就是"这首歌是不是围绕某个角色写的"这类判断.

    只查能机械证伪的(与 check_notes 同分寸):
      1. 存在;
      2. 四个小节标题齐全;
      3. 非占位(>= 500 字);
      4. 「歌曲在番剧背景下的分析」节里点名了至少一个角色, 且该名字在
         anime.background.json 的 characters 里找得到  这条正对
         "这首是围绕某角色整季经历写的, 所以元素与风格要取该角色的".
    语义质量(这个角色选得对不对)不做 FAIL.
    """
    p = os.path.join(proj, "song-brief.md")
    if not os.path.exists(p):
        res.append((BAD, "song-brief.md", "缺失  先写它再动手做特效（见 shared/hard-rules.md 第 4b 条）"))
        return
    try:
        txt = open(p, encoding="utf-8").read()
    except Exception as exc:
        res.append((BAD, "song-brief.md", "读不了: %s" % exc))
        return
    t = txt.strip()
    if len(t) < 500:
        res.append((BAD, "song-brief.md", "只有 %d 字, 已到占位水平（需 >=500）" % len(t)))
        return
    secs = ["番剧背景", "歌曲纯歌词意境分析", "歌曲在番剧背景下的分析", "歌词特效"]
    miss = [s for s in secs if s not in txt]
    if miss:
        res.append((BAD, "song-brief.md", "缺小节: %s" % "、".join(miss)))
        return
    # 第 3 节必须点名一个真实角色
    m = re.search(r"##\s*歌曲在番剧背景下的分析(.*?)(?=\n##\s|\Z)", txt, re.S)
    sec = m.group(1) if m else ""
    bg = load(os.path.join(proj, "anime.background.json")) or {}
    names = {c.get("name") for c in (bg.get("characters") or []) if c.get("name")}
    names |= {c.get("name_cn") for c in (bg.get("characters") or []) if c.get("name_cn")}
    hit = sorted(n for n in names if n and n in sec)
    if not names:
        res.append((WARN, "song-brief.md", "anime.background.json 里没有角色，无法核对第 3 节点名的角色"))
    elif not hit:
        res.append((BAD, "song-brief.md",
                    "「歌曲在番剧背景下的分析」没点名任何角色  这首歌对应谁 / 哪段经历没写清, "
                    "元素与风格就没有取舍依据"))
    else:
        res.append((OK, "song-brief.md", "四节齐全，%d 字，点名角色 %s" % (len(t), "/".join(hit[:3]))))


STE_BAD = ("赋能", "闭环", "抓手", "拉通", "尽快", "若干", "大概", "多次",
           "以上", "以下", "以内", "进行优化", "做出决定")


def check_prose(proj, res):
    """写作规范(STE 受控写作): 只查能机械证伪的三样.

    为什么要有它: 描述写得比做得好听, 与实际产物脱节时没人发现. 行长的上限不是
    文风偏好  单句超长 = 一句话里塞了多个动作, 读的人无法照着做.
    """
    files = [os.path.join(proj, "song-brief.md"),
             os.path.join(proj, "anime.notes.md"),
             os.path.join(proj, "anime.elements.md"),
             os.path.join(proj, "review", "channels.md")]
    long_sent = []
    bad_punct = []
    bad_word = []
    for f in files:
        if not os.path.exists(f):
            continue
        base = os.path.basename(f)
        for i, ln in enumerate(open(f, encoding="utf-8"), 1):
            s = ln.rstrip("\n")
            if not s.strip() or s.lstrip().startswith(("#", "|", ">", "-", "`")):
                continue
            # 中文标点: 句读与引号, 用半角
            for cp in ("，", "。", "、", "；", "：", "！", "？", "（", "）", "“", "”"):
                if cp in s:
                    bad_punct.append("%s:%d" % (base, i))
                    break
            for w in STE_BAD:
                if w in s and not re.search(r"\d\s*%s" % w, s):
                    bad_word.append("%s:%d %s" % (base, i, w))
                    break
            # 单句长度: 按句读切, 取最长的一段
            parts = [x for x in re.split(r"[.;:!?]", s) if x.strip()]
            for pt in parts:
                n = len(re.findall(r"[\u4e00-\u9fff]", pt))
                if n > 45:
                    long_sent.append("%s:%d(%d字)" % (base, i, n))
                    break
    if bad_punct:
        res.append((WARN, "写作:标点", "%d 处用了中文标点（需半角）: %s"
                    % (len(bad_punct), ", ".join(bad_punct[:3]))))
    if long_sent:
        res.append((WARN, "写作:句长", "%d 行有超长句（>45 汉字）: %s"
                    % (len(long_sent), ", ".join(long_sent[:3]))))
    if bad_word:
        res.append((WARN, "写作:用词", "%d 处用了含糊/套话词: %s"
                    % (len(bad_word), ", ".join(bad_word[:3]))))
    if not (bad_punct or long_sent or bad_word):
        res.append((OK, "写作规范", "标点/句长/用词 全部通过"))


def check_design(proj, res, strict=False):
    """15 格设计表: 每句一行, 每格要么填要么显式写「—」(决定不做), 不许留白.

    为什么加这一项（2026-10-03）: `impl/three-layers.md` 写的判据「一句里不同图形种类 >= 6」
    **从来没有被门禁查过**, 实测某工程每句图形种类中位只有 4(按绘图路径哈希),
    却 13 步全绿交付了. 门禁不管的判据 = 不存在的判据.

    这一版把"设计维度"本身变成可查的列: 3 个文本对象(主/副/背景) × 5 个生命阶段(出现/逐字/
    词组/意象/消失) = 15 格, 加 3 个定位列. 查五件事:
      * 15 列齐全、每行无空串(留白 = 忘了做, `—` = 决定不做);
      * 全曲取值有变化(全曲同一个值 = 从没设计过);
      * `副·出现` / `副·逐字` 被填过  副文本(注音/中文)在旧表里一列都没有,
        于是 33 句全走默认(注音永远晚 0.06s、中文永远晚 0.20s), 用户看到的"一句里全都在同时动"就是这个;
      * `承上` 与上一行的 `启下` 有同名变量  句间关联的机械形式(见 `impl/thread.md`);
      * `背景·场景` 多数行非空  背景层必须由 MV 画面驱动.

    阈值与 `impl/density.md` 同源: 定在"低于它一定不合格"的位置.
    默认 WARN(旧格式的表还没迁移), 加 `--strict-design` 升为 FAIL.
    """
    dp = os.path.join(proj, "review", "design-table.md")
    if not os.path.exists(dp):
        res.append((WARN, "review/design-table.md", "缺失  15 格设计表没写"))
        return
    dtxt = open(dp, encoding="utf-8").read()
    hdr = next((l for l in dtxt.splitlines() if l.startswith("|") and "主·出现" in l), None)
    if hdr is None:
        # Agent Notes: hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开
        # 
        msg = ("还是旧格式(入/出/高亮 3 格)  新格式见 steps/4-kfx/42-text-main/impl/design-table.md: "
               "主·出现/逐字/词组/意象/消失 + 副·出现/逐字/消失 + 中·词对应 + 背景·场景/情绪/番剧 + 承上/启下")
        res.append((BAD if strict else WARN, "review/design-table.md", msg))
        return
    cols = [c.strip() for c in hdr.strip().strip("|").split("|")]
    if "中·词对应" not in cols:
        res.append((BAD if strict else WARN, "review/design-table.md",
                    "缺 `中·词对应` 列  中文不做逐字, 它的视觉必须由「对应哪个日文词」驱动"
                    "（见 shared/hard-rules.md 第 6d 条）；缺这一列 = 中文层没有设计"))
    rows = [l for l in dtxt.splitlines()
            if l.startswith("|") and l.count("|") >= len(cols) and "主·出现" not in l
            and not re.match(r"^\|\s*[-: ]+\|", l)]
    if not rows:
        res.append((BAD if strict else WARN, "review/design-table.md", "表头在但解析不出数据行"))
        return
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    n, bad = len(cells), 0

    blank = [i for i, c in enumerate(cells) if any(x == "" for x in c)]
    if blank:
        res.append((BAD if strict else WARN, "review/design-table.md",
                    "%d 行有空串(第 %s 行)  空着=忘了做, `—`=决定不做, 两者必须区别"
                    % (len(blank), ",".join(str(i + 1) for i in blank[:5]))))
        bad += 1

    def col(name):
        """Agent Notes
        .agents/notes/implemented/process/2026-10-05-karaoke-scripts-grouping.md
        """
        i = cols.index(name)
        return [c[i] for c in cells]

    # 空串在上一条已经报过; 这里的统计只认"真的填了"(既不是空也不是放弃符)
    def filled(name):
        return sum(1 for x in col(name) if x not in ("", "—"))

    # 样本太少时多样性的分母不可信(3 种取值要求至少 3 行), 降级为 WARN 而不是假 FAIL
    diverse = n >= 4
    lvl = (lambda ok: (OK if ok else BAD)) if (strict and diverse) else (lambda ok: (OK if ok else WARN))

    def varies(name, need):
        v = set(col(name)) - {"—", ""}
        ok = len(v) >= need
        res.append((lvl(ok), "design-table:" + name,
                    "%d 种取值%s%s" % (len(v), "" if ok else "（需 >=%d, 全曲同一个值=从没设计过）" % need,
                                        "" if diverse else "；仅 %d 行, 样本不足只给 WARN" % n)))
        return ok

    varies("主·逐字", 3)
    varies("副·出现", 3)
    nz = filled("副·逐字") / n
    res.append((lvl(nz >= 0.5), "design-table:副·逐字", "%.0f%% 的行填了注音逐拍" % (nz * 100)))
    carry = sum(1 for a, b in zip(cells, cells[1:])
                if set(re.findall(r"[\u4e00-\u9fffA-Za-z_]+", a[cols.index("启下")]))
                & set(re.findall(r"[\u4e00-\u9fffA-Za-z_]+", b[cols.index("承上")])))
    cr = carry / max(1, n - 1)
    res.append((lvl(cr >= 0.6), "design-table:承上/启下",
                "%d/%d 行的承上与上一行启下有同名变量（需 >=60%%）" % (carry, n - 1)))
    sc = filled("背景·场景") / n
    res.append((lvl(sc >= 0.7), "design-table:背景·场景", "%.0f%% 的行指到具体镜头（需 >=70%%）" % (sc * 100)))
    # 中·词对应: 中文不做逐字, 若连词对应也不写, 这一层就是纯背景字
    cnvals = col("中·词对应")
    cnf = sum(1 for x in cnvals if x not in ("", "—"))
    res.append((lvl(cnf / n >= 0.6), "design-table:中·词对应",
                "%d/%d 行填了中文词对应（需 >=60%%）" % (cnf, n)))
    # 同句只许选一层: 混用 = 没想清楚哪层在做主
    mixed = [i for i, x in enumerate(cnvals)
             if sum(1 for lv in ("L1", "L2", "L3") if lv in x) > 1]
    if mixed:
        res.append((BAD if strict else WARN, "design-table:中·词对应",
                    "%d 行同句混用了 L1/L2/L3（第 %s 行） 每句只能选一层"
                    % (len(mixed), ",".join(str(i + 1) for i in mixed[:5]))))
    if not bad:
        res.append((OK, "review/design-table.md", "%d 句 17 格齐全" % n))
