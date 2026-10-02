# Agent Note: 句内配色 —— 声部归属检测 + 段落色系

Status: implemented

- 影响: `.agents/skills/hx-anime-karaoke-ass/scripts/voices.py`(新增)、
  `scripts/assfx/color.py`(新增)、`steps/11-design/impl/color.md`(新增)

## Problem

用户: 「目前每 1 句话它的总体特效是统一的. 就比如说颜色可能前面的和后面的, 它可能需要颜色区分或者说唱的人不同.
你在同 1 句话里面, 你用的颜色基本上是一样的, 这是一个问题. 」

实测确认:

- `anim.py::Karaoke.colors(ch)` 只返回 `th["hi"], th["glow"]` —— **一句里所有字同色**,
  齐唱/和声/主唱全一个色.
- 库里其实**已经有**逐字改色的接口: `Karaoke(hl_color=lambda ch: (hi, glow))`,
  且 `dev/ヨスガノソラ/ピンキージョーンズ/make_ass.py:1101` 用过它(成员名彩蛋).
  缺的不是接口, 是**"这个字该是什么颜色"的判据**。
- 专业成品的实测做法(三份成品, 两条规律):

| 成品 | 做法 | 证据 |
|---|---|---|
| Charlotte OP | 描边**四色轮换, 每段一色**; 填充恒白 | `\3c` 只有 4 种, 全曲不变 |
| 东方「轨迹さえ」 | 全曲一套色域 | 6 种有色标签, 色相集中度 R=0.99 |
| 天使の3P「羽ばたきのバースデイ」 | **逐字分配, 同一色域内游走** | 28257 条字形事件 97% 带 `\t(...\1c...)` 终色, 61 种终色 |
| 点兔「ときめきポポロン♪」 | 角色色 + 主题色, 逐字取 | 11 色, 4 个样式前缀各一套 |

即 **"段落"是一层**(Charlotte 换段不换句), **"谁在唱"是另一层**(天使/点兔逐字分配).

## Decision

两件事, 各自都有可证伪的判据与反验样本:

1. **`scripts/voices.py`** —— 每个音拍判 `solo / octave / fifth / chorus / none`.
   自实现 YIN(不引入 scipy), 只回答"这一处是一条音高线还是多条", **不做说话人分离**.
   - 句级门槛是必需的: 单字判定会被伴奏的谐波骗过. 用句级基频置信中位 < `--min-base`
     (默认 0.55) 整句判 `none`.
   - 反验样本(同一套判据跑两条轨, 漆黑子弹 482 音拍):
     人声轨 `stems/vocals16k.wav` → `none` **67/482 = 14%**;
     伴奏轨 `stems/inst.wav` → `none` **447/482 = 93%**, 句级基线 0.05~0.44.
   - 稳健跨度用 p10~p90 而非 ptp: 音拍边界会混进邻音的 1~2 帧, ptp 把它们算成"跳了 8 个半音"
     而误判 none(实测改前 `none` 26%, 改后 14%, 伴奏轨仍 93% —— 反验判据没被削弱).
2. **`scripts/assfx/color.py`** —— `Scheme`(段落色域, 逐字在折线上游走) +
   `Palette`(段落列表 + `at(t)` 查询) + `make_hl_color(ph, palette, voices)`(造回调, 直接塞进 `Karaoke`).
   - `Scheme.roles = {"octave": 26, "fifth": 208}`: 声部色是**主色的色相旋转**, 同明度同饱和 ——
     不是另挑一个好看的颜色, 观感才是"同一套配色里的另一个位置".
   - `fold(ph, t_break, k0, k1)`: 句内折返点. 折返时刻挂在**语义反转词**上
     (与 `steps/11-design/impl/per-line.md` §3「把语法结构变成时间结构」同源),
     不是随机换色.
   - 填充恒白、色彩只走描边 —— 遵守 `doc/KFX-RULES.md`, 配色变多不许把对比度吃回去
     (`py/music/kfx_gate.py` 会量).

## Alternatives considered

- **什么都不做, 靠人眼看"这里该换色了"**: 最强理由是配色是审美. 否决:
  "同一句里颜色是否变过"、"变化是否挂在语义反转点上"都能机械查;
  而"这个色好不好看"本来就不在门禁范围(与 elements-table 的取舍一致).
- **上说话人分离模型(如 pyannote / 3D-Speaker)**: 最强理由是它能给出"是谁在唱", 信息最全.
  否决: 本任务只需要"一个音高线还是多条", YIN 就够(实测 4.1s 跑完 244s 曲子);
  引入模型会把 skill 的环境从"无额外依赖"变成要下权重、要 GPU,
  而收益只是把 `chorus` 细分到具体角色 —— 那需要的是官方角色歌信息, 不是更好的模型.
- **用 scipy 的 stft 复用 `check_sync.py` 的基频**: 最强理由是避免重写 YIN.
  否决: scipy 不在共享环境里(`hx-karaoke --check` 只装列出的依赖),
  加一个只为 4 秒计算的依赖不划算; 自实现 YIN 40 行, 且与 `check_sync.py` 的判据解耦.
- **逐字都换色(整句彩虹)**: 最强理由是"用户说颜色要区分". 否决(实测专业作品):
  天使の3P 的 61 色是**同一色域内的游走**(集中度 R=0.61), 不是随机彩虹;
  彩虹会把可读性吃掉, 也违反 `KFX-RULES.md` 的描边亮度上限.
- **把 `voices.py` 做成 make_ass 的自动依赖**: 否决: 它需要 `stems/vocals16k.wav`,
  而 04-vocals 是可以跳过的(纯器乐/找不到人声时). 做成**按需调用的独立脚本**,
  判不出来时配色退回单色, 不阻断主流程.

## Consequences

- 实机跑通: `hx-karaoke voices.py --vocals dev/漆黑子弹/トコハナ/stems/vocals16k.wav ...` →
  `{'solo': 202, 'none': 67, 'chorus': 123, 'fifth': 36, 'octave': 54}`, 4.1s,
  产物 `dev/漆黑子弹/トコハナ/review/voices.json`.
- `color.py` 只依赖 `assfx.core` 的 `col`, 不改 `anim.py`/`gen.py` 的任何签名 ——
  现有工程不受影响, 要用时传 `o={"hl_color": make_hl_color(...)}`.
- 已知边界: `chorus` 只说明"多于一条音高线", 不区分"两个人齐唱"与"一个人+混响";
  置信度低时一律 `none`. 判不出来的地方保持单色, 这比随机上色可靠.
