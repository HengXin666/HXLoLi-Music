# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""karetpl 用法示例：读一份带模板的 ASS，执行它，写出结果。

跑法：
    hx-karaoke example.py <源.ass> [输出.ass]

要点：**本包不含任何特效名**。想让结果不同，改的是那份 ASS 里的 Comment，
不是这里的参数  这是刻意的设计（见 CONTRACT.md 的约束 1）。
"""
import sys

from karetpl import AssWriter, Expander, Metrics, Program


class FontMetrics(Metrics):
    """注入字体度量。

    默认实现按"每字 = fs + spacing"整数进位，够用但不精确。
    某成品实测：line.width 用整数（8 字 = 600），$scenter 用真实 advance（75.14）。
    换字体就在这里覆盖，**不必改 karetpl 本身**。
    """

    def __init__(self, center_advance=None):
        super().__init__(center_advance=center_advance)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    dst = sys.argv[2] if len(sys.argv) > 2 else "karetpl_out.ass"
    if not src:
        sys.exit("用法: hx-karaoke example.py <源.ass> [输出.ass]")

    prog = Program.from_file(src)
    print(f"程序: code={len(prog.code)} templates={len(prog.templates)} "
          f"karaoke={len(prog.karaoke)} styles={len(prog.styles)}")

    exp = Expander(prog, metrics=FontMetrics(75.14), seed=7)
    events = exp.expand()
    print(f"展开 {len(events)} 条")
    if exp.warnings:
        print(f"警告 {len(exp.warnings)} 条（前 3 条）:")
        for w in exp.warnings[:3]:
            print("   ", w[:100])

    n = AssWriter.write(events, dst, styles=prog.styles,
                        res=(prog.res_x, prog.res_y), title=prog.title)
    print(f"写出 {n} 条 -> {dst}")


if __name__ == "__main__":
    main()
