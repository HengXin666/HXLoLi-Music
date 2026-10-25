#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键建好本 skill 的运行环境 (venv + 依赖 + 字体 + 设备自检)。

为什么需要它  实测事实, 不是推测:

1. `uv run <脚本>` 会给每个**带 inline 依赖块**的脚本建一个**独立的脚本环境**
   (实测: a.py/b.py/c.py 三个依赖完全相同的脚本 -> 三个 environments-v2/a-*, b-*, c-*)。
   本 skill 有 27 个带 inline 块的脚本, 而且**每次新增/改动脚本, 它首次运行都要现场装包**:
   实测一个依赖 scipy+matplotlib 的新脚本 `uv run` 首次 **14.5s**、再次 0.0s;
   同一个脚本走 hx-karaoke (共享环境已含这两个包) 首次 **0.0s**。
   这就是"每次都靠 agent 判断环境"的来源。

   **别把这里的理由写成"省盘"**: uv 的包内容本来就靠硬链接共用。按 inode 实测,
   `environments-v2` 里 92.5% 的文件是硬链接, 124 个脚本环境对 `archive-v0` 的
   **独占增量合计只有 0.65 GiB**。用多次独立 `du` 求和会把硬链接重复计, 得到假的
   "12GB 重复"  这个错误数字曾经写在本文件里, 已按实测更正。

2. **不能在 skill 目录里建 `.venv`**  skill 在仓库内, uv 的项目发现会一路向上找到
   `HXLoLi-Music/pyproject.toml`, 把这个 `.venv` 当成**项目的** venv 并重新同步成
   仓库的 Python 与依赖 (实测: 建完立刻变成 py3.14 + 根项目依赖, 连 numpy 都被换掉)。
   所以环境必须落在仓库之外: 本脚本用 `~/.cache/hx-anime-karaoke-ass/venv`
   (与 skill 已有的 `~/.cache/hx-anime-karaoke-ass/svg` 缓存同级)。

设计: **一份依赖清单, 一个环境, 一个命令**。
  * 清单 = `scripts/**/*.py` 头部 inline 块里 dependencies 的**并集**, 由本脚本从源码提取,
    不是手抄。任何一个脚本声明了新依赖而不更新清单, 本脚本会直接报错。
  * 环境 = 上面那个 venv, 幂等: 已建好且依赖齐全就直接返回, 不重装。
  * 之后所有脚本一律用 `hx-karaoke <脚本> [参数...]` 跑 (见 bin/hx-karaoke)。
    `uv run` 仍可用 (实测它会把脚本目录放进 sys.path[0], 跨脚本 import 也通),
    只是新脚本首跑要等装包。

用法:
  uv run scripts/setup.py            # 需要 uv 在 PATH; 但本脚本只用标准库
  python3 scripts/setup.py           # 等价
  python3 scripts/setup.py --check   # 只体检不装 (缺什么报什么, 退出码非 0)
  python3 scripts/setup.py --recreate # 删掉重建
  python3 scripts/setup.py --no-fonts # 跳过字体下载 (52MB)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

from setup.env import FONTS, SCRIPTS, STATE, VENV, installed, missing, run, script_deps, wanted, write_req
from setup.fonts_check import check_fonts

def fetch_fonts() -> int:
    """字体复用已有的 fetch_fonts.py (它自己幂等: 已存在就跳过)."""
    vpy = os.path.join(VENV, "bin", "python")
    return run([vpy, os.path.join(SCRIPTS, "setup", "fetch_fonts.py")])


