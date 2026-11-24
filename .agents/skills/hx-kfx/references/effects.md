# 效果实现 (scripts/kfx_*.py)

| 模块 | 内容 |
|---|---|
| `kfx_lyrics.py` | lyrics.txt + timing.json -> 句 / 单元 / 音拍 |
| `kfx_layout.py` | 用真实字形宽度排版 (libass 字号 = winAscent+winDescent, 实测误差 < 1%), 振假名按音拍分位 |
| `kfx_fx_text.py` | 文字层: 每单元 4 层 (光晕 / 未唱 / 已唱擦亮 / 起音光), 进退场, 中文行 |
| `kfx_fx_scene.py` | 粒子与名场面 |
| `kfx_shapes.py` | 绘图: 雪花, 叶, 花瓣, 水滴, 火苗, 碎片, 魔法阵, 裂纹, 红线, 光束 |
| `kfx_build.py` | 排程 (一次一行) 与组装 |
| `kfx_check.py` / `kfx_preview.py` | 门禁与抽帧 |

## 文字层

- 光晕 (layer 1): `\1a&HFF&` 只留描边, `\bord7\blur8` 暗色 -> 任何底片都可读
- 未唱 (layer 2): 段落 base 色 + 暗描边, 进场动画在这一层
- 已唱 (layer 3): 从 `\clip(xl,..,xl,..)` 用 `\t` 擦到 `\clip(xl,..,xr,..)`, 时长 = 该单元的音长; 白字 + 发光色描边, 起音回弹 `\fscx110 -> 100`
- 起音光 (layer 4): 发光色描边光圈, 0.55s 内放大并消失
- 退场是独立事件 (同一事件里不能有两个 `\move`), 退场波从左到右, 在 tout 结束, 下一行不用等

## 排程

一次一行. 一行在首音前 0.75s 进场, 但不早于上一行最后一个音拍结束; 无空隙时新行边唱边进, 旧行用 >= 0.22s 快速退场.

## 名场面

- cracks: 单元起音时从字处向两侧画出裂纹 (clip 展开 0.14s) + 白色冲击光 + 碎片迸射
- magic_circle: 带刻度与六芒星的双环, `\frx66` 倒在地面并缓慢自转; libass 透视会把倾斜圆盘的视觉中心往下推约 0.42r, 已补偿
- red_thread: 正弦细线, 随演唱进度从左到右拉出, 位于日文与中文之间
- rays: 5 道光束从上方斜落, 慢摆; flip: 已唱层 `\fry360`; tilt: `\frz-9` 歪头; tear: 字下落三滴; veil: 雾幕横扫; whiteout: 背后白色光晕

## 加新效果

在 `kfx_direction.py` 的可选集合里登记名字, 在 `kfx_fx_text.exit_tags` / `_enter_tags` 或 `kfx_fx_scene._m_<kind>` 里实现, 再在 `references/direction-schema.md` 写一行. 不要在生成器里写只对某首歌成立的分支.
