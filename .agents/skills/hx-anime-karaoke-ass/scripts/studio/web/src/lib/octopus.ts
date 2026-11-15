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
  const text = await (await fetch(subUrl)).text();
  const refs = imgRefs(text);
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
  if (written) o.setTrack(text);
  return { written, missing };
}

export async function createOctopus(
  p: Project, canvas: HTMLCanvasElement, onReady: (missing: string[]) => void, onError: (e: string) => void,
): Promise<OctopusInstance> {
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
  const ready = async () => {
    if (injected || !inst) return;
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
    onReady(missing);
  };
  inst = new C({
    canvas,
    subUrl: p.out_ass,
    workerUrl: `${base}subtitles-octopus-worker.js`,
    legacyWorkerUrl: `${base}subtitles-octopus-worker-legacy.js`,
    fonts: p.fonts.map((f) => f.url),
    availableFonts: avail,
    onReady: () => { void ready(); },
    onError: (e: unknown) => onError(String((e as Error)?.message ?? e)),
  });
  return inst;
}
