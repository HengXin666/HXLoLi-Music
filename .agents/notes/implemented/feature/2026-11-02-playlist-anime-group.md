# Agent Note: 播放列表按番剧归属分组

Status: implemented

Decision-ID: playlist-anime-group

## Code

- `py/music/scanner.py`

## Problem

用户 2026-11-02 希望主站播放器"把这些歌曲按照番剧进行归类, 以树形展开"。`playlist.json` 每首歌只有 `id, title, artist, audioUrl, assUrl, assFonts, coverUrl`, 没有番剧字段, 前端无从分组。
实际归属早就写在目录里: `static/music/<番剧名>/<歌>.mp3`。凭歌名人工对表已经错过三条 (朝焼けのスターマイン、モノクローム果樹園、トコハナ), 所以归属必须从路径读, 不能手写。
例外: `static/music/ちぃむdmp☆/` 是歌手目录, 不是番剧。

## Decision

- `py/music/scanner.py` 的 `anime_of()` 取 `static/music/` 下的一级目录名, 原样写成 `track["anime"] = {"title": 目录名}`; 直接放在根下, 或目录名在 `py/music/config.py` 的 `NON_ANIME_DIRS` 里的, 写 `null`。
- 字段放在 `audioUrl` 之后, 随 `playlist.json` 一起生成; 不拆到 `static/info/`。
- 不在这里关联 ANiMeRecord id: 目录名与番剧库名称不一一对应 (中日文混用), 由主站按名称匹配, 匹配不上就不关联。
- 本次同时手动更新 `playlist.json` (与脚本输出一致), 让本地 9527 立即可见; 下一次 CI 生成会覆盖成同样内容。

## Alternatives considered

- 什么都不做: 最强理由是 15 首歌一页列表也能看完。否决: 用户明确要按番剧归类, 而且天使の3P 一部就有 4 首, 平铺列表看不出归属。
- 复用现有方案 (手写一张 歌 id -> 番剧 的映射表): 最强理由是能写任意名字、能直接写 ANiMeRecord id。否决: 人工对表已经错三条; 目录本来就是归属的唯一真源, 新歌放进目录就自动归类, 映射表每加一首都要维护。
- 把归属写进音频标签 (TALB 专辑名): 专辑名是唱片名, 不是番剧名, 很多曲子没有。否决。

## Consequences

- `playlist.json` 每首歌多一个 `anime` 字段 (`{"title": 目录名}` 或 `null`), 位置在 `audioUrl` 之后; 旧字段不变, 不读该字段的前端不受影响.
- 新歌只要放进 `static/music/<番剧名>/` 就自动归类, 不需要维护映射表; 放在根下或歌手目录的歌, 需要把目录名加进 `py/music/config.py` 的 `NON_ANIME_DIRS` 才会写成 `null`.
- 归属完全取决于目录名: 同一部番用了两种目录名 (中日文混用) 会被分成两组, 由主站按名称匹配时处理.
- 与 ANiMeRecord 的关联不在此处做, 匹配不上的番剧只显示目录名.
- 2026-11-09 本次入库用 `git commit --no-verify` 绕过本地 pre-commit, 由用户授权, 不是校验通过. 红线诊断: 0 项错误, 4 项 code-only-diff, 完整 JSON 存在 `.agents/reports/redline/2026-11-09-commit-b.json`.
- 豁免的 4 条: `py/music/config.py` 与 `py/music/scanner.py` 各对 `process/2026-09-28-kfx-quality-redline.md` 和 `bug-fix/2026-10-02-kfx-gate-structural-criteria.md` 报一次. 根因: 这两篇 kfx 记录同时管 `py/music` 与 `py/ass`, 本次改动属于本记录 (番剧分组), 与 kfx 质量红线和门禁判据无关; 若给两篇 kfx 记录补一条 Consequences, 并集配对会转而对本次没有改的 `py/ass`, `py/ass/model` 报 note-only. 同类问题与长期解法见 `.agents/notes/implemented/feature/2026-11-09-karaoke-fx-gate-studio.md`.
