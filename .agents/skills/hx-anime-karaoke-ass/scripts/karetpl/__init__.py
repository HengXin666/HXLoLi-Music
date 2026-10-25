# -*- coding: utf-8 -*-
"""karetpl  执行 ASS 内嵌模板程序（Karaoke Templater 的运行时）。

契约见同目录 CONTRACT.md。对外四个名字：

    from karetpl import Program, Expander, Metrics, AssWriter

    prog = Program.from_file("some.ass")
    evs  = Expander(prog).expand()
    AssWriter.write(evs, "out.ass", styles=prog.styles, res=(prog.res_x, prog.res_y))

它只把作者写好的程序跑出来，不发明特效  所以"像不像"由程序决定，不由本包决定。
"""
from karetpl.expander import Expander
from karetpl.metrics import Metrics
from karetpl.model import Event, Program, SourceLine, Style, Syllable, Template
from karetpl.parse import from_file, parse
from karetpl import writer
AssWriter = writer

__all__ = ["Program", "Expander", "Metrics", "AssWriter",
           "Event", "SourceLine", "Style", "Syllable", "Template", "from_file", "parse"]
