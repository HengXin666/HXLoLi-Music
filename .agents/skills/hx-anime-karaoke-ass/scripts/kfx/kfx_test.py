"""kfx self test. Run after ANY change to scripts/kfx/kfx_*.py:   python3 kfx_test.py [--full]

T1 golden : examples/mushoku_ed1/kfx (オンリー, the version the user approved = kfx3 v2.1) rebuilds byte-identical.
            A verb change that alters the golden is a visible change to an approved song: show it to the user first,
            and only after they approve run with --bless to store the new md5.
T2 tags   : the golden passes K1/K3 of kfx_check.py (--full also renders it for K2).
T3 design : the validator rejects what was rejected before (unknown 物象, unknown verb, banned 意境 words, untouched glyphs).
T4 gate   : kfx_check.py catches an effect drawn far outside the lyric box and a non-lyric event name.
T5 docs   : kfx_README.md lists every verb in VERBS.
"""
import hashlib, os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kfx_build as B

FIX = os.path.join(B.SKILL, 'examples', 'mushoku_ed1', 'kfx')
FONTS = os.path.join(B.SKILL, 'fonts')
GOLD = os.path.join(FIX, 'golden.md5')
fails = []


def ok(cond, what):
    print(('PASS ' if cond else 'FAIL ') + what)
    if not cond:
        fails.append(what)


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def main():
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, 'out.kfx.ass')
    B.build(FIX, os.path.join(FIX, 'design.md'), out, FONTS)
    if '--bless' in sys.argv:
        open(GOLD, 'w').write(md5(out) + '\n')
        print('blessed', md5(out))
    ok(md5(out) == open(GOLD).read().strip(), 'T1 golden rebuilds byte-identical')
    chk = [sys.executable, os.path.join(HERE, 'kfx_check.py'), out, '--fonts', FONTS]
    r = subprocess.run(chk + ([] if '--full' in sys.argv else ['--only', 'tags']), capture_output=True, text=True)
    ok(r.returncode == 0, 'T2 golden passes kfx_check' + ('' if r.returncode == 0 else ': ' + r.stdout[-400:]))

    base = open(os.path.join(FIX, 'design.md'), encoding='utf-8').read()
    cases = {'unknown 物象': base.replace('- 出场: 化', '- 物象: 细雪×16\n- 出场: 化', 1),
             'unknown verb': base.replace('{盖 心跳 起 亮}', '{盖 心跳 起 亮 环绕}', 1),
             'banned 意境 word': base.replace('- 意境: 老师的宽檐帽', '- 意境: 幕布落下, 老师的宽檐帽', 1),
             'untouched glyph': base.replace('[愛の]{盖 心跳 起 亮} ', '', 1)}
    for name, text in cases.items():
        ok(text != base, f'T3 case applies: {name}')
        errs = B.check_design(FIX, text, FONTS)[3]
        ok(bool(errs), f'T3 validator rejects {name}')

    import kfx_verbs as V
    doc = open(os.path.join(HERE, 'kfx_README.md'), encoding='utf-8').read().split('## 动作表')[1]
    miss = [k for k in V.VERBS if k not in doc]
    ok(not miss, 'T5 README verb table lists every verb' + (f': missing {miss}' if miss else ''))

    lines = open(out, encoding='utf-8-sig').read().split('\n')
    head = [l for l in lines if not l.startswith('Dialogue:')]
    l00 = [l for l in lines if l.startswith('Dialogue:') and l.split(',', 9)[4] == 'ly:L00']
    t0 = min(l.split(',', 9)[1] for l in l00)
    t1 = max(l.split(',', 9)[2] for l in l00)
    bad = [f'Dialogue: 9,{t0},{t1},FX,fx:L00,0,0,0,,{{\\an7\\pos(80,80)\\bord0\\1c&HFFFFFF&\\p1}}m 0 0 l 200 0 200 200 0 200{{\\p0}}',
           f'Dialogue: 9,{t0},{t1},FX,wx,0,0,0,,{{\\an7\\pos(900,900)\\p1}}m 0 0 l 10 0 10 10{{\\p0}}']
    syn = os.path.join(tmp, 'bad.ass')
    open(syn, 'w', encoding='utf-8-sig').write('\n'.join(head + l00 + bad) + '\n')
    r = subprocess.run([sys.executable, os.path.join(HERE, 'kfx_check.py'), syn, '--fonts', FONTS],
                       capture_output=True, text=True)
    ok(r.returncode == 1 and 'K2 t=' in r.stdout, 'T4 gate catches drawing outside the lyric box')
    ok('K3' in r.stdout and "'wx'" in r.stdout, 'T4 gate catches a non-lyric event name')
    print('ALL PASS' if not fails else f'{len(fails)} FAILED')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
