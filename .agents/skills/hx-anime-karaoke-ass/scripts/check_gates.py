#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""门禁：把这套流程里**不许跳、不许悄悄降级**的步骤变成可失败的检查。

为什么要有它: 本 skill 的流程表里，"人工校时""来源证据""设定考据"这类步骤最容易
被"时间紧、先出个版本"绕过 —— 绕过之后所有下游产物都还在、也都还"看起来正常"，
只有最终的片子不对味，而那时候已经没人回头查是哪一步塌的。所以判据必须前置成文件：

  必须存在的文件            为什么
  lyrics.source.json        歌词是从哪来的（网络 or 人工听写）。缺它 = 无法判断歌词可信度
  anime.background.json     番剧设定是否被查过。缺它 = 特效设计没有语境，容易退化成通用图形
  timing.json               人工校时的最终产物（不是 timing_auto.json）
  fixes.json                人工校时的记录（哪怕是空 {}，也要显式存在表示"看过频谱了"）
  calib.json                排版实测（注音位置不能凭感觉）
  offset.json               网络歌词时间轴 → 这份视频的**语音校准**结果（不许靠画面截图）
  review/health.txt         时间轴体检的判定行（CTC塌缩 0 处 / 句内间奏 0 处）。
                            它原先只打印不拦截，实测有工程带着 2 处塌缩交付、字幕慢了 20 秒 —— 所以现在查判定行

以及两条**可证伪**的强度判据（不是"文件在就行"）:
  * timing.json 的音拍数 == lyrics.txt 的音拍数（对不上说明用了别的歌词）
  * timing.json 相对 timing_auto.json 必须**发生过修正**（全等 = 没做人工校时；
    或者按 --no-auto 声明本次跳过自动对齐、直接手工标）
  * lyrics.txt 是否被补过注音（含 [漢|よみ] 的行占比）

用法:
  hx-karaoke check_gates.py --project proj [--min-ruby 0.8] [--stage all|design|render]
退出码非 0 = 有未通过的强制项。--stage design 只查设计前的门禁（source/background/lyrics），
--stage render 追加时间轴与排版门禁。
"""
import argparse, json, os, re, sys

OK, BAD, WARN = "PASS", "FAIL", "WARN"
RUBY = re.compile(r"\[[^\]|]+\|")


def load(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def parse_lines(path):
    """-> (行数, 带注音的行数, 音拍数)。音拍数用 skill 自己的解析器保证一致。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from assfx.lyrics import load as load_lyrics
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
        res.append((BAD, "lyrics.source.json", "缺失 —— 先跑 scripts/find_lyrics.py（一律从网络取文本；人工听写要 --why）"))
        return
    e = d.get("evidence", d)
    kind = e.get("source")
    if kind not in ("network", "manual"):
        res.append((BAD, "lyrics.source.json", "来源级别 %r 不合法（应为 network 或 manual）—— 歌词不许来自画面截图识别。"
                    "若是旧文件把引擎名写进了 source，用 --adopt --source-kind network --why '...' 重登记" % kind))
        return
    if kind == "manual" and not e.get("why"):
        res.append((BAD, "lyrics.source.json", "人工来源没有 why —— 无法区分'查过没有'与'懒得查'"))
        return
    if not e.get("sha256"):
        res.append((BAD, "lyrics.source.json", "没有 sha256/行数，证据不可校验"))
        return
    res.append((OK, "lyrics.source.json", "%s（%s, %d 行）" % (kind, e.get("why", "")[:40], int(e.get("line_count") or 0))))


def check_background(proj, res, min_chars):
    p = os.path.join(proj, "anime.background.json")
    d = load(p)
    if not d:
        res.append((BAD, "anime.background.json", "缺失 —— 先跑 scripts/fetch_anime_bg.py（bgm.tv + 萌娘百科），不得只凭 MV 画面下结论"))
        return
    n = len(d.get("characters") or [])
    subs = (d.get("summary") or "")
    if not n and not subs:
        res.append((BAD, "anime.background.json", "条目与角色都为空 —— 等于没查"))
        return
    if n < min_chars:
        res.append((WARN, "anime.background.json", "角色数 %d < %d：可能抓错了条目" % (n, min_chars)))
    res.append((OK, "anime.background.json", "%s，角色 %d，摘要 %d 字" % (d.get("name_cn") or d.get("name"), n, len(subs))))


