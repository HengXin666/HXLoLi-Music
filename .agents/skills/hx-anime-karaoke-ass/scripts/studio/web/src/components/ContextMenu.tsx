import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { menuHeader, menuItems, review, type MEntry, type MItem } from '../lib/actions';
import { useStore } from '../lib/store';
import s from './ContextMenu.module.css';

/**
 * 右键菜单 (三处共用). 自写而不引 radix: 需要精确控制 150ms 子菜单延迟与安全三角, 且便于 Playwright 断言.
 * - portal 到 body, 贴边翻转并夹到视口内
 * - 键盘: 上下选项 (跳过分隔与置灰), 右键进子菜单, 左键/Esc 逐级退出, Enter 执行
 * - 子菜单悬停 150ms 打开; 指针在 "安全三角" (上一个指针点 -> 子菜单近边两角) 内移动时不切换
 * - 置灰项 hover 300ms 出 tooltip 说原因
 */
const SUB_DELAY = 150;

type Pt = { x: number; y: number };
function inTri(p: Pt, a: Pt, b: Pt, c: Pt) {
  const d = (p1: Pt, p2: Pt, p3: Pt) => (p1.x - p3.x) * (p2.y - p3.y) - (p2.x - p3.x) * (p1.y - p3.y);
  const d1 = d(p, a, b), d2 = d(p, b, c), d3 = d(p, c, a);
  return !((d1 < 0 || d2 < 0 || d3 < 0) && (d1 > 0 || d2 > 0 || d3 > 0));
}

const enabled = (e: MEntry): e is MItem => e !== 'sep' && !e.disabled;

function place(el: HTMLElement, x: number, y: number, flipFrom?: DOMRect) {
  const r = el.getBoundingClientRect();
  const W = innerWidth, H = innerHeight, m = 4;
  let nx = x, ny = y;
  if (flipFrom) {
    // 子菜单: 默认在父项右侧, 放不下翻到左侧
    nx = flipFrom.right - 2;
    if (nx + r.width > W - m) nx = flipFrom.left - r.width + 2;
    ny = flipFrom.top - 5;
  } else {
    if (nx + r.width > W - m) nx = x - r.width;
    if (ny + r.height > H - m) ny = y - r.height;
  }
  nx = Math.max(m, Math.min(W - r.width - m, nx));
  ny = Math.max(m, Math.min(H - r.height - m, ny));
  el.style.left = `${Math.round(nx)}px`;
  el.style.top = `${Math.round(ny)}px`;
  el.dataset.flipX = String(nx < x - 1 && !flipFrom ? 1 : flipFrom && nx < flipFrom.left ? 1 : 0);
  el.dataset.flipY = String(ny < y - 1 ? 1 : 0);
}

function List({ items, level, x, y, parent, active, setActive, openSub, onRun, header, listRef }: {
  items: MEntry[]; level: number; x: number; y: number; parent?: DOMRect; active: number; setActive: (i: number) => void;
  openSub: (i: number | null, immediate?: boolean, pt?: Pt) => void; onRun: (it: MItem) => void; header?: string;
  listRef: (el: HTMLDivElement | null) => void;
}) {
  const el = useRef<HTMLDivElement | null>(null);
  const [tip, setTip] = useState<{ text: string; x: number; y: number } | null>(null);
  const tipT = useRef(0);
  useLayoutEffect(() => { if (el.current) place(el.current, x, y, parent); }, [x, y, parent, items.length]);
  return (
    <div ref={(e) => { el.current = e; listRef(e); }} className={s.menu} role="menu" data-level={level}
      data-testid={level === 0 ? 'ctx-menu' : `ctx-sub-${level}`} onContextMenu={(e) => e.preventDefault()}>
      {header && <div className={s.header} data-testid="ctx-header">{header}</div>}
      {header && <div className={s.sep} role="separator" data-head="1" />}
      {items.map((it, i) => it === 'sep' ? <div key={`sep${i}`} className={s.sep} role="separator" /> : (
        <div key={it.id} role="menuitem" data-id={it.id} aria-disabled={!!it.disabled || undefined}
          aria-haspopup={it.sub ? 'menu' : undefined} data-active={i === active || undefined}
          className={s.item} title={it.disabled || undefined}
          onPointerEnter={(e) => {
            clearTimeout(tipT.current);
            setTip(null);
            if (it.disabled) {
              const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
              const reason = it.disabled;
              tipT.current = window.setTimeout(() => setTip({ text: reason, x: r.right + 6, y: r.top }), 300);
            }
            setActive(i);
            openSub(it.sub && !it.disabled ? i : null, false, { x: e.clientX, y: e.clientY });
          }}
          onPointerLeave={() => { clearTimeout(tipT.current); setTip(null); }}
          onClick={(e) => {
            e.stopPropagation();
            if (it.disabled) return;
            if (it.sub) openSub(i, true);
            else onRun(it);
          }}>
          <span className={s.check}>{it.checked ? '✓' : ''}</span>
          <span className={s.label}>{it.label}</span>
          {it.kbd && <span className={s.kbd}>{it.kbd}</span>}
          {it.sub && <span className={s.arrow}>›</span>}
        </div>
      ))}
      {tip && createPortal(<div className={s.tip} role="tooltip" data-testid="ctx-tip"
        style={{ left: Math.min(tip.x, innerWidth - 260), top: tip.y }}>{tip.text}</div>, document.body)}
    </div>
  );
}

