/* 播放时钟: 音频为主时钟, 放在 React 外. 组件用 subscribe 订阅, 每帧回调, 不触发 React 重渲染. */
type Fn = (t: number) => void;

class Clock {
  readonly audio: HTMLAudioElement;
  private fns = new Set<Fn>();
  private last = -1;
  private raf = 0;
  private manual = 0; // 没有音频时的手动时间

  constructor() {
    this.audio = new Audio();
    this.audio.preload = 'auto';
    const loop = () => {
      const t = this.t();
      if (t !== this.last) {
        this.last = t;
        this.fns.forEach((f) => f(t));
      }
      this.raf = requestAnimationFrame(loop);
    };
    this.raf = requestAnimationFrame(loop);
  }
  t(): number { return this.audio.src ? this.audio.currentTime : this.manual; }
  get playing(): boolean { return !this.audio.paused; }
  get duration(): number { return Number.isFinite(this.audio.duration) ? this.audio.duration : 0; }
  setSrc(url: string | null) { if (url) this.audio.src = url; }
  play() { return this.audio.play().catch(() => undefined); }
  pause() { this.audio.pause(); }
  toggle() { if (this.audio.paused) void this.play(); else this.pause(); }
  seek(t: number) {
    const d = this.duration || Infinity;
    const v = Math.max(0, Math.min(d, t));
    if (this.audio.src) this.audio.currentTime = v; else this.manual = v;
  }
  setRate(r: number) { this.audio.playbackRate = r; }
  subscribe(f: Fn): () => void { this.fns.add(f); f(this.t()); return () => { this.fns.delete(f); }; }
  dispose() { cancelAnimationFrame(this.raf); }
}

export const clock = new Clock();
