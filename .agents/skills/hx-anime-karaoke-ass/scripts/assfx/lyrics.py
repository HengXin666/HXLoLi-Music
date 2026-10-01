# -*- coding: utf-8 -*-
"""
歌词标注格式解析（一行一句）:

    时间 | 日文(带标注) | 中文翻译
    00:26.586 | [愛|あい]のイロハを[学|まな]んでも | 纵然学会了爱的入门

日文标注语法:
    [漢|かん]        单个汉字 + 振假名（注音以“汉字”为单位，逐字对齐在各自汉字正上方）
    [世界|せ.かい]   多字词：用 . 把读音按汉字切开 → 每个汉字各自注音、各自按音拍高亮（推荐写法）
    [今日|=きょう]   熟字训/义训（读音无法按字拆分）：= 开头，整组居中注音
                     多字词既没有 . 也没有 = 时会告警（lint），默认按整组处理
    {Latin|かな}     非假名片段（英文和声等）；显示原文，对齐时用假名读音，不显示注音
    かな / カナ      每个音拍一个单元；片假名对齐时自动转平假名
    空格             词间空白（显示为 0.5em 间隔）
    ？！、。…        仅显示，不参与计时（并入前一个单元）
    " / "            长句拆成多句显示（日文、中文用同样段数切）；后续段与前段一起对齐
时间取官方/lrc 时间（歌曲时间轴），在 project.json 里用 offset 平移到视频时间轴。
"""
import re

SMALL = set("ゃゅょぁぃぅぇぉゎャュョァィゥェォヮ")
PUNCT = set("？！?!、。…・「」『』（）()〜～,.，：")


def kata2hira(s):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def morae(kana):
    out = []
    for ch in kana:
        if ch in SMALL and out:
            out[-1] += ch
        else:
            out.append(ch)
    return out


LINT = []      # 标注告警（load 后打印）

TOKEN = re.compile(r"\[([^\]|]+)\|([^\]]+)\]|\{([^}|]+)\|([^}]+)\}|(\s+)|(.)")


def parse_jp(text):
    """-> list of units: {surf, read(hira, 用于对齐), ruby(显示用注音或None), kind, morae}"""
    units = []
    for m in TOKEN.finditer(text.strip()):
        kanji, yomi, latin, lread, space, ch = m.groups()
        if kanji:
            parts, group = None, False
            if yomi.startswith("="):
                yomi = yomi[1:]; group = True
            if "." in yomi:
                parts = yomi.split(".")
                if len(parts) != len(kanji):
                    raise ValueError(f"[{kanji}|{yomi}] 读音切分数 {len(parts)} ≠ 汉字数 {len(kanji)}")
                if any(p[:1] in SMALL for p in parts):
                    raise ValueError(f"[{kanji}|{yomi}] 切分点不能落在小假名前")
                yomi = "".join(parts)
            elif len(kanji) == 1:
                parts = [yomi]
            elif not group:
                LINT.append(f"多字汉字 [{kanji}|{yomi}] 没有按字切分读音（写成 [{kanji}|x.y] ；熟字训用 [{kanji}|={yomi}]）")
            r = kata2hira(yomi)
            u = dict(surf=kanji, read=r, ruby=yomi, kind="kanji", morae=morae(r), ruby_parts=parts)
            if parts:
                u["part_morae"] = [len(morae(kata2hira(p))) for p in parts]
                if sum(u["part_morae"]) != len(u["morae"]):
                    raise ValueError(f"[{kanji}|{yomi}] 切分后音拍数不一致")
            units.append(u)
        elif latin:
            r = kata2hira(lread)
            units.append(dict(surf=latin, read=r, ruby=None, kind="latin", morae=morae(r)))
        elif space:
            units.append(dict(surf=" ", kind="space", morae=[]))
        else:
            if ch in PUNCT:
                if units and units[-1]["kind"] != "space":
                    units[-1]["surf"] += ch
                else:
                    units.append(dict(surf=ch, kind="punct", morae=[]))
                continue
            if ch in SMALL and units and units[-1]["kind"] == "kana":
                units[-1]["surf"] += ch; units[-1]["read"] += kata2hira(ch)
                units[-1]["morae"] = morae(units[-1]["read"])
                continue
            units.append(dict(surf=ch, read=kata2hira(ch), ruby=None, kind="kana", morae=morae(kata2hira(ch))))
    return units


def parse_time(s):
    s = s.strip()
    if not s or s == "-":
        return None
    p = s.split(":")
    return float(p[0]) * 60 + float(p[1]) if len(p) == 2 else float(s)


def load(path):
    lines = []
    for raw in open(path, encoding="utf-8"):
        raw = raw.rstrip("\n")
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        # 注意 [漢字|よみ] 里也有 "|"，所以按 " | "（两侧带空格）切
        parts = [x.strip() for x in raw.split(" | ")]
        t, jp, zh = parts[0], parts[1], parts[2] if len(parts) > 2 else ""
        # 长句拆显示：日文/中文都用 " / " 切成同样段数；后续段没有 lrc 时间（cont=True），
        # 对齐时与前一段合并成同一个块（不在中间切窗口），显示时是独立的一句
        jps = [x.strip() for x in jp.split(" / ")]
        zhs = [x.strip() for x in zh.split(" / ")]
        if len(zhs) != len(jps):
            if len(jps) > 1:
                print(f"[lyrics lint] 中文段数({len(zhs)})≠日文段数({len(jps)})，中文整句放在第一段: {jp}")
            zhs = [zh] + [""] * (len(jps) - 1)
        for k, (jj, zz) in enumerate(zip(jps, zhs)):
            # 整句包在（）里 = 合いの手/コール（和主唱重叠的伴唱、口号）：不参与 CTC 对齐和切窗，
            # 时间由 fixes.json 指定（默认按 lrc 时间起每拍一个音），显示时作为小号副字幕
            call = (jj[:1] in "（(" and jj[-1:] in "）)")
            lines.append(dict(idx=len(lines), t_lrc=parse_time(t) if k == 0 else None, jp=jj, zh=zz,
                              units=parse_jp(jj), cont=k > 0, call=call))
    for w in dict.fromkeys(LINT):
        print("[lyrics lint]", w)
    LINT.clear()
    return lines


def plain(units):
    return "".join(u["surf"] for u in units)


if __name__ == "__main__":
    import sys, json
    for ln in load(sys.argv[1]):
        print(ln["idx"], ln["t_lrc"], plain(ln["units"]), "|", " ".join("/".join(u["morae"]) for u in ln["units"] if u["morae"]))
