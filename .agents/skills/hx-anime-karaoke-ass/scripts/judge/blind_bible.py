#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专属性盲审: 只给设计, 不给番名, 看审稿人能不能认出作品.

  hx-karaoke judge/blind_bible.py --project proj --packet          # 出两份去名盲审包 (real 与 decoy)
  hx-karaoke judge/blind_bible.py --project proj                   # 按 bible/blind/answers.json 计分
  hx-karaoke judge/blind_bible.py --calibrate projA projB ...      # 用成品的正反例算阈值建议

real 包 = 选定方向 + 落地符号的形态描述; decoy 包 = 同一方向把专属母题换成本作的通用母题.
decoy 是反例: 它认出率高说明审稿人靠的不是专属元素, 阈值就没有区分能力 (硬规则 10b).
每个包至少盲审 MIN_ROUNDS 轮 (互相独立的审稿人), 取一致, 降低单次主观判断的波动.
"""
import argparse, json, os, re, sys, unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from judge.bible_io import Bible, background_names, nonempty   # noqa: E402

MIN_ROUNDS = 3
# 认出率阈值. None = 未标定, 只报 WARN. 标定记录写在设计圣经那篇 agent note 的 Consequences.
THRESHOLD = None
MASK = "■"
# decoy 补位用的通用形态 (任何奇幻或战斗番都成立). 只在本作 unique=0 的符号不够 3 个时补.
GENERIC_FORMS = ["飘落的花瓣", "掌心一团柔光", "地面旋转的魔法阵", "泪滴落下", "星光闪烁", "裂开的心形"]


def redactor(bible, proj):
    extra = list((bible.work or {}).get("redact") or []) + background_names(proj)
    words = sorted({w for w in bible.proper_nouns() + extra if nonempty(w) and len(w.strip()) >= 2},
                   key=len, reverse=True)

    def red(s):
        s = re.sub(r"「[^」]*」", "「%s」" % MASK, str(s or ""))     # 歌词原文也会泄露曲名
        for w in words:
            s = s.replace(w, MASK)
        return s
    return red, words


def build(bible, proj, decoy=False):
    """返回盲审包正文. decoy=True 时把专属母题换成通用母题 (unique<=1)."""
    red, _ = redactor(bible, proj)
    ds = (bible.data.get("directions.json") or {}).get("directions") or []
    d = next((x for x in ds if x.get("chosen")), None)
    if not d:
        raise SystemExit("directions.json 没有选定方向, 出不了盲审包")
    motifs = [m for m in d.get("motifs") or [] if m in bible.symbols]
    if decoy:
        # 反例: 同一首歌的通用化版本. 只留标注 unique=0 的符号 (因来源不足降级的符号仍带作品信息, 不算通用),
        # 运动语言, 色彩, 高潮描述里含专属内容, 一并不给; 不够 3 个用通用形态补.
        motifs = [k for k, v in bible.symbols.items() if v.get("unique") == 0]
    out = ["# 盲审包", "", "下面是一首动画歌曲卡拉OK字幕的特效设计. 作品名, 人名与歌词原文已涂成 %s." % MASK,
           "请只凭设计内容回答: 这是哪部动画? 给出最可能的作品名 (guess), 另给两个备选, 再给 0-1 的把握 (conf).", ""]
    out += ["## 整体"]
    if not decoy:
        out += ["- 运动语言: " + red(d.get("motion"))]
    out += ["- 字体气质: " + red(d.get("type_mood"))]
    if not decoy:
        out += ["- 色彩: " + ", ".join(p.get("hex", "") for p in d.get("palette") or [])]
    out += ["", "## 母题 (可画的形态)"]
    forms = [red(bible.symbols[m].get("form")) for m in motifs]
    if decoy:
        forms += GENERIC_FORMS[:max(0, 5 - len(forms))]
    for x in forms:
        out.append("- " + x)
    if not decoy:
        out += ["", "## 高潮段处理", "- " + red((d.get("climax") or {}).get("treatment"))]
        out += ["", "## 逐句落地"]
        for it in (bible.data.get("landing.json") or {}).get("items") or []:
            if nonempty(it.get("what")):
                out.append("- " + red(it["what"]))
    return "\n".join(out) + "\n"


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    return re.sub(r"[\s・·\-_:：「」『』()（）〜~!！?？]", "", s)


def is_hit(guess, names):
    g = norm(guess)
    return bool(g) and any(n and (n in g or (len(g) >= 2 and g in n)) for n in map(norm, names))


def score(proj):
    """返回 {packet: (命中, 轮数)}."""
    bible = Bible(proj)
    names = [bible.work.get("title")] + list(bible.work.get("aliases") or [])
    p = os.path.join(proj, "bible", "blind", "answers.json")
    if not os.path.isfile(p):
        return None
    out = {}
    for r in json.load(open(p, encoding="utf-8")).get("rounds") or []:
        h, n = out.get(r.get("packet"), (0, 0))
        out[r.get("packet")] = (h + is_hit(r.get("guess"), names), n + 1)
    return out


def gate(proj, res):
    """给 check_bible 用. 未标定只报 WARN."""
    sc = score(proj)
    if sc is None:
        res.warn("盲审", "没有 bible/blind/answers.json. 先跑 --packet, 让 >=%d 个独立审稿人只看包答题" % MIN_ROUNDS)
        return None
    h, n = sc.get("real", (0, 0))
    if n < MIN_ROUNDS:
        res.warn("盲审轮数", "real 包只审了 %d 轮, 要 >=%d 轮取一致" % (n, MIN_ROUNDS))
    rate = h / n if n else 0.0
    dh, dn = sc.get("decoy", (0, 0))
    msg = "认出率 real %d/%d" % (h, n) + (", decoy %d/%d" % (dh, dn) if dn else ", 没有 decoy 对照")
    if THRESHOLD is None:
        res.warn("盲审认出率", msg + ". 阈值未标定, 只报 WARN (硬规则 10b)")
    else:
        res.check(n >= MIN_ROUNDS and rate >= THRESHOLD, "盲审认出率", msg + ", 阈值 %.2f" % THRESHOLD)
    return rate


def calibrate(projs):
    real, dec = [], []
    for p in projs:
        sc = score(p) or {}
        for k, lst in (("real", real), ("decoy", dec)):
            h, n = sc.get(k, (0, 0))
            if n:
                lst.append(h / n)
                print("%-6s %d/%d  %s" % (k, h, n, p))
    if not real or not dec:
        print("正例或反例为空, 不能标定")
        return 1
    lo, hi = min(real), max(dec)
    if lo <= hi:
        print("正例最低 %.2f <= 反例最高 %.2f: 没有区分能力, 不许定阈值" % (lo, hi))
        return 1
    th = int(((lo + hi) / 2) * 20) / 20
    print("正例最低 %.2f, 反例最高 %.2f, 建议 THRESHOLD = %.2f (取中点, 向下取到 0.05)" % (lo, hi, th))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project")
    ap.add_argument("--packet", action="store_true")
    ap.add_argument("--calibrate", nargs="+")
    a = ap.parse_args()
    if a.calibrate:
        return calibrate(a.calibrate)
    if not a.project:
        ap.error("要 --project 或 --calibrate")
    if a.packet:
        bible, d = Bible(a.project), os.path.join(a.project, "bible", "blind")
        os.makedirs(d, exist_ok=True)
        for kind in ("real", "decoy"):
            txt = build(bible, a.project, decoy=(kind == "decoy"))
            open(os.path.join(d, "packet-%s.md" % kind), "w", encoding="utf-8").write(txt)
            print("写出 %s" % os.path.join(d, "packet-%s.md" % kind))
        return 0
    from judge.common import Res
    res = Res()
    gate(a.project, res)
    res.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
