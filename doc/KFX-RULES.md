# HX-KFX 规则

ASS 特效歌词的制作规则。**每条都来自实测，不是经验之谈。**

改这个文件之前先读「怎么验证」一节：新增规则必须附一条可复现的测量命令，
否则它只是意见，不是规则。

---

## 0. 铁律

**渲染之前先测量。** 配色、可读性、对比度都是可以算出数字的。
看着"还行"就交付，是这份文档存在的唯一原因。

判据用 WCAG 2.1 contrast ratio（W3C 原文，非转述）：

| 对象 | 门槛 |
|---|---|
| 大字号（≥18pt，或 ≥14pt 粗体） | ≥ **3:1** |
| 普通字号 | ≥ **4.5:1** |

原文特别强调：**4.499:1 不算过，不能四舍五入**。
按 1080p 的 ASS 字号换算，正文 60px 以上都算"大字号"，门槛 3:1；
但本项目的实际教训是**别贴着 3:1 交付**，见下条。

---

## 1. 填充与描边：必须拉开，不能同色系

**规则**：填充与描边的对比度 ≥ **4.5:1**。

**教训（实测）**：曾经用 填充 `(232,244,255)` + 描边 `(168,216,248)`，
两者对比只有 **1.36:1**，渲染出来轮廓完全消失、糊成一团。
共同规律是「都偏浅」**浅色描边一律不合格**。

**描边亮度的硬上限**：要让白填充有清晰轮廓，描边亮度必须 ≤ **0.1833**
（纯灰约 RGB ≤ 118）。**描边必须比中灰更暗。**

**专业成品的做法**（Charlotte `Lia - Bravely You.ass`，实测提取）：

```
\1c 填充 = &HFFFFFF&                纯白，全曲不变
\3c 描边 = 四色轮换，每段一色：
     &H672791& → RGB(145, 39,103) 梅紫     对白 7.81:1
     &HBA4561& → RGB( 97, 69,186) 紫罗兰   对白 6.84:1
     &H45C043& → RGB( 67,192, 69) 绿       对白 2.37:1  ← 唯一不合格的
     &HA06E31& → RGB( 49,110,160) 蓝       对白 5.43:1
```

规律是**白填充 + 饱和的中间调彩色描边**，不是白描边。
注意它自己也有一色（绿）只到 2.37:1  说明 2.37:1 在动效场景下勉强能用，
但**那是下限，不是目标**。

**实测合格的描边色**（对白填充）：

| 颜色 | RGB | 对比 |
|---|---|---|
| 纯黑 | (0,0,0) | 21.00:1 |
| 深蓝黑 | (10,14,24) | 19.29:1 |
| 近黑 | (16,16,20) | 18.98:1 |
| 深红 | (140,30,40) | 9.01:1 |
| 深青 | (20,90,100) | 7.85:1 |
| Charlotte 梅紫 | (145,39,103) | 7.81:1 |
| Charlotte 紫罗兰 | (97,69,186) | 6.84:1 |
| 中灰 100 | (100,100,100) | 5.92:1 |
| Charlotte 蓝 | (49,110,160) | 5.43:1 |
| 深金 | (140,105,30) | 5.05:1 |
| 中灰 118 | (118,118,118) | 4.54:1 |

**不合格**：浅灰 180 → 2.07:1；浅蓝 (168,216,248) → 1.52:1。

---

## 2. 「整行先出现再逐字点亮」时，暗态也必须看得见

**前提**：这条是**本项目特有**的规则。Charlotte 不用这套机制（它是逐字放大出现，
没有"整行暗着等待"的状态），所以拿这条去量 Charlotte 会 FAIL  那是正常的，
不是它不合格。**只有做"整行先出现"时才适用。**

**规则**：未点亮（暗态）的填充，对背景 ≥ **3:1**。

