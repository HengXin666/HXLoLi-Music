# 49 生成: `scripts/assfx/` 库结构

库在 `<skill>/scripts/assfx/`, **写生成器之前读这一节**, 不要从零猜 API.

- `lyrics.py` 歌词标注解析: 逐字 `[漢字|よみ]` / `[世界|せ.かい]` / 熟字训 `[今日|=きょう]`、合いの手 call 行、`{English|かな}`、片假名/小假名/标点规则
- `layout.py` 逐字坐标(fontTools 宽度 × libass 缩放)、振假名、中文、`Phrase.band`
- `anim.py` `Karaoke` 渲染器: 阴影/底字/高亮/辉光/长音光晕五层; 入场 slide/rise/drop/zoom/flip/flipx/spin/fade/glitch,
  退场 wind/rise/sink/scatter/zoom/flip/fade, 高亮 wipe/bloom/jump/flipx/shake/ink; 英文单元按音拍分段擦亮
- `shapes.py` 40+ 矢量图形(心/花/樱/枫叶/羽毛/雪花/麦穗/飞鸟/泪滴/火焰/裂纹/碎片/闪电/刀光/剑/盾/锁链/魔法阵/符文环/
  治愈十字/魔女帽/书/书页/烛火/红线/涟漪/面纱/齿轮/眼/罗盘/光芒…)+ `flat/affine/norm/bbox`
- `props.py` **番剧专属道具的精密矢量路径**: 红眼 / 巨石碑 / 錵弹丸 / 猫耳 / 黑魔女帽 /
  太刀 / 盾 / シェンフィールド球 / 常花 等 41 个(MDI + Bootstrap Icons, 经 svg2ass 采样).
  **手绘拼贴画不出可辨认的物件** —— 同一物体两者差一个量级(自行车 3148 字符 vs 两个圆圈).
  `P.prefetch()` 预热, 断网时失败项逐个报出, 不静默降级.
- `motifs.py` **意境层与逐词母题**: `AMBIENT`(10 种意境背景)/ `MOTION`(12 种逐词动作)/
  `ambient()` / `keyword_motifs()` / `apply()`. 一句 = 1 意境 + 1 主母题 + ≤3 逐词母题.
- `beat.py` **卡点层**: `MusicEvents`(载 `review/music-events.json`) / `beat_scatter`(按十六分网格群发) /
  `beat_pulse`(拍级呼吸) / `beat_drop`(段落起爆) / `beat_sink`(低频下沉); `BEAT_SHAPES` 是 10 种现代几何.
  **独立时钟** —— 不要用 `k.t_in/k.t_end` 当区间(那又跟句走了). 规格与实测参数见 `../../44-beat/index.md`.
- `bg.py` **背景层**: `SceneTimeline`(载 `review/scene-timeline.json`) / `bg_drift`(色温跟着画面的低存在感颗粒) /
  `bg_frames`(镜头切换处的整片柔光) / `hue_to_hex`. 与卡点层的分工(平坦 vs 脉冲)见 `../../45-bg/index.md`.
- `image.py` **图片层**: `put_image`(纹理必须按图片真实尺寸出矩形, 否则平铺成 N 张) /
  `pop_image`(卡点弹出) / `side_slots`(左右元素) / `check_images`(边缘体检).
  注意 `a_peak` 是 **alpha 值**(0=不透明, 255=全透明), 图片默认 8. 见 `../../46-image/index.md`.
- `carry.py` **句间承接**: `Carry`(跨句状态: 末色/末位置/剩余动量/末图形/强度) /
  `entry`(入场接上一句动量) / `tint`(色温承接) / `boost`(意象长一级) / `from_events`(从刚发射的事件反解).
  见 `../../48-thread/index.md`.
- `color.py` **色彩系统**: `Scheme`(段落色域, 逐字在折线上游走) / `Palette` / `make_hl_color`(接 `Karaoke` 的
  `hl_color` 回调) / `fold` / `find_break`(句内折返点挂在语义反转词上). 见 `../../47-color/index.md`.
- `svg2ass.py` **精细图形: 网络 SVG -> ASS 绘图代码**. `from_url/from_file/fetch`.
  手绘拼贴(circle+rect)做不出"精细"的物体; 改用现成矢量图, 实测自行车转出 **3148 字符**的真实路径.
  缓存**不在 skill 目录**(`ASSFX_SVG_CACHE` 或 `~/.cache/hx-anime-karaoke-ass/svg`), 可离线复现.
- `bake_shapes.py` 把网络图标渲染成**实心**路径(线稿直接采样出来只有 1~2px 细线, 等于没画).
  用法: `hx-karaoke assfx/bake_shapes.py --out proj/assets/shapes.json [--video proj/base.mp4]`.
  **产物必须写进工程目录**, 脚本会拒绝把 `--out` 指向 skill 内部.
- `fx.py` band 约束发射器: `shape/text/burst/drift/pulse/glow/floor_spin`
- `geom.py` 事件包围盒估算(缩放、frz/frx/fry 含 libass 透视、`\org`、边框/模糊、clip)
- `core.py` `Doc`(样式、band 登记、写出)、颜色/时间工具
- `gen.py` `Generator`: 逐句出入场窗口规划、渲染、band 登记、标题/间奏/片尾卡(`card()`); `find/seq/span/mid/flicker/sway` 小工具
- `line.py` / `ribbon.py` / `thread.py` —— 线条、缎带、缝线类几何的共用实现(画飘带/红线/锁链时用)

## 两条几何铁律(写在实现里, 别绕过)

9. **不用 `\frx` 做大图形**: libass 透视距离只有 ~312px, 半径 >150px 的图形倾斜会畸变甚至翻到镜头后.
   地面魔法阵用 `shapes.flat()` 预压扁 + `FX.floor_spin()` 逐帧旋转.
10. **绘图要归一化**: libass 把 `\an5` 绘图的原点放在对齐框左上角, 以 (0,0) 为中心画的图会偏移 (xmin,ymin);
   `shapes.norm()`(`FX.shape` 已自动调用).

另有两条来自实测的绘图格式要求:
- **`\p1` 里必须逐点带 `l`**: `m x y a b c d` 会被 libass 当成「一串单点路径」, 填充面积为 0, 图形退化成 1px 点.
- **多个绘图叠加时每个部件要各自 `\pos`**: `FX.shape` 会 `norm()` 居中, 图形里写的偏移会丢失.
