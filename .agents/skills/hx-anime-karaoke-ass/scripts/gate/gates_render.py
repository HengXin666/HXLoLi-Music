# -*- coding: utf-8 -*-
"""出片前门禁(lyrics / timing / offset / coverage / health / calib): 追加时间轴与排版判据."""


import json
import os
import re
import sys

from gate.gates_meta import BAD, OK, WARN, load, parse_lines   # noqa: F401


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
        res.append((BAD, "lyrics.txt", "带振假名的行 %.0f%% < %.0f%%（%d/%d） 日文注音没做完"
                    % (ratio * 100, min_ruby * 100, ruby, rows)))
    else:
        res.append((OK, "lyrics.txt", "%d 行，注音 %d 行，音拍 %s" % (rows, ruby, mora)))
    return mora


def check_timing(proj, res, expect_mora):
    p, pa = os.path.join(proj, "timing.json"), os.path.join(proj, "timing_auto.json")
    d = load(p)
    if not d:
        res.append((BAD, "timing.json", "缺失  人工校时（第 6 步）没做"))
        return
    if expect_mora and len(d) != expect_mora:
        res.append((BAD, "timing.json", "音拍数 %d ≠ lyrics.txt 的 %d  用了别的歌词或漏了行" % (len(d), expect_mora)))
    else:
        res.append((OK, "timing.json", "%d 个音拍" % len(d)))
    fx = load(os.path.join(proj, "fixes.json"))
    if fx is None:
        res.append((BAD, "fixes.json", "缺失  人工校时必须留下记录（看过没问题也要写 {} + why）"))
    else:
        n = len([k for k in fx if not k.startswith("_")])
        why = fx.get("_why") if isinstance(fx, dict) else None
        if n == 0 and not why:
            res.append((WARN, "fixes.json", "0 条修正且没写 _why  要么是确实没问题（写一句），要么是没看频谱"))
        else:
            res.append((OK, "fixes.json", "%d 条修正%s" % (n, "，已注明: " + str(why)[:40] if why else "")))


def check_offset(proj, res):
    p = os.path.join(proj, "offset.json")
    d = load(p)
    if not d:
        res.append((BAD, "offset.json", "缺失  网络歌词的时间轴与这份视频的差量没测过（calibrate_offset.py，语音校准）"))
        return
    # 判据用**稳健**离散度（剔除结构性离群后的 p90-p10），缺失时退回全量值。
    # 依据见 calibrate_offset.py main 里的说明：整曲 MV 与 CD 版的分段差异会被下游逐行锚点吸收，
    # 用全量值会把这类工程永久判 FAIL。
    disp = d.get("dispersion_robust", d.get("dispersion"))
    med = d.get("median")
    if med is None or disp is None:
        res.append((BAD, "offset.json", "没有 median/dispersion  证据不可判定"))
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
    """歌词覆盖：漏句是最难自查的错  漏掉的行在成片里只是一段空白，
    越界/字体/时间/密度所有门禁都照常通过。实测一例漏了 2 句正词，
    其中一句正好落在 198.7-203.5s（成片里 4.84 秒无字幕，而该段确实在唱）。"""
    p = os.path.join(proj, "review", "coverage.txt")
    if not os.path.exists(p):
        res.append((BAD, "review/coverage.txt", "缺失  歌词覆盖审计没做（check_lyrics_coverage.py，会非零退出）"))
        return
    txt = open(p, encoding="utf-8").read()
    if "PASSED" in txt:
        res.append((OK, "review/coverage.txt", "网络歌词逐句有对应，无疑似漏句空档"))
    else:
        res.append((BAD, "review/coverage.txt", "有漏句嫌疑  见该文件；补齐 lyrics.txt 后重跑对齐"))


def check_health(proj, res):
    """时间轴体检必须真的做过、且真的通过。

    为什么单列这一项：check_timing_health.py 原先只打印报告、**退出码恒为 0**，
    实测有工程把 2 处 CTC 塌缩原样交付  timing.json 跨度 22.73s 而真值 1.50s，
    成片里那句歌词比声音晚了 20 秒，而所有其它门禁全绿。所以这里必须查**判定行**。
    """
    p = os.path.join(proj, "review", "health.txt")
    if not os.path.exists(p):
        res.append((BAD, "review/health.txt", "缺失  时间轴体检没做（check_timing_health.py 现在会非零退出）"))
        return
    try:
        txt = open(p, encoding="utf-8").read()
    except Exception as exc:
        res.append((BAD, "review/health.txt", "读不了: %s" % exc))
        return
    m1 = re.search(r"CTC塌缩\s*(\d+)\s*处", txt)
    m2 = re.search(r"句内间奏\s*(\d+)\s*处", txt)
    if not m1 or not m2:
        res.append((BAD, "review/health.txt", "没有判定行  报告是旧版脚本产的，重跑 check_timing_health.py"))
        return
    col, inn = int(m1.group(1)), int(m2.group(1))
    if col or inn:
        res.append((BAD, "review/health.txt",
                    "CTC塌缩 %d 处 / 句内间奏 %d 处（都应为 0） 长音与间奏被算进了歌词，字幕会慢几秒" % (col, inn)))
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
            res.append((WARN, "kf.json", "在，但没有 review/kf-report.md  kf_timing.py align 是不是没跑完？"))


def check_calib(proj, res):
    p = os.path.join(proj, "calib.json")
    if not os.path.exists(p):
        res.append((BAD, "calib.json", "缺失  注音高度必须实测（calibrate_ruby.py）"))
    else:
        res.append((OK, "calib.json", "在"))
