# Agent Note: 一首歌挂多份 ASS 歌词 (播放列表 lyrics 字段)

Status: implemented

Decision-ID: playlist-multi-lyrics

## Code

- `py/music/lyrics.py`

## Problem

主站播放器 (HXLoLi `src/utils/music/musicDataLoader.ts`, 2026-11-24 music-player-v2) 已支持一首歌多份歌词: `MusicTrack.lyrics: [{ key, label, assUrl, detailId? }]`, 没选过时播第一份, 选择按歌存 localStorage, 每份歌词的字体 / 边界框读 `static/info/<detailId 或歌曲 id>.json`. 音乐库只认 `<音频同名>.ass` 一份, 产不出 `lyrics`. 2026-11-26 用户要把 罪恶王冠 kfx 成品挂上去, 同时保留旧 assfx 版作另一个选项.

## Decision

**只用文件名约定, 不加配置文件; 只有多份时才出 `lyrics`.**

- `<音频同名>.ass` = 默认歌词, key `default`, 排第一 (播放器默认播它). 原有字段 (`assUrl`, `assFonts`, `static/info/<id>.json`) 照旧由它产出, 旧前端不受影响.
- `<音频同名>.<标签>.ass` = 另一份, key = 标签, 只允许 `[A-Za-z0-9_-]` (标签进 URL 和 info 文件名), 按标签排序. 各自过 kfx_gate 红线, 不过的只跳过这一份. 字体 / 图片 / 边界框写到 `static/info/<id>.<标签>.json`, playlist 里 `detailId` 指向它; `fonts` 与默认歌词相同 (目录级 + 全局).
- 展示名: ASS `[Script Info]` 里一行注释 `; lyric-label: <名字>` (ASS 注释, libass 忽略); 没写时默认歌词叫 "默认", 其它叫标签名.
- 只有一份歌词的歌不出 `lyrics` 字段, playlist.json 对其它歌逐字节不变.
- 同时修: kfx_gate `has_outline` 遇到 `\bord3.6.0` 这类畸形数值会抛异常让整个 make.sh 崩溃, 改为只取第一个数.

## Alternatives considered

- 什么都不做: 最强理由是可以直接覆盖旧 ASS. 否决: 用户要求旧版保留作选项, 主站已经做好了切换.
- 旁边放一个 `lyrics.json` 写顺序和展示名: 更灵活. 否决: 多一份要同步的文件; 标签 + 注释已能表达默认项和展示名.
- 标签直接用中文展示名: 省掉注释. 否决: 中文进 info 文件名和 CDN 路径, 切片与缓存都要转义; 标签当稳定 key, 展示名可随时改.

## Consequences

- 发布新版本时把要默认的那份放成 `<同名>.ass`, 旧版改名成 `<同名>.<标签>.ass`, 加一行 `; lyric-label:` 即可, 不用改代码.
- 换默认项 = 交换两个文件名; 用户在主站已选过的 key 仍有效 (key 跟标签走), 没选过的跟着新默认.
- 删掉一份带标签的歌词后, 旧的 `static/info/<id>.<标签>.json` 不会自动删, 需要手动清.

- 2026-11-28: 加 "; lyric-desc: <一句话>" 风格说明, 写进 lyrics 条目的 desc, 博客悬停歌词按钮时显示. 罪恶王冠, オンリー, ろりこんでよかった~ 的两份歌词按风格起了名字 (用户: 别让所有歌词看起来都一样)
