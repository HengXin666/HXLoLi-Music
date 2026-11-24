#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step contract check: the skeleton under steps/ must hold, not only read well.

Two modes:
  hx-karaoke check_steps.py                  # skeleton: every step contract is complete
  hx-karaoke check_steps.py --project proj   # progress: which step artifacts exist

Skeleton mode checks each steps/<group>/<key>/index.md:
  * the key is in SKILL.md, and in the group index.md when the group has one
  * headings: 只做这一件事 / 命令 / 产物 / 过关条件 (命令 may be a bash block)
  * every artifact in STEPS below is named in that index.md (doc and code pair)
  * every script after hx-karaoke resolves under scripts/
  * every "第 NN 步" points to an existing step key
Exit 1 when any check fails. Progress mode only reports; exit 0.
"""
import argparse
import glob
import os
import re
import sys

SKILL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# key -> (group, artifacts). An artifact is "a|b" (any one counts),
# a trailing "/" is a directory, a "*" is a glob, a leading "?" is optional.
# Mainline order follows SKILL.md and steps/5-verify/index.md (16 before 15).
STEPS = [
    ("00-env", "1-source", []),
    ("01-source", "1-source", ["base.mp4"]),
    ("02-lyrics", "2-lyrics", ["lyrics.txt", "lyrics.source.json"]),
    ("03-offset", "2-lyrics", ["offset.json"]),
    ("04-vocals", "2-lyrics", ["stems/vocals16k.wav", "stems/inst.wav", "stems/vocals.wav"]),
    ("05-align", "2-lyrics", ["timing_auto.json"]),
    ("06-kf-timing", "2-lyrics", ["?kf.json", "timing_kf.json", "review/kf-report.md"]),
    ("07-grid", "2-lyrics", ["grid.json", "timing_snap.json|timing_grid.json"]),
    ("08-review-timing", "2-lyrics", ["timing.json", "fixes.json", "review/health.txt",
                                      "review/coverage.txt"]),
    ("09-ruby", "2-lyrics", ["calib.json"]),
    ("10-anime-bg", "3-anime-bg", ["anime.background.json", "anime.notes.md",
                                   "anime.elements.md", "song-brief.md"]),
    ("11-design-bible", "3-anime-bg", ["bible/symbols.json", "bible/characters.json", "bible/scenes.json",
                                       "bible/lyric-map.json"]),
    ("39-directions", "4-kfx", ["bible/directions.json"]),
    ("40-music-events", "4-kfx", ["review/music-events.json"]),
    ("41-channels", "4-kfx", ["review/channels.md"]),
    ("42-text-main", "4-kfx", ["review/design-table.md"]),
    ("43-text-sub", "4-kfx", ["review/design-table.md"]),
    ("44-beat", "4-kfx", ["review/beat/"]),
    ("45-bg", "4-kfx", ["review/scene-timeline.json"]),
    ("46-image", "4-kfx", ["?assets/*.png"]),
    ("47-color", "4-kfx", ["?review/voices.json"]),
    ("48-thread", "4-kfx", ["review/design-table.md"]),
    ("49-generate", "4-kfx", ["out.ass", "out.manifest.json", "bible/landing.json"]),
    ("12-station", "5-verify", ["out.raw.ass", "out.raw.manifest.json", "review.jsonl",
                                "review/accept/"]),
    ("13-validate", "5-verify", ["validate.txt"]),
    ("14-inspect", "5-verify", ["review/*.jpg"]),
    ("16-blind-review", "5-verify", ["review/score.md", "review/score-blind.md"]),
    ("15-render", "5-verify", ["out.mkv|out.mp4"]),
]
# Side steps: not on the mainline, run only when their case applies.
SIDE = [("50-reverse", "4-kfx", ["reverse/"])]

HEADS = (("只做", "只做这一件事"), ("命令", "命令"), ("产物", "产物"), ("过关", "过关条件"))
NO_CMD = "本步无专用脚本"
SCRIPT_RE = re.compile(r"hx-karaoke\s+(?:scripts/)?([\w./-]+\.py)")
STEPREF_RE = re.compile(r"第 ?(\d{1,2})(?:[–-](\d{1,2}))?[a-z]? ?步")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def script_names():
    out = set()
    for p in glob.glob(os.path.join(SKILL, "scripts", "**", "*.py"), recursive=True):
        out.add(os.path.basename(p))
        out.add(os.path.relpath(p, os.path.join(SKILL, "scripts")))
    return out


def check_contract(key, group, arts, text, scripts, res):
    heads = " ".join(re.findall(r"^##+ (.*)$", text, re.M))
    for tag, word in HEADS:
        if tag in heads:
            continue
        if tag == "命令" and ("```bash" in text or NO_CMD in text):
            continue
        res.append((key, "缺一节: %s" % word))
    for art in arts:
        names = [a.lstrip("?") for a in art.split("|")]
        if not any(n in text for n in names):
            res.append((key, "产物没写进契约: %s" % art.lstrip("?")))
    for name in sorted(set(SCRIPT_RE.findall(text))):
        if name.startswith("proj/"):
            continue
        if name not in scripts and os.path.basename(name) not in scripts:
            res.append((key, "脚本不存在: %s" % name))


def check_steprefs(where, text, nums, res):
    for m in STEPREF_RE.finditer(text):
        if any(g and int(g) not in nums for g in m.groups()):
            res.append((where, "指向不存在的步骤: %s" % m.group(0)))


def skeleton():
    """Agent Notes
    .agents/notes/implemented/process/2026-11-16-karaoke-step-contract-check.md
    """
    res, scripts = [], script_names()
    every = STEPS + SIDE
    nums = {int(k[:2]) for k, _, _ in every}
    skill_md = read(os.path.join(SKILL, "SKILL.md"))
    on_disk = {os.path.basename(os.path.dirname(p)): p for p in
               glob.glob(os.path.join(SKILL, "steps", "*", "*", "index.md"))}
    for key, group, arts in every:
        path = os.path.join(SKILL, "steps", group, key, "index.md")
        if not os.path.exists(path):
            res.append((key, "契约文件不存在: steps/%s/%s/index.md" % (group, key)))
            continue
        text = read(path)
        check_contract(key, group, arts, text, scripts, res)
        if "`%s`" % key not in skill_md:
            res.append((key, "SKILL.md 的步骤表里没有这一步"))
        gidx = os.path.join(SKILL, "steps", group, "index.md")
        if os.path.exists(gidx) and "`%s`" % key not in read(gidx):
            res.append((key, "steps/%s/index.md 的子步骤表里没有这一步" % group))
    known = {k for k, _, _ in every}
    for key in sorted(set(on_disk) - known):
        res.append((key, "目录在, 但 check_steps.py 的 STEPS 里没有登记"))
    docs = glob.glob(os.path.join(SKILL, "steps", "**", "*.md"), recursive=True)
    docs += glob.glob(os.path.join(SKILL, "scripts", "**", "*.py"), recursive=True)
    docs += [os.path.join(SKILL, "SKILL.md")]
    for p in sorted(docs):
        check_steprefs(os.path.relpath(p, SKILL), read(p), nums, res)
    for where, why in res:
        print("FAIL %-22s %s" % (where, why))
    print("\n%s: %d 步 (主线 %d, 旁路 %d), %d 项失败"
          % ("FAILED" if res else "PASSED", len(every), len(STEPS), len(SIDE), len(res)))
    return 1 if res else 0


def present(proj, art):
    for name in art.lstrip("?").split("|"):
        p = os.path.join(proj, name)
        if "*" in name and glob.glob(p):
            return True
        if name.endswith("/") and os.path.isdir(p) and os.listdir(p):
            return True
        if not name.endswith("/") and "*" not in name and os.path.isfile(p):
            return True
    return False


def progress(proj):
    """Each step's artifacts are its state. Print done / missing per step."""
    nxt = None
    for key, group, arts in STEPS:
        need = [a for a in arts if not a.startswith("?")]
        miss = [a for a in need if not present(proj, a)]
        opt = [a.lstrip("?") for a in arts if a.startswith("?") and not present(proj, a)]
        if not arts:
            st = "----"
        else:
            st = "MISS" if miss else "DONE"
        if miss and nxt is None:
            nxt = key
        line = "%s %-18s" % (st, key)
        if miss:
            line += " 缺: " + ", ".join(miss)
        if opt:
            line += " (可选未见: %s)" % ", ".join(opt)
        print(line)
    print("\n下一步: %s" % (nxt or "主线产物齐全"))
    print("产物在不等于判据过. 判据用 check_gates.py 与各步过关条件里的命令.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="步骤契约体检 / 工程进度")
    ap.add_argument("--project", help="给出工程目录时, 只报每步产物在不在")
    a = ap.parse_args()
    if a.project:
        if not os.path.isdir(a.project):
            print("工程目录不存在: %s" % a.project, file=sys.stderr)
            return 2
        return progress(a.project)
    return skeleton()


if __name__ == "__main__":
    raise SystemExit(main())
