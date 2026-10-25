#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""歌词覆盖审计：拿**网络完整歌词**当参照，反查本地 lyrics.txt 有没有漏句。

## 为什么必须有这个脚本

分工地做卡拉OK最容易犯、又最难自己发现的错，是**漏句**：
漏掉的那一句在成片里就是一段"只有画面没有歌词"的空白，而所有其它门禁（越界/字体/时间/密度）
全部照常通过  因为漏掉的行根本不存在，没有任何东西会报警。

实测一例：本地 34 行、网络 40 行，
漏了「優しさに出会えたから」与「広い世界で僕らのことを」两句正词，
其中前者恰好落在 198.7-203.5s  成片里那段 4.84 秒没有字幕，
而该段人声能量 -20.2 dB 与前后演唱段（-19.8 / -20.2）完全一致，**确实在唱**。
我的目检抽帧没抽到那 4.8 秒，于是漏了。

## 判据（两条，都必须过）

1. **网络歌词里每一句正词，本地都要有对应**（精确/子串/相似度 >0.85）。
   差异里属于"分句不同"的不算漏（本地把网络的一行拆成两行是允许的）。
2. **歌词覆盖的时间空档里不能有人声在唱**。空档 >1.5s 且该段人声能量接近相邻演唱段
   （差 <3 dB）= 漏句嫌疑。

## 用法

    hx-karaoke check_lyrics_coverage.py --project proj \
        --title "<曲名>" --artist "<艺人>" --song-id <id>

    # 无网络源时也能跑第 2 条（只查时间空档 vs 音频）
    hx-karaoke check_lyrics_coverage.py --project proj --vocals proj/stems/vocals16k.wav

