# 12 验收台: 固定产物 + 按单元精确调整

> 2026-11-09 起, 旧预览台 (原 `scripts/station/`, 端口 5197) 已删除. 浏览器端只剩新台子 `scripts/studio/`, 命令行只剩 `scripts/accept/accept.py`. 两边共用的 ASS 读写与单元清单代码在 `scripts/assdoc/` (`assdoc.py` = ASS 最小读写, `spec.py` = 单元清单 / 参数层). 下文凡写 "台子" 都指 studio.

## 只做这一件事

把 `49-generate` 出的 `out.ass` 放进浏览器验收台. 用户只看成品, 指出哪里不行、哪里好; agent 按单元去改生成器, 满意的单元冻结. 不靠整首重跑碰运气

## 为什么需要它

生成器的随机数按单元 key 取种子 (`assfx/base/seeding.py`, `gen.phrase_keys`). key 来自句子文字, 与句序无关. 所以 "只换一句的随机" 在库里本来就成立. 缺的是一个按单元看、按单元标、按单元改的入口: 页面负责看和标, `accept.py` 负责冻结与改代码核对

## 开台子

```bash
npm --prefix scripts/studio/web run build      # 前端构建 (改过 web/src 才需要; 依赖装在 web/node_modules, 不进 git)
python3 scripts/studio/server/app.py --project <工程目录> --port 5199   # http://127.0.0.1:5199/ (只绑本机; 远程用 ssh -L)
hx-karaoke accept/accept.py init <工程目录>     # v3 工程标志 = review/accept/state.json; 之后 out.ass 由 accept build 出 (冻结快照 + raw)
```

服务端是标准库 HTTP, 读工程的 `out.ass` / `out.raw.manifest.json` / `timing.json` / 参考 ASS (`static/music/<番>/<歌> .ass`), 改文件时经 `/api/watch` (WebSocket) 推给页面

## 页面 (plan 3.4-3.7)

| 区域 | 做什么 |
|---|---|
| 监视器 | 片源视频 (EDL, 默认 `source/ed1_creditless.mp4`, video_t = song_t + 0.73) + 定制 libass 画布. 声音只来自 `song.mp3`, 视频强制静音 |
| 对比按钮 "对比: 成品 / 参考" | 成品 = 本工程 `out.ass`, 参考 = 参考 ASS. 点开后 成品 / 参考 两段切换, x 关闭; 划变 / 左右并排在右键菜单 |
| 歌词面板 | 当前句放大居中 (停在 40% 高度, transform 平滑, 不用 scrollTop), 逐字按 timing 填色, 其它句降透明; 滚轮或拖动进浏览模式, 浮出 "回到当前句", 3s 无操作自动回跟随 |
| 选字 | 单击放光标并 seek, 拖选 (可跨句), Shift 扩展, Ctrl/Cmd 追加一段, 双击选词 (timing 的 unit), 三击或点行号选整句, 方向键 / Shift+方向键, Esc 清选区 |
| 右键菜单 (歌词 / 时间线片段 / 画面三处同一套) | 播放 / 循环 / 0.5x 循环, 说明这里 (E), 写批注 (N), 不行 > 症状标签 / 自定义, 好 (冻结) G, 换一个构想 R, 与参考对比 >, 只看 >, 在时间线中定位 F, 复制时间码, 复制所选事件, 导出当前帧 PNG |
| 检查器 ("说明这里") | 一句话说明 (几条事件, 按层语义名分布, 主要出自哪个 fx 函数 + 源码行, 这句在 arc 里的角色/手法/构想/why, 与参考的倍数) + 这里已有的标注 + arc / 事件归属 / 音乐事件 / 与参考同一句对比 / ASS 原文列表 |
| 时间线 | 全曲 / 刻度 / MV / 波形 / 节拍 / 字层组 (JP RB CN) / FX 组 0-8 / 卡片 / 标注 / 密度 (out 面积 + 参考虚线). 普通滚轮以指针为中心缩放, Shift+滚轮平移. 轨头 眼 / 独显 / 锁, 轨高可拖, 组可折叠 |

FX 轨按 assfx 的 "三明治" 层序命名 (`base/core.py` 的 `TEXT_LIFT=0` 时): 0 字后底光, 1 字底, 2 字身, 3 跳字, 4 辉光, 5 近字粒子, 6 迸散, 7 前景主体, 8 顶层闪光. 定义在 `scripts/studio/web/src/lib/tracks.ts` 的 `FX_ROLE`

## 标注记到哪里

页面不写盘. 所有写动作走 `POST /api/review`, 服务端追加到工程的 `review.jsonl`, 一行一条:

