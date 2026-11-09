# -*- coding: utf-8 -*-
"""参数层 (预览台 v2): 改的是生成器的输入, 不是 ASS 文本.

三份东西:
  out.raw.manifest.json        生成器写的单元清单 (assfx/layer/manifest.py), 预览台只读
  review/station/overrides.json  单元参数的覆盖值 + 备注 + 参数锁, 经 ASSFX_OVERRIDES 喂回生成器
  review/station/manifest.last.json  上一次构建的清单, 用来报"单元变化表"

为什么不用输出层补丁改设计: 补丁按 Name/正则改文本, 重跑后最脆, 也绕开了色彩系统.
参数层的改动重跑后仍成立, 词汇与 PHRASES / 设计表一致, 交付说明能写出"由 A 改为 B".

隔离 (判据 G2): 每次改参数都重跑生成器, 再按单元比对新旧 raw. 本单元之外有事件变了就回滚并报错.
window 组参数 (din/dout/lead/hold) 允许牵动清单 deps 里列的下一句, 这是出入场规划的真实依赖.
"""
import copy
import json
import os
import shutil
import time

from assdoc.assdoc import AssDoc, event_line

FILE = "overrides.json"
LAST = "manifest.last.json"
FORMAT = "assfx-overrides"


def dead_knobs(u, man):
    """单元没用到的统一旋钮. 统一旋钮 = 卡片 schema 里的 knob 组 (density/size/alpha), 不写死名字.
    清单没有 knobs_used (老版 assfx) 时不判, 全部当有效."""
    used = u.get("knobs_used")
    if used is None:
        return set()
    gen = {f["key"] for f in (man.get("schema") or {}).get("card", []) if f.get("group") == "knob"}
    return gen - set(used)


def manifest_path(ass_path):
    return (ass_path[:-4] if ass_path.endswith(".ass") else ass_path) + ".manifest.json"


def load_manifest(ass_path):
    p = manifest_path(ass_path)
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def _check():
    from assfx.layer import overrides as OV
    return OV.check