export default function ContextMenu() {
  const menu = useStore((x) => x.menu);
  const noteBox = useStore((x) => x.noteBox);
  // 依赖这些状态的菜单项要随之重算
  useStore((x) => x.ranges);
  useStore((x) => x.explain);
  useStore((x) => x.compare);
  useStore((x) => x.abShow);
  useStore((x) => x.vis);
  useStore((x) => x.onlyUnits);
  const set = useStore((x) => x.set);
  const [stack, setStack] = useState<number[]>([-1]); // 每级的 active 下标
  const [openAt, setOpenAt] = useState<(number | null)[]>([null]); // 每级打开的子菜单所在项
  const lists = useRef<(HTMLDivElement | null)[]>([]);
  const subT = useRef(0);
  const lastPt = useRef<Pt>({ x: 0, y: 0 });
  const curPt = useRef<Pt>({ x: 0, y: 0 });

  useEffect(() => { if (menu) { setStack([-1]); setOpenAt([null]); } }, [menu]);

  const close = useCallback(() => { clearTimeout(subT.current); set({ menu: null }); }, [set]);

  const levels: MEntry[][] = [];
  if (menu) {
    let cur: MEntry[] = menuItems();
    levels.push(cur);
    for (let l = 0; l < openAt.length; l++) {
      const i = openAt[l];
      if (i == null) break;
      const it = cur[i];
      if (!it || it === 'sep' || !it.sub) break;
      cur = it.sub;
      levels.push(cur);
    }
  }

  const run = useCallback(async (it: MItem) => {
    if (!it.run) return;
    const r = it.run(); // 先执行 (noteAt 要读菜单位置), 再关
    close();
    await r;
  }, [close]);

  const setActive = (level: number, i: number) => setStack((st) => { const n = st.slice(0, level + 1); while (n.length <= level) n.push(-1); n[level] = i; return n; });
  // pt = 触发这次切换的指针位置 (pointerenter 先于 pointermove 派发, 所以 curPt 此时还是上一个点, 正好当三角的顶点)
  const openSub = (level: number, i: number | null, immediate = false, pt?: Pt) => {
    clearTimeout(subT.current);
    const apply = () => setOpenAt((o) => { const n = o.slice(0, level + 1); while (n.length <= level) n.push(null); n[level] = i; if (i != null) n.push(null); return n; });
    // 安全三角: 子菜单已开着, 指针正朝它移动时不切换
    const sub = lists.current[level + 1];
    if (!immediate && sub && openAt[level] != null && openAt[level] !== i) {
      const r = sub.getBoundingClientRect();
      const apex = pt ? curPt.current : lastPt.current, p0 = pt ?? curPt.current;
      const left = r.left > apex.x;
      const a = { x: left ? r.left : r.right, y: r.top - 4 }, b = { x: left ? r.left : r.right, y: r.bottom + 4 };
      if (inTri(p0, apex, a, b)) {
        subT.current = window.setTimeout(() => openSub(level, i, true), SUB_DELAY * 2);
        return;
      }
    }
    if (immediate) apply();
    else subT.current = window.setTimeout(apply, i == null ? 0 : SUB_DELAY);
  };

  // 键盘 + 外部点击
  useEffect(() => {
    if (!menu) return;
    const onKey = (e: KeyboardEvent) => {
      let lv = 0;
      for (let l = 0; l < levels.length; l++) if ((stack[l] ?? -1) >= 0) lv = l;
      const items = levels[lv];
      const act = stack[lv] ?? -1;
      const move = (d: number) => {
        const n = items.length;
        let i = act;
        for (let k = 0; k < n; k++) { i = (i + d + n) % n; if (enabled(items[i])) break; }
        setActive(lv, i);
        // 换了项: 关掉更深的子菜单
        setOpenAt((o) => o.slice(0, lv + 1).map((v, j) => (j === lv ? null : v)));
      };
      e.preventDefault();
      e.stopPropagation();
      if (e.key === 'ArrowDown') move(1);
      else if (e.key === 'ArrowUp') move(-1);
      else if (e.key === 'ArrowRight' || e.key === 'Enter' || e.key === ' ') {
        const it = items[act];
        if (!it || it === 'sep' || it.disabled) return;
        if (it.sub) {
          setOpenAt((o) => { const n = o.slice(0, lv + 1); n[lv] = act; n.push(null); return n; });
          const first = it.sub.findIndex(enabled);
          setStack((st) => { const n = st.slice(0, lv + 1); n.push(first); return n; });
        } else if (e.key !== 'ArrowRight') void run(it);
      } else if (e.key === 'ArrowLeft' || e.key === 'Escape') {
        if (lv === 0) { if (e.key === 'Escape') close(); return; }
        setOpenAt((o) => { const n = o.slice(0, lv); n[lv - 1] = null; return n; });
        setStack((st) => st.slice(0, lv));
      }
    };
    const onDown = (e: PointerEvent) => {
      if ((e.target as HTMLElement).closest('[role=menu]')) return;
      close();
    };
    const onMove = (e: PointerEvent) => { lastPt.current = curPt.current; curPt.current = { x: e.clientX, y: e.clientY }; };
    window.addEventListener('keydown', onKey, true);
    window.addEventListener('pointerdown', onDown, true);
    window.addEventListener('pointermove', onMove, true);
    window.addEventListener('blur', close);
    window.addEventListener('resize', close);
    return () => {
      window.removeEventListener('keydown', onKey, true);
      window.removeEventListener('pointerdown', onDown, true);
      window.removeEventListener('pointermove', onMove, true);
      window.removeEventListener('blur', close);
      window.removeEventListener('resize', close);
    };
  });

  const parentRect = (l: number): DOMRect | undefined => {
    const idx = openAt[l - 1];
    const host = lists.current[l - 1];
    const el = idx != null ? host?.querySelectorAll<HTMLElement>('[role=menuitem], [role=separator]:not([data-head])')[idx] : null;
    return el?.getBoundingClientRect();
  };

  return createPortal(
    <>
      {menu && levels.map((items, l) => (
        <List key={l} items={items} level={l} x={menu.x} y={menu.y} parent={l ? parentRect(l) : undefined}
          active={stack[l] ?? -1} setActive={(i) => setActive(l, i)} openSub={(i, im, pt) => openSub(l, i, im, pt)}
          onRun={run} header={l === 0 ? menuHeader() : undefined} listRef={(e) => { lists.current[l] = e; }} />
      ))}
      {noteBox && <NoteInput />}
    </>,
    document.body,
  );
}