```json
{"id": "r...", "sel": [{"line": 27, "from": 3, "to": 4}], "t0": 176.939, "t1": 177.939, "kind": "bad", "tags": ["太吵"], "text": "", "frame": 176.94, "created": "..."}
```

| kind | 页面 | 颜色 (时间线标注轨 / 歌词下划线 / 检查器一致) |
|---|---|---|
| `bad` | 不行 (可带症状标签或一句话) | 橙 |
| `good` | 好 (冻结) | 绿 |
| `redo` | 换一个构想 | 紫 |
| `note` | 写批注 | 蓝 |

agent 读 `review.jsonl` 后用 `accept.py` 落到 v3 的 `issues.json` / `goods.json` (格式见 `impl/issues.md`):

```bash
hx-karaoke accept/accept.py units .                    # 列单元, 句单元带字下标
hx-karaoke accept/accept.py issue . --unit K --action bad --tag 看不清 --chars 2-5
hx-karaoke accept/accept.py good . --unit K --chars 2-5      # 冻结 "好"
hx-karaoke accept/accept.py where . I3                 # 问题 -> 单元, 函数, 源文件, 剧本条目, 波及的 "好"
hx-karaoke accept/accept.py begin .                    # 改代码前存基准
hx-karaoke accept/accept.py predict . --scope K1,K2    # 重跑前预测影响集
hx-karaoke accept/accept.py verify . --scope K1,K2     # 重跑生成器 + 三条硬核对 (G2), 通过才构建
hx-karaoke accept/accept.py build .                    # out.ass = 冻结快照(raw)
```

## 参数层 (v2) 的现状

v2 的页面属性面板、抽签、输出层补丁、`set/pin/cands/pick/patch/report` 命令行都随旧预览台删除了. 保留的部分:

- 生成器侧的清单与覆盖接口不变: `Generator.render()` 写 `out.raw.manifest.json`, 生成器经 `ASSFX_OVERRIDES` 读 `review/station/overrides.json` (`assfx/layer/overrides.py`). 字段与开放范围见 `impl/manifest.md`, 预设词汇见 `impl/presets.md`
- 读写清单与覆盖的代码在 `scripts/assdoc/spec.py` (`load_manifest`, `manifest_path`, 覆盖的 set / reset / pin / 状态与过期判断), `accept/` 与 `selfreview/` 都从这里 import
- 隔离规则 (G2) 由 `accept.py verify` 承担: 改单元 X, X 之外逐字节不变; window 组参数 (`din dout lead hold`) 只许多牵动清单 `deps.window` 列出的下一句

时间问题按来源分流, 与以前相同:
- 字的音拍错: 回 `08-review-timing` 改 `fixes.json`. 不在这里平移字层
- 出入场窗口不对: 改 `lead / hold / din / dout`
- 生成器表达不了的局部: 改生成器 (工程目录下的 `fx_*.py`), 不直接改 `out.ass`

## 判据

- `python3 scripts/studio/server/e2e_ui.py --project <工程>` 全部通过. 真 chromium + playwright, 操作一律走真实鼠标键盘, `window.__hx` 只读状态; 批注写临时文件, 跑完核对工程 `review.jsonl` 未被改动. 覆盖 3.5 歌词面板 / 3.6 右键菜单 / 3.7 时间线轨的每一行, 以及对比按钮、滚轮缩放、FX 轨名、标注轨、检查器、视频静音
- `python3 scripts/studio/server/check_viewports.py --project <工程>`: 9 个视口组合无滚动条、无溢出、画布像素 = 显示尺寸 x DPR
- `hx-karaoke accept/selftest_accept.py` 与 `hx-karaoke selfreview/selftest_selfreview.py` 全部 PASS
- `accept.py goods .` 里没有 stale 的 "好", `accept.py issues . --open` 里没有未处理的问题

## 产物与过关条件

`out.raw.ass` + `out.raw.manifest.json` + `review.jsonl` + `review/accept/` (+ 用过参数层时的 `review/station/overrides.json`) + 由它们构建出的 `out.ass`. 全部在工程目录, 不进 skill (见 `shared/hard-rules.md` 第 11 条). 然后进入 `13-validate`

## 字体与豆腐块

- 台子把字体目录里的全部字体交给 libass: 工程目录的 `fonts/` 优先, 没有时用 skill 的 `fonts/` (`server/app.py` 的 `fonts_dir`). 按字体内部的 family 名匹配 ASS 样式
- 没有 CJK 回退链: ASS 指定的字体不在目录里, 或字体缺字, 画面就出豆腐块. 要看到 ASS 指定的字形, 把那个字体放进 `fonts/`