**教训（实测）**：曾用暗态填充 `(46,40,34)` 打在背景 `(11,16,22)` 上，
对比只有 **1.31:1**，暗态描边 `(16,8,4)` 更是 **1.04:1** 
效果是"整行根本没出现"，而不是"整行出现了但暗"。

**按背景 (11,16,22) 反查暗态灰阶**：

| 灰阶 RGB | 对背景 | 判定 |
|---|---|---|
| 89 | 2.73:1 | 太暗 |
| **108** | 3.64:1 | 可用下限 |
| **123** | 4.51:1 | 推荐 |
| 136 | 5.39:1 | 更清晰但削弱了亮暗对比 |
| 148 | 6.29:1 | 亮暗对比不足，失去"点亮"的意义 |

**设计取舍**：暗态越亮越可读，但亮暗差越小，"点亮"越不明显。
实测的平衡点在 **暗态亮度 0.15~0.20（灰阶 108~123）**，
此时点亮前后对比约 **4:1 以上**，两件事都成立。

## 3. 背景必须压暗

**规则**：字幕底板的亮度要低到让白填充达到 ≥ 12:1。

Charlotte 用的近黑背景 `(11,13,21)` 配白填充是 **18:1**。
本项目的黑底 `(11,16,22)` 配白填充是 **17.11:1**  这档没问题。

反例是浅灰或彩色底板：白字在上面做不出对比，只能加"黑描边"补救，
而黑描边会把彩色的设计感吃掉。

---

## 怎么验证

三条命令，改完配色就跑。

**1. 量配色对（不需要渲染）**

```bash
cd /home/hx/Loli/code/HXLoLis/HXLoLi-Music && .venv/bin/python - <<'PY'
import numpy as np
def lum(c):
    c=np.array(c,dtype=float)/255.0
    c=np.where(c<=0.03928,c/12.92,((c+0.055)/1.055)**2.4)
    return float(0.2126*c[0]+0.7152*c[1]+0.0722*c[2])
def R(a,b):
    l1,l2=lum(a),lum(b); hi,lo=max(l1,l2),min(l1,l2)
    return (hi+0.05)/(lo+0.05)
fill=(255,255,255); outline=(145,39,103); bg=(11,16,22)
print("填充/描边 %.2f:1  (需 >= 4.5)" % R(fill,outline))
print("填充/背景 %.2f:1  (需 >= 12)" % R(fill,bg))
PY
```

**2. 量渲染结果（真实像素，不是理论值）**

```bash
cd /home/hx/Loli/code/HXLoLis/HXLoLi-Music && .venv/bin/python - <<'PY'
from PIL import Image
import numpy as np
from collections import Counter
def lum(c):
    c=np.array(c,dtype=float)/255.0
    c=np.where(c<=0.03928,c/12.92,((c+0.055)/1.055)**2.4)
    return float(0.2126*c[0]+0.7152*c[1]+0.0722*c[2])
a=np.asarray(Image.open("shots/frame.png").convert("RGB")).astype(int)
q=(a//16*16).reshape(-1,3)
for c,n in Counter(map(tuple,q)).most_common(8):
    if n>=200: print("RGB%-16s %7d px  亮度%.3f" % (str(c),n,lum(c)))
PY
```

**3. 抽帧看过程**（看的是"逐字点亮"是否真的发生）

```bash
for t in 1.25 1.8 2.4 3.0; do
  ffmpeg -y -ss $t -i out.mp4 -frames:v 1 shots/f_$t.png
done
```
同一句的连续几帧里，**亮着的字数必须递增，字的位置必须不动**。

---

## 附录 A：环境

| 组件 | 位置 | 备注 |
|---|---|---|
| Aegisub 3.4.2 | `~/.local/opt/aegisub` | 官方包解到用户目录，免 root |
| aegisub-mcp | `~/.local/opt/aegisub-mcp` | 本地补丁在 `patches/local-fixes.patch` |
| Python 依赖 | 项目顶层 `.venv` | `uv sync` 安装（numpy + pillow 已写进 `pyproject.toml`） |

