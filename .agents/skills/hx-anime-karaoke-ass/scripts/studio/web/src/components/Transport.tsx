import { useEffect, useRef } from 'react';
import { clock } from '../lib/clock';
import { baseName, clearLoop, loopSelection, REF_SRC, setCompare } from '../lib/actions';
import { fmtTime, useStore } from '../lib/store';
import s from './Transport.module.css';

const abTip = (ref: string) => `与参考对比 (A/B 切换): 成品 = 本工程生成的 out.ass; 参考 = ${ref}. 两者同一时刻、同一画面, 点 成品 / 参考 在两者间切换, 画面角标写明当前看的是哪个. 划变 / 左右并排在右键 > 与参考对比.`;

export default function Transport() {
  const playing = useStore((x) => x.playing);
  const dur = useStore((x) => x.duration);
  const rate = useStore((x) => x.rate);
  const set = useStore((x) => x.set);
  const loop = useStore((x) => x.loop);
  // 原来取 ref_ass (接口 URL "/api/ass/ref") 的末段, 永远显示 "ref": 等于没说在跟谁比
  const refPath = useStore((x) => x.project?.ref_path);
  const refInfo = useStore((x) => x.project?.ref);
  const AB_TIP = abTip(`${baseName(refPath)} (${REF_SRC[refInfo?.source ?? 'none']})`);
  const noRefTip = refInfo?.error ? `参考 ASS ${REF_SRC[refInfo.source]}: ${refInfo.error}. 点顶栏 "参考" 选一份` : '没有参考 ASS (static/music/<番名>/ 下没有文件名含歌名的 .ass), 不能对比';
  const compare = useStore((x) => x.compare);
  const abShow = useStore((x) => x.abShow);
  const hasSel = useStore((x) => x.ranges.length > 0);
  const hasRef = useStore((x) => !!x.project?.ref_ass);
  const tRef = useRef<HTMLSpanElement>(null);
  useEffect(() => clock.subscribe((t) => { if (tRef.current) tRef.current.textContent = fmtTime(t); }), []);
  return (
    <div className={s.bar}>
      <button className={s.btn} onClick={() => clock.seek(0)} title="回到开头">⏮</button>
      <button className={s.btn} onClick={() => clock.toggle()} title="播放 / 暂停 (Space)" data-testid="play">
        {playing ? '❚❚' : '▶'}
      </button>
      <span className={s.time}><span ref={tRef}>00:00.00</span><span className={s.dim}> / {fmtTime(dur)}</span></span>
      <button className={s.btn} data-on={loop ? 1 : undefined} disabled={!loop && !hasSel} data-testid="loop-btn"
        title={loop ? '取消循环 (L)' : hasSel ? '循环选区 (L)' : '没有选区'} onClick={() => (loop ? clearLoop() : loopSelection(1))}>⟲</button>
      <span className={s.grow} />
      {compare !== 'ab' ? (
        <button className={s.wide} disabled={!hasRef} data-testid="ab-btn"
          title={hasRef ? AB_TIP : noRefTip} onClick={() => setCompare('ab')}>
          对比: 成品 / 参考
        </button>
      ) : (
        <span className={s.seg} data-testid="ab-btn" title={AB_TIP}>
          <button className={s.segb} data-on={abShow === 'out' || undefined} data-testid="ab-out"
            onClick={() => { if (abShow !== 'out') setCompare('ab'); }}>成品</button>
          <button className={s.segb} data-on={abShow === 'ref' || undefined} data-testid="ab-ref"
            onClick={() => { if (abShow !== 'ref') setCompare('ab'); }}>参考</button>
          <button className={s.segx} title="关闭对比, 回到只看成品" data-testid="ab-close"
            onClick={() => useStore.setState({ compare: 'off', abShow: 'out' })}>×</button>
        </span>
      )}
      <label className={s.lab}>倍速
        <select value={rate} onChange={(e) => { const r = Number(e.target.value); clock.setRate(r); set({ rate: r }); }}>
          {[0.25, 0.5, 0.75, 1, 1.25].map((r) => <option key={r} value={r}>{r}x</option>)}
        </select>
      </label>
      <label className={s.lab}>音量
        <input type="range" min={0} max={1} step={0.05} defaultValue={1}
          onChange={(e) => { clock.audio.volume = Number(e.target.value); }} />
      </label>
    </div>
  );
}
