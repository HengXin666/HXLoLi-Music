# 精细图形: 从网络矢量图转 ASS 绘图代码

## 为什么必须这么做

用 `shapes.py` 里的 `circle` / `rect` / `arc` 拼一个"自行车", 出来的只是几个圆圈加几条线. 用户原话: **"你画的图都太不精细了, 你必须要在网上去找图片, 然后把它变为 SVG 或者直接内封渲染. "**

实测差距(同一物体)

| 物体 | 手绘拼贴 | 网络 SVG 转出 |
|---|---|---|
| 自行车 | 两个圆圈 + 几条线 | **3148 字符**真实车架/辐条/齿轮路径 |
| 水 | 几条波浪线 | **4156 字符**真实水波 |
| 花 | `flower(s,n)` 简单多边形 | **6881 字符**层叠花瓣 |

## 工具: `scripts/assfx/base/svg2ass.py`

```python
from assfx.base.svg2ass import from_url, from_file

# 取网络图标并转成 ASS 绘图代码（带缓存，可离线复现）
d = from_url("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/icons/bicycle.svg", size=64)
f.shape(5, t0, t1, x, y, draw=d, c1="#FFFFFF", c3="#2030A0", bord=1.2)
```

输出是以**视觉中心为原点**的 `m/l` 序列, 可直接当 ASS 的 `\pos` 用

### 已知可用的图形源(实测 200 OK)

    https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/icons/<name>.svg

验证过的名字: bicycle / window / water / flower1 / heart-fill / moon-stars / music-note-beamed / cloud-rain / tree / bird / umbrella / hourglass / stars / wind / droplet / sun / moon / snow / rainbow / camera / book

图形名可在 `https://icons.getbootstrap.com/` 检索

## 两条踩过的坑(不要重犯)

### 坑一: 不要手写 SVG 解析器

先手写了一个支持 M/L/H/V/C/S/Q/T/A/Z 的解析器, 实测渲染时 bicycle / window / moon-stars 出现**实心团块**(环的孔被填死)、tree / music-note 形状错乱  相对指令与圆弧的方向处理有隐 bug, 改了两轮仍不对. **改用 `svgelements`(纯 python, 一个包)后一次通过. **

安装(skill 的 venv 里)

```bash
uv pip install --python <venv>/bin/python svgelements
```

### 坑二: npoint 返回 numpy 数组, 不是 Point

    seg.npoint(ts)        # -> ndarray[[x, y], ...]   必须按下标取
    seg.point(t)          # -> Point                  可以用 .x / .y

写成 `q.x` 会得到 `AttributeError: 'numpy.ndarray' object has no attribute 'x'`

## 做法: 把曲线采样成折线

ASS 的 `\p1` 只认 `m` / `l` / `b`. 用折线近似曲线最简单, 且**不可能出方向错**  每条子路径的点序原样保留, ASS 的 nonzero 填充会自动把孔挖出来

采样密度用 `flatten` 控制(默认 0.6 个单位一段), 输出长度用 `min_step` 合并(默认 0.35px). **注意 ASS 事件太长会影响播放器加载**, 一个图形控制在 3~7KB 为宜

## 缓存: **不在 skill 目录里**

`svg2ass.fetch()` 下载的 SVG 原件缓存到 `ASSFX_SVG_CACHE`, 未设时用`~/.cache/hx-anime-karaoke-ass/svg`(键 = url 的 sha1 前 16 位). 同名不重复下载, 可离线复现

**不许把缓存放回 skill 里**: 缓存是某一次运行的产物, 写进 skill 就等于把"某个工程的素材"
永久混进 skill 本体  换首歌时旧图形还在, 删都分不清哪些该留. skill 只放代码与契约, 不带任何一次运行的痕迹. 要换图形直接删缓存里对应文件即可

同理, **烧好的图形(`bake_shapes.py` 的产物 `shapes.json`)属于工程**, 用 `--out proj/assets/shapes.json` 写进工程目录; 脚本会拒绝把 `--out` 指向 skill 内部
