# 清单契约: 生成器怎么接入参数层

预览台不从事件 Name 猜单元. 生成器在写 ASS 时同目录写 `<out>.manifest.json`, 说清有哪些单元, 每个单元能调什么. 思路照 video-shotcraft 的 `workbench.ts`: 一份事实源, 按 schema 编辑, 节奏命门不开放

## 接入要做的几件事

用 `Generator` 的工程 (模板与示例都是) 只需三处:

1. 有名字的色组: `register_theme("SUN", TH(...), why="夕阳, 暖色室内")`. 改色只能在有名字的色组之间切, 交付说明才写得出 "由 SKY 改为 SUN"
2. 配方标注: `@recipe(why="...", knobs=[knob("drops", 2, 0, 6, 1, "每字光线数")])`. 配方里用 `f.opt("drops", 2)` 读. 没标注的 `fx_*` 也会登记, 只是没有专属旋钮
3. 段单元: 卡点/背景/图片按段调用 `p = G.segment("beat", t0, t1, BAND_ALL, level=lv, family=fam)`. 用 `seed_parts(..., salt=p["salt"])` 取种子, `f.set_knobs(p["knobs"])`
4. (可选) `G.inputs(HERE, "timing.json", ...)`: 登记上游输入. 它们变了, 锁住的单元标过期

自写卡片函数的工程 (如示例) 用 `G.card_unit(name, t0, t1, band)` 拿 salt 与旋钮

没有任何覆盖时, 输出与接入前逐字节相同. 本 skill 的示例与 dev 下 7 个工程都实测过

## 单元

| kind | key | 认领的事件 |
|---|---|---|
| phrase | 句子文字哈希 + 出现次序 (`phrase_keys`) | `ly:<name>` `fx:<name>` |
| card | `card:<卡名>` | `card:<name>` `fx:<name>` |
| beat / bg / img | `<kind>@<段起点ms>` | `fx:<kind>`, 起点落在段内的 |

每个单元记: `params` (有效值), `defaults` (没有覆盖时的值), `fp` (本句音拍与布局指纹), `deps.window` (改出入场会牵动谁), `applied` (规划后的实际 in/out/din/dout), `clamp`

## 开放的参数及其意义

| 组 | 参数 | 意义 |
|---|---|---|
| 设计 | `theme` `th.hi` `th.glow` `th.dark` | 本句色族与三色. 走色彩系统 (47-color) |
| 设计 | `motion` `ent` `ext` `hl` | 入退场与高亮手法. 预设带 why |
| 设计 | `fx` | 换本句特效配方 |
| 出入场窗口 | `din` `dout` `lead` `hold` | 进太急, 挂太久. 会牵动下一句入场 |
| 旋钮 | `density` `size` `alpha` | 太满 / 太空 / 太亮. 在 FX 发射器内统一生效, 仍受 band 夹取. 只开放配方真正用到的, 见下 |
| 旋钮 | 配方专属 | 配方 `knobs` 声明的内容量 |
| 随机 | `salt` | 只重抽本单元 |
| 段 | `level` `family` `enabled` | 卡点密度等级, 色族, 关掉本段 |

统一旋钮不是每个配方都有效. `density` 只作用于 `f.burst` / `f.drift` (发射粒子). `size` 与 `alpha` 只作用于 `f.shape` (画图形).
- FX 运行时记下用到的旋钮. 清单按单元写成 `knobs_used`.
- 预览台面板只显示 `knobs_used` 里的统一旋钮. 已有覆盖的旋钮仍显示, 用来点"默认"清掉.
- 服务端拒收对没用到的旋钮的改动. 理由: 拖一个没反应的滑块比没有这个滑块更糟.
- 清单没有 `knobs_used` (老版 assfx) 时, 全部显示, 不拒收.
- 段与卡片要用 `G.segment()` / `G.card_unit()` 返回的 `knobs` 建 FX. 这样用到的旋钮才记回本单元.

## 不开放的参数

| 参数 | 理由 |
|---|---|
| 逐字错落曲线 `stg_in/stg_out`, `\t` 加速度, pop 比例 | 节奏命门. 调坏品相的概率远高于调好 |
| 退场向量的随机区间 | 由 `salt` 换签, 不开放区间本身 |
| 位置, band 尺寸 | 铁律 6b 字幕只有一个位置; 铁律 5 band 由版面算出 |
| 字的音拍时间 | 属于 `08-review-timing` 的 `fixes.json`, 在源头改 |
| 卡片文案 / 位置 | 改字回生成器; 位置同上 |

## 覆盖文件

`review/station/overrides.json`:

```json
{"format": "assfx-overrides", "version": 1,
 "units": {"ac3478d69a#0": {"params": {"motion": "破碎", "density": 0.7},
                             "notes": {"motion": "这句是战斗画面", "density": "粒子抢字"},
                             "pin": null}}}
```

生成器只读 `params`. 非法值 (未知参数, 越界, 不在选项里, 预设不存在) 直接报错退出, 不静默忽略
