# Agent Note: 母题图到歌词的间隙是硬约束, 生成器与门禁共用一把尺子

Status: implemented

Decision-ID: karaoke-motif-text-gap

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/draw/motif_gap.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/qa/validate_ass.py`

## Problem

`\1img` 贴进来的母题图 (手, 发辫, 剑) 放在行首或行尾外侧时, band 剩余的宽度往往放不下. `FX.shape` 的 band 夹取会把图推回 band 内, 但不报错. 推回的方向正对着字, 结果是图压字, 整个流程没有任何一处报出来.

2026-11-10 的 オンリー 第 31 句 (托水球的手) 实测: 行尾在 x 约 1530, band 右界在 x 约 1626, 只剩 96px. 110 宽的手请求的中心在 1576.7, 被夹回 1570.1. 再加 dx +12 请求到 1588.7, 仍被夹回 1570.1. 拇指和「た」重叠, 生成器和 validate 都没有报.

## Decision

- 唯一的尺子在 `assfx/draw/motif_gap.py`, 由三个函数组成:
  - `image_points`: 量图. 取 alpha > 8 的像素 (含外发光), 按 `\an5` `\pos` 中心落点, 乘静态 `\fscx/\fscy`, 转静态 `\frz`.
  - `text_ink_boxes`: 量字. 只取同 band 的 ly: 事件里填充可见的那几层, 静态 `\1a&HFF&` 的纯光晕层不算. 位置用静止位置 (`\pos`, 或 `\move` 的终点). 每个字的框是字体 glyf 包围盒加静态 `\bord`.
  - `min_gap`: 取点到框的最小距离. 只比较显示时间有交叠的图和字.
- 阈值 `MOTIF_GAP = 8` px.
- 生成器侧在下发前用这把尺子, 按 FX.shape 同一公式模拟夹取, 求出满足间隙的最大尺寸, 再按比例缩小并打印原尺寸和新尺寸. 发生夹取时打印 WARN, 写明位移多少 px.
- 校验器 `qa/validate_ass.py` 调 `check_ass` 兜底, 间隙不足报 `[E] 母题压字`, 退出码为 1.
- 为什么是 E 不是 W: 夹取是静默的, 画面上只差几十像素, 只有机器量得出来. 压字直接伤可读性, 不是可以商量的风格项. 报 W 会淹没在密度和重叠告警里.
- 不静默的边界: 字体不在 fontsdir 时退回 0.72em 估宽. 这个估值可能偏大 (白白缩小图) 也可能偏小 (漏掉压字), 所以框里记下估宽的字体名, 校验器报 W, 生成器打印 WARN. 用 `\move` 定位的图暂时只报 W, 不量间隙.

## Alternatives considered

- 放宽母题层的 band: 能直接腾出位置. 否决. band 是 validate 的根基, 为贴图改 band 等于拆掉门禁.
- 母题改放到字的上方或下方: 能绕开横向空间不够的问题. 否决作为通用解. 换位置治标不治本, 而且要改每处的布局代码.
- 什么都不做, 每处手工缩 fit: 现状就是这样. 否决. 夹取会继续静默, 下一处还会再踩一次.
- 门禁只报 WARN: 否决, 理由同上一节.
- 尺子放进 `draw/image.py`: 否决. 那样文件会超过 300 行, 而且尺子被生成器和门禁两处共用, 本来就该独立成一层.

## Consequences

- 2026-11-10 在 オンリー p31 上验证 (工程层的贴图器在 `dev/`, 没有进 skill):
  - 当前配置 (fit w76): 间隙 10.1px, 通过, 退出码 0.
  - dx -9: 间隙 1.1px, 报 [E], 退出码 1.
  - dx -40: 间隙 0.0px, 报 [E], 退出码 1.
  - fit w200: 自动缩到 80, 间隙 8.3px, 通过.
  - fit w200 并关掉自动缩: 夹取 WARN 显示位移 -67px, 压到「れ」, 报 [E].
  - 没有贴图的 out.ass 逐字节不变, validate 通过.
- 尺子量的是静止状态. 入场或高亮的瞬时放大 (`\t` 里的 `\fsc`) 和光晕 (`\blur`) 不算, 所以字的 pop 动画瞬间可能贴近图.
- 用字形量出来的间隙, 比按渲染像素 (亮度过半) 量的更严, p31 上 10.1px 对 14.3px.
- 工程层贴图器 (slot 配置, 融合字段, 自动缩) 目前只在 `dev/` 里. 等 7 处母题都验证过之后再迁进 skill 的 examples 或 templates.
