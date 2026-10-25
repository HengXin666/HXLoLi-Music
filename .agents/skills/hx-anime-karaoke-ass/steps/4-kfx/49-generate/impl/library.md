# 生成器怎么写: 库的分工与两条几何铁律

库在 `<skill>/scripts/assfx/`. **不要从零猜 API**  但也不要把它当清单背: 先想清楚你要发什么(一个图形 / 一段文字 / 一层脉冲), 再去对应模块里找发射器

## 按"你想做什么"找模块

| 你想做 | 去哪 | 关键入口 |
|---|---|---|
| 发一个图形 / 文字 / 粒子 / 柔光 | `layer/fx.py` | `FX.shape / text / burst / drift / pulse / glow / floor_spin` |
| 逐字高亮、振假名、中文排版 | `text/anim.py` `text/layout.py` | `Karaoke`(五层: 阴影/底字/高亮/辉光/长音光晕)、`Phrase.band` |
| 解析歌词标注 | `base/lyrics.py` | `[漢字\|よみ]` / `[世界\|せ.かい]` / 熟字训 `[今日\|=きょう]` / call 行 |
| 要一个**几何语汇**(心/花/星/裂纹…) | `draw/shapes.py` | 可参数化: 尺寸、瓣数、角度都能调 |
| 要一个**现成的具象物件**(眼/剑/盾/花/雪) | `asset/props.py` | 拿来即用、不可参数化; **只有通用物件** |
| 要**网络矢量图**转 ASS 路径 | `base/svg2ass.py` | `from_url / from_file / fetch`(带缓存, 可离线复现) |
| 要**实心**图标(线稿会太细) | `asset/bake_shapes.py` | 位图→加粗→取轮廓; 产物**必须写进工程目录** |
| 一句的意境 / 主母题 / 辅助母题 | `deco/motifs.py` | `AMBIENT` / `MOTION` / `ambient()` / `keyword_motifs()` |
| 卡点层(跟音乐网格, 不跟字) | `layer/music/beat.py` | `MusicEvents` / `beat_scatter` / `beat_pulse` / `beat_drop` / `beat_sink` |
| 背景层(跟镜头, 跨句不停) | `layer/music/bg.py` | `SceneTimeline` / `bg_drift` / `bg_frames` |
| 图片层(`\1img`) | `draw/image.py` | `put_image` / `pop_image` / `side_slots` / `check_images` |
| 句间承接(跨句状态) | `layer/carry.py` | `Carry` / `entry` / `tint` / `boost` / `from_events` |
| 色彩系统(段落色域 / 句内游走) | `text/color.py` | `Scheme` / `Palette` / `make_hl_color` / `fold` / `find_break` |
| 逐句出入场窗口 / band 登记 / 卡片 | `layer/gen.py` | `Generator` / `card()`; 小工具 `find/seq/span/mid/flicker/sway` |
| 线条 / 缎带 / 缝线类几何 | `deco/line.py` `deco/ribbon.py` `deco/thread.py` | 画飘带/红线/锁链时用 |
| 事件包围盒估算 | `base/geom.py` | 缩放、`frz/frx/fry`(含 libass 透视)、`\org`、边框/模糊、clip |

`kfx/score/score_kfx.py` 不属 `assfx/` 库: 它读成品 ass 算六组分数(见 `../../5-verify/16-blind-review/index.md`)

## 三条几何铁律(写在实现里, 别绕过)

1. **不用 `\frx` 做大图形**: libass 透视距离只有 ~312px, 半径 >150px 的图形倾斜会畸变甚至翻到镜头后. 地面法阵用 `shapes.flat()` 预压扁 + `FX.floor_spin()` 逐帧旋转
2. **绘图要归一化**: libass 把 `\an5` 绘图的原点放在对齐框左上角, 以 (0,0) 为中心画的图会偏移 (xmin, ymin); `shapes.norm()`(`FX.shape` 已自动调用)
3. **`\p1` 里必须逐点带 `l`**: `m x y a b c d` 会被 libass 当成「一串单点路径」, 填充面积为 0, 图形退化成 1px 点. 多个绘图叠加时**每个部件要各自 `\pos`**  `FX.shape` 会 `norm()` 居中, 图形里写的偏移会丢失
