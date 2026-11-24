# Agent Note: kfx_build 同时写 manifest, 验收台才有歌词

Status: implemented

Decision-ID: kfx-manifest-for-studio

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/kfx/kfx_build.py`

## Problem

新工程 (ときめきアン・ドゥ・トロワ) 在验收台左侧歌词栏为空. studio 的 lyrics() 只读 out.<x>.manifest.json 的 phrase 单元, kfx_build 只写 ASS; オンリー 能显示是因为工程里留着旧生成器写的 manifest.
同次发现: 台子的声音只认工程里的 song.mp3 / song.flac / song.m4a (或参考解析结果), 视频轨按静音处理, 新工程没有 song.* 就没有声音.

## Decision

kfx_build 每次 build 在 ASS 旁写 out.kfx.manifest.json: 每行一个 phrase 单元 (name LNN, t, band, chars [ch, a, b, x, w], cn), meta.text_lift = 0. ASS 字节不变.
新工程从 base.mp4 拷出 song.m4a (ffmpeg -i base.mp4 -vn -c:a copy song.m4a), 后续写进 kfx_README 新工程步骤.

## Verification

kfx_test.py ALL PASS (オンリー 金样逐字节不变); 新工程 /api/lyrics 返回 63 行.

## Alternatives considered

- 什么都不做: 新工程台子歌词永远为空, 只有 オンリー 靠旧文件能用, 不取.
- 复用现有方案 (旧生成器的 manifest 写法): 旧生成器已删; 这里沿用它的格式 (phrase 单元字段相同), 只把写入挪进 kfx_build.
- 让 studio 在没有 manifest 时从 timing.json + lyrics.txt 现算歌词: 要在台子里重复一遍 kfx 的排版 (x / w), 两份代码会漂移, 不取.
- 只给新工程手工补 manifest: 每次重建就丢, 不取.

## Consequences

- 每次 kfx_build 多写一个 json (~70KB); 验收台歌词栏、设计稿跟随、选区评审对所有 kfx 工程可用.
- manifest 的 band / chars 是排版结果的快照, 只给台子用, 不是输入.