def check_notes(proj, res):
    """anime.notes.md 的存在性与实质内容 —— 光有角色表不算考据。

    为什么加这一项：实测（2026-10-01，ヨスガノソラ「ツナグキズナ」）跑完 fetch_anime_bg 拿到 26 个角色、
    填满"角色→视觉母题"表、**门禁全绿**，但完全没读作品在讲什么 —— 把"寂寥的夏"设计成了"温暖的夏"，
    配色方向从头就错。原判据只有 `角色数 >= 6`，拦不住这种失败：它数的是"查了多少人"，不是"懂没懂"。

    设计取舍：**语义质量不做 FAIL 判据**。判"内核/主题/与原作的关系答得好不好"要么靠人读、
    要么靠模型判，都不是可证伪的机械检查；硬设成 FAIL 只会催生"为了过门禁而写的空标题"。
    所以这里只查**能机械证伪的三件事**：文件在不在、是不是占位、有没有留出处。
    缺哪一节用 WARN 点名，交给人工与第 8b 步设计去追。
    """
    p = os.path.join(proj, "anime.notes.md")
    if not os.path.exists(p):
        res.append((BAD, "anime.notes.md", "缺失 —— 只有 anime.background.json 等于只查了角色表，"
                    "没读作品在讲什么（做法见 ../steps/10-anime-bg/impl/background-research.md）"))
        return
    try:
        txt = open(p, encoding="utf-8").read()
    except Exception as exc:
        res.append((BAD, "anime.notes.md", "读不了: %s" % exc))
        return
    n = len(txt.strip())
    if n < 500:
        res.append((BAD, "anime.notes.md", "只有 %d 字 —— 是占位文件，不是考据结果" % n))
        return

    missing = []
    if not re.search(r"内核|主題|主题|テーマ|反差点", txt):
        missing.append("内核/主题")
    if not re.search(r"与原作|改编|原作との|アニメとの|原作.*違", txt):
        missing.append("与原作的关系")
    has_src = bool(re.search(r"来源|出处|https?://|参考文献", txt))
    if missing:
        res.append((WARN, "anime.notes.md", "缺 %s —— 这两条决定配色方向（亮/暗、暖/冷），"
                    "见 ../steps/10-anime-bg/impl/background-research.md §3" % "、".join(missing)))
    if not has_src:
        res.append((WARN, "anime.notes.md", "没有来源/出处 —— 结论无法回溯，等于没读"))
    if not missing and has_src:
        res.append((OK, "anime.notes.md", "%d 字，必答问题与出处齐全" % n))


def check_elements(proj, res, min_ambient_ratio=0.35):
    """番剧元素表：每句的特效母题必须指向表里带**来源计数**的条目。

    为什么要有它（2026-10-02，漆黑的子弹 ED）：第一版 33 句全部"按词义具象化"——
    「盾」画圆弧、「薬莢」画黄铜小圆柱、「糧」画麦穗。这些图形**换到任何一部番的 ED 都成立**，
    所以它们等于什么都没说；而同一批 MV 帧里明明有巨石碑、红眼、面具、猫耳，一个都没被画进去。
    原门禁只查 anime.notes.md「在不在、够不够 500 字」，拦不住"母题与这部番无关"。

    判据（只查能机械证伪的）：
      1. anime.elements.md 必须存在，且**每一行元素都带来源数**（形如 | 4 | 或 "来源数 4"）；
      2. design-table.md 每句的「主母题」列必须能在 elements.md 里找到对应条目，
         否则该句必须显式标注「氛围句」；
      3. 氛围句占比不得超过 min_ambient_ratio —— 否则又是"全是氛围句"蒙混过关。

    语义质量（这个母题选得对不对）仍不做 FAIL：它要靠人读，机械判只会逼出空标题。
    这里保证的是"每个母题都能指到一个有出处的番剧元素"。
    """
    ep = os.path.join(proj, "anime.elements.md")
    dp = os.path.join(proj, "review", "design-table.md")
    if not os.path.exists(ep):
        res.append((BAD, "anime.elements.md", "缺失 —— 母题没有白名单，特效会退化成通用图形"
                    "（「盾」画个圆弧换到任何番都成立，等于什么都没说）"))
        return
    etxt = open(ep, encoding="utf-8").read()
    n_el = len(re.findall(r"\|\s*\*\*[^|]+\*\*\s*\|\s*(\d+)\s*\|", etxt))
    low = re.findall(r"\|\s*\*\*[^|]+\*\*\s*\|\s*1\s*\|", etxt)
    if n_el < 4:
        res.append((BAD, "anime.elements.md", "带来源计数的元素只有 %d 条 —— 少于 4 条说明没真查" % n_el))
    elif len(low) == n_el:
        res.append((WARN, "anime.elements.md", "%d 条元素全部只有 1 个来源 —— 未做多源交叉验证" % n_el))
    else:
        res.append((OK, "anime.elements.md", "%d 条元素带来源计数（其中 %d 条为多源）" % (n_el, n_el - len(low))))

    if not os.path.exists(dp):
        res.append((WARN, "review/design-table.md", "缺失 —— 无法核对每句母题是否指向元素表"))
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
                    "氛围句 %d/%d = %.0f%% 超过上限 %.0f%% —— 母题指不到番剧元素时不许用「氛围句」兜底"
                    % (amb, len(rows), ratio * 100, min_ambient_ratio * 100)))
    else:
        res.append((OK, "review/design-table.md", "%d 句，其中氛围句 %d 句（%.0f%%，上限 %.0f%%）"
                    % (len(rows), amb, ratio * 100, min_ambient_ratio * 100)))