跑模板器（官方 Karaoke Templater）：

```bash
cd /home/hx/Loli/code/HXLoLis/HXLoLi-Music
export AEGISUB_AUTOMATION_INCLUDE=/home/hx/.local/opt/aegisub/usr/share/aegisub/automation/include
/home/hx/.local/opt/aegisub-mcp/.venv/bin/python - <<'PY'
import sys, os
sys.path.insert(0,"/home/hx/.local/opt/aegisub-mcp/src")
import aegisub_mcp.lua.engine as E
from aegisub_mcp.asscore import document as doc
INC=os.environ["AEGISUB_AUTOMATION_INCLUDE"]
AL="/home/hx/.local/opt/aegisub/usr/share/aegisub/automation/autoload"
d=doc.AssDocument.load("IN.ass")
e=E.LuaEngine(d)
for f in ("karaskel.lua","utils.lua","unicode.lua"):
    e.load_file(os.path.join(INC,f))
e.load_file(os.path.join(AL,"kara-templater.lua"))
r=e.run_filter("Karaoke template")
print("ok:", r.ok, r.error or "")
if r.ok: d.save("OUT.ass")
PY
```

---

## 附录 B2：检查器自己的坑（它骗过我）

**`lstrip("0x")` 是字符集不是前缀。**
`lstrip` 剥的是"字符集合里的任意字符"，所以 `"0B1016".lstrip("0x")` 会把开头的
`0` 和 `B` 都剥掉，得到 `"1016"`  之后所有解析都是垃圾。
用 `startswith("0x")` 判断，别用 `lstrip`。

**ASS 的 `&HBBGGRR&` 与网页 `#RRGGBB` 顺序相反。**
混用会静默把红蓝对调：`0B1016` 当作网页色是 `RGB(11,16,22)`，
当作 ASS 色是 `RGB(22,16,11)`。**背景解析错一个色序，所有对比度数字全部失真。**

教训：检查器给出 PASS 之后，**要拿一个已知答案的样本反验它**。
本项目的反验证样本：
`check_contrast.py --fill FFFFFF --outline 91276F --bg 0B1016 --ghost 6C6C6C`
应当输出 填充/描边 ≈ 7.8:1（Charlotte 的梅紫），偏差超过 0.1 就是解析错了。

---

## 附录 B：KFX 模板写法（踩过的坑）

**1. 模板行的 effect 栏写 `template syl`，正文放文本栏。**
写成别的都不识别；而且**不报错，静默不生成**。

**2. 模板正文必须自带外层 `{` `}`。**
漏了的话整串标签会被当正文渲染  屏幕上出现满屏 `\an5\pos(...)` 的字面文字。

**3. 算术要用 `!expr!`，不是 `$var+180`。**
写成 `$sstart+180` 会原样输出字符串 `"0+180"`，只有 `!$sstart+180!` 才求值。

**4. `$sstart` 是相对行首，`$lstart` 是绝对毫秒。**
两者相减会得到负数。要算字的相对时刻，直接用 `$sstart`。

**5. 音量/时间变量实测值**（用于推导）：
`$sstart` 逐字递增（实测 0 / 680 / 1240 / 1920 / 2480），
`$lstart` = 行首绝对毫秒（实测 1170），`$sdur` = 该字时长。

---

## 附录 C：当前达到的水平与差距

| 项 | 状态 |
|---|---|
| 用官方模板器生成 | 已跑通，165 事件，零报错 |
| 整行先出现再逐字点亮 | 已实现（`!$sstart!` 驱动） |
| 配色符合可读性 | **待重做**（当前 1.36:1，不合格） |
| 覆盖全曲 | 只 17 句（源文件是缺陷版，逐字时间被多副本污染） |
| 视觉设计深度 | 远不够；参照 Charlotte 的手法（日文双层幻影 + 中文四条 clip 撕裂扫描） |