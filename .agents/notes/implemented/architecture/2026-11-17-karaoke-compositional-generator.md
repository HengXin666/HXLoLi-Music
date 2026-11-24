# Agent Note: 组合式生成: 设计中间表示 + 形状来源 + 母题来源门禁 + 跨作品指纹

Status: implemented

Decision-ID: karaoke-compositional-generator

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/layer/compose.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/draw/resolve.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/tests/test_compose.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/gate/check_motif_mono.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/kfx/fingerprint.py`
- `.agents/skills/hx-anime-karaoke-ass/scripts/qa/calib_vector_gap.py`
- `.agents/skills/hx-anime-karaoke-ass/templates/motif_img.py`
- `.agents/skills/hx-anime-karaoke-ass/examples/mushoku_ed1/make_ass.py`

## Problem

生成器每首歌手写 fx 函数, 母题形状种类刚过门禁下限 (15 对 19), 示例与模板只有一套, 新歌容易长成旧歌的样子.
已知质量雷未闭合: 贴图缩放锯齿 (known-gaps #10), 矢量母题压字无门禁 (#13), 一句两套主母题 (#14), 具象素材缩小失读 (#12).
实测: 用本 skill 出的两份已发布成品 (比翼の羽根 / オンリー) 特效指纹相似度 0.969, 与外部同一模板批量出的两首 (0.999) 同一量级.

## Decision

- 设计中间表示 `design.ir.json` (`assfx/layer/ir.py`): 词汇表 motifs (形状来源 + 组合法 + 色 + 出处) 与逐句 role / main / aux / clock / color / relation / text / escape. 结构严格校验, 多余键报错.
- 组合器 `assfx/layer/compose.py` 把 IR 翻成 Generator 的 PHRASES / FXMAP: 主母题 x 组合法 (`grammar.py` 八种) + 辅助母题 + 句间关系; escape 是逃生口, 指向工程专属函数, 写不出来的句子照旧手写.
- 形状来源 `assfx/draw/`: kit (几何语汇) / glyph (字体轮廓, 二次贝塞尔按 2/3 规则精确升三次) / svg (faithful 精确矢量) / prop; 预缩放帧序列 `frames.py` (贴图生长逐档换图, 不用 \fsc, 收 #10); 可读下限 `legible.py` (素材配置写 kind / min_px, 低于下限 place() 不贴图回退另一种形式, 收 #12).
- 母题来源: 运行期记录 (`provenance.py`, `@main_motif`), 生成后写 `<out>.motifs.json`; 门禁 `gate/check_motif_mono.py` 一句 >1 主母题或与声明不符判 FAIL (#14).
- 跨作品指纹 `kfx/fingerprint.py`: 6 组分布余弦均值; 阈值按 17 份已发布成品标定, 见 `shared/calibration.md`.
- 矢量压字 (#13) 的 over 兜底与前景判定按 `qa/calib_vector_gap.py` 在 8 份本 skill 成品上的分布定分界, 见 `shared/calibration.md`.
- 示例 オンリー 改为 IR 驱动, 33 句全部走逃生口 (定稿视觉不动), 输出与改前逐字节相同.

## Alternatives considered

- 什么都不做, 继续每首手写: 最强理由是定稿质量全靠手写拿到, 抽象层可能让效果平庸. 否决: 同质化已经实测到 (0.969), 且一句两套主母题这类雷靠人眼才发现.
- 复用现有 PHRASES 字典加几个字段: 最强理由是零迁移成本. 否决: PHRASES 只有 fx 名, 母题 / 时钟 / 关系散在函数体和注释里, 门禁与指纹读不到.
- 做成模板库 (每类句子一个现成函数): 最强理由是出片快. 否决: 模板化正是同质化来源; 词汇表与组合法分开才能每首换语言.
- 静态读代码查一句两套主母题: 最强理由是不用跑生成器. 否决: 主母题常藏在转调里 (fx_sword_cut 调 fx_main.p29), 静态读名字会漏.

## Consequences

- 新歌的逐句设计写在 IR 里, 验收台单元与种子不变 (key 仍按 lines 取).
- 逃生口函数要用 `@main_motif` 声明它调用的主母题函数, 否则门禁只认 IR 声明.
- 指纹只能说 "长得像", 不能说 "好不好"; 上限质量仍靠盲审.
