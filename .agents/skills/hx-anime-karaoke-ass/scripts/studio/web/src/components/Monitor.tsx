import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, type PlaceBlock, type PlaceLine } from '../lib/api';
import { clock } from '../lib/clock';
import { createOctopus, type OctopusInstance } from '../lib/octopus';
import { inRanges } from '../lib/sel';
import { useStore } from '../lib/store';
import { filterAss } from '../lib/tracks';
import { setSelection, selectLine } from '../lib/actions';
import s from './Monitor.module.css';

/**
 * 节目监视器: 按容器宽高双向 contain 算 16:9 矩形 (不用 aspect-ratio 撑高).
 * 视频 (EDL) + 定制 libass 画布 (像素 = 显示尺寸 x DPR). 与参考对比: A/B 切换 / 划变 / 左右并排 (第二个 libass 实例渲染参考 ASS).
 * 时间线轨的眼/独显与 "只看" 在这里落地: 过滤 out.ass 后 setTrack.
 * 选区叠层: 所选字的字框 + 该句 band 框. 右键: 按包围盒命中当前时刻的事件 (服务端 /api/hit).
 * 位置预设预览: 第二块画布每帧从成品画布拷像素, 把当前在场句的 "日文块 (含注音)" 与 "中文行" 两块各自擦掉原处、
 * 贴到服务端给的位移处 (矩形与位移全来自 GET /api/placement, 这里不算布局). 块外/跨块的特效不跟, 画面上常驻大号提示.
 */
const PW = 1920, PH = 1080;
type Rect = { x: number; y: number; w: number; h: number };

function fit(W: number, H: number): Rect {
  const w = Math.floor(Math.min(W, (H * 16) / 9));
  const h = Math.floor((w * 9) / 16);
  return { x: Math.floor((W - w) / 2), y: Math.floor((H - h) / 2), w, h };
}

