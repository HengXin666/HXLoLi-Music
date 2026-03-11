"""
ASS 字幕预扫描模块

用 ffmpeg + libass 渲染 ASS 字幕, 扫描像素计算边界框 (bounding box),
生成时间轴 bounds 供前端裁剪显示
"""

import os
import subprocess
import tempfile
from pathlib import Path

from .config import (
    PRESCAN_WIDTH, PRESCAN_HEIGHT, PRESCAN_FPS,
    FONTS_DIR, STATIC_MUSIC_DIR,
)
from .cache import get_cache, set_cache
from .ass_parser import _extract_ass_fonts_impl


def _scan_frame_rgba(data: bytes, width: int, height: int) -> dict:
    """扫描单帧 RGBA 原始数据, 返回该帧的 TwoBlockBounds.

    上下分区: y < midLine 归上区块, y >= midLine 归下区块.
    像素 RGB 非黑 视为有内容 (ffmpeg 渲染在黑底上, alpha 恒为 255).

    每个区块有独立的 left/right, 避免不同位置的内容互相干扰裁剪窗口.
    同时保留全局 left/right 用于兼容.
    """
    mid_line = height >> 1
    step = 2  # 隔行扫描加速
    top_y_min = float('inf')
    top_y_max = 0
    btm_y_min = float('inf')
    btm_y_max = 0
    # 全局 left/right (兼容)
    left = float('inf')
    right = 0
    # top/btm 独立 left/right
    left_t = float('inf')
    right_t = 0
    left_b = float('inf')
    right_b = 0

    row_bytes = width * 4  # RGBA, 每像素4字节
    for y in range(0, height, step):
        row_start = y * row_bytes
        for x in range(0, width, step):
            px = row_start + x * 4
            # 检查 RGB 任一通道非零 (ffmpeg 黑底上的字幕)
            if data[px] > 0 or data[px + 1] > 0 or data[px + 2] > 0:
                if x < left:
                    left = x
                if x + step > right:
                    right = x + step
                if y < mid_line:
                    if y < top_y_min:
                        top_y_min = y
                    if y + step > top_y_max:
                        top_y_max = y + step
                    if x < left_t:
                        left_t = x
                    if x + step > right_t:
                        right_t = x + step
                else:
                    if y < btm_y_min:
                        btm_y_min = y
                    if y + step > btm_y_max:
                        btm_y_max = y + step
                    if x < left_b:
                        left_b = x
                    if x + step > right_b:
                        right_b = x + step

    # 裁剪到画布范围
    if right > width:
        right = width
    if right_t > width:
        right_t = width
    if right_b > width:
        right_b = width
    if top_y_max > height:
        top_y_max = height
    if btm_y_max > height:
        btm_y_max = height

    return {
        'topYMin': top_y_min if top_y_min != float('inf') else 0,
        'topYMax': top_y_max,
        'btmYMin': btm_y_min if btm_y_min != float('inf') else 0,
        'btmYMax': btm_y_max,
        'left': left if left != float('inf') else 0,
        'right': right,
        'leftT': left_t if left_t != float('inf') else 0,
        'rightT': right_t,
        'leftB': left_b if left_b != float('inf') else 0,
        'rightB': right_b,
    }


def _merge_bounds(a: dict, b: dict) -> dict:
    """合并两个 bounds (取并集)

    对于 top/btm 区域: 如果一方的 yMax==0 表示该方无此区域, 则使用另一方的值
    对于 left/right: 如果一方的 right==0 表示该方无内容, 则使用另一方的值
    """
    # top 区域
    a_has_top = a['topYMax'] > 0
    b_has_top = b['topYMax'] > 0
    if a_has_top and b_has_top:
        top_y_min = min(a['topYMin'], b['topYMin'])
        top_y_max = max(a['topYMax'], b['topYMax'])
    elif a_has_top:
        top_y_min, top_y_max = a['topYMin'], a['topYMax']
    elif b_has_top:
        top_y_min, top_y_max = b['topYMin'], b['topYMax']
    else:
        top_y_min, top_y_max = 0, 0

    # btm 区域
    a_has_btm = a['btmYMax'] > 0
    b_has_btm = b['btmYMax'] > 0
    if a_has_btm and b_has_btm:
        btm_y_min = min(a['btmYMin'], b['btmYMin'])
        btm_y_max = max(a['btmYMax'], b['btmYMax'])
    elif a_has_btm:
        btm_y_min, btm_y_max = a['btmYMin'], a['btmYMax']
    elif b_has_btm:
        btm_y_min, btm_y_max = b['btmYMin'], b['btmYMax']
    else:
        btm_y_min, btm_y_max = 0, 0

    # 全局左右 (兼容)
    a_has_lr = a['right'] > 0
    b_has_lr = b['right'] > 0
    if a_has_lr and b_has_lr:
        left = min(a['left'], b['left'])
        right = max(a['right'], b['right'])
    elif a_has_lr:
        left, right = a['left'], a['right']
    elif b_has_lr:
        left, right = b['left'], b['right']
    else:
        left, right = 0, 0

    # top 区域独立左右
    a_has_lr_t = a.get('rightT', 0) > 0
    b_has_lr_t = b.get('rightT', 0) > 0
    if a_has_lr_t and b_has_lr_t:
        left_t = min(a['leftT'], b['leftT'])
        right_t = max(a['rightT'], b['rightT'])
    elif a_has_lr_t:
        left_t, right_t = a['leftT'], a['rightT']
    elif b_has_lr_t:
        left_t, right_t = b['leftT'], b['rightT']
    else:
        left_t, right_t = 0, 0

    # btm 区域独立左右
    a_has_lr_b = a.get('rightB', 0) > 0
    b_has_lr_b = b.get('rightB', 0) > 0
    if a_has_lr_b and b_has_lr_b:
        left_b = min(a['leftB'], b['leftB'])
        right_b = max(a['rightB'], b['rightB'])
    elif a_has_lr_b:
        left_b, right_b = a['leftB'], a['rightB']
    elif b_has_lr_b:
        left_b, right_b = b['leftB'], b['rightB']
    else:
        left_b, right_b = 0, 0

    return {
        'topYMin': top_y_min, 'topYMax': top_y_max,
        'btmYMin': btm_y_min, 'btmYMax': btm_y_max,
        'left': left, 'right': right,
        'leftT': left_t, 'rightT': right_t,
        'leftB': left_b, 'rightB': right_b,
    }


def _smooth_bounds_timeline(
    frame_bounds: list[dict],
    fps: int = PRESCAN_FPS,
    window_sec: float = 2.0,
    ema_alpha: float = 0.15,
) -> list[dict]:
    """对逐帧 bounds 序列做 滑动窗口并集 + EMA 平滑, 生成稳定的时间轴 bounds

    核心理念:
    - 空帧 (无字幕内容) 不参与滑动窗口并集计算
    - EMA 只在有内容的区间段内平滑, 空帧区间保持空状态
    - 扩张 (bounds 变大) 立即响应, 收缩 (bounds 变小) 缓慢衰减
    - 双向 EMA 消除正向滞后

    Args:
        frame_bounds: 每帧的 bounds dict 列表 (包含空帧)
        fps: 采样帧率
        window_sec: 滑动窗口半径 (秒)
        ema_alpha: EMA 平滑系数, 越小越平滑

    Returns:
        平滑后的 bounds 时间序列, 每项含 't' 时间戳
    """
    n = len(frame_bounds)
    if n == 0:
        return []

    window_frames = int(window_sec * fps)
    EMPTY = {'topYMin': 0, 'topYMax': 0, 'btmYMin': 0, 'btmYMax': 0,
             'left': 0, 'right': 0, 'leftT': 0, 'rightT': 0, 'leftB': 0, 'rightB': 0}

    def has_content(b: dict) -> bool:
        return b['topYMax'] > 0 or b['btmYMax'] > 0 or b['right'] > 0

    # ---- 第 1 步: 滑动窗口并集 ----
    windowed = []
    for i in range(n):
        lo = max(0, i - window_frames)
        hi = min(n, i + window_frames + 1)
        merged = None
        for j in range(lo, hi):
            fb = frame_bounds[j]
            if not has_content(fb):
                continue
            if merged is None:
                merged = dict(fb)
            else:
                merged = _merge_bounds(merged, fb)
        windowed.append(merged if merged else dict(EMPTY))

    # ---- 第 2 步: 正向 EMA 平滑 ----
    smoothed = [dict(windowed[0])]
    for i in range(1, n):
        prev = smoothed[-1]
        cur = windowed[i]
        cur_has = has_content(cur)
        prev_has = has_content(prev)

        if not cur_has:
            smoothed.append(dict(EMPTY))
            continue

        if not prev_has:
            smoothed.append(dict(cur))
            continue

        # 两帧都有内容 → 分区域 EMA 平滑
        s = {}

        # top 区域
        cur_has_top = cur['topYMax'] > 0
        prev_has_top = prev['topYMax'] > 0
        if cur_has_top and prev_has_top:
            s['topYMin'] = cur['topYMin'] if cur['topYMin'] < prev['topYMin'] else int(prev['topYMin'] + ema_alpha * (cur['topYMin'] - prev['topYMin']))
            s['topYMax'] = cur['topYMax'] if cur['topYMax'] > prev['topYMax'] else int(prev['topYMax'] + ema_alpha * (cur['topYMax'] - prev['topYMax']))
        elif cur_has_top:
            s['topYMin'] = cur['topYMin']; s['topYMax'] = cur['topYMax']
        elif prev_has_top:
            s['topYMin'] = prev['topYMin']; s['topYMax'] = prev['topYMax']
        else:
            s['topYMin'] = 0; s['topYMax'] = 0

        # btm 区域
        cur_has_btm = cur['btmYMax'] > 0
        prev_has_btm = prev['btmYMax'] > 0
        if cur_has_btm and prev_has_btm:
            s['btmYMin'] = cur['btmYMin'] if cur['btmYMin'] < prev['btmYMin'] else int(prev['btmYMin'] + ema_alpha * (cur['btmYMin'] - prev['btmYMin']))
            s['btmYMax'] = cur['btmYMax'] if cur['btmYMax'] > prev['btmYMax'] else int(prev['btmYMax'] + ema_alpha * (cur['btmYMax'] - prev['btmYMax']))
        elif cur_has_btm:
            s['btmYMin'] = cur['btmYMin']; s['btmYMax'] = cur['btmYMax']
        elif prev_has_btm:
            s['btmYMin'] = prev['btmYMin']; s['btmYMax'] = prev['btmYMax']
        else:
            s['btmYMin'] = 0; s['btmYMax'] = 0

        # 全局左右
        s['left'] = cur['left'] if cur['left'] < prev['left'] else int(prev['left'] + ema_alpha * (cur['left'] - prev['left']))
        s['right'] = cur['right'] if cur['right'] > prev['right'] else int(prev['right'] + ema_alpha * (cur['right'] - prev['right']))

        # top 区域独立左右
        cur_has_lr_t = cur.get('rightT', 0) > 0
        prev_has_lr_t = prev.get('rightT', 0) > 0
        if cur_has_lr_t and prev_has_lr_t:
            s['leftT'] = cur['leftT'] if cur['leftT'] < prev['leftT'] else int(prev['leftT'] + ema_alpha * (cur['leftT'] - prev['leftT']))
            s['rightT'] = cur['rightT'] if cur['rightT'] > prev['rightT'] else int(prev['rightT'] + ema_alpha * (cur['rightT'] - prev['rightT']))
        elif cur_has_lr_t:
            s['leftT'] = cur['leftT']; s['rightT'] = cur['rightT']
        elif prev_has_lr_t:
            s['leftT'] = prev['leftT']; s['rightT'] = prev['rightT']
        else:
            s['leftT'] = 0; s['rightT'] = 0

        # btm 区域独立左右
        cur_has_lr_b = cur.get('rightB', 0) > 0
        prev_has_lr_b = prev.get('rightB', 0) > 0
        if cur_has_lr_b and prev_has_lr_b:
            s['leftB'] = cur['leftB'] if cur['leftB'] < prev['leftB'] else int(prev['leftB'] + ema_alpha * (cur['leftB'] - prev['leftB']))
            s['rightB'] = cur['rightB'] if cur['rightB'] > prev['rightB'] else int(prev['rightB'] + ema_alpha * (cur['rightB'] - prev['rightB']))
        elif cur_has_lr_b:
            s['leftB'] = cur['leftB']; s['rightB'] = cur['rightB']
        elif prev_has_lr_b:
            s['leftB'] = prev['leftB']; s['rightB'] = prev['rightB']
        else:
            s['leftB'] = 0; s['rightB'] = 0

        smoothed.append(s)

    # ---- 第 3 步: 反向 EMA 再平滑一遍 (消除正向 EMA 的滞后) ----
    for i in range(n - 2, -1, -1):
        nxt = smoothed[i + 1]
        cur = smoothed[i]
        nxt_has = has_content(nxt)
        cur_has = has_content(cur)

        if not cur_has or not nxt_has:
            continue

        # top 区域
        if cur['topYMax'] > 0 and nxt['topYMax'] > 0:
            if nxt['topYMin'] < cur['topYMin']:
                cur['topYMin'] = nxt['topYMin']
            else:
                cur['topYMin'] = int(cur['topYMin'] + ema_alpha * (nxt['topYMin'] - cur['topYMin']))
            if nxt['topYMax'] > cur['topYMax']:
                cur['topYMax'] = nxt['topYMax']
            else:
                cur['topYMax'] = int(cur['topYMax'] + ema_alpha * (nxt['topYMax'] - cur['topYMax']))

        # btm 区域
        if cur['btmYMax'] > 0 and nxt['btmYMax'] > 0:
            if nxt['btmYMin'] < cur['btmYMin']:
                cur['btmYMin'] = nxt['btmYMin']
            else:
                cur['btmYMin'] = int(cur['btmYMin'] + ema_alpha * (nxt['btmYMin'] - cur['btmYMin']))
            if nxt['btmYMax'] > cur['btmYMax']:
                cur['btmYMax'] = nxt['btmYMax']
            else:
                cur['btmYMax'] = int(cur['btmYMax'] + ema_alpha * (nxt['btmYMax'] - cur['btmYMax']))

        # 全局左右
        if nxt['left'] < cur['left']:
            cur['left'] = nxt['left']
        else:
            cur['left'] = int(cur['left'] + ema_alpha * (nxt['left'] - cur['left']))
        if nxt['right'] > cur['right']:
            cur['right'] = nxt['right']
        else:
            cur['right'] = int(cur['right'] + ema_alpha * (nxt['right'] - cur['right']))

        # top 独立左右
        if cur.get('rightT', 0) > 0 and nxt.get('rightT', 0) > 0:
            if nxt['leftT'] < cur['leftT']:
                cur['leftT'] = nxt['leftT']
            else:
                cur['leftT'] = int(cur['leftT'] + ema_alpha * (nxt['leftT'] - cur['leftT']))
            if nxt['rightT'] > cur['rightT']:
                cur['rightT'] = nxt['rightT']
            else:
                cur['rightT'] = int(cur['rightT'] + ema_alpha * (nxt['rightT'] - cur['rightT']))

        # btm 独立左右
        if cur.get('rightB', 0) > 0 and nxt.get('rightB', 0) > 0:
            if nxt['leftB'] < cur['leftB']:
                cur['leftB'] = nxt['leftB']
            else:
                cur['leftB'] = int(cur['leftB'] + ema_alpha * (nxt['leftB'] - cur['leftB']))
            if nxt['rightB'] > cur['rightB']:
                cur['rightB'] = nxt['rightB']
            else:
                cur['rightB'] = int(cur['rightB'] + ema_alpha * (nxt['rightB'] - cur['rightB']))

    # ---- 第 4 步: 构建带时间戳的输出, 并去重相邻相同项 ----
    timeline = []
    prev_entry = None
    for i, s in enumerate(smoothed):
        t = round(i / fps, 2)
        entry = {
            't': t,
            'topYMin': s['topYMin'], 'topYMax': s['topYMax'],
            'btmYMin': s['btmYMin'], 'btmYMax': s['btmYMax'],
            'left': s['left'], 'right': s['right'],
            'leftT': s.get('leftT', 0), 'rightT': s.get('rightT', 0),
            'leftB': s.get('leftB', 0), 'rightB': s.get('rightB', 0),
        }
        # 相邻相同则跳过 (减少 JSON 体积), 但保留首尾
        if prev_entry is not None and i < n - 1:
            same = all(
                entry[k] == prev_entry[k]
                for k in ('topYMin', 'topYMax', 'btmYMin', 'btmYMax', 'left', 'right',
                          'leftT', 'rightT', 'leftB', 'rightB')
            )
            if same:
                continue
        timeline.append(entry)
        prev_entry = entry

    return timeline


