# -*- coding: utf-8 -*-
"""`--probe`: 只体检不出图  渲染器在不在、`\\1img` 引用的图片能不能找到、用了哪些字体."""
import os
import re


def probe(ass_path, find_octopus, find_chrome):
    """
    .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
    .agents/notes/implemented/process/2026-10-05-karaoke-scripts-grouping.md
find_octopus / find_chrome 由调用方注入(见 octo_browser), 便于单独测探测逻辑."""
    ok = True
    oct_dir = find_octopus()
    print("定制版渲染器:", oct_dir or "**未找到** (设 ASSFX_OCTOPUS_DIR)")
    ok &= bool(oct_dir)
    if oct_dir:
        w = os.path.join(oct_dir, "libass", "libass.wasm")
        with open(w, "rb") as f:
            blob = f.read()
        # Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈; hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开
        # 
        # 
        tags = [t.decode() for t in re.findall(rb"[1-4]img", blob)]
        print("  wasm 内 VSFilterMod 标签:", sorted(set(x for x in tags)), "(系统 libass 为 0 个)")
    ch = find_chrome()
    print("chromium:", ch or "**未找到** (设 ASSFX_CHROME)")
    ok &= bool(ch)
    d = os.path.dirname(os.path.abspath(ass_path))
    txt = open(ass_path, encoding="utf-8-sig", errors="replace").read()
    imgs = []
    for m in re.finditer(r"\\[1-4]img\(([^)]+)\)", txt):
        rel = m.group(1).strip()
        if rel.startswith("data:") or "!" in rel or "$" in rel:
            continue
        if rel not in imgs:
            imgs.append(rel)
    print(f"\\1img 引用 {len(imgs)} 个:")
    for rel in imgs:
        p = os.path.join(d, rel)
        state = "OK" if os.path.exists(p) else "**缺失**"
        size = ""
        if os.path.exists(p):
            try:
                from PIL import Image
                size = " %s" % (Image.open(p).size,)
            except Exception:
                pass
        print(f"  [{state}] {rel}{size}")
        ok &= os.path.exists(p)
        if imgs.count(rel) == 0 and rel == "":
            ok = False
    # 字体
    fonts = sorted(set(re.findall(r"^Style: [^,]+,([^,]+),", txt, re.M)))
    print("字体:", ", ".join(fonts))
    return 0 if ok else 1
