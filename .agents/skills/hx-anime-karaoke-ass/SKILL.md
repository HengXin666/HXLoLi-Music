---
name: hx-anime-karaoke-ass
disable-model-invocation: true
description: >-
  为番剧 OP/ED/插曲 MV 制作字幕组级的卡拉OK 特效字幕 (ASS): 日文逐拍高亮 + 振假名 + 中文翻译,
  特效用 \p 矢量绘图按画面与歌词含义逐句设计, 并严格限制在字幕附近 (歌词块包围盒外扩 5%).
  链路: 找完整版 MV 与去水印, 歌词来源定级 (一律网络, 禁止从画面识别), 语音时间轴校准,
  读音基准 (CTC 听音优先于词典), 人声分离, CTC 音拍级强制对齐, 网络逐字歌词融合, 节拍网格,
  频谱人工校时与时间轴体检, 振假名实测定位, 原作内涵考据与番剧元素表, 逐句特效设计,
  生成, 强制门禁与自动校验, 抽帧目检, 渲染出片.
  当用户要做卡拉OK字幕 / 特效歌词 / K轴 / ASS特效 / 歌词MV / 番剧OP/ED字幕时使用.
---

# 番剧卡拉OK 特效字幕 (ASS)

目标: 一条完整 MV + 一份 ASS. 歌词卡得准 (每个音拍落在音符起音上), 排得稳 (注音贴字, 中文不抢画面),
特效有意义 (每句都能说出对应哪个镜头 / 哪句词义 / 番剧的哪个设定), 不越界 (只在字幕附近 5%).

先读 `shared/hard-rules.md` - 十条跨步骤铁律, 违反任一条都要返工.

脚本, 模板与示例都不在本文件里列: 走到哪一步, 那一步的契约会点名它需要的脚本与参考文件.
一律 `uv run <脚本>` (uv 按脚本的 inline 依赖元数据自建环境), 不要用裸 `python`.

## 步骤表

| # | 步骤 | 关心什么 | 契约 |
|---|------|---------|------|
| 00 | setup | 字体与算力设备 | `steps/00-setup/index.md` |
| 01 | source | 完整版 1080p, 水印干净 | `steps/01-source/index.md` |
| 02 | lyrics | 来源定级 + 标注 + 读音基准 | `steps/02-lyrics/index.md` |
| 03 | offset | 网络时间轴与这份视频差多少 | `steps/03-offset/index.md` |
| 04 | vocals | 分出人声与伴奏 | `steps/04-vocals/index.md` |
| 05 | align | CTC 音拍级强制对齐 | `steps/05-align/index.md` |
| 06 | kf-timing | 网络逐字定形状 + 本地定平移 | `steps/06-kf-timing/index.md` |
| 07 | grid | 节拍网格与吸附 (含 07b 重对齐) | `steps/07-grid/index.md` |
| 08 | review-timing | 人工校时 + 时间轴体检 (会非零退出) | `steps/08-review-timing/index.md` |
| 09 | ruby | 注音高度实测 | `steps/09-ruby/index.md` |
| 10 | anime-bg | 原作内涵 + 番剧元素表 | `steps/10-anime-bg/index.md` |
| 11 | design | 逐句特效设计 | `steps/11-design/index.md` |
| 12 | generate | 把设计表翻译成生成器 | `steps/12-generate/index.md` |
| 13 | validate | 门禁 + 自动校验 + 可见性 | `steps/13-validate/index.md` |
| 14 | inspect | 抽帧目检 | `steps/14-inspect/index.md` |
| 15 | render | 封装出片 | `steps/15-render/index.md` |

`steps/NN-xxx/index.md` 是那一步的契约: 只做什么 / 命令与脚本 / 判据 / 产物 / 过关条件.
步骤内可插拔的做法放在同级 `impl/` 下, 契约会点名什么时候读哪个.
