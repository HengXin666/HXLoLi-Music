import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { crisp, useHiDpiCanvas } from '../hooks/useHiDpiCanvas';
import { useSize } from '../hooks/useSize';
import { loopSelection, selectLine, setSelection } from '../lib/actions';
import type { Clip, Review } from '../lib/api';
import { clock } from '../lib/clock';
import { fmtTime, toast, useStore } from '../lib/store';
import { GROUP_NAME, REVIEW_KIND, TRACKS, hasEye, visible, type TrackDef } from '../lib/tracks';
import s from './Timeline.module.css';

/**
 * 时间线 (plan 3.4 / 3.7): 三层 = 静态画布 (刻度/轨底/片段/波形/密度) + 动态画布 (播放头/选区/悬停/循环) + DOM 文字层.
 * 轨: 全曲缩略 | 刻度 | MV | 波形 | 节拍 | 字层组 JP RB CN | FX 组 0-8 | 卡片 | 密度 (out 面积 + 参考虚线).
 * 轨头: 眼 (显示) / S (独显) / 锁, 轨高可拖, 轨组可折叠. 眼/S 同时决定监视器里渲染哪些事件.
 * 高度分配见 layoutRows 上方注释: 展开/折叠不改时间线总高; FX 展开放不下时在时间线内纵向滚动 (自绘细条), 页面永不出滚动条.
 */
const HEAD_W = 140;
const ROLE: Record<string, string> = { high: '#f0b85a', carrier: '#5e8fd8', rest: '#5b6474' };
const TRACK_COLOR: Record<string, string> = {
  jp: '#c9a7f0', rb: '#a08bd0', cn: '#8fb8e8', card: '#e88f8f',
  fx0: '#3f6f9e', fx1: '#46799f', fx2: '#4f84a3', fx3: '#5a8fa6', fx4: '#6699a6', fx5: '#5fa58c', fx6: '#6aa874', fx7: '#86ab62', fx8: '#a7aa5a',
};

export interface Row { id: string; name: string; y: number; h: number; def?: TrackDef; group?: 'text' | 'fx'; members?: string[]; auto?: boolean; vy?: number; vh?: number }

