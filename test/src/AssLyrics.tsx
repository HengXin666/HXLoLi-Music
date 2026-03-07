/**
 * ASS 歌词渲染悬浮窗组件 (本地测试版)
 *
 * 基于 HXLoLi 前端仓库的 AssLyrics.tsx 简化而来:
 * - 移除 Docusaurus 依赖 (useDocusaurusContext)
 * - 移除 CDN URL 转换 (toMusicCdnUrl)
 * - 直接使用本地路径
 * - 保留完整的 ASS 预处理裁剪逻辑
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
    FaAlignCenter,
    FaBackward,
    FaCrop,
    FaExpand,
    FaFastBackward,
    FaForward,
    FaLock,
    FaLockOpen,
    FaPause,
    FaPlay,
    FaStepBackward,
    FaStepForward,
    FaTimes,
    FaUndo,
} from 'react-icons/fa';
import { useMusicStore } from './musicStore';

/** 全局重置位置的事件名 */
const RESET_POSITION_EVENT = 'hxloli-lyrics-reset-position';

const POSITION_KEY = 'hxloli-lyrics-position';
const SIZE_KEY = 'hxloli-lyrics-size';
const LOCK_KEY = 'hxloli-lyrics-locked';
const SUBTITLE_OFFSET_KEY = 'hxloli-lyrics-subtitle-offset';
const PREPROCESS_ASS_KEY = 'hxloli-lyrics-preprocess-ass';

/** 默认尺寸 */
const DEFAULT_SIZE = { w: 500, h: 350 };

function defaultPosition(): { x: number; y: number } {
  const x = Math.max(0, Math.round((window.innerWidth - DEFAULT_SIZE.w) / 2));
  const y = Math.max(0, Math.round((window.innerHeight - DEFAULT_SIZE.h) / 2));
  return { x, y };
}

function loadPosition(): { x: number; y: number } {
  try { const raw = localStorage.getItem(POSITION_KEY); if (raw) return JSON.parse(raw); } catch {}
  return defaultPosition();
}
function savePosition(pos: { x: number; y: number }) {
  try { localStorage.setItem(POSITION_KEY, JSON.stringify(pos)); } catch {}
}
function loadSize(): { w: number; h: number } {
  try { const raw = localStorage.getItem(SIZE_KEY); if (raw) return JSON.parse(raw); } catch {}
  return { ...DEFAULT_SIZE };
}
function saveSize(size: { w: number; h: number }) {
  try { localStorage.setItem(SIZE_KEY, JSON.stringify(size)); } catch {}
}
function loadLocked(): boolean {
  try { return localStorage.getItem(LOCK_KEY) === 'true'; } catch { return false; }
}
function saveLocked(locked: boolean) {
  try { localStorage.setItem(LOCK_KEY, JSON.stringify(locked)); } catch {}
}
function loadSubtitleOffset(): number {
  try { const raw = localStorage.getItem(SUBTITLE_OFFSET_KEY); if (raw) return parseFloat(raw) || 0; } catch {}
  return 0;
}
function saveSubtitleOffset(offset: number) {
  try { localStorage.setItem(SUBTITLE_OFFSET_KEY, JSON.stringify(offset)); } catch {}
}
function loadPreprocessAss(): boolean {
  try { const raw = localStorage.getItem(PREPROCESS_ASS_KEY); if (raw !== null) return raw === 'true'; } catch {}
  return true;
}
function savePreprocessAss(enabled: boolean) {
  try { localStorage.setItem(PREPROCESS_ASS_KEY, JSON.stringify(enabled)); } catch {}
}

// ========== ASS 预处理裁剪逻辑 ==========
interface TwoBlockBounds {
  topYMin: number; topYMax: number;
  btmYMin: number; btmYMax: number;
  left: number; right: number;
}

/** 时间轴 bounds 关键点 (由 Python 预计算) */
interface BoundsTimelinePoint extends TwoBlockBounds {
  t: number;
}

function boundsHasTop(b: TwoBlockBounds): boolean { return b.topYMin !== Infinity; }
function boundsHasBtm(b: TwoBlockBounds): boolean { return b.btmYMin !== Infinity; }
function boundsHasContent(b: TwoBlockBounds): boolean { return boundsHasTop(b) || boundsHasBtm(b); }

