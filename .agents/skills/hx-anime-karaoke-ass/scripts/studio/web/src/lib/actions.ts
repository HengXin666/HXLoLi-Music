/* 右键菜单 / 快捷键 共用的动作. 写动作一律走 POST /api/review, 页面本身不写盘. */
import { api, type Review } from './api';
import { clock } from './clock';
import { inRanges, lineRange, merge, summarize, toSel, fmtTc, type Range } from './sel';
import { toast, useStore, type Compare } from './store';
import { FX_IDS, TEXT_IDS, FILTER_IDS, type VisMap } from './tracks';

const S = () => useStore.getState();

export function selSummary() {
  const s = S();
  return summarize(s.ranges, s.lines, s.ix);
}

export function setSelection(ranges: Range[], caret?: number | null, anchor?: number | null) {
  const s = S();
  useStore.setState({
    ranges: merge(ranges),
    caret: caret === undefined ? s.caret : caret,
    anchor: anchor === undefined ? s.anchor : anchor,
  });
}

export function selectLine(li: number) {
  const s = S();
  const r = lineRange(li, s.lines, s.ix);
  setSelection([r], r[0], r[0]);
}

/** 参考 ASS 变了 (界面里选了 / ref.json 或 playlist.json 被改): 换 project (重建参考实例) + 重取两份 profile (门禁阈值来自参考) */
export async function reloadRef() {
  const p = await api.project();
  const [out, ref] = await Promise.all([api.profile('out'), p.ref_ass ? api.profile('ref') : Promise.resolve(null)]);
  useStore.setState({ project: p, out, ref });
}

/** 参考来源的人话 (界面各处共用, 带文字不只靠颜色) */
export const REF_SRC: Record<string, string> = { manual: '手动指定', playlist: 'playlist.json', unique: '唯一同名', ambiguous: '未定', error: '出错', none: '无' };
export const baseName = (p: string | null | undefined) => (p ?? '').split(/[\\/]/).pop() ?? '';  // 服务端 relpath 在 Windows 上是反斜杠

/** 右键点在选区外: 先把选区换成被点的字 (PR 的行为) */
export function ensureSelectedAt(g: number) {
  const s = S();
  if (!inRanges(s.ranges, g)) setSelection([[g, g]], g, g);
}

// ---------- 选区 -> explain (防抖)
let exTimer = 0;
let exSeq = 0;
useStore.subscribe((s, p) => {
  if (s.ranges === p.ranges && s.lines === p.lines) return;
  clearTimeout(exTimer);
  if (!s.ranges.length) { useStore.setState({ explain: null, explainBusy: false, explainErr: '' }); return; }
  const seq = ++exSeq;
  useStore.setState({ explainBusy: true });
  exTimer = window.setTimeout(async () => {
    const st = S();
    try {
      const items = await api.explain(toSel(st.ranges, st.lines, st.ix));
      if (seq === exSeq) useStore.setState({ explain: items, explainBusy: false, explainErr: '' });
    } catch (e) {
      // 不再静默: 检查器与状态栏要能说出为什么没有内容
      if (seq === exSeq) useStore.setState({ explain: null, explainBusy: false, explainErr: String((e as Error)?.message || e) });
    }
  }, 90);
});

export function explainCounts() {
  const ex = S().explain || [];
  let fx = 0, jp = 0, all = 0;
  for (const it of ex) {
    all += it.n;
    for (const [k, v] of Object.entries(it.counts)) {
      if (k.startsWith('fx')) fx += v;
      if (k === 'jp') jp += v;
    }
  }
  return { fx, jp, all };
}

// ---------- 回放
export function playSelection() {
  const sm = selSummary();
  if (!sm) return;
  useStore.setState({ loop: null, stopAt: sm.t1 });
  clock.seek(sm.t0);
  void clock.play();
}

export function loopSelection(rate = 1) {
  const sm = selSummary();
  if (!sm) return;
  useStore.setState({ loop: { t0: sm.t0, t1: sm.t1 }, stopAt: null, rate });
  clock.setRate(rate);
  clock.seek(sm.t0);
  void clock.play();
  toast(`循环 ${fmtTc(sm.t0)}-${fmtTc(sm.t1)}${rate !== 1 ? ` · ${rate}x` : ''}`);
}

export function clearLoop() {
  useStore.setState({ loop: null, stopAt: null });
}

// ---------- 批注与判定
export async function review(kind: Review['kind'], tags: string[] = [], text = '') {
  const s = S();
  const sm = selSummary();
  if (!sm) return;
  const rec = await api.postReview({ sel: toSel(s.ranges, s.lines, s.ix), t0: +sm.t0.toFixed(3), t1: +sm.t1.toFixed(3), kind, tags, text, frame: +clock.t().toFixed(3) });
  useStore.setState({ reviews: [...S().reviews, rec] });
  const what = kind === 'bad' ? `不行 · ${tags.join(' ') || text}` : kind === 'good' ? '好 (冻结)' : kind === 'redo' ? '换一个构想' : '批注';
  toast(`已记录 ${what} (${sm.label} ${sm.n} 字)`);
  return rec;
}

