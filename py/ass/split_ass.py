#!/usr/bin/env python3
"""
ASS 字幕分割工具

用法:
  # 智能分割（自动检测 OP/ED 边界，各自偏移到 0:00）
  python split_ass.py smart <input.ass> [--gap <秒>] [--out-dir <目录>]

  # 指定区间分割（将 [L, R] 区间提取，时间偏移到 L' 开始）
  python split_ass.py range <input.ass> <L> <R> <L'> [--out <output.ass>]

时间格式: H:MM:SS.cc  例如 0:01:30.00

示例:
  python split_ass.py smart op_ed.ass
  python split_ass.py smart op_ed.ass --gap 10 --out-dir ./output
  python split_ass.py range full.ass 0:00:00.00 0:01:30.00 0:00:00.00 --out op.ass
  python split_ass.py range full.ass 0:03:00.00 0:04:30.00 0:00:00.00 --out ed.ass
  python split_ass.py range full.ass 0:03:00.00 all 0:00:00.00 --out ed.ass
"""

import re
import sys
import argparse
from pathlib import Path
from typing import Optional


# ─────────────────────────── 时间工具 ───────────────────────────

def parse_time(s: str) -> float:
    """将 ASS 时间字符串 H:MM:SS.cc 解析为秒（浮点）"""
    m = re.match(r'^(\d+):(\d{2}):(\d{2})\.(\d{2})$', s.strip())
    if not m:
        raise ValueError(f"无法解析时间: {s!r}，格式应为 H:MM:SS.cc")
    h, mi, sec, cs = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    return h * 3600 + mi * 60 + sec + cs / 100.0


def format_time(t: float) -> str:
    """将秒（浮点）格式化为 ASS 时间字符串 H:MM:SS.cc"""
    if t < 0:
        t = 0.0
    cs = round(t * 100)
    h = cs // 360000
    cs %= 360000
    mi = cs // 6000
    cs %= 6000
    sec = cs // 100
    cs %= 100
    return f"{h}:{mi:02d}:{sec:02d}.{cs:02d}"


# ─────────────────────────── ASS 解析 ───────────────────────────

def read_ass(path: str) -> list[str]:
    """读取 ASS 文件，自动检测编码"""
    for enc in ("utf-8-sig", "utf-8", "gbk", "shift_jis"):
        try:
            with open(path, encoding=enc) as f:
                return f.readlines()
        except (UnicodeDecodeError, LookupError):
            continue
    raise RuntimeError(f"无法解码文件: {path}")


