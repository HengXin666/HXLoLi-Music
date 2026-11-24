# Agent Note: 卡拉OK setup_env 补齐 have_uv/HERE 导入, 修复 hx-karaoke 首次建环境

Status: implemented

Decision-ID: karaoke-setup-env-imports

- 决策依据: 用户 2026-11-20 报告: 本机没有 cache venv 时跑 `hx-karaoke`, `scripts/setup/setup_env.py` 第 157 行 `uv = have_uv()` 抛 `NameError: name 'have_uv' is not defined`, 默认入口坏.
- 相关: [karaoke-env-single-command](../process/2026-10-02-karaoke-env-single-command.md), [karaoke-scripts-grouping](../process/2026-10-05-karaoke-scripts-grouping.md)

## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/setup/setup_env.py`

## Problem

scripts 分组 (6246e0c) 把环境常量和工具函数移到 `setup/env.py`, 但 `setup_env.py` 的导入行没跟上. pyflakes 实查有三处未定义名:

- `setup_env.py`: `have_uv` (建环境第一步), `HERE` (`smoke()` 与 `install_command()`).
- `env.py`: `have_uv()` 里用了 `shutil`, 但没有 `import shutil`.

`--check` 分支在 `have_uv()` 之前返回, 所以体检不报错, 只有真正建环境时才炸. 已有 cache venv 的机器不走这条路, 所以一直没暴露.

## Decision

- `setup_env.py` 从 `setup.env` 导入 `HERE` 与 `have_uv`, 删掉没用的 `FONTS`, `installed`.
- `env.py` 补 `import shutil`.
- `setup_env.py` 在导入 `setup.env` 前把自己的 `scripts/` 放进 `sys.path`. `bin/hx-karaoke` 本来就设 PYTHONPATH, 但文件头写的用法是直接 `python3 .../setup_env.py`, 那时 `sys.path[0]` 是 `scripts/setup`, 必然 `ModuleNotFoundError: No module named 'setup'`. 文件头用法改成真实路径 `scripts/setup/setup_env.py`, 删掉过时的 `scripts/setup.py`.
- 不改建环境流程本身.

## Verification

- `pyflakes` 对两个文件: 无未定义名.
- 空白状态端到端: `HX_KARAOKE_STATE=<空目录> hx-karaoke <任一脚本>`, 自动建 venv, 装依赖, 拉字体, 自检, 接好命令, 再跑该脚本.
- 2026-11-20 复核 (当时用的 pvfx 生成器已于 2026-11-22 删除, 生成器现为 kfx) (技能目录副本, 全新 HX_KARAOKE_STATE 与 HOME): `bin/hx-karaoke kfx/pv_build.py --project dev/漆黑子弹/トコハナ` 退出码 0, 建 venv (py3.11) -> 装 15 项 -> 字体 7 个 -> smoke 169 模块依赖失败 0 -> 生成 33 句 5036 事件; 与已有环境直跑的产物逐字节一致. 不经入口直接 `python3 scripts/setup/setup_env.py --check` 也退出码 0. `hx-karaoke assfx/tests/test_pvfx.py` 输出 `pvfx selftest: OK`.
- 复核机器是 aarch64 Linux: demucs 4.1.0 依赖的 sphn 0.2.1 在 PyPI 只有 x86_64 / macOS arm64 / win 轮子, aarch64 Linux 要现场编 Rust; 复核时用 uv override 跳过 sphn. x86_64 Linux 有现成轮子, 不受影响.

## Alternatives considered

- 什么都不做 / 复用现有: 让人绕过入口用现成 venv. 否决: 用户明确要求默认入口能干净建环境.
- 在 `setup_env.py` 里再写一份 `have_uv`: 会和 `env.py` 的同名函数各自漂移. 否决, 单一来源留在 `env.py`.

## Consequences

- 默认入口 `hx-karaoke <脚本>` 在空状态下能自己建好环境; `have_uv` 只在 `env.py` 一处.