// 折叠语义: collapsed[g] === true 折叠; === false 用户明确展开 (不自动折叠); 缺省 = 按高度自动. FX 组默认折叠.
// 高度分配 (2026-11-09 用户定):
//  - 时间线总高只由用户拖分隔条决定; 展开/折叠组不改变它, 所以监视器画面大小不跳.
//  - 密度/波形是弹性轨, 先让到最小; 密度最多长到 80.
//  - FX 组展开后放不下: FX 9 条保持原高, 在时间线里开一个纵向滚动窗口 (自绘细滚动条), 其余轨不压.
//    窗口不足 FXWIN_MIN 时才依次: 自动折叠字层组 -> 按档压 MV/节拍/卡片/标注 -> 字层.
//  - FX 组为自动态 (缺省) 且放不下时先自动折叠 FX, 再自动折叠字层, 最后才按档压.
//  - 有富余: 密度到 80 -> 波形到 64 -> 其余普通轨各自最多 +50% -> 剩下才留在底部.
const ELASTIC = ['density', 'wave'];
const DENSITY_MAX = 80;
const WAVE_MAX = 64;
const FXWIN_MIN = 52; // 滚动窗口至少露出两条 FX
type BRow = { id: string; name: string; h: number; min: number; fixed: boolean; def?: TrackDef; group?: 'text' | 'fx'; members?: string[] };
export interface FxWin { y: number; h: number; content: number; scroll: number; max: number }
function buildRows(trackH: Record<string, number>, col: Record<string, boolean>): BRow[] {
  const rows: BRow[] = [];
  const seen = new Set<string>();
  for (const t of TRACKS) {
    if (t.group && col[t.group]) {
      if (seen.has(t.group)) continue;
      seen.add(t.group);
      const members = TRACKS.filter((x) => x.group === t.group).map((x) => x.id);
      rows.push({ id: `g:${t.group}`, name: GROUP_NAME[t.group], h: trackH[`g:${t.group}`] ?? 20, min: 10, fixed: false, group: t.group, members });
      continue;
    }
    rows.push({ id: t.id, name: t.name, h: trackH[t.id] ?? t.def, min: t.min, fixed: !!t.fixed, def: t, group: t.group });
  }
  return rows;
}
const isFx = (r: { group?: string; members?: string[] }) => r.group === 'fx' && !r.members;
/** 不压任何非弹性轨时需要的高度 (密度/波形取最小); fxScroll 时 FX 只算最小窗口. */
function need(trackH: Record<string, number>, col: Record<string, boolean>, fxScroll: boolean): number {
  const rows = buildRows(trackH, col);
  const fx = rows.filter(isFx).reduce((a, r) => a + r.h, 0);
  const rest = rows.filter((r) => !isFx(r)).reduce((a, r) => a + (ELASTIC.includes(r.id) && trackH[r.id] == null ? r.min : r.h), 0);
  return rest + (fxScroll ? Math.min(fx, FXWIN_MIN) : fx);
}
export function layoutRows(H: number, trackH: Record<string, number>, collapsed: Record<string, boolean>, fxScrollTop = 0): { rows: Row[]; win: FxWin | null } {
  let col = { ...collapsed };
  const auto = new Set<string>();
  const fxOpen = () => !col.fx; // 展开 (明确或自动态未折叠)
  for (const g of ['fx', 'text'] as const) {
    if (need(trackH, col, col.fx === false) <= H) break;
    if (col[g] === undefined) { col = { ...col, [g]: true }; auto.add(g); }
  }
  const rows = buildRows(trackH, col);
  const userSized = (id: string) => trackH[id] != null;
  const scrollable = fxOpen() && col.fx === false; // 只有用户明确展开的 FX 才开滚动窗口
  const fxContent = rows.filter(isFx).reduce((a, r) => a + r.h, 0);
  // 参与总高计算时, 可滚动的 FX 先按最小窗口算
  const hOf = (r: BRow) => (scrollable && isFx(r) ? 0 : r.h);
  const fxBase = scrollable ? Math.min(fxContent, FXWIN_MIN) : 0;
  const sum = () => rows.reduce((a, r) => a + hOf(r), 0) + fxBase;
  const TIERS: ((r: BRow) => boolean)[] = [
    (r) => ELASTIC.includes(r.id),
    (r) => ['mv', 'beat', 'card', 'review', 'g:text', 'g:fx'].includes(r.id),
    (r) => r.group === 'text' && !r.members,
    (r) => !scrollable && isFx(r),
    () => true, // 最后才动用户亲手拖过高度的轨
  ];
  // 第 0 档 (密度/波形) 为 FX 全部内容让路; 后面各档只为保住 FX 最小窗口才压
  let deficit = sum() - fxBase + fxContent * (scrollable ? 1 : 0) - H;
  for (let ti = 0; ti < TIERS.length && deficit > 0; ti++) {
    if (ti === 1) deficit = sum() - H;
    if (deficit <= 0) break;
    const last = ti === TIERS.length - 1;
    const tier = rows.filter((r) => !r.fixed && !(scrollable && isFx(r)) && (last ? userSized(r.id) : !userSized(r.id) && TIERS[ti](r)));
    const avail = tier.reduce((a, r) => a + (r.h - r.min), 0);
    if (avail <= 0) continue;
    const k = Math.min(1, deficit / avail);
    for (const r of tier) r.h = Math.max(r.min, Math.floor(r.h - (r.h - r.min) * k));
    deficit = sum() - (ti === 0 ? fxBase - fxContent * (scrollable ? 1 : 0) : 0) - H;
  }
  deficit = sum() - H;
  let winH = 0;
  if (scrollable) {
    // 窗口 = 其余轨之外的全部高度, 但不超过 FX 内容高
    winH = Math.max(Math.min(fxContent, FXWIN_MIN), Math.min(fxContent, fxBase - deficit));
    deficit = sum() - fxBase + winH - H;
  }
  if (deficit < 0) {
    let spare = -deficit;
    const grow = (r: BRow | undefined, cap: number) => {
      if (!r || userSized(r.id) || spare <= 0) return;
      const add = Math.min(spare, Math.max(0, cap - r.h)); r.h += add; spare -= add;
    };
    grow(rows.find((r) => r.id === 'density'), DENSITY_MAX);
    grow(rows.find((r) => r.id === 'wave'), WAVE_MAX);
    const plain = rows.filter((r) => !r.fixed && !r.members && !isFx(r) && !ELASTIC.includes(r.id) && !userSized(r.id) && r.def);
    while (spare > 0 && plain.some((r) => r.h < Math.round(r.def!.def * 1.5))) {
      for (const r of plain) { if (spare <= 0) break; if (r.h < Math.round(r.def!.def * 1.5)) { r.h += 1; spare -= 1; } }
    }
  }
  // 摆放: FX 滚动窗口内的行给出可见几何 (与窗口求交), 另带内容坐标 vy
  const out: Row[] = [];
  let y = 0;
  let win: FxWin | null = null;
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    const base = { id: r.id, name: r.name, def: r.def, group: r.group, members: r.members, auto: r.members ? auto.has(r.group!) : false };
    if (scrollable && isFx(r)) {
      if (!win) {
        const max = Math.max(0, fxContent - winH);
        win = { y, h: winH, content: fxContent, scroll: Math.max(0, Math.min(max, fxScrollTop)), max };
      }
      let vy = win.y - win.scroll;
      for (const q of rows.slice(rows.indexOf(rows.find(isFx)!), i)) vy += q.h;
      const top = Math.max(vy, win.y), bot = Math.min(vy + r.h, win.y + win.h);
      out.push({ ...base, y: top, h: Math.max(0, bot - top), vy, vh: r.h });
      if (!isFx(rows[i + 1] ?? {})) y = win.y + win.h;
      continue;
    }
    out.push({ ...base, y, h: r.h });
    y += r.h;
  }
  return { rows: out, win };
}

function niceStep(secPerPx: number): number {
  const target = secPerPx * 90;
  for (const st of [0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120]) if (st >= target) return st;
  return 300;
}

