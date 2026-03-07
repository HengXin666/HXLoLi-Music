/**
 * 简化版音乐播放器状态管理 (基于 Zustand)
 *
 * 与 HXLoLi 前端仓库的 musicStore 不同，这里不需要：
 * - 跨 Tab 同步 (Leader/Follower)
 * - CDN URL 转换
 * - 播放列表远程加载
 *
 * 直接本地播放，用于测试 ASS 歌词渲染效果
 */
import { create } from 'zustand';
import type { MusicTrack } from './types';

/** 播放模式 */
export type PlayMode = 'list-loop' | 'single-loop' | 'shuffle';

interface MusicPlayerState {
  playlist: MusicTrack[];
  trackIndex: number;
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  volume: number;
  playMode: PlayMode;
  initialized: boolean;
  showLyrics: boolean;
  lyricsFullscreen: boolean;
  panelExpanded: boolean;
}

interface MusicPlayerActions {
  init: (playlist: MusicTrack[]) => void;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  next: () => void;
  prev: () => void;
  seek: (time: number) => void;
  setTrack: (index: number) => void;
  setVolume: (vol: number) => void;
  toggleLyrics: () => void;
  toggleLyricsFullscreen: () => void;
  cyclePlayMode: () => void;
  togglePanel: () => void;
  closePanel: () => void;
  /** 获取当前播放时间 (直接从 audio 读取) */
  getInterpolatedTime: () => number;
}

export type MusicStore = MusicPlayerState & MusicPlayerActions;

// 单例 audio 元素
let audio: HTMLAudioElement | null = null;
let rafId: number | null = null;

function getNextIndex(current: number, total: number, mode: PlayMode): number {
  if (total === 0) return 0;
  switch (mode) {
    case 'single-loop': return current;
    case 'shuffle': {
      if (total <= 1) return 0;
      let next = current;
      while (next === current) next = Math.floor(Math.random() * total);
      return next;
    }
    default: return (current + 1) % total;
  }
}

function getPrevIndex(current: number, total: number, mode: PlayMode): number {
  if (total === 0) return 0;
  switch (mode) {
    case 'single-loop': return current;
    case 'shuffle': {
      if (total <= 1) return 0;
      let prev = current;
      while (prev === current) prev = Math.floor(Math.random() * total);
      return prev;
    }
    default: return (current - 1 + total) % total;
  }
}

export const useMusicStore = create<MusicStore>((set, get) => {
  function startTimeUpdate() {
    stopTimeUpdate();
    const tick = () => {
      if (audio && !audio.paused) {
        set({ currentTime: audio.currentTime, duration: audio.duration || 0 });
      }
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
  }

  function stopTimeUpdate() {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  function loadTrack(index: number, autoPlay = false, seekTo?: number) {
    if (!audio) return;
    const list = get().playlist;
    if (index < 0 || index >= list.length) return;
    const track = list[index];

    audio.pause();
    set({ trackIndex: index, currentTime: seekTo ?? 0, duration: 0, isPlaying: autoPlay });
    audio.src = track.audioUrl;

    const onCanPlay = () => {
      if (!audio) return;
      audio.removeEventListener('canplay', onCanPlay);
      audio.removeEventListener('error', onError);
      set({ duration: audio.duration || 0 });
      if (seekTo !== undefined && seekTo > 0) audio.currentTime = seekTo;
      if (autoPlay) {
        audio.volume = get().volume;
        audio.play().then(() => set({ isPlaying: true })).catch(() => set({ isPlaying: false }));
      }
    };
    const onError = () => {
      if (!audio) return;
      audio.removeEventListener('canplay', onCanPlay);
      audio.removeEventListener('error', onError);
      console.error('[MusicPlayer] 加载音频失败:', track.audioUrl);
      set({ isPlaying: false });
    };
    audio.addEventListener('canplay', onCanPlay);
    audio.addEventListener('error', onError);
  }

  return {
    playlist: [],
    trackIndex: 0,
    currentTime: 0,
    duration: 0,
    isPlaying: false,
    volume: 0.7,
    playMode: 'list-loop',
    initialized: false,
    showLyrics: true,
    lyricsFullscreen: false,
    panelExpanded: false,

    init: (playlist: MusicTrack[]) => {
      if (get().initialized) return;
      set({ initialized: true, playlist, showLyrics: true });

      audio = new Audio();
      audio.volume = get().volume;

      audio.addEventListener('ended', () => {
        const s = get();
        if (s.playlist.length > 0) {
          if (s.playMode === 'single-loop') {
            audio!.currentTime = 0;
            audio!.play().then(() => set({ isPlaying: true })).catch(() => set({ isPlaying: false }));
          } else {
            const next = getNextIndex(s.trackIndex, s.playlist.length, s.playMode);
            loadTrack(next, true);
          }
        }
      });

      audio.addEventListener('loadedmetadata', () => {
        if (audio) set({ duration: audio.duration || 0 });
      });

      startTimeUpdate();
      if (playlist.length > 0) loadTrack(0, false);
    },

    getInterpolatedTime: () => {
      if (audio) return audio.currentTime;
      return get().currentTime;
    },

    play: () => {
      if (!audio || get().playlist.length === 0) return;
      audio.play().then(() => set({ isPlaying: true })).catch(() => set({ isPlaying: false }));
    },
    pause: () => {
      if (!audio) return;
      audio.pause();
      set({ isPlaying: false });
    },
    toggle: () => {
      if (!audio || get().playlist.length === 0) return;
      if (audio.paused) {
        audio.play().then(() => set({ isPlaying: true })).catch(() => set({ isPlaying: false }));
      } else {
        audio.pause();
        set({ isPlaying: false });
      }
    },
    next: () => {
      const s = get();
      if (s.playlist.length === 0) return;
      loadTrack(getNextIndex(s.trackIndex, s.playlist.length, s.playMode), true);
    },
    prev: () => {
      const s = get();
      if (s.playlist.length === 0) return;
      loadTrack(getPrevIndex(s.trackIndex, s.playlist.length, s.playMode), true);
    },
    seek: (time: number) => {
      if (!audio) return;
      audio.currentTime = time;
      set({ currentTime: time });
    },
    setTrack: (index: number) => loadTrack(index, true),
    setVolume: (vol: number) => {
      if (audio) audio.volume = vol;
      set({ volume: vol });
    },
    toggleLyrics: () => set((s) => ({ showLyrics: !s.showLyrics })),
    toggleLyricsFullscreen: () => set((s) => ({ lyricsFullscreen: !s.lyricsFullscreen })),
    cyclePlayMode: () => {
      const modes: PlayMode[] = ['list-loop', 'single-loop', 'shuffle'];
      const current = get().playMode;
      const idx = modes.indexOf(current);
      set({ playMode: modes[(idx + 1) % modes.length] });
    },
    togglePanel: () => set((s) => ({ panelExpanded: !s.panelExpanded })),
    closePanel: () => set({ panelExpanded: false }),
  };
});
