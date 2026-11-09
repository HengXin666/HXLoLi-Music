/* 定制版 libass (SubtitlesOctopus + VSFilterMod 扩展的 wasm), 与 render_octopus.py 出片同一份文件, 由服务的 /octopus/ 发出. */
import type { Project } from './api';

export interface OctopusInstance {
  setCurrentTime(t: number): void;
  setTrack(text: string): void;
  resize(w: number, h: number, top?: number, left?: number): void;
  dispose(): void;
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

export async function createOctopus(
  p: Project, canvas: HTMLCanvasElement, onReady: () => void, onError: (e: string) => void,
): Promise<OctopusInstance> {
  const base = p.octopus ?? '/octopus/';
  const C = await loadScript(base);
  const avail: Record<string, string> = {};
  for (const f of p.fonts) for (const fam of f.families) avail[fam.toLowerCase()] = f.url;
  return new C({
    canvas,
    subUrl: p.out_ass,
    workerUrl: `${base}subtitles-octopus-worker.js`,
    legacyWorkerUrl: `${base}subtitles-octopus-worker-legacy.js`,
    fonts: p.fonts.map((f) => f.url),
    availableFonts: avail,
    onReady,
    onError: (e: unknown) => onError(String((e as Error)?.message ?? e)),
  });
}
