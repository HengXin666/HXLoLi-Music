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
    // 先挂下一帧再调订阅者: 任何一个订阅者抛错都不能断掉 rAF 链 (以前 libass 崩后 setCurrentTime 抛 TypeError,
    // 播放头/歌词/时间线/参考侧全停, 音频照响). 挂 rAF 只是登记回调, 帧率不变; 每个订阅者再各自隔离.
    const loop = () => {
      this.raf = requestAnimationFrame(loop);
      const t = this.t();
      if (t !== this.last) {
        this.last = t;
        this.fns.forEach((f) => this.call(f, t));
      }
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
  subscribe(f: Fn): () => void { this.fns.add(f); this.call(f, this.t()); return () => { this.fns.delete(f); this.bad.delete(f); }; }
  /** 订阅者出错只记日志 (每个订阅者只打一次, 不刷屏), 不影响其它订阅者和下一帧. 出错次数挂在 window.__clockErrors 供 e2e 查. */
  private bad = new Set<Fn>();
  private call(f: Fn, t: number) {
    try { f(t); } catch (e) {
      const w = window as unknown as { __clockErrors?: number };
      w.__clockErrors = (w.__clockErrors ?? 0) + 1;
      if (!this.bad.has(f)) { this.bad.add(f); console.error('[clock] 订阅者抛错, 已隔离 (只报一次):', e); }
    }
  }
  dispose() { cancelAnimationFrame(this.raf); }
}

export const clock = new Clock();
