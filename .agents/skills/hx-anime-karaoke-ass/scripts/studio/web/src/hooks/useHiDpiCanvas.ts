import { useEffect, useRef, useState } from 'react';

export interface CanvasSize { w: number; h: number; dpr: number; pw: number; ph: number }

/**
 * HiDPI 画布: ResizeObserver 量 CSS 尺寸, canvas.width/height = 设备像素 (优先 devicePixelContentBoxSize,
 * 否则 round(css x dpr)), 上下文 setTransform(dpr). 监听 matchMedia(resolution) 处理拖到另一块屏.
 * 返回尺寸; 尺寸变化后调用方重画.
 */
export function useHiDpiCanvas(ref: React.RefObject<HTMLCanvasElement | null>): CanvasSize {
  const [size, setSize] = useState<CanvasSize>({ w: 0, h: 0, dpr: 1, pw: 0, ph: 0 });
  const last = useRef('');

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    let mq: MediaQueryList | null = null;
    const apply = (w: number, h: number, pw?: number, ph?: number) => {
      const dpr = window.devicePixelRatio || 1;
      // devicePixelContentBoxSize 只在与 round(css x dpr) 相差 <=1 时采用 (有的环境会报 CSS 像素)
      const ew = Math.round(w * dpr);
      const eh = Math.round(h * dpr);
      const PW = Math.max(1, pw != null && Math.abs(pw - w * dpr) <= 1 ? pw : ew);
      const PH = Math.max(1, ph != null && Math.abs(ph - h * dpr) <= 1 ? ph : eh);
      const key = `${PW}x${PH}@${dpr}`;
      if (key === last.current) return;
      last.current = key;
      if (cv.width !== PW) cv.width = PW;
      if (cv.height !== PH) cv.height = PH;
      cv.dataset.cssW = String(w);
      cv.dataset.dpr = String(dpr);
      setSize({ w, h, dpr, pw: PW, ph: PH });
    };
    const ro = new ResizeObserver((es) => {
      const e = es[es.length - 1];
      const box = (e as ResizeObserverEntry & { devicePixelContentBoxSize?: ReadonlyArray<ResizeObserverSize> })
        .devicePixelContentBoxSize?.[0];
      const r = e.contentRect;
      apply(r.width, r.height, box?.inlineSize, box?.blockSize);
    });
    try { ro.observe(cv, { box: 'device-pixel-content-box' }); } catch { ro.observe(cv); }
    const watchDpr = () => {
      mq?.removeEventListener('change', onDpr);
      mq = matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`);
      mq.addEventListener('change', onDpr);
    };
    function onDpr() {
      const r = cv!.getBoundingClientRect();
      last.current = '';
      apply(r.width, r.height);
      watchDpr();
    }
    watchDpr();
    return () => { ro.disconnect(); mq?.removeEventListener('change', onDpr); };
  }, [ref]);

  return size;
}

/** 1px 线对齐到设备像素中心 */
export const crisp = (x: number, dpr: number) => (Math.round(x * dpr) + 0.5) / dpr;
