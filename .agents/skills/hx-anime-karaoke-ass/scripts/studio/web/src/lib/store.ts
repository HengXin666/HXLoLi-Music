import { create } from 'zustand';
import type { Beats, Clip, Edl, ExplainItem, HitEvent, LyricLine, Peaks, PlaceLine, PlacementRes, Preset, Project, ProfileRes, Review } from './api';
import { buildIndex, type Index, type Range } from './sel';
import { defaultVis, type VisMap } from './tracks';

export interface View { v0: number; v1: number }
export type Compare = 'off' | 'ab' | 'wipe' | 'side';
export interface MenuState { x: number; y: number; source: 'lyrics' | 'timeline' | 'monitor'; hits?: HitEvent[] }
export interface NoteBox { x: number; y: number; kind: 'note' | 'bad'; tag?: string }

const LS_VIS = 'hxstudio.vis';
const LS_H = 'hxstudio.trackH';
const LS_COL = 'hxstudio.collapsed.v2'; // v2 (2026-11-09): FX 组默认折叠; true=折叠, false=用户明确展开 (不自动折叠), 缺省=按高度自动
const load = <T,>(k: string, d: T): T => { try { const v = localStorage.getItem(k); return v ? { ...d, ...JSON.parse(v) } : d; } catch { return d; } };

interface S {
  project: Project | null;
  lines: LyricLine[];
  ix: Index;
  out: ProfileRes | null;
  ref: ProfileRes | null;
  peaks: Peaks | null;
  edl: Edl | null;
  clips: Clip[];
  beats: Beats | null;
  reviews: Review[];
  duration: number;
  view: View;
  playing: boolean;
  rate: number;
  curLine: number; // lines 下标, -1 = 无
  octo: 'loading' | 'ready' | 'error' | 'off';
  octoErr: string;
  assRev: number; // out.ass 热重载计数
  hover: number | null; // 时间线悬停时间
  hoverLine: number | null; // 歌词浏览模式悬停句 (lines 下标)
  // 选区
  caret: number | null;
  anchor: number | null;
  ranges: Range[];
  explainBusy: boolean; // 选区说明请求中
  explainErr: string; // 最近一次说明请求的错误 (空 = 无)
  explain: ExplainItem[] | null; // 当前选区的说明 (状态栏/检查器/时间线涉及轨)
  // 回放
  loop: { t0: number; t1: number } | null;
  stopAt: number | null; // 播放选区: 到点停
  // 菜单/检查器/对比
  menu: MenuState | null;
  noteBox: NoteBox | null;
  inspector: boolean;
  inspectHits: HitEvent[] | null;
  compare: Compare;
  abShow: 'out' | 'ref';
  wipe: number; // 划变位置 0..1
  vis: VisMap;
  onlyUnits: string[] | null;
  trackH: Record<string, number>;
  collapsed: Record<string, boolean>;
  monitorKept: number;
  // 位置预设: place = 服务端状态 (当前预设/任务); placeCand = 正在预览的候选 (null = 不预览); placeLines = 服务端给的每句块位移
  place: PlacementRes | null;
  placeOpen: boolean;
  placeCand: Preset | null;
  placeLines: PlaceLine[] | null;
  toast: string;
  set: (p: Partial<S>) => void;
}

export const useStore = create<S>((set) => ({
  project: null,
  lines: [],
  ix: { flat: [], start: [] },
  out: null,
  ref: null,
  peaks: null,
  edl: null,
  clips: [],
  beats: null,
  reviews: [],
  duration: 0,
  view: { v0: 0, v1: 1 },
  playing: false,
  rate: 1,
  curLine: -1,
  octo: 'loading',
  octoErr: '',
  assRev: 0,
  hover: null,
  hoverLine: null,
  caret: null,
  anchor: null,
  ranges: [],
  explain: null,
  explainBusy: false,
  explainErr: '',
  loop: null,
  stopAt: null,
  menu: null,
  noteBox: null,
  inspector: false,
  inspectHits: null,
  compare: 'off',
  abShow: 'out',
  wipe: 0.5,
  vis: load(LS_VIS, defaultVis()),
  onlyUnits: null,
  trackH: load<Record<string, number>>(LS_H, {}),
  collapsed: load<Record<string, boolean>>(LS_COL, { fx: true }),
  monitorKept: 0,
  place: null,
  placeOpen: false,
  placeCand: null,
  placeLines: null,
  toast: '',
  set: (p) => set(p),
}));

// 持久化: 轨显示, 轨高, 折叠
useStore.subscribe((s, p) => {
  if (s.vis !== p.vis) localStorage.setItem(LS_VIS, JSON.stringify(s.vis));
  if (s.trackH !== p.trackH) localStorage.setItem(LS_H, JSON.stringify(s.trackH));
  if (s.collapsed !== p.collapsed) localStorage.setItem(LS_COL, JSON.stringify(s.collapsed));
  if (s.lines !== p.lines) useStore.setState({ ix: buildIndex(s.lines) });
});

/** 当前句: 已开始的句里起点最晚的那句 (句尾淡出与下一句重叠时, 取新开始的句).
 * 句间空隙保持上一句; 第一句之前取第一句 (即将唱的句), 所以有歌词时恒 >= 0. */
/*
 * Agent Notes: studio 状态
 * .agents/notes/implemented/feature/2026-11-09-karaoke-studio.md
 */
export function lineAt(lines: LyricLine[], t: number): number {
  if (!lines.length) return -1;
  let best = 0, bs = -Infinity;
  for (let i = 0; i < lines.length; i++) {
    const a = lines[i].t[0];
    if (a <= t && a >= bs) { best = i; bs = a; }
  }
  return best;
}

export function fmtTime(t: number, cs = true): string {
  if (!Number.isFinite(t)) t = 0;
  const m = Math.floor(t / 60);
  const s = t - m * 60;
  return `${String(m).padStart(2, '0')}:${cs ? s.toFixed(2).padStart(5, '0') : String(Math.floor(s)).padStart(2, '0')}`;
}

let toastTimer = 0;
export function toast(msg: string) {
  useStore.setState({ toast: msg });
  clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => useStore.setState({ toast: '' }), 2600);
}
