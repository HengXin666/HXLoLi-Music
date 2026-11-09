# -*- coding: utf-8 -*-
"""issues.json: 用户在验收台上标的每一条. 格式见 steps/5-verify/12-station/impl/issues.md.

用户只指出哪里不对, 不描述需求. 动作:
  bad      不行 (可选诊断标签, 可选一句话)
  good     好 (冻结, 同时作为正面样本)
  another  换一个 (不说原因, 要一个不同构想)
  pick     选 A/B/C (agent 给了候选时)
  accept   收下 (对 agent 的修改结果)
  reject   再驳回
标签描述症状, 不是开药方. 每个标签有固定的根因层 (ROUTE), agent 先改上游产物再改代码.
"""
import json
import os
import time

ACTIONS = ("bad", "good", "another", "pick", "accept", "reject")
# 标签 -> (根因层, 先查/先改的产物, 做法)
ROUTE = {
    "看不清": ("生成", None, "同构想内调对比/尺寸/层序"),
    "太吵": ("剧本", "judge/arc.json", "降该句强度预算"),
    "太素": ("剧本", "judge/arc.json", "升该句强度预算, 可升为高光"),
    "和画面冲突": ("视频元素", "judge/shots.json", "复核该时段镜头表, 再改"),
    "和词义不搭": ("歌词视觉化", "judge/lines.visual.json", "重做该句分析, 再出新构想"),
    "时机早": ("生成", None, "对齐卡点或起音"),
    "时机晚": ("生成", None, "对齐卡点或起音"),
    "重复了": ("剧本", "judge/arc.json", "查手法重复, 换手法"),
    "出戏": ("风格表", "judge/style.json", "查风格表, 必要时修风格表"),
    "字错/音错": ("机械档", "fixes.json", "改 fixes.json 重跑机械档, 不进设计"),
}
NO_TAG = ("剧本", "judge/arc.json", "换锚点出 2 个新构想")
STATUS = ("open", "fixing", "proposed", "done", "need-human", "dropped")
MAX_AUTO = 2          # 每条最多自动改 2 次; 之后带候选回给用户


class Issues:
    def __init__(self, d):
        self.dir = d
        self.path = os.path.join(d, "issues.json")
        self.data = json.load(open(self.path, encoding="utf-8")) if os.path.exists(self.path) else \
            dict(format="accept-issues", version=1, items=[], seq=0)

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        tmp = self.path + ".tmp"
        json.dump(self.data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    @property
    def items(self):
        return self.data["items"]

    def get(self, iid):
        x = next((i for i in self.items if i["id"] == iid), None)
        if x is None:
            raise SystemExit("没有这条问题: %s" % iid)
        return x

    def cand_dir(self, iid):
        """候选与前后对比的 ASS: review/accept/cands/<问题 id>/<A|B|C|before>.ass (agent 写, 台子载入预览)."""
        return os.path.join(self.dir, "cands", iid)

    def add(self, sel, action, tag=None, say="", frame=None, choice=None, of=None):
        """sel 可以是一段选区, 也可以是多段的列表 (台子上的多段歌词). 多段时 sel = 第一段, sels = 全部."""
        sels = sel if isinstance(sel, list) else [sel]
        if not sels:
            raise SystemExit("选区是空的")
        sel = sels[0]
        if action not in ACTIONS:
            raise SystemExit("动作只能是 %s" % (ACTIONS,))
        if tag and tag not in ROUTE:
            raise SystemExit("标签只能是 %s (标签描述症状, 不写做法)" % "/".join(ROUTE))
        if tag and action != "bad":
            raise SystemExit("只有 bad 带诊断标签")
        if action == "pick" and not choice:
            raise SystemExit("pick 要给 --choice (A/B/C)")
        if action == "pick" and of and choice not in (self._last_cands(self.get(of)) or []):
            raise SystemExit("%s 没有候选 %s" % (of, choice))
        if action in ("accept", "reject", "pick") and not of:
            raise SystemExit("%s 是对某条问题的回应, 要给 --of <问题 id>" % action)
        self.data["seq"] += 1
        it = dict(id="I%d" % self.data["seq"], sel=sel, action=action, tag=tag, say=say, frame=frame,
                  choice=choice, of=of, status="done" if action == "good" else "open",
                  tries=0, history=[], at=time.strftime("%Y-%m-%d %H:%M:%S"))
        if len(sels) > 1:
            it["sels"] = sels
        if of:
            self._respond(self.get(of), it)
        self.items.append(it)
        self.save()
        return it

    def _respond(self, tgt, it):
        a = it["action"]
        if a == "accept":
            tgt["status"] = "done"
        elif a == "reject":
            tgt["status"] = "open"
        elif a == "pick":
            tgt["status"] = "fixing"
            tgt["picked"] = it["choice"]
        it["status"] = "done"

    def route(self, it):
        """(根因层, 产物, 做法). 换一个与无标签的不行都走剧本."""
        return ROUTE.get(it.get("tag")) or NO_TAG

    def resolve(self, iid, diag, change, status="proposed", candidates=None, fork=None, declared=None):
        """agent 回写: 诊断一句, 改了什么一句. status=proposed 等用户收下/驳回; 超次数自动转 need-human."""
        it = self.get(iid)
        if status not in STATUS:
            raise SystemExit("status 只能是 %s" % (STATUS,))
        if not diag or not change:
            raise SystemExit("resolve 要写 --diag (诊断一句) 与 --change (改了什么一句)")
        for c in candidates or []:
            if not os.path.exists(os.path.join(self.cand_dir(iid), c + ".ass")):
                raise SystemExit("候选 %s 没有文件 %s. 先把候选的 out 写到那里, 台子才能预览" %
                                 (c, os.path.relpath(os.path.join(self.cand_dir(iid), c + ".ass"), os.path.dirname(os.path.dirname(self.dir)))))
        it["tries"] += 1
        if status == "proposed" and it["tries"] > MAX_AUTO and not candidates:
            raise SystemExit("%s 已自动改过 %d 次: 带 --candidates 回给用户, 或标 need-human" % (iid, MAX_AUTO))
        it["status"] = status
        it["history"].append(dict(diag=diag, change=change, status=status, candidates=candidates, fork=fork,
                                  declared=declared, at=time.strftime("%Y-%m-%d %H:%M:%S")))
        self.save()
        return it

    @staticmethod
    def _last_cands(it):
        return next((h.get("candidates") for h in reversed(it.get("history") or []) if h.get("candidates")), None)

    def sels(self, it):
        return it.get("sels") or [it["sel"]]

    def merged(self):
        """同一标签在三处以上出现 (未关闭的): 按全局问题处理, 改风格表或剧本, 不逐句修."""
        n = {}
        for it in self.items:
            if it["status"] in ("open", "fixing") and it.get("tag"):
                n.setdefault(it["tag"], []).append(it["id"])
        return {t: ids for t, ids in n.items() if len(ids) >= 3}
