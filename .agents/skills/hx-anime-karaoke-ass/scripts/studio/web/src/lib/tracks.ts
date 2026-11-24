/* 时间线轨定义 + 轨显示状态 (眼/独显/锁) -> 监视器 ASS 过滤. 轨的归属规则与服务端 analysis.track_of 一致. */

export type TrackId =
  | 'overview' | 'ruler' | 'mv' | 'wave' | 'beat'
  | 'jp' | 'rb' | 'cn'
  | 'fx0' | 'fx1' | 'fx2' | 'fx3' | 'fx4' | 'fx5' | 'fx6' | 'fx7' | 'fx8'
  | 'card' | 'review' | 'density';

export interface TrackDef {
  id: TrackId; name: string; title?: string; group?: 'text' | 'fx'; def: number; min: number;
  filter?: boolean; // 影响监视器 ASS 渲染 (眼/S/锁)
  eye?: boolean; // 有眼睛但不进 ASS 过滤 (mv: 关掉即监视器不画视频). 纯时间线轨 (波形/节拍/密度/标注) 不给眼睛, 免得骗人
  lockable?: boolean;
  fixed?: boolean; // 不可拖高
}

/**
 * FX 层的职责 (assfx 的 "三明治" 层序). FX 事件的层号与 TEXT_LIFT 无关 (只抬 ly: 事件), 字层按样式归轨,
 * 所以 TEXT_LIFT=0 (字夹在 FX 中间) 与缺省 20 (字在 FX 之上) 的工程都按下面的层义读:
 *   0 字后 (氛围床 bg_drift/bg_frames, 母题底光, 逐字字后光晕 anim.py ev(0))
 *   1-2 与字底/字身同层 (JP/RB/CN 的描边与正文在 1-2), 3 跳字 (anim.py 逐字 pop ev(3)), 4 逐字辉光 (anim.py ev(4) blur 光)
 *   5 近字母题粒子 (deco/motifs layer=5), 6 迸散 (motifs burst layer=6), 7 前景主体 (母题主图形, 条数最多), 8 最上闪光 (fx.py sparkle layer=8)
 */
export const FX_ROLE: [string, string][] = [
  ['字后底光', '字的下面: 氛围床、母题底光、逐字字后光晕'],
  ['字底', '与字描边同层 (JP/RB/CN 的底层)'],
  ['字身', '与正文同层'],
  ['跳字', '逐字弹跳 / 换形的字层'],
  ['辉光', '逐字高光的模糊辉光'],
  ['近字粒子', '贴着字飘的母题粒子 (字前)'],
  ['迸散', '卡点迸散 / burst (字前)'],
  ['前景主体', '母题主图形, 字前条数最多的一层'],
  ['顶层闪光', '最上层的闪点 / sparkle'],
];

export const FX_IDS = ['fx0', 'fx1', 'fx2', 'fx3', 'fx4', 'fx5', 'fx6', 'fx7', 'fx8'] as const;
export const TEXT_IDS = ['jp', 'rb', 'cn'] as const;
export const FILTER_IDS: TrackId[] = [...TEXT_IDS, ...FX_IDS, 'card'];

export const TRACKS: TrackDef[] = [
  { id: 'overview', name: '全曲', def: 12, min: 12, fixed: true },
  { id: 'ruler', name: '', def: 20, min: 20, fixed: true },
  { id: 'mv', name: 'MV', title: 'MV 视频轨: 眼睛关掉则监视器只画字幕, 不画视频', def: 20, min: 10, eye: true },
  { id: 'wave', name: '波形', def: 40, min: 18 },
  { id: 'beat', name: '节拍', def: 20, min: 8 },
  { id: 'jp', name: 'JP', group: 'text', def: 28, min: 14, filter: true, lockable: true },
  { id: 'rb', name: 'RB', group: 'text', def: 22, min: 12, filter: true, lockable: true },
  { id: 'cn', name: 'CN', group: 'text', def: 24, min: 12, filter: true, lockable: true },
  ...FX_IDS.map((id, i) => ({ id, name: `${i} ${FX_ROLE[i][0]}`, title: `FX 层 ${i} · ${FX_ROLE[i][0]}: ${FX_ROLE[i][1]}`, group: 'fx' as const, def: 26, min: 14, filter: true, lockable: true })),
  { id: 'card', name: '卡片', title: '片头/片尾卡片 (CARD/TITLE/PRO 样式与 card:/fx:title|pro|mid|out 事件)', def: 20, min: 10, filter: true, lockable: true },
  { id: 'review', name: '标注', title: '标注 (review): 橙 = 不行, 绿 = 好 (冻结), 紫 = 换一个构想, 蓝 = 备注. 点一下选中它标的字', def: 20, min: 10 },
  { id: 'density', name: '密度', def: 60, min: 28 },
];

