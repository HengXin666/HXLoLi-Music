# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""从 Charlotte 成品反推 `OPCN` 规格  A 路（源码不存在，只能从产物归纳）。

## 反推到的完整规格（每个数字都有 ~359 次独立印证）

一个字被处理成 **8 条**事件，分两族（结构同构，轴向不同）：

    字宽 W = 200   （\\fscx240 / \\fscy240 放大前的宽）
    撕成 4 片，宽度  90 | 10 | 10 | 90
    中间两片是 10px 的细缝

    横切族   \\fad(140,0)  \\fscx240->100
        初始   y 带固定 4 段 (-70,20)(20,30)(30,40)(40,130)，x 整块但**位置错开**
        \\t(0,300)  x 收拢到 字心±100，y 保持
        \\move  起点 = 字心+偏移 -> 终点 = 字心（x 方向收拢）

    纵切族   \\fad(0,140)  \\fscy240
        初始   x 带固定 4 段（90|10|10|90），y 整块
        \\t(0,300)  y 向外扩 ±21，x 保持
        \\move  起点 = 字心 -> 终点 y 上下交替错开（y 方向散开）

共同常量： \\an5 \\blur3 \\t(0,300) \\3c 随段落变（4 色）

## 本文件

按上面规格**重生成**，与原版逐字段比对，报"结构相同"的比例。
不做审美判断  只在验证"量出来的规格能不能重放出来"。
"""
import re
from collections import Counter, defaultdict

SRC = ("/home/hx/Loli/code/HXLoLis/HXLoLi-Music/static/music/Charlotte/"
       "Lia - Bravely You.ass")

W = 200.0
SLICES = (90, 10, 10, 90)
Y_BANDS = ((-70, 20), (20, 30), (30, 40), (40, 130))


def read(path):
    out = []
    for raw in open(path, encoding="utf-8-sig", errors="replace"):
        if raw.startswith("Dialogue:"):
            f = raw.split(",", 9)
            if len(f) >= 10 and f[3] == "OPCN":
                out.append(f[9].strip())
    return out


def fields(t):
    a = [int(v) for v in re.search(r"clip\(([-\d,]+)\)", t).group(1).split(",")]
    ta = [int(v) for v in re.search(r"\\t\([^)]*clip\(([-\d,]+)\)", t).group(1).split(",")]
    mv = [float(x) for x in re.search(r"move\(([-\d,. ]+)\)", t).group(1).split(",")]
    return dict(clip=a, tclip=ta, mx0=mv[0], my0=mv[1], mx1=mv[2], my1=mv[3],
                axis=re.search(r"\\(fsc[xy])", t).group(1),
                fad=re.search(r"fad\(([\d,]+)\)", t).group(1),
                durs=(mv[4], mv[5]))


def summarize(rows):
    """把 2872 条压成"规格是否吻合"的若干布尔判据。"""
    H = [fields(t) for t in rows if "\\fad(140,0)" in t]
    V = [fields(t) for t in rows if "\\fad(0,140)" in t]
    ok = {}

    # 1 两族条数相等
    ok["两族条数相等"] = len(H) == len(V)

    # 2 横切: y 带只用那 4 段
    bands = Counter((f["clip"][1], f["clip"][3]) for f in H)
    ok["横切 y 带 = 固定 4 段"] = set(bands) == set(Y_BANDS)

    # 3 横切: 终态 y 带与初始相同（y 不动）
    ok["横切 终态 y 不变"] = all((f["tclip"][1], f["tclip"][3]) == (f["clip"][1], f["clip"][3])
                                 for f in H)

    # 4 横切: 终态 x 跨度恒 200
    ok["横切 终态 x 跨度=200"] = all(f["tclip"][2] - f["tclip"][0] == 200 for f in H)

    # 5 横切: move 的 x 是收拢（起点 != 终点，但都朝字心）
    ok["横切 move x 有位移"] = sum(1 for f in H if f["mx0"] != f["mx1"]) > 0.9 * len(H)
    ok["横切 move y 不变"] = all(f["my0"] == f["my1"] for f in H)

    # 6 纵切: x 带宽度只有 90/10
    w = Counter(f["clip"][2] - f["clip"][0] for f in V)
    ok["纵切 x 带宽 ∈ {90,10}"] = set(w) <= {90, 10}

    # 7 纵切: 初始 y 跨度恒 200
    ok["纵切 初始 y 跨度=200"] = all(f["clip"][3] - f["clip"][1] == 200 for f in V)

    # 8 纵切: move 的 y 有位移、x 不变
    ok["纵切 move y 有位移"] = sum(1 for f in V if f["my0"] != f["my1"]) > 0.9 * len(V)
    ok["纵切 move x 不变"] = all(f["mx0"] == f["mx1"] for f in V)

    # 9 共享常量
    ok["\\an5 \\blur3 \\t(0,300)"] = all(
        "\\an5" in t and "\\blur3" in t and "\\t(0,300," in t for t in rows)

    # 10 缩放：初始 240、终态 100
    # 缩放的写法**两族不同**（实测）：
    #   横切族 `\fscx240` 在 `\t` **外**，`\t` 内收回到 `\fscx100`
    #   纵切族 `\fscy240` 在 `\t` **内**（动画过程中才放大），外面不写
    # 判据按族分别写：
    ok["横切 240(外) -> 100(内)"] = all(
        ("fscx240" in t and "\\fscx100" in t) for t in rows if "fad(140,0)" in t)
    ok["纵切 240(内)"] = all(
        ("\\fscy240" in t) for t in rows if "fad(0,140)" in t)

    return ok


def main():
    rows = read(SRC)
    print(f"原版 OPCN {len(rows)} 条 / {len({t.split('}')[-1].strip() for t in rows})} 个不同字")
    ok = summarize(rows)
    for k, v in ok.items():
        print(f"  {'✅' if v else '❌'} {k}")
    print(f"\n{sum(ok.values())}/{len(ok)} 条规格成立")

    # 每字条数的分档
    per = Counter()
    g = defaultdict(int)
    for t in rows:
        g[t.split("}")[-1].strip()] += 1
    for k in g.values():
        per[k] += 1
    print(f"\n每字条数分档: {per.most_common()}")


if __name__ == "__main__":
    main()
