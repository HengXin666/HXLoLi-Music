/* 播放时钟: 音频为主时钟, 放在 React 外. 组件用 subscribe 订阅, 每帧回调, 不触发 React 重渲染. */
type Fn = (t: number) => void;
type StateFn = (playing: boolean) => void;

class Clock {
  readonly audio: HTMLAudioElement;
  private fns = new Set<Fn>();
  private last = -1;
  private raf = 0;
  private manual = 0; // 没有音频时的手动时间
  // 没有音频的工程 (static/music 里没有这首的音频): 用墙钟走时间, 播放 / 播放选区 / 循环照常可用.
  // 以前 play() 对空 src 的 audio 调用会被拒, paused 却变 false, 时间不走, 播放选区永远停不下来.
  private silentAt: number | null = null; // 墙钟起点 (performance.now), null = 没在走
  private rate = 1;

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
    // 播放状态变化必须无条件通知: rAF 环只在 t 变化时回调, 暂停那一刻 t 若没变 (静音工程 silentAt 路径、
    // currentTime 精度截断) 订阅者一次都收不到, 视频就停不下来. 音频的 play/pause/ended 事件 (静音工程由
    // play()/pause() 自己派发) 与 play()/pause() 调用本身都会走 kick(), 去重后各回调一次.
    for (const ev of ['play', 'playing', 'pause', 'ended', 'seeked']) this.audio.addEventListener(ev, () => this.kick());
  }
  /**
   * 播放状态变了 (或 seek 落定): 先通知状态订阅者, 再不论 t 有没有变都把当前 t 推给所有逐帧订阅者一次.
   * Agent Notes: 暂停后视频不停 (逐帧回调只在 t 变化时触发)
   * .agents/notes/implemented/bug-fix/2026-11-19-studio-pause-video-sync.md
   */
  private kick() {
    const p = this.playing;
    if (p !== this.lastPlaying) { this.lastPlaying = p; this.stateFns.forEach((f) => this.callState(f, p)); }
    const t = this.t();
    this.last = t;
    this.fns.forEach((f) => this.call(f, t));
  }
  private lastPlaying = false;
  private stateFns = new Set<StateFn>();
  /** 订阅播放状态 (true=在播). 订阅时立即回调一次当前状态. */
  subscribeState(f: StateFn): () => void { this.stateFns.add(f); this.callState(f, this.playing); return () => { this.stateFns.delete(f); }; }
  private callState(f: StateFn, p: boolean) {
    try { f(p); } catch (e) { console.error('[clock] 状态订阅者抛错:', e); }
  }
  t(): number {
    if (this.audio.src) return this.audio.currentTime;
    return this.silentAt == null ? this.manual : this.manual + ((performance.now() - this.silentAt) / 1000) * this.rate;
  }
  get playing(): boolean { return this.audio.src ? !this.audio.paused : this.silentAt != null; }
  get duration(): number { return Number.isFinite(this.audio.duration) ? this.audio.duration : 0; }
  setSrc(url: string | null) { if (url) this.audio.src = url; }
  play() {
    if (!this.audio.src) { if (this.silentAt == null) { this.silentAt = performance.now(); this.audio.dispatchEvent(new Event('play')); } return Promise.resolve(); }
    return this.audio.play().then(() => this.kick(), () => this.kick());
  }
  pause() {
    if (!this.audio.src) { if (this.silentAt != null) { this.manual = this.t(); this.silentAt = null; this.audio.dispatchEvent(new Event('pause')); } return; }
    this.audio.pause();
    this.kick();   // 不等异步 pause 事件, 同步把视频停掉
  }
  toggle() { if (this.playing) this.pause(); else void this.play(); }
  seek(t: number) {
    const d = this.duration || Infinity;
    const v = Math.max(0, Math.min(d, t));
    if (this.audio.src) this.audio.currentTime = v;
    else { this.manual = v; if (this.silentAt != null) this.silentAt = performance.now(); }
  }
  setRate(r: number) {
    if (!this.audio.src && this.silentAt != null) { this.manual = this.t(); this.silentAt = performance.now(); }
    this.rate = r;
    this.audio.playbackRate = r;
  }
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