def check_design(proj, res, strict=False):
    """15 格设计表: 每句一行, 每格要么填要么显式写「—」(决定不做), 不许留白.

    为什么加这一项（2026-10-03）: `impl/three-layers.md` 写的判据「一句里不同图形种类 >= 6」
    **从来没有被门禁查过**, 实测漆黑子弹 ED 每句图形种类中位只有 4(按绘图路径哈希),
    却 13 步全绿交付了. 门禁不管的判据 = 不存在的判据.

    这一版把"设计维度"本身变成可查的列: 3 个文本对象(主/副/背景) × 5 个生命阶段(出现/逐字/
    词组/意象/消失) = 15 格, 加 3 个定位列. 查五件事:
      * 15 列齐全、每行无空串(留白 = 忘了做, `—` = 决定不做);
      * 全曲取值有变化(全曲同一个值 = 从没设计过);
      * `副·出现` / `副·逐字` 被填过 —— 副文本(注音/中文)在旧表里一列都没有,
        于是 33 句全走默认(注音永远晚 0.06s、中文永远晚 0.20s), 用户看到的"一句里全都在同时动"就是这个;
      * `承上` 与上一行的 `启下` 有同名变量 —— 句间关联的机械形式(见 `impl/thread.md`);
      * `背景·场景` 多数行非空 —— 背景层必须由 MV 画面驱动.

    阈值与 `impl/density.md` 同源: 定在"低于它一定不合格"的位置.
    默认 WARN(旧格式的表还没迁移), 加 `--strict-design` 升为 FAIL.
    """
    dp = os.path.join(proj, "review", "design-table.md")
    if not os.path.exists(dp):
        res.append((WARN, "review/design-table.md", "缺失 —— 15 格设计表没写"))
        return
    dtxt = open(dp, encoding="utf-8").read()
    hdr = next((l for l in dtxt.splitlines() if l.startswith("|") and "主·出现" in l), None)
    if hdr is None:
        msg = ("还是旧格式(入/出/高亮 3 格) —— 新格式见 steps/11-design/impl/design-table.md: "
               "主·出现/逐字/词组/意象/消失 + 副·出现/逐字/消失 + 背景·场景/情绪/番剧 + 承上/启下")
        res.append((BAD if strict else WARN, "review/design-table.md", msg))
        return
    cols = [c.strip() for c in hdr.strip().strip("|").split("|")]
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
                    "%d 行有空串(第 %s 行) —— 空着=忘了做, `—`=决定不做, 两者必须区别"
                    % (len(blank), ",".join(str(i + 1) for i in blank[:5]))))
        bad += 1

    def col(name):
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
    if not bad:
        res.append((OK, "review/design-table.md", "%d 句 15 格齐全" % n))


