# -*- coding: utf-8 -*-
"""kfx_sync: 查字幕和人声/节拍对不对得上, 并按证据修.  (通用工具, 任何一首歌都能用)

为什么要有它: 用户的耳朵对 0.1 s 的慢很敏感 ("有一段都慢了 0.1~0.2 s"), 但说不出是哪一段.
不要问用户, 用人声分轨自己量: 每个 mora 的起点附近 (±win) 找人声频谱通量的峰, 峰相对记号的偏差就是这一下慢/快了多少.
单个 mora 噪声大, 所以按行取中位数, 再看连续几行是否同向偏 (= 用户说的 "一段").

  uv run kfx_sync.py lag  <工程>            # 报表: 每行偏差中位数, 标出连续偏慢/偏快的段
  uv run kfx_sync.py fix  <工程> [--thr 0.06] [--max 0.2]   # 只移 |中位数|>thr 的行, 整行平移, 最多 max 秒, 先备份 timing.json
  uv run kfx_sync.py beats <工程>           # 打印拍网格 (grid.json) 的前几拍, 给设计 "卡点" 用

约定: 工程目录有 stems/vocals16k.wav (人声分轨) 与 timing.json ([{line, s, e, ...}] 每个 mora 一条).
偏差 d = 人声峰时刻 - 记号时刻: d<0 = 记号比人声晚 (字慢了), d>0 = 记号早了.
"""

import json, os, shutil, sys, time, wave
import numpy as np


def _flux(P):
    w = wave.open(os.path.join(P, 'stems', 'vocals16k.wav'))
    sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float)
    if w.getnchannels() > 1:
        x = x.reshape(-1, w.getnchannels()).mean(1)
    hop, n = 160, 512
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * np.hanning(n)
    S = np.log1p(np.abs(np.fft.rfft(fr, axis=1)))
    fl = np.r_[0, np.maximum(0, np.diff(S, axis=0)).sum(1)]
    fl = fl - np.convolve(fl, np.ones(50) / 50, 'same')
    fl[fl < 0] = 0
    return fl, hop / sr


def line_lags(P, win=0.25):
    fl, dt = _flux(P)
    t = json.load(open(os.path.join(P, 'timing.json'), encoding='utf-8'))
    per = {}
    for m in t:
        i0, i1 = int((m['s'] - win) / dt), int((m['s'] + win) / dt)
        seg = fl[max(i0, 0):i1]
        if len(seg) and seg.max() > 0:
            per.setdefault(m['line'], []).append((max(i0, 0) + seg.argmax()) * dt - m['s'])
    first = {}
    for m in t:
        first.setdefault(m['line'], m['s'])
    return t, {l: (first[l], float(np.median(v)), len(v)) for l, v in per.items()}


def lag(P, thr=0.06):
    _, L = line_lags(P)
    run = []
    for l in sorted(L):
        s, d, n = L[l]
        tag = '慢' if d < -thr else ('快' if d > thr else '')
        print(f'L{l:02d} {s:7.2f}s  中位 {d:+.3f}  n={n:2d} {tag}')
        run.append(tag)
    i = 0
    while i < len(run):                       # 连续 >=2 行同向 = 一段
        j = i
        while j + 1 < len(run) and run[j + 1] == run[i] and run[i]:
            j += 1
        if run[i] and j > i:
            ks = sorted(L)
            print(f'段: L{ks[i]:02d}-L{ks[j]:02d} 都偏{run[i]}')
        i = j + 1
    return L


def fix(P, thr=0.06, mx=0.2):
    t, L = line_lags(P)
    shutil.copy(os.path.join(P, 'timing.json'), os.path.join(P, 'review', f'timing.presync.{int(time.time())}.json'))
    moved = {}
    for l, (s, d, n) in L.items():
        if abs(d) > thr and n >= 3:
            moved[l] = max(-mx, min(mx, d))
    for m in t:
        if m['line'] in moved:
            m['s'] = round(m['s'] + moved[m['line']], 3)
            m['e'] = round(m['e'] + moved[m['line']], 3)
    json.dump(t, open(os.path.join(P, 'timing.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for l in sorted(moved):
        print(f'L{l:02d} 移 {moved[l]:+.3f}s')
    return moved


def _inst_flux(P):
    w = wave.open(os.path.join(P, 'stems', 'inst.wav'))
    sr, ch = w.getframerate(), w.getnchannels()
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float)
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)
    hop, n = int(sr * 0.01), 2048
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * np.hanning(n)
    F = np.abs(np.fft.rfft(fr, axis=1))
    f = np.fft.rfftfreq(n, 1 / sr)
    allf = np.r_[0, np.maximum(0, np.diff(np.log1p(F), axis=0)).sum(1)]
    low = F[:, (f > 30) & (f < 150)].sum(1)
    low = np.r_[0, np.maximum(0, np.diff(np.log1p(low)))]
    return allf, low, 0.01, x.size / sr


def beats(P, b0=None, bt=None):
    """拍网格: 固定 bpm 的网格会漂 (本曲 100~140 s 漂到 +0.09 s, 特效就会 "不在点上"), 所以逐拍跟踪:
    预测 = 上一拍 + 周期, 在 ±60 ms 内找伴奏通量峰, 周期用最近 8 拍滑动平均. 小节头 = 低频 (底鼓) 最强的相位.
    写 beats.json: {"beats": [t...], "bar0": 小节头相位, "period": 周期}; kfx 的卡点动作 / 物象都读它."""
    allf, low, dt, dur = _inst_flux(P)
    if b0 is None:
        g = json.load(open(os.path.join(P, 'grid.json')))
        b0 = g['segments'][0][1]
        bt = g['period']

    def at(a, t, r=0.03):
        i = int(t / dt)
        k = int(r / dt)
        seg = a[max(i - k, 0):i + k + 1]
        return seg
    out = [b0]
    per = bt
    while out[-1] + per < dur - 0.2:
        pred = out[-1] + per
        seg = at(allf, pred, 0.06)
        i0 = max(int(pred / dt) - 6, 0)
        if len(seg) and seg.max() > np.percentile(allf, 75):
            t = (i0 + int(seg.argmax())) * dt
            t = pred + 0.5 * (t - pred)               # 半信半疑: 只往峰拉一半, 防被切分音拽走
        else:
            t = pred
        out.append(round(t, 3))
        if len(out) > 9:
            per = min(max((out[-1] - out[-9]) / 8, bt * 0.97), bt * 1.03)
    ph = [np.mean([at(low, out[k], 0.03).max() for k in range(p, len(out), 4)]) for p in range(4)]
    bar0 = int(np.argmax(ph))
    json.dump(dict(beats=out, bar0=bar0, period=bt, note='kfx_sync beats'), open(os.path.join(P, 'beats.json'), 'w'))
    print(f'{len(out)} 拍, 小节头相位 {bar0} (各相位底鼓 {np.round(ph, 2).tolist()}), 首拍 {out[0]}, 末拍 {out[-1]}')
    # 检查: 每 20 s 网格相对通量的最佳偏移, 应在 ±0.02 内
    for s in range(0, int(dur), 20):
        ks = [t for t in out if s <= t < s + 20]
        if ks:
            best = max(np.arange(-0.1, 0.101, 0.01), key=lambda o: sum(at(allf, t + o, 0.0).max() for t in ks))
            print(f'  {s:3d}s 偏移 {best:+.2f}')


if __name__ == '__main__':
    cmd, P = sys.argv[1], sys.argv[2]
    a = sys.argv[3:]
    thr = float(a[a.index('--thr') + 1]) if '--thr' in a else 0.06
    mx = float(a[a.index('--max') + 1]) if '--max' in a else 0.2
    {'lag': lambda: lag(P, thr), 'fix': lambda: fix(P, thr, mx), 'beats': lambda: beats(P)}[cmd]()
