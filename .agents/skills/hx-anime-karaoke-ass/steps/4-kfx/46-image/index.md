# 46 图片层设计(抠图 + `\1img`)

## 只做这一件事

挑**少数几张**抠干净的图, 用 `\1img` 在**卡点或特定位置**贴进字幕. 产物是
`proj/assets/*.png` + 生成器里对 `assfx/image.py` 的调用.

## 渲染器前提(先确认这条, 否则整层是空谈)

| 渲染器 | `\1img` |
|---|---|
| 系统 libass(ffmpeg 的 `subtitles=` 滤镜) | **不支持** — 静默退化成纯色填充, **不报错** |
| **HXLoLi 定制版**(SubtitlesOctopus WASM) | **支持**, 另含 `\2img \3img \4img \distort \fsvp \fsc \pbo \rnd \frs` |

本仓库的字幕由定制版渲染(见仓库 `README.md`), 所以这一层成立.
**验证必须用 `render_octopus.py`**: 用 ffmpeg 截图会得到"白块"这种假结论(实测踩过).

```bash
hx-karaoke render_octopus.py proj/out.ass --probe     # 先体检: 渲染器/图片/字体
```

## 两个实测规格

1. **`\1img` 是填充纹理, 不是"贴一张图". 纹理按绘制矩形平铺.**
   矩形 = 图片尺寸时正好显示一次; 矩形更大就铺成 N×M 张
   (实测 300×240 矩形 + 105×84 图 = 铺了 **9 张**兔子).
   所以生成矩形时**必须读图片真实尺寸** —— `assfx/image.py` 的 `put_image` 已经强制这么做.
2. **图片路径相对 ass 文件所在目录, 且必须先写进 worker 虚拟 FS.**
   没写进去时控制台报 `[vsfiltermod] Failed to load image: X (can't fopen)`,
   画面空白但**渲染不失败** —— 静默失败. `render_octopus.py` 会自动把图写进 FS.

## 用量(用户 2026-10-03 定的)

「图片它本身占用是比较大的, 也不需要特别多, 它可能只需要几张在某些位置」
「有些地方是这样子, 但是有些地方就比如说点兔, 他那个确实又可以这么用」

点兔「ときめきポポロン♪」实测用量:
- 共 **11 张图**: 吉祥物全身 105×84, 小表情 5 张 51×44, 人物大图 3 张 375×296
- 出现位置: 句间 / 卡点, 每次 1~2 张, **全曲 <8 处**
- 做法: 小图随字飞出; 大图只在特定句出现

**不是必须每首都用.** 没有合适的吉祥物/符号, 就写"不做".

## 抠图: 质量是硬判据

用户原话: 「只要抠的完整, 你不可能一个人抠了一半, 出来以后,
他的头发整个上边是平的一个矩形, 这样子显然是不对的」

```bash
hx-karaoke cutout.py --from-video proj/base.mp4 --at 24.5 --out proj/assets/eye.png --pad 24
hx-karaoke cutout.py --in proj/assets/eye.png --check-only     # 只体检
```

四条判据(机械可查):

| 检查 | 判据 | 不合规意味着 |
|---|---|---|
| 四边 alpha 实色占比 | 每边 ≤1% | 主体贴边 = 被裁切, 就是"切平的头发" |
| 主体占比 | 8%~85% | 太小=抠漏; 太大=基本没抠 |
| 羽化过渡带 | 存在 0<alpha<248 的像素 | 全二值 = 羽化被砍, 边缘发硬 |
| 图片尺寸 vs 矩形 | 必须相等 | 不等会平铺成多张 |

**反验样本(已实测)**: `static/music/点兔/Picture/tipi.png` → PASS(四边全 0);
`static/music/点兔/Picture/end/1.png` → **FAIL**(底部 alpha 均值 103.5、实色占比 46.93%,
正是"被切平"的样本). 判据能真正拦住这一类.

`--pad` 是**防贴边的第一道保险**: 抠图前加透明边距, 即使模型想贴边输出,
边缘也一定落在 alpha=0 的区域里.

## 怎么用

```python
from assfx.image import put_image, pop_image, side_slots, check_images
side_slots(f, t_cardkey, ["assets/tipi.png"], path_dir=PROJ, y=940, life=1.6)  # 左右各一张
pop_image(f, 3, t, 700, 940, "assets/eye.png", path_dir=PROJ)                  # 卡点弹一张
```

`a_peak` 在库里是 **alpha 值**(0=不透明, 255=全透明). 图片默认给 8.
(踩过: 传 255 得到一张全透明的图, 渲染出来空白.)

## 过关条件

- `hx-karaoke cutout.py --check-only` 全部 PASS.
- `render_octopus.py --probe` 报告 `\1img` 引用的图**全部存在**.
- 目检: 图**没有平铺重复**(平铺说明矩形尺寸 ≠ 图片尺寸).
- 全曲用图数量 ≤10 张、出现次数 ≤8 处(超了就退回 `45-bg` 用图形表达).

## 这一步要用的脚本

- `<skill>/scripts/cutout.py` - 抠图 + 四边/占比/羽化体检
- `<skill>/scripts/assfx/image.py` - `put_image` / `pop_image` / `side_slots` / `check_images`
- `<skill>/scripts/render_octopus.py` - 真渲染器(`--probe` 体检 + 出图目检)
