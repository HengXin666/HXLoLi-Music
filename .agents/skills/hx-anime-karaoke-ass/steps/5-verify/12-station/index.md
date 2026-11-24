# 12 验收台: 固定产物 + 按单元精确调整

> 2026-11-09 起, 旧预览台 (原 `scripts/station/`, 端口 5197) 已删除. 浏览器端只剩新台子 `scripts/studio/`, 命令行只剩 `scripts/accept/accept.py`. 两边共用的 ASS 读写与单元清单代码在 `scripts/assdoc/` (`assdoc.py` = ASS 最小读写, `spec.py` = 单元清单 / 参数层). 下文凡写 "台子" 都指 studio.

## 只做这一件事

把 `49-generate` 出的 `out.ass` 放进浏览器验收台, 走 "看, 挑, 改, 证" 的闭环: 用户看成品并标 (看), 对 "换一个构想" 在台上并排挑候选 (挑), agent 或台子按单元改生成器 (改), 每次改动由 G2 与隔离核对证明只动了该动的单元 (证). 每条标注都有可查的处理状态. 不靠整首重跑碰运气

## 为什么需要它

生成器的随机数按单元 key 取种子 (`assfx/base/seeding.py`, `gen.phrase_keys`). key 来自句子文字, 与句序无关. 所以 "只换一句的随机" 在库里本来就成立. 缺的是一个按单元看、按单元标、按单元改的入口: 页面负责看和标, `accept.py` 负责冻结与改代码核对

## 开台子

```bash
npm --prefix scripts/studio/web run build      # 前端构建 (改过 web/src 才需要; 依赖装在 web/node_modules, 不进 git)
python3 scripts/studio/server/app.py --project <工程目录> --port 5199   # http://127.0.0.1:5199/ (只绑本机; 远程用 ssh -L)
hx-karaoke accept/accept.py init <工程目录>     # v3 工程标志 = review/accept/state.json; 之后 out.ass 由 accept build 出 (冻结快照 + raw)
```

服务端是标准库 HTTP, 读工程的 `out.ass` / `out.manifest.json` (没有时读 accept 的 raw 清单) / `timing.json` / 参考 ASS (refpick: ref.json > playlist.json > 唯一同名; 没有也能开台), 改文件时经 `/api/watch` (WebSocket) 推给页面

## 页面 (plan 3.4-3.7)

| 区域 | 做什么 |
|---|---|
| 监视器 | 片源视频 + 定制 libass 画布. 片源按工程元数据: `mv.edl.json` > 工程 `studio.json` 的 `video` (相对工程目录) > `01-source` 契约的 `base.mp4`; 都没有就黑底. video_t = song_t + 偏移, 偏移取 `studio.json` 的 `video_offset` > `judge/shots.json` 的 `video_offset` > 0. 声音只来自工程音频 (`song.mp3` 或 refpick 选出的那份), 视频强制静音. 不再有某首歌专属的默认文件名 |
| 对比按钮 "对比: 成品 / 对比对象" | 成品 = 本工程 `out.ass`. 对比对象按顺序退化: 用户在 "闭环" 面板选的 (参考 / 上一版 / 候选 X) > 参考 ASS > 上一版 (`review/accept/prev.ass`, accept build 前留下) > 无. 没有参考 ASS 的新歌照样能对比上一版或候选. 门禁阈值只认参考 ASS 本身, 对比上一版 / 候选时门禁写 "未判定 · 无参考" |
| 顶栏 "闭环 · n 未结" | 打开 "看, 挑, 改, 证" 面板: 每条标注的类型、处理状态、最近一次改动 (诊断 / 改了什么 / G2); 换一个构想 / 不行 的标注有 "生成候选"; 候选有 "看" (监视器对比对象换成它并进 A/B) 与 "冻结"; 对比对象切换 (参考 / 上一版). 自审需人判 (selfreview --handoff) 的问题没有标注来源, 也列在这里 |
| 歌词面板 | 当前句放大居中 (停在 40% 高度, transform 平滑, 不用 scrollTop), 逐字按 timing 填色, 其它句降透明; 滚轮或拖动进浏览模式, 浮出 "回到当前句", 3s 无操作自动回跟随 |
| 选字 | 单击放光标并 seek, 拖选 (可跨句), Shift 扩展, Ctrl/Cmd 追加一段, 双击选词 (timing 的 unit), 三击或点行号选整句, 方向键 / Shift+方向键, Esc 清选区 |
| 右键菜单 (歌词 / 时间线片段 / 画面三处同一套) | 播放 / 循环 / 0.5x 循环, 说明这里 (E), 写批注 (N), 不行 > 症状标签 / 自定义, 好 (冻结) G, 换一个构想 R, 与参考对比 >, 只看 >, 在时间线中定位 F, 复制时间码, 复制所选事件, 导出当前帧 PNG |
| 检查器 ("说明这里") | 一句话说明 (几条事件, 按层语义名分布, 主要出自哪个 fx 函数 + 源码行, 这句在 arc 里的角色/手法/构想/why, 与参考的倍数) + 这里已有的标注 + arc / 事件归属 / 音乐事件 / 与参考同一句对比 / ASS 原文列表 |
| 时间线 | 全曲 / 刻度 / MV / 波形 / 节拍 / 字层组 (JP RB CN) / FX 组 0-8 / 卡片 / 标注 / 密度 (out 面积 + 参考虚线). 普通滚轮以指针为中心缩放, Shift+滚轮平移. 轨头 眼 / 独显 / 锁, 轨高可拖, 组可折叠 |

FX 轨按 assfx 的 "三明治" 层序命名 (FX 层号不受 `TEXT_LIFT` 影响; 字层按样式归轨, 工程自定义样式按 Name 前缀 `ly:/fx:/card:` 归轨). 字身层 = `TEXT_LIFT + 2`, 台子从清单 `meta.text_lift` 读 (老清单按 out.ass 里 ly: 事件的最小层号推), 不假设 0: 0 字后底光, 1 字底, 2 字身, 3 跳字, 4 辉光, 5 近字粒子, 6 迸散, 7 前景主体, 8 顶层闪光. 定义在 `scripts/studio/web/src/lib/tracks.ts` 的 `FX_ROLE`

## 标注记到哪里

页面不写盘. 所有写动作走 `POST /api/review`, 服务端追加到工程的 `review.jsonl`, 一行一条:

```json
{"id": "r...", "sel": [{"line": 27, "from": 3, "to": 4}], "t0": 176.939, "t1": 177.939, "kind": "bad", "tags": ["太吵"], "text": "", "frame": 176.94, "created": "...",
 "status": "open", "issue": "I3", "changes": [{"at": "...", "status": "proposed", "diag": "...", "what": "...", "candidates": ["A", "B"]}]}
```

处理状态 (`status`, 与 issues.json 同一套, 外加 `noted`): `open` 提出 / `fixing` 在改 / `proposed` 有改动或候选等用户看 / `done` 关闭 / `need-human` 要用户定 / `dropped` 作废 (选区落不到单元上) / `noted` 批注 (不需处理). 台子写入时就带 `status` (`open` 或 `noted`) 和空 `changes`; 之后只由 accept 回写 (`accept/reviewlog.py`): `intake` 把还没挂问题的标注收成 issues 并回写 `issue`, 之后每个改状态的命令 (`resolve` / `issue --of` / `cands` / `pick`) 都把 issue 的 `status` 与 `history` 回写成这条标注的 `status` 与 `changes` (含候选、选了哪个、G2 结果). 回写只改目标行, 其它行 (含坏行) 字节不变. 没有 `status` 的老记录读出时按 `open` / `noted` 显示并标 `status_src: default`, `accept.py sync` 写实

| kind | 页面 | 颜色 (时间线标注轨 / 歌词下划线 / 检查器一致) |
|---|---|---|
| `bad` | 不行 (可带症状标签或一句话) | 橙 |
| `good` | 好 (冻结) | 绿 |
| `redo` | 换一个构想 | 紫 |
| `note` | 写批注 | 蓝 |

agent 用 `accept.py intake` 把 `review.jsonl` 落到 v3 的 `issues.json` / `goods.json` (格式见 `impl/issues.md`), 不再手工读:

```bash
hx-karaoke accept/accept.py intake .                   # 标注 -> 问题 (bad/redo/good), 回写 status 与 issue
hx-karaoke accept/accept.py cands . I3 [--n 3]          # 换一个构想: 只重跑本单元出 2-3 个候选 (impl/cands.md)
hx-karaoke accept/accept.py pick . I3 --choice B        # 选中 -> picks.json -> 整首重跑 -> G2 + 隔离核对 -> 冻结
hx-karaoke accept/accept.py ideas .                    # 构想记录 (未选中的候选)
hx-karaoke accept/accept.py sync .                     # 按 issues 回写全部标注的状态
hx-karaoke accept/accept.py units .                    # 列单元, 句单元带字下标
hx-karaoke accept/accept.py issue . --unit K --action bad --tag 看不清 --chars 2-5
hx-karaoke accept/accept.py good . --unit K --chars 2-5      # 冻结 "好"
hx-karaoke accept/accept.py where . I3                 # 问题 -> 单元, 函数, 源文件, 剧本条目, 波及的 "好"
hx-karaoke accept/accept.py begin .                    # 改代码前存基准
hx-karaoke accept/accept.py predict . --scope K1,K2    # 重跑前预测影响集
hx-karaoke accept/accept.py verify . --scope K1,K2     # 重跑生成器 + 三条硬核对 (G2), 通过才构建
hx-karaoke accept/accept.py build .                    # out.ass = 冻结快照(raw)
```

