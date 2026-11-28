# Agent Note: 新版歌词按声明的范围裁剪, 不再动态打标

Status: implemented

Decision-ID: playlist-lyric-box

## Code

- `py/music/lyric_box.py`
- `py/music/scanner.py`

## Problem

用户 2026-11-28 指出: 博客悬浮窗的歌词还是按 ffmpeg 逐帧预扫描出的动态时间轴 (assBoundsTimeline) 来裁剪。可是新版歌词已经规定了展示范围, 理论上可以直接裁, 不需要再动态打标。

skill 的硬规则 5 和 6b 写明: 字幕居中贴底, 特效不出 band。band 是歌词块外扩 5%。这样整片字幕退化成一个固定矩形, 裁剪是常数。逐帧裁剪的实测缩放漂移是 56.6%

## Decision

- `lyric_box.declared_box()` 先读文件自己的声明
  - `; lyric-box: x0 y0 x1 y1`: 新约定, 坐标按 PlayRes。目前还没有文件写它, 留给生成器或验收台发布时写
  - `; assfx-band: <名字> x0 y0 x1 y1 t0 t1`: assfx 每句登记的 band 和时间。按声明直接排成阶梯时间轴, 一句之内是常量。几句交叠时取并集, 句间保持上一句。没写时间就用并集当常量
- 有声明时不跑预扫描
- kfx 成品 (事件 Name 是 `ly:*` / `fx:*`) 不写声明, 但内容按规则都在 kfx_build 的 `P['box']` 里。这里用预扫描的全局并集当常量矩形, 不给时间轴。预扫描结果有缓存
- 其余老歌词照旧用动态时间轴
- 前端不用改: 没有 `assBoundsTimeline` 时, `AssLyrics.tsx` 本来就用 `assBounds` 做常量裁剪

## Alternatives considered

- 让 kfx_build 在 ASS 头写 `; lyric-box:`: 最直接。暂不做: オンリー v2.1 金样要求逐字节重现 (kfx_test), 加一行头会破坏它; 而且用户本地的 kfx_build 有未提交改动
- 从 kfx 事件的坐标静态推 `P['box']`: 要字形宽度, 算不准
- 所有歌词都改常量并集: 老的手工歌词位置会变, 并集太大, 字会被缩小

## Consequences

- 2026-11-28 生成结果: 6 份 kfx 成品走常量矩形, 5 份 assfx 走阶梯时间轴, 其余 8 份仍是动态时间轴
- 抽查比翼の羽根, adrenaline!!!, 罪恶王冠 kfx 版, 每 15 秒渲染一帧, 墨迹全部落在给出的矩形内, 越界 0 px
- 以后 kfx 成品如果写了 `; lyric-box:`, 就连预扫描也不用跑