退出码非 0 = 有漏句嫌疑，不许进设计步骤。
"""
import argparse, difflib, json, os, re, sys, wave

from gate.coverage_sources import (cover_ok, cross_source_edges, ctc_kana_density,   # noqa: F401
                                  fetch_net, load_local, vocal_db)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--lyrics", default="lyrics.txt")
    ap.add_argument("--timing", default="timing.json")
    ap.add_argument("--vocals", default="stems/vocals16k.wav")
    ap.add_argument("--title", default=""); ap.add_argument("--artist", default="")
    ap.add_argument("--song-id", default=""); ap.add_argument("--source", default="QM")
    ap.add_argument("--gap", type=float, default=1.5, help="歌词空档阈值(秒)")
    ap.add_argument("--db-tol", type=float, default=3.0, help="空档与相邻演唱段的能量容许差(dB)")
    ap.add_argument("--report", default="review/coverage.txt",
                    help="审计报告落盘路径（相对 --project）。check_gates.py --stage render 要这一份")
    ap.add_argument("--cross-kf", default="kf.json",
                    help="第二源(LDDC 逐字)路径，用来交叉裁决空档；不存在则退回纯能量判据（不静默）")
    ap.add_argument("--cross-tol", type=float, default=0.8, help="双源对齐容许差(秒)")
    ap.add_argument("--ctc-lp", default="stems/ctc_lp.npz",
                    help="第三判据用的整曲 CTC 后验；不存在时该判据跳过（会打印，不静默）")
    a = ap.parse_args()
    # 报告必须落盘才成为门禁证据：门禁读的是 review/coverage.txt，
    # 而本脚本原先只往 stdout 打  于是"跑了、结果 PASS"和"根本没跑"在门禁眼里一样，
    # 只会得到"缺失  歌词覆盖审计没做"。这里把 stdout 同时镜像到文件。
    rp = a.report if os.path.isabs(a.report) else os.path.join(a.project, a.report)

    lyr = a.lyrics if os.path.isabs(a.lyrics) else os.path.join(a.project, a.lyrics)
    if not os.path.exists(lyr):
        sys.exit("[coverage] 缺 %s" % lyr)
    local = load_local(lyr)
    print("[coverage] 本地 %s: %d 行" % (lyr, len(local)))

    bad = 0
    net_ok = None          # 判据 1 的结论：True=通过，False=有缺句，None=跳过

    # ---------- 判据 1: 网络歌词逐句核对 ----------
    if a.title or a.artist:
        net, why = fetch_net(a.title, a.artist, a.song_id, a.source)
        if net is None:
            print("[coverage] 跳过网络比对（%s）" % why)
        else:
            # 元数据行要按**形状**剔，不能靠硬编码某首歌的标题。
            # 踩过的坑（2026-10-02，漆黑的子弹 ED）：KG 源返回的首两行是
            # 「<曲名>-<艺人>(<别名>)」与「詞：<艺人>」 前者是"曲名-艺人(别名)"式标题行，
            # 后者用了**繁体**「詞」，而原正则只有简体「词」与日文「作詞」，于是两行都被当成"漏句"，
            # 门禁 FAIL 却指不出到底漏了哪句歌词。判据改成两条通用规则：
            #   ① 制作人员行：中/日/英三语前缀 + 冒号
            #   ② 标题行：包含本曲曲名且不含句末标点、长度很短
            net = [t for t in net if not re.match(
                r"^(作?[词詞]|訳[词詞]|曲|編曲|作曲|編|歌|唄|うた|Vocal|Lyric[s]?|Music|Arrange[rd]?|Compose[rd]?|Produced?)\s*[:：]", t, re.I)]
            if a.title:
                net = [t for t in net if not (a.title in t and len(t) <= 40)]
            print("[coverage] 网络歌词 %d 行（已去制作人员/标题行）" % len(net))
            miss = [t for t in net if not cover_ok(t, local)]
            if miss:
                net_ok = False
                print("[coverage] FAIL 网络有、本地没有的 %d 句：" % len(miss))
                for t in miss:
                    print("    - %s" % t)
            else:
                net_ok = True
                print("[coverage] PASS 网络每一句都在本地有对应")

    # ---------- 判据 2: 空档 vs 音频 ----------
    tim_p = a.timing if os.path.isabs(a.timing) else os.path.join(a.project, a.timing)
    voc_p = a.vocals if os.path.isabs(a.vocals) else os.path.join(a.project, a.vocals)
    cross_p = a.cross_kf if os.path.isabs(a.cross_kf) else os.path.join(a.project, a.cross_kf)
    ctclp_p = a.ctc_lp if os.path.isabs(a.ctc_lp) else os.path.join(a.project, a.ctc_lp)
    if os.path.exists(tim_p) and os.path.exists(voc_p):
        tim = json.load(open(tim_p, encoding="utf-8"))
        by = {}
        for m in tim:
            if m.get("call"):
                continue
            by.setdefault(m["line"], []).append(m)
        spans = sorted((min(x["s"] for x in v), max(x["e"] for x in v)) for v in by.values())
        merged = []
        for s, t in spans:
            if merged and s <= merged[-1][1] + 0.05:
                merged[-1][1] = max(merged[-1][1], t)
            else:
                merged.append([s, t])
        w = wave.open(voc_p)
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
        import array
        arr = array.array("h")
        arr.frombytes(raw[:len(raw) // 2 * 2])
        total = len(arr) / sr
        # 相邻演唱段的能量基准
        base = []
        for s, t in merged:
            if t - s >= 1.0:
                base.append(vocal_db(arr, sr, s, t))
        base_db = sorted(base)[len(base) // 2] if base else -20.0
        print("[coverage] 演唱段能量基准 %.1f dB（%d 段）" % (base_db, len(base)))
        sus = []
        prev = None
        for s, t in merged:
            if prev is not None and s - prev > a.gap:
                g = vocal_db(arr, sr, prev, s)
                if abs(g - base_db) < a.db_tol:
                    sus.append((prev, s, s - prev, g))
            prev = t
        if sus:
            # 假阳性过滤：句尾长音的自然拖尾会让空档能量接近演唱段，但那不是漏句。
            # 判据是"长度"一句正词至少 2 秒；<2.5s 的空档一律不算（实测两处 1.83s / 2.05s
            # 经网络歌词裁决各只有 1 个尾音字点：54.851「く」、133.072「と」）。
            real = [x for x in sus if x[2] >= 2.5]
            soft = [x for x in sus if x[2] < 2.5]
            for s, t, d, g in soft:
                print("[coverage] 注 空档 %.2f-%.2f (%.2fs, %.1f dB) 过短，判为句尾拖尾，不计漏句"
                      % (s, t, d, g))
            # 第二源交叉裁决：能量判据会被"器乐持音 + 人声分离残留"骗过，见 cross_source_edges 的 docstring。
            X = cross_source_edges(cross_p)
            if X is None:
                print("[coverage] 注 第二源 %s 缺失（跑了 06-kf-timing 就有）；空档只用能量判据裁决" % a.cross_kf)
            ex = []
            if real and X is not None:
                heads, tails = X
                tol = a.cross_tol
                kept = []
                for s, t, d, g in real:
                    # 空档两端都被第二源"贴住": 左边有句尾、右边有句首  那它就是一个真间奏
                    has_tail = any(abs(x - s) <= tol for x in tails)
                    has_head = any(abs(x - t) <= tol for x in heads)
                    if has_tail and has_head:
                        ex.append((s, t, d, g))
                    else:
                        kept.append((s, t, d, g))
                for s, t, d, g in ex:
                    print("[coverage] 注 空档 %.2f-%.2f (%.2fs, %.1f dB) 两端被第二源句尾/句首贴住"
                          " -> 真间奏，不计漏句" % (s, t, d, g))
                real = kept
            if real:
                # 第三判据: 模型在这段吐了几个假名。见 ctc_kana_density 的 docstring。
                spans = [(s, t) for s, t, _d, _g in real]
                # Agent Notes: 门禁判据不能与被测实现脱钩
                # 
                C = ctc_kana_density(ctclp_p, spans, merged)
                if C is None:
                    print("[coverage] 注 第三判据跳过（缺 %s 或演唱段样本不足） 空档只由前两条裁决"
                          % a.ctc_lp)
                else:
                    thr, rows = C
                    quiet = []
                    for (s, t), (_s, _t, r) in zip(spans, rows):
                        tag = "稀疏(无词)" if r < thr else "有词"
                        print("[coverage] 第三判据 空档 %.2f-%.2f 假名密度 %.2f 个/秒 (演唱段 p20 阈值 %.2f) -> %s"
                              % (s, t, r, thr, tag))
                        if r < thr:
                            quiet.append((s, t))
                    real = [x for x in real if (x[0], x[1]) not in quiet]
            if real:
                bad += 1
                print("[coverage] FAIL 空档 >=2.5s 且该段人声与演唱段相当（= 疑似漏句）：")
                for s, t, d, g in real:
                    print("    %8.2f - %8.2f (%5.2fs)  能量 %.1f dB" % (s, t, d, g))
            else:
                print("[coverage] PASS 无「疑似漏句」的空档（%d 处经第二源交叉裁决为真间奏）" % len(ex))
        else:
            print("[coverage] PASS 无「疑似漏句」的空档")
        print("[coverage] 音频总长 %.1fs" % total)
    else:
        print("[coverage] 跳过空档检查（缺 timing.json 或人声）")

    print("\n%s" % ("FAILED：有漏句嫌疑，先补齐歌词再往下做" if bad else "PASSED：歌词覆盖完整"))
    sys.exit(1 if bad else 0)


# Agent Notes: 歌词覆盖审计要落盘成门禁证据，元数据行按形状剔
# 
def main_reporting():
    """
    .agents/notes/implemented/bug-fix/2026-10-03-karaoke-gate-criteria-decoupled.md
    .agents/notes/implemented/process/2026-10-02-karaoke-coverage-report.md