function useOcto(which: 'out' | 'ref', canvas: React.RefObject<HTMLCanvasElement | null>, r: Rect, active: boolean, gen = '') {
  const project = useStore((x) => x.project);
  const inst = useRef<OctopusInstance | null>(null);
  const [ready, setReady] = useState(false);
  const set = useStore((x) => x.set);
  // 像素 = CSS x DPR
  useEffect(() => {
    const c = canvas.current;
    if (!c || !r.w || !active) return;
    const dpr = window.devicePixelRatio || 1;
    const pw = Math.round(r.w * dpr), ph = Math.round(r.h * dpr);
    c.dataset.cssW = String(r.w);
    c.dataset.dpr = String(dpr);
    if (inst.current) inst.current.resize(pw, ph);
    else { c.width = pw; c.height = ph; }
  }, [r, active, canvas]);
  useEffect(() => {
    if (!active || !project || !canvas.current || !r.w || inst.current) return;
    if (!project.octopus) { if (which === 'out') set({ octo: 'off' }); return; }
    const sub = which === 'out' ? project.out_ass : project.ref_ass;
    if (!sub) return;
    let dead = false;
    createOctopus({ ...project, out_ass: sub }, canvas.current,
      (miss) => {
        if (dead) return;
        setReady(true);
        if (which === 'out') set(miss.length ? { octo: 'partial', octoMissing: miss, octoErr: `贴图缺 ${miss.length} 张: ${miss.join('; ')}` }
          : { octo: 'ready', octoMissing: [], octoErr: '' });
        inst.current?.setCurrentTime(clock.t());
      },
      (e) => { if (which === 'out') set({ octo: 'error', octoErr: e }); },
    ).then((o) => { if (dead) o.dispose(); else inst.current = o; })
      .catch((e) => { if (which === 'out') set({ octo: 'error', octoErr: String(e) }); });
    return () => { dead = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project, r.w > 0, active, gen]);
  useEffect(() => () => {
    // 关掉对比 / 换容器: 释放实例, 下次重建
    inst.current?.dispose();
    inst.current = null;
    setReady(false);
  }, [active, gen]);
  useEffect(() => clock.subscribe((t) => inst.current?.setCurrentTime(t)), []);
  return { inst, ready };
}

function usePlacementPreview(src: React.RefObject<HTMLCanvasElement | null>, dst: React.RefObject<HTMLCanvasElement | null>, lines: PlaceLine[] | null) {
  useEffect(() => {
    if (!lines) return;
    let raf = 0;
    const draw = () => {
      const a = src.current, b = dst.current;
      if (a && b && a.width && a.height) {
        if (b.width !== a.width || b.height !== a.height) { b.width = a.width; b.height = a.height; }
        const kx = a.width / PW, ky = a.height / PH;
        const ctx = b.getContext('2d')!;
        ctx.clearRect(0, 0, b.width, b.height);
        ctx.drawImage(a, 0, 0);
        const t = clock.t();
        const blocks: PlaceBlock[] = [];
        for (const l of lines) if (t >= l.t[0] && t <= l.t[1]) { blocks.push(l.jp); if (l.cn) blocks.push(l.cn); }
        // 先把所有在场块的原处擦掉, 再贴 (两句交叠时不会互相擦)
        for (const k of blocks) ctx.clearRect(k.src[0] * kx, k.src[1] * ky, (k.src[2] - k.src[0]) * kx, (k.src[3] - k.src[1]) * ky);
        for (const k of blocks) {
          const [x0, y0, x1, y1] = k.src;
          ctx.drawImage(a, x0 * kx, y0 * ky, (x1 - x0) * kx, (y1 - y0) * ky, (x0 + k.dx) * kx, (y0 + k.dy) * ky, (x1 - x0) * kx, (y1 - y0) * ky);
        }
        b.dataset.blocks = String(blocks.length);
        b.dataset.t = t.toFixed(2);
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [lines, src, dst]);
}

function useVideoSync(vid: React.RefObject<HTMLVideoElement | null>) {
  const edl = useStore((x) => x.edl);
  useEffect(() => clock.subscribe((t) => {
    const v = vid.current;
    if (!v) return;
    const seg = edl?.segments.find((g) => t >= g.t0 && (g.t1 == null || t < g.t1));
    const want = seg ? seg.src_t0 + (t - seg.t0) : -1;
    const inRange = seg && want >= 0 && (!Number.isFinite(v.duration) || want < v.duration - 0.05);
    v.style.visibility = inRange ? 'visible' : 'hidden';
    if (!inRange) { if (!v.paused) v.pause(); return; }
    // 声音只来自 clock 的 song.mp3. 视频 (片源自带同一首歌, 比 song 晚 0.73s) 必须静音:
    // React 的 muted 只设属性不写 attribute, 某些浏览器/换 src 后会丢, 这里每帧兜底, 再把音量压到 0
    if (!v.muted) v.muted = true;
    if (v.volume !== 0) v.volume = 0;
    v.playbackRate = clock.audio.playbackRate;
    if (clock.playing) {
      if (v.paused) void v.play().catch(() => undefined);
      if (Math.abs(v.currentTime - want) > 0.2) v.currentTime = want;
    } else {
      if (!v.paused) v.pause();
      if (Math.abs(v.currentTime - want) > 0.03) v.currentTime = want;
    }
  }), [edl, vid]);
}

export default function Monitor() {
  const box = useRef<HTMLDivElement>(null);
  const cvOut = useRef<HTMLCanvasElement>(null);
  const cvRef = useRef<HTMLCanvasElement>(null);
  const vidOut = useRef<HTMLVideoElement>(null);
  const vidRef = useRef<HTMLVideoElement>(null);
  const [W, setW] = useState({ w: 0, h: 0 });
  const project = useStore((x) => x.project);
  const edl = useStore((x) => x.edl);
  const assRev = useStore((x) => x.assRev);
  const compare = useStore((x) => x.compare);
  const abShow = useStore((x) => x.abShow);
  const wipe = useStore((x) => x.wipe);
  const vis = useStore((x) => x.vis);
  const onlyUnits = useStore((x) => x.onlyUnits);
  // MV 轨的眼睛: 关掉则两个画框都不画视频 (只留字幕). 用 opacity 而不是 visibility, 后者每帧由 useVideoSync 按 EDL 改写
  const mvOn = vis.mv?.eye ?? true;
  const mvStyle = mvOn ? undefined : { opacity: 0 };
  const lines = useStore((x) => x.lines);
  const ix = useStore((x) => x.ix);
  const ranges = useStore((x) => x.ranges);
  const menu = useStore((x) => x.menu);
  const kept = useStore((x) => x.monitorKept);
  const placeLines = useStore((x) => x.placeLines);
  const placeCand = useStore((x) => x.placeCand);
  const placeNote = useStore((x) => x.place?.note);
  const previewing = !!placeCand && !!placeLines;
  const cvPrev = useRef<HTMLCanvasElement>(null);
  const set = useStore((x) => x.set);

  useEffect(() => {
    const el = box.current!;
    const ro = new ResizeObserver(([e]) => setW({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const side = compare === 'side';
  const rOut = useMemo(() => (side ? (() => { const a = fit(W.w / 2 - 2, W.h); return { ...a, x: Math.floor(W.w / 2 - 2 - a.w) }; })() : fit(W.w, W.h)), [W, side]);
  const rRef = useMemo(() => (side ? (() => { const a = fit(W.w / 2 - 2, W.h); return { ...a, x: Math.ceil(W.w / 2 + 2) }; })() : rOut), [W, side, rOut]);
  const refActive = compare !== 'off' && !!project?.ref_ass;

  const out = useOcto('out', cvOut, rOut, true);
  // 参考实例: 换容器 (并排 <-> 叠放) 时重建
  const refKey = side ? 'side' : 'inline';
  const ref = useOcto('ref', cvRef, rRef, refActive, refKey);
  useVideoSync(vidOut);
  useVideoSync(vidRef);
  usePlacementPreview(cvOut, cvPrev, previewing ? placeLines : null);

  // ---- 轨显示过滤 + 热重载
  const outText = useRef<string | null>(null);
  const applyFilter = useCallback(async (reload: boolean) => {
    if (!out.inst.current) return;
    if (reload || outText.current == null) outText.current = await api.assText('out');
    const st = useStore.getState();
    const f = filterAss(outText.current, st.vis, st.onlyUnits);
    out.inst.current?.setTrack(f.text);
    set({ monitorKept: f.kept });
    out.inst.current?.setCurrentTime(clock.t());
  }, [out.inst, set]);
  useEffect(() => { if (out.ready) void applyFilter(false); }, [vis, onlyUnits, out.ready, applyFilter]);
  useEffect(() => { if (assRev && out.ready) void applyFilter(true); }, [assRev, out.ready, applyFilter]);

  // ---- 选区叠层 (1920x1080 坐标)
  const overlay = useMemo(() => {
    const ink: number[][] = [];
    const bands: { li: number; b: number[] }[] = [];
    const seen = new Set<number>();
    for (const [a, b] of ranges) for (let g = a; g <= b; g++) {
      const f = ix.flat[g];
      if (!f) continue;
      const c = lines[f.li].chars[f.ci];
      if (c.box) ink.push(c.box);
      if (!seen.has(f.li)) { seen.add(f.li); if (lines[f.li].band?.length === 4) bands.push({ li: f.li, b: lines[f.li].band }); }
    }
    return { ink, bands };
  }, [ranges, ix, lines]);
  const hitBoxes = menu?.source === 'monitor' ? menu.hits ?? [] : [];

  // ---- 右键命中
  const onCtx = async (e: React.MouseEvent, r: Rect) => {
    e.preventDefault();
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * PW;
    const y = ((e.clientY - rect.top) / rect.height) * PH;
    const cx = e.clientX, cy = e.clientY;
    if (!r.w) return;
    const hits = await api.hit(+clock.t().toFixed(3), +x.toFixed(1), +y.toFixed(1)).catch(() => []);
    // PR 行为: 命中的句不在选区里, 先换选区 (点在字框里选该字, 否则整句)
    const st = useStore.getState();
    const cnt = new Map<string, number>();
    for (const h of hits) { const u = h.name.split(':').pop()!; cnt.set(u, (cnt.get(u) ?? 0) + 1); }
    const unit = [...cnt.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
    const li = unit ? st.lines.findIndex((l) => l.name === unit) : -1;
    if (li >= 0) {
      const ci = st.lines[li].chars.findIndex((c) => c.box && x >= c.box[0] && x <= c.box[2] && y >= c.box[1] && y <= c.box[3]);
      const g = ci >= 0 ? st.ix.start[li] + ci : null;
      if (g != null) { if (!inRanges(st.ranges, g)) setSelection([[g, g]], g, g); }
      else if (!inRanges(st.ranges, st.ix.start[li])) selectLine(li);
    }
    set({ menu: { x: cx, y: cy, source: 'monitor', hits } });
  };

  // ---- 划变手柄
  const onWipe = (e: React.PointerEvent) => {
    e.stopPropagation();
    const el = e.currentTarget as HTMLElement;
    const fr = el.parentElement!.getBoundingClientRect();
    el.setPointerCapture(e.pointerId);
    const mv = (m: PointerEvent) => set({ wipe: Math.max(0.02, Math.min(0.98, (m.clientX - fr.left) / fr.width)) });
    const up = () => { el.removeEventListener('pointermove', mv); el.removeEventListener('pointerup', up); };
    el.addEventListener('pointermove', mv);
    el.addEventListener('pointerup', up);
  };

  const src = project?.video && edl && edl.segments.length ? `/media/${edl.segments[0].src}` : null;
  const showOut = !(compare === 'ab' && abShow === 'ref');
  const outClip = compare === 'wipe' ? `inset(0 ${((1 - wipe) * 100).toFixed(2)}% 0 0)` : undefined;
  const refClip = compare === 'wipe' ? `inset(0 0 0 ${(wipe * 100).toFixed(2)}%)` : undefined;
  const refInline = refActive && !side;

  return (
    <div className={s.box} ref={box} data-testid="monitor" data-compare={compare} data-ab={abShow}
      data-kept={kept} data-ref-ready={ref.ready || undefined} data-preview={previewing || undefined}>
      <div className={s.frame} style={{ left: rOut.x, top: rOut.y, width: rOut.w, height: rOut.h }} data-testid="frame-out"
        onContextMenu={(e) => onCtx(e, rOut)}>
        {src && <video ref={vidOut} className={s.video} src={src} muted playsInline preload="auto" style={mvStyle} data-mv-off={!mvOn || undefined} data-testid="video-out" />}
        <canvas ref={cvOut} className={s.subs} data-hidpi="monitor" style={{ visibility: showOut && !previewing ? 'visible' : 'hidden', clipPath: outClip }} />
        {previewing && <canvas ref={cvPrev} className={s.subs} data-hidpi="monitor-preview" data-testid="monitor-preview"
          style={{ visibility: showOut ? 'visible' : 'hidden', clipPath: outClip }} />}
        {refInline && <canvas key={refKey} ref={cvRef} className={s.subs} data-hidpi="monitor-ref"
          style={{ visibility: compare === 'ab' && abShow === 'out' ? 'hidden' : 'visible', clipPath: refClip }} />}
        <svg className={s.ov} viewBox={`0 0 ${PW} ${PH}`} preserveAspectRatio="none">
          {overlay.bands.map(({ li, b }) => (
            <rect key={`b${li}`} data-testid="sel-band" x={b[0]} y={b[1]} width={b[2] - b[0]} height={b[3] - b[1]}
              fill="none" stroke="#f0b85a" strokeWidth={2} strokeDasharray="10 6" vectorEffect="non-scaling-stroke" />
          ))}
          {overlay.ink.map((b, i) => (
            <rect key={`i${i}`} data-testid="sel-ink" x={b[0]} y={b[1]} width={b[2] - b[0]} height={b[3] - b[1]}
              fill="rgba(110,168,255,0.12)" stroke="#6ea8ff" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
          ))}
          {hitBoxes.map((h) => (
            <rect key={`h${h.ln}`} data-testid="hit-box" x={h.box[0]} y={h.box[1]} width={h.box[2] - h.box[0]} height={h.box[3] - h.box[1]}
              fill="none" stroke="#ef6b6b" strokeWidth={1} vectorEffect="non-scaling-stroke" />
          ))}
        </svg>
        {previewing && (
          <div className={s.prevNote} data-testid="preview-note" role="note" data-at={placeCand?.v === 'top' ? 'bottom' : 'top'}>
            <b>⚠ 近似预览</b><span>{(placeNote || '').replace(/^近似预览[,，]\s*/, '').replace(/[,，]\s*/g, ' · ')}</span>
          </div>
        )}
        {compare === 'wipe' && (
          <div className={s.wipe} style={{ left: `${wipe * 100}%` }} onPointerDown={onWipe} data-testid="wipe-handle">
            <span className={s.wl}>out</span><span className={s.wr}>参考</span>
          </div>
        )}
        {compare === 'ab' && <div className={s.badge} data-testid="ab-badge">{abShow === 'ref' ? '参考 (static/music 参考 ASS)' : '成品 (out.ass)'}</div>}
        {side && <div className={s.badge}>out</div>}
      </div>
      {side && (
        <div className={s.frame} style={{ left: rRef.x, top: rRef.y, width: rRef.w, height: rRef.h }} data-testid="frame-ref">
          {src && <video ref={vidRef} className={s.video} src={src} muted playsInline preload="auto" style={mvStyle} data-mv-off={!mvOn || undefined} data-testid="video-ref" />}
          <canvas key={refKey} ref={cvRef} className={s.subs} data-hidpi="monitor-ref" />
          <div className={s.badge}>参考</div>
        </div>
      )}
    </div>
  );
}
