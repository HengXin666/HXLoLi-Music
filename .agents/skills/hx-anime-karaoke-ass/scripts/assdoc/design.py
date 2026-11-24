# -*- coding: utf-8 -*-
"""设计稿 (design.md) 给验收台用的视图. 格式与校验只有一份: scripts/kfx/kfx_design.py (说明见 kfx/kfx_README.md).

本模块不再自己解析: 它把 kfx 的解析结果和校验错误整理成验收台设计稿面板要的形状, 并负责整节替换与保存后重建.
  python3 design.py <工程目录>            打印每行校验结果 (退出码 1 = 有问题)
  python3 design.py <工程目录> --json     输出面板用的 JSON
"""
import json
import os
import re
import sys

KFX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kfx")
if KFX not in sys.path:
    sys.path.insert(0, KFX)
import kfx_build as B  # noqa: E402
import kfx_design as KD  # noqa: E402

HEAD = re.compile(r"^##\s+L(\d+)\s*·\s*(.+)$")
FILE = "design.md"
OUT = "out.kfx.ass"


def _sections(text):
    """[(标题行, 正文)], 正文原样保留, 回写时整节替换."""
    secs, cur, buf = [], None, []
    for l in text.split("\n"):
        if l.startswith("## "):
            if cur is not None:
                secs.append((cur, "\n".join(buf).strip("\n")))
            cur, buf = l, []
        elif cur is not None:
            buf.append(l)
    if cur is not None:
        secs.append((cur, "\n".join(buf).strip("\n")))
    return secs


def _motifs(table):
    out = []
    for l in table.split("\n"):
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        if l.strip().startswith("|") and len(c) >= 4 and c[0] != "意象" and not set(c[0]) <= set("-: "):
            out.append(dict(name=c[0], src=c[1], who=c[2], means=c[3], whole="", each=""))
    return out


# Agent Notes: 设计稿面板只是 kfx 设计稿的视图, 解析与校验唯一实现在 kfx_design.py
# .agents/notes/implemented/architecture/2026-11-22-karaoke-kfx-single-generator.md
def parse(text, proj=None, fonts=None):
    """返回面板要的 {title, global, motifs, lines, errors}. 有 proj 时按工程歌词校验并给出每行时间."""
    d = KD.parse(text)
    song, errs = {}, []
    if proj:
        try:
            d, lines, _, errs = B.check_design(proj, text, fonts or B.default_fonts(proj))
            song = {L.idx: L for L in lines}
        except Exception as e:  # 歌词 / 字体读不了: 面板照样显示文本, 顶上报错
            errs = ["读不了工程歌词或字体, 没法校验: %s" % e]
    title = next((l[2:].strip() for l in text.split("\n") if l.startswith("# ")), "")
    heads = {int(m.group(1)): (h, body) for h, body in _sections(text) for m in [HEAD.match(h.strip())] if m}
    per = {}
    top = []
    for e in errs:
        m = re.match(r"^L(\d+): (.*)$", e)
        (per.setdefault(int(m.group(1)), []).append(m.group(2)) if m else top.append(e))
    out = []
    for no in sorted(d["lines"]):
        D = d["lines"][no]
        f = D["fields"]
        S = song.get(no)
        jp = S.text if S else D["text"]
        want = jp.replace(" ", "")
        kmap = [i for i, ch in enumerate(want) if not re.match(r"\s|\u3000", ch)]
        pats = []
        for p in D["patches"]:
            if "at" in p:
                a = kmap.index(p["at"]) if p["at"] in kmap else 0
                pats.append(dict(text=p["text"], start=a, end=a + len(re.sub(r"\s|\u3000", "", p["text"])),
                                 fx=["·".join([v] + args) for v, args in p["fx"]]))
        c = re.match(r"#([0-9A-Fa-f]{6})", f.get("色", ""))
        h, body = heads.get(no, ("## L%02d · %s" % (no, D["text"]), ""))
        out.append(dict(
            key="L%02d" % no, no=no, t0=(S.t_in if S else 0.0), t1=(S.t_end if S else 0.0), role="", head=h.strip(),
            jp=jp, cn=(S.cn if S else ""), patch=f.get("补丁", ""), patches=pats,
            color=("#" + c.group(1).upper()) if c else None, color_note=f.get("色", "")[c.end():].strip() if c else f.get("色", ""),
            entry="默认", hit="默认", exit=f.get("出场", ""), why=f.get("为什么", ""),
            phrases=[dict(on=p["text"], fx=p["fx"], desc="") for p in pats],
            yijing=f.get("意境", ""), whole=f.get("整行", ""), each=f.get("每字", ""),
            errors=per.get(no, []), raw=body))
    return dict(title=title, motifs=_motifs(d.get("motifs", "")), lines=out, errors=top,
                **{"global": ["%s: %s" % kv for kv in d.get("globals", {}).items()]})


def replace_section(text, key, new_body):
    """把 key (L05) 那一节的正文换成 new_body; new_body 以 '## ' 开头时标题行一起换."""
    lines = text.split("\n")
    st = en = None
    for i, l in enumerate(lines):
        m = HEAD.match(l.strip()) if l.startswith("## ") else None
        if st is None and m and "L%02d" % int(m.group(1)) == key:
            st = i
            continue
        if st is not None and l.startswith("## "):
            en = i
            break
    if st is None:
        raise KeyError("设计稿里没有 " + key)
    en = len(lines) if en is None else en
    nb = new_body.strip("\n").split("\n")
    if nb and nb[0].startswith("## "):
        head, nb = nb[0], nb[1:]
        if not HEAD.match(head.strip()) or "L%02d" % int(HEAD.match(head.strip()).group(1)) != key:
            raise ValueError("标题行格式不对或改了行号: " + head)
    else:
        head = lines[st]
    return "\n".join(lines[:st] + [head, ""] + nb + [""] + lines[en:])


def rebuild(proj, fonts=None):
    """照设计稿重建 out.kfx.ass: 先写临时文件, 成功才原子替换; 设计稿不过校验时旧成品一个字节都不动.
    返回 {ok, events, ms, errors}."""
    import time
    t = time.time()
    out = os.path.join(proj, OUT)
    tmp = out + ".building"
    try:
        n, _ = B.build(proj, os.path.join(proj, FILE), tmp, fonts or B.default_fonts(proj))
    except B.DesignError as e:
        return dict(ok=False, events=0, ms=int((time.time() - t) * 1000), errors=e.errs)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    os.replace(tmp, out)
    return dict(ok=True, events=n, ms=int((time.time() - t) * 1000), errors=[])


if __name__ == "__main__":
    proj = sys.argv[1]
    d = parse(open(os.path.join(proj, FILE), encoding="utf-8").read(), proj=proj)
    if "--json" in sys.argv:
        json.dump(d, sys.stdout, ensure_ascii=False, indent=1)
        sys.exit(0)
    bad = 0
    for L in d["lines"]:
        print("%s %-24s %s" % (L["key"], L["jp"][:24], "OK" if not L["errors"] else "; ".join(L["errors"])))
        bad += bool(L["errors"])
    print("%d 行, %d 行有问题%s" % (len(d["lines"]), bad, "; " + "; ".join(d["errors"]) if d["errors"] else ""))
    sys.exit(1 if bad or d["errors"] else 0)
