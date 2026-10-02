# 47 色彩系统

## 只做这一件事

定下**全曲的配色结构**: 段落色系 → 句内折返 → 声部色 → (可选)背景跟随.

## 专业成品是怎么做的(实测三份, 两类)

| 成品 | 做法 | 实测 |
|---|---|---|
| Charlotte OP | 描边**四色, 每段一色**; 填充恒白 | `\3c` 只有 4 种, 全曲不变 |
| 东方「轨迹さえ」 | 全曲一套色域 | 6 种有色标签, 色相集中度 **R=0.99** |
| 天使の3P「羽ばたきのバースデイ」 | **逐字分配, 同一色域内游走** | 28257 条字形事件 **97%** 带 `\t(...\1c...)` 终色, **61 种**终色 |
| 点兔「ときめきポポロン♪」 | 角色色 + 主题色逐字取 | 11 色, 4 个样式前缀各一套 |

**两条被钉死的规律**:
1. **"段落"是一层** —— Charlotte 换的是段, 不是句. 逐句换色会丢掉全曲统一性.
2. **"谁在唱"是另一层** —— 天使の3P 的 61 色是**同一色域内的游走**(集中度 R=0.61), 不是彩虹.

## 四件事

### 1. 段落色系

段边界**不许凭"听着像副歌"**: 与 `impl/density.md` §1b 同源, 用 chordwiki 的转调点.

```python
from assfx.color import Palette, Scheme
PAL = Palette([
    ( 56.7, 135.0, Scheme("主歌A", ["#16243C", "#8A98A8"], level=1)),
    (135.0, 213.5, Scheme("副歌1", ["#C02840", "#E0642A"], level=2)),
    (213.5, 245.0, Scheme("副歌2", ["#E8B34A", "#EEF4FA"], level=3)),
])
```

句内颜色**不是随机换**, 而是在这段色域的折线上**按字游走**(`Scheme.at(k)`).

### 2. 句内折返点

挂在**语义反转词**上(与 `42-text-main/impl/per-line.md` §3 同源):

```python
from assfx.color import find_break, fold
t_break, word = find_break(ph, ["ない", "でも", "けど"])
ramps = fold(ph, t_break, k_before=0.15, k_after=0.85)
```

判据: **把那段颜色单独拿出来, 不看歌词, 能看出"这里意思反了"吗?**

### 3. 声部色(先测, 不猜)

```bash
hx-karaoke voices.py --vocals proj/stems/vocals16k.wav --timing proj/timing.json \
    --lyrics proj/lyrics.txt --out proj/review/voices.json
```

**反验必须做**: 换 `stems/inst.wav` 再跑一遍, `none` 占比应显著上升
(实测人声 `none` 14% vs 伴奏 `none` **93%`). 没做反验的声部判定不许采信.

声部色用**色相旋转**派生, 不是另挑一个颜色: 同明度同饱和, 观感才是"同一套配色里的另一个位置".

### 4. 背景跟随(默认关)

**能做**: 从 MV 逐段抽帧算主色 → 生成色系 → 文本描边跟着走.
**代价**: 会牺牲全曲色彩统一性. 参考里最"高级"的两份(Charlotte / 东方)恰恰是**克制的** ——
它们不追背景.

**本项目默认关闭**, 要开就**逐段跟随、且全曲仍受一个统一色域约束**.
开了以后必须重跑对比度检查, 不许把可读性吃回去.

## 不许越过的红线

- 填充恒为纯白, 色彩只走描边(`doc/KFX-RULES.md`).
- **描边亮度上限 ≤0.1833**(对白填充 ≥4.5:1). 逐字游走时每次派生后都要复量;
  亮端色(`#FFFFFF`)不能直接当描边色 —— 它会连描边一起吃掉.
- 单色族 = 无色彩叙事; 彩虹 = 可读性灾难. 专业成品的区间是 **1~4 个色相族**.

## 实测: 修之前是"每句一色", 修之后是"每句 12 色"

用本项目漆黑子弹 ED 重做过一次对照(`dev/漆黑子弹/トコハナ/review/v4-vs-v5.md`),
输入文件完全相同, 只改配色接法:

| 量 | 未接 `hl_color` | 接了 `make_hl_color` |
|---|---|---|
| 高亮层填充色种类 | 17 | **587** |
| **每句有彩填充色种类(中位)** | **1** | **12** |
| 每句有彩填充色种类(最大) | 1 | **36** |

中位 1 说明旧版**确实是一句一色**(不是"看起来差不多"), 这条判据可以直接拿来量。

**量法**(不改代码就能跑):

```bash
hx-karaoke python -c "
import re,colorsys,collections,statistics
per=collections.defaultdict(set)
for ln in open('proj/out.ass',encoding='utf-8-sig'):
    if not ln.startswith('Dialogue:'): continue
    f=ln.split(',',9)
    if len(f)<10 or not f[4].startswith('ly:') or int(f[0].split(':')[1])<23: continue
    for m in re.finditer(r'\\\\1c&H00([0-9A-Fa-f]{6})&', f[9]):
        c=m.group(1).upper(); r,g,b=[int(c[i:i+2],16)/255 for i in (0,2,4)]
        h,s,v=colorsys.rgb_to_hsv(r,g,b)
        if s>0.25 and v>0.25: per[f[4]].add(c)
print('每句有彩色 中位', statistics.median([len(v) for v in per.values()]))
"
```

**只看 Layer >= 23 的 `ly:` 事件** —— 那是高亮层(`Doc.ev` 把文字统一抬到特效之上).
数 Layer 21/22 是底字层, 它的颜色本来就不该分化, 拿它当判据会得出错误的结论.

## 一个真实的坑: 声部 key 要对齐

`voices.py` 的 key 是 `<line>.<unit>.<mora>`, 而一个字可能**跨多个音拍**.
`make_hl_color` 里写死 `mora=0` 时命中率极低, 声部色等于没生效(全部退回 solo).
必须按该字的 `ch["morae"]` 列表逐个查, 取第一个命中的.

## 过关条件

- 全曲色相族 **1~4 个**; 同族内**有变化**(逐字游走或按段变档).
- **每句有彩填充色种类 中位 >= 3**(旧版是 1; 实测接上后可到 12).
- **每句色相跨度落在 20°~120°**, 且 >=90% 的句在区间内.
  实测第一版: 中位 26°(方向对) 但 5/32 句 >180°(过了)、25/32 句 <=3°(等于没动) ——
  **分布极不均匀**. 光看"有彩色种类"会以为很丰富, 看跨度才发现大部分句色相没动.
  跨度算法要补首尾环绕间隔, 否则 23° 与 25° 会被算成 359°.
- 目检: 任意帧的填充/描边对比度达标(`doc/KFX-RULES.md` 的三条命令).
- 声部配色必须附**反验数字**(人声 vs 伴奏的 `none` 占比).

## 这一步要用的脚本

- `<skill>/scripts/assfx/color.py` - `Scheme` / `Palette` / `make_hl_color` / `fold` / `find_break`
- `<skill>/scripts/voices.py` - 声部归属检测(带反验)