## 候选闭环 (看, 挑, 改, 证)

台上一条龙, 每一步也都能在命令行做 (台子只是调 `accept.py`, 不在服务进程里改工程):

1. 看: 选字 / 选句, 右键 "换一个构想" (R) 或 "不行". 标注落 `review.jsonl`, `status=open`
2. 挑: 顶栏 "闭环" 面板里点这条的 "生成候选". 服务端 (`studio/server/loop.py`, 后台单飞, 与位置预设共用生成器锁) 依次 `accept init/build` (工程还没进 v3 时) -> `intake` -> `cands`. 候选只重跑本单元 (`ASSFX_ONLY`), 2-3 个, 提案顺序与去重见 `impl/cands.md`. 状态 -> `proposed`
3. 点 "看 A" / "看 B": 监视器的对比对象换成该候选 (整首预览 = 当前 out.ass 换掉本单元), 进 A/B, 角标写明 "候选 A (I3)"; 空格切换 成品 / 候选
4. 改 + 证: 点 "冻结 B" -> `accept pick`: 存基准 -> 选中参数写进 `review/accept/picks.json` (accept 重跑生成器时经 `ASSFX_OVERRIDES` 喂回, 选中者是生成器真输出) -> 整首重跑 -> G2 三条 (A 碰到 "好" / B 越出本单元 / C 追踪漏依赖) + 隔离核对 (整首重跑里本单元 == 候选快照, 逐行) -> 都过才冻结为 "好" 并构建. 任何一条不过: raw 与 picks 恢复为基准, 状态 `need-human`, 原因写进 changes
5. 未选的候选进构想记录 `review/accept/ideas.jsonl` (+ `ideas/<I>-<X>.unit.ass`), 下次 "换一个构想" 不再提同样的参数. 标注状态 `done`, changes 写明选了哪个与 G2 结果. 对比对象回到自动 (无参考 = 上一版)

判据: `python3 scripts/studio/server/e2e_loop.py --project <工程>` 全部通过 (在临时副本上跑, 原工程一个字节不动).

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
- `python3 scripts/studio/server/e2e_ui.py` 的测试句按工程数据挑 (第一句 >= 10 字且有振假名的句), 期望值 (行号 / 振假名 / 角色 / fx 函数 / 层号 / 卡片) 都从工程数据取, 不写死某首歌; 没有剧本 (`judge/arc.json`) 的工程不出角色徽标, 没有片源的工程监视器无 video
- `python3 scripts/studio/server/e2e_loop.py --project <工程>`: 候选闭环全程在台上通过 (见上节)
- `python3 scripts/studio/server/check_viewports.py --project <工程>`: 9 个视口组合无滚动条、无溢出、画布像素 = 显示尺寸 x DPR
- `hx-karaoke accept/selftest_accept.py` 与 `hx-karaoke selfreview/selftest_selfreview.py` 全部 PASS
- `accept.py goods .` 里没有 stale 的 "好", `accept.py issues . --open` 里没有未处理的问题

## 产物与过关条件

`out.raw.ass` + `out.raw.manifest.json` + `review.jsonl` (每条带 status) + `review/accept/` (issues / goods / picks.json / cands / ideas.jsonl / prev.ass) (+ 用过参数层时的 `review/station/overrides.json`) + 由它们构建出的 `out.ass` 与 `out.manifest.json`. 全部在工程目录, 不进 skill (见 `shared/hard-rules.md` 第 11 条). 然后进入 `13-validate`

## 字体与豆腐块

- 台子把字体目录里的全部字体交给 libass: 工程目录的 `fonts/` 优先, 没有时用 skill 的 `fonts/` (`server/app.py` 的 `fonts_dir`). 按字体内部的 family 名匹配 ASS 样式
- 没有 CJK 回退链: ASS 指定的字体不在目录里, 或字体缺字, 画面就出豆腐块. 要看到 ASS 指定的字形, 把那个字体放进 `fonts/`