def smoke() -> int:
    """装完自检: 逐模块 import + 打印关键库版本 + 设备探测.

    import 冒烟期间几个入口脚本会往 stderr 打 argparse 用法 / ffmpeg 报错 
    那是 import 期副作用, 不是诊断信息。这里只回放 [smoke] / FAIL / skip 行, 其余丢弃。
    """
    vpy = os.path.join(VENV, "bin", "python")
    code = r"""
import importlib, os, sys

# 判定口径: 只把「依赖没装」当失败。
# 有几个脚本在 import 期就真的干活 (parity_cmp 读 sys.argv[1], shape_gallery 直接跑 ffmpeg,
# 其余入口脚本无参数时 argparse 退 2)  它们在 import 冒烟里报的错与依赖无关, 记为 skip。
FAIL_TYPES = (ModuleNotFoundError, ImportError)

here = sys.argv[1]
os.chdir(here); sys.path.insert(0, os.path.abspath('scripts'))

mods = []
for root, dirs, fs in os.walk('scripts'):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in sorted(fs):
        if f.endswith('.py'):
            mods.append(os.path.relpath(os.path.join(root, f), 'scripts')[:-3].replace('/', '.'))

bad, skipped = [], []
for mod in mods:
    try:
        importlib.import_module(mod)
    except FAIL_TYPES as e:
        bad.append((mod, type(e).__name__, str(e)[:80]))
    except BaseException as e:
        # SystemExit 也是 BaseException  只捕 Exception 会让 argparse 的入口脚本
        # 直接终止整个冒烟进程 (实测: 第一个入口脚本就把后面的模块全跳过了)。
        # 这类是 import 期副作用 (无参数时 exit / 读 sys.argv / 跑 ffmpeg), 记为 skip。
        skipped.append((mod, type(e).__name__))

print(f"[smoke] 模块 {len(mods)} 个: 依赖失败 {len(bad)}, import 期副作用跳过 {len(skipped)}")
for m, t, e in bad:
    print(f"  FAIL {m}: {t}: {e}")
for m, t in skipped:
    print(f"  skip {m}: {t}")

import numpy, scipy, torch, transformers
print(f"[smoke] numpy {numpy.__version__} / scipy {scipy.__version__} / torch {torch.__version__}"
      f" / transformers {transformers.__version__}")
from setup.device import pick_device, log_device       # scripts/ 已在 sys.path 上
log_device(pick_device(), 'setup 自检')
print("[smoke] OK" if not bad else "[smoke] 有依赖缺失")
sys.exit(1 if bad else 0)
"""
    p = subprocess.Popen([vpy, "-c", code, HERE], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert p.stdout is not None
    for line in p.stdout:
        if line.startswith(("[smoke]", "[device]", "  FAIL", "  skip")):
            sys.stdout.write(line)
    sys.stdout.flush()
    return p.wait()


def install_command() -> tuple[bool, str]:
    """把 bin/hx-karaoke 接到 PATH 上 (~/.local/bin)。返回 (是否可用, 说明)."""
    src = os.path.join(HERE, "bin", "hx-karaoke")
    if not os.path.exists(src):
        return False, f"缺少 {src}"
    os.chmod(src, 0o755)
    bindir = os.path.join(os.path.expanduser("~"), ".local", "bin")
    os.makedirs(bindir, exist_ok=True)
    dst = os.path.join(bindir, "hx-karaoke")
    if os.path.islink(dst) and os.path.realpath(dst) == os.path.realpath(src):
        pass                                     # 已接好
    elif os.path.exists(dst) and not os.path.islink(dst):
        return False, f"{dst} 已存在且不是符号链接, 不覆盖"
    else:
        if os.path.lexists(dst):
            os.remove(dst)
        os.symlink(src, dst)
    on_path = bindir in os.environ.get("PATH", "").split(os.pathsep)
    return on_path, (dst if on_path else f"{dst} (不在 PATH 上, 请把 {bindir} 加进 PATH)")


def main() -> int:
    ap = argparse.ArgumentParser(description="一键建好 hx-anime-karaoke-ass 的运行环境")
    ap.add_argument("--check", action="store_true", help="只体检, 不安装")
    ap.add_argument("--recreate", action="store_true", help="删掉 venv 重建")
    ap.add_argument("--no-fonts", action="store_true", help="跳过字体")
    ap.add_argument("--no-smoke", action="store_true", help="跳过装完自检")
    a = ap.parse_args()

    deps = wanted()
    print(f"[setup] 环境位置  {VENV}")
    print(f"[setup] 依赖清单  {len(deps)} 项 (从 {len(script_deps())} 个脚本的 inline 块汇总)")

    if a.check:
        miss = missing(deps)
        font_miss = check_fonts()
        print(f"[check] 缺依赖 {len(miss)}: {miss or '无'}")
        print(f"[check] 缺字体 {len(font_miss)}: {font_miss or '无'}")
        return 1 if (miss or font_miss) else 0

    uv = have_uv()
    if uv is None:
        print("[setup] 找不到 uv  请先装 uv (https://docs.astral.sh/uv/)", file=sys.stderr)
        return 2

    if a.recreate and os.path.exists(VENV):
        print("[setup] --recreate: 删除旧环境")
        shutil.rmtree(VENV, ignore_errors=True)

    fresh = not os.path.exists(os.path.join(VENV, "bin", "python"))
    if fresh:
        os.makedirs(STATE, exist_ok=True)
        # --no-project: 不让 uv 把仓库根的 pyproject.toml 当成这个环境的主人
        if run([uv, "venv", "--no-project", "--python", "3.11", VENV]) != 0:
            return 2
    else:
        print("[setup] 环境已存在, 跳过创建")

    req = write_req(deps)
    miss = missing(deps)
    if miss:
        print(f"[setup] 需要安装/补齐 {len(miss)} 项: {miss}")
        if run([uv, "pip", "install", "--python", os.path.join(VENV, "bin", "python"), "-r", req]) != 0:
            return 2
    else:
        print("[setup] 依赖已齐全, 跳过安装")

    if not a.no_fonts:
        font_miss = check_fonts()
        if font_miss:
            print(f"[setup] 补字体 {len(font_miss)} 个: {font_miss}")
            if fetch_fonts() != 0:
                print("[setup] 字体下载失败  后续 validate_ass 会判 FAIL", file=sys.stderr)
        else:
            print("[setup] 字体已齐全, 跳过下载")

    if not a.no_smoke:
        rc = smoke()
        if rc != 0:
            print("[setup] 自检未通过  上面的 FAIL 行就是原因", file=sys.stderr)
            return 1

    ok, where = install_command()
    print(f"[setup] 命令 hx-karaoke: {where}" + ("" if ok else "  <- 需要处理"))
    if not ok:
        return 1

    print(f"\n[setup] 就绪。跑脚本一律用:\n    hx-karaoke <脚本> [参数...]")
    print(f"    (即 {VENV}/bin/python; 不要再 uv run, 也不要另建 .venv)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
