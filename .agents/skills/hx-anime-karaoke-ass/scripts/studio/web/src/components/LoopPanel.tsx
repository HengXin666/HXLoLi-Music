import { useState } from 'react';
import { api } from '../lib/api';
import type { CandSet, CmpOpt, LoopReview } from '../lib/api';
import { reloadLoop, reloadRef } from '../lib/actions';
import { useStore } from '../lib/store';
import s from './RefPanel.module.css';
import l from './LoopPanel.module.css';

/** 处理状态的人话 (与 accept/reviewlog.py STATUS 同一套) */
export const STATUS_TXT: Record<string, string> = {
  open: '待处理', fixing: '在改', proposed: '等你看', done: '已关闭', 'need-human': '需要你定', dropped: '作废', noted: '批注',
};
const KIND_TXT: Record<string, string> = { bad: '不行', good: '好', redo: '换一个构想', note: '批注' };

/**
 * 看, 挑, 改, 证 (顶栏 "闭环" 打开的浮层).
 *  - 每条标注: 类型, 处理状态, 最近一次改动 (诊断 / 改了什么 / G2)
 *  - 换一个构想 / 不行: "生成候选" = 服务端 intake + 只重跑本单元出 2-3 个候选 (accept cands)
 *  - 候选: "看 A" = 监视器对比对象换成候选 A 并进 A/B; "冻结 A" = accept pick (picks.json -> 整首重跑 -> G2 + 隔离核对 -> 冻结)
 *  - 对比对象: 参考 / 上一版 / 候选 (没有参考时自动退到上一版)
 */
/*
 * Agent Notes: 看, 挑, 改, 证 面板 (标注状态 / 候选 A/B / 冻结 / 对比对象)
 * .agents/notes/implemented/feature/2026-11-17-karaoke-station-loop.md
 */
