/**
 * 主应用组件 - HXLoLi-Music 本地测试预览
 *
 * 提供：
 * 1. 播放列表面板（选歌、播放/暂停、进度条）
 * 2. ASS 歌词悬浮窗渲染
 * 3. 音量控制
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
    FaMusic, FaPause, FaPlay, FaRandom,
    FaRetweet,
    FaStepBackward, FaStepForward, FaVolumeDown, FaVolumeMute, FaVolumeUp
} from 'react-icons/fa';
import AssLyrics from './AssLyrics';
import AssLyricsLibass from './AssLyricsLibass';
import { useMusicStore, type PlayMode } from './musicStore';
import type { MusicTrack } from './types';

/** 渲染引擎类型 */
type RendererEngine = 'octopus' | 'libass-wasm';

const RENDERER_KEY = 'hxloli-lyrics-renderer';

function loadRenderer(): RendererEngine {
  try { const raw = localStorage.getItem(RENDERER_KEY); if (raw === 'libass-wasm') return 'libass-wasm'; } catch {}
  return 'octopus';
}
function saveRenderer(engine: RendererEngine) {
  try { localStorage.setItem(RENDERER_KEY, engine); } catch {}
}

/** 格式化时间 mm:ss */
function formatTime(seconds: number): string {
  if (!seconds || !isFinite(seconds)) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

const PLAY_MODE_INFO: Record<PlayMode, { icon: React.ReactNode; title: string }> = {
  'list-loop': { icon: <FaRetweet size={14} />, title: '列表循环' },
  'single-loop': {
    icon: (
      <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
        <FaRetweet size={14} />
        <span style={{ position: 'absolute', fontSize: 7, fontWeight: 'bold', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}>1</span>
      </span>
    ),
    title: '单曲循环',
  },
  'shuffle': { icon: <FaRandom size={14} />, title: '随机播放' },
};

export default function App(): React.ReactElement {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rendererEngine, setRendererEngine] = useState<RendererEngine>(loadRenderer);

  const toggleRenderer = useCallback(() => {
    setRendererEngine((prev) => {
      const next: RendererEngine = prev === 'octopus' ? 'libass-wasm' : 'octopus';
      saveRenderer(next);
      return next;
    });
  }, []);

  const pl = useMusicStore((s) => s.playlist);
  const trackIndex = useMusicStore((s) => s.trackIndex);
  const currentTime = useMusicStore((s) => s.currentTime);
  const duration = useMusicStore((s) => s.duration);
  const isPlaying = useMusicStore((s) => s.isPlaying);
  const volume = useMusicStore((s) => s.volume);
  const showLyrics = useMusicStore((s) => s.showLyrics);
  const playMode = useMusicStore((s) => s.playMode);

  const init = useMusicStore((s) => s.init);
  const toggle = useMusicStore((s) => s.toggle);
  const next = useMusicStore((s) => s.next);
  const prev = useMusicStore((s) => s.prev);
  const seek = useMusicStore((s) => s.seek);
  const setVolume = useMusicStore((s) => s.setVolume);
  const setTrack = useMusicStore((s) => s.setTrack);
  const toggleLyrics = useMusicStore((s) => s.toggleLyrics);
  const cyclePlayMode = useMusicStore((s) => s.cyclePlayMode);

  const currentTrack = pl[trackIndex] ?? null;

  // 加载播放列表
  useEffect(() => {
    fetch('/playlist.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: MusicTrack[]) => {
        setLoading(false);
        init(data);
      })
      .catch((err) => {
        setLoading(false);
        setError(`加载播放列表失败: ${err.message}\n请确保已运行 Python 脚本生成 playlist.json`);
      });
  }, [init]);

  // 进度条拖拽
  // 核心思路: 拖拽期间用 ref 冻结 slider 显示值, 松手后执行 seek
  const seekingRef = useRef(false);
  const seekValueRef = useRef(0);
  const [seekRender, setSeekRender] = useState(0); // 用于触发重渲染

  const handleSeekStart = useCallback(() => {
    seekingRef.current = true;
    seekValueRef.current = useMusicStore.getState().currentTime;
  }, []);

  const handleSeekInput = useCallback((e: React.FormEvent<HTMLInputElement>) => {
    const val = parseFloat((e.target as HTMLInputElement).value);
    seekingRef.current = true;
    seekValueRef.current = val;
    setSeekRender((n) => n + 1);
  }, []);

  const handleSeekEnd = useCallback(() => {
    if (seekingRef.current) {
      const val = seekValueRef.current;
      seekingRef.current = false;
      seek(val);
      setSeekRender((n) => n + 1);
    }
  }, [seek]);

  // 全局 mouseup 监听: 防止鼠标移出 slider 后释放导致 seek 不提交
  useEffect(() => {
    const onGlobalUp = () => {
      if (seekingRef.current) {
        const val = seekValueRef.current;
        seekingRef.current = false;
        seek(val);
        setSeekRender((n) => n + 1);
      }
    };
    window.addEventListener('mouseup', onGlobalUp);
    window.addEventListener('touchend', onGlobalUp);
    return () => {
      window.removeEventListener('mouseup', onGlobalUp);
      window.removeEventListener('touchend', onGlobalUp);
    };
  }, [seek]);

  // 音量
  const [muted, setMuted] = useState(false);
  const prevVolumeRef = useRef(volume);

  const toggleMute = useCallback(() => {
    if (muted || volume === 0) {
      const restoreVol = prevVolumeRef.current > 0 ? prevVolumeRef.current : 0.7;
      setVolume(restoreVol);
      setMuted(false);
    } else {
      prevVolumeRef.current = volume;
      setVolume(0);
      setMuted(true);
    }
  }, [muted, volume, setVolume]);

  const VolumeIcon = volume === 0 || muted ? FaVolumeMute : volume < 0.5 ? FaVolumeDown : FaVolumeUp;

  if (loading) {
    return (
      <div style={pageStyle}>
        <div style={cardStyle}>
          <div style={{ textAlign: 'center', padding: 40 }}>
            <div style={{ fontSize: 32, marginBottom: 16 }}>🎵</div>
            <div style={{ color: 'rgba(255,255,255,0.6)' }}>加载播放列表中...</div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={pageStyle}>
        <div style={cardStyle}>
          <div style={{ textAlign: 'center', padding: 40 }}>
            <div style={{ fontSize: 32, marginBottom: 16 }}>❌</div>
            <div style={{ color: '#ff6b6b', whiteSpace: 'pre-line' }}>{error}</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      {/* 顶部标题 */}
      <header style={{ textAlign: 'center', marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: '#fff', margin: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
          <span>🎵</span>
          <span>HXLoLi-Music 本地测试</span>
        </h1>
        <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 13, marginTop: 4 }}>
          测试 ASS 歌词渲染效果 • 预处理裁剪 • 悬浮窗
        </p>
        {/* 渲染引擎切换 */}
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)' }}>渲染引擎:</span>
          <button onClick={toggleRenderer}
            style={{
              fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 12,
              border: '1px solid', cursor: 'pointer', transition: 'all 0.15s',
              ...(rendererEngine === 'libass-wasm'
                ? { background: 'rgba(0, 255, 136, 0.15)', borderColor: '#00ff88', color: '#00ff88' }
                : { background: 'rgba(136, 136, 255, 0.15)', borderColor: '#8888ff', color: '#8888ff' }),
            }}
            title={`当前: ${rendererEngine}\n点击切换渲染引擎`}>
            {rendererEngine === 'libass-wasm' ? '🚀 libass-wasm (原生图片)' : '🐙 SubtitlesOctopus'}
          </button>
        </div>
      </header>

      {/* 主播放器 */}
      <div style={cardStyle}>
        {/* 当前曲目 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          {currentTrack?.coverUrl ? (
            <img src={currentTrack.coverUrl} alt="" style={{ width: 64, height: 64, borderRadius: 8, objectFit: 'cover' }} />
          ) : (
            <div style={{ width: 64, height: 64, borderRadius: 8, background: 'linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,136,255,0.12))', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <FaMusic size={24} color="rgba(255,255,255,0.4)" />
            </div>
          )}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 16, fontWeight: 600, color: '#fff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {currentTrack?.title || '无曲目'}
            </div>
            <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)', marginTop: 2 }}>
              {currentTrack?.artist || 'Unknown'}
            </div>
            {currentTrack?.assFonts && currentTrack.assFonts.length > 0 && (
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', marginTop: 4 }}>
                🔤 所需字体: {currentTrack.assFonts.join(', ')}
              </div>
            )}
          </div>
        </div>

        {/* 进度条 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <span style={timeLabelStyle}>{formatTime(seekingRef.current ? seekValueRef.current : currentTime)}</span>
          <input type="range" min={0} max={duration || 0} step={0.1}
            value={seekingRef.current ? seekValueRef.current : currentTime}
            onMouseDown={handleSeekStart}
            onTouchStart={handleSeekStart}
            onInput={handleSeekInput}
            onMouseUp={handleSeekEnd}
            onTouchEnd={handleSeekEnd}
            style={progressBarStyle} />
          <span style={timeLabelStyle}>{formatTime(duration)}</span>
        </div>

        {/* 控制按钮 */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16, marginBottom: 12 }}>
          <button onClick={cyclePlayMode} style={ctrlBtnStyle} title={PLAY_MODE_INFO[playMode].title}>
            {PLAY_MODE_INFO[playMode].icon}
          </button>
          <button onClick={prev} style={ctrlBtnStyle} title="上一曲"><FaStepBackward size={14} /></button>
          <button onClick={toggle} style={ctrlBtnMainStyle} title={isPlaying ? '暂停' : '播放'}>
            {isPlaying ? <FaPause size={18} /> : <FaPlay size={18} style={{ marginLeft: 2 }} />}
          </button>
          <button onClick={next} style={ctrlBtnStyle} title="下一曲"><FaStepForward size={14} /></button>
        </div>

        {/* 音量 + 歌词按钮 */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}>
            <button onClick={toggleMute} style={volumeBtnStyle} title={muted || volume === 0 ? '取消静音' : '静音'}>
              <VolumeIcon size={14} />
            </button>
            <input type="range" min={0} max={1} step={0.01} value={volume}
              onChange={(e) => { setVolume(parseFloat(e.target.value)); if (parseFloat(e.target.value) > 0) setMuted(false); }}
              style={volumeBarStyle} />
            <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', minWidth: 28, textAlign: 'right' }}>
              {Math.round(volume * 100)}%
            </span>
          </div>
          {currentTrack?.assUrl && (
            <button onClick={toggleLyrics}
              style={{ ...lyricsBtnStyle, ...(showLyrics ? { background: '#ff88ff', borderColor: '#ff88ff', color: '#fff' } : {}) }}
              title={showLyrics ? '隐藏歌词' : '显示歌词'}>
              词
            </button>
          )}
        </div>

      </div>

      {/* 播放列表 */}
      <div style={{ ...cardStyle, marginTop: 16 }}>
        <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.4)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>
          播放列表 ({pl.length})
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {pl.map((track, i) => (
            <button key={track.id} onClick={() => setTrack(i)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
                borderRadius: 6, border: 'none', cursor: 'pointer', textAlign: 'left', width: '100%',
                fontSize: 13, transition: 'background 0.15s',
                background: i === trackIndex ? 'rgba(255, 136, 255, 0.12)' : 'transparent',
                color: i === trackIndex ? '#ff88ff' : '#e0e0e0',
              }}>
              <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', minWidth: 16, textAlign: 'right' }}>{i + 1}</span>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{track.title}</span>
              <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', flexShrink: 0 }}>{track.artist}</span>
              {track.assUrl && <span title="有歌词" style={{ fontSize: 10 }}>🎤</span>}
            </button>
          ))}
        </div>
      </div>

      {/* ASS 歌词悬浮窗 */}
      {rendererEngine === 'libass-wasm' ? <AssLyricsLibass /> : <AssLyrics />}
    </div>
  );
}

