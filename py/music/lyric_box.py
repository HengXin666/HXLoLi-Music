"""
歌词的固定展示范围

新版歌词 (kfx / assfx) 按 skill 的硬规则 5 与 6b, 全部内容都在一个固定矩形里: 字幕居中贴底,
特效不出歌词块外扩 5% 的 band. 这种歌词博客直接按常量矩形裁剪, 不需要 ffmpeg 逐帧扫描出的
动态时间轴 (assBoundsTimeline), 后者在前端插值会让悬浮窗里的字号跟着抖.

范围从哪来 (先到先用):
  1. [Script Info] 里 "; lyric-box: x0 y0 x1 y1" (生成器或验收台发布时写, 坐标按 PlayRes)
  2. "; assfx-band: <名字> x0 y0 x1 y1 t0 t1" (assfx 生成器每句登记的 band 和它的时间):
     按声明直接生成阶梯时间轴, 一句之内是常量, 不再逐帧扫描; 没写时间的按并集当常量
  3. 都没有, 但是 kfx 成品 (事件 Name 是 ly:* / fx:*): 返回 None, 由调用方用预扫描的全局并集当常量矩形
其余 (老的手工歌词) 照旧用动态时间轴.

输出与预扫描同一格式 (TwoBlockBounds, 1920x1080 画布), 只用下半块.
"""

import re
from pathlib import Path

from .config import PRESCAN_WIDTH, PRESCAN_HEIGHT

_BOX_RE = re.compile(r'^;\s*lyric-box:\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)')
_BAND_RE = re.compile(r'^;\s*assfx-band:\s*\S+\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)(?:\s+(-?[\d.]+)\s+(-?[\d.]+))?')
_RES_RE = re.compile(r'^PlayRes([XY]):\s*(\d+)')
KFX_SCAN_EVENTS = 400     # 判断 kfx 成品时最多看多少条事件


def _header(ass_path: Path) -> tuple[list[str], dict]:
    """[Script Info] 段的行, 以及 PlayResX/Y."""
    lines, res = [], {}
    with open(ass_path, encoding='utf-8-sig', errors='replace') as fh:
        for i, line in enumerate(fh):
            s = line.strip()
            if i > 0 and s.startswith('['):
                break
            lines.append(s)
            m = _RES_RE.match(s)
            if m:
                res[m.group(1)] = int(m.group(2))
    return lines, res


def _to_bounds(x0: float, y0: float, x1: float, y1: float, res: dict) -> dict:
    sx = PRESCAN_WIDTH / res.get('X', PRESCAN_WIDTH)
    sy = PRESCAN_HEIGHT / res.get('Y', PRESCAN_HEIGHT)
    L = max(0, int(round(min(x0, x1) * sx)))
    R = min(PRESCAN_WIDTH, int(round(max(x0, x1) * sx)))
    T = max(0, int(round(min(y0, y1) * sy)))
    B = min(PRESCAN_HEIGHT, int(round(max(y0, y1) * sy)))
    return {'topYMin': 0, 'topYMax': 0, 'btmYMin': T, 'btmYMax': B,
            'left': L, 'right': R, 'leftT': 0, 'rightT': 0, 'leftB': L, 'rightB': R}


def _union(bands: list[tuple]) -> tuple:
    return (min(min(b[0], b[2]) for b in bands), min(min(b[1], b[3]) for b in bands),
            max(max(b[0], b[2]) for b in bands), max(max(b[1], b[3]) for b in bands))


def _band_timeline(bands: list[tuple], res: dict) -> list[dict]:
    """
    每句的 band 按时间排成阶梯: 每个起止时刻前后各取一点, 一句之内是常量;
    几句同时在场 (交叠换句) 取它们的并集; 两句之间没有 band 时保持上一句, 不跳回全屏.
    """
    edges = sorted({t for b in bands for t in (b[4], b[5])})
    pts, last = [], None
    EPS = 0.01

    def at(t):
        act = [b for b in bands if b[4] <= t < b[5]]
        return _union(act) if act else None

    for t in edges:
        for tt in (max(0.0, t - EPS), t):
            box = at(tt) or last
            if box is None:
                continue
            last = box
            p = _to_bounds(*box, res)
            p['t'] = round(tt, 3)
            if not pts or pts[-1]['t'] < p['t']:
                pts.append(p)
    return pts


def declared_box(ass_path: Path) -> dict | None:
    """
    文件自己声明的范围; 没声明返回 None.
    返回 {'bounds': 常量矩形, 'timeline': 阶梯时间轴或 None, 'source': 来源说明}.
    """
    try:
        lines, res = _header(ass_path)
    except OSError:
        return None
    for s in lines:
        m = _BOX_RE.match(s)
        if m:
            return {'bounds': _to_bounds(*map(float, m.groups()), res), 'timeline': None, 'source': 'lyric-box'}
    bands = []
    for m in (_BAND_RE.match(s) for s in lines):
        if m:
            g = [float(v) if v is not None else None for v in m.groups()]
            bands.append(tuple(g))
    if not bands:
        return None
    union = _to_bounds(*_union(bands), res)
    timed = [b for b in bands if b[4] is not None and b[5] is not None and b[5] > b[4]]
    if len(timed) == len(bands):
        return {'bounds': union, 'timeline': _band_timeline(timed, res), 'source': f'assfx-band x{len(bands)}'}
    return {'bounds': union, 'timeline': None, 'source': f'assfx-band x{len(bands)} (无时间, 并集)'}


def is_kfx(ass_path: Path) -> bool:
    """kfx 成品: 事件 Name 字段是 ly:<句> / fx:<句> (kfx_build 的约定)."""
    n = 0
    try:
        with open(ass_path, encoding='utf-8-sig', errors='replace') as fh:
            for line in fh:
                if not line.startswith('Dialogue:'):
                    continue
                parts = line.split(',', 5)
                if len(parts) > 4 and parts[4].strip().startswith(('ly:', 'fx:')):
                    return True
                n += 1
                if n >= KFX_SCAN_EVENTS:
                    break
    except OSError:
        pass
    return False


def as_fixed(bounds: dict) -> dict:
    """预扫描的全局并集 -> 单块常量矩形 (上下两块合成一块, 与声明范围同形)."""
    blocks = [(bounds.get(k + 'YMin', 0), bounds.get(k + 'YMax', 0)) for k in ('top', 'btm')]
    blocks = [(a, b) for a, b in blocks if b > 0]
    if not blocks:
        return bounds
    L, R = bounds.get('left', 0), bounds.get('right', PRESCAN_WIDTH)
    T, B = min(a for a, _ in blocks), max(b for _, b in blocks)
    return {'topYMin': 0, 'topYMax': 0, 'btmYMin': T, 'btmYMax': B,
            'left': L, 'right': R, 'leftT': 0, 'rightT': 0, 'leftB': L, 'rightB': R}
