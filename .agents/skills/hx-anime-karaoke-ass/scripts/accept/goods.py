# -*- coding: utf-8 -*-
""""好" 的冻结: 快照是保证, 指纹是报警 (plan 2.4).

  review/accept/goods.json       每条 "好": 选区, 快照文件, 指纹, 实际冻结范围
  review/accept/goods/<id>.ass   快照: 标 "好" 时选区内事件的原文 (整单元时连 band)

构建: out.ass = 冻结快照(生成器输出). 先删掉生成器输出里同选区的事件, 再放回快照.
状态 (每次构建与 G2 核对时算):
  ok       生成器新输出的同选区事件与快照逐行相同
  touched  不同, 并且输入指纹没变: 代码改动碰到了 "好" -> G2 判越权
  stale    输入指纹变了 (时间/歌词/校准): 快照不对应新输入. 照旧用快照, 台子请用户重看, 不自动替换
指纹: 单元 fp (清单) + 清单 inputs 的哈希 + deps.code 各函数哈希 + deps.data.
"""
import json
import os
import time

from accept import sel as S
from assdoc.assdoc import AssDoc


class Goods:
    def __init__(self, d):
        self.dir = d
        self.path = os.path.join(d, "goods.json")
        self.data = json.load(open(self.path, encoding="utf-8")) if os.path.exists(self.path) else \
            dict(format="accept-goods", version=1, items=[], seq=0)

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        tmp = self.path + ".tmp"
        json.dump(self.data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    @property
    def items(self):
        return self.data["items"]

    # ------------------------------------------------------------ 标记
    def mark(self, gen_doc, man, sel, issue=None, note=""):
        """把选区当前的生成器输出存为快照. 返回这条 "好" (含实际冻结范围)."""
        sel = S.norm(sel)
        evs, cover = S.pick(gen_doc, man, sel)
        if not evs:
            raise SystemExit("选区 %s 里没有事件, 没东西可冻结" % S.label(sel, man))
        clash = [g["id"] for g in self.items if g["sel"]["unit"] == sel["unit"]]
        self.data["seq"] += 1
        gid = "G%d" % self.data["seq"]
        u = S.units(man)[sel["unit"]]
        snap = AssDoc(["[Script Info]"], "Format: " + ", ".join(
            ("Layer", "Start", "End", "Style", "Name", "MarginL", "MarginR", "MarginV", "Effect", "Text")),
            [dict(e) for e in evs], {u["name"]: gen_doc.bands[u["name"]]} if cover == "all" and u["name"] in gen_doc.bands else {})
        os.makedirs(os.path.join(self.dir, "goods"), exist_ok=True)
        rel = os.path.join("goods", gid + ".ass")
        snap.write(os.path.join(self.dir, rel))
        g = dict(id=gid, sel=sel, file=rel, n=len(evs), cover=cover, fp=fingerprint(man, sel["unit"]),
                 issue=issue, note=note, at=time.strftime("%Y-%m-%d %H:%M:%S"))
        self.items.append(g)
        self.save()
        return g, clash

    def remove(self, gid):
        g = self.get(gid)
        self.items.remove(g)
        self.save()
        return g

    def get(self, gid):
        g = next((x for x in self.items if x["id"] == gid), None)
        if g is None:
            raise SystemExit("没有这条 \"好\": %s" % gid)
        return g

    def snap(self, g):
        return AssDoc.load(os.path.join(self.dir, g["file"]))

    # ------------------------------------------------------------ 状态与构建
    def status(self, gen_doc, man):
        """{id: (状态, 说明)}. 见模块头."""
        out = {}
        us = S.units(man)
        for g in self.items:
            if g["sel"]["unit"] not in us:
                out[g["id"]] = ("stale", "单元 %s 不在新清单里 (歌词或分句变了)" % g["sel"]["unit"])
                continue
            new = fingerprint(man, g["sel"]["unit"])
            # 句单元的 fp 已含本句音拍时间/位置/band, 只看它; 没有 fp 的单元 (卡片/段) 退回看上游文件哈希
            keys = ("fp",) if g["fp"].get("fp") else ("inputs",)
            inp = [k for k in keys if new.get(k) != g["fp"].get(k)]
            cur, _ = S.pick(gen_doc, man, g["sel"])
            same = S.lines(cur) == S.lines(self.snap(g).events)
            if inp:
                out[g["id"]] = ("stale", "输入变了 (%s), 快照照旧, 请用户重看" % ",".join(inp))
            elif same:
                out[g["id"]] = ("ok", "")
            else:
                fns = sorted(k for k, h in new["code"].items() if g["fp"]["code"].get(k) != h)
                out[g["id"]] = ("touched", "生成器新输出与快照不同. 变了的函数: %s" % (fns or "无 (看 deps.data)"))
        return out

    def apply(self, gen_doc, man):
        """out = 冻结快照(生成器输出). 返回新 AssDoc; gen_doc 不改."""
        doc = AssDoc(list(gen_doc.head), gen_doc.fmt, [dict(e) for e in gen_doc.events], dict(gen_doc.bands))
        us = S.units(man)
        for g in self.items:
            if g["sel"]["unit"] in us:
                cur, _ = S.pick(doc, man, g["sel"])
                drop = {id(e) for e in cur}
                doc.events = [e for e in doc.events if id(e) not in drop]
            sn = self.snap(g)
            doc.events += [dict(e) for e in sn.events]
            doc.bands.update(sn.bands)
        return doc

    def units_hit(self, units):
        """会被这组单元的改动波及的 "好"."""
        return [g for g in self.items if g["sel"]["unit"] in set(units)]


def fingerprint(man, key):
    u = S.units(man).get(key) or {}
    fns = (man.get("code") or {}).get("fns", {})
    deps = u.get("deps") or {}
    return dict(fp=u.get("fp"), inputs=man.get("inputs"), data=deps.get("data"),
                code={k: (fns.get(k) or {}).get("h") for k in deps.get("code", [])})
