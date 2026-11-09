#!/usr/bin/env python3
"""FX 量下限门禁 (plan.md 4.1). 冻结口径: A 阶段结束后不得为过关修改.

用法:
  check_fx_profile.py <被测.ass> --ref <参考.ass> [--ratio 0.8] [--json]
  check_fx_profile.py <被测.ass> --ref-profile <参考画像.json>
  check_fx_profile.py <参考.ass> --dump-profile <输出.json>     # 只算画像
退出码: 0 = OK, 1 = BAD, 2 = 输入错误.

阈值不写死: 先对参考算画像, 再乘 ratio. 下面的 FLOOR/CAP 是定义的一部分.
"""
import argparse
import json
import math
import re
import statistics as st
import sys

STEP = 0.1          # 存活采样格 100ms
STEPPED_MAX = 0.15  # 逐帧步进: 时长 <= 0.15s
SKEL_LEN = 60       # 骨架签名取前 60 字符
COVER_FLOOR = 0.80  # 有 FX 时间占比: 至少 80%, 但不高于参考本身
PEAK_CAP = 3.0      # 峰值/中位: 下限 min(3, 参考*ratio)
# 上限项 (2026-11-09 新增, 未冻结): 只报 WARN, 不进结论. 下限挡不住"比参考重好几倍", 先跑出离参考多远再定阈值.
CAP_RATIO = 1.5     # 暂定: 每句中位 / 存活中位 不超过参考的 1.5 倍

LINE_KEY = re.compile(r'p\d+')
DRAW = re.compile(r'\\p[1-9]\}(.*?)(?:\{|$)')
NUM = re.compile(r'-?\d+(?:\.\d+)?')


# Agent Notes: 特效门禁 (FX 画像对照参考, 结果不到就改生成器, 尺子不动)
# .agents/notes/implemented/feature/2026-11-09-karaoke-fx-gate-studio.md
def ts(x):
    h, m, s = x.strip().split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse(text):
    """-> list of dict(layer,start,end,style,name,text,raw)."""
    ev = []
    for l in text.split('\n'):
        if not l.startswith('Dialogue:'):
            continue
        p = l[len('Dialogue:'):].strip().split(',', 9)
        if len(p) < 10:
            continue
        ev.append(dict(layer=int(p[0]), start=ts(p[1]), end=ts(p[2]), style=p[3].strip(),
                       name=p[4].strip(), text=p[9], raw=l))
    return ev


def load(path):
    with open(path, encoding='utf-8-sig') as f:
        return f.read()


def line_key(name):
    k = name.split(':')[-1]
    return k if LINE_KEY.fullmatch(k) else None


def profile(text):
    ev = parse(text)
    fx = [e for e in ev if e['style'] == 'FX']
    jp = [e for e in ev if e['style'] == 'JP']
    if not jp:
        raise ValueError('没有 JP 行, 无法定位演唱段与字层')

    # 3 每句
    keys = sorted({k for e in ev for k in [line_key(e['name'])] if k})
    per = {k: 0 for k in keys}
    for e in fx:
        k = line_key(e['name'])
        if k in per:
            per[k] += 1
    pv = list(per.values()) or [0]
    med = st.median(pv)

    # 4/5 存活
    t0 = min(e['start'] for e in jp)
    t1 = max(e['end'] for e in jp)
    n = max(1, int(round((t1 - t0) / STEP)))
    diff = [0] * (n + 1)
    for e in fx:
        a = max(0, math.ceil((e['start'] - t0) / STEP - 1e-9))
        b = min(n, math.ceil((e['end'] - t0) / STEP - 1e-9))  # [start,end) 内的采样点
        if b > a:
            diff[a] += 1
            diff[b] -= 1
    alive, c = [], 0
    for i in range(n):
        c += diff[i]
        alive.append(c)

    # 6 字前
    main_layer = st.mode([e['layer'] for e in jp])
    front = sum(1 for e in fx if e['layer'] > main_layer)

    # 9 骨架
    skel = set()
    for e in fx:
        for m in DRAW.finditer(e['text']):
            skel.add(NUM.sub('#', m.group(1))[:SKEL_LEN])

    jt = [e['text'] for e in jp]
    return dict(
        fx_count=len(fx),
        fx_bytes=sum(len(e['raw'].encode('utf-8')) for e in fx),
        lines=len(keys), line_min=min(pv), line_median=med, line_max=max(pv),
        line_zero=sum(1 for v in pv if v == 0), per_line=per,
        span=[round(t0, 3), round(t1, 3)],
        coverage=sum(1 for a in alive if a > 0) / len(alive),
        alive_median=st.median(alive),
        jp_main_layer=main_layer, front=front, front_ratio=front / len(fx) if fx else 0.0,
        stepped=sum(1 for e in fx if e['end'] - e['start'] <= STEPPED_MAX),
        peak_ratio=(max(pv) / med) if med else float('inf') if max(pv) else 0.0,
        skeletons=len(skel),
        jp_frz=sum(t.count('\\frz') for t in jt),
        jp_fax_frx=sum(t.count('\\fax') + t.count('\\frx') for t in jt),
        alive_curve=alive,
    )


def thresholds(ref, r):
    return dict(
        fx_count=ref['fx_count'] * r,
        fx_bytes=ref['fx_bytes'] * r,
        line_min=math.ceil(ref['line_min'] * r),
        line_median=ref['line_median'] * r,
        coverage=min(max(ref['coverage'] * r, COVER_FLOOR), ref['coverage']),
        alive_median=ref['alive_median'] * r,
        front_ratio=ref['front_ratio'] * r,
        stepped=ref['stepped'] * r,
        peak_ratio=min(PEAK_CAP, ref['peak_ratio'] * r),
        skeletons=math.floor(ref['skeletons'] * r),
        jp_frz=ref['jp_frz'] * r,
        jp_fax_frx=ref['jp_fax_frx'] * r,
    )


ITEMS = [  # (编号, 名称, 指标键们)
    (1, 'FX 条数', ['fx_count']),
    (2, 'FX 字节', ['fx_bytes']),
    (3, '每句 最少/中位', ['line_min', 'line_median']),
    (4, '有 FX 时间占比', ['coverage']),
    (5, '同时存活中位', ['alive_median']),
    (6, '字前 FX 占比', ['front_ratio']),
    (7, '逐帧步进', ['stepped']),
    (8, '峰值/中位', ['peak_ratio']),
    (9, '骨架种类', ['skeletons']),
    (10, 'JP \\frz / \\fax+\\frx', ['jp_frz', 'jp_fax_frx']),
]


CAP_ITEMS = [(11, '上限(未冻结) 每句中位/存活中位', ['line_median', 'alive_median'])]


def caps(p, ref, r=CAP_RATIO):
    res = []
    for no, label, ks in CAP_ITEMS:
        cap = {k: ref[k] * r for k in ks}
        state = 'OK' if all(p[k] <= cap[k] for k in ks) else 'WARN'
        res.append(dict(no=no, item=label, state=state, value={k: p[k] for k in ks}, cap=cap,
                        x_ref={k: (p[k] / ref[k]) if ref[k] else None for k in ks}))
    return res


def judge(p, th):
    res = []
    for no, label, ks in ITEMS:
        ok = all(p[k] >= th[k] for k in ks)
        state = 'OK' if ok else 'BAD'
        if no == 8 and p['line_median'] < th['line_median']:
            state = 'SKIP'  # 每句中位未达标时, 峰值/中位不计入 (中位过小比值失真)
        res.append(dict(no=no, item=label, state=state,
                        value={k: p[k] for k in ks}, floor={k: th[k] for k in ks}))
    return res


def fmt(v):
    if isinstance(v, float):
        return f'{v:.3f}' if v < 10 else f'{v:.1f}'
    return str(v)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('ass')
    ap.add_argument('--ref')
    ap.add_argument('--ref-profile')
    ap.add_argument('--ratio', type=float, default=0.8)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--dump-profile')
    a = ap.parse_args(argv)
    try:
        p = profile(load(a.ass))
        if a.dump_profile:
            with open(a.dump_profile, 'w', encoding='utf-8') as f:
                json.dump(p, f, ensure_ascii=False)
            print(f'profile -> {a.dump_profile}')
            return 0
        if a.ref:
            ref = profile(load(a.ref))
        elif a.ref_profile:
            with open(a.ref_profile, encoding='utf-8') as f:
                ref = json.load(f)
        else:
            print('需要 --ref 或 --ref-profile', file=sys.stderr)
            return 2
    except (OSError, ValueError) as e:
        print(f'输入错误: {e}', file=sys.stderr)
        return 2
    th = thresholds(ref, a.ratio)
    res = judge(p, th)
    bad = [r for r in res if r['state'] == 'BAD']
    verdict = 'BAD' if bad else 'OK'
    cres = caps(p, ref)
    if a.json:
        out = {k: v for k, v in p.items() if k not in ('alive_curve', 'per_line')}
        print(json.dumps(dict(verdict=verdict, bad=len(bad), ratio=a.ratio, items=res, caps=cres,
                              profile=out, per_line=p['per_line']), ensure_ascii=False, indent=1))
    else:
        print(f'check_fx_profile  ratio={a.ratio}  句数={p["lines"]}  0-FX 句={p["line_zero"]}')
        for r in res:
            v = ' / '.join(fmt(x) for x in r['value'].values())
            fl = ' / '.join(fmt(x) for x in r['floor'].values())
            print(f'  [{r["state"]:4}] {r["no"]:2}. {r["item"]:<18} {v:>18}   下限 {fl}')
        for r in cres:
            v = ' / '.join(fmt(x) for x in r['value'].values())
            cp = ' / '.join(fmt(x) for x in r['cap'].values())
            xr = ' / '.join(f'{x:.2f}x' for x in r['x_ref'].values() if x is not None)
            print(f'  [{r["state"]:4}] {r["no"]:2}. {r["item"]:<18} {v:>18}   上限 {cp}  (参考的 {xr}; 不进结论)')
        print(f'{verdict}  ({len(bad)} 项 BAD)')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
