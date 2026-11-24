# -*- coding: utf-8 -*-
"""具象素材的可读下限 (known-gaps #12 已定方向: 低于下限就换母题形式, 不是继续调参).

为什么不是自动阈值: 拿 オンリー 的三张抠图量过 (见 shared/calibration.md 的 #12 节): 轮廓 IoU 在 76~110px 仍 >0.99,
可读与否取决于视角和内部细节 (掌心侧视, 手指线条被双色调糊掉), 轮廓类指标没有区分能力 (10b). 所以下限由人看过后
写进素材配置, 代码只负责守住它:
  slot 字段 kind: "figurative" (具象: 手, 人, 道具) | "abstract" (光球, 纹样); 缺省 abstract.
  slot 字段 min_px: 成片短边下限 (px). 具象 slot 必须写.
"""


def below_floor(slot_cfg, w, h):
    """成片尺寸低于可读下限时返回原因 (调用方回退到另一种母题形式), 否则 None."""
    lim = slot_cfg.get("min_px")
    if lim is None:
        return None
    side = min(w, h)
    if side < float(lim):
        return "低于可读下限: 短边 %.0fpx < min_px %g (换母题形式, 不要继续缩)" % (side, float(lim))
    return None


def audit(slots):
    """静态体检素材配置: 具象 slot 没写 min_px 报 W. 返回 [(级别, slot, 说明)]."""
    out = []
    for name, s in sorted((slots or {}).items()):
        if not isinstance(s, dict) or not s.get("enabled", True):
            continue
        if s.get("kind") == "figurative" and s.get("min_px") is None:
            out.append(("W", name, "具象素材没写可读下限 min_px (人看过成片尺寸后填)"))
        if s.get("kind") is None and any(k in str(s.get("file", "")) for k in ("hand", "face", "body", "person")):
            out.append(("W", name, "文件名像具象素材但没标 kind (标 figurative 并写 min_px, 或标 abstract)"))
    return out
