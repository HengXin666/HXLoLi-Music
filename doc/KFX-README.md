# KFX 规则  ASS 特效歌词的可读性与配色

让「做 KFX」这件事**可验证**，而不是靠眼睛看着"还行"。

## 文件

| 文件 | 作用 |
|---|---|
| `doc/KFX-RULES.md` | **主文档**。配色/可读性的规则，每条都带实测依据与验证命令 |
| `py/ass/check_contrast.py` | 配色检查器。改完先跑它，再渲染 |

跑之前先 `uv sync`（numpy / pillow 已在 `pyproject.toml` 里）。

## 三件事，按顺序做

**1. 定配色 → 先量数字**

```bash
py/ass/check_contrast.py --fill FFFFFF --outline 91276F --bg 0B1016
```
填充/描边必须 ≥ 4.5:1。**浅色描边一律不合格**（这是踩过的坑）。
做"整行先出现"时再加 `--ghost` 指定暗态色，要求 ≥ 3:1。

**2. 渲染 → 再量真实像素**

```bash
py/ass/check_contrast.py --image shots/frame.png
```
理论值对了，渲染出来还可能不对（色彩空间、模糊、叠加）。

**3. 抽帧看过程**

同一句连抽几帧，确认**亮着的字数递增、字的位置不动**。

## 为什么要有这个目录

真实的失败记录：

- 用 填充 `(232,244,255)` + 描边 `(168,216,248)`，两者只差 **1.36:1**，
  渲染出来轮廓消失、糊成一团。我当时**看了渲染图还报了"做完了"**。
- 未点亮的字用 `(46,40,34)` 打在 `(11,16,22)` 背景上，只有 **1.31:1**，
  效果是"整行没出现"而不是"整行暗着"。

**共同点：没有可验证的判据就去渲染，而且渲染完没有回头量。**

## 测量环境

依赖已经声明在 `pyproject.toml` 里，安装一次即可：

```bash
cd /home/hx/Loli/code/HXLoLis/HXLoLi-Music
uv sync
```

然后：

```bash
.venv/bin/python py/ass/check_contrast.py --fill FFFFFF --outline 4D7726 --bg 0B1016 --ghost 888888
```
