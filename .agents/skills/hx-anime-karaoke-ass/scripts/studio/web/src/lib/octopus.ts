/* 定制版 libass (SubtitlesOctopus + VSFilterMod 扩展的 wasm), 与 render_octopus.py 出片同一份文件, 由服务的 /octopus/ 发出. */
import type { Project } from './api';

export interface OctopusInstance {
  setCurrentTime(t: number): void;
  setTrack(text: string): void;
  resize(w: number, h: number, top?: number, left?: number): void;
  dispose(): void;
  writeFile(path: string, data: Uint8Array): void;
}
type Ctor = new (o: Record<string, unknown>) => OctopusInstance;

let loading: Promise<Ctor> | null = null;

function loadScript(base: string): Promise<Ctor> {
  if (loading) return loading;
  loading = new Promise((res, rej) => {
    const w = window as unknown as { SubtitlesOctopus?: Ctor };
    if (w.SubtitlesOctopus) return res(w.SubtitlesOctopus);
    const s = document.createElement('script');
    s.src = `${base}subtitles-octopus.js`;
    s.onload = () => (w.SubtitlesOctopus ? res(w.SubtitlesOctopus) : rej(new Error('SubtitlesOctopus 未定义')));
    s.onerror = () => rej(new Error('加载 subtitles-octopus.js 失败'));
    document.head.appendChild(s);
  });
  return loading;
}

/** ASS 里 \\1img..\\4img 引用的相对路径 (去重). 跳过 data: 和带 ! / $ 的写法, 与 render_octopus.py 一致. */
export function imgRefs(text: string): string[] {
  const out = new Set<string>();
  for (const m of text.matchAll(/\\[1-4]img\(([^)]+)\)/g)) {
    const r = m[1].trim();
    if (!r || r.startsWith('data:') || r.includes('!') || r.includes('$')) continue;
    out.add(r);
  }
  return [...out];
}

/** 取回 ASS 引用的贴图写进 worker 虚拟 FS, 再重载 track (只 writeFile 不重载, libass 不会去找图).
 *  图片接口: /api/ass/<which> -> /api/img/<which>/<相对路径>, 按 ASS 所在目录解析. 返回写入数和取不到的路径. */
/*
 * Agent Notes: studio 自己把 \1img 贴图注入 worker 虚拟 FS, 逐张独立, 缺图报 partial
 * .agents/notes/implemented/feature/2026-11-13-karaoke-studio-img-inject.md
 */
async function injectImages(o: OctopusInstance, subUrl: string): Promise<{ written: number; missing: string[] }> {
  // 先要一份小清单 (服务端扫好的), 没有贴图就不再整份下载 ASS; 老服务没有这个接口时退回自己扫
  let refs: string[];
  let text: string | null = null;
  const which = subUrl.endsWith('/api/ass/ref') ? 'ref' : 'out';
  const lr = await fetch(subUrl.replace(/\/api\/ass\/(out|ref)$/, `/api/imgrefs?which=${which}`)).catch(() => null);
  if (lr && lr.ok) refs = ((await lr.json()) as { refs: string[] }).refs;
  else { text = await (await fetch(subUrl)).text(); refs = imgRefs(text); }
  if (!refs.length) return { written: 0, missing: [] };
  const base = subUrl.replace('/api/ass/', '/api/img/') + '/';
  const missing: string[] = [];
  let written = 0;
  // 逐张独立: 坏一张不拖累其余 (3 张坏 1 张, 另 2 张照常显示)
  await Promise.all(refs.map(async (rel) => {
    try {
      const r = await fetch(base + rel.split('/').map(encodeURIComponent).join('/'));
      if (!r.ok) { missing.push(`${rel} (HTTP ${r.status})`); return; }
      o.writeFile(rel, new Uint8Array(await r.arrayBuffer()));
      written++;
    } catch (e) {
      missing.push(`${rel} (${String((e as Error)?.message ?? e)})`);
    }
  }));
  if (written) o.setTrack(text ?? await (await fetch(subUrl)).text());
  return { written, missing };
}

/** 实例健康: crashed = 就绪后 worker 抛错/abort (SubtitlesOctopus 已自己 dispose, 不可恢复);
 *  stalled = 看门狗 STALL_MS 内没收到 worker 任何消息 (被杀/卡死/单帧太慢); ok = stalled 后又有回包. */