export default function LoopPanel() {
  const open = useStore((x) => x.loopOpen);
  const st = useStore((x) => x.loopState);
  const set = useStore((x) => x.set);
  const [err, setErr] = useState('');
  if (!open) return null;
  const job = st?.job;
  const busy = !!job?.running;
  const call = async (what: 'cmp' | 'cands' | 'pick', body: Record<string, unknown>) => {
    setErr('');
    try {
      await api.loopPost(what, body);
      if (what === 'cmp') await reloadRef();
      await reloadLoop();
    } catch (e) { setErr(String((e as Error).message || e)); }
  };
  const show = async (o: CmpOpt) => {
    await call('cmp', o.kind === 'cand' ? { kind: 'cand', issue: o.issue, c: o.c } : { kind: o.kind });
    useStore.setState({ compare: 'ab', abShow: 'ref' });
  };
  const candOf = (r: LoopReview): CandSet | undefined => (r.issue ? st?.cands[r.issue] : undefined);
  const cmp = st?.cmp;
  return (
    <div className={`${s.panel} ${l.panel}`} data-testid="loop-panel" role="dialog" aria-label="看, 挑, 改, 证">
      <div className={s.head}>
        <b>看 · 挑 · 改 · 证</b>
        <span className={s.grow} />
        <button className={s.x} onClick={() => set({ loopOpen: false })} aria-label="关闭" data-testid="loop-close">×</button>
      </div>
      <div className={s.now} data-testid="cmp-now" data-kind={cmp?.kind}>
        <b>对比对象</b><span className={s.name}>{cmp ? `${cmp.label}${cmp.auto ? ' (自动)' : ''}` : '载入中'}</span>
        <span className={s.src}>
          {(cmp?.options ?? []).filter((o) => o.kind !== 'cand').map((o) => (
            <button key={o.kind} className={l.mini} data-testid={`cmp-${o.kind}`} disabled={busy} data-cur={cmp?.kind === o.kind || undefined} onClick={() => void show(o)}>{o.label}</button>
          ))}
        </span>
      </div>
      {!st?.accept && <div className={s.why} data-testid="loop-noaccept">工程还没进 accept (review/accept/state.json): 第一次 "生成候选" 时自动 init + build</div>}
      <ul className={`${s.list} ${l.list}`} data-testid="loop-list">
        {(st?.reviews ?? []).map((r) => {
          const cs = candOf(r);
          const last = r.changes[r.changes.length - 1];
          const canGen = (r.kind === 'redo' || r.kind === 'bad') && r.status !== 'done' && r.status !== 'dropped' && !(cs && cs.state === 'open');
          return (
            <li key={r.id} className={l.row} data-testid="loop-row" data-id={r.id} data-kind={r.kind} data-status={r.status} data-issue={r.issue || undefined}>
              <div className={l.line}>
                <span className={l.kind} data-kind={r.kind}>{KIND_TXT[r.kind]}</span>
                <span className={s.name}>{r.tags.join(' ')}{r.text ? ` ${r.text}` : ''} {r.t0.toFixed(2)}-{r.t1.toFixed(2)}s</span>
                <span className={l.st} data-testid="loop-status" data-status={r.status} title={r.status_src === 'default' ? '还没被 accept 回写, 按类型推定' : `问题 ${r.issue ?? '-'}`}>
                  {STATUS_TXT[r.status] ?? r.status}{r.issue ? ` · ${r.issue}` : ''}
                </span>
                {canGen && <button className={l.mini} disabled={busy} data-testid="cand-gen" onClick={() => void call('cands', r.id.startsWith('issue:') ? { issue: r.issue } : { review: r.id })}>生成候选</button>}
              </div>
              {last && last.what && <div className={l.chg} data-testid="loop-change" title={r.changes.map((c) => `${c.at ?? ''} ${c.status ?? ''} ${c.diag ?? ''} ${c.what ?? ''}`).join('\n')}>
                {last.g2 ? `G2 ${last.g2.ok ? '通过' : '未过'}${last.g2.isolation ? ' · 隔离核对 ' + last.g2.isolation : ''} · ` : ''}{last.what}
              </div>}
              {cs && (
                <div className={l.cands} data-testid="cand-set" data-issue={cs.issue} data-state={cs.state}>
                  {cs.items.map((c) => {
                    const cur = cmp?.kind === 'cand' && cmp.issue === cs.issue && cmp.c === c.id;
                    return (
                      <span key={c.id} className={l.cand} data-cur={cur || undefined} data-picked={cs.picked === c.id || undefined} title={`${c.why}\n${c.n} 个事件, 只重跑本单元 ${c.secs}s`}>
                        <b>{c.id}</b>
                        {cs.state === 'open' && <>
                          <button className={l.mini} disabled={busy} data-testid={`cand-show-${c.id}`} onClick={() => void show({ kind: 'cand', issue: cs.issue, c: c.id, label: '' })}>看</button>
                          <button className={l.mini} disabled={busy} data-testid={`cand-pick-${c.id}`} onClick={() => void call('pick', { issue: cs.issue, c: c.id })}>冻结</button>
                        </>}
                        {cs.picked === c.id && <span className={l.ok}>已选</span>}
                      </span>
                    );
                  })}
                  {cs.siblings.length > 0 && <span className={l.note} title={cs.siblings.join(', ')}>重复歌词: 只改这一处</span>}
                </div>
              )}
            </li>
          );
        })}
        {st && st.reviews.length === 0 && <li className={s.why}>还没有标注</li>}
      </ul>
      <div className={s.msg} data-testid="loop-msg" data-error={err || job?.ok === false ? 'y' : undefined} data-job={job?.running ? 'running' : job?.ok === true ? 'ok' : job?.ok === false ? 'fail' : 'idle'} title={job?.out || undefined}>
        {err || (job?.running ? `${job.kind === 'pick' ? '冻结中 (整首重跑 + G2 + 隔离核对)' : '生成候选中 (只重跑本单元)'} …`
          : job?.ok === false ? `${job.kind} 失败: ${job.error}` : job?.ok ? `${job.kind === 'pick' ? '冻结完成, G2 通过' : '候选已生成'}` : '')}
      </div>
    </div>
  );
}