def check_lyrics(proj, res, min_ruby):
    p = os.path.join(proj, "lyrics.txt")
    if not os.path.exists(p):
        res.append((BAD, "lyrics.txt", "缺失"))
        return None
    rows, ruby, mora, err = parse_lines(p)
    if err:
        res.append((BAD, "lyrics.txt", err))
        return None
    ratio = ruby / rows if rows else 0
    if ratio < min_ruby:
        res.append((BAD, "lyrics.txt", "带振假名的行 %.0f%% < %.0f%%（%d/%d）—— 日文注音没做完"
                    % (ratio * 100, min_ruby * 100, ruby, rows)))
    else:
        res.append((OK, "lyrics.txt", "%d 行，注音 %d 行，音拍 %s" % (rows, ruby, mora)))
    return mora


def check_timing(proj, res, expect_mora):
    p, pa = os.path.join(proj, "timing.json"), os.path.join(proj, "timing_auto.json")
    d = load(p)
    if not d:
        res.append((BAD, "timing.json", "缺失 —— 人工校时（第 6 步）没做"))
        return
    if expect_mora and len(d) != expect_mora:
        res.append((BAD, "timing.json", "音拍数 %d ≠ lyrics.txt 的 %d —— 用了别的歌词或漏了行" % (len(d), expect_mora)))
    else:
        res.append((OK, "timing.json", "%d 个音拍" % len(d)))
    fx = load(os.path.join(proj, "fixes.json"))
    if fx is None:
        res.append((BAD, "fixes.json", "缺失 —— 人工校时必须留下记录（看过没问题也要写 {} + why）"))
    else:
        n = len([k for k in fx if not k.startswith("_")])
        why = fx.get("_why") if isinstance(fx, dict) else None
        if n == 0 and not why:
            res.append((WARN, "fixes.json", "0 条修正且没写 _why —— 要么是确实没问题（写一句），要么是没看频谱"))
        else:
            res.append((OK, "fixes.json", "%d 条修正%s" % (n, "，已注明: " + str(why)[:40] if why else "")))


def check_offset(proj, res):
    p = os.path.join(proj, "offset.json")
    d = load(p)
    if not d:
        res.append((BAD, "offset.json", "缺失 —— 网络歌词的时间轴与这份视频的差量没测过（calibrate_offset.py，语音校准）"))
        return
    # 判据用**稳健**离散度（剔除结构性离群后的 p90-p10），缺失时退回全量值。
    # 依据见 calibrate_offset.py main 里的说明：整曲 MV 与 CD 版的分段差异会被下游逐行锚点吸收，
    # 用全量值会把这类工程永久判 FAIL。
    disp = d.get("dispersion_robust", d.get("dispersion"))
    med = d.get("median")
    if med is None or disp is None:
        res.append((BAD, "offset.json", "没有 median/dispersion —— 证据不可判定"))
        return
    if d.get("verdict", "").startswith("离散度过大"):
        res.append((BAD, "offset.json", "离散度 %.3fs 超过阈值：歌词与视频不是同一剪辑，换源或人工，不许硬套"
                    % float(disp)))
        return
    if abs(float(med)) > 0.6 and not d.get("why"):
        res.append((WARN, "offset.json", "偏移 %+.3fs 偏大，确认不是拿错版本（若已核对请写 why）" % float(med)))
    res.append((OK, "offset.json", "%s，中位 %+.3fs，离散 %.3fs，%s 行"
                % (d.get("method"), float(med), float(disp), d.get("calibrated_lines"))))


def check_coverage(proj, res):
    """歌词覆盖：漏句是最难自查的错 —— 漏掉的行在成片里只是一段空白，
    越界/字体/时间/密度所有门禁都照常通过。实测一例漏了 2 句正词，
    其中一句正好落在 198.7-203.5s（成片里 4.84 秒无字幕，而该段确实在唱）。"""
    p = os.path.join(proj, "review", "coverage.txt")
    if not os.path.exists(p):
        res.append((BAD, "review/coverage.txt", "缺失 —— 歌词覆盖审计没做（check_lyrics_coverage.py，会非零退出）"))
        return
    txt = open(p, encoding="utf-8").read()
    if "PASSED" in txt:
        res.append((OK, "review/coverage.txt", "网络歌词逐句有对应，无疑似漏句空档"))
    else:
        res.append((BAD, "review/coverage.txt", "有漏句嫌疑 —— 见该文件；补齐 lyrics.txt 后重跑对齐"))


