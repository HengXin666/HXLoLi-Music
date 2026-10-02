# 15 封装出片

## 只做这一件事

把 `out.ass` 变成可以**直接发出去看**的东西。两种交付形态, 按需选:

| 形态 | 命令 | 用途 |
|---|---|---|
| **外挂字幕 MKV** | `render.sh` | 交字幕组/自己存档: 视频流原样封装, 字幕独立一轨, 改字幕不用重编码 |
| **烧好字幕的 MP4** | `render_video.py` | 直接发给别人看: 谁播都一样, 不依赖播放器装字体/支持 ASS |

## ⚠ 一条必须先知道的事: 出片不能用 ffmpeg 渲字幕

本仓库的 ASS 由 **HXLoLi 定制版 libass**(SubtitlesOctopus WASM)渲染, 支持
`\1img` 等 VSFilterMod 标签; **系统 ffmpeg 的 libass 不支持**, 遇到它们会
**静默退化成纯色块**. 所以 `ffmpeg -vf subtitles=` 出来的片子,
和观众在站上看到的**不是一回事**(图片层会变成白块).

`render_video.py` 因此走这条链:

    逐帧: SubtitlesOctopus(定制版) -> 透明 PNG
    叠加: ffmpeg overlay 到 MV 同刻帧
    编码: libx264 + aac

## 命令

```bash
# 外挂字幕(几秒, 不重编码)
bash render.sh proj/base.mp4 proj/out.ass "$(hx-karaoke --fonts)" proj/out.mkv

# 烧好字幕的成片
hx-karaoke render_video.py --ass proj/out.ass --video proj/base.mp4 --out proj/out.mp4
hx-karaoke render_video.py ... --start 176 --end 196 --fps 12      # 只出一段
```

## 吞吐与取舍(实测)

约 **1.7 帧/秒**(1920x1080, 含 seek 与 PNG 编解码).

| 帧率 | 全曲(260s)耗时 | 说明 |
|---|---|---|
| 20fps(源) | ~50 分钟 | 最高保真 |
| **12fps** | **~25 分钟** | 推荐; 歌词特效不是高速运动, 观感差别很小 |
| 10fps | ~21 分钟 | 极限 |

**中间帧写到 `~/Storage`, 不写 `/tmp`** —— 全曲 3000+ 张 1920×1080 PNG 约 4~6GB,
而 `/tmp` 是 tmpfs(8GB), 会把它写满(实测写满后**连 shell 都无法输出**, 报
`UNKNOWN: unknown error, write`)。`render_video.py` 默认就写 `~/Storage/hxkv-frames`,
跑完自动清理(要保留加 `--keep-frames`)。

## 产物与过关条件

- 取消静音: `ffprobe` 应看到 `h264` + `aac`, 分辨率为 `PlayResX/Y`, 时长与区间一致
- 抽 3 帧(句首/高潮/句尾)目检: 文字清晰、图片层没有白块、卡点层没有糊成一片
- **片子里的图像必须与 `render_octopus.py` 单帧渲染一致** —— 若不一致,
  说明叠加那一步丢了 alpha 或用了错的帧序列

## 这一步要用的脚本

- `<skill>/scripts/render.sh` - 外挂字幕 MKV(几秒)
- `<skill>/scripts/render_video.py` - 烧字幕 MP4(逐帧走定制版渲染器)
- `<skill>/scripts/render_octopus.py` - 单帧渲染(出片链路的第一步, 也可单独目检)
