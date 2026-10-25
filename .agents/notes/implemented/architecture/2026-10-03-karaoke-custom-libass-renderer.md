# Agent Note: 本机有两个 libass, 能力不同  目检必须用定制版

Status: implemented

Decision-ID: karaoke-custom-libass-renderer


## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/render/render_octopus.py`

## Problem

用户 2026-10-03 要求加一层"图片层": 「我们这个特效字幕是改版过的, 因此它应该是可以嵌入图片的」.

第一轮验证时我用系统 `ffmpeg` 的 `subtitles=` 滤镜渲染一份写了 `\1img(tipi.png)\p1` 的 ass,
得到**纯色白块**; `strings /usr/lib/libass.so.9 | grep 1img` 为 **0 个匹配**.
据此我差点得出"图片层在本机做不了"的结论  **这是错的**, 而且错得很隐蔽:
`\1img` 不被识别时 libass **不报错**, 只是把它当普通填充色渲染.

真正的原因: 本仓库的字幕由 **HXLoLi 定制版 libass**(SubtitlesOctopus WASM)渲染.
仓库 `README.md` 第 8 行就写着"原生支持 VSFilterMod 扩展标签(`\1img` 图片纹理…)".
`py/music/scanner.py:119` 与 `py/music/ass_parser.py` 整条链都在处理 `\1img` 
点兔的 `assImageData`(9 张图)**已经生成好了**.

实测两个渲染器的能力差:

| 渲染器 | VSFilterMod 标签 |
|---|---|
| `/usr/lib/libass.so.9`(ffmpeg 用它) | **0 个** |
| `HX-LoLis/HXLoLi/static/music/ass-worker/libass/libass.wasm` | `1img` `2img` `3img` `4img` `distort` `fsvp` `fsc` `pbo` `rnd` `frs` |

## Decision

新增 `scripts/render/render_octopus.py`: 用 Playwright + 定制版 wasm 出图, 并自动把 `\1img` 引用的图
与字体写进 worker 虚拟 FS. **抽帧目检与图片层验证一律走它**; 带视频底/带 band 框的辅助截图
(`snapshots.py`) 只能用来判排版与 band 贴合, **不能用来判 MOD 标签**.

落地时踩到并修掉的四个坑(都记在脚本注释里):

1. **canvas 必须显式设 `width/height`**  不设就是 HTML 默认的 300×150, 出图被裁.
2. **配置走文件, 不走 argv**  字体 + 图片的 base64 有几百 KB,
   实测报 `OSError: [Errno 7] Argument list too long: 'node'`.
3. **帧直接写盘, 不经过 stdout**  一次 1920×1080 PNG 的 base64 约 1MB, 多帧撑爆管道.
4. **canvas 是透明的, 必须自己合成到黑底再量**  否则读图工具把透明区渲染成白色,
   得到"整帧发白但非黑像素只有 14%"这种自相矛盾的数.

第 4 条尤其容易骗过自己: 第一版量出"非黑像素 291565"看着像有内容, 实际那是 alpha 通道的
非零计数, 与画面亮度无关.

## Alternatives considered

- **什么都不做, 目检继续用 snapshots.py(ffmpeg)**: 最强理由是"它一直能用, 且带视频底更好看".
  否决(实测): 它对 MOD 标签**静默退化**。图片层是这一轮明确要加的东西,
  用它做目检等于闭着眼睛验  画面上什么都没有, 报告里却是"渲染成功".
- **让 ffmpeg 链接定制版 wasm**: 技术上不成立  wasm 是 Emscripten 产物, 不是 shared library,
  ffmpeg 的 `subtitles=` 滤镜无法加载它.
- **改用 Aegisub 的 render 接口出图**: 否决(实测): `~/.local/opt/aegisub/usr/lib/libass.so.9.4.2`
  同样 `strings | grep 1img` 为 0, 也不支持.
- **在 Python 里直接调 wasm(wasmtime/wasmer)**: 最强理由是省掉浏览器。
  否决: SubtitlesOctopus 的 wasm 是给 worker + Canvas 用的, 需要 `OffscreenCanvas`/`ImageData`
  等 Web API; 在 Python 里重搭这套桥的成本远高于用 Playwright。
  本机已有 playwright + chromium(实测 `~/.cache/ms-playwright/chromium-1243`).
- **把"用哪个渲染器"写成文档约定, 不加脚本**: 否决。这正是本项目反复踩的坑 
  约定停留在描述层面就没人执行(与 `2026-09-28-kfx-quality-redline.md` 的结论一致).

## 重做对照中又发现三处(2026-10-03 当天, 用 v4/v5 对照暴露)

**1. 字体名必须用字体文件里的真实族名, 不是文件名.**
`dev/漆黑子弹/トコハナ/make_ass.py` 里写的是 `LXGW WenKai Medium`,
而 `LXGWWenKai-Medium.ttf` 的实际族名是 **`霞鹜文楷 Medium`**.
定制版 libass 找不到就回落, 症状是**满屏豆腐块**;
而系统 ffmpeg 有自己的字体回退, **把这个缺陷完全掩盖了**  它一直存在却没被发现.
这是"必须用真渲染器目检"的第二个理由(第一个是 MOD 标签静默退化).
`render_octopus.py --probe` 现在会打印 `img` 引用与全部样式字体, 先跑它.

**2. 写进 Worker FS 之后必须 `setTrack` 重载.**
只 `writeFile` 不重载时, libass 仍在用 fallback 字体(图片同理不生效 
这与 `img` 的 `can't fopen` 是同一处机制). 主站的做法就是
**写 FS → `setTrack(subContent)` 热重载**(见 `AssLyrics.tsx`). 已照做.

**3. 取帧不能按秒逐帧推进.**
第一版让渲染器从 0 按 1/8 秒推到 194s 才截图(1556 次渲染), 之后所有文字变成豆腐块 
看起来像字体缺失, 实际是 libass 的**字形缓存被挤掉**.
按日志区分: 真缺字形有 `libass: Glyph 0x... not found in font for (...)`, 缓存淘汰**没有这条日志**.
现在只走两跳(目标前 0.05s → 目标), 足以让 `\t` 取到正确插值.

## Consequences

- 新增 `scripts/render/render_octopus.py`; 用法 `hx-karaoke render_octopus.py <ass> --probe` /
  `--times t1,t2 --out dir/`.
- 实跑验证: 冒烟 ass(1920×1080 + `\1img`) → 45510 亮像素, 提比兔子纹理正常渲染;
  9 张平铺的成因也由此被量出来(矩形 300×240 vs 图 105×84).
- 依赖: playwright(本机 `/data/nvme0_p4/img-to-react/web`)、chromium、node.
  三者都用环境变量可覆盖(`ASSFX_OCTOPUS_DIR` / `ASSFX_PLAYWRIGHT` / `ASSFX_CHROME`),
  找不到时报错点名, 不静默降级。
- `steps/5-verify/14-inspect` 的目检清单新增四条: 卡点层与字音拍不重合 / 卡点不排成一条横线 /
  图片无平铺重复 / 图片边缘未被切平。
- 实跑对照(`dev/漆黑子弹/トコハナ/review/v4-vs-v5.md`): 同一份 ass 用定制版渲染,
  图片层从 0 到 4 条, 左右各一张延珠, 发丝完整。