class Spec:
    def __init__(self, st):
        self.st = st
        self.path = os.path.join(st.dir, FILE)
        self.data = json.load(open(self.path, encoding="utf-8")) if os.path.exists(self.path) else \
            dict(format=FORMAT, version=1, units={})

    # ---------------------------------------------------------------- 读
    @property
    def man(self):
        return load_manifest(self.st.p(self.st.cfg["raw"]))

    def on(self):
        return self.man is not None

    def units(self, man=None):
        man = man or self.man
        return {u["key"]: u for u in (man or {}).get("units", [])}

    def entry(self, key):
        return self.data["units"].get(key) or {}

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        json.dump(self.data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def env_path(self):
        """给生成器的覆盖文件路径; 没有任何覆盖时返回 None (生成器原样输出)."""
        return self.path if any(v.get("params") for v in self.data["units"].values()) else None

    # ---------------------------------------------------------------- 校验
    def schema_of(self, u, man):
        kind = "phrase" if u["kind"] == "phrase" else ("card" if u["kind"] == "card" else "segment")
        return man["schema"][kind]

    def validate(self, key, params, man=None):
        man = man or self.man
        u = self.units(man).get(key)
        if not u:
            raise SystemExit("清单里没有单元 %s (可能句子改了或被删了)" % key)
        err = _check()(key, params, self.schema_of(u, man), u["params"].get("fx"), man.get("presets") or {})
        if err:
            raise SystemExit("参数不对: " + err)
        return u

    # ---------------------------------------------------------------- 写
    def set(self, key, param, value, note):
        """改一个参数. 等于生成器默认值时删掉这条覆盖 (文件里只留真正的改动)."""
        if not str(note or "").strip():
            raise SystemExit("参数改动必须写备注: 为什么改 (铁律: 每个特效都能说出意义)")
        e = self.data["units"].setdefault(key, {})
        if e.get("pin"):
            raise SystemExit("%s 已锁定, 先解锁再改" % key)
        params = dict(e.get("params") or {})
        params[param] = value
        u = self.validate(key, params)
        dead = dead_knobs(u, self.man)
        if param in dead and u["defaults"].get(param) != value:
            raise SystemExit("%s 的配方没用到旋钮 %s (%s), 改了不会有任何效果, 拒收" % (
                key, param, "不发射粒子" if param == "density" else "不画图形"))
        if u["defaults"].get(param) == value:
            params.pop(param)
            e.setdefault("notes", {}).pop(param, None)
        else:
            e.setdefault("notes", {})[param] = str(note)[:300]
        e["params"] = params
        self._tidy(key)
        return u

    def reset(self, key, param=None):
        e = self.data["units"].get(key)
        if not e or e.get("pin"):
            return False
        if param is None:
            e["params"], e["notes"] = {}, {}
        else:
            (e.get("params") or {}).pop(param, None)
            (e.get("notes") or {}).pop(param, None)
        self._tidy(key)
        return True

    def pin(self, key, note):
        """参数锁: 冻结本单元的全部有效参数 + 输入指纹. 生成器默认值以后再变, 本单元也不跟着变;
        上游 timing 改了, 本单元按同一设计重渲, 并标"输入变了"让人看一眼."""
        man = self.man
        u = self.units(man).get(key)
        if not u:
            raise SystemExit("清单里没有单元 %s" % key)
        e = self.data["units"].setdefault(key, {})
        if e.get("pin"):
            return False
        e["pin"] = dict(fp=u.get("fp"), inputs=man.get("inputs"), note=str(note or ""),
                        at=time.strftime("%Y-%m-%d %H:%M:%S"), before=copy.deepcopy(e.get("params") or {}))
        e["params"] = {k: v for k, v in u["params"].items() if v not in ("", None)}
        return True

    def unpin(self, key):
        e = self.data["units"].get(key)
        if not e or not e.get("pin"):
            return False
        e["params"] = e["pin"].get("before") or {}
        e.pop("pin")
        self._tidy(key)
        return True

    def _tidy(self, key):
        e = self.data["units"].get(key)
        if e is not None and not e.get("params") and not e.get("pin"):
            self.data["units"].pop(key)

    # ---------------------------------------------------------------- 状态
    def status(self, man=None):
        """每个单元: default / edited / pinned / stale (锁住后输入变了) / orphan (覆盖指向的 key 已不存在)."""
        man = man or self.man
        us = self.units(man)
        out = {}
        for k, u in us.items():
            e = self.entry(k)
            pin = e.get("pin")
            st = "pinned" if pin else ("edited" if e.get("params") else "default")
            why = []
            if pin and pin.get("fp") and u.get("fp") and pin["fp"] != u["fp"]:
                st = "stale"
                why = [n for n, h in (man.get("inputs") or {}).items() if (pin.get("inputs") or {}).get(n) != h] \
                    or ["本句音拍/布局指纹"]
            out[k] = dict(state=st, why=why, params=e.get("params") or {}, notes=e.get("notes") or {}, pin=pin)
        for k in self.data["units"]:
            if k not in us:
                out[k] = dict(state="orphan", why=["清单里已没有这个单元"], params=self.entry(k).get("params"),
                              notes=self.entry(k).get("notes") or {}, pin=self.entry(k).get("pin"))
        return out

    def diff_last(self, man):
        """与上次构建的清单比: 新增 / 删除 / 指纹变化的单元 key. 比完把本次存成 last."""
        lp = os.path.join(self.st.dir, LAST)
        old = json.load(open(lp, encoding="utf-8")) if os.path.exists(lp) else None
        d = dict(added=[], removed=[], changed=[], revision=man.get("revision"))
        if old:
            a, b = self.units(old), self.units(man)
            d["added"] = [k for k in b if k not in a]
            d["removed"] = [k for k in a if k not in b]
            d["changed"] = [k for k in b if k in a and a[k].get("fp") != b[k].get("fp")]
        shutil.copy(manifest_path(self.st.p(self.st.cfg["raw"])), lp)
        return d


# -------------------------------------------------------------------- 单元归属与隔离
def claims(man):
    """每个单元认领哪些事件: (Name 集合, 起点区间或 None). 段单元共用 Name, 靠起点区间区分."""
    out = {}
    for u in man.get("units", []):
        n = u["name"]
        if u["kind"] == "phrase":
            out[u["key"]] = ({"ly:" + n, "fx:" + n}, None)
        elif u["kind"] == "card":
            out[u["key"]] = ({"card:" + n, "fx:" + n}, None)
        else:
            out[u["key"]] = ({"fx:" + n}, tuple(u["t"]))
    return out


def owner_of(cl, ev):
    for k, (names, rng) in cl.items():
        if ev["name"] in names and (rng is None or rng[0] - 1e-6 <= ev["s"] < rng[1] - 1e-6):
            return k
    return None


def by_owner(doc, cl):
    out = {}
    for e in doc.events:
        out.setdefault(owner_of(cl, e), []).append(event_line(e))
    for k in out:
        out[k].sort()
    return out


def changed_units(old_doc, new_doc, man):
    """新旧两份 raw 里, 哪些单元的事件变了 (None = 不属于任何单元的事件)."""
    cl = claims(man)
    a, b = by_owner(old_doc, cl), by_owner(new_doc, cl)
    ch = [k for k in set(a) | set(b) if a.get(k) != b.get(k)]
    for name, band in old_doc.bands.items():         # band 也算: 别句的 band 变了一样是越权
        if new_doc.bands.get(name) != band:
            ch += [k for k, u in ((u["key"], u) for u in man["units"]) if u["name"] == name]
    return sorted(set(ch), key=str)


def label(k):
    """报错与列表里的单元名. None 桶不打 None, 说清楚是什么."""
    return "单元之外的事件 (生成器输出里不归任何单元的行)" if k is None else str(k)


def adopt_loss(raw_doc, gen_doc, man):
    """adopt 过的 raw 与生成器输出 (同一份覆盖) 的差: 下次重跑会丢掉的内容. 返回提示文字, 没有差返回 None.
    adopt 把磁盘上的 out.ass 整份当 raw, 手写行与手改不在生成器的输入里, 重跑必然消失.
    这不是改参数造成的越权, 所以隔离校验的基准用生成器输出, 不用 raw; 丢掉的内容单独报出来."""
    cl = claims(man)
    units = [k for k in changed_units(gen_doc, raw_doc, man) if k is not None]
    a, b = by_owner(raw_doc, cl).get(None, []), list(by_owner(gen_doc, cl).get(None, []))
    extra = 0
    for x in a:
        if x in b:
            b.remove(x)
        else:
            extra += 1
    if not units and not extra:
        return None
    what = (["单元 %s 的手改" % ", ".join(units)] if units else []) + \
        (["%d 条不属于任何单元的事件 (多半是 adopt 带进来的手写行)" % extra] if extra else [])
    return ("adopt 进来的 out.ass 与生成器输出不同, 这次重跑已丢弃: %s. "
            "参数层只认生成器输出; 要留住手写内容请用快照锁, 不要靠 adopt" % ", 以及 ".join(what))


def allowed(man, key, params):
    """改 key 的这些参数时允许变的单元: 本单元 + window 组参数牵动的 deps."""
    us = {u["key"]: u for u in man["units"]}
    ok = {key}
    win = {"din", "dout", "lead", "hold", "motion"}
    if us.get(key) and win & set(params):
        ok |= set((us[key].get("deps") or {}).get("window") or [])
    return ok


def load_doc(path):
    return AssDoc.load(path)
