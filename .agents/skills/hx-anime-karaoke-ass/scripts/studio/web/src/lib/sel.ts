/* 歌词选区 (文本编辑器口径, 字粒度). 位置 = 全曲字的全局下标 g. 纯函数, 不依赖 React. */
import type { LyricLine, SelRange } from './api';

export interface Flat { li: number; ci: number }
export interface Index { flat: Flat[]; start: number[] }

export function buildIndex(lines: LyricLine[]): Index {
  const flat: Flat[] = [];
  const start: number[] = [];
  lines.forEach((l, li) => {
    start.push(flat.length);
    l.chars.forEach((_, ci) => flat.push({ li, ci }));
  });
  return { flat, start };
}

export type Range = [number, number];

export const norm = (a: number, b: number): Range => (a <= b ? [a, b] : [b, a]);

/** 合并重叠 / 相邻区间 */
export function merge(rs: Range[]): Range[] {
  const s = [...rs].map(([a, b]) => norm(a, b)).sort((x, y) => x[0] - y[0]);
  const out: Range[] = [];
  for (const r of s) {
    const last = out[out.length - 1];
    if (last && r[0] <= last[1] + 1) last[1] = Math.max(last[1], r[1]);
    else out.push([r[0], r[1]]);
  }
  return out;
}

export function inRanges(rs: Range[], g: number): boolean {
  return rs.some(([a, b]) => g >= a && g <= b);
}

/** 全局区间 -> 按句拆开 [{line(arc 行号), from, to}] */
export function toSel(rs: Range[], lines: LyricLine[], ix: Index): SelRange[] {
  const out: SelRange[] = [];
  for (const [a, b] of merge(rs)) {
    let g = a;
    while (g <= b) {
      const { li } = ix.flat[g];
      const end = Math.min(b, ix.start[li] + lines[li].chars.length - 1);
      out.push({ line: lines[li].line ?? li, from: g - ix.start[li], to: end - ix.start[li] });
      g = end + 1;
    }
  }
  return out;
}

export interface Summary { n: number; t0: number; t1: number; lines: number[]; label: string; text: string }

export function summarize(rs: Range[], lines: LyricLine[], ix: Index): Summary | null {
  const m = merge(rs);
  if (!m.length) return null;
  let n = 0, t0 = Infinity, t1 = -Infinity, text = '';
  const ls = new Set<number>();
  for (const [a, b] of m) {
    for (let g = a; g <= b; g++) {
      const { li, ci } = ix.flat[g];
      const L = lines[li];
      const c = L.chars[ci];
      n++;
      ls.add(li);
      text += c.ch;
      const whole = ci === 0 && g + L.chars.length - 1 <= b;
      t0 = Math.min(t0, whole ? L.t[0] : c.s);
      const lastOfLine = ci === L.chars.length - 1;
      t1 = Math.max(t1, lastOfLine && g - L.chars.length + 1 >= a ? L.t[1] : c.e);
    }
  }
  const arr = [...ls].sort((x, y) => x - y);
  const no = (li: number) => `L${String(lines[li].line ?? li).padStart(2, '0')}`;
  const label = arr.length === 1 ? no(arr[0]) : `${no(arr[0])}-${no(arr[arr.length - 1])}`;
  return { n, t0, t1, lines: arr, label, text };
}

/** 双击选词: 同句同 unit 的连续字 */
export function wordAt(g: number, lines: LyricLine[], ix: Index): Range {
  const { li, ci } = ix.flat[g];
  const ch = lines[li].chars;
  const u = ch[ci].unit;
  if (u == null) return [g, g];
  let a = ci, b = ci;
  while (a > 0 && ch[a - 1].unit === u) a--;
  while (b < ch.length - 1 && ch[b + 1].unit === u) b++;
  return [ix.start[li] + a, ix.start[li] + b];
}

export function lineRange(li: number, lines: LyricLine[], ix: Index): Range {
  return [ix.start[li], ix.start[li] + lines[li].chars.length - 1];
}

/** 上下换句: 同列 (按字下标) 落到相邻句, 越界取末字 */
export function vertical(g: number, d: -1 | 1, lines: LyricLine[], ix: Index): number {
  const { li, ci } = ix.flat[g];
  const nl = Math.max(0, Math.min(lines.length - 1, li + d));
  if (nl === li) return g;
  return ix.start[nl] + Math.min(ci, lines[nl].chars.length - 1);
}

export function fmtTc(t: number): string {
  const m = Math.floor(t / 60);
  const s = t - m * 60;
  return `${String(m).padStart(2, '0')}:${s.toFixed(2).padStart(5, '0')}`;
}