/**
 * 从时间轴 bounds 中按当前时间插值获取 bounds
 *
 * 使用二分查找找到最近的两个关键点, 线性插值得到当前时刻的 bounds
 * 这样可以在不同时间段使用不同的裁剪窗口, 实现实时跟踪
 */
function interpolateBoundsAtTime(timeline: BoundsTimelinePoint[], time: number): TwoBlockBounds {
  const n = timeline.length;
  if (n === 0) return { topYMin: 0, topYMax: 0, btmYMin: 0, btmYMax: 0, left: 0, right: 0 };
  if (n === 1 || time <= timeline[0].t) return timeline[0];
  if (time >= timeline[n - 1].t) return timeline[n - 1];

  // 二分查找: 找到最大的 i 使得 timeline[i].t <= time
  let lo = 0, hi = n - 1;
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1;
    if (timeline[mid].t <= time) lo = mid;
    else hi = mid;
  }

  const a = timeline[lo];
  const b = timeline[hi];
  const dt = b.t - a.t;
  if (dt <= 0) return a;

  const ratio = (time - a.t) / dt;
  return {
    topYMin: Math.round(a.topYMin + (b.topYMin - a.topYMin) * ratio),
    topYMax: Math.round(a.topYMax + (b.topYMax - a.topYMax) * ratio),
    btmYMin: Math.round(a.btmYMin + (b.btmYMin - a.btmYMin) * ratio),
    btmYMax: Math.round(a.btmYMax + (b.btmYMax - a.btmYMax) * ratio),
    left:    Math.round(a.left    + (b.left    - a.left)    * ratio),
    right:   Math.round(a.right   + (b.right   - a.right)   * ratio),
  };
}

function cropAndDraw(srcCanvas: HTMLCanvasElement, dstCanvas: HTMLCanvasElement, bounds: TwoBlockBounds) {
  const hasTop = boundsHasTop(bounds);
  const hasBtm = boundsHasBtm(bounds);
  if (!hasTop && !hasBtm) return;

  const contentW = bounds.right - bounds.left;
  const topH = hasTop ? (bounds.topYMax - bounds.topYMin) : 0;
  const btmH = hasBtm ? (bounds.btmYMax - bounds.btmYMin) : 0;
  const totalH = topH + btmH;

  if (contentW <= 0 || totalH <= 0) return;

  const dstCtx = dstCanvas.getContext('2d');
  if (!dstCtx) return;

  dstCtx.clearRect(0, 0, dstCanvas.width, dstCanvas.height);

  const scaleX = dstCanvas.width / contentW;
  const scaleY = dstCanvas.height / totalH;
  const scale = Math.min(scaleX, scaleY, 1);

  const drawW = contentW * scale;
  const drawH = totalH * scale;
  const offsetX = (dstCanvas.width - drawW) / 2;
  const offsetY = (dstCanvas.height - drawH) / 2;

  if (hasTop && topH > 0) {
    dstCtx.drawImage(srcCanvas, bounds.left, bounds.topYMin, contentW, topH, offsetX, offsetY, drawW, topH * scale);
  }
  if (hasBtm && btmH > 0) {
    dstCtx.drawImage(srcCanvas, bounds.left, bounds.btmYMin, contentW, btmH, offsetX, offsetY + topH * scale, drawW, btmH * scale);
  }
}

// ========== Script loader ==========
let scriptLoaded = false;
let scriptLoading = false;
let scriptCallbacks: Array<() => void> = [];

function loadSubtitlesOctopusScript(onReady: () => void) {
  if ((window as any).SubtitlesOctopus) { scriptLoaded = true; onReady(); return; }
  if (scriptLoaded) { onReady(); return; }
  scriptCallbacks.push(onReady);
  if (scriptLoading) return;
  scriptLoading = true;

  const scriptUrl = '/music/ass-worker/subtitles-octopus.js';
  console.log('[ASS] 开始加载脚本:', scriptUrl);

  const script = document.createElement('script');
  script.src = scriptUrl;
  script.async = true;
  script.onload = () => {
    console.log('[ASS] 脚本加载完成, window.SubtitlesOctopus:', typeof (window as any).SubtitlesOctopus);
    if (typeof (window as any).SubtitlesOctopus !== 'function') {
      fetch(scriptUrl).then(r => r.text()).then(code => {
        const fakeModule: any = { exports: {} };
        const wrapper = new Function('module', 'exports', code);
        wrapper(fakeModule, fakeModule.exports);
        if (typeof fakeModule.exports === 'function') {
          (window as any).SubtitlesOctopus = fakeModule.exports;
        }
        finishLoading();
      }).catch(() => finishLoading());
    } else {
      finishLoading();
    }
  };
  script.onerror = () => { scriptLoading = false; };

  function finishLoading() {
    scriptLoaded = true; scriptLoading = false;
    const cbs = scriptCallbacks.slice(); scriptCallbacks = [];
    cbs.forEach(cb => cb());
  }
  document.head.appendChild(script);
}

