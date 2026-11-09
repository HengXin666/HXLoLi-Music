import { useEffect, useMemo, useRef, useState } from 'react';
import { api, type RawEvent } from '../lib/api';
import { useStore } from '../lib/store';
import { FX_ROLE, REVIEW_KIND } from '../lib/tracks';
import type { ExplainItem, Review } from '../lib/api';
import s from './Inspector.module.css';

/**
 * 检查器 ("说明这里", plan 3.6): 选区 -> 每条事件属于哪个 fx 函数 + 源码位置, 层号, 标签摘要;
 * arc.json 角色/手法/why; 锚定的音乐事件; 参考 ASS 同一句的条数与类别对比. 末尾是选区事件列表 (虚拟滚动).
 * 本面板与歌词面板是仅有的两处内部滚动 (隐藏原生滚动条).
 */
const ROW = 18;
const srcStr = (x: { file: string; line: number | null; note?: string }) => `${x.file}${x.line ? `:${x.line}` : ''}`;
const fnName = (fn: string) => (fn.includes(':') ? fn.split(':').slice(1).join(':') : fn);
const ROLE_CN: Record<string, string> = { high: '高光句', carrier: '承载句', rest: '留白句' };

/** 一句话说明: 这几个字由哪些事件构成, 落在哪几层 (按层的语义名), 主要出自哪个 fx 函数, 这句在 arc 里的角色 */
function plain(it: ExplainItem): string[] {
  const out: string[] = [];
  const byLayer = new Map<string, number>();
  let text = 0;
  for (const g of it.groups) {
    if (g.style === 'FX') {
      const k = `${g.layer} ${FX_ROLE[Math.max(0, Math.min(8, g.layer))]?.[0] ?? ''}`;
      byLayer.set(k, (byLayer.get(k) ?? 0) + g.n);
    } else text += g.n;
  }
  const fx = [...byLayer.values()].reduce((a, b) => a + b, 0);
  out.push(`这 ${[...it.text].length} 字「${it.text}」在 ${it.t0.toFixed(2)}-${it.t1.toFixed(2)}s 共 ${it.n} 条事件: 字层 ${text} 条, 特效 ${fx} 条${fx ? ` (按层: ${[...byLayer].sort().map(([k, n]) => `${k} ${n}`).join(', ')})` : ''}.`);
  // 同一函数在不同层的分组合并, 名字带上模块 (fx_bed.hits), 一眼知道去哪个文件改
  const byFn = new Map<string, { n: number; src: string }>();
  for (const g of it.groups) {
    if (g.style !== 'FX' || g.ambiguous) continue;
    const mod = g.src[0]?.file ? g.src[0].file.split('/').pop()!.replace(/\.py$/, '') : '';
    const k = mod ? `${mod}.${fnName(g.fn)}` : fnName(g.fn);
    const e = byFn.get(k) ?? { n: 0, src: g.src[0] ? srcStr(g.src[0]) : '' };
    e.n += g.n;
    byFn.set(k, e);
  }
  const top = [...byFn].sort((x, y) => y[1].n - x[1].n).slice(0, 3);
  if (top.length) out.push(`特效主要出自 ${top.map(([k, e]) => `${k} ×${e.n}${e.src ? ` (${e.src})` : ''}`).join('、')}.`);
  const a = it.arc;
  const role = a.role ? ROLE_CN[a.role] ?? a.role : null;
  if (role || a.technique || a.idea) out.push(`这句在全曲弧线里是${role ?? '—'}${a.technique ? `, 手法 ${a.technique}` : ''}${a.idea ? `, 构想 "${a.idea}"` : ''}.`);
  if (a.why || a.section_why) out.push(`为什么: ${a.why ?? a.section_why}`);
  const rf = it.ref.window;
  out.push(`参考 ASS 同一时段 ${rf} 条, 成品 ${it.n} 条${rf ? ` (${(it.n / rf).toFixed(2)} 倍)` : ''}.`);
  return out;
}

