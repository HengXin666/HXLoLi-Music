# -*- coding: utf-8 -*-
"""选区 -> 事件. 验收台的选区是 "单元 + 句内字偏移 + 可选时间框", 不是 Name 正则.

选区 (issues.json 与 goods.json 同一格式):
  {"unit": "<清单单元 key>", "chars": [i0, i1] 或 null, "t": [a, b] 或 null, "layer": "ly|fx|card" 或 null}
  chars 是半开区间, 按清单 chars 的下标 (句内第几个字). 只有 phrase 单元有 chars.
  layer 是事件 Name 的前缀 (ly 字层, fx 特效层, card 卡片), 与时间线的泳道一致. null = 全部层.
  一条问题可以有多段选区 (issues 的 sels), 每段各是上面的格式.

事件与字相交: 事件的 \\pos 或 \\move 起点 x 落在某个字的框 (x ± w/2) 里, 就属于这个字.
没有位置的事件覆盖整句. 冻结时一个事件覆盖整句, 就冻结整个事件 (报告里的 "实际范围" 会说出来).
"""
import re

from assdoc import spec as SP
from assdoc.assdoc import event_line

POS = re.compile(r"\\(?:pos|move)\(\s*([-\d.]+)\s*,\s*([-\d.]+)")


def units(man):
    return {u["key"]: u for u in (man or {}).get("units", [])}


def unit_events(doc, man, key):
    cl = SP.claims(man)
    return [e for e in doc.events if SP.owner_of(cl, e) == key]


def ev_chars(ev, chars):
    """事件覆盖的字下标集合; 没有位置或不在任何字框里的返回 None (= 整句)."""
    m = POS.search(ev["text"])
    if not m or not chars:
        return None
    x = float(m.group(1))
    hit = {j for j, c in enumerate(chars) if abs(x - c[3]) <= c[4] / 2 + 0.5}
    return hit or None


def norm(sel):
    s = dict(unit=sel["unit"], chars=sel.get("chars"), t=sel.get("t"), layer=sel.get("layer"))
    if s["chars"] is not None:
        s["chars"] = [int(s["chars"][0]), int(s["chars"][1])]
    if s["t"] is not None:
        s["t"] = [float(s["t"][0]), float(s["t"][1])]
    return s


def pick(doc, man, sel):
    """返回 (事件列表, 实际覆盖的字下标排好序的列表 或 "all")."""
    sel = norm(sel)
    u = units(man).get(sel["unit"])
    if u is None:
        raise SystemExit("清单里没有单元 %s (看 accept.py units)" % sel["unit"])
    chars = u.get("chars") or []
    want = set(range(*sel["chars"])) if sel["chars"] and chars else None
    evs, cover = [], set()
    for e in unit_events(doc, man, sel["unit"]):
        if sel["t"] and not (e["s"] < sel["t"][1] and e["e"] > sel["t"][0]):
            continue
        if sel["layer"] and e["name"].split(":", 1)[0] != sel["layer"]:
            continue
        cs = ev_chars(e, chars)
        if want is not None and cs is not None and not (cs & want):
            continue
        evs.append(e)
        cover |= cs if cs is not None else set(range(len(chars)))
    whole = want is None or not chars or cover >= set(range(len(chars)))
    return evs, ("all" if whole else sorted(cover))


def lines(evs):
    return sorted(event_line(e) for e in evs)


def label(sel, man=None):
    sel = norm(sel)
    u = units(man).get(sel["unit"]) if man else None
    s = sel["unit"]
    if u and u.get("label"):
        s += " (%s)" % u["label"][:24]
    if sel["chars"] and u and u.get("chars"):
        s += " 字 %d-%d \"%s\"" % (sel["chars"][0], sel["chars"][1] - 1,
                                  "".join(c[0] for c in u["chars"][sel["chars"][0]:sel["chars"][1]]))
    if sel["t"]:
        s += " %.2f-%.2fs" % tuple(sel["t"])
    if sel["layer"]:
        s += " 层 %s" % sel["layer"]
    return s
