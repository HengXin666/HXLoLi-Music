# 00 准备: 环境 + 字体 + 设备

## 只做这一件事

把跑完整条链路的**环境前提**备好: 运行环境、字体、算力设备. 不做任何与具体歌曲相关的判断

## 命令: 一条

```bash
hx-karaoke --check        # 体检: 缺环境/缺依赖/缺字体都会列出来, 齐了就退出码 0
hx-karaoke setup_env.py   # 缺什么补什么 (幂等, 齐了就秒过)
```

`setup_env.py` 做完三件事, 都不需要判断

1. **环境**: 建/复用一个共享 venv 并装齐依赖 (见下); 位置 `${XDG_CACHE_HOME:-~/.cache}/hx-anime-karaoke-ass/venv`
2. **字体**: 下 7 个 OFL ttf 到 `<skill>/fonts/` (52MB, 不进 git)
3. **自检**: 逐脚本 import 冒烟 + 关键库版本 + `device.py` 设备探测; 缺依赖时退出码非 0

再跑一次不会重装: 环境与字体各自有幂等判定, 已经齐全就直接跳过

## 工作区: `dev/<番名>/<歌曲名>/`

**所有工程一律放 `dev/<番名>/<歌曲名>/`**, 与发布目录 `static/music/<番名>/` **一一对应** (`<番名>` 用中文名, 与 `static/music/` 下已有的目录名保持一致; 原创非番剧曲用艺人/作品名)

```bash
mkdir -p dev/<番名>/<歌曲名>
cd dev/<番名>/<歌曲名>          # 之后所有命令都在这里跑, --project 也就都是 "."
hx-karaoke align_ctc.py --lyrics lyrics.txt --vocals stems/vocals16k.wav --out timing_auto.json
```

为什么是这个形态

- **整棵 `dev/` 在 `.gitignore` 里**. 工作区里的东西是**中间产物**  完整 MV(`base.mp4`, 单首 100~170MB)、分离出的人声与伴奏、逐次迭代的 `timing*.json` / `fixes.json`、频谱截图、抽帧、矢量缓存. 它们只对"这一次制作"成立, 提交它们会把仓库变成几个 GB 的素材库
- **与发布目录同构**, 于是搬家是一次 `mv`, 不需要重新判断归属: `dev/<番名>/<歌曲名>/` 里的最终文件搬到 `static/music/<番名>/`
- 工程目录名变了不影响内部路径: `make_ass.py` 的 skill 位置取自 `ASSFX` (由 `hx-karaoke` 导出), **不写相对层数**  写了层数的话, 在 `dev/` 与 `static/` 之间搬家就会断链 (实测: 三个老工程的相对路径在搬进 `dev/` 后全部失效). 取字体同理, 用 `"$(hx-karaoke --fonts)"` 而不是自己数 `../`

## 发布: 做完了才搬, 并跑一次 make.sh

```bash
DEST=static/music/<番名>; NAME="<艺人> - <曲名> (<中文名>)"
# 1) 音频抽成 mp3,**与 ass 同名**(find_matching_ass 是按同名配对的)
ffmpeg -i dev/<番名>/<歌曲名>/base.mp4 -vn -c:a libmp3lame -q:a 2 "$DEST/$NAME.mp3"
# 2) 成品 ass 改名放进去
cp dev/<番名>/<歌曲名>/out.ass "$DEST/$NAME.ass"
# 3) 字体放目录级 fonts/ (与已有发布目录同约定)
# 4) 生成索引, 并**核对新曲真的进了 playlist**
bash make.sh
```

发布前先过门禁: 在工程目录跑 `hx-karaoke check_gates.py --project . --stage render`, 退出码非 0 就不许搬. 搬完 `make.sh` 后核对三件事: `playlist.json` 里有这条、它的 `audioUrl`/`assUrl` 指向的文件都存在、`static/info/<id>.json` 生成了

## 为什么统一用一条命令, 以及为什么不是 `uv run` / 不是 `.venv`

三条都是实测结论, 不是偏好