def _prescan_ass_bounds_impl(ass_path: Path, duration_sec: float) -> dict | None:
    """用 ffmpeg 渲染 ASS 字幕并扫描像素, 计算时间轴 bounds — 实际计算逻辑

    新方案 (滑动窗口 + EMA 平滑):
    - 固定 1920x1080 画布
    - 以 2fps 采样整首歌
    - 逐帧记录独立 bounds
    - 滑动窗口 (±2s) 取并集 + EMA 平滑
    - 输出时间序列 + 全局 bounds 兼容旧逻辑

    Args:
        ass_path: ASS 字幕文件路径
        duration_sec: 歌曲总时长 (秒)

    Returns:
        包含 'bounds' (全局) 和 'timeline' (时间序列) 的 dict, 无内容返回 None
    """
    if duration_sec <= 0:
        print(f"    └─ [预扫描] 时长为 0, 跳过")
        return None

    # 检查 ffmpeg 是否可用
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print(f"    └─ [预扫描] ffmpeg 不可用, 跳过")
        return None

    w, h = PRESCAN_WIDTH, PRESCAN_HEIGHT
    frame_size = w * h * 4  # RGBA 每帧字节数

    # 生成临时 fontconfig 配置, 将 ASS 中引用的字体映射到 CJK fallback 字体
    fonts_dir_str = str(FONTS_DIR).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    ass_fonts = _extract_ass_fonts_impl(ass_path)
    alias_entries = '\n'.join(
        f'  <alias><family>{fn}</family><accept><family>Noto Sans SC</family></accept></alias>'
        for fn in ass_fonts
    )
    fc_config = f"""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>{fonts_dir_str}</dir>
{alias_entries}
</fontconfig>
"""
    fc_tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False, encoding='utf-8')
    fc_tmp.write(fc_config)
    fc_tmp.close()
    fc_tmp_path = fc_tmp.name

    # ffmpeg 命令: 黑底 + ASS 字幕渲染, 输出 rawvideo RGBA
    ass_path_escaped = str(ass_path).replace('\\', '/').replace(':', '\\:').replace("'", "\\'")
    fonts_dir_escaped = str(FONTS_DIR).replace('\\', '/').replace(':', '\\:').replace("'", "\\'")
    cmd = [
        'ffmpeg',
        '-f', 'lavfi',
        '-i', f'color=c=black:s={w}x{h}:d={duration_sec:.2f}:r={PRESCAN_FPS}',
        '-vf', f"subtitles=filename='{ass_path_escaped}':fontsdir='{fonts_dir_escaped}'",
        '-f', 'rawvideo',
        '-pix_fmt', 'rgba',
        '-v', 'error',
        '-',
    ]

    # 设置 FONTCONFIG_FILE 环境变量
    env = os.environ.copy()
    env['FONTCONFIG_FILE'] = fc_tmp_path

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        )
    except Exception as e:
        print(f"    └─ [预扫描] ffmpeg 启动失败: {e}")
        return None

    # 逐帧记录 bounds
    frame_bounds: list[dict] = []
    global_bounds = {
        'topYMin': 0, 'topYMax': 0,
        'btmYMin': 0, 'btmYMax': 0,
        'left': 0, 'right': 0,
    }
    has_content = False

    try:
        while True:
            data = proc.stdout.read(frame_size)
            if len(data) < frame_size:
                break
            fb = _scan_frame_rgba(data, w, h)
            frame_bounds.append(fb)
            if fb['topYMax'] > 0 or fb['btmYMax'] > 0 or fb['right'] > 0:
                if not has_content:
                    global_bounds = dict(fb)
                    has_content = True
                else:
                    global_bounds = _merge_bounds(global_bounds, fb)
    finally:
        proc.stdout.close()
        proc.wait()

    stderr_output = proc.stderr.read().decode(errors='replace').strip()
    proc.stderr.close()
    if stderr_output:
        print(f"    └─ [预扫描] ffmpeg stderr: {stderr_output[:200]}")

    # 清理临时 fontconfig 文件
    try:
        os.unlink(fc_tmp_path)
    except OSError:
        pass

    frame_count = len(frame_bounds)
    if not has_content:
        print(f"    └─ [预扫描] {frame_count} 帧, 无字幕内容")
        return None

    # 生成平滑时间轴 bounds
    timeline = _smooth_bounds_timeline(frame_bounds, PRESCAN_FPS)

    print(f"    └─ [预扫描] {frame_count} 帧, 全局 bounds: "
          f"top=[{global_bounds['topYMin']},{global_bounds['topYMax']}] "
          f"btm=[{global_bounds['btmYMin']},{global_bounds['btmYMax']}] "
          f"lr=[{global_bounds['left']},{global_bounds['right']}]")
    print(f"    └─ [预扫描] 时间轴: {len(timeline)} 个关键点 "
          f"(从 {frame_count} 帧去重压缩)")

    return {
        'bounds': global_bounds,
        'timeline': timeline,
    }


def prescan_ass_bounds(ass_path: Path, duration_sec: float, ass_hash: str) -> dict | None:
    """预扫描 ASS 字幕边界框, 优先使用缓存

    缓存键包含 ASS 哈希和时长, 任一变更则重新计算
    """
    cache_key = str(ass_path.relative_to(STATIC_MUSIC_DIR))
    combined_hash = f"{ass_hash}:{duration_sec:.2f}"
    cached = get_cache('ass_bounds_v2', cache_key, combined_hash)
    if cached is not None:
        result = cached.get('result')
        if result:
            bounds = result.get('bounds', {})
            timeline_len = len(result.get('timeline', []))
            print(f"    └─ [预扫描] 使用缓存: "
                  f"top=[{bounds.get('topYMin',0)},{bounds.get('topYMax',0)}] "
                  f"btm=[{bounds.get('btmYMin',0)},{bounds.get('btmYMax',0)}] "
                  f"lr=[{bounds.get('left',0)},{bounds.get('right',0)}] "
                  f"timeline={timeline_len}点")
        else:
            print(f"    └─ [预扫描] 使用缓存: 无字幕内容")
        return result

    result = _prescan_ass_bounds_impl(ass_path, duration_sec)
    set_cache('ass_bounds_v2', cache_key, combined_hash, {'result': result})
    return result
