# Agent Note: 卡拉OK skill 的环境收敛为一条命令 + 仓库外的单一共享 venv

Status: implemented

Decision-ID: karaoke-env-single-command

- 决策依据: 用户原话「对于环境的安装，每次使用都需要 agent 去判断，还是环境的话就很麻烦。
  我希望你能配置成一个命令。然后一键搞定就可以了」
- 相关: [karaoke-runtime-artifacts-out-of-skill](2026-10-02-karaoke-runtime-artifacts-out-of-skill.md)
  （同一条原则的另一半：产物移出 skill / 环境也移出 skill）

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/setup/env.py`

## Problem

`steps/00-setup/index.md` 的原判据是「一律 `uv run <脚本>`，不要裸 `python`」。这条在单脚本时成立，
在这个 skill 的规模上不成立，原因是**实测的**：

1. **`uv run` 会给每个脚本建一个独立的脚本环境，新脚本首次要现场装包。**
   实测三个依赖完全相同的 `a.py`/`b.py`/`c.py` 得到三个目录
   `environments-v2/a-1771ecae…`、`b-ef3c904a…`、`c-369bcfa7…`。
   本 skill 有 **27 个**带 inline 依赖块的脚本  关键在于**每次新增/改动一个脚本，
   首次运行都要等一组包装完**：实测一个依赖 `scipy`+`matplotlib` 的新脚本
   `uv run` **首次 14.5s、再次 0.0s**；同一个脚本走 `hx-karaoke`（共享环境已含这两个包）
   **首次 0.0s**。这就是「每次使用都需要 agent 去判断环境」的实际形态。

   > **更正（2026-10-02，用户指出后复测）**：本条原先写的是「同一个 torch 被装十几遍、
   > `environments-v2` 实测 12GB 重复」。那个数字是**错的**  它是用多次独立的 `du`
   > 调用求和得到的，而 `du` 只在**单次遍历内**对同一 inode 去重，多次调用会把硬链接重复计。
   > 按 inode 实测：`environments-v2` 里 92.5% 的文件是硬链接，**124 个脚本环境对
   > `archive-v0` 的独占增量合计只有 0.65 GiB**，两树并集的真实占盘 25.57 GiB
   > （archive 24.92 + env 独占 0.65）。也就是说 **uv 的包内容本来就是共用的**，
   > 用户「Python 环境缓存应该是共用的」这个判断成立。
   > 结论不变（仍然收敛成一条命令），但**理由从"省盘"改成"省新脚本首次装包的时间 +
   > 统一的脚本/字体入口"**  见下面 Alternatives 里被改判的那条。
2. **不能在 skill 目录里建 `.venv`。** skill 在仓库内，uv 的项目发现会一路向上找到
   `HXLoLi-Music/pyproject.toml`，把那个 `.venv` 当成**仓库的** venv 并重新同步成
   仓库的 Python 与依赖。实测：`uv venv --python 3.11 .venv` 建完立刻变成
   `pyvenv.cfg` 写 `version_info = 3.14.7` + 根项目依赖，连 numpy 都被换成根项目的版本，
   于是 `import scipy` 直接 `ModuleNotFoundError`。这个坑在动手前不知道，是踩出来的。

## Decision

**一份依赖清单，一个环境，一条命令。**

- 环境位置 `${XDG_CACHE_HOME:-~/.cache}/hx-anime-karaoke-ass/venv`  **仓库之外**，
  与 skill 已有的 svg 缓存同级。用 `uv venv --no-project` 建，显式关掉项目发现。
- 依赖清单 = `scripts/**/*.py` 头部 inline 块里 dependencies 的**并集**，
  由 `scripts/setup/setup_env.py` 从源码提取，**不是手抄**；另有 `EXTRA`（`torchaudio`、
  `transformers>=5.18,<6`，后者对齐实测跑通的版本）。清单写进
  `~/.cache/hx-anime-karaoke-ass/requirements.txt`。
- `bin/hx-karaoke` 是所有脚本的**唯一入口**：`hx-karaoke <脚本> [参数...]`。
  它把 `<skill>/scripts` 放进 `PYTHONPATH`（于是 `ctc_read.py` 能 import `align_ctc`，
  工程里的 `make_ass.py` 能 import `assfx.*`），导出 `SKILL_ROOT` / `ASSFX` / `ASSFX_FONTS`，
  按 `原样路径 → <skill>/scripts/ → <skill>/` 解析脚本名，`*.sh` 交给 bash、其余交给 venv 的 python。
  `setup_env.py` 一步把它符号链接到 `~/.local/bin/hx-karaoke`。
- `setup_env.py` 幂等：环境存在且依赖齐全就跳过、字体齐就跳过，最后跑一次自检
  （逐模块 import + 关键库版本 + `device.py` 设备探测）；**缺依赖退出码非 0**。
- `steps/00-setup/index.md` 的契约从「字体与设备」改成「环境 + 字体 + 设备」，
  命令收缩成 `hx-karaoke --check` 与 `hx-karaoke setup_env.py` 两条。
  22 个步骤文档 + 27 个脚本 docstring 里的 `uv run` 全部改成 `hx-karaoke`，`$S` 变量取消。
- `steps/00-setup/index.md` 里保留**为什么不用 uv run / 不建 .venv** 的两条实测依据，
  否则下一个人会把 `uv run` 改回来。

### MiliKara 评测（用户第二个要求）

同一次会话里按要求评测了 [MiliKara](https://github.com/BilyHurington/MiliKara)。
**结论是回退，不引入**  那是另一条决策，见
[2026-10-02-milikara-not-adopted](../../rejected/architecture/2026-10-02-milikara-not-adopted.md)。

那篇里也记录了评测方法上的两个坑（我第一版评错了维度：先评注音而它主攻对齐；
第二版裁判有循环污染：拿网络逐字源当尺子，而我们的成品恰是同一份源校准的）。
本文只管环境那一条决策，不再复述评测数字。

## Alternatives considered

- **什么都不做，保留 `uv run`**：最强理由是「uv 本来就是为脚本依赖而生的，`uv run` 是官方做法，
  换成一堆自定义包装是过度工程」。
  **这条在 2026-10-02 被复测改判了一半**（用户指出「Python 环境缓存应该是共用的」之后）：
  - 原先写的「12GB 重复」**不成立**（见 Problem 里的更正），uv 的包内容本来就靠硬链接共用，
    所以「省盘」不能作为理由。
  - 但它**仍然被否决**，理由换成实测的启动成本：新脚本首次 `uv run` 要现场装包
    （`scipy`+`matplotlib` 实测 **14.5s**），而共享环境里已有这些包时 `hx-karaoke` **0.0s**。
    本 skill 的脚本会持续新增/改动，每次首跑都付这个等待。
  - 另外 **`uv run` 并不是"不能用"**  实测它会把脚本所在目录放进 `sys.path[0]`，
    所以 `ctc_read.py` 的跨脚本 import 与工程的 `make_ass.py`（配 `ASSFX`）都能跑通，
    产物 md5 与 `hx-karaoke` 相同。它是**可用的备选**，只是每次新脚本首跑更慢。
- **在 skill 目录内建 `.venv`，让所有脚本共用它**：最强理由是「路径最短、最符合直觉，
  而且用户说的就是『一键搞定』」。否决：实测被 uv 项目发现接管，建成即被同步成仓库的
  py3.14 环境，`scipy` 缺失。要让它在仓库内可用，就得给每个调用点加 `--no-project`
  或把 skill 移出仓库  前者的隐式依赖比「环境放仓库外」更难记。
- **把 `scripts/setup/setup_env.py` 写成 `uv run scripts/setup/setup_env.py` 的调用方式**：
  最强理由是「与其它脚本一致」。否决：setup 脚本的职责就是**制造**那个环境，
  它自己不该依赖 uv 的脚本环境解析。改成 `python3 scripts/setup/setup_env.py`（只用标准库），
  `hx-karaoke` 首次调用时自动补建。
- **把 MiliKara 整个接进来替代 `align_ctc.py`**：详见
  [2026-10-02-milikara-not-adopted](../../rejected/architecture/2026-10-02-milikara-not-adopted.md) 
  是那条独立决策，本文不重复。

## Consequences

- 环境从「27 个脚本各一个」变成「1 个」。**注意成本口径**：这不是"省了 12GB"
  （uv 本来就共用包内容：`archive-v0` 25.06 GiB 是唯一一份包本体，
  `environments-v2` 124 个环境对它的独占增量只有 0.65 GiB），
  而是「新脚本首次不必再装包」+「脚本/字体的入口统一成一条命令」。
  共享环境本身 5.64 GiB（含 torch 2.14.1+cu130），对 `archive-v0` 的独占增量约 **0.08 GiB**。
- **撤回一条错误建议**：本文早先（以及给用户的答复里）说过
  「旧目录不自动删  需要时手动清 `~/.cache/uv/environments-v2`，能省 12GB」。
  按 inode 复测后这句是错的：删那 124 个环境只释放 **0.65 GiB**（它们的独占增量），
  不是表观 12.9 GiB。删它们没有实质收益，**不值得动**。
- 代价：`hx-karaoke` 是新命令，文档与习惯都要改。已在 22 个步骤文档与 27 个脚本 docstring
  里同步，并在 `SKILL.md` 与 `steps/00-setup/index.md` 写了原因。
  **但 `uv run` 仍然可用**（见 Alternatives），文档里不再把它说成"禁止"。
- 收益：`hx-karaoke --check` 把「环境齐不齐」变成一个退出码，`setup_env.py` 把
  「装什么」变成一个从源码提取的清单；新脚本首跑不再有装包等待。

## Testing

- `hx-karaoke --check` → 退出码 0（缺依赖 0 / 缺字体 0）。
- `python3 scripts/setup/setup_env.py --no-fonts` → `[smoke] 模块 43 个: 依赖失败 0` + 设备探测到 cuda。
- 无损对拍：用新环境重生成 `dev/漆黑子弹/トコハナ/out.ass`，与既有产物
  **md5 完全相同**（`8a66e35cff41b17396e7e04277553c9b`）；
  `hx-karaoke check_gates.py --project . --stage render`（在 `dev/漆黑子弹/トコハナ`）→ 13 项全 PASS；
  `hx-karaoke validate_ass.py out.ass --fontsdir <skill>/fonts --timing timing.json` → 通过。
- **成本口径实测**（按 inode 去重，不是多次 `du` 求和）：
  `archive-v0`（所有包的本体）**25.06 GiB**；`environments-v2` 124 个脚本环境对它的
  **独占增量 0.65 GiB**；共享 venv 对它的**独占增量 0.08 GiB**；三者并集 **25.79 GiB**。
  也就是说**包本体只存一份**，各环境靠硬链接共享  用户「Python 环境缓存应该是共用的」
  这个判断成立。推论：删那 124 个环境只释放 0.65 GiB（它们的独占增量），
  不是它们的表观 12.9 GiB。
- **启动成本实测**：新脚本（`scipy`+`matplotlib`）首次 `uv run` **14.5s**、
  再次 0.0s；同脚本 `hx-karaoke` **0.0s**。
- `node .agents/skills/hx-agent-notes/scripts/cli/verify-all.ts` → all gates passed。
