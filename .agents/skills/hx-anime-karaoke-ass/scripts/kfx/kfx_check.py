"""kfx check: gates every kfx output must pass before it is shown or published. Exit code 1 on any failure.

  python3 kfx_check.py out.kfx.ass --fonts DIR [--fps 2] [--only band|tags]

K1 tags  : only standard libass tags; no spinning (one \\t turning >= 90 deg), no flicker (alpha up/down >= 4 times in 1 s).
K2 band  : real render on black. The lyric box is the union of everything the lyric events (Name ly:*) light up over the
           song; every lit pixel of the whole file must sit inside that box grown by 5 % of the frame (96 px left/right,
           54 px up/down at 1080p).
           The user crops the lyric area when using the subtitle, so anything outside is cut off.
K3 names : every event is a lyric event (ly:Lnn) or an effect event (fx:Lnn or fx); nothing else (no wx / scene objects).
"""
import argparse, os, re, subprocess, sys, tempfile
import numpy as np

W, H = 1920, 1080
GROW_X, GROW_Y = 96, 54
LIT = 40          # grey level that counts as a drawn pixel
SLACK = 40        # lit pixels allowed outside the box per frame (blur fringe)
STD = set('b i u s bord xbord ybord shad xshad yshad be blur fn fs fscx fscy fsp fe frx fry frz fr fax fay c 1c 2c 3c 4c '
          'alpha 1a 2a 3a 4a an a k K kf ko q r pos move org fad fade clip iclip p pbo t'.split())
TAG = re.compile(r'\\(\d?[a-z]+)')


def events(path):
    out = []
    for raw in open(path, encoding='utf-8-sig'):
        if raw.startswith('Dialogue:'):
            f = raw.rstrip('\n').split(',', 9)
            out.append((f[4], f[9]))
    return out


def tag_names(text):
    names = []
    for blk in re.findall(r'\{([^}]*)\}', text):
        for m in TAG.finditer(blk):
            n = m.group(1)
            k = next((s for s in sorted(STD, key=len, reverse=True) if n.startswith(s)), None)
            names.append(k or n)
    return names


def k1(evs):
    bad = []
    for i, (name, text) in enumerate(evs):
        for n in set(tag_names(text)):
            if n not in STD:
                bad.append(f'K1 event {i} ({name}): non-standard tag \\{n}')
        base = 0.0
        m = re.search(r'\\frz?(-?[\d.]+)', text.split('\\t(')[0])
        if m:
            base = float(m.group(1))
        for t in re.findall(r'\\t\(([^()]*(?:\([^()]*\)[^()]*)*)\)', text):
            r = re.search(r'\\frz?(-?[\d.]+)', t)
            if r and abs(float(r.group(1)) - base) >= 90:
                bad.append(f'K1 event {i} ({name}): spins {abs(float(r.group(1)) - base):.0f} deg in one \\t')
        flips = re.findall(r'\\t\((-?\d+),(-?\d+),[^()]*?\\alpha&H([0-9A-Fa-f]{2})&', text)
        if len(flips) >= 4:
            seq = sorted((int(a), int(x, 16)) for a, _, x in flips)
            dirs = [1 if b[1] > a[1] else -1 for a, b in zip(seq, seq[1:]) if b[1] != a[1]]
            turns = sum(1 for a, b in zip(dirs, dirs[1:]) if a != b)
            if turns >= 3 and seq[-1][0] - seq[0][0] <= 1000:
                bad.append(f'K1 event {i} ({name}): alpha flickers {turns + 1} times within 1 s')
    return bad


def k3(evs):
    bad = [f'K3 event {i}: name {n!r} is not ly:Lnn / fx:Lnn / fx' for i, (n, _) in enumerate(evs)
           if not re.fullmatch(r'(ly|fx):L\d\d|fx', n)]
    return bad[:20]


def frames(ass, fonts, dur, fps):
    vf = f"ass={ass}:fontsdir={fonts},format=gray"
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=black:s={W}x{H}:r={fps}:d={dur}',
                          '-vf', vf, '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
    n = 0
    while True:
        b = p.stdout.read(W * H)
        if len(b) < W * H:
            break
        yield n / fps, np.frombuffer(b, np.uint8).reshape(H, W) > LIT
        n += 1
    p.wait()


def k2(path, fonts, fps):
    lines = open(path, encoding='utf-8-sig').read().split('\n')
    ly = [l for l in lines if not l.startswith('Dialogue:') or l.split(',', 9)[4].startswith('ly:')]
    end = max(ts(l.split(',', 9)[2]) for l in lines if l.startswith('Dialogue:'))
    lyp = os.path.join(tempfile.mkdtemp(), 'ly.ass')
    open(lyp, 'w', encoding='utf-8-sig').write('\n'.join(ly))
    x0 = y0 = 10 ** 6
    x1 = y1 = -1
    for _, b in frames(lyp, fonts, end + 0.5, fps):
        if b.any():
            ys, xs = np.nonzero(b)
            x0, y0, x1, y1 = min(x0, xs.min()), min(y0, ys.min()), max(x1, xs.max()), max(y1, ys.max())
    if x1 < 0:
        return ['K2: no lyric pixel rendered (fonts missing?)']
    print(f'K2 lyric box {x0},{y0}-{x1},{y1}; allowed {x0 - GROW_X},{y0 - GROW_Y}-{x1 + GROW_X},{y1 + GROW_Y}')
    X0, X1, Y0, Y1 = max(0, x0 - GROW_X), min(W, x1 + GROW_X + 1), max(0, y0 - GROW_Y), min(H, y1 + GROW_Y + 1)
    bad = []
    for t, a in frames(path, fonts, end + 0.5, fps):
        out = int(a.sum() - a[Y0:Y1, X0:X1].sum())
        if out > SLACK:
            ya, xa = np.nonzero(a)
            bad.append(f'K2 t={t:.1f}s: {out} px outside the allowed box (drawn {xa.min()},{ya.min()}-{xa.max()},{ya.max()})')
    return bad


def ts(s):
    h, m, x = s.split(':')
    return int(h) * 3600 + int(m) * 60 + float(x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ass')
    ap.add_argument('--fonts', required=True)
    ap.add_argument('--fps', type=float, default=2)
    ap.add_argument('--only', choices=['tags', 'band'])
    a = ap.parse_args()
    evs = events(a.ass)
    bad = []
    if a.only != 'band':
        bad += k1(evs) + k3(evs)
    if a.only != 'tags':
        bad += k2(a.ass, a.fonts, a.fps)
    for b in bad[:60]:
        print(b)
    print(f'{a.ass}: {len(evs)} events, {len(bad)} problems' + (' -> FAIL' if bad else ' -> PASS'))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
