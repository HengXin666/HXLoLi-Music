#!/usr/bin/env python3
"""
ASS 字幕整体时间偏移工具

用法:
  uv run shift_ass.py <input.ass> <offset>

offset 格式示例:
  +1s        向后偏移 1 秒
  -500ms     向前偏移 500 毫秒
  +1.5s      向后偏移 1.5 秒
  -2s        向前偏移 2 秒
  +100ms     向后偏移 100 毫秒

说明:
  - 若偏移后时间为负数，强制裁到 0s 并打印警告
  - 输出文件默认为 <stem>_shifted.ass，可用 --out 指定
"""

import re
import sys
from pathlib import Path

# 复用 split_ass.py 中的工具函数（同目录）
sys.path.insert(0, str(Path(__file__).parent))
from split_ass import parse_time, format_time, read_ass, write_ass, parse_event, rebuild_event


def parse_offset(s: str) -> float:
    """
    解析偏移量字符串，返回秒（浮点，可为负）。
    支持格式：+1s / -500ms / +1.5s / -2s 等
    """
    m = re.fullmatch(r'([+-]?\d+(?:\.\d+)?)(ms|s)', s.strip())
    if not m:
        raise ValueError(
            f"无法解析偏移量: {s!r}\n"
            "格式示例: +1s  -500ms  +1.5s  -2s  +100ms"
        )
    value, unit = float(m.group(1)), m.group(2)
    return value / 1000.0 if unit == "ms" else value


def shift_ass(input_path: str, offset: float, output_path: str) -> None:
    print(f"[时间偏移] {input_path}")
    direction = "后移" if offset >= 0 else "前移"
    print(f"  偏移量: {direction} {abs(offset):.3f}s")

    lines = read_ass(input_path)
    warned = False
    result = []

    for line in lines:
        ev = parse_event(line)
        if ev is None:
            result.append(line)
            continue

        etype, layer, start, end, rest = ev
        new_start = start + offset
        new_end = end + offset

        if new_start < 0:
            if not warned:
                print(f"  [警告] 部分行偏移后时间为负，已强制裁到 0:00:00.00")
                warned = True
            new_end = max(new_end, 0.0)
            new_start = 0.0

        result.append(rebuild_event(etype, layer, new_start, new_end, rest))

    write_ass(result, output_path)
    print("[完成]")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="ASS 字幕整体时间偏移工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input", help="输入 ASS 文件路径")
    # 用 nargs='?' 配合 parse_known_args 绕过 argparse 把 -8s 当选项的问题
    parser.add_argument("--out", default=None, help="输出文件路径（默认 <stem>_shifted.ass）")

    # 手动从 sys.argv 里提取 offset（可能是 -8s 这种负数形式）
    raw_args = sys.argv[1:]
    # 找出 --out 及其值，剩余的位置参数就是 input 和 offset
    positional = []
    out_val = None
    i = 0
    while i < len(raw_args):
        if raw_args[i] == "--out" and i + 1 < len(raw_args):
            out_val = raw_args[i + 1]
            i += 2
        elif raw_args[i].startswith("--out="):
            out_val = raw_args[i][6:]
            i += 1
        elif raw_args[i] in ("-h", "--help"):
            parser.print_help()
            sys.exit(0)
        else:
            positional.append(raw_args[i])
            i += 1

    if len(positional) != 2:
        parser.print_usage()
        print(f"[错误] 需要且仅需要 2 个位置参数: input offset，实际得到 {len(positional)} 个")
        sys.exit(1)

    class Args:
        pass
    args = Args()
    args.input = positional[0]
    args.offset = positional[1]
    args.out = out_val

    try:
        offset = parse_offset(args.offset)
    except ValueError as e:
        print(f"[错误] {e}")
        sys.exit(1)

    output_path = args.out
    if output_path is None:
        stem = Path(args.input).stem
        output_path = str(Path(args.input).parent / f"{stem}_shifted.ass")

    shift_ass(args.input, offset, output_path)


if __name__ == "__main__":
    main()
