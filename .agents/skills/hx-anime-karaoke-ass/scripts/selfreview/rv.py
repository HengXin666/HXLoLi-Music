# -*- coding: utf-8 -*-
"""自审的共用读取: 剧本, 高光, 每句时间, 每句事件指纹, 句 -> 单元.

产物在 proj/judge/review/: state.json (预算状态), rN/ (每轮一个目录).
"""
import hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from judge.common import Song, load_json, jpath      # noqa: E402
from assdoc.assdoc import AssDoc                      # noqa: E402

SUB = os.path.join("judge", "review")


class Ctx:
    def __init__(self, proj, ass="out.ass"):
        self.proj = os.path.abspath(proj)
        self.dir = os.path.join(self.proj, SUB)
        self.ass = os.path.join(self.proj, ass)
        if not os.path.exists(self.ass):
            raise SystemExit("没有 %s. 先跑生成器 (或 accept.py build)" % self.ass)
        self.song = Song(self.proj)
        arc, err = load_json(jpath(self.proj, "arc.json"))
        if err:
            raise SystemExit("自审要先有 judge/arc.json (%s). 先过 check_judge.py --stage arc" % err)
        self.arc = {r["line"]: r for r in arc.get("lines", []) if isinstance(r, dict) and "line" in r}
        bar, _ = load_json(jpath(self.proj, "bar.json"))
        self.bar = bar or {}
        self.hl = {i for h in self.bar.get("highlights", []) for i in h.get("lines", [])}

    def p(self, *a):
        return os.path.join(self.dir, *a)

    def rdir(self, n):
        return self.p("r%d" % n)

    # ---------------------------------------------------------------- 状态
    def load_state(self):
        d, _ = load_json(self.p("state.json"))
        return d

    def save_state(self, st):
        os.makedirs(self.dir, exist_ok=True)
        tmp = self.p("state.json.tmp")
        json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, self.p("state.json"))

    # ---------------------------------------------------------------- 每句
    def times(self, i):
        """抽帧时刻: 普通句 1 帧 (句中), 高光句 3 帧 (句首后 0.3s, 句中, 句尾前 0.3s)."""
        s, e = self.song.spans[i]
        mid = round((s + e) / 2, 2)
        if i not in self.hl:
            return [mid]
        return [round(min(s + 0.3, mid), 2), mid, round(max(e - 0.3, mid), 2)]

    def line_hash(self, doc=None):
        """每句时间内的事件指纹. 指纹变了的句子才要重抽帧 (增量渲染)."""
        doc = doc or AssDoc.load(self.ass)
        out = {}
        for i, (s, e) in self.song.spans.items():
            rows = sorted("%s|%s|%s|%s|%s" % (ev["layer"], ev["S"], ev["E"], ev["style"], ev["text"])
                          for ev in doc.events if ev["kind"] == "Dialogue" and ev["s"] < e and ev["e"] > s)
            out[i] = hashlib.sha1("\n".join(rows).encode("utf-8")).hexdigest()[:12]
        return out

    def units_of(self, i, man):
        """句 -> 句单元 key. 先看单元的 lines, 再按时间重叠."""
        s, e = self.song.spans[i]
        us = [u for u in man.get("units", []) if u.get("kind") == "phrase"]
        hit = [u["key"] for u in us if i in (u.get("lines") or [])]
        return hit or [u["key"] for u in us if u.get("t") and u["t"][0] < e and u["t"][1] > s]

    def anchor_words(self, i):
        """这一句剧本锚点能被说出来的词: motif 名, image 词, 镜头的主体与符号, 构想里的高光 unique."""
        a = self.arc.get(i) or {}
        words = []
        shots = {s.get("id"): s for s in (load_json(jpath(self.proj, "shots.json"))[0] or {}).get("shots", [])}
        for x in a.get("anchors") or []:
            ref = x.get("ref")
            if x.get("kind") in ("motif", "image") and isinstance(ref, str):
                words.append(ref)
            elif x.get("kind") == "shot" and ref in shots:
                words.append(shots[ref].get("subject", ""))
                words += shots[ref].get("symbols") or []
        for h in self.bar.get("highlights", []):
            if i in h.get("lines", []) and isinstance(h.get("anchor"), dict):
                words += [v for v in h["anchor"].values() if isinstance(v, str)]
        return [w.strip() for w in words if isinstance(w, str) and w.strip()]