export default function Inspector() {
  const explain = useStore((x) => x.explain);
  const busy = useStore((x) => x.explainBusy);
  const err = useStore((x) => x.explainErr);
  const ranges = useStore((x) => x.ranges);
  const menuHits = useStore((x) => x.inspectHits);
  const set = useStore((x) => x.set);
  const body = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [events, setEvents] = useState<RawEvent[]>([]);
  const [scroll, setScroll] = useState(0);
  const [vh, setVh] = useState(400);

  const lns = useMemo(() => {
    const a = new Set<number>();
    for (const it of explain || []) for (const g of it.groups) g.lines.forEach((l) => a.add(l));
    for (const h of menuHits || []) a.add(h.ln);
    return [...a].sort((x, y) => x - y);
  }, [explain, menuHits]);

  useEffect(() => {
    if (!lns.length) { setEvents([]); return; }
    let live = true;
    api.events(lns).then((r) => live && setEvents(r.events)).catch(() => undefined);
    return () => { live = false; };
  }, [lns]);

  useEffect(() => {
    const el = body.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setVh(el.clientHeight));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const listTop = listRef.current?.offsetTop ?? 0;
  const first = Math.max(0, Math.floor((scroll - listTop) / ROW) - 5);
  const last = Math.min(events.length, Math.ceil((scroll - listTop + vh) / ROW) + 5);

  return (
    <section className={s.ins} data-testid="inspector">
      <div className={s.head}>
        <span>检查器 · 说明这里</span>
        <span className={s.grow} />
        <button className={s.x} onClick={() => set({ inspector: false })} title="关闭" data-testid="inspector-close">×</button>
      </div>
      <div className={s.body} ref={body} data-scroll-ok onScroll={(e) => setScroll((e.target as HTMLElement).scrollTop)}>
        {!ranges.length && !menuHits?.length && <div className={s.empty}>没有选区. 在歌词里选字 (或右键时间线片段 / 画面) 后按 E.</div>}
        {ranges.length > 0 && !explain?.length && busy && <div className={s.empty} data-testid="ins-loading">正在读取选区的说明 …</div>}
        {ranges.length > 0 && !explain?.length && !busy && err && <div className={s.err} data-testid="ins-error">说明读取失败: {err}. 服务端 /api/explain 出错, 看 studio 服务日志.</div>}
        {(explain || []).length > 0 && (
          <div className={s.block} data-testid="ins-plain">
            <div className={s.h2}>一句话说明</div>
            {(explain || []).map((it) => (
              <div key={`p${it.name}${it.t0}`} className={s.plain}>
                <b>L{String(it.line).padStart(2, '0')} {it.text}</b>
                {plain(it).map((t, k) => <div key={k}>{t}</div>)}
              </div>
            ))}
          </div>
        )}
        <ReviewsHere explain={explain} />
        {menuHits && menuHits.length > 0 && (
          <div className={s.block} data-testid="ins-hits">
            <div className={s.h2}>画面命中 {menuHits.length} 个事件</div>
            <table className={s.tb}><tbody>
              {menuHits.slice(0, 40).map((h) => (
                <tr key={h.ln}><td className={s.mono}>#{h.ln}</td><td>{h.style} L{h.layer}</td><td>{h.name}</td>
                  <td className={s.mono}>{h.fns.map(fnName).join(' | ') || '?'}</td></tr>
              ))}
            </tbody></table>
          </div>
        )}
        {(explain || []).map((it) => (
          <div key={`${it.name}${it.t0}`} className={s.item} data-testid="ins-item">
            <div className={s.h1}>
              <b>L{String(it.line).padStart(2, '0')}</b> {it.text} <span className={s.dim}>{it.t0.toFixed(2)}-{it.t1.toFixed(2)}s · {it.label} · 事件 {it.n}</span>
            </div>
            <div className={s.block} data-testid="ins-arc">
              <div className={s.h2}>arc</div>
              <dl className={s.dl}>
                <dt>角色</dt><dd>{it.arc.role ?? '—'}</dd>
                <dt>手法</dt><dd>{it.arc.technique ?? '—'}</dd>
                <dt>构想</dt><dd>{it.arc.idea ?? '—'}</dd>
                <dt>why</dt><dd>{it.arc.why ?? it.arc.section_why ?? '—'}</dd>
                <dt>段落</dt><dd>{it.arc.section ?? '—'}{it.arc.thread?.state ? ` · ${it.arc.thread.mode ?? ''} ${it.arc.thread.state}` : ''}</dd>
                <dt>锚点</dt><dd>{it.arc.anchors?.map((a) => `${a.kind}:${a.ref}`).join(' · ') || '—'}</dd>
                <dt>参数</dt><dd className={s.mono}>{Object.entries(it.params).map(([k, v]) => `${k}=${String(v)}`).join(' ')}</dd>
              </dl>
            </div>
            <div className={s.block} data-testid="ins-groups">
              <div className={s.h2}>事件归属 (fx 函数 · 源码 · 层 · 条数)</div>
              <table className={s.tb}>
                <thead><tr><th>fx 函数</th><th>源码</th><th>样式</th><th>层</th><th>条</th><th>标签摘要</th></tr></thead>
                <tbody>
                  {it.groups.map((g) => (
                    <tr key={`${g.fn}${g.style}${g.layer}`}>
                      <td className={s.mono} title={g.ambiguous ? `候选: ${g.candidates.join(', ')}` : ''}>
                        {g.ambiguous ? `${g.candidates.map(fnName).join(' | ') || '?'} (候选)` : fnName(g.fn)}
                      </td>
                      <td className={s.mono}>{g.src.map(srcStr).join(' ')}</td>
                      <td>{g.style}</td><td>{g.layer}</td><td className={s.num}>{g.n}</td>
                      <td className={s.tags} title={g.tags}>{g.tags}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className={s.note}>本句单元 emit: {it.emit.map((e) => `${fnName(e.fn)}×${e.n} [L${e.layers.join(',')}] ${srcStr(e.src)}`).join(' · ')}</div>
            </div>
            <div className={s.block} data-testid="ins-music">
              <div className={s.h2}>音乐事件</div>
              <div>节拍 {it.music.beats} 拍{it.music.bpm ? ` (BPM ${it.music.bpm})` : ''} · 起音 {it.music.onset.length} · 低频重拍 {it.music.sub.length}</div>
              <div className={s.mono}>{it.music.onset.slice(0, 16).map((o) => `${o.t.toFixed(2)}${o.s != null ? `(${o.s.toFixed(2)})` : ''}`).join(' ')}</div>
              {it.music.sub.length > 0 && <div className={s.mono}>sub: {it.music.sub.map((t) => t.toFixed(2)).join(' ')}</div>}
            </div>
            <div className={s.block} data-testid="ins-ref">
              <div className={s.h2}>与参考同一句对比</div>
              <table className={s.tb}>
                <thead><tr><th>类别</th><th>out 选区</th><th>参考 选区</th><th>out 整句</th><th>参考 整句</th></tr></thead>
                <tbody>
                  {[...new Set([...Object.keys(it.ref.out_line), ...Object.keys(it.ref.cat_line)])].sort().map((k) => (
                    <tr key={k}><td>{k}</td><td className={s.num}>{it.ref.out_window[k] ?? 0}</td><td className={s.num}>{it.ref.cat_window[k] ?? 0}</td>
                      <td className={s.num}>{it.ref.out_line[k] ?? 0}</td><td className={s.num}>{it.ref.cat_line[k] ?? 0}</td></tr>
                  ))}
                  <tr className={s.sum}><td>合计</td><td className={s.num}>{it.n}</td><td className={s.num}>{it.ref.window}</td>
                    <td className={s.num}>{Object.values(it.ref.out_line).reduce((a, b) => a + b, 0)}</td><td className={s.num}>{it.ref.line}</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        ))}
        {events.length > 0 && (
          <div className={s.block}>
            <div className={s.h2}>选区事件 {events.length} 条 (ASS 原文)</div>
            <div ref={listRef} className={s.list} style={{ height: events.length * ROW }} data-testid="ins-events" data-total={events.length}>
              {events.slice(first, last).map((e, k) => (
                <div key={e.ln} className={s.row} style={{ top: (first + k) * ROW }} title={e.raw}>
                  <span className={s.mono}>#{e.ln}</span> <span>{e.style} L{e.layer}</span> <span className={s.mono}>{e.t0.toFixed(2)}</span>{' '}
                  <span className={s.mono}>{e.owners.map(fnName).join('|') || '?'}</span> <span className={s.raw}>{e.text}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

/** 选区时段内已有的标注 (按类型着色), 让 "说明这里" 能看到之前标过什么 */
function ReviewsHere({ explain }: { explain: ExplainItem[] | null }) {
  const reviews = useStore((x) => x.reviews);
  if (!explain?.length) return null;
  const t0 = Math.min(...explain.map((it) => it.t0)), t1 = Math.max(...explain.map((it) => it.t1));
  const lines = new Set(explain.map((it) => it.line));
  const hit = reviews.filter((r: Review) => r.t1 > t0 && r.t0 < t1 && r.sel.some((sr) => lines.has(sr.line)));
  return (
    <div className={s.block} data-testid="ins-reviews">
      <div className={s.h2}>这里的标注 {hit.length} 条</div>
      {!hit.length && <div className={s.dim}>还没有标注. 右键 &gt; 不行 / 好 / 换一个构想 / 写批注.</div>}
      {hit.slice(-20).reverse().map((r) => (
        <div key={r.id} className={s.rv}>
          <i className={s.rvk} style={{ background: REVIEW_KIND[r.kind]?.c }} />
          <b>{REVIEW_KIND[r.kind]?.cn ?? r.kind}</b>
          <span className={s.mono}> {r.t0.toFixed(2)}-{r.t1.toFixed(2)}s</span>
          {r.tags.length > 0 && <span> · {r.tags.join(' / ')}</span>}
          {r.text && <span> · {r.text}</span>}
          <span className={s.dim}> · {r.created}</span>
        </div>
      ))}
    </div>
  );
}
