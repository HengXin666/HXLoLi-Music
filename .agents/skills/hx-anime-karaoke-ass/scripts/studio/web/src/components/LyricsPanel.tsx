import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { ensureSelectedAt, selectLine, setSelection } from '../lib/actions';
import { clock } from '../lib/clock';
import { inRanges, norm, vertical, wordAt, type Range } from '../lib/sel';
import { useStore } from '../lib/store';
import s from './LyricsPanel.module.css';

/**
 * 滚动歌词面板 (plan 3.5, QQ 音乐式).
 * - 当前句放大居中, 逐字填色按 timing 的字时间走 (clock 订阅直接改 DOM, 不进 React)
 * - 跟随: 当前句中心平滑停在面板 40% 高度 (transform 动画, 不用 scrollTop)
 * - 滚轮/拖动进入浏览模式, 底部 "回到当前句" 胶囊; 3s 无操作或点胶囊恢复跟随
 * - 浏览模式悬停某句: 时间线同步高亮该句时段 (不动播放头)
 * - 选字: 单击/拖动/Shift/Ctrl 追加/双击词/三击或行号整句/方向键/Esc
 */
const ROLE_CN: Record<string, string> = { high: '高光', carrier: '承载', rest: '留白' };
const IDLE = 3000;

export default function LyricsPanel() {
  const lines = useStore((x) => x.lines);
  const staleErr = useStore((x) => x.syncErr.data);
  const offline = useStore((x) => x.live === 'down');
  const stale = !!staleErr || offline;
  const ix = useStore((x) => x.ix);
  const cur = useStore((x) => x.curLine);
  const ranges = useStore((x) => x.ranges);
  const caret = useStore((x) => x.caret);
  const reviews = useStore((x) => x.reviews);
  const set = useStore((x) => x.set);
  const vp = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  const [browse, setBrowse] = useState(false);
  const [off, setOff] = useState(0);
  const offRef = useRef(0);
  offRef.current = off;
  const idle = useRef(0);
  const drag = useRef<{ mode: 'sel' | 'add' | 'scroll'; anchor: number; y0: number; off0: number; moved: boolean } | null>(null);

  // ---- 跟随
  const follow = useCallback(() => {
    const v = vp.current, el = inner.current?.querySelector<HTMLElement>(`[data-i="${useStore.getState().curLine}"]`);
    if (!v || !el) return;
    setOff(el.offsetTop + el.offsetHeight / 2 - v.clientHeight * 0.4);
  }, []);
  useLayoutEffect(() => {
    if (browse) return;
    follow();
    const r = requestAnimationFrame(follow); // 当前句放大后再量一次
    return () => cancelAnimationFrame(r);
  }, [cur, browse, lines, follow]);
  useEffect(() => {
    const ro = new ResizeObserver(() => { if (!browse) follow(); });
    if (vp.current) ro.observe(vp.current);
    // 当前句字号有 0.25s 过渡, 行高在过渡中变化: 量内容高度, 变了就重新对准 40%
    if (inner.current) ro.observe(inner.current);
    return () => ro.disconnect();
  }, [browse, follow]);

  const enterBrowse = useCallback(() => {
    setBrowse(true);
    clearTimeout(idle.current);
    idle.current = window.setTimeout(() => { setBrowse(false); set({ hoverLine: null }); }, IDLE);
  }, [set]);
  const backToCurrent = () => { clearTimeout(idle.current); setBrowse(false); set({ hoverLine: null }); };
  useEffect(() => () => clearTimeout(idle.current), []);

  const clampOff = (o: number) => {
    const v = vp.current, i = inner.current;
    if (!v || !i) return o;
    return Math.max(-v.clientHeight * 0.4, Math.min(i.scrollHeight - v.clientHeight * 0.6, o));
  };
  useEffect(() => {
    const v = vp.current;
    if (!v) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      enterBrowse();
      setOff((o) => clampOff(o + e.deltaY));
    };
    v.addEventListener('wheel', onWheel, { passive: false });
    return () => v.removeEventListener('wheel', onWheel);
  }, [enterBrowse]);

  // ---- 逐字填色: 当前句每帧更新 --p (DOM 直改)
  useEffect(() => {
    let lastLine: HTMLElement | null = null;
    return clock.subscribe((t) => {
      const st = useStore.getState();
      const el = inner.current?.querySelector<HTMLElement>(`[data-i="${st.curLine}"]`) ?? null;
      if (lastLine && lastLine !== el) lastLine.querySelectorAll<HTMLElement>('[data-g]').forEach((c) => { c.style.removeProperty('--p'); delete c.dataset.on; });
      lastLine = el;
      if (!el) return;
      const L = st.lines[st.curLine];
      el.querySelectorAll<HTMLElement>('[data-g]').forEach((c) => {
        const ch = L.chars[Number(c.dataset.ci)];
        const p = Math.max(0, Math.min(1, (t - ch.s) / Math.max(0.01, ch.e - ch.s)));
        c.style.setProperty('--p', p.toFixed(3));
        if (p > 0) c.dataset.on = '1'; else delete c.dataset.on;
      });
    });
  }, [lines]);

  // ---- 批注下划线: 每字最新的 good/bad
  const rvMap = useMemo(() => {
    const m = new Map<number, 'good' | 'bad' | 'redo' | 'note'>();
    const li = new Map(lines.map((l, i) => [l.line ?? i, i]));
    for (const r of reviews) {
      for (const sr of r.sel) {
        const i = li.get(sr.line);
        if (i == null) continue;
        for (let c = sr.from; c <= sr.to; c++) m.set(ix.start[i] + c, r.kind);
      }
    }
    return m;
  }, [reviews, lines, ix]);

  const maxFx = useMemo(() => Math.max(1, ...lines.map((l) => Math.max(l.fx, l.ref_fx))), [lines]);

  // ---- 选字
  const gAt = (x: number, y: number): number | null => {
    const el = document.elementFromPoint(x, y)?.closest<HTMLElement>('[data-g]');
    return el ? Number(el.dataset.g) : null;
  };
  const seekChar = (g: number) => {
    const { li, ci } = ix.flat[g];
    clock.seek(lines[li].chars[ci].s + 0.001);
  };
  const onCharDown = (e: React.MouseEvent, g: number) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    vp.current?.focus({ preventScroll: true });
    const st = useStore.getState();
    if (e.detail === 2) { const w = wordAt(g, lines, ix); setSelection([w], w[1], w[0]); return; }
    if (e.detail >= 3) { selectLine(ix.flat[g].li); return; }
    if (e.shiftKey) {
      const a = st.anchor ?? st.caret ?? g;
      const keep = st.ranges.slice(0, -1);
      setSelection([...keep, norm(a, g)], g, a);
      return;
    }
    if (e.ctrlKey || e.metaKey) {
      setSelection([...st.ranges, [g, g]], g, g);
      drag.current = { mode: 'add', anchor: g, y0: e.clientY, off0: offRef.current, moved: false };
    } else {
      set({ ranges: [], caret: g, anchor: g });
      seekChar(g);
      drag.current = { mode: 'sel', anchor: g, y0: e.clientY, off0: offRef.current, moved: false };
    }
    const base = (e.ctrlKey || e.metaKey) ? st.ranges : [];
    const move = (m: MouseEvent) => {
      const d = drag.current;
      if (!d) return;
      const h = gAt(m.clientX, m.clientY);
      if (h == null || (h === d.anchor && !d.moved)) return;
      d.moved = true;
      setSelection([...base, norm(d.anchor, h)], h, d.anchor);
    };
    const up = () => { drag.current = null; window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  };

  // 空白处: 拖动 = 浏览滚动, 单击 = 跳到该句开头
  const onBlankDown = (e: React.MouseEvent) => {
    if (e.button !== 0 && e.button !== 1) return;
    vp.current?.focus({ preventScroll: true });
    const lineEl = (e.target as HTMLElement).closest<HTMLElement>('[data-i]');
    const d = { y0: e.clientY, off0: offRef.current, moved: false };
    const move = (m: MouseEvent) => {
      if (!d.moved && Math.abs(m.clientY - d.y0) < 4) return;
      d.moved = true;
      enterBrowse();
      setOff(clampOff(d.off0 - (m.clientY - d.y0)));
    };
    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
      if (!d.moved && lineEl && e.button === 0) clock.seek(lines[Number(lineEl.dataset.i)].t[0] + 0.001);
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  };

  const onKey = (e: React.KeyboardEvent) => {
    const st = useStore.getState();
    if (!ix.flat.length) return;
    const n = ix.flat.length;
    const c = st.caret ?? (st.ranges[0]?.[0] ?? ix.start[Math.max(0, st.curLine)] ?? 0);
    let to: number | null = null;
    if (e.key === 'ArrowLeft') to = Math.max(0, c - 1);
    else if (e.key === 'ArrowRight') to = Math.min(n - 1, c + 1);
    else if (e.key === 'ArrowUp') to = vertical(c, -1, lines, ix);
    else if (e.key === 'ArrowDown') to = vertical(c, 1, lines, ix);
    else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); set({ ranges: [] }); return; }
    if (to == null || e.altKey) return;
    e.preventDefault();
    e.stopPropagation();
    if (e.shiftKey) {
      const a = st.anchor ?? c;
      setSelection([...st.ranges.slice(0, -1), norm(a, to)] as Range[], to, a);
    } else {
      set({ ranges: [], caret: to, anchor: to });
      seekChar(to);
    }
    // 光标所在句不在视野: 进浏览把它带进来
    const el = inner.current?.querySelector<HTMLElement>(`[data-g="${to}"]`);
    const v = vp.current;
    if (el && v) {
      const r = el.getBoundingClientRect(), vr = v.getBoundingClientRect();
      if (r.top < vr.top + 20 || r.bottom > vr.bottom - 20) { enterBrowse(); setOff((o) => clampOff(o + (r.top - vr.top) - vr.height * 0.4)); }
    }
  };

  const onCtx = (e: React.MouseEvent) => {
    e.preventDefault();
    const g = (e.target as HTMLElement).closest<HTMLElement>('[data-g]');
    const lineEl = (e.target as HTMLElement).closest<HTMLElement>('[data-i]');
    if (g) ensureSelectedAt(Number(g.dataset.g));
    else if (lineEl) {
      const li = Number(lineEl.dataset.i);
      const st = useStore.getState();
      if (!inRanges(st.ranges, ix.start[li])) selectLine(li);
    }
    set({ menu: { x: e.clientX, y: e.clientY, source: 'lyrics' } });
  };

  return (
    <aside className={s.panel} data-stale={stale || undefined}>
      <div className={s.head}>歌词 <span className={s.dim}>{lines.length} 句</span>
        {stale && (
          // 歌词/门禁热更新失败或连接断开: 这里显示的不是最新. 就地标出来, 不只靠顶栏
          <span className={s.stale} data-testid="stale-lyrics" data-why={staleErr ? 'error' : 'offline'}
            title={staleErr ? `歌词刷新失败, 显示的是上一次成功的版本: ${staleErr}` : '与服务断开, 磁盘上的改动不会显示'}>
            {staleErr ? '上次刷新失败 · 旧版' : '未连接 · 可能不是最新'}
          </span>
        )}
        <span className={s.grow} />
        <span className={s.mode} data-testid="lyrics-mode">{browse ? '浏览' : '跟随'}</span>
      </div>
      <div className={s.vp} ref={vp} data-scroll-ok data-testid="lyrics" data-mode={browse ? 'browse' : 'follow'} tabIndex={0}
        onKeyDown={onKey} onContextMenu={onCtx} onMouseDown={onBlankDown}>
        <div ref={inner} className={s.inner} data-testid="lyrics-inner"
          style={{ transform: `translate3d(0, ${-off}px, 0)`, transition: browse ? 'none' : 'transform 0.45s cubic-bezier(0.2, 0.7, 0.2, 1)' }}>
          {lines.map((l, i) => (
            <div key={l.name} data-i={i} className={s.line} data-cur={i === cur || undefined} data-role={l.role ?? undefined}
              onMouseEnter={() => browse && set({ hoverLine: i })} onMouseLeave={() => browse && set({ hoverLine: null })}>
              <button className={s.no} data-testid="lineno" tabIndex={-1}
                onMouseDown={(e) => { if (e.button === 0) { e.stopPropagation(); e.preventDefault(); vp.current?.focus({ preventScroll: true }); selectLine(i); } }}>
                {String(l.line ?? i).padStart(2, '0')}
              </button>
              <div className={s.texts}>
                <div className={s.jp}>
                  {l.chars.map((c) => {
                    const g = ix.start[i] + c.i;
                    return (
                      <span key={c.i} className={s.ch} data-g={g} data-ci={c.i} data-sel={inRanges(ranges, g) || undefined}
                        data-caret={caret === g || undefined} data-rv={rvMap.get(g)} onMouseDown={(e) => onCharDown(e, g)}>
                        {c.ruby ? <ruby><span className={s.b}>{c.ch}</span><rt>{c.ruby}</rt></ruby> : <span className={s.b}>{c.ch}</span>}
                      </span>
                    );
                  })}
                </div>
                {l.cn && <div className={s.cn}>{l.cn}</div>}
              </div>
              <div className={s.badges}>
                {l.role && <span className={s.role} data-role={l.role}>{ROLE_CN[l.role] ?? l.role}</span>}
                <span className={s.fx} title={`本句 FX ${l.fx} 条, 参考 ${l.ref_fx} 条`}>FX {l.fx}</span>
                <svg className={s.mini} width="40" height="6" viewBox="0 0 40 6" aria-label={`out ${l.fx} / 参考 ${l.ref_fx}`}>
                  <rect x="0" y="0" width="40" height="6" fill="#262a33" />
                  <rect x="0" y="0" width={(40 * l.fx) / maxFx} height="6" fill="#6ea8ff" />
                  <line x1={(40 * l.ref_fx) / maxFx} x2={(40 * l.ref_fx) / maxFx} y1="0" y2="6" stroke="#f0a24a" strokeWidth="1.5" strokeDasharray="2 1" />
                </svg>
              </div>
            </div>
          ))}
        </div>
      </div>
      {browse && <button className={s.back} data-testid="back-to-current" onClick={backToCurrent}>回到当前句</button>}
    </aside>
  );
}
