# Agent Note: 无歌手标签时从文件名拆出歌手

Status: implemented

Decision-ID: playlist-artist-title-split

## Code

- `py/music/scanner.py`

## Problem

用户 2026-11-25 指出歌手和歌名本该分开。没有歌手标签的音频 (Charlotte, ヨスガノソラ, 罪恶王冠) 在 `playlist.json` 里 `title` 是整个文件名 `Lia - Bravely You`, `artist` 是 `Unknown`, 主站列表只能把整串当歌名显示。仓库里此前没有文件名解析, `metadata.py` 只读标签, 读不到就用文件名。

## Decision

- `split_artist_title()` 只在歌手缺失 (空或 `Unknown`) 且标题含 ` - ` 时生效, 按第一个 ` - ` 拆成 `歌手 - 歌名`; 有歌手标签的曲目一律不动。
- 放在 `scanner.py` 组装 track 时, 不放进 `extract_metadata`: 元数据缓存保持原样, 规则改了不用清缓存。
- 拆不开的 (东方的 `果てなき風の軌跡さえ_风祝`) 仍是 `Unknown`, 主站本来就隐藏 `Unknown`。

## Alternatives considered

- 什么都不做, 补齐音频标签: 最强理由是标签才是权威来源。否决: 要逐个改二进制文件, 新加的歌还会再犯。
- 同时识别 `歌名 - 歌手`: 有标签的曲目文件名两种顺序都有。否决: 无标签时没有依据判断哪边是歌手, 现有三首无标签曲目都是 `歌手 - 歌名`, 猜错比不拆更糟。

## Consequences

- 无标签曲目的文件名应写成 `歌手 - 歌名`; 写反了会把歌名当歌手, 这时给音频补上歌手标签即可覆盖。
- 下一次 pipeline 生成的 `playlist.json` 里这三首会变: `Bravely You` / `Lia`, `比翼の羽根 (OP)` / `eufonius`, `The Everlasting Guilty Crown (罪恶王冠 OP2)` / `EGOIST`。