// ---------- 对比 / 只看
export function setCompare(c: Compare) {
  const s = S();
  if (!s.project?.ref_ass) return;
  if (c === 'ab') {
    if (s.compare === 'ab') useStore.setState({ abShow: s.abShow === 'out' ? 'ref' : 'out' });
    else useStore.setState({ compare: 'ab', abShow: 'ref' });
  } else useStore.setState({ compare: s.compare === c ? 'off' : c, abShow: 'out' });
}

export function soloOnly(which: 'text' | 'fx' | 'card') {
  const s = S();
  const ids: string[] = which === 'text' ? [...TEXT_IDS] : which === 'fx' ? [...FX_IDS] : ['card'];
  const already = FILTER_IDS.every((t) => !!s.vis[t]?.solo === ids.includes(t));
  const vis: VisMap = { ...s.vis };
  for (const t of FILTER_IDS) vis[t] = { ...vis[t], solo: already ? false : ids.includes(t) };
  useStore.setState({ vis });
}

export function onlyThisLine() {
  const s = S();
  const sm = selSummary();
  if (s.onlyUnits) { useStore.setState({ onlyUnits: null }); return; }
  if (!sm) return;
  useStore.setState({ onlyUnits: sm.lines.map((li) => s.lines[li].name) });
}

export function locate() {
  const sm = selSummary();
  if (!sm) return;
  const s = S();
  const pad = Math.max(0.5, (sm.t1 - sm.t0) * 0.25);
  const v0 = Math.max(0, sm.t0 - pad);
  const v1 = Math.min(s.duration || sm.t1 + pad, sm.t1 + pad);
  useStore.setState({ view: { v0, v1 } });
}

// ---------- 复制 / 导出
async function copyText(t: string) {
  try { await navigator.clipboard.writeText(t); }
  catch {
    const ta = document.createElement('textarea');
    ta.value = t;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
  }
  (window as unknown as { __lastCopy?: string }).__lastCopy = t;
}

export async function copyTimecode() {
  const sm = selSummary();
  const t = sm ? `${fmtTc(sm.t0)}-${fmtTc(sm.t1)}` : fmtTc(clock.t());
  await copyText(t);
  toast(`已复制时间码 ${t}`);
}

export async function copyEvents() {
  const s = S();
  const lns = new Set<number>();
  for (const it of s.explain || []) for (const g of it.groups) g.lines.forEach((l) => lns.add(l));
  if (s.menu?.hits) s.menu.hits.forEach((h) => lns.add(h.ln));
  if (!lns.size) return;
  const r = await api.events([...lns].sort((a, b) => a - b));
  const txt = r.events.map((e) => e.raw).join('\n');
  await copyText(txt);
  toast(`已复制 ${r.events.length} 条事件 (ASS 原文)`);
}

export async function exportFrame() {
  const frame = document.querySelector<HTMLElement>('[data-testid=frame-out]');
  const sub = frame?.querySelector<HTMLCanvasElement>('canvas[data-hidpi=monitor]');
  if (!sub) return;
  const c = document.createElement('canvas');
  c.width = sub.width;
  c.height = sub.height;
  const g = c.getContext('2d')!;
  g.fillStyle = '#000';
  g.fillRect(0, 0, c.width, c.height);
  const v = frame!.querySelector<HTMLVideoElement>('video');
  if (v && v.style.visibility !== 'hidden' && v.readyState >= 2) g.drawImage(v, 0, 0, c.width, c.height);
  g.drawImage(sub, 0, 0);
  const t = clock.t();
  const url = c.toDataURL('image/png');
  const a = document.createElement('a');
  a.href = url;
  a.download = `frame_${t.toFixed(2)}.png`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  toast(`已导出 ${a.download} (${c.width}x${c.height})`);
}

export function openInspector() {
  const hits = S().menu?.source === 'monitor' ? S().menu?.hits ?? null : null;
  if (!S().ranges.length && !hits?.length) return;
  useStore.setState({ inspector: true, inspectHits: hits });
}

export function noteAt(kind: 'note' | 'bad', tag?: string) {
  const m = S().menu;
  const x = m?.x ?? innerWidth / 2;
  const y = m?.y ?? innerHeight / 2;
  useStore.setState({ noteBox: { x, y, kind, tag } });
}

// ---------- 菜单结构 (三处共用)
export interface MItem {
  id: string; label: string; kbd?: string; disabled?: string | false; run?: () => void | Promise<unknown>;
  sub?: MItem[]; checked?: boolean;
}
export type MEntry = MItem | 'sep';

export const BAD_TAGS = ['看不清', '太吵', '太素', '出戏', '卡点不准', '盖字'];

export function menuHeader(): string {
  const s = S();
  const sm = selSummary();
  const hits = s.menu?.hits;
  const parts: string[] = [];
  if (s.menu?.source === 'monitor') parts.push(`此处 ${hits?.length ?? 0} 个事件`);
  if (sm) {
    const L = s.lines[sm.lines[0]];
    const text = sm.lines.length === 1 ? (sm.n === L.chars.length ? L.text : sm.text) : sm.text;
    parts.push(`${sm.n} 字 · ${sm.label} ${text.length > 14 ? text.slice(0, 14) + '…' : text} · ${sm.t0.toFixed(2)}-${sm.t1.toFixed(2)}s`);
  } else if (s.menu?.source !== 'monitor') parts.push('无选区');
  return parts.join(' · ');
}

