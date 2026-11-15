export interface FontInfo { file: string; url: string; families: string[]; regular?: boolean }
/** out.ass 用到但 fonts 目录里对不上名字的字体 (服务端算, 忽略大小写比族名/全名/PostScript 名). libass 会用后备字体画: 能显示, 字形可能不对. 不是 fatal. */
export interface FontMissing { name: string; uses: number; line: number; via: string[] }
export interface EdlSegment { kind: 'orig' | 'reuse' | 'still' | 'none'; t0: number; t1: number | null; src: string; src_t0: number }
export interface Edl { version: number; source: 'file' | 'default' | 'none'; segments: EdlSegment[] }
export interface Section { id: string; lines: number[]; budget?: number; why?: string }
/** 参考 ASS 用的是哪份, 怎么定的 (服务端 refpick.py). 不挑 "更好的那版": 只认 ref.json / playlist.json / 唯一同名 */
export type RefSource = 'manual' | 'playlist' | 'unique' | 'ambiguous' | 'error' | 'none';
export interface RefCand { path: string; dialogues: number; mtime: string }
/** err_kind: error 的来源, 前端按它分支 (不看 error 文字). ref_json = 工程 ref.json (可在面板清除) / playlist / candidates = 多份未定 */
export type RefErrKind = 'ref_json' | 'playlist' | 'candidates';
export interface RefInfo { source: RefSource; error: string | null; err_kind?: RefErrKind | null; set_at: string | null; candidates: RefCand[] }
export interface Project {
  dir: string; anime: string; song: string; duration: number;
  audio: (string | null)[]; video: string | null;
  out_ass: string; ref_ass: string | null; ref_path: string | null; ref: RefInfo; audio_error?: string | null;
  fonts: FontInfo[]; fonts_missing?: FontMissing[]; fonts_unparsed?: string[]; edl: Edl; sections: Section[]; octopus: string | null;
}
export interface LyricChar {
  i: number; ch: string; s: number; e: number; x: number; w: number;
  ruby: string; unit: number | null; box?: [number, number, number, number]; mora: [string, number, number][];
}
export interface LyricLine {
  name: string; line: number | null; label: string; t: [number, number]; band: number[];
  text: string; role: 'high' | 'carrier' | 'rest' | null; technique: string | null; cn: string;
  fx: number; fn: string | null; chars: LyricChar[];
  jp_y: number | null; fs: number; ref_fx: number;
}
export interface Profile {
  fx_count: number; fx_bytes: number; line_min: number; line_median: number; line_max: number;
  span: [number, number]; coverage: number; alive_median: number; front_ratio: number;
  stepped: number; peak_ratio: number; skeletons: number; jp_frz: number; jp_fax_frx: number;
  alive_curve: number[]; per_line: Record<string, number>;
}
export interface JudgeRow { no: number; item: string; state: 'OK' | 'BAD' | 'SKIP' }
export interface ProfileRes { which: string; step: number; profile: Profile; judge?: JudgeRow[] }
export interface Peaks { rate: number; peaks: number[] }
export interface Clip { track: string; unit: string; t0: number; t1: number; n: number; layers: number[]; fns: [string, number][] }
export interface Beats { bpm: number | null; grid: number[]; onset: number[]; sub: number[]; strength: Record<string, number> }
export interface SelRange { line: number; from: number; to: number }
export interface Src { file: string; line: number | null; note?: string }
export interface ExplainGroup {
  fn: string; ambiguous: boolean; candidates: string[]; style: string; layer: number; n: number; tags: string;
  lines: number[]; src: Src[];
}
export interface ExplainItem {
  line: number; name: string; label: string; text: string; whole: boolean; t0: number; t1: number; n: number;
  counts: Record<string, number>; groups: ExplainGroup[];
  arc: { role: string | null; technique: string | null; idea: string | null; why: string | null; anchors: { kind: string; ref: string }[] | null;
    highlight: unknown; thread: { mode?: string; state?: string } | null; section: string | null; section_why: string | null };
  params: Record<string, unknown>;
  emit: { fn: string; n: number; layers: number[]; t: [number, number]; src: Src }[];
  music: { onset: { t: number; s: number | null }[]; sub: number[]; beats: number; bpm: number | null };
  ref: { window: number; line: number; cat_window: Record<string, number>; cat_line: Record<string, number>;
    out_window: Record<string, number>; out_line: Record<string, number> };
}
export interface HitEvent { ln: number; style: string; layer: number; name: string; t0: number; t1: number; box: number[]; track: string; fns: string[] }
export interface Review { id: string; sel: SelRange[]; t0: number; t1: number; kind: 'bad' | 'good' | 'redo' | 'note'; tags: string[]; text: string; frame?: number | null; created: string }
export interface RawEvent { ln: number; layer: number; t0: number; t1: number; style: string; name: string; text: string; owners: string[]; raw?: string }