def write_ass(lines: list[str], path: str) -> None:
    """写出 ASS 文件（UTF-8 with BOM，与 Aegisub 兼容）"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.writelines(lines)
    print(f"  → 已写出: {path}")


# ─────────────────────────── 事件行解析 ───────────────────────────

_EVENT_RE = re.compile(
    r'^(Dialogue|Comment):\s*(\d+),(\d+:\d{2}:\d{2}\.\d{2}),(\d+:\d{2}:\d{2}\.\d{2}),(.*)',
    re.DOTALL
)


def parse_event(line: str):
    """解析一行事件，返回 (type, layer, start_s, end_s, rest) 或 None"""
    m = _EVENT_RE.match(line)
    if not m:
        return None
    etype = m.group(1)
    layer = m.group(2)
    start = parse_time(m.group(3))
    end = parse_time(m.group(4))
    rest = m.group(5)
    return etype, layer, start, end, rest


def rebuild_event(etype: str, layer: str, start: float, end: float, rest: str) -> str:
    return f"{etype}: {layer},{format_time(start)},{format_time(end)},{rest}"


# ─────────────────────────── 头部 / 样式提取 ───────────────────────────

def split_sections(lines: list[str]) -> tuple[list[str], list[str], list[str]]:
    """
    将 ASS 文件分为三段：
      header  - [Script Info] 及 [Aegisub Project Garbage]
      styles  - [V4+ Styles]
      events  - [Events]
    返回 (header_lines, style_lines, event_lines)
    """
    header, styles, events = [], [], []
    section = "header"
    for line in lines:
        low = line.strip().lower()
        if low == "[v4+ styles]":
            section = "styles"
        elif low == "[events]":
            section = "events"
        if section == "header":
            header.append(line)
        elif section == "styles":
            styles.append(line)
        else:
            events.append(line)
    return header, styles, events


def clean_project_garbage(header: list[str]) -> list[str]:
    """移除 [Aegisub Project Garbage] 节（含内容），避免路径残留"""
    result = []
    in_garbage = False
    for line in header:
        low = line.strip().lower()
        if low == "[aegisub project garbage]":
            in_garbage = True
            continue
        if in_garbage and low.startswith("["):
            in_garbage = False
        if not in_garbage:
            result.append(line)
    return result


# ─────────────────────────── 核心：区间提取 ───────────────────────────

def extract_range(
    event_lines: list[str],
    L: float,
    R: float,
    L_prime: float,
) -> list[str]:
    """
    从 event_lines 中提取 [L, R] 区间内的事件行，
    并将时间整体偏移，使 L 对应 L_prime。
    完全在区间外的行被丢弃；跨越边界的行被裁剪。
    """
    offset = L_prime - L
    result = []
    for line in event_lines:
        ev = parse_event(line)
        if ev is None:
            # 非事件行（Format: 行、空行等）原样保留
            result.append(line)
            continue
        etype, layer, start, end, rest = ev
        # 完全在区间外 → 丢弃
        if end <= L or start >= R:
            continue
        # 裁剪到区间
        new_start = max(start, L) + offset
        new_end = min(end, R) + offset
        result.append(rebuild_event(etype, layer, new_start, new_end, rest))
    return result


# ─────────────────────────── 智能分割 ───────────────────────────

def detect_op_ed_boundary(event_lines: list[str], gap_threshold: float = 5.0):
    """
    自动检测 OP 和 ED 的时间边界。
    策略：收集所有 Dialogue 行的时间，找到最大的"静默间隔"作为分割点。
    返回 (op_end, ed_start) 秒，若无法检测则返回 None。
    """
    times = []
    for line in event_lines:
        ev = parse_event(line)
        if ev and ev[0] == "Dialogue":
            _, _, start, end, _ = ev
            times.append((start, end))

    if not times:
        return None

    times.sort()
    # 找最大间隔
    best_gap = -1.0
    best_op_end = 0.0
    best_ed_start = 0.0
    for i in range(len(times) - 1):
        gap_start = times[i][1]   # 当前行结束
        gap_end = times[i + 1][0]  # 下一行开始
        gap = gap_end - gap_start
        if gap > best_gap:
            best_gap = gap
            best_op_end = gap_start
            best_ed_start = gap_end

    if best_gap < gap_threshold:
        print(f"  [警告] 最大静默间隔仅 {best_gap:.2f}s（阈值 {gap_threshold}s），"
              f"智能分割可能不准确")

    return best_op_end, best_ed_start


def smart_split(
    input_path: str,
    gap_threshold: float = 5.0,
    out_dir: Optional[str] = None,
) -> None:
    """智能分割：自动检测 OP/ED 边界，各自偏移到 0:00"""
    print(f"[智能分割] {input_path}")
    lines = read_ass(input_path)
    header, styles, events = split_sections(lines)
    header = clean_project_garbage(header)

    result = detect_op_ed_boundary(events, gap_threshold)
    if result is None:
        print("  [错误] 未找到任何 Dialogue 行，无法分割")
        sys.exit(1)

    op_end, ed_start = result
    total_end = max(
        (parse_event(l)[3] for l in events if parse_event(l) and parse_event(l)[0] == "Dialogue"),
        default=0.0
    )

    print(f"  检测到分割点: OP 结束={format_time(op_end)}  ED 开始={format_time(ed_start)}")
    print(f"  OP 区间: [0:00:00.00, {format_time(op_end)}]")
    print(f"  ED 区间: [{format_time(ed_start)}, {format_time(total_end)}]")

    stem = Path(input_path).stem
    if out_dir is None:
        out_dir = str(Path(input_path).parent)

    # 生成 OP
    op_events = extract_range(events, 0.0, op_end, 0.0)
    op_lines = header + styles + op_events
    write_ass(op_lines, str(Path(out_dir) / f"{stem}_OP.ass"))

    # 生成 ED
    ed_events = extract_range(events, ed_start, total_end + 1.0, 0.0)
    ed_lines = header + styles + ed_events
    write_ass(ed_lines, str(Path(out_dir) / f"{stem}_ED.ass"))

    print("[完成]")


# ─────────────────────────── 指定区间分割 ───────────────────────────

def range_split(
    input_path: str,
    L: float,
    R: float,
    L_prime: float,
    output_path: Optional[str] = None,
) -> None:
    """指定区间分割：提取 [L, R]，时间偏移到 L' 开始"""
    print(f"[区间分割] {input_path}")
    r_str = "all" if R == float("inf") else format_time(R)
    print(f"  区间: [{format_time(L)}, {r_str}]  → 偏移到 {format_time(L_prime)} 开始")
    lines = read_ass(input_path)
    header, styles, events = split_sections(lines)
    header = clean_project_garbage(header)

    out_events = extract_range(events, L, R, L_prime)
    out_lines = header + styles + out_events

    if output_path is None:
        stem = Path(input_path).stem
        output_path = str(Path(input_path).parent / f"{stem}_clip.ass")

    write_ass(out_lines, output_path)
    print("[完成]")


# ─────────────────────────── CLI ───────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ASS 字幕分割工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # smart 子命令
    p_smart = sub.add_parser("smart", help="智能分割（自动检测 OP/ED 边界）")
    p_smart.add_argument("input", help="输入 ASS 文件路径")
    p_smart.add_argument(
        "--gap", type=float, default=5.0,
        help="判定为分割点的最小静默间隔（秒，默认 5.0）"
    )
    p_smart.add_argument("--out-dir", default=None, help="输出目录（默认与输入文件同目录）")

    # range 子命令
    p_range = sub.add_parser("range", help="指定区间分割")
    p_range.add_argument("input", help="输入 ASS 文件路径")
    p_range.add_argument("L", help="区间开始时间，格式 H:MM:SS.cc")
    p_range.add_argument("R", help="区间结束时间，格式 H:MM:SS.cc；或填 all 表示取到文件末尾")
    p_range.add_argument("L_prime", metavar="L'", help="输出起始时间，格式 H:MM:SS.cc")
    p_range.add_argument("--out", default=None, help="输出文件路径（默认 <stem>_clip.ass）")

    args = parser.parse_args()

    if args.cmd == "smart":
        smart_split(args.input, gap_threshold=args.gap, out_dir=args.out_dir)
    elif args.cmd == "range":
        L = parse_time(args.L)
        R = float("inf") if args.R.strip().lower() == "all" else parse_time(args.R)
        L_prime = parse_time(args.L_prime)
        if L >= R:
            print(f"[错误] L ({args.L}) 必须小于 R ({args.R})")
            sys.exit(1)
        range_split(args.input, L, R, L_prime, output_path=args.out)


if __name__ == "__main__":
    main()
