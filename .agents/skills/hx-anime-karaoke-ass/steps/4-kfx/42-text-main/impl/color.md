# 句内配色: 段落色系 · 声部 · 折返点

## 症状

用户 2026-10-03: 「目前每 1 句话它的总体特效是统一的. 就比如说颜色可能前面的和后面的, 它可能需要颜色区分或者说唱的人不同. 你在同 1 句话里面, 你用的颜色基本上是一样的, 这是一个问题. 」

机制上是必然的: `anim.py::Karaoke.colors()` 只返回 `th["hi"], th["glow"]`  一句里所有字、所有声部同色. 接口其实是有的(`Karaoke(hl_color=lambda ch: (hi, glow))`, 某工程用过它做角色名彩蛋), **缺的是"这个字该是什么颜色"的判据**

## 专业成品的实测做法(三份, 两类)

| 成品 | 做法 | 实测 |
|---|---|---|
| 成品 A (OP) | 描边**四色, 每段一色**; 填充恒白 | `\3c` 只有 4 种, 全曲不变 |
| 成品 B | 全曲一套色域 | 6 种有色标签, 色相集中度 **R=0.99** |
| 成品 C | **逐字分配, 在同一色域里游走** | 28257 条字形事件 **97%** 带 `\t(...\1c...)` 终色, **61 种**终色 |
| 成品 D | 4 个角色色 + 主题色逐字取 | 11 种颜色, 4 个样式前缀各挂一套 |

**两条从专业成品里量出来的规律**:
1. **"段落"是一层**  成品 A 换的是段, 不是句. 逐句换色会丢掉全曲统一性
2. **"谁在唱"是另一层**  成品 C 的 61 色是**同一色域内的游走**(集中度 R=0.61), 不是彩虹. 逐字乱换会把可读性吃掉, 也撞 `doc/KFX-RULES.md` 的描边亮度上限

## 三件要做的事

### 1. 段落色系(`assfx/text/color.py::Scheme` / `Palette`)

段边界**不许凭"听着像副歌"**: 与 `impl/density.md` §1b 同源, 用 chordwiki 的转调点

```python
from assfx.text.color import Palette, Scheme
PAL = Palette([
    ( 56.7, 135.0, Scheme("主歌A", ["#16243C", "#4A3F30"], level=1)),          # C#m 系, 最暗
    (135.0, 213.5, Scheme("副歌1", ["#C02840", "#E0642A"], level=2)),          # D 系, 第一级台阶
    (213.5, 245.0, Scheme("副歌2", ["#E8B34A", "#FFFFFF"], level=3)),          # E♭ 系, 全曲最高
], default=Scheme("main", ["#DCE8F4", "#FFFFFF"]))
```

一句之内的颜色**不是随机换**, 而是**在这段色域的折线上按字游走**(`Scheme.at(k)`). 这就是"前面和后面颜色不同"与"全曲统一"同时成立的形式

### 2. 声部配色(`scripts/kfx/voices.py` → `Scheme.roles`)

先测, 不猜

```bash
hx-karaoke voices.py --vocals proj/stems/vocals16k.wav --timing proj/timing.json \
    --lyrics proj/lyrics.txt --out proj/review/voices.json
```

判据是**基频直方图的峰距**(八度 ≈ 11~13 半音 / 五度 ≈ 5.5~8.5 半音 / 三峰以上 = 齐唱), 不需要说话人分离模型. 反验必须做: 换 `stems/inst.wav` 跑一遍, `none` 占比应显著上升(实测人声 `none` 14% vs 伴奏 `none` **93%**)

```python
SC.roles = {"octave": 26, "fifth": 208, "chorus": -34}   # 声部 → 色相旋转角度
```

色相旋转而不是另挑颜色: 派生色与主色**同明度同饱和**, 观感是"同一套配色里的另一个位置"

### 3. 句内折返点(`color.fold()`)

挂在**语义反转词**上(与 `impl/per-line.md` §3 同源: 把句子的语法结构变成动画的时间结构)

```python
from assfx.text.color import find_break, fold
t_break, word = find_break(ph, ["ない", "でも", "けど"])     # 否定/转折
ramps = fold(ph, t_break, k_before=0.15, k_after=0.85)        # 折返点两侧用色域的两端
```

判据: **把那段颜色单独拿出来, 不看歌词, 能看出"这里意思反了"吗?** 看不出就说明折返点选错了

## 接进生成器

```python
from assfx.text.color import Palette, Scheme, make_hl_color
hl = make_hl_color(ph, PAL, voices=VJ["tags"])                 # voices=None 则只按段落色域游走
P["o"] = dict(P.get("o", {}), hl_color=hl)
```

`make_hl_color` 关掉 `use_voice` / `use_ramp` 就退回"一句一色"  对比实验用得上(见 `doc/KFX-SEMANTIC-MODEL.md` §三「意象层去掉会退化成任何歌都能套」的同类验证)

## 不许越过的红线

- 填充恒为纯白, 色彩表达只走描边(`doc/KFX-RULES.md`): 配色变多不许把对比度吃回去
- 描边亮度上限 ≤0.1833(对白填充 ≥4.5:1). 逐字游走时**每次派生后都要复量**, 亮端色(`#FFFFFF`)不能直接当描边色  它会连描边一起吃掉
- 单色族 = 无色彩叙事; 彩虹 = 可读性灾难. 专业成品的区间是 **1~4 个色相族** (专业成品实测 3~4 族; 只做段间换档而族内无变化时, 缺的是族内游走)