/** 歌词位置预设. 坐标与位移全由服务端 (assfx/text/placement.py) 算, 前端只按矩形与位移画, 不复算布局. */
export interface Preset { v: 'top' | 'middle' | 'bottom'; h: 'left' | 'center' | 'right'; order: 'jp_top' | 'cn_top'; gap: 'tight' | 'normal' | 'loose' }
export interface PlaceBlock { src: [number, number, number, number]; dx: number; dy: number }
export interface PlaceLine { name: string; t: [number, number]; jp: PlaceBlock; cn: PlaceBlock | null }
export interface PlaceJob { running: boolean; ok: boolean | null; error: string | null; preset: Preset | null; seq: number }
export interface PlacementRes {
  current: Preset; default: Preset; source: 'file' | 'default'; enums: { v: Preset['v'][]; h: Preset['h'][]; order: Preset['order'][]; gap: Preset['gap'][] };
  job: PlaceJob; note: string; frozen: number; candidate?: Preset; lines?: PlaceLine[]; rows_missing?: number;
}

async function j<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} ${r.status}`);
  return r.json() as Promise<T>;
}

export const api = {
  project: () => j<Project>('/api/project'),
  lyrics: () => j<{ lines: LyricLine[] }>('/api/lyrics').then((r) => r.lines),
  profile: (which: 'out' | 'ref') => j<ProfileRes>(`/api/profile?which=${which}`),
  peaks: () => j<Peaks>('/api/peaks'),
  edl: () => j<Edl>('/api/edl'),
  clips: () => j<{ clips: Clip[]; beats: Beats }>('/api/clips'),
  explain: (sel: SelRange[]) => j<{ items: ExplainItem[] }>(`/api/explain?sel=${encodeURIComponent(JSON.stringify(sel))}`).then((r) => r.items),
  hit: (t: number, x: number, y: number) => j<{ events: HitEvent[] }>(`/api/hit?t=${t}&x=${x}&y=${y}`).then((r) => r.events),
  reviews: () => j<{ items: Review[] }>('/api/review').then((r) => r.items),
  events: (lines: number[], raw = true) => j<{ total: number; events: RawEvent[] }>(`/api/events?lines=${lines.join(',')}&raw=${raw ? 1 : 0}&limit=20000`),
  postReview: async (b: Omit<Review, 'id' | 'created'>) => {
    const r = await fetch('/api/review', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(b) });
    if (!r.ok) throw new Error(`review ${r.status}`);
    return r.json() as Promise<Review>;
  },
  placement: (cand?: Preset) => j<PlacementRes>(`/api/placement${cand ? `?${new URLSearchParams(cand as unknown as Record<string, string>)}` : ''}`),
  applyPlacement: async (p: Preset) => {
    const r = await fetch('/api/placement', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(p) });
    const b = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error((b as { error?: string }).error || `placement ${r.status}`);
    return b as { started: boolean; preset: Preset };
  },
  chooseRef: async (ass: string | null) => {
    const r = await fetch('/api/ref', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ass }) });
    const t = await r.text();
    let b: { error?: string } = {};
    try { b = JSON.parse(t); } catch { /* 非 JSON: 下面按状态码报 */ }
    if (!r.ok) throw new Error(b.error || `/api/ref ${r.status}${t ? ': ' + t.slice(0, 120) : ''}`);
    return b as Pick<Project, 'ref_ass' | 'ref_path' | 'ref'>;
  },
  // 不查 r.ok 的话 404/500 的错误 JSON 会被当成字幕喂给 libass (画面空白, 无任何提示)
  assText: async (which: 'out' | 'ref') => {
    const r = await fetch(`/api/ass/${which}`, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`/api/ass/${which} ${r.status}`);
    return r.text();
  },
};

/** 服务端文件变化推送. onConn: 连上 true / 断开 false (断开期间的改动收不到, 界面要说).
 *  重连时服务端先发 hello{state}: 与断开前最后一次 state 比对, 有变化的项当作 changed 补发, 免得服务器重启期间改过的 out.ass 永不刷新. */
export function watch(onChange: (what: string[]) => void, onConn?: (up: boolean) => void): () => void {
  let ws: WebSocket | null = null;
  let stop = false;
  let held = false;   // 测试钩子: 断开后暂不重连
  let retry = 0;
  let last: Record<string, number> | null = null;
  const open = () => {
    if (stop || held) return;
    const w = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/watch`);
    ws = w;
    w.onopen = () => { retry = 0; onConn?.(true); };
    w.onmessage = (m) => {
      let d: { type?: string; what?: string[]; state?: Record<string, number> };
      try { d = JSON.parse(m.data as string); } catch { return; }
      if (d.type !== 'hello' && d.type !== 'changed') return;
      const prev = last;
      if (d.state) last = d.state;
      const what = d.type === 'changed' ? d.what ?? [] : prev && d.state ? Object.keys(d.state).filter((k) => d.state![k] !== prev[k]) : [];
      if (what.length) onChange(what);
    };
    w.onclose = () => {
      if (ws !== w) return;
      ws = null;
      if (stop) return;
      onConn?.(false);
      if (!held) setTimeout(open, Math.min(5000, 500 * 2 ** retry++));
    };
  };
  // e2e HR3 用: drop() 断开且不自动重连, release() 放开重连. 不影响正常使用
  (window as unknown as { __hxWatch: unknown }).__hxWatch = {
    drop: () => { held = true; ws?.close(); },
    release: () => { if (held) { held = false; open(); } },
  };
  open();
  return () => { stop = true; ws?.close(); };
}