const EyeIcon = ({ on }: { on: boolean }) => (
  <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden><path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z" fill="none" stroke="currentColor" strokeWidth="1.4" />
    {on ? <circle cx="8" cy="8" r="2.2" fill="currentColor" /> : <path d="M2 14L14 2" stroke="currentColor" strokeWidth="1.4" />}</svg>
);
const LockIcon = ({ on }: { on: boolean }) => (
  <svg width="11" height="12" viewBox="0 0 14 16" aria-hidden><rect x="2" y="7" width="10" height="8" rx="1.5" fill={on ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.3" />
    <path d={on ? 'M4.5 7V5a2.5 2.5 0 015 0v2' : 'M4.5 7V5a2.5 2.5 0 015 0'} fill="none" stroke="currentColor" strokeWidth="1.3" /></svg>
);

/*
 * Agent Notes: 轨头眼睛按钮只渲染给 hasEye() 的轨
 * .agents/notes/implemented/feature/2026-11-11-karaoke-studio-track-visibility.md
 */
export default function Timeline() {
  const wrap = useRef<HTMLDivElement>(null);
  const cvS = useRef<HTMLCanvasElement>(null);
  const cvD = useRef<HTMLCanvasElement>(null);
  const lane = useRef<HTMLDivElement>(null);
  const S = useHiDpiCanvas(cvS);
  const D = useHiDpiCanvas(cvD);
  const box = useSize(wrap);
  const lines = useStore((x) => x.lines);
  const out = useStore((x) => x.out);
  const ref = useStore((x) => x.ref);
  const peaks = useStore((x) => x.peaks);
  const edl = useStore((x) => x.edl);
  const clips = useStore((x) => x.clips);
  const beats = useStore((x) => x.beats);
  const dur = useStore((x) => x.duration);
  const view = useStore((x) => x.view);
  const vis = useStore((x) => x.vis);
  const trackH = useStore((x) => x.trackH);
  const collapsed = useStore((x) => x.collapsed);
  const explain = useStore((x) => x.explain);
  const hoverLine = useStore((x) => x.hoverLine);
  const loop = useStore((x) => x.loop);
  const reviews = useStore((x) => x.reviews);
  const set = useStore((x) => x.set);
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);

  const [fxScroll, setFxScroll] = useState(0);
  const { rows, win } = useMemo(() => layoutRows(S.h || box.h, trackH, collapsed, fxScroll), [S.h, box.h, trackH, collapsed, fxScroll]);
  const winRef = useRef(win);
  winRef.current = win;
  const scrollFx = useCallback((d: number) => { const w = winRef.current; if (w) setFxScroll(Math.max(0, Math.min(w.max, w.scroll + d))); }, []);
  const R = useMemo(() => Object.fromEntries(rows.map((r) => [r.id, r])), [rows]);
  const byTrack = useMemo(() => {
    const m: Record<string, Clip[]> = {};
    for (const c of clips) (m[c.track] ||= []).push(c);
    return m;
  }, [clips]);
  const rowClips = useCallback((r: Row): Clip[] => (r.members ? r.members.flatMap((id) => byTrack[id] || []) : byTrack[r.id] || []), [byTrack]);
  const lineIdx = useMemo(() => new Map(lines.map((l, i) => [l.name, i])), [lines]);

  const W = S.w;
  const x2t = useCallback((x: number) => view.v0 + (x / Math.max(1, W)) * (view.v1 - view.v0), [view, W]);
  const t2x = useCallback((t: number) => ((t - view.v0) / (view.v1 - view.v0)) * W, [view, W]);

  // ---- 静态层
  useEffect(() => {
    const c = cvS.current;
    if (!c || !S.w) return;
    const g = c.getContext('2d')!;
    const { dpr } = S;
    const px = (v: number) => Math.round(v * dpr) / dpr;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, S.w, S.h);
    rows.forEach((tr, i) => {
      if (tr.h <= 0) return;
      g.fillStyle = i % 2 ? '#14161b' : '#171a20';
      g.fillRect(0, tr.y, S.w, tr.h);
      g.fillStyle = '#262a33';
      g.fillRect(0, Math.round((tr.y + tr.h) * dpr - 1) / dpr, S.w, 1 / dpr);
    });
    const full = dur || 1;
    const dim = (id: string) => { g.globalAlpha = (vis[id]?.eye ?? true) ? 1 : 0.18; };
    // 全曲缩略条 + 视野框
    const ov = R.overview;
    for (const l of lines) {
      g.fillStyle = ROLE[l.role ?? 'rest'] ?? '#5b6474';
      g.fillRect((l.t[0] / full) * S.w, ov.y + 3, Math.max(1, ((l.t[1] - l.t[0]) / full) * S.w), ov.h - 6);
    }
    g.strokeStyle = '#6ea8ff';
    g.lineWidth = 1 / dpr;
    g.strokeRect(crisp((view.v0 / full) * S.w, dpr), crisp(ov.y + 1, dpr), Math.max(2, ((view.v1 - view.v0) / full) * S.w - 1 / dpr), ov.h - 2);
    // 刻度
    const ru = R.ruler;
    const st = niceStep((view.v1 - view.v0) / S.w);
    g.fillStyle = '#4a5160';
    for (let t = Math.ceil(view.v0 / st) * st; t <= view.v1; t += st) {
      const x = crisp(t2x(t), dpr);
      g.fillRect(x - 0.5 / dpr, ru.y + ru.h - 8, 1 / dpr, 8);
      for (let k = 1; k < 4; k++) g.fillRect(crisp(t2x(t + (st * k) / 4), dpr) - 0.5 / dpr, ru.y + ru.h - 4, 1 / dpr, 4);
    }
    // MV
    if (R.mv) {
      dim('mv');
      const mv = R.mv;
      for (const sg of edl?.segments ?? []) {
        const a = t2x(sg.t0), b = t2x(sg.t1 ?? Math.min(full, sg.t0 + 87));
        g.fillStyle = sg.kind === 'orig' ? '#3b7a5a' : sg.kind === 'reuse' ? '#7a6a3b' : '#4a4f5c';
        g.fillRect(px(a), mv.y + 2, Math.max(1, px(b - a)), mv.h - 4);
      }
      g.globalAlpha = 1;
    }
    // 波形
    const wv = R.wave;
    if (wv && peaks && peaks.peaks.length) {
      g.globalAlpha = 1; // wave 没有眼睛 (对画面无作用), 旧 localStorage 里的 eye:false 也不许把它变暗
      const mid = wv.y + wv.h / 2;
      g.fillStyle = '#4f7fb8';
      const pw = 1 / dpr;
      for (let x = 0; x < S.w; x += pw) {
        const i0 = Math.max(0, Math.floor(x2t(x) * peaks.rate));
        const i1 = Math.min(peaks.peaks.length, Math.max(i0 + 1, Math.ceil(x2t(x + pw) * peaks.rate)));
        let m = 0;
        for (let i = i0; i < i1; i++) if (peaks.peaks[i] > m) m = peaks.peaks[i];
        const hh = m * (wv.h / 2 - 2);
        if (hh > 0) g.fillRect(x, mid - hh, pw, hh * 2);
      }
      g.globalAlpha = 1;
    }
    // 节拍: 拍线 (每 4 拍一小节加粗) + 起音点 (强度 -> 透明度)
    const bt = R.beat;
    if (bt && beats) {
      g.globalAlpha = 1; // beat 没有眼睛 (对画面无作用), 旧 localStorage 里的 eye:false 也不许把它变暗
      const secPerPx = (view.v1 - view.v0) / S.w;
      const every = secPerPx * 6 > 0.2 ? 4 : 1;
      beats.grid.forEach((t, i) => {
        if (t < view.v0 || t > view.v1 || i % every) return;
        g.fillStyle = i % 4 === 0 ? '#59606e' : '#3a404c';
        g.fillRect(crisp(t2x(t), dpr) - 0.5 / dpr, bt.y + (i % 4 === 0 ? 1 : bt.h / 2), 1 / dpr, i % 4 === 0 ? bt.h - 2 : bt.h / 2 - 1);
      });
      for (const t of beats.onset) {
        if (t < view.v0 || t > view.v1) continue;
        const sv = beats.strength[String(t)] ?? 0.5;
        g.fillStyle = `rgba(240,184,90,${0.25 + sv * 0.75})`;
        g.fillRect(px(t2x(t)) - 1, bt.y + bt.h / 2 - 1.5, 2, 3);
      }
      g.globalAlpha = 1;
    }
    // 片段轨
    for (const r of rows) {
      if (!(r.def?.filter || r.members)) continue;
      const cs = rowClips(r);
      const id = r.members ? r.members[0] : r.id;
      g.globalAlpha = r.members ? (r.members.some((m) => visible(vis, m)) ? 1 : 0.18) : visible(vis, id) ? 1 : 0.18;
      for (const cl of cs) {
        const a = t2x(cl.t0), b = t2x(cl.t1);
        if (b < 0 || a > S.w) continue;
        g.fillStyle = TRACK_COLOR[cl.track] ?? '#5b6474';
        const pad = r.h > 10 ? 2 : 1;
        if (r.h <= pad * 2) continue;
        // 滚动窗口边缘只露出一部分的 FX 行: 按内容坐标算出 clip 的上下边, 再与可见区求交 (而不是把整条压扁)
        if (r.vy != null) {
          const top = Math.max(r.y, r.vy + pad), bot = Math.min(r.y + r.h, r.vy + (r.vh ?? r.h) - pad);
          if (bot > top) g.fillRect(px(a), top, Math.max(1, px(b - a) - 1 / dpr), bot - top);
          continue;
        }
        g.fillRect(px(a), r.y + pad, Math.max(1, px(b - a) - 1 / dpr), r.h - pad * 2);
      }
      if (vis[id]?.lock && !r.members) {
        g.fillStyle = 'rgba(0,0,0,0.35)';
        for (let x = 0; x < S.w; x += 8) g.fillRect(x, r.y, 4, r.h);
      }
      g.globalAlpha = 1;
    }
    // 标注轨: 每条 review 一段, 按类型着色; 同一时刻多条时按类型分上下四格
    const rv = R.review;
    if (rv) {
      const kinds: Review['kind'][] = ['bad', 'good', 'redo', 'note'];
      const lh = Math.max(2, (rv.h - 2) / 4);
      for (const it of reviews) {
        const a = t2x(it.t0), b = t2x(it.t1);
        if (b < 0 || a > S.w) continue;
        const k = kinds.indexOf(it.kind);
        g.fillStyle = REVIEW_KIND[it.kind]?.c ?? '#888';
        g.fillRect(px(a), rv.y + 1 + Math.max(0, k) * lh, Math.max(2, px(b - a)), Math.max(1, lh - 1));
      }
    }
    // 密度: out 面积 + 参考虚线 (同口径 100ms)
    const de = R.density;
    const curve = (r: typeof out) => r ? { c: r.profile.alive_curve, t0: r.profile.span[0], st: r.step } : null;
    const o = curve(out);
    const rf = curve(ref);
    const mx = Math.max(1, ...(o ? o.c : [1]), ...(rf ? rf.c : [1]));
    const yOf = (v: number) => de.y + de.h - 2 - (v / mx) * (de.h - 6);
    const val = (cv: NonNullable<ReturnType<typeof curve>>, t: number) => {
      const i = Math.floor((t - cv.t0) / cv.st);
      return i >= 0 && i < cv.c.length ? cv.c[i] : 0;
    };
    g.globalAlpha = 1; // density 没有眼睛 (对画面无作用), 旧 localStorage 里的 eye:false 也不许把它变暗
    if (o) {
      g.beginPath();
      g.moveTo(0, yOf(0));
      for (let x = 0; x <= S.w; x += 1) g.lineTo(x, yOf(val(o, x2t(x))));
      g.lineTo(S.w, yOf(0));
      g.closePath();
      g.fillStyle = 'rgba(110,168,255,0.35)';
      g.fill();
    }
    if (rf) {
      g.beginPath();
      for (let x = 0; x <= S.w; x += 1) { const y = yOf(val(rf, x2t(x))); if (x === 0) g.moveTo(x, y); else g.lineTo(x, y); }
      g.setLineDash([4, 3]);
      g.strokeStyle = '#f0a24a';
      g.lineWidth = 1;
      g.stroke();
      g.setLineDash([]);
    }
    g.globalAlpha = 1;
  }, [S, rows, R, lines, out, ref, peaks, edl, beats, vis, rowClips, dur, view, t2x, x2t, reviews]);

  // ---- 动态层: 选区 (涉及轨加亮) + 浏览悬停句 + 循环区 + 播放头 + 悬停线
  const drawDyn = useCallback((t: number) => {
    const c = cvD.current;
    if (!c || !D.w) return;
    const g = c.getContext('2d')!;
    const { dpr } = D;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, D.w, D.h);
    const st = useStore.getState();
    const top = R.ruler ? R.ruler.y + R.ruler.h : 0;
    for (const it of st.explain || []) {
      const a = t2x(it.t0), b = t2x(it.t1);
      g.fillStyle = 'rgba(110,168,255,0.12)';
      g.fillRect(a, top, Math.max(1, b - a), D.h - top);
      g.fillStyle = 'rgba(110,168,255,0.35)';
      for (const r of rows) {
        const ids = r.members ?? [r.id];
        if (ids.some((id) => (it.counts[id] ?? 0) > 0)) g.fillRect(a, r.y, Math.max(1, b - a), r.h);
      }
      g.strokeStyle = '#6ea8ff';
      g.lineWidth = 1 / dpr;
      g.strokeRect(crisp(a, dpr), top + 0.5, Math.max(1, b - a), D.h - top - 1);
    }
    if (st.hoverLine != null && st.lines[st.hoverLine]) {
      const L = st.lines[st.hoverLine];
      const a = t2x(L.t[0]), b = t2x(L.t[1]);
      g.fillStyle = 'rgba(240,184,90,0.16)';
      g.fillRect(a, top, Math.max(1, b - a), D.h - top);
      g.fillStyle = '#f0b85a';
      g.fillRect(a, top, Math.max(1, b - a), 2);
    }
    if (st.loop && R.ruler) {
      g.fillStyle = 'rgba(89,195,138,0.8)';
      g.fillRect(t2x(st.loop.t0), R.ruler.y + 1, Math.max(2, t2x(st.loop.t1) - t2x(st.loop.t0)), 4);
    }
    if (st.hover != null) {
      g.fillStyle = 'rgba(255,255,255,0.25)';
      g.fillRect(crisp(t2x(st.hover), dpr) - 0.5 / dpr, 0, 1 / dpr, D.h);
    }
    const x = crisp(t2x(t), dpr);
    g.fillStyle = '#ff5d5d';
    g.fillRect(x - 0.5 / dpr, 0, Math.max(1, Math.round(dpr)) / dpr, D.h);
    const full = dur || 1;
    if (R.overview) g.fillRect(crisp((t / full) * D.w, dpr) - 0.5 / dpr, R.overview.y, 1 / dpr, R.overview.h);
  }, [D, t2x, dur, R, rows]);
  useEffect(() => clock.subscribe(drawDyn), [drawDyn]);
  useEffect(() => { drawDyn(clock.t()); }, [drawDyn, explain, hoverLine, loop]);
  useEffect(() => useStore.subscribe((st, pv) => { if (st.hover !== pv.hover) drawDyn(clock.t()); }), [drawDyn]);

  // 播放时跟随: 播放头出视野则翻页
  useEffect(() => clock.subscribe((t) => {
    const v = useStore.getState().view;
    if (clock.playing && (t > v.v1 || t < v.v0)) {
      const w = v.v1 - v.v0;
      set({ view: { v0: Math.max(0, t - w * 0.1), v1: Math.max(0, t - w * 0.1) + w } });
    }
  }), [set]);

  // ---- 交互
  const clampView = useCallback((v0: number, v1: number) => {
    const full = dur || 1;
    let w = Math.max(0.5, Math.min(full, v1 - v0));
    let a = Math.max(0, Math.min(full - w, v0));
    if (!Number.isFinite(a)) { a = 0; w = full; }
    return { v0: a, v1: a + w };
  }, [dur]);
  useEffect(() => {
    const el = lane.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const v = useStore.getState().view;
      const rect = el.getBoundingClientRect();
      // Alt+滚轮 在 FX 滚动窗口里 = 纵向滚动 FX (轨头列上普通滚轮也是)
      const w = winRef.current;
      const yy = e.clientY - rect.top;
      if (e.altKey && w && yy >= w.y && yy < w.y + w.h) { scrollFx(e.deltaY); return; }
      const tAt = v.v0 + ((e.clientX - rect.left) / rect.width) * (v.v1 - v.v0);
      // 普通滚轮 = 以指针处为中心缩放; Shift+滚轮 或 触控板横向 = 平移 (Ctrl+滚轮同样缩放, 兼容老习惯)
      const pan = e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY);
      if (!pan) {
        const k = Math.exp(e.deltaY * 0.0015);
        set({ view: clampView(tAt - (tAt - v.v0) * k, tAt + (v.v1 - tAt) * k) });
      } else {
        const dd = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
        const d = (dd / rect.width) * (v.v1 - v.v0);
        set({ view: clampView(v.v0 + d, v.v1 + d) });
      }
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [clampView, set, scrollFx]);

  const rowAt = (y: number) => rows.find((r) => y >= r.y && y < r.y + r.h);
  const clipAt = (r: Row | undefined, t: number): Clip | null => {
    if (!r || !(r.def?.filter || r.members)) return null;
    const cs = rowClips(r).filter((c) => t >= c.t0 && t <= c.t1);
    return cs.sort((a, b) => (a.t1 - a.t0) - (b.t1 - b.t0))[0] ?? null;
  };
  const lockedRow = (r: Row | undefined) => !!r && !r.members && !!vis[r.id]?.lock;

  const onDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    const el = lane.current!;
    const rect = el.getBoundingClientRect();
    const y = e.clientY - rect.top;
    const rvHit = reviewAt(rowAt(y), x2t(e.clientX - rect.left), y);
    if (rvHit) { selectReview(rvHit); return; }
    const full = dur || 1;
    const inOv = y < R.overview.y + R.overview.h;
    const at = (cx: number) => {
      const x = cx - rect.left;
      if (inOv) {
        const v = useStore.getState().view;
        const w = v.v1 - v.v0;
        const c = (x / rect.width) * full;
        set({ view: clampView(c - w / 2, c + w / 2) });
      } else clock.seek(x2t(x));
    };
    el.setPointerCapture(e.pointerId);
    at(e.clientX);
    const mv = (m: PointerEvent) => at(m.clientX);
    const up = () => { el.removeEventListener('pointermove', mv); el.removeEventListener('pointerup', up); };
    el.addEventListener('pointermove', mv);
    el.addEventListener('pointerup', up);
  };
  const onMove = (e: React.PointerEvent) => {
    const rect = lane.current!.getBoundingClientRect();
    const t = x2t(e.clientX - rect.left);
    set({ hover: t });
    const r = rowAt(e.clientY - rect.top);
    const rvh = reviewAt(r, t, e.clientY - rect.top);
    if (rvh) { setTip({ x: e.clientX - rect.left + 12, y: e.clientY - rect.top + 12, text: reviewText(rvh) }); return; }
    const cl = clipAt(r, t);
    if (cl) {
      const fns = cl.fns.filter(([f]) => f !== '?').map(([f, n]) => `${f.includes(':') ? f.split(':').slice(1).join(':') : f}×${n}`).join(', ');
      setTip({ x: e.clientX - rect.left + 12, y: e.clientY - rect.top + 12, text: `${cl.unit} · ${cl.track} · ${cl.n} 条 · 层 ${cl.layers.join(',')}${fns ? ` · ${fns}` : ''}` });
    } else setTip(null);
  };
  const reviewAt = (r: Row | undefined, t: number, y: number): Review | null => {
    if (!r || r.id !== 'review') return null;
    const tol = ((view.v1 - view.v0) / Math.max(1, W)) * 3; // 3px 容差, 窄标注也点得中
    const hit = reviews.filter((it) => t >= it.t0 - tol && t <= it.t1 + tol);
    // 标注轨按类型分上下四格 (与绘制同口径): 优先取指针所在那一格的类型, 那一格没有才退回同一时刻的其它标注
    const lh = Math.max(2, (r.h - 2) / 4);
    const kind = (['bad', 'good', 'redo', 'note'] as const)[Math.max(0, Math.min(3, Math.floor((y - r.y - 1) / lh)))];
    const byLen = (a: Review, b: Review) => (a.t1 - a.t0) - (b.t1 - b.t0);
    return hit.filter((it) => it.kind === kind).sort(byLen)[0] ?? hit.sort(byLen)[0] ?? null;
  };
  const reviewText = (it: Review) => {
    const n = it.sel.reduce((a, sr) => a + sr.to - sr.from + 1, 0);
    const where = it.sel.map((sr) => `L${String(sr.line).padStart(2, '0')}`).filter((v, i, a) => a.indexOf(v) === i).join('-');
    const body = [it.tags.join(' / '), it.text].filter(Boolean).join(' · ');
    return `${REVIEW_KIND[it.kind]?.cn ?? it.kind} · ${where} ${n} 字 · ${it.t0.toFixed(2)}-${it.t1.toFixed(2)}s${body ? ` · ${body}` : ''}`;
  };
  const selectReview = (it: Review) => {
    const st = useStore.getState();
    const li = new Map(st.lines.map((l, i) => [l.line ?? i, i]));
    const rs: [number, number][] = [];
    for (const sr of it.sel) { const i = li.get(sr.line); if (i != null) rs.push([st.ix.start[i] + sr.from, st.ix.start[i] + sr.to]); }
    if (rs.length) setSelection(rs, rs[0][0], rs[0][0]);
    clock.seek(it.t0 + 0.001);
  };
  const lineOfClip = (cl: Clip | null) => (cl ? lineIdx.get(cl.unit) : undefined);
  const onDbl = (e: React.MouseEvent) => {
    const rect = lane.current!.getBoundingClientRect();
    const r = rowAt(e.clientY - rect.top);
    if (lockedRow(r)) { toast('轨已锁定'); return; }
    const li = lineOfClip(clipAt(r, x2t(e.clientX - rect.left)));
    if (li == null) return;
    selectLine(li);
    loopSelection(1);
  };
  const onCtx = (e: React.MouseEvent) => {
    e.preventDefault();
    const rect = lane.current!.getBoundingClientRect();
    const r = rowAt(e.clientY - rect.top);
    if (lockedRow(r)) { toast('轨已锁定, 不能在锁定轨上选取'); return; }
    const t = x2t(e.clientX - rect.left);
    let li = lineOfClip(clipAt(r, t));
    if (li == null) { const l = lines.findIndex((L) => t >= L.t[0] && t < L.t[1]); if (l >= 0 && r && (r.def?.filter || r.members)) li = l; }
    if (li != null) selectLine(li);
    set({ menu: { x: e.clientX, y: e.clientY, source: 'timeline' } });
  };

  // ---- 轨头
  const toggle = (id: string, k: 'eye' | 'solo' | 'lock', ids?: string[]) => {
    const v = { ...useStore.getState().vis };
    const list = ids ?? [id];
    const on = !list.every((x) => v[x]?.[k]);
    if (k === 'eye' && ids) for (const x of list) v[x] = { ...v[x], eye: !list.every((y) => v[y]?.eye) };
    else for (const x of list) v[x] = { ...v[x], [k]: on };
    set({ vis: v });
  };
  const startResize = (e: React.PointerEvent, r: Row) => {
    e.stopPropagation();
    e.preventDefault();
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    const y0 = e.clientY, h0 = r.h;
    const min = r.def?.min ?? 10;
    const mv = (m: PointerEvent) => set({ trackH: { ...useStore.getState().trackH, [r.id]: Math.max(min, Math.min(160, Math.round(h0 + m.clientY - y0))) } });
    const up = () => { el.removeEventListener('pointermove', mv); el.removeEventListener('pointerup', up); };
    el.addEventListener('pointermove', mv);
    el.addEventListener('pointerup', up);
  };

  // ---- DOM 文字层
  const ticks = useMemo(() => {
    if (!W) return [];
    const st = niceStep((view.v1 - view.v0) / W);
    const r: { x: number; s: string }[] = [];
    for (let t = Math.ceil(view.v0 / st) * st; t <= view.v1; t += st) r.push({ x: t2x(t), s: fmtTime(t, st < 1) });
    return r;
  }, [view, W, t2x]);
  const labels = useMemo(() => {
    const out: { key: string; x: number; y: number; w: number; text: string }[] = [];
    for (const r of rows) {
      if (!r.def?.filter || r.members || (r.vh ?? r.h) < 13 || r.h <= 0) continue; // 折叠组行里 9 层叠在一起, 不画逐段文字 (会互相压)
      for (const cl of rowClips(r)) {
        const a = t2x(cl.t0), b = t2x(cl.t1);
        if (b - a < 30 || b < 0 || a > W) continue;
        const ly = r.vy != null ? r.vy + ((r.vh ?? r.h) - 12) / 2 : r.y + (r.h - 12) / 2;
        if (r.vy != null && (ly < r.y || ly + 12 > r.y + r.h)) continue; // 窗口边缘露不全的字不画
        out.push({ key: `${r.id}${cl.track}${cl.unit}`, x: Math.max(0, a) + 3, y: ly, w: b - Math.max(0, a) - 5, text: b - a > 70 ? `${cl.unit} ${cl.n}` : cl.unit });
      }
    }
    return out;
  }, [rows, rowClips, t2x, W]);

  const groupSpans = useMemo(() => {
    const g: { group: 'text' | 'fx'; y: number; h: number; collapsed: boolean; auto: boolean }[] = [];
    for (const grp of ['text', 'fx'] as const) {
      const rs = rows.filter((r) => r.group === grp);
      if (!rs.length) continue;
      g.push({ group: grp, y: rs[0].y, h: rs[rs.length - 1].y + rs[rs.length - 1].h - rs[0].y, collapsed: !!rs[0].members, auto: !!rs[0].auto });
    }
    return g;
  }, [rows]);

  return (
    <section className={s.tl} ref={wrap} data-testid="timeline" data-hover-line={hoverLine ?? ''}
      data-sel={explain ? JSON.stringify(explain.map((it) => [it.t0, it.t1, Object.keys(it.counts)])) : ''}
      data-view={`${view.v0.toFixed(3)},${view.v1.toFixed(3)}`}
      data-rows={rows.map((r) => `${r.id}:${r.y}:${r.h}`).join(' ')}
      data-fxwin={win ? `${win.y}:${win.h}:${win.content}:${win.scroll}` : ''}
      data-fxrows={rows.filter((r) => r.group === 'fx' && !r.members).map((r) => `${r.id}:${r.vh ?? r.h}`).join(' ')}>
      <div className={s.heads} style={{ width: HEAD_W }} data-testid="tl-heads">
        {groupSpans.map((gs) => (
          <button key={gs.group} className={s.grp} style={{ top: gs.y, height: gs.h }} data-testid={`group-${gs.group}`}
            data-collapsed={gs.collapsed || undefined} title={`${GROUP_NAME[gs.group]}: ${gs.collapsed ? '展开' : '折叠'}${gs.auto ? ' (高度不够, 已自动折叠)' : ''}`}
            onClick={() => set({ collapsed: { ...collapsed, [gs.group]: !gs.collapsed } })}>{gs.collapsed ? '▸' : '▾'}</button>
        ))}
        {(() => {
          const head = (r: Row, top: number, h: number) => {
          const ids = r.members ?? [r.id];
          const eye = ids.every((x) => vis[x]?.eye ?? true);
          const solo = ids.every((x) => vis[x]?.solo);
          const lock = ids.every((x) => vis[x]?.lock);
          const filt = !!(r.def?.filter || r.members);
          const small = h < 13;
          return (
            <div key={r.id} className={s.head} style={{ top, height: h, paddingLeft: r.group ? 16 : 8 }} data-track={r.id} data-small={small || undefined}>
              {r.members
                ? <span className={s.hname} data-testid={`group-head-${r.group}`} style={{ cursor: 'pointer' }} title={`${GROUP_NAME[r.group!]}: 点击展开${r.auto ? ' (高度不够, 已自动折叠)' : ''}`}
                    onClick={() => set({ collapsed: { ...collapsed, [r.group!]: false } })}>▸ {r.group === 'fx' ? 'FX 0-8' : '字层'}</span>
                : <span className={s.hname} title={r.def?.title ?? r.name}>{r.name}</span>}
              {r.id !== 'overview' && (
                <span className={s.btns}>
                  {(filt || hasEye(r.def)) && <button data-act="eye" aria-pressed={eye} className={s.hb} title={r.id === 'mv' ? '显示视频 (关掉则监视器只画字幕)' : '显示'} onClick={() => toggle(r.id, 'eye', r.members)}><EyeIcon on={eye} /></button>}
                  {filt && <button data-act="solo" aria-pressed={solo} className={s.hb} data-on={solo || undefined} title="独显 (只在监视器渲染独显轨)" onClick={() => toggle(r.id, 'solo', r.members)}>S</button>}
                  {filt && <button data-act="lock" aria-pressed={lock} className={s.hb} data-on={lock || undefined} title="锁 (锁定轨上不能选取/右键)" onClick={() => toggle(r.id, 'lock', r.members)}><LockIcon on={lock} /></button>}
                </span>
              )}
              {!r.def?.fixed && r.id !== 'density' && <div className={s.rz} data-testid={`resize-${r.id}`} onPointerDown={(e) => startResize(e, r)} />}
            </div>
          );
          };
          const normal = rows.filter((r) => r.name && r.vy == null).map((r) => head(r, r.y, r.h));
          if (!win) return normal;
          return [...normal,
            <div key="fxwin" className={s.fxwin} style={{ top: win.y, height: win.h }} data-testid="fx-win-heads"
              onWheel={(e) => scrollFx(e.deltaY)}>
              {rows.filter((r) => r.vy != null).map((r) => head(r, r.vy! - win.y, r.vh ?? r.h))}
            </div>];
        })()}
      </div>
      <div className={s.lane} ref={lane} onPointerDown={onDown} onPointerMove={onMove} onDoubleClick={onDbl} onContextMenu={onCtx}
        onPointerLeave={() => { set({ hover: null }); setTip(null); }}>
        <canvas ref={cvS} className={s.cv} data-hidpi="timeline-static" />
        <canvas ref={cvD} className={s.cv} data-hidpi="timeline-dynamic" />
        <div className={s.text}>
          {R.ruler && ticks.map((k) => <span key={k.s + k.x} className={s.tick} style={{ left: k.x + 3, top: R.ruler.y + 2 }}>{k.s}</span>)}
          {rows.filter((r) => r.members).map((r) => (
            <button key={r.id} className={s.gpill} data-testid={`group-pill-${r.group}`} style={{ top: r.y + 1, height: r.h - 2 }}
              onPointerDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()} onContextMenu={(e) => e.stopPropagation()}
              onClick={() => set({ collapsed: { ...collapsed, [r.group!]: false } })}>▸ {GROUP_NAME[r.group!]}{r.auto ? ' · 高度不够已自动折叠' : ''} · 点击展开</button>
          ))}
          {win && win.max > 0 && (
            <div className={s.vbar} data-testid="fx-vbar" style={{ top: win.y + (win.scroll / win.content) * win.h, height: Math.max(16, (win.h * win.h) / win.content) }}
              onPointerDown={(e) => {
                e.stopPropagation();
                const el = e.currentTarget; el.setPointerCapture(e.pointerId);
                const y0 = e.clientY, s0 = win.scroll, k = win.content / win.h;
                const mv = (m: PointerEvent) => setFxScroll(Math.max(0, Math.min(win.max, s0 + (m.clientY - y0) * k)));
                const up = () => { el.removeEventListener('pointermove', mv); el.removeEventListener('pointerup', up); };
                el.addEventListener('pointermove', mv); el.addEventListener('pointerup', up);
              }} />
          )}
          {R.density && (
            <div className={s.legend} style={{ top: R.density.y + 2, left: 'auto', right: 8 }}>
              <i className={s.lo} /> out <i className={s.lr} /> 参考
            </div>
          )}
          {labels.map((l) => <span key={l.key} className={s.lab} style={{ left: l.x, top: l.y, maxWidth: l.w }}>{l.text}</span>)}
          {tip && <div className={s.tip} data-testid="clip-tip" style={{ left: Math.min(tip.x, W - 280), top: Math.min(tip.y, (S.h || 200) - 24) }}>{tip.text}</div>}
        </div>
      </div>
    </section>
  );
}
