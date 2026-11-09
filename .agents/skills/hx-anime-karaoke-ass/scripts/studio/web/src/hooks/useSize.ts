import { useEffect, useState } from 'react';

/*
 * Agent Notes: studio 画布尺寸
 * .agents/notes/implemented/feature/2026-11-09-karaoke-studio.md
 */
export function useSize(ref: React.RefObject<HTMLElement | null>) {
  const [s, setS] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setS({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return s;
}