// ========== 样式 ==========

const pageStyle: React.CSSProperties = {
  maxWidth: 480,
  margin: '0 auto',
  padding: '32px 16px',
  minHeight: '100vh',
};

const cardStyle: React.CSSProperties = {
  background: 'rgba(255,255,255,0.06)',
  borderRadius: 12,
  padding: 16,
  border: '1px solid rgba(255,255,255,0.08)',
};

const timeLabelStyle: React.CSSProperties = {
  fontSize: 11,
  color: 'rgba(255,255,255,0.5)',
  minWidth: 32,
  textAlign: 'center',
  fontVariantNumeric: 'tabular-nums',
};

const progressBarStyle: React.CSSProperties = {
  flex: 1,
  height: 4,
  WebkitAppearance: 'none',
  appearance: 'none' as any,
  background: 'rgba(255,255,255,0.15)',
  borderRadius: 2,
  outline: 'none',
  cursor: 'pointer',
};

const ctrlBtnStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: 32, height: 32, border: 'none', background: 'none',
  color: '#e0e0e0', cursor: 'pointer', borderRadius: '50%',
  transition: 'background 0.15s', padding: 0,
};

const ctrlBtnMainStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: 44, height: 44, border: 'none', background: '#ff88ff',
  color: '#fff', cursor: 'pointer', borderRadius: '50%',
  transition: 'opacity 0.15s', padding: 0,
};

const volumeBtnStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: 24, height: 24, border: 'none', background: 'none',
  color: 'rgba(255,255,255,0.6)', cursor: 'pointer', borderRadius: 4, padding: 0,
};

const volumeBarStyle: React.CSSProperties = {
  width: 80, height: 3,
  WebkitAppearance: 'none', appearance: 'none' as any,
  background: 'rgba(255,255,255,0.15)', borderRadius: 2, outline: 'none', cursor: 'pointer',
};

const lyricsBtnStyle: React.CSSProperties = {
  fontSize: 12, fontWeight: 700, width: 28, height: 28,
  borderRadius: 6, border: '1.5px solid rgba(255,255,255,0.25)',
  background: 'none', color: 'rgba(255,255,255,0.6)',
  cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
  transition: 'all 0.15s', padding: 0,
};
