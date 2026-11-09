import { useCallback, useEffect, useRef, useState } from 'react';
import { shortcut } from '../lib/actions';
import { api, watch } from '../lib/api';
import { clock } from '../lib/clock';
import { lineAt, useStore } from '../lib/store';
import { onPlacementChanged, refreshPlacement } from '../lib/placement';
import ContextMenu from './ContextMenu';
import Inspector from './Inspector';
import LyricsPanel from './LyricsPanel';
import Monitor from './Monitor';
import StatusBar from './StatusBar';
import Timeline from './Timeline';
import TopBar from './TopBar';
import Transport from './Transport';
import s from './App.module.css';

const LS_TL = 'hxstudio.tlH';
const LS_SIDE = 'hxstudio.sideW';

function useSplit(key: string, def: number, min: number, max: () => number, axis: 'x' | 'y', invert: boolean) {
  const [v, setV] = useState(() => Number(localStorage.getItem(key)) || def);
  const clamp = useCallback((x: number) => Math.max(min, Math.min(max(), x)), [min, max]);
  useEffect(() => {
    const onR = () => setV((x) => clamp(x));
    window.addEventListener('resize', onR);
    onR();
    return () => window.removeEventListener('resize', onR);
  }, [clamp]);
  const onDown = (e: React.PointerEvent) => {
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    const p0 = axis === 'x' ? e.clientX : e.clientY;
    const v0 = v;
    const move = (m: PointerEvent) => {
      const d = (axis === 'x' ? m.clientX : m.clientY) - p0;
      const nv = clamp(v0 + (invert ? -d : d));
      setV(nv);
      localStorage.setItem(key, String(Math.round(nv)));
    };
    const up = () => { el.removeEventListener('pointermove', move); el.removeEventListener('pointerup', up); };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', up);
  };
  return [v, onDown, (x: number) => setV(clamp(x))] as const;
}

/*
 * Agent Notes: studio 主界面网格
 * .agents/notes/implemented/feature/2026-11-09-karaoke-studio.md
 */
export default function App() {
  const set = useStore((x) => x.set);
  const inspector = useStore((x) => x.inspector);
  const toastMsg = useStore((x) => x.toast);
  const root = useRef<HTMLDivElement>(null);
  const maxTl = useCallback(() => Math.max(140, window.innerHeight - 36 - 24 - 220), []);
  const maxSide = useCallback(() => Math.max(260, Math.min(640, window.innerWidth * 0.45)), []);
  const [tlH, onTl] = useSplit(LS_TL, Math.round(window.innerHeight * 0.42), 120, maxTl, 'y', true);

  const [sideW, onSide] = useSplit(LS_SIDE, Math.round(Math.min(420, window.innerWidth * 0.26)), 240, maxSide, 'x', true);

  // 数据
  useEffect(() => {
    let live = true;
    (async () => {
      const p = await api.project();
      if (!live) return;
      clock.setSrc(p.audio[0]);
      set({ project: p, edl: p.edl, duration: p.duration, view: { v0: 0, v1: p.duration || 1 } });
      const [lines, out] = await Promise.all([api.lyrics(), api.profile('out')]);
      if (!live) return;
      set({ lines, out });
      api.profile('ref').then((ref) => live && set({ ref })).catch(() => undefined);
      api.peaks().then((peaks) => live && set({ peaks })).catch(() => undefined);
      api.clips().then((r) => live && set({ clips: r.clips, beats: r.beats })).catch(() => undefined);
      api.reviews().then((reviews) => live && set({ reviews })).catch(() => undefined);
      refreshPlacement().catch(() => undefined);
      document.body.dataset.ready = '1';
    })().catch((e) => { document.body.dataset.ready = 'error'; console.error(e); });
    const off = watch(async (what) => {
      if (what.includes('out') || what.includes('manifest')) {
        const [lines, out] = await Promise.all([api.lyrics(), api.profile('out')]);
        set({ lines, out, assRev: useStore.getState().assRev + 1 });
        api.clips().then((r) => set({ clips: r.clips, beats: r.beats })).catch(() => undefined);
      }
      if (what.includes('review')) set({ reviews: await api.reviews() });
      if (what.includes('edl')) set({ edl: await api.edl() });
      if (what.includes('job') || what.includes('placement')) await onPlacementChanged();
    });
    return () => { live = false; off(); };
  }, [set]);

  // 播放状态, 当前句, 播放选区到点停, 循环
  useEffect(() => {
    const a = clock.audio;
    const sync = () => set({ playing: !a.paused, duration: clock.duration || useStore.getState().duration });
    a.addEventListener('play', sync);
    a.addEventListener('pause', sync);
    a.addEventListener('loadedmetadata', sync);
    const off = clock.subscribe((t) => {
      const st = useStore.getState();
      const i = lineAt(st.lines, t);
      if (i !== st.curLine) set({ curLine: i });
      if (clock.playing && st.stopAt != null && t >= st.stopAt) { clock.pause(); clock.seek(st.stopAt); set({ stopAt: null }); }
      if (clock.playing && st.loop && (t >= st.loop.t1 || t < st.loop.t0 - 0.25)) clock.seek(st.loop.t0);
    });
    return () => { off(); a.removeEventListener('play', sync); a.removeEventListener('pause', sync); a.removeEventListener('loadedmetadata', sync); };
  }, [set]);

  // 键盘: 菜单快捷键 (Space/L/Shift+L/E/N/G/R/F/Ctrl+Shift+C) + Alt+左右逐帧/逐秒. 菜单打开时由菜单处理.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest('input,select,textarea')) return;
      if (useStore.getState().menu) return;
      if (e.key === 'ArrowLeft' && e.altKey) { e.preventDefault(); clock.seek(clock.t() - (e.shiftKey ? 1 : 1 / 24)); return; }
      if (e.key === 'ArrowRight' && e.altKey) { e.preventDefault(); clock.seek(clock.t() + (e.shiftKey ? 1 : 1 / 24)); return; }
      if (e.key === 'Escape' && useStore.getState().noteBox) { set({ noteBox: null }); return; }
      if (shortcut(e)) e.preventDefault();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [set]);

  return (
    <div ref={root} className={s.app} style={{ '--tl-h': `${tlH}px`, '--side-w': `${sideW}px` } as React.CSSProperties}>
      <TopBar />
      <div className={s.main}>
        <div className={s.upper}>
          <div className={s.monitorCol}>
            <Monitor />
            <Transport />
          </div>
          <div className={s.vsplit} onPointerDown={onSide} role="separator" aria-orientation="vertical" />
          <div className={s.side} data-ins={inspector || undefined}>
            <LyricsPanel />
            {inspector && <Inspector />}
          </div>
        </div>
        <div className={s.hsplit} onPointerDown={onTl} role="separator" aria-orientation="horizontal" />
        <Timeline />
      </div>
      <StatusBar />
      <ContextMenu />
      {toastMsg && <div className={s.toast} role="status" data-testid="toast">{toastMsg}</div>}
    </div>
  );
}