let globalSubtitleOffset = loadSubtitleOffset();

export default function AssLyrics(): React.ReactElement | null {
  const showLyrics = useMusicStore((s) => s.showLyrics);
  const lyricsFullscreen = useMusicStore((s) => s.lyricsFullscreen);
  const trackIndex = useMusicStore((s) => s.trackIndex);
  const pl = useMusicStore((s) => s.playlist);
  const isPlaying = useMusicStore((s) => s.isPlaying);
  const toggleLyrics = useMusicStore((s) => s.toggleLyrics);
  const toggleLyricsFullscreen = useMusicStore((s) => s.toggleLyricsFullscreen);
  const toggle = useMusicStore((s) => s.toggle);
  const next = useMusicStore((s) => s.next);
  const prev = useMusicStore((s) => s.prev);
  const seek = useMusicStore((s) => s.seek);

  const currentTrack = pl[trackIndex] ?? null;

  const containerRef = useRef<HTMLDivElement>(null);
  const canvasContainerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const octopusRef = useRef<any>(null);
  const [position, setPosition] = useState(loadPosition);
  const [size, setSize] = useState(loadSize);
  const [locked, setLocked] = useState(loadLocked);
  const [subtitleOffset, setSubtitleOffset] = useState(loadSubtitleOffset);
  const [toolbarVisible, setToolbarVisible] = useState(false);
  const [, forceUpdate] = useState(0);
  const [rebuildToken, setRebuildToken] = useState(0);
  const [preprocessAss, setPreprocessAss] = useState(loadPreprocessAss);
  const offscreenCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const displayCanvasRef = useRef<HTMLCanvasElement>(null);
  const cachedBoundsRef = useRef<TwoBlockBounds | null>(null);
  const timelineRef = useRef<BoundsTimelinePoint[] | null>(null);
  const isDragging = useRef(false);
  const isResizing = useRef(false);
  const dragOffset = useRef({ x: 0, y: 0 });
  const rafIdRef = useRef<number | null>(null);
  const initRetryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const toolbarTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const resetPosition = useCallback(() => {
    const pos = defaultPosition();
    const sz = { ...DEFAULT_SIZE };
    setPosition(pos); setSize(sz);
    savePosition(pos); saveSize(sz);
  }, []);

  const toggleLock = useCallback(() => {
    setLocked((prev) => { const next = !prev; saveLocked(next); return next; });
  }, []);

  const subtitleSlower = useCallback(() => {
    setSubtitleOffset((prev) => { const next = +(prev - 0.5).toFixed(1); globalSubtitleOffset = next; saveSubtitleOffset(next); return next; });
  }, []);

  const subtitleFaster = useCallback(() => {
    setSubtitleOffset((prev) => { const next = +(prev + 0.5).toFixed(1); globalSubtitleOffset = next; saveSubtitleOffset(next); return next; });
  }, []);

  const resetSubtitleOffset = useCallback(() => {
    setSubtitleOffset(0); globalSubtitleOffset = 0; saveSubtitleOffset(0);
  }, []);

  const seekToStart = useCallback(() => { seek(0); }, [seek]);

  const togglePreprocessAss = useCallback(() => {
    setPreprocessAss((prev) => { const next = !prev; savePreprocessAss(next); setRebuildToken((n) => n + 1); return next; });
  }, []);

  const centerHorizontally = useCallback(() => {
    const x = Math.max(0, Math.round((window.innerWidth - size.w) / 2));
    const newPos = { x, y: position.y };
    setPosition(newPos); savePosition(newPos);
  }, [size.w, position.y]);

  const showToolbar = useCallback(() => {
    setToolbarVisible(true);
    if (toolbarTimerRef.current) clearTimeout(toolbarTimerRef.current);
    toolbarTimerRef.current = setTimeout(() => { if (!isDragging.current) setToolbarVisible(false); }, 3000);
  }, []);

  const hideToolbar = useCallback(() => {
    if (toolbarTimerRef.current) clearTimeout(toolbarTimerRef.current);
    toolbarTimerRef.current = setTimeout(() => { if (!isDragging.current) setToolbarVisible(false); }, 500);
  }, []);

  // 监听外部触发的重置位置事件
  useEffect(() => {
    const handler = () => { resetPosition(); forceUpdate((n) => n + 1); };
    window.addEventListener(RESET_POSITION_EVENT, handler);
    return () => window.removeEventListener(RESET_POSITION_EVENT, handler);
  }, [resetPosition]);

  // 持续推送 currentTime 到 octopus 的 RAF 循环
  const shouldRender = showLyrics;

  useEffect(() => {
    if (!shouldRender) return;
    let lastPushedTime = -1;
    const tick = () => {
      const oct = octopusRef.current;
      if (oct) {
        const ct = useMusicStore.getState().getInterpolatedTime() + globalSubtitleOffset;
        const adjustedCt = Math.max(0, ct);

        // 如果有时间轴 bounds, 动态插值获取当前时刻的裁剪窗口
        // 否则退回到全局固定 bounds
        if (preprocessAss && offscreenCanvasRef.current && displayCanvasRef.current) {
          const tl = timelineRef.current;
          const currentBounds = tl
            ? interpolateBoundsAtTime(tl, adjustedCt)
            : cachedBoundsRef.current;
          if (currentBounds) {
            cropAndDraw(offscreenCanvasRef.current, displayCanvasRef.current, currentBounds);
          }
        }

        const delta = adjustedCt - lastPushedTime;
        if (delta > 0.016 || delta < -0.5) {
          try { oct.setCurrentTime(adjustedCt); } catch {}
          lastPushedTime = adjustedCt;
        }
      }
      rafIdRef.current = requestAnimationFrame(tick);
    };
    rafIdRef.current = requestAnimationFrame(tick);
    return () => { if (rafIdRef.current !== null) { cancelAnimationFrame(rafIdRef.current); rafIdRef.current = null; } };
  }, [shouldRender, preprocessAss]);

  // 初始化 / 切换曲目时重建 octopus
  useEffect(() => {
    if (!showLyrics || !currentTrack?.assUrl) {
      if (octopusRef.current) { try { octopusRef.current.dispose(); } catch {} octopusRef.current = null; }
      return;
    }

    let disposed = false;

    const initOctopus = async () => {
      let renderCanvas: HTMLCanvasElement;

      if (preprocessAss) {
        if (!offscreenCanvasRef.current) offscreenCanvasRef.current = document.createElement('canvas');
        renderCanvas = offscreenCanvasRef.current;
        renderCanvas.width = 1920;
        renderCanvas.height = 1080;

        const displayCanvas = displayCanvasRef.current;
        if (displayCanvas) {
          if (lyricsFullscreen) {
            displayCanvas.width = window.innerWidth;
            displayCanvas.height = window.innerHeight;
          } else {
            displayCanvas.width = Math.round(size.w);
            displayCanvas.height = Math.round(size.h);
          }
        }
      } else {
        renderCanvas = canvasRef.current!;
      }

      if (!renderCanvas) {
        if (!disposed) initRetryRef.current = setTimeout(initOctopus, 150);
        return;
      }

      let pixelW: number, pixelH: number;
      if (preprocessAss) { pixelW = 1920; pixelH = 1080; }
      else if (lyricsFullscreen) { pixelW = window.innerWidth; pixelH = window.innerHeight; }
      else { pixelW = Math.round(size.w); pixelH = Math.round(size.h); }

      if (pixelW <= 0 || pixelH <= 0) {
        if (!disposed) initRetryRef.current = setTimeout(initOctopus, 200);
        return;
      }

      renderCanvas.width = pixelW;
      renderCanvas.height = pixelH;

      console.log(`[ASS] 初始化 canvas: ${pixelW}x${pixelH}, 预处理: ${preprocessAss}, assUrl: ${currentTrack.assUrl}`);

      if (octopusRef.current) { try { octopusRef.current.dispose(); } catch {} octopusRef.current = null; }

      const origin = window.location.origin;
      const workerUrl = `${origin}/music/ass-worker/subtitles-octopus-worker.js`;
      const legacyWorkerUrl = `${origin}/music/ass-worker/subtitles-octopus-worker-legacy.js`;

      const Ctor = (window as any).SubtitlesOctopus;
      if (!Ctor) { console.error('[ASS] SubtitlesOctopus 构造函数未找到!'); return; }

      // 本地版：直接用 /static/music/fonts/ 路径
      const cjkFallbackUrl = '/static/music/fonts/NotoSansSC-Regular.ttf';
      const availableFonts: Record<string, string> = {};

      const safeUrl = (url: string): string => {
        if (/%[0-9A-Fa-f]{2}/.test(url)) return url;
        return encodeURI(url);
      };

      const assUrlRaw = currentTrack.assUrl!;
      const subFullUrl = safeUrl(assUrlRaw.startsWith('http') ? assUrlRaw : `${origin}${assUrlRaw}`);

      console.log('[ASS] 正在 fetch ASS 文件:', subFullUrl);
      let subContent: string | null = null;
      try {
        const resp = await fetch(subFullUrl);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        subContent = await resp.text();
        console.log(`[ASS] ASS 文件加载成功, 大小: ${subContent.length} 字符`);
      } catch (fetchErr) {
        console.error('[ASS] fetch ASS 文件失败:', fetchErr);
        return;
      }

      if (disposed) return;

      try {
        const instance = new Ctor({
          canvas: renderCanvas,
          subContent: subContent,
          fonts: [],
          availableFonts,
          fallbackFont: safeUrl(cjkFallbackUrl),
          lazyFileLoading: false,
          workerUrl: safeUrl(workerUrl),
          legacyWorkerUrl: safeUrl(legacyWorkerUrl),
          renderMode: 'wasm-blend',
          targetFps: 24,
          prescaleFactor: 0.8,
          prescaleHeightLimit: 1080,
          maxRenderHeight: 720,
          debug: true,
          onReady: () => {
            console.log('[ASS] SubtitlesOctopus 就绪');
            if (preprocessAss) {
              // 优先使用时间轴 bounds (新方案: 滑动窗口 + EMA 平滑)
              if (currentTrack.assBoundsTimeline && currentTrack.assBoundsTimeline.length > 0) {
                timelineRef.current = currentTrack.assBoundsTimeline as BoundsTimelinePoint[];
                cachedBoundsRef.current = null; // 有 timeline 就不用固定 bounds
                console.log(`[ASS] 使用时间轴 bounds: ${currentTrack.assBoundsTimeline.length} 个关键点`);
              } else if (currentTrack.assBounds) {
                // 回退到全局固定 bounds (旧方案)
                const b = currentTrack.assBounds;
                const bounds: TwoBlockBounds = {
                  topYMin: b.topYMin, topYMax: b.topYMax,
                  btmYMin: b.btmYMin, btmYMax: b.btmYMax,
                  left: b.left, right: b.right,
                };
                if (boundsHasContent(bounds)) {
                  cachedBoundsRef.current = bounds;
                  console.log('[ASS] 使用全局 assBounds (无时间轴):', bounds);
                } else {
                  cachedBoundsRef.current = null;
                }
                timelineRef.current = null;
              }
            }
            const ct = useMusicStore.getState().getInterpolatedTime() + globalSubtitleOffset;
            try { instance.setCurrentTime(Math.max(0, ct)); } catch {}
          },
          onError: (err: any) => console.error('[ASS] SubtitlesOctopus 错误:', err),
        });

        if (!disposed) { octopusRef.current = instance; }
        else { instance.dispose(); }
      } catch (err) {
        console.error('[ASS] 创建 SubtitlesOctopus 实例失败:', err);
      }
    };

    loadSubtitlesOctopusScript(() => {
      if (disposed) return;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => { if (!disposed) initOctopus(); });
      });
    });

    return () => {
      disposed = true;
      if (initRetryRef.current) { clearTimeout(initRetryRef.current); initRetryRef.current = null; }
      cachedBoundsRef.current = null;
      timelineRef.current = null;
      if (octopusRef.current) { try { octopusRef.current.dispose(); } catch {} octopusRef.current = null; }
    };
  }, [showLyrics, currentTrack?.assUrl, currentTrack?.fonts, lyricsFullscreen, size, rebuildToken, preprocessAss]);

  // 全屏切换 / 窗口 resize
  useEffect(() => {
    if (!showLyrics) return;
    const handleResize = () => {
      if (useMusicStore.getState().lyricsFullscreen) setRebuildToken((n) => n + 1);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [showLyrics]);

  const prevFullscreen = useRef(lyricsFullscreen);
  useEffect(() => {
    if (prevFullscreen.current !== lyricsFullscreen) { prevFullscreen.current = lyricsFullscreen; setRebuildToken((n) => n + 1); }
  }, [lyricsFullscreen]);

  // 拖拽逻辑
  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    if (locked) return;
    if ((e.target as HTMLElement).dataset.dragHandle !== 'true') return;
    isDragging.current = true;
    dragOffset.current = { x: e.clientX - position.x, y: e.clientY - position.y };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, [position, locked]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (isDragging.current) setPosition({ x: e.clientX - dragOffset.current.x, y: e.clientY - dragOffset.current.y });
  }, []);

  const handlePointerUp = useCallback(() => {
    if (isDragging.current) { isDragging.current = false; savePosition(position); }
  }, [position]);

  // 缩放逻辑
  const handleResizePointerDown = useCallback((e: React.PointerEvent) => {
    if (locked) return;
    e.stopPropagation(); e.preventDefault();
    isResizing.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, [locked]);

  const handleResizePointerMove = useCallback((e: React.PointerEvent) => {
    if (isResizing.current && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setSize({ w: Math.max(300, e.clientX - rect.left), h: Math.max(200, e.clientY - rect.top) });
    }
  }, []);

  const handleResizePointerUp = useCallback(() => {
    if (isResizing.current) { isResizing.current = false; saveSize(size); setRebuildToken((n) => n + 1); }
  }, [size]);

  useEffect(() => { return () => { if (toolbarTimerRef.current) clearTimeout(toolbarTimerRef.current); }; }, []);

  if (!showLyrics || !currentTrack?.assUrl) return null;

  // 工具栏
  const toolbarContent = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap', justifyContent: 'center' }}>
      <button onClick={prev} style={toolbarBtnStyle} title="上一首"><FaStepBackward size={11} /></button>
      <button onClick={toggle} style={toolbarBtnStyle} title={isPlaying ? '暂停' : '播放'}>
        {isPlaying ? <FaPause size={11} /> : <FaPlay size={11} />}
      </button>
      <button onClick={next} style={toolbarBtnStyle} title="下一首"><FaStepForward size={11} /></button>
      <button onClick={seekToStart} style={toolbarBtnStyle} title="回到开头"><FaFastBackward size={11} /></button>
      <span style={separatorStyle}>│</span>
      <button onClick={subtitleSlower} style={toolbarBtnStyle} title="字幕慢 0.5s"><FaBackward size={10} /></button>
      <button onClick={subtitleFaster} style={toolbarBtnStyle} title="字幕快 0.5s"><FaForward size={10} /></button>
      {subtitleOffset !== 0 && (
        <span style={{ color: 'rgba(255,255,255,0.6)', fontSize: 10, margin: '0 2px', whiteSpace: 'nowrap' }}>
          {subtitleOffset > 0 ? '+' : ''}{subtitleOffset.toFixed(1)}s
        </span>
      )}
      <button onClick={resetSubtitleOffset} style={toolbarBtnStyle} title="重置时间偏移"><FaUndo size={10} /></button>
      <button onClick={toggleLock} style={{ ...toolbarBtnStyle, background: locked ? 'rgba(255, 180, 0, 0.4)' : toolbarBtnStyle.background }} title={locked ? '解锁' : '锁定'}>
        {locked ? <FaLock size={11} /> : <FaLockOpen size={11} />}
      </button>
      <span style={separatorStyle}>│</span>
      <button onClick={centerHorizontally} style={toolbarBtnStyle} title="水平居中"><FaAlignCenter size={11} /></button>
      <button onClick={togglePreprocessAss} style={{ ...toolbarBtnStyle, background: preprocessAss ? 'rgba(0, 200, 100, 0.4)' : toolbarBtnStyle.background }} title={preprocessAss ? '关闭裁剪' : '开启裁剪'}>
        <FaCrop size={11} />
      </button>
      <button onClick={() => toggleLyricsFullscreen()} style={toolbarBtnStyle} title="全屏"><FaExpand size={11} /></button>
      <button onClick={toggleLyrics} style={toolbarBtnStyle} title="关闭"><FaTimes size={11} /></button>
    </div>
  );

  // 全屏模式
  if (lyricsFullscreen) {
    return (
      <div ref={containerRef} style={{ position: 'fixed', inset: 0, zIndex: 10000, background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        onMouseEnter={showToolbar} onMouseMove={showToolbar} onMouseLeave={hideToolbar}>
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10001, display: 'flex', justifyContent: 'center', padding: '8px 12px', background: 'linear-gradient(to bottom, rgba(0,0,0,0.7) 0%, transparent 100%)', opacity: toolbarVisible ? 1 : 0, transition: 'opacity 0.3s', pointerEvents: toolbarVisible ? 'auto' : 'none' }}>
          {toolbarContent}
        </div>
        <div ref={canvasContainerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
          <canvas ref={preprocessAss ? displayCanvasRef : canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
          {preprocessAss && <canvas ref={canvasRef} style={{ display: 'none' }} />}
        </div>
      </div>
    );
  }

  // 悬浮窗模式
  return (
    <div ref={containerRef}
      onPointerMove={(e) => { handlePointerMove(e); handleResizePointerMove(e); }}
      onPointerUp={() => { handlePointerUp(); handleResizePointerUp(); }}
      onMouseEnter={showToolbar} onMouseMove={showToolbar} onMouseLeave={hideToolbar}
      style={{
        position: 'fixed', left: position.x, top: position.y, width: size.w, height: size.h,
        zIndex: 9999, background: locked ? 'transparent' : 'rgba(0, 0, 0, 0.85)',
        borderRadius: locked ? 0 : 8, boxShadow: locked ? 'none' : '0 4px 24px rgba(0,0,0,0.5)',
        overflow: 'hidden', border: locked ? 'none' : '1px solid rgba(255,255,255,0.1)',
        userSelect: 'none', pointerEvents: locked ? 'none' : 'auto',
        transition: 'background 0.2s, box-shadow 0.2s, border 0.2s',
      }}>
      <div ref={canvasContainerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
        <canvas ref={preprocessAss ? displayCanvasRef : canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
        {preprocessAss && <canvas ref={canvasRef} style={{ display: 'none' }} />}
      </div>
      {!locked && (
        <div data-drag-handle="true" onPointerDown={handlePointerDown}
          style={{
            position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10,
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '4px 8px',
            background: 'linear-gradient(to bottom, rgba(0,0,0,0.8) 0%, rgba(0,0,0,0.4) 70%, transparent 100%)',
            cursor: 'grab', opacity: toolbarVisible ? 1 : 0, transition: 'opacity 0.3s',
            pointerEvents: toolbarVisible ? 'auto' : 'none',
          }}>
          {toolbarContent}
        </div>
      )}
      {locked && (
        <button onClick={toggleLock}
          style={{ ...toolbarBtnStyle, position: 'absolute', top: 4, right: 4, pointerEvents: 'auto', opacity: 0.15, zIndex: 10, width: 28, height: 28 }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = '1'; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = '0.15'; }}
          title="解锁">
          <FaLock size={12} />
        </button>
      )}
      {!locked && (
        <div onPointerDown={handleResizePointerDown}
          style={{ position: 'absolute', right: 0, bottom: 0, width: 16, height: 16, cursor: 'nwse-resize', background: 'linear-gradient(135deg, transparent 50%, rgba(255,255,255,0.3) 50%)', zIndex: 11 }} />
      )}
    </div>
  );
}

const toolbarBtnStyle: React.CSSProperties = {
  background: 'rgba(255,255,255,0.15)', border: 'none', color: '#fff',
  width: 26, height: 26, borderRadius: 4, cursor: 'pointer',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  fontSize: 13, padding: 0, lineHeight: 1, transition: 'background 0.15s', flexShrink: 0,
};

const separatorStyle: React.CSSProperties = {
  color: 'rgba(255,255,255,0.25)', fontSize: 14, margin: '0 2px', userSelect: 'none', lineHeight: 1,
};