/*
 * Agent Notes: 轨头眼睛只给对监视器真有作用的轨 (filter 轨与 mv); 纯时间线轨不给眼睛
 * .agents/notes/implemented/feature/2026-11-11-karaoke-studio-track-visibility.md
 */
export const hasEye = (t?: TrackDef): boolean => !!(t?.filter || t?.eye);

export const GROUP_NAME = { text: '字层 JP/RB/CN', fx: 'FX 0-8 (9 层, 字后→字前)' } as const;

export interface Vis { eye: boolean; solo: boolean; lock: boolean }
export type VisMap = Record<string, Vis>;

export const defaultVis = (): VisMap => Object.fromEntries(TRACKS.map((t) => [t.id, { eye: true, solo: false, lock: false }]));

export function visible(vm: VisMap, id: string): boolean {
  const anySolo = FILTER_IDS.some((t) => vm[t]?.solo);
  const v = vm[id];
  if (!v) return true;
  return v.eye && (!anySolo || v.solo);
}

const CARD_STYLES = new Set(['CARD', 'CARDCN', 'TITLE', 'TLAT', 'PRO', 'PROCN']);
const CARD_FX = new Set(['fx:title', 'fx:pro', 'fx:mid', 'fx:out']);

export function trackOf(style: string, layer: number, name: string): TrackId | null {
  if (style === 'FX') {
    if (name.startsWith('card:') || CARD_FX.has(name)) return 'card';
    return FX_IDS[Math.max(0, Math.min(8, layer))];
  }
  if (style === 'JP' || style === 'LAT') return 'jp';
  if (style === 'RB') return 'rb';
  if (style === 'CN') return 'cn';
  if (CARD_STYLES.has(style)) return 'card';
  // 工程自定义样式 (如 NAME): 按 Name 前缀归轨, 不然眼睛 / 独显永远藏不掉它
  if (name.startsWith('card:')) return 'card';
  if (name.startsWith('fx:')) return FX_IDS[Math.max(0, Math.min(8, layer))];
  if (name.startsWith('ly:')) return 'jp';
  return null;
}

/** 按轨显示状态与 "本句事件" 过滤 ASS 文本. 返回过滤后文本与保留的 Dialogue 条数 */
export function filterAss(text: string, vm: VisMap, onlyUnits: string[] | null): { text: string; kept: number; total: number } {
  const anyHidden = FILTER_IDS.some((t) => !visible(vm, t));
  const lines = text.split(/\r?\n/);
  let kept = 0, total = 0;
  if (!anyHidden && !onlyUnits) {
    for (const l of lines) if (l.startsWith('Dialogue:')) total++;
    return { text, kept: total, total };
  }
  const only = onlyUnits ? new Set(onlyUnits) : null;
  const out: string[] = [];
  for (const l of lines) {
    if (!l.startsWith('Dialogue:')) { out.push(l); continue; }
    total++;
    const p = l.slice(9).split(',', 5);
    const layer = parseInt(p[0], 10) || 0;
    const style = (p[3] || '').trim();
    const name = (p[4] || '').trim();
    const tr = trackOf(style, layer, name);
    if (tr && !visible(vm, tr)) continue;
    if (only) {
      const u = name.includes(':') ? name.slice(name.indexOf(':') + 1) : name;
      if (!only.has(u)) continue;
    }
    kept++;
    out.push(l);
  }
  return { text: out.join('\n'), kept, total };
}

/** 标注类型 -> 颜色/中文 (时间线标注轨, 歌词下划线, 检查器共用) */
export const REVIEW_KIND: Record<'bad' | 'good' | 'redo' | 'note', { c: string; cn: string }> = {
  bad: { c: '#f0a24a', cn: '不行' }, good: { c: '#59c38a', cn: '好 (冻结)' }, redo: { c: '#b48cff', cn: '换一个构想' }, note: { c: '#6ea8ff', cn: '备注' },
};