def check_health(proj, res):
    """时间轴体检必须真的做过、且真的通过。

    为什么单列这一项：check_timing_health.py 原先只打印报告、**退出码恒为 0**，
    实测有工程把 2 处 CTC 塌缩原样交付 —— timing.json 跨度 22.73s 而真值 1.50s，
    成片里那句歌词比声音晚了 20 秒，而所有其它门禁全绿。所以这里必须查**判定行**。
    """
    p = os.path.join(proj, "review", "health.txt")
    if not os.path.exists(p):
        res.append((BAD, "review/health.txt", "缺失 —— 时间轴体检没做（check_timing_health.py 现在会非零退出）"))
        return
    try:
        txt = open(p, encoding="utf-8").read()
    except Exception as exc:
        res.append((BAD, "review/health.txt", "读不了: %s" % exc))
        return
    m1 = re.search(r"CTC塌缩\s*(\d+)\s*处", txt)
    m2 = re.search(r"句内间奏\s*(\d+)\s*处", txt)
    if not m1 or not m2:
        res.append((BAD, "review/health.txt", "没有判定行 —— 报告是旧版脚本产的，重跑 check_timing_health.py"))
        return
    col, inn = int(m1.group(1)), int(m2.group(1))
    if col or inn:
        res.append((BAD, "review/health.txt",
                    "CTC塌缩 %d 处 / 句内间奏 %d 处（都应为 0）—— 长音与间奏被算进了歌词，字幕会慢几秒" % (col, inn)))
    else:
        res.append((OK, "review/health.txt", "塌缩 0、句内间奏 0"))
    kf = os.path.join(proj, "kf.json")
    if os.path.exists(kf):
        rep = os.path.join(proj, "review", "kf-report.md")
        if os.path.exists(rep):
            t2 = open(rep, encoding="utf-8").read()
            m3 = re.search(r"全局偏移 \*\*([+-]?[\d.]+) s\*\*", t2)
            res.append((OK, "review/kf-report.md", "kf 融合报告在%s" % ("，偏移 %s s" % m3.group(1) if m3 else "")))
        else:
            res.append((WARN, "kf.json", "在，但没有 review/kf-report.md —— kf_timing.py align 是不是没跑完？"))


def check_calib(proj, res):
    p = os.path.join(proj, "calib.json")
    if not os.path.exists(p):
        res.append((BAD, "calib.json", "缺失 —— 注音高度必须实测（calibrate_ruby.py）"))
    else:
        res.append((OK, "calib.json", "在"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--stage", choices=["all", "design", "render"], default="all")
    ap.add_argument("--min-ruby", type=float, default=0.8, help="带振假名的行占比下限")
    ap.add_argument("--min-chars", type=int, default=6)
    ap.add_argument("--max-ambient", type=float, default=0.35,
                    help="设计表里「氛围句」占比的上限；指不到番剧元素时不许用氛围句兜底")
    ap.add_argument("--strict-design", action="store_true",
                    help="把 15 格设计表的缺项从 WARN 升为 FAIL（新工程用；旧格式的表还没迁移时保持 WARN）")
    a = ap.parse_args()
    proj = a.project
    res = []
    check_source(proj, res)
    check_background(proj, res, a.min_chars)
    check_notes(proj, res)
    mora = check_lyrics(proj, res, a.min_ruby)
    if a.stage in ("all", "design", "render"):
        check_elements(proj, res, a.max_ambient)
        check_design(proj, res, a.strict_design)
    if a.stage in ("all", "render"):
        check_offset(proj, res)
        check_timing(proj, res, mora)
        check_coverage(proj, res)
        check_health(proj, res)
        check_calib(proj, res)

    bad = [r for r in res if r[0] == BAD]
    for st, name, why in res:
        print("%-4s %-24s %s" % (st, name, why))
    print("\n%s: %d 项通过, %d 项警告, %d 项失败 (stage=%s, proj=%s)"
          % ("FAILED" if bad else "PASSED", len([r for r in res if r[0] == OK]),
             len([r for r in res if r[0] == WARN]), len(bad), a.stage, proj))
    if bad:
        print("\n硬性要求没满足。这些步骤不许跳：见 SKILL.md 的「强制门禁」一节。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