- **`uv run <脚本>` 会给每个脚本建一个独立的脚本环境, 新脚本首次要现场装包.** uv 的脚本环境按**脚本文件**命名 (`environments-v2/<脚本名>-<hash>`), 实测三个依赖完全相同的`a.py`/`b.py`/`c.py` 得到三个环境目录. 本 skill 有 27 个带 inline 依赖块的脚本, 而且**每次新增/改动脚本, 它首次运行都要等一组包装完**: 实测一个依赖 `scipy`+`matplotlib` 的新脚本 `uv run` **首次 14.5s**、再次 0.0s; 同一个脚本走 `hx-karaoke`(共享环境已含这两个包) **首次 0.0s**. 这就是"每次都要 agent 去判断环境"的实际形态. ← **注意别把理由写成"省盘"**: uv 的包内容本来就靠硬链接共用. 按 inode 实测, `environments-v2` 里 92.5% 的文件是硬链接, 124 个脚本环境对 `archive-v0` 的**独占增量合计只有 0.65 GiB**. 用多次独立 `du` 求和会把硬链接重复计, 得到假的"12GB 重复"
- **不能在 skill 目录里建 `.venv`.** skill 在仓库内, uv 的项目发现会向上找到`HXLoLi-Music/pyproject.toml`, 把这个 `.venv` 当成**仓库的** venv 并重新同步成仓库的Python 与依赖(实测: 建完立刻变成 py3.14 + 根项目依赖, numpy 都被换掉). 所以共享环境必须落在仓库之外
- **`uv run` 不是"不能用", 它是可用备选.** 实测它会把脚本所在目录放进 `sys.path[0]`, 所以跨脚本 import 也通 (`ctc_read.py` 的 import、工程的 `make_ass.py` 配 `ASSFX` 都能跑, 产物 md5 与 `hx-karaoke` 相同). 推荐 `hx-karaoke` 是因为它免掉"新脚本首次装包" 的等待, 并把脚本/字体路径收敛成一个入口

## 跑脚本一律 `hx-karaoke`

```bash
hx-karaoke <脚本> [参数...]      # 例: hx-karaoke align_ctc.py --lyrics proj/lyrics.txt ...
hx-karaoke python -c '...'       # 直接跑 python
hx-karaoke --env                 # 打印环境位置与关键库版本
```

- `hx-karaoke` 是 `bin/hx-karaoke` 装到 `~/.local/bin/` 的符号链接, 由 `setup_env.py` 一步装好
- 它把 `<skill>/scripts` 放进 `PYTHONPATH` (子进程内), 并接受 `ASSFX` / `ASSFX_FONTS` 覆盖
- 脚本名先在 `<skill>/scripts/` 下找(含各职责子目录, 如 `align/` `kf/` `kfx/score/`), 再按原样当路径找  `hx-karaoke ctc_read.py ...` 与 `hx-karaoke scripts/ctc/ctc_read.py ...` 等价
- 统一用它, 不要在工程里另建 `.venv`. (`uv run` 能用, 见上; 只是新脚本首跑更慢. )

依赖清单来自各脚本头部的 inline 依赖块(并集), 由 `setup_env.py` 从源码提取, 不是手抄: 改了某个脚本的 inline 块, 重跑 `hx-karaoke setup_env.py` 即可, 它会发现新依赖并补齐

- 字体: 日文正文/注音用 Shippori Mincho B1、中文用霞鹜文楷; 元气系换 Mochiy Pop One + 站酷快乐体; 拉丁和声用 Cormorant Garamond Italic. 全部 OFL, **不进 git**, 换机器就重跑
- 字体路径别手写: 用 `"$(hx-karaoke --fonts)"` 取绝对值 (或 `--fontsdir fonts` 指相对当前工程的软链)

## 设备: 默认自动优先 GPU

`device.py` 探测到 CUDA 就用(本机 RTX 4080 Laptop 实测可用). `ASSFX_DEVICE=cpu` 或 `--device cpu` 关掉. 12GB 显存跑 htdemucs_ft 整曲可能 OOM, 已捕获并自动退回 CPU

**换机器或换设备时要证明它不影响结果**, 不能默认

```bash
hx-karaoke device_check.py --vocals proj/stems/vocals16k.wav --seconds 60
```

判据是**尖峰帧位移**(逐帧 argmax 一致率 + 峰值帧位置差): 位移 ≤1 帧(20ms) 才算等价. 实测本机一致率 100%、位移 0.000s, 故 GPU 可直接出终稿; 位移 >1 帧时终稿用 `ASSFX_DEVICE=cpu` 复跑

**别用短片段下结论**: 12s 片段上 CUDA 因初始化开销可能比 CPU 还慢(实测 8.1s vs 3.1s),
但整曲(切几十块逐块前向)才是真实场景, GPU 的优势在那里

## 产物与过关条件

- `hx-karaoke --check` 退出码 0: 环境齐全、`<skill>/fonts/` 下 7 个 ttf 齐. 缺字体时 `validate_ass.py` 会判 FAIL(libass 会静默回退, 效果全变)
- `hx-karaoke --env` 能打印出 python 与 torch/transformers 版本
- `device_check.py` 的位移 ≤1 帧. 未做过这一步就在交付说明里写明"未验证设备等价性"
