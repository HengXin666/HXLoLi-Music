import { useCallback, useEffect, useMemo, useState } from 'react';
import { designApi, type Design, type DesignLine } from '../lib/api';
import { clock } from '../lib/clock';
import s from './DesignPanel.module.css';

/**
 * 设计稿面板: design.md 的每一行 = 歌词原文 + 补丁 + 文字描述. 先改设计稿, 再渲染.
 * - 跟随: 显示播放头所在行的设计 (卡片); "全部" 列出所有行, 点行号跳到该句
 * - 编辑: 整节文本改完保存 (PUT /api/design), 服务端解析校验, 问题标黄但照样存
 * - 文件被别处改了 (mtime 不符) 服务端拒收, 这里提示刷新
 */
const fmt = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(2).padStart(5, '0')}`;

function Patched({ L }: { L: DesignLine }) {
  // 原文按补丁切片; 全角空格保留成词组间距
  const parts: { t: string; fx?: string[] }[] = [];
  const jp = L.jp.replace(/\([^)]*\)/g, '');
  let k = 0; // 去空白后的下标
  let buf = '';
  let open: DesignLine['patches'][number] | undefined;
  const flush = (fx?: string[]) => { if (buf) parts.push({ t: buf, fx }); buf = ''; };
  for (const ch of jp) {
    if (/\s|　/.test(ch)) { if (!open) { flush(); parts.push({ t: '　' }); } continue; }
    const p = L.patches.find((x) => x.start === k);
    if (p && !open) { flush(); open = p; }
    buf += ch;
    k++;
    if (open && k === open.end) { flush(open.fx); open = undefined; }
  }
  flush(open?.fx);
  return (
    <div className={s.jp}>
      {parts.map((p, i) => p.fx
        ? <span key={i} className={s.patch} style={{ borderColor: L.color ?? undefined }}>
            <span className={s.ptext}>{p.t}</span>
            <span className={s.chips}>{p.fx.map((f) => <span key={f} className={s.chip}>{f}</span>)}</span>
          </span>
        : <span key={i} className={s.plain}>{p.t}</span>)}
    </div>
  );
}

function Card({ L, onSave, busy }: { L: DesignLine; onSave: (body: string) => Promise<void>; busy: boolean }) {
  const [edit, setEdit] = useState<string | null>(null);
  useEffect(() => { setEdit(null); }, [L.key]);
  if (edit !== null) {
    return (
      <div className={s.card}>
        <textarea className={s.ta} value={edit} onChange={(e) => setEdit(e.target.value)} spellCheck={false} data-scroll-ok />
        <div className={s.row}>
          <button className={s.btn} disabled={busy} onClick={() => { void onSave(edit).then(() => setEdit(null)).catch(() => undefined); }}>保存</button>
          <button className={s.btn2} onClick={() => setEdit(null)}>取消</button>
          <span className={s.dim}>保存后渲染器照这一节重做这一行</span>
        </div>
      </div>
    );
  }
  return (
    <div className={s.card} data-bad={L.errors.length ? 1 : undefined}>
      <div className={s.chead}>
        <button className={s.key} onClick={() => clock.seek(L.t0)} title="跳到这一句">{L.key}</button>
        <span className={s.dim}>{fmt(L.t0)}–{fmt(L.t1)}</span>
        <span className={s.role}>{L.role}</span>
        <span className={s.grow} />
        <button className={s.btn2} onClick={() => setEdit(`${L.head}\n\n${L.raw}`)}>编辑</button>
      </div>
      <Patched L={L} />
      <div className={s.cn}>{L.cn}</div>
      {L.yijing && (
        <div className={s.yj}>
          <div><b>意境</b> {L.yijing}</div>
          <div><span>整行</span>{L.whole}</div>
          <div><span>每字</span>{L.each}</div>
        </div>
      )}
      <div className={s.fields}>
        <span>色</span><span><i className={s.sw} style={{ background: L.color ?? 'transparent' }} />{L.color} {L.color_note}</span>
        <span>入场</span><span>{L.entry}</span>
        <span>唱到</span><span>{L.hit}</span>
        <span>出场</span><span>{L.exit}</span>
      </div>
      <ul className={s.phr}>
        {L.phrases.map((p, i) => (
          <li key={i}><b>{p.on}</b> <span className={s.fxs}>{p.fx.join(' ')}</span><div className={s.desc}>{p.desc}</div></li>
        ))}
      </ul>
      {L.why && <div className={s.why}>为什么: {L.why}</div>}
      {L.errors.map((e, i) => <div key={i} className={s.err}>{e}</div>)}
    </div>
  );
}

export default function DesignPanel() {
  const [d, setD] = useState<Design | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [all, setAll] = useState(false);
  const [cur, setCur] = useState<string | null>(null);

  const load = useCallback(() => designApi.get().then((x) => { setD(x); setErr(null); }).catch((e) => setErr(String(e.message ?? e))), []);
  useEffect(() => {
    void load();
    const on = () => { void load(); };
    window.addEventListener('hx-design', on);
    return () => window.removeEventListener('hx-design', on);
  }, [load]);

  const lines = useMemo(() => d?.lines ?? [], [d]);
  useEffect(() => clock.subscribe((t) => {
    let k: string | null = null;
    for (const L of lines) if (t >= L.t0 - 0.05) k = L.key; // 最后一个已开始的行
    setCur((c) => (c === k ? c : k));
  }), [lines]);

  const save = async (key: string, body: string) => {
    setBusy(true);
    try { setD(await designApi.putSection(key, body, d?.mtime)); setErr(null); }
    catch (e) { setErr(String((e as Error).message)); throw e; }
    finally { setBusy(false); }
  };

  const bad = lines.filter((L) => L.errors.length).length;
  const L = lines.find((x) => x.key === cur) ?? lines[0];
  return (
    <div className={s.panel} data-testid="design-panel">
      <div className={s.head}>
        <span>设计稿</span>
        {d?.exists && <span className={s.dim}>{lines.length} 行{bad ? `, ${bad} 行有问题` : ''}</span>}
        <span className={s.grow} />
        <button className={s.tog} data-on={!all || undefined} onClick={() => setAll(false)}>跟随</button>
        <button className={s.tog} data-on={all || undefined} onClick={() => setAll(true)}>全部</button>
      </div>
      <div className={s.body} data-scroll-ok>
        {err && <div className={s.err}>{err}</div>}
        {d && !d.exists && <div className={s.empty}>工程里还没有 design.md. 先照 scripts/kfx/kfx_README.md 写设计稿, 再渲染.</div>}
        {d?.errors.map((e, i) => <div key={i} className={s.err}>{e}</div>)}
        {d?.exists && !all && L && <Card L={L} busy={busy} onSave={(b) => save(L.key, b)} />}
        {d?.exists && all && (
          <>
            {(d.motifs?.length ?? 0) > 0 && (
              <div className={s.global}><b>意象表</b>
                {d.motifs!.map((m) => <div key={m.name}><b>{m.name}</b> · {m.src} · {m.who} · 整行: {m.whole} · 每字: {m.each}</div>)}
              </div>
            )}
            {d.global.length > 0 && <div className={s.global}><b>全局</b>{d.global.map((g, i) => <div key={i}>{g}</div>)}</div>}
            {lines.map((x) => (
              <div key={x.key} className={s.mini} data-cur={x.key === cur || undefined} data-bad={x.errors.length ? 1 : undefined}>
                <button className={s.key} onClick={() => clock.seek(x.t0)}>{x.key}</button>
                <div><Patched L={x} /><div className={s.dim}>{x.yijing || x.why} · 出场 {x.exit}</div></div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
