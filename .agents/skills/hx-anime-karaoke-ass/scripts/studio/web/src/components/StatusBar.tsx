import { useEffect, useRef, useState } from 'react';
import { clock } from '../lib/clock';
import { explainCounts, selSummary } from '../lib/actions';
import { fmtTime, useStore } from '../lib/store';
import s from './Bars.module.css';

export default function StatusBar() {
  const tRef = useRef<HTMLSpanElement>(null);
  const aliveRef = useRef<HTMLSpanElement>(null);
  const lines = useStore((x) => x.lines);
  const cur = useStore((x) => x.curLine);
  const out = useStore((x) => x.out);
  useStore((x) => x.ranges);
  const explain = useStore((x) => x.explain);
  const kept = useStore((x) => x.monitorKept);
  const loop = useStore((x) => x.loop);
  const [vp, setVp] = useState('');
  useEffect(() => {
    const f = () => setVp(`${innerWidth}×${innerHeight} @${devicePixelRatio}x`);
    f();
    addEventListener('resize', f);
    return () => removeEventListener('resize', f);
  }, []);
  useEffect(() => clock.subscribe((t) => {
    if (tRef.current) tRef.current.textContent = fmtTime(t);
    if (aliveRef.current && out) {
      const i = Math.floor((t - out.profile.span[0]) / out.step);
      const v = i >= 0 && i < out.profile.alive_curve.length ? out.profile.alive_curve[i] : 0;
      aliveRef.current.textContent = String(v);
    }
  }), [out]);
  const L = cur >= 0 ? lines[cur] : null;
  const sm = selSummary();
  const ec = explainCounts();
  const selText = sm ? `${sm.n} 字 ${sm.label} ${sm.t0.toFixed(2)}-${sm.t1.toFixed(2)}s${explain ? `, 涉及 FX ${ec.fx} / JP ${ec.jp}` : ''}` : '';
  return (
    <footer className={s.status}>
      <span className={s.mono} ref={tRef}>00:00.00</span>
      <span className={s.sep} />
      {sm ? <span data-testid="status-sel" className={s.sel}>{selText}</span>
        : <span>{L ? `${L.name} ${L.t[0].toFixed(2)}-${L.t[1].toFixed(2)}s · ${L.fn ?? ''} · FX ${L.fx}` : '—'}</span>}
      <span className={s.sep} />
      <span>存活 FX <span className={s.mono} ref={aliveRef}>0</span></span>
      {loop && <><span className={s.sep} /><span data-testid="status-loop">循环 {loop.t0.toFixed(2)}-{loop.t1.toFixed(2)}s</span></>}
      <span className={s.sep} />
      <span title="监视器当前渲染的事件条数 (轨显示过滤后)">渲染 {kept}</span>
      <span className={s.grow} />
      <span className={s.mono} data-testid="viewport">{vp}</span>
    </footer>
  );
}
