# -*- coding: utf-8 -*-
"""运行环境的位置与依赖清单 (从各脚本头部的 inline 依赖块汇总).

为什么单独一个模块: 环境位置(STATE/VENV)与依赖并集是**跨进程的契约** 
setup_env.py 用它们建环境, bin/hx-karaoke 与 --check 也按同一份清单判定齐全,
把它们写在建环境的主流程旁边, 会让"清单变了要重跑什么"埋在两百行命令行逻辑里.

环境必须落在仓库之外: skill 在仓库内, uv 的项目发现会一路向上找到仓库根的
pyproject.toml, 把 skill 内的 .venv 当成项目的 venv 并重新同步成仓库的 Python 与依赖
(实测: 建完立刻变成 py3.14 + 根项目依赖). 决策记录见

"""
from __future__ import annotations

import glob
import os
import re
import subprocess

# Agent Notes: 卡拉OK skill 的环境收敛为一条命令 + 仓库外的单一共享 venv
# 
# Agent Notes: 卡拉OK skill 的环境收敛为一条命令 + 仓库外的单一共享 venv
# .agents/notes/implemented/process/2026-10-02-karaoke-env-single-command.md
HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # <skill>
# Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
# 
# Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
# .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
SCRIPTS = os.path.join(HERE, "scripts")
FONTS = os.path.join(HERE, "fonts")

# 环境落在仓库之外  理由见文件头 (uv 项目发现会把 skill 内的 .venv 接管掉)
# 决策记录: 
CACHE_HOME = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
# HX_KARAOKE_STATE 可整块改掉环境位置 (换机器/做隔离验证用); PACKAGING 里也认这个变量。
STATE = os.environ.get("HX_KARAOKE_STATE") or os.path.join(CACHE_HOME, "hx-anime-karaoke-ass")
VENV = os.path.join(STATE, "venv")

# 手动附加项: 不在任何脚本 inline 块里、但运行期需要
#   torchaudio  demucs 的音频 IO; transformers>=5.18 是实测 align_ctc 跑通的版本
EXTRA = ["torchaudio", "transformers>=5.18,<6"]

# 依赖名 -> 校验时用的 import 名 (不一致的才要写)
# Agent Notes: hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开
# 
# Agent Notes: hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开
# .agents/notes/implemented/process/2026-10-05-karaoke-scripts-grouping.md
IMPORT_NAME = {"pillow": "PIL", "fonttools": "fontTools", "scikit-image": "skimage", "cairosvg": "cairosvg"}

_BLOCK = re.compile(r"# /// script\s*\n(.*?)# ///", re.S)
_DEPS = re.compile(r"dependencies\s*=\s*\[(.*?)\]", re.S)
_NAME_OK = re.compile(r"^[A-Za-z0-9_.\-]+$")
_REQ_SPLIT = re.compile(r"^\s*([A-Za-z0-9_.\-]+)")


def norm(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def script_deps() -> dict[str, list[str]]:
    """每个脚本声明的依赖 (只有真正能当包名用的才算, 过滤掉解析串进来的普通字符串)."""
    out: dict[str, list[str]] = {}
    for path in sorted(glob.glob(os.path.join(SCRIPTS, "**", "*.py"), recursive=True)):
        src = open(path, encoding="utf-8").read()
        m = _BLOCK.search(src)
        if not m:
            continue
        dm = _DEPS.search(m.group(1))
        if not dm:
            continue
        deps = [d for d in re.findall(r'"([^"]+)"', dm.group(1)) if _NAME_OK.match(d)]
        out[os.path.relpath(path, HERE)] = deps
    return out


def wanted() -> list[str]:
    """全部依赖 (去重、保序): 脚本并集 + EXTRA.

    去重按**基础包名**: 脚本里写 `transformers`, EXTRA 里写 `transformers>=5.18,<6`,
    它们是同一个包, 必须只留一条 (留 EXTRA 那条, 因为它带版本约束)。
    """
    seen: dict[str, str] = {}
    for deps in script_deps().values():
        for d in deps:
            seen.setdefault(norm(d), d)
    for d in EXTRA:
        seen[norm(_REQ_SPLIT.match(d).group(1))] = d      # EXTRA 覆盖脚本里的裸名
    return list(seen.values())


def req_file() -> str:
    return os.path.join(STATE, "requirements.txt")


def write_req(deps: list[str]) -> str:
    os.makedirs(STATE, exist_ok=True)
    p = req_file()
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("# 由 scripts/setup.py 从 scripts/**/*.py 的 inline 依赖块生成  不要手改\n")
        fh.write("# 改依赖请改脚本头部的 inline 块, 再重跑 setup.py\n")
        fh.write("\n".join(deps) + "\n")
    return p


def have_uv() -> str | None:
    return shutil.which("uv")


def run(cmd: list[str], **kw) -> int:
    print("  $ " + " ".join(cmd), flush=True)
    return subprocess.call(cmd, **kw)


def installed() -> set[str]:
    if not os.path.exists(os.path.join(VENV, "bin", "python")):
        return set()
    out = subprocess.run(
        [os.path.join(VENV, "bin", "python"), "-c",
         "import importlib.metadata as m;print('\\n'.join(sorted(d.metadata['Name'] or '' for d in m.distributions())))"],
        capture_output=True, text=True)
    if out.returncode != 0:
        return set()
    return {norm(x) for x in out.stdout.split()}


def missing(deps: list[str]) -> list[str]:
    have = installed()
    return [d for d in deps if norm(_REQ_SPLIT.match(d).group(1)) not in have]
