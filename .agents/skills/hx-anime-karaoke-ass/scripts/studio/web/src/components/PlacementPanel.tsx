import { useEffect } from 'react';
import type { Preset } from '../lib/api';
import { applyPlacement, clearPreview, pickPlacement, refreshPlacement, samePreset } from '../lib/placement';
import { syncFail, syncOk, useStore } from '../lib/store';
import s from './PlacementPanel.module.css';

const VN: Record<Preset['v'], string> = { top: '顶', middle: '中', bottom: '底' };
const HN: Record<Preset['h'], string> = { left: '左', center: '中', right: '右' };
const ON: Record<Preset['order'], string> = { jp_top: '日上中下', cn_top: '中上日下' };
const GN: Record<Preset['gap'], string> = { tight: '紧', normal: '标准', loose: '松' };
const name = (p: Preset) => `${VN[p.v]}${HN[p.h]} · ${ON[p.order]} · 行距${GN[p.gap]}`;

/**
 * 歌词位置预设面板 (顶栏 "位置" 打开的浮层, 不占布局, 不引入滚动条).
 * 9 位置 x 语言顺序 x 行距: 点一下 = 候选, 监视器立刻近似预览 (块位移由服务端算); "应用" = POST 重跑生成器.
 * 生成中按钮禁用, 状态只来自服务端 (GET /api/placement 的 job, /api/watch 推 job 变化).
 */
export default function PlacementPanel() {
  const place = useStore((x) => x.place);
  const cand = useStore((x) => x.placeCand);
  const open = useStore((x) => x.placeOpen);
  const set = useStore((x) => x.set);
  const placeErr = useStore((x) => x.syncErr.place);
  // 打开时刷新; 成败同样记进 syncErr (原来是未处理的 rejection)
  useEffect(() => { if (open) refreshPlacement().then(() => syncOk('place'), (e) => syncFail('place', e)); }, [open]);
  if (!open || !place) return null;
  const cur = place.current;
  const sel = cand ?? cur;
  const running = place.job.running;
  const pick = (p: Partial<Preset>) => { if (!running) void pickPlacement({ ...sel, ...p }); };
  const dirty = !!cand && !samePreset(cand, cur);
  return (
    <div className={s.panel} data-testid="placement-panel" data-running={running || undefined} role="dialog" aria-label="歌词位置">
      <div className={s.head}>
        <span>歌词位置</span>
        <span className={s.grow} />
        <button className={s.x} onClick={() => set({ placeOpen: false })} aria-label="关闭" data-testid="place-close">×</button>
      </div>
      <div className={s.now} data-testid="place-current" data-source={place.source}>
        <b>现在生效</b> {name(cur)}
        <span className={s.src}>{place.source === 'file' ? 'placement.json' : '默认 (无 placement.json)'}</span>
      </div>
      <div className={s.pick} data-testid="place-cand" data-dirty={dirty || undefined}>
        <b>{dirty ? '正在预览' : '选择'}</b> {dirty ? name(sel) : '与现在生效相同, 未预览'}
      </div>
      <div className={s.body}>
        <div className={s.grid} role="radiogroup" aria-label="位置">
          {place.enums.v.map((v) => place.enums.h.map((h) => (
            <button key={`${v}-${h}`} role="radio" aria-checked={sel.v === v && sel.h === h} disabled={running}
              data-testid={`place-${v}-${h}`} data-cur={(cur.v === v && cur.h === h) || undefined}
              className={s.cell} onClick={() => pick({ v, h })} title={`${VN[v]}${HN[h]}`}>
              <span className={s.dot} data-v={v} data-h={h} />
            </button>
          )))}
        </div>
        <div className={s.col}>
          <div className={s.seg} role="radiogroup" aria-label="语言顺序">
            {place.enums.order.map((o) => (
              <button key={o} role="radio" aria-checked={sel.order === o} disabled={running} data-testid={`place-order-${o}`} onClick={() => pick({ order: o })}>{ON[o]}</button>
            ))}
          </div>
          <div className={s.seg} role="radiogroup" aria-label="行距">
            {place.enums.gap.map((g) => (
              <button key={g} role="radio" aria-checked={sel.gap === g} disabled={running} data-testid={`place-gap-${g}`} onClick={() => pick({ gap: g })}>{GN[g]}</button>
            ))}
          </div>
          <div className={s.acts}>
            <button className={s.apply} disabled={!dirty || running || place.frozen > 0} onClick={() => void applyPlacement()} data-testid="place-apply">
              {running ? '生成中…' : '应用并重跑'}
            </button>
            <button disabled={!dirty || running} onClick={clearPreview} data-testid="place-revert">取消预览</button>
          </div>
        </div>
      </div>
      <div className={s.msg} data-testid="place-msg" data-stale={placeErr ? 'y' : undefined} title={placeErr || undefined}>
        {placeErr ? `状态刷新失败, 下面可能是旧状态: ${placeErr.slice(0, 40)}`
          : running ? '生成器运行中, 完成后监视器自动刷新'
          : place.frozen > 0 ? `有 ${place.frozen} 条冻结的 "好", 请走 accept 流程`
          : place.job.ok === false ? `上次失败, 配置未改: ${(place.job.error || '').slice(0, 60)}`
          : dirty ? place.note : '选一个位置即可在监视器预览'}
      </div>
    </div>
  );
}
