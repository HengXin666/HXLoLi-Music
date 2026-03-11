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
  /** 封面图片 URL (可选) */
  coverUrl?: string;
  /** ASS 歌词中使用的字体名列表 (可选) */
  assFonts?: string[];
}

/** 歌曲详细配置 (按需加载, 从 static/info/{id}.json 获取) */
export interface MusicTrackDetail {
  /** 歌词所需的字体文件 URL 列表 (可选) */
  fonts?: string[];
  /** ASS 字体名到字体文件 URL 的映射 (可选, 供 SubtitlesOctopus availableFonts 使用) */
  assFontMap?: Record<string, string>;
  /** ASS \\1img 引用的图片路径列表 (可选) */
  assImages?: string[];
  /** ASS \\1img 图片的 base64 数据, key=相对路径, value=data URI */
  assImageData?: Record<string, string>;
  /** ASS \\1img 图片事件列表 */
  assImageEvents?: Array<{
    start: number;
    end: number;
    img: string;
    pos?: [number, number];
    move?: [number, number, number, number];
    moveT?: [number, number];
    fadIn?: number;
    fadOut?: number;
    an?: number;
    drawW?: number;
    drawH?: number;
  }>;
  /** ASS 预扫描边界框 */
  assBounds?: {
    topYMin: number;
    topYMax: number;
    btmYMin: number;
    btmYMax: number;
    left: number;
    right: number;
    leftT?: number;
    rightT?: number;
    leftB?: number;
    rightB?: number;
  };
  /** ASS 预扫描边界框时间轴 */
  assBoundsTimeline?: Array<{
    t: number;
    topYMin: number;
    topYMax: number;
    btmYMin: number;
    btmYMax: number;
    left: number;
    right: number;
    leftT?: number;
    rightT?: number;
    leftB?: number;
    rightB?: number;
  }>;
}
