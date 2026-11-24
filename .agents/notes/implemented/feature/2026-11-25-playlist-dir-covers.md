# Agent Note: 播放列表导出目录封面

Status: implemented

Decision-ID: playlist-dir-covers

## Code

- `py/music/scanner.py`

## Problem

用户 2026-11-25 希望主站播放列表按文件夹 (番剧) 树形展示, 并显示文件夹封面, "文件夹可能有图片"。`playlist.json` 只有每首歌的 `coverUrl`, 前端不知道哪个目录自带封面, 只能拿歌曲封面拼图。

## Decision

- 约定: 目录封面是该目录里的 `cover.*` 或 `folder.*` (扩展名取 `COVER_EXTENSIONS`)。和 `find_matching_cover` 的目录级兜底同名, 一张图同时是目录封面和该目录里无封面歌曲的封面。
- `py/music/scanner.py` 的 `dir_covers_of()` 从 `static/music/` 下一级开始, 逐级向下到歌曲所在目录, 有封面的写成 `track["dirCovers"] = {"番剧A": "/static/music/番剧A/cover.jpg", "番剧A/OST": ...}`; 一张都没有就不写该字段。
- 字段跟着每首歌走, 不单独出一份目录表: `playlist.json` 是数组, 加顶层对象会破坏旧前端; 同目录的歌重复几十字节, 可以接受。主站按 key 合并。

## Alternatives considered

- 什么都不做: 最强理由是前端用歌曲封面拼图已能区分目录。否决: 用户明确说文件夹会有自己的图; 没有歌曲封面的目录 (Charlotte, 罪恶王冠等) 只能显示音符。
- 复用现有方案 (前端直接请求 `<目录>/cover.jpg`): 最强理由是音乐库零改动。否决: 不知道扩展名也不知道有没有, 每个目录要试多次, 大量 404 还会被多 CDN 竞速放大。
- 改 `playlist.json` 为 `{tracks, folders}` 对象: 结构更干净。否决: 主站旧版本和本地 serve.py 都按数组读, 要两仓同时切换。

## Consequences

- 往 `static/music/<目录>/` 放一张 `cover.jpg` 就有目录封面, 不用改配置。
- 该目录里没有同名封面的歌也会用这张图作 `coverUrl` (原有兜底, 本次未改)。
- 当前仓库还没有任何目录封面, 本次生成的 `playlist.json` 不变。
