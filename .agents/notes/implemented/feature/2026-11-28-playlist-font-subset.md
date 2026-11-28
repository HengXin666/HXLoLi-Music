# Agent Note: 歌词字体按本曲用字子集化, 红线只提示

Status: implemented

Decision-ID: playlist-font-subset

## Code

- `py/music/font_subset.py`
- `py/music/gen_music_playlist.py`
- `py/music/scanner.py`
- `py/music/kfx_gate.py`

## Problem

用户 2026-11-28 反馈主站歌词加载很慢。实测每首歌的 `static/info/<id>.json` 的 `fonts` 都带完整字体: 兜底 NotoSansSC 17.8MB, 目录里的 LXGW WenKai 23MB 和 Shippori Mincho 14MB, 一首歌合计 40 到 55MB。ASS 本身已经走 gzip, 只剩原大小的 10% 左右, 所以瓶颈在字体。

同一天, 扫描时的内嵌红线把 6 首已在验收台发布的 kfx 成品挡在播放列表外。用户说进了 static/music 的都是在验收台发布过, 本人看过确认的, 红线不解决问题。

另外 `_furi_lag` 逐对比较注音和主字, 3 万多条事件的成品要跑十几分钟。

## Decision

- `font_subset.py` 按本曲 ASS 的 Dialogue 正文 (去掉 `{...}`) 加 ASCII 收字符集, 用 fontTools 裁出子集, 写到 `static/cdn/subset/<hash>/<原文件名>`。文件名和字体家族名都不变, 前端照旧按文件名写进 Worker 的 `/fonts/`
- hash 由原字体 md5 和字符集算出, 字体和歌词不变就复用。本次没用到的子集目录会被删掉
- 小于 1MB 的字体不裁, 省不了多少
- 裁剪失败就用原字体, 不影响生成
- 带标签的歌词按各自的 ASS 裁
- 红线未通过只打印, 不再 `return None`
- `_furi_lag` 先解析成整数, 再排序加二分, 只看可能重叠的主字。结果与逐对比较一致 (并列时同样取原顺序靠前的那条)
- 可读配色的配对跳过 `\1a&HFF&` 开头的光晕或垫底层, 理由同 bord0 的发光层

## Alternatives considered

- 字体转 woff2: 体积更小。否决: libass 依赖 FreeType 带 brotli 才能读 woff2, 没确认主站的 SubtitlesOctopus 构建带了它
- 前端按需取字形: 改动大, 还要服务端配合
- 保留红线, 加白名单文件: 用户说进 static 就是白名单, 再维护一份名单是重复劳动

## Consequences

- 实测子集大小: NotoSansSC 16.9MB 到约 300KB, LXGW 23.2MB 到约 195KB, Shippori 13.9MB 到约 250KB, Lolita 11.4MB 到 110KB。整个 subset 目录约 4MB
- 用 ffmpeg 的 subtitles 滤镜, 拿原字体和子集字体渲染罪恶王冠 kfx 版的 30s, 45s, 75s, 120s 四帧, 逐像素完全一致
- 主站 `AssLyrics.tsx` 发现本曲带 NotoSansSC 子集时, 就不再下载 17MB 的完整版 (HXLoLi 仓库同日提交)
- 红线不再拦截。质量把关只靠验收台发布这一步