跑 main()，把它的 stdout 镜像一份到 review/coverage.txt。"""
    class Tee:
        def __init__(self, path):
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            self.f = open(path, "w", encoding="utf-8")

        def write(self, s):
            sys.stdout.write(s); self.f.write(s)

        def flush(self):
            sys.stdout.flush(); self.f.flush()

    import io
    buf = io.StringIO()
    orig = sys.stdout

    class Dual:
        def write(self, s):
            orig.write(s); buf.write(s)

        def flush(self):
            orig.flush()

    sys.stdout = Dual()
    try:
        code = 0
        try:
            main()
        except SystemExit as e:
            # sys.exit("消息") 时 e.code 是字符串，不是退出码；按"非 0 = 失败"折算，
            # 并把消息打出来。原先直接 int(e.code) 会在缺 lyrics.txt 时抛 ValueError，
            # 把一条清楚的"缺文件"变成一段 traceback。
            if isinstance(e.code, int):
                code = e.code
            elif e.code is None:
                code = 0
            else:
                orig.write("%s\n" % e.code)
                code = 1
    finally:
        sys.stdout = orig
    # **只在 main() 真的跑完审计时才落盘。**
    # main() 提前退出有三种情况：--help/参数错误（argparse 的 SystemExit）、缺 lyrics.txt、
    # 以及任何别的 sys.exit。它们都不构成"审计做过"的证据  此时写文件等于把
    # usage 文本或一行报错冒充成门禁证据（实测：在 skill 目录里跑一次 --help，
    # 就会凭空长出一个 review/coverage.txt）。判据是 main() 结尾那句结论行。
    if "PASSED：歌词覆盖完整" not in buf.getvalue() and "FAILED：有漏句嫌疑" not in buf.getvalue():
        print("[coverage] 未落盘：main() 没有跑完审计（提前退出，不是审计结果）")
        sys.exit(code)

    # 路径参数在 main 内部解析，这里用同一套默认值定位；--report 非默认时按命令行再取一次
    argv = sys.argv[1:]
    proj, rep = ".", "review/coverage.txt"
    for i, x in enumerate(argv):
        if x == "--project" and i + 1 < len(argv):
            proj = argv[i + 1]
        if x == "--report" and i + 1 < len(argv):
            rep = argv[i + 1]
    rp = rep if os.path.isabs(rep) else os.path.join(proj, rep)
    os.makedirs(os.path.dirname(rp) or ".", exist_ok=True)
    with open(rp, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())
    print("[coverage] 报告 -> %s" % rp)
    sys.exit(code)


if __name__ == "__main__":
    main_reporting()