export function menuItems(): MEntry[] {
  const s = S();
  const has = !!s.ranges.length;
  const noSel = has ? false : '没有选区: 先在歌词里选字, 或右键时间线片段';
  const noRef = s.project?.ref_ass ? false : s.project?.ref?.error ? `参考 ASS ${REF_SRC[s.project.ref.source]}: ${s.project.ref.error}` : '没有参考 ASS';
  const nEv = (s.explain || []).reduce((a, it) => a + it.n, 0) + (s.menu?.hits?.length ?? 0);
  const anySolo = (ids: readonly string[]) => FILTER_IDS.every((t) => !!s.vis[t]?.solo === ids.includes(t));
  return [
    { id: 'play', label: '播放选区', kbd: 'Space', disabled: noSel, run: playSelection },
    { id: 'loop', label: '循环选区', kbd: 'L', disabled: noSel, run: () => loopSelection(1) },
    { id: 'loop-half', label: '0.5x 循环', kbd: 'Shift+L', disabled: noSel, run: () => loopSelection(0.5) },
    'sep',
    { id: 'explain', label: '说明这里 …', kbd: 'E', disabled: has || s.menu?.hits?.length ? false : '没有选区, 此处也没有事件', run: openInspector },
    { id: 'note', label: '写批注 …', kbd: 'N', disabled: noSel, run: () => noteAt('note') },
    'sep',
    {
      id: 'bad', label: '不行', disabled: noSel, sub: [
        ...BAD_TAGS.map((t) => ({ id: `bad:${t}`, label: t, run: () => review('bad', [t]) })),
        { id: 'bad:custom', label: '自定义 …', run: () => noteAt('bad') },
      ],
    },
    { id: 'good', label: '好 (冻结)', kbd: 'G', disabled: noSel, run: () => review('good') },
    { id: 'redo', label: '换一个构想', kbd: 'R', disabled: noSel, run: () => review('redo') },
    'sep',
    {
      id: 'compare', label: '与参考对比', disabled: noRef, sub: [
        { id: 'cmp:ab', label: s.compare === 'ab' ? `A/B 切换 (现在: ${s.abShow === 'ref' ? '参考' : 'out'})` : 'A/B 切换', checked: s.compare === 'ab', run: () => setCompare('ab') },
        { id: 'cmp:wipe', label: '划变对比', checked: s.compare === 'wipe', run: () => setCompare('wipe') },
        { id: 'cmp:side', label: '左右并排', checked: s.compare === 'side', run: () => setCompare('side') },
      ],
    },
    {
      id: 'only', label: '只看', sub: [
        { id: 'only:text', label: '字层', checked: anySolo(TEXT_IDS), run: () => soloOnly('text') },
        { id: 'only:fx', label: 'FX', checked: anySolo(FX_IDS), run: () => soloOnly('fx') },
        { id: 'only:card', label: '卡片', checked: anySolo(['card']), run: () => soloOnly('card') },
        { id: 'only:line', label: '本句事件', checked: !!s.onlyUnits, disabled: s.onlyUnits ? false : noSel, run: onlyThisLine },
      ],
    },
    { id: 'locate', label: '在时间线中定位', kbd: 'F', disabled: noSel, run: locate },
    'sep',
    { id: 'copy-tc', label: '复制时间码', kbd: 'Ctrl+Shift+C', run: copyTimecode },
    { id: 'copy-ass', label: '复制所选事件 (ASS 原文)', disabled: nEv ? false : '选区里没有事件', run: copyEvents },
    { id: 'export', label: '导出当前帧 PNG', run: exportFrame },
  ];
}

/** 无菜单时的快捷键 (菜单打开时由菜单处理). 返回 true = 已处理 */
export function shortcut(e: KeyboardEvent): boolean {
  const k = e.key.toLowerCase();
  const has = !!S().ranges.length;
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && k === 'c') { void copyTimecode(); return true; }
  if (e.ctrlKey || e.metaKey || e.altKey) return false;
  if (e.code === 'Space') {
    if (S().stopAt != null || S().loop) { clearLoop(); clock.pause(); return true; }
    if (has && !clock.playing) playSelection(); else clock.toggle();
    return true;
  }
  if (!has && k !== 'escape') return false;
  if (k === 'l') { if (S().loop) { clearLoop(); clock.setRate(1); useStore.setState({ rate: 1 }); } else loopSelection(e.shiftKey ? 0.5 : 1); return true; }
  if (k === 'e') { openInspector(); return true; }
  if (k === 'n') { noteAt('note'); return true; }
  if (k === 'g') { void review('good'); return true; }
  if (k === 'r') { void review('redo'); return true; }
  if (k === 'f') { locate(); return true; }
  return false;
}