export type OctoHealth = { state: 'crashed' | 'stalled' | 'ok'; reason: string; at: number };
export interface OctoHandle extends OctopusInstance {
  /** 非空 = 已死 (原因), 之后所有调用都是空操作 */
  readonly dead: string;
}

/** 看门狗阈值 (ms). 默认 4000, 可用 window.__octoStallMs 覆盖 (e2e / 量真实工程时调). */
export const STALL_MS = 4000;
const stallMs = () => (window as unknown as { __octoStallMs?: number }).__octoStallMs ?? STALL_MS;
const PING_MS = 1000;

export async function createOctopus(
  p: Project, canvas: HTMLCanvasElement, onReady: (missing: string[]) => void, onError: (e: string) => void,
  onHealth: (h: OctoHealth) => void = () => undefined,
): Promise<OctoHandle> {
  const base = p.octopus ?? '/octopus/';
  const C = await loadScript(base);
  // availableFonts 只是按名字懒加载的索引, 一个名字只能指一个文件; 所有字体文件已经在 fonts 里整批预载,
  // 同族多字重 (Regular/Bold) 时 libass 照样能按 \\b 挑到对的字重. 这里只让索引确定: 常规字重优先, 其余按文件名先到先得,
  // 不再 "后到覆盖" (以前取决于目录排序). 被挤掉的名字打一条日志, 方便对拍时查.
  const avail: Record<string, string> = {};
  const clash: string[] = [];
  for (const f of [...p.fonts].sort((a, b) => Number(!!b.regular) - Number(!!a.regular))) {
    for (const fam of f.families) {
      const k = fam.toLowerCase();
      if (!(k in avail)) avail[k] = f.url;
      else if (avail[k] !== f.url) clash.push(`${fam}: ${avail[k]} (保留) / ${f.url}`);
    }
  }
  if (clash.length) console.info(`[octo] 字体同名 ${clash.length} 处, 索引按常规字重优先:`, clash);
  let inst: OctopusInstance | null = null;
  let injected = false;
  // ---- 死亡标记 + 看门狗
  // SubtitlesOctopus 的 workerError (上游与定制版都一样): onErrorEvent -> 非 debug 下 self.dispose() (worker 置 null) -> throw.
  // 之后再调 setCurrentTime 会抛 TypeError; 以前这一抛打断 clock 的 rAF, 整个 studio 定住. 所以 onError 一来就标 dead, 之后全空操作.
  // 被 terminate / worker 卡死则没有任何事件 (实测), 只能靠回包判断: 每秒发一次 get-styles (worker 必回, 主线程忽略回包),
  // 任何 worker 消息都算活着. 不能靠渲染回包: worker 只在画面变了时才回 renderCanvas, 停在两段空白之间时本来就不回.
  let dead = '';
  let armed = false;
  let lastT = 0;
  let pingAt = 0;      // 未回的 ping 发出时刻, 0 = 无
  let stalled = false;
  let maxPing = 0, maxSpent = 0;
  let dog = 0;
  const now = () => performance.now();
  const worker = () => (inst as unknown as { worker?: Worker | null } | null)?.worker ?? null;
  const stop = () => { if (dog) { clearInterval(dog); dog = 0; } };
  const die = (reason: string) => {
    if (dead) return;
    dead = reason || '未知错误';
    stop();
  };
  const onMsg = (ev: MessageEvent) => {
    if (pingAt) { maxPing = Math.max(maxPing, now() - pingAt); pingAt = 0; canvas.dataset.octoPingMaxMs = maxPing.toFixed(0); }
    const d = ev.data as { target?: string; spentTime?: number } | null;
    if (d?.target === 'canvas' && typeof d.spentTime === 'number' && d.spentTime > maxSpent) {
      maxSpent = d.spentTime;
      canvas.dataset.octoFrameMaxMs = maxSpent.toFixed(0);   // worker 自报的单帧渲染耗时最大值, 给定阈值用
    }
    if (stalled && !dead) { stalled = false; onHealth({ state: 'ok', reason: '', at: lastT }); }
  };
  const arm = () => {
    const w = worker();
    if (armed || dead || !w) return;
    armed = true;
    w.addEventListener('message', onMsg);
    dog = window.setInterval(() => {
      const ww = worker();
      if (dead) return stop();
      if (!ww) { die('worker 已不存在'); onHealth({ state: 'crashed', reason: dead, at: lastT }); return; }
      if (pingAt) {
        if (!stalled && now() - pingAt > stallMs()) {
          stalled = true;
          onHealth({ state: 'stalled', reason: `worker ${Math.round(stallMs() / 1000)}s 没有回应 (被终止, 卡死, 或单帧过慢)`, at: lastT });
        }
        return;
      }
      pingAt = now();
      try { ww.postMessage({ target: 'get-styles' }); } catch (e) { die(String((e as Error)?.message ?? e)); onHealth({ state: 'crashed', reason: dead, at: lastT }); }
    }, PING_MS);
  };
  const ready = async () => {
    if (injected || !inst || dead) return;
    injected = true;
    let missing: string[] = [];
    try {
      const r = await injectImages(inst, p.out_ass);
      missing = r.missing;
      console.info(`[octo] 贴图注入 ${r.written} 张` + (missing.length ? `, 取不到 ${missing.length} 张: ${missing.join(', ')}` : ''));
    } catch (e) {
      missing = [`贴图注入失败: ${String((e as Error)?.message ?? e)}`];   // 读 ASS 都失败: 整体算缺, 不能当就绪
      console.warn('[octo] 贴图注入失败', e);
    }
    if (dead) return;
    onReady(missing);
    arm();
  };
  inst = new C({
    canvas,
    subUrl: p.out_ass,
    workerUrl: `${base}subtitles-octopus-worker.js`,
    legacyWorkerUrl: `${base}subtitles-octopus-worker-legacy.js`,
    fonts: p.fonts.map((f) => f.url),
    // availableFonts 传空: 字体已经整批预载. worker 预载用 'font<i>-文件名', 按名懒加载用 'font<自增>-文件名', 两套编号撞名时
    // 写同一个文件 -> FS error, worker 崩 (罪恶王冠: Lolita 先懒加载占 font0, Cormorant Light 懒加载成 font1-CormorantGaramond-Light.ttf,
    // 与预载的 font1 同名). libass 从 /fonts 目录按族名找字, 不需要这张索引. avail 仍算出来只为打同名日志.
    availableFonts: {},
    ...(p.fallback_font ? { fallbackFont: p.fallback_font } : {}),
    onReady: () => { void ready(); },
    onError: (e: unknown) => {
      const msg = String((e as ErrorEvent)?.message ?? (e as Error)?.message ?? e);
      const wasReady = armed || injected;
      die(msg);
      if (wasReady) onHealth({ state: 'crashed', reason: msg, at: lastT });
      else onError(msg);   // 载入阶段就失败: 维持原来的 'error'
    },
  });
  const o = inst;
  // 外壳: dead 之后全部空操作; 内层抛错 (例如 worker 已被置 null) 也就地标死, 不往外抛
  const guard = (what: string, f: () => void) => {
    if (dead) return;
    try { f(); } catch (e) {
      die(`${what}: ${String((e as Error)?.message ?? e)}`);
      onHealth({ state: 'crashed', reason: dead, at: lastT });
    }
  };
  let disposed = false;
  return {
    get dead() { return dead; },
    setCurrentTime: (t) => { lastT = t; guard('setCurrentTime', () => o.setCurrentTime(t)); },
    setTrack: (text) => guard('setTrack', () => o.setTrack(text)),
    resize: (w, h, top, left) => guard('resize', () => o.resize(w, h, top, left)),
    writeFile: (path, data) => guard('writeFile', () => o.writeFile(path, data)),
    dispose: () => {
      if (disposed) return;
      disposed = true;
      stop();
      worker()?.removeEventListener('message', onMsg);
      const wasDead = !!dead;   // 已死 = workerError 已自行 dispose (worker=null), 再调必抛, 这种才静默
      if (!dead) dead = 'disposed';
      try { o.dispose(); } catch (e) { if (!wasDead) console.warn('[octo] dispose 抛错 (实例当时还活着):', e); }
    },
  };
}