function NoteInput() {
  const nb = useStore((x) => x.noteBox)!;
  const set = useStore((x) => x.set);
  const [v, setV] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const ref = useRef<HTMLInputElement>(null);
  const box = useRef<HTMLDivElement>(null);
  // 框开着时再从菜单开一个 (openNote 直接换 noteBox, 中间不经过 null), 组件不卸载: 上一个框的红字不能串过来.
  // v 不清: 框里没发出去的字是用户的, 不替他扔 (要扔他会自己删)
  useLayoutEffect(() => { setErr(''); ref.current?.focus(); if (box.current) place(box.current, nb.x, nb.y); }, [nb]);
  // 原来先关框再发请求: POST 失败时用户打的字随框一起没了, 而且没有任何提示 (以为存上了).
  // 现在: 写入成功 (服务端 201) 才关框; 失败框留着、字留着, 框里写明没写进去和原因, 可直接再按 Enter 重试
  const submit = async () => {
    const t = v.trim();
    if (!t || busy) return;
    setBusy(true);
    setErr('');
    const r = nb.kind === 'bad' ? await review('bad', [t], t) : await review('note', [], t);
    setBusy(false);
    // 只关 "发出这条的那个框"; 写入期间换成了新框就不去关新框, 红字也不写到新框上
    if (useStore.getState().noteBox !== nb) return;
    if (r?.rec) { set({ noteBox: null }); return; }
    setErr(r ? `没写进去, 内容还在框里, 可再按 Enter 重试: ${r.error}` : '没写进去: 当前没有选区');
    ref.current?.focus();
  };
  return (
    <div ref={box} className={s.note} role="dialog" data-testid="note-box" data-busy={busy || undefined} data-error={err ? 'y' : undefined}>
      <div className={s.noteHead}>{nb.kind === 'bad' ? '不行 · 自定义原因' : '写批注'} <span className={s.dim}>Enter 记入 review, Esc 取消</span></div>
      <input ref={ref} value={v} onChange={(e) => setV(e.target.value)} placeholder={nb.kind === 'bad' ? '哪里不行' : '批注'} readOnly={busy}
        onKeyDown={(e) => {
          e.stopPropagation();
          if (e.key === 'Enter') void submit();
          if (e.key === 'Escape' && !busy) set({ noteBox: null });
        }} />
      {(busy || err) && (
        <div data-testid="note-msg" role={err ? 'alert' : 'status'}
          style={{ marginTop: 6, fontSize: 11, color: err ? 'var(--bad)' : 'var(--fg-2)', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
          {err || '写入中…'}
        </div>
      )}
    </div>
  );
}
