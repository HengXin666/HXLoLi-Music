/** 单首歌曲的信息 (与前端 HXLoLi 仓库的 MusicTrack 保持一致) */
export interface MusicTrack {
  /** 歌曲唯一ID */
  id: string;
  /** 歌曲标题 */
  title: string;
  /** 歌手/艺术家 */
  artist: string;
  /** 音频文件URL */
  audioUrl: string;
  /** ASS 歌词文件URL (可选) */
  assUrl?: string;
  /** 歌词所需的字体文件 URL 列表 (可选) */
  fonts?: string[];
  /** 封面图片 URL (可选) */
  coverUrl?: string;
  /** ASS 歌词中使用的字体名列表 (可选) */
  assFonts?: string[];
  /** ASS 预扫描边界框 (由 Python 脚本预计算, 固定 1920x1080 画布) */
  assBounds?: {
    topYMin: number;
    topYMax: number;
    btmYMin: number;
    btmYMax: number;
    left: number;
    right: number;
  };
  /** ASS 预扫描边界框时间轴 (滑动窗口 + EMA 平滑, 每个关键点含时间戳) */
  assBoundsTimeline?: Array<{
    t: number;
    topYMin: number;
    topYMax: number;
    btmYMin: number;
    btmYMax: number;
    left: number;
    right: number;
  }>;
}
