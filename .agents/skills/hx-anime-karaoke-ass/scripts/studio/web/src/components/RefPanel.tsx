import { useState } from 'react';
import { api } from '../lib/api';
import { baseName, reloadRef, REF_SRC } from '../lib/actions';
import { syncFail, syncOk, useStore } from '../lib/store';
import s from './RefPanel.module.css';

const WHY: Record<string, string> = {
  manual: '工程目录 ref.json 手动指定',
  playlist: 'playlist.json 里网站发布的那份',
  unique: 'static/music 下文件名含歌名的只有这一份',
  ambiguous: '多份候选, 没有明确来源, 没有选',
  error: '指定的来源有问题, 没有选',
  none: 'static/music 下没有文件名含歌名的 .ass',
};

/**
 * 参考 ASS 面板 (顶栏 "参考" 打开的浮层). 列出全部候选 (文件名 / Dialogue 条数 / 修改时间), 写明现在用哪份、怎么定的.
 * 不替人挑: "用这份" = 写工程 ref.json (服务端记指定时间), 之后按热更新重取. 门禁阈值来自参考, 所以选错 = 门禁全错.
 */
export default function RefPanel() {
  const open = useStore((x) => x.refOpen);
  const p = useStore((x) => x.project);
  const set = useStore((x) => x.set);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  if (!open || !p) return null;
  const r = p.ref;
  const pick = async (path: string | null) => {
    setBusy(true);
    setErr('');
    const msg = (e: unknown) => String(e instanceof Error ? e.message : e);
    // 两步分开报: 写 ref.json 失败 = 没指定成; 写成了但重取失败 = 已指定但界面还是旧的 (不能说成 "指定失败")
    try { await api.chooseRef(path); }
    catch (e) { setErr(`${path === null ? '清除失败' : '指定失败'}: ${msg(e)}`); setBusy(false); return; }
    // path=null 是清除: 服务端从 ref.json 删掉这项 (删空则删文件), 不是 "写入", 文案分开
    const saved = path === null ? '已清除手动指定 (已从 ref.json 移除)' : '选择已保存 (已写入 ref.json)';
    try { await reloadRef(); syncOk('ref'); }
    catch (e) { syncFail('ref', e); setErr(`${saved}, 不用再点; 但界面刷新失败, 显示的仍是旧参考: ${msg(e)} · 点顶栏「参考 ASS 未刷新」重试`); }
    finally { setBusy(false); }
  };
  return (
    <div className={s.panel} data-testid="ref-panel" data-source={r.source} role="dialog" aria-label="参考 ASS">
      <div className={s.head}>
        <span>参考 ASS</span>
        <span className={s.grow} />
        <button className={s.x} onClick={() => set({ refOpen: false })} aria-label="关闭" data-testid="ref-close">×</button>
      </div>
      <div className={s.now} data-testid="ref-current">
        <b>现在用</b> {p.ref_path ? baseName(p.ref_path) : '(无)'}
        <span className={s.src}>{REF_SRC[r.source]}</span>
      </div>
      <div className={s.why} data-testid="ref-why" data-error={r.error ? 'y' : undefined}>
        {r.error ?? WHY[r.source]}{r.source === 'manual' && r.set_at ? ` · 指定于 ${r.set_at}` : ''}
      </div>
      <ul className={s.list}>
        {r.candidates.map((c) => {
          const cur = c.path === p.ref_path;
          return (
            <li key={c.path} className={s.row} data-cur={cur || undefined} data-testid="ref-cand" data-path={c.path}>
              <span className={s.name} title={c.path}>{baseName(c.path)}</span>
              <span className={s.meta}>{c.dialogues} 条 · 改于 {c.mtime}</span>
              {cur ? <span className={s.tag}>当前</span> : (
                <button disabled={busy} onClick={() => void pick(c.path)} data-testid="ref-use">用这份</button>
              )}
            </li>
          );
        })}
      </ul>
      {/* ref.json 出错 (坏 JSON / 文件不存在 / 不在候选集) 也要能在界面里清掉, 否则只能手删文件; 按服务端 err_kind 判断, 不看错误文字 */}
      {(r.source === 'manual' || r.err_kind === 'ref_json') && (
        <button className={s.clear} disabled={busy} onClick={() => void pick(null)} data-testid="ref-clear">清除手动指定 (回到 playlist / 唯一同名)</button>
      )}
      <div className={s.msg} data-testid="ref-msg" data-error={err ? 'y' : undefined}>{err || (busy ? '写入中…' : '')}</div>
    </div>
  );
}
