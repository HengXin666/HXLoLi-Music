#!/usr/bin/env python3
"""检查一份 ASS 里有没有静默失效的事件  占了事件数但不产生任何像素。

实测背景: 一份生产级成品里存在三类残渣, 它们照样占着事件数与文件体积:
  1. 未求值的模板占位符 (如 !shape[math.random(3)]!)  libass 渲染 0 像素;
  2. 结束时间 <= 开始时间的事件 (最极端 -0.67 秒)  libass 静默丢弃;
  3. 定义了却从未被引用的素材名。
后果: 按事件数评估作品的手法会失真  写了多少与播了多少不相等。

用法: python3 lint_events.py <字幕.ass>
退出码 0 = 无残渣; 1 = 有; 2 = 参数错。
"""
import re
import sys

BS = chr(92)


def t2ms(t: str) -> int:
    h, m, s = t.split(":")
    return int(h) * 3600000 + int(m) * 60000 + int(round(float(s) * 1000))


def main() -> int:
    path = sys.argv[1]
    unresolved = []
    bad_time = []
    total = 0
    for i, line in enumerate(open(path, encoding="utf-8-sig", errors="replace"), 1):
        if not line.startswith("Dialogue:"):
            continue
        total += 1
        f = line[9:].split(",", 9)
        if len(f) < 10:
            continue
        t0, t1, text = t2ms(f[1]), t2ms(f[2]), f[9]
        if t1 <= t0:
            bad_time.append((i, (t1 - t0) / 1000.0))
        # 未求值的模板占位符: 形如 !expr!
        if "!" in text and re.search(r"![^!]{1,80}!", text):
            unresolved.append((i, re.search(r"![^!]{1,80}!", text).group(0)[:60]))
    print("Dialogue 总数: %d" % total)
    print()
    print("未求值的模板占位符: %d 条 (渲染 0 像素)" % len(unresolved))
    for i, s in unresolved[:3]:
        print("   行 %d: %s" % (i, s))
    print("零或负时长事件: %d 条 (libass 静默丢弃)" % len(bad_time))
    for i, d in bad_time[:3]:
        print("   行 %d: %.2f 秒" % (i, d))
    bad = len(unresolved) + len(bad_time)
    print()
    if bad:
        print("总判定: 有 %d 条残渣 (%.1f%%)  按事件数统计手法规模会失真" % (bad, bad / max(total, 1) * 100))
        return 1
    print("总判定: 无残渣")
    return 0


if __name__ == "__main__":
    sys.exit(main())