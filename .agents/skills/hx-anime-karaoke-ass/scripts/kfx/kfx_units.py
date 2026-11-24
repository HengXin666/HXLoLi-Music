"""kfx_units: make timing.json's units match kfx's tokens (README 坑 12), for any song.

    python3 kfx_units.py <工程>            # report the lines whose units do not match, change nothing
    python3 kfx_units.py <工程> --write    # rewrite timing.json (backup timing.before-units.json first)

Why: kfx gives every TOKEN of lyrics.txt its own unit number (a small kana ュ ゃ ぁ is its own token, 「 」 and ? too),
and reads timing.json by (line, unit). An aligner that writes one unit per mora (きゅ, ちゃ, もぉ) or skips 「 shifts every
later glyph of the line onto its neighbour's time, and the last glyphs, left without time, fall onto the next line's
start (ろりこん 2026-11-24: モキュモキュにしてやるぞ lit one to two morae late and its やるぞ hung over the next line;
the user: "1 分 15 秒左右, 对齐有问题").
How: the line's morae, in order, are read as a stream of kana characters (a mora of two characters splits its window,
the small kana taking the last 40 %); tokens then take characters in order: a plain kana takes one, a ruby group takes
as many as its reading has, 「 」 ? ! 、 。 and spaces take none (they ride on the glyph before, as before)."""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kfx_lyrics as LM

SMALL = set('ぁぃぅぇぉゃゅょゎァィゥェォャュョヮ')
NOTIME = set(' \u3000「」『』?？!！、。…・')


def need(m):
    if m.group(1):
        return len(m.group(2).replace('.', '').replace('=', ''))
    if m.group(3):
        return len(m.group(4))
    return 0 if m.group(5) in NOTIME else 1


def remap(P):
    rows = LM.parse_rows(os.path.join(P, 'lyrics.txt'))
    T = json.load(open(os.path.join(P, 'timing.json'), encoding='utf-8'))
    out, bad = [], []
    for li, (_, jp, _) in enumerate(rows):
        ms = sorted([r for r in T if r['line'] == li], key=lambda r: (r['unit'], r['mora']))
        toks = list(LM.TOKEN.finditer(jp))
        stream = []
        for r in ms:
            tx = r['text']
            if len(tx) == 1:
                stream.append((r['s'], r['e'], tx))
                continue
            w = [0.4 if c in SMALL else 1.0 for c in tx]
            t, d = r['s'], r['e'] - r['s']
            for c, k in zip(tx, w):
                dt = d * k / sum(w)
                stream.append((round(t, 3), round(t + dt, 3), c))
                t += dt
        want = [need(m) for m in toks]
        if sum(want) != len(stream):
            bad.append(f'L{li:02d}: lyrics 要 {sum(want)} 个假名, timing 有 {len(stream)} 个, 没法自动对, 原样保留')
            out += ms
            continue
        i, new = 0, []
        for u, n in enumerate(want):
            for k in range(n):
                s, e, c = stream[i]
                new.append(dict(line=li, unit=u, mora=k, text=c, s=s, e=e))
                i += 1
        span = lambda rs: {u: (round(min(r['s'] for r in rs if r['unit'] == u), 2), round(max(r['e'] for r in rs if r['unit'] == u), 2))
                           for u in {r['unit'] for r in rs}}
        if span(new) != span(ms):
            bad.append(f'L{li:02d}: 重编号, 字和时间原来错位 ({len({r["unit"] for r in ms})} 个 unit -> {len(span(new))} 个有时间的记号)')
        out += new
    return out, bad


if __name__ == '__main__':
    P = sys.argv[1]
    out, bad = remap(P)
    print('\n'.join(bad) or '全部对得上')
    if '--write' in sys.argv and any('重编号' in b for b in bad):
        tp = os.path.join(P, 'timing.json')
        bk = os.path.join(P, 'timing.before-units.json')
        if not os.path.exists(bk):
            shutil.copy(tp, bk)
        json.dump(out, open(tp, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        print('写入', tp, '(备份', bk + ')')
