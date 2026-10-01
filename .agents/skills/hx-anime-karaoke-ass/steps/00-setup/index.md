# 00 准备：字体与设备

## 只做这一件事

把跑完整条链路的两个外部前提备好：**字体**与**算力设备**。不做任何与具体歌曲相关的判断。

## 命令

```bash
export S=<skill>/scripts              # 本 skill 的 scripts/ 目录
uv run $S/fetch_fonts.py              # 字体下到 <skill>/fonts/（52MB，不进 git）
uv run $S/device.py                   # 打印本次会用的 torch 设备
```

- 一律 `uv run`，不要裸 `python`：uv 按脚本的 inline 依赖元数据建临时环境。
- 字体：日文正文/注音用 Shippori Mincho B1、中文用霞鹜文楷；元气系换 Mochiy Pop One + 站酷快乐体；
  拉丁和声用 Cormorant Garamond Italic。全部 OFL，**不进 git**，换机器就重跑这条。
- 后面所有命令里的 `--fontsdir fonts` 都指 `<skill>/fonts`；用 `ASSFX_FONTS` 可指向别处。

## 设备：默认自动优先 GPU

`device.py` 探测到 CUDA 就用（本机 RTX 4080 Laptop 实测可用）。`ASSFX_DEVICE=cpu` 或 `--device cpu` 关掉。
12GB 显存跑 htdemucs_ft 整曲可能 OOM，已捕获并自动退回 CPU。

**换机器或换设备时要证明它不影响结果**，不能默认：

```bash
uv run $S/device_check.py --vocals proj/stems/vocals16k.wav --seconds 60
```

判据是**尖峰帧位移**（逐帧 argmax 一致率 + 峰值帧位置差）：位移 ≤1 帧(20ms) 才算等价。
实测本机一致率 100%、位移 0.000s，故 GPU 可直接出终稿；位移 >1 帧时终稿用 `ASSFX_DEVICE=cpu` 复跑。

**别用短片段下结论**：12s 片段上 CUDA 因初始化开销可能比 CPU 还慢（实测 8.1s vs 3.1s），
但整曲（切几十块逐块前向）才是真实场景，GPU 的优势在那里。

## 产物与过关条件

- `<skill>/fonts/` 下 7 个 ttf 齐；缺字体时 `validate_ass.py` 会判 FAIL（libass 会静默回退，效果全变）。
- `device_check.py` 的位移 ≤1 帧。未做过这一步就在交付说明里写明"未验证设备等价性"。
