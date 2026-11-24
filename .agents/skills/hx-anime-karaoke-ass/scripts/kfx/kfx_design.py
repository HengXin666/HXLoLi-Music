"""kfx design.md parser + validator. Format and verb table: kfx_README.md."""
import re
from kfx_verbs import VERBS, ATMOS, EXITS, WEAK
PROPV = set()
FIELDS = ('色', '意境', '整行', '每字', '补丁', '出场', '为什么', '物象')
# the user's standing bans (2026-11-22): words that must not appear in a line's 意境, because the effect they name was rejected
BANNED = ('幕布', '火', '烧', '旋转', '环绕', '闪烁', '括号', '阴影', '穿字', '草', '石堆')

MIN_ACTS = 10      # per line: at least this many actions that touch words (亮/照/星/飘 do not count)
MIN_KINDS = 5      # ... of at least this many different verbs
MIN_PROPS = 0      # per line: at least this many actions done with a drawn thing from the show (杖 帽 水弹 岩弹 结 阵 信 刺 冻 落 护)

PATCH = re.compile(r"\[([^\]]+)\]\{([^}]*)\}")


def parse(text):
    d = dict(stance='', motifs='', globals={}, lines={}, errors=[])
    sec = None
    cur = None
    for raw in text.split('\n'):
        s = raw.rstrip()
        m = re.match(r'^##\s+L(\d+)\s*·\s*(.+)$', s)
        if m:
            cur = dict(no=int(m.group(1)), text=m.group(2).strip(), fields={}, patches=[], errors=[])
            d['lines'][cur['no']] = cur
            sec = 'line'
            continue
        m = re.match(r'^##\s+(.+)$', s)
        if m:
            sec = m.group(1).strip()
            cur = None
            continue
        if sec == 'line' and cur is not None:
            m = re.match(r'^-\s*([^:：]+)[:：]\s*(.*)$', s)
            if m:
                cur['fields'][m.group(1).strip()] = m.group(2).strip()
        elif sec == '立场':
            d['stance'] += s + '\n'
        elif sec == '意象':
            d['motifs'] += s + '\n'
        elif sec == '全局':
            m = re.match(r'^-\s*([^:：]+)[:：]\s*(.*)$', s)
            if m:
                d['globals'][m.group(1).strip()] = m.group(2).strip()
    for L in d['lines'].values():
        f = L['fields']
        for w, fx in PATCH.findall(f.get('补丁', '')):
            items = []
            for tok in fx.split():
                parts = tok.split('·')
                items.append((parts[0], parts[1:]))
            L['patches'].append(dict(text=w, fx=items))
    return d


def validate(d, lines):
    errs = []
    if len(d['stance'].strip()) < 40:
        errs.append('立场: 没写, 或太短 (要写谁在唱, 唱给谁, 出处)')
    if '|' not in d['motifs']:
        errs.append('意象: 缺意象表')
    # density floors are per song: a busy song (オンリー) wants many small moves per line; a telop song whose lyric is
    # the picture wants fewer, bigger ones so the words stay readable. 全局 每行最少动作 / 每行最少种类 lower them,
    # and the design must say why in 立场. Defaults = the floors the golden sample was made with.
    g = d.get('globals', {})
    min_acts = int(g.get('每行最少动作', MIN_ACTS).split()[0]) if isinstance(g.get('每行最少动作'), str) else MIN_ACTS
    min_kinds = int(g.get('每行最少种类', MIN_KINDS).split()[0]) if isinstance(g.get('每行最少种类'), str) else MIN_KINDS
    for L in lines:
        D = d['lines'].get(L.idx)
        if D is None:
            errs.append(f'L{L.idx:02d}: 设计稿里没有这一行')
            continue
        e = D['errors']
        want = L.text.replace(' ', '')
        if D['text'].replace(' ', '').replace('\u3000', '') != want:
            e.append(f'标题歌词和 lyrics 不一致: {D["text"]} != {want}')
        f = D['fields']
        for k in f:
            if k not in FIELDS:
                e.append(f'未知字段 {k} (只认 {" ".join(FIELDS)})')
        for w in BANNED:
            if w in f.get('意境', ''):
                e.append(f'意境 里有禁用的效果词 {w}')
        for k in ('色', '意境', '补丁', '出场', '为什么'):
            if not f.get(k):
                e.append(f'缺 {k}')
        if f.get('色') and not re.match(r'#[0-9A-Fa-f]{6}', f['色']):
            e.append('色 要以 #RRGGBB 开头')
        if f.get('出场') and f['出场'].split()[0] not in EXITS:
            e.append(f'出场 只能是 {"/".join(sorted(EXITS))}')
        cur = 0
        verbs_used = set()
        acts = 0
        touched = [False] * len(want)
        for p in D['patches']:
            pt = p['text'].replace(' ', '')
            q = want.find(pt, cur)
            if q < 0:
                e.append(f'补丁词 [{p["text"]}] 不在原文里 (或顺序不对)')
                continue
            p['at'] = q
            p['len'] = len(pt)
            cur = q + len(pt)
            for v, args in p['fx']:
                if v not in VERBS:
                    e.append(f'未知动作 {v}')
                verbs_used.add(v)
                if v not in WEAK:
                    acts += 1
                    for i in range(q, q + len(pt)):
                        touched[i] = True
        n = len(want)
        need = 3 if n >= 6 else (2 if n >= 4 else 1)
        if len(D['patches']) < need:
            e.append(f'词组太少: {len(D["patches"])} < {need}')
        if acts < min_acts:
            e.append(f'作用在字上的动作太少: {acts} < {min_acts} (至少, 不是正好)')
        if len(verbs_used - WEAK) < min_kinds:
            e.append(f'动作种类太少: {len(verbs_used - WEAK)} < {min_kinds}')
        blank = ''.join(ch for ch, t in zip(want, touched) if not t and ch not in '？?!！、。')
        if blank:
            e.append(f'这些字没有任何动作碰到 (不许留白): {blank}')
        nprop = sum(1 for p in D['patches'] for v, _ in p['fx'] if v in PROPV and v not in ('斩', '大斩'))
        if nprop < MIN_PROPS:
            e.append(f'番剧道具太少: {nprop} < {MIN_PROPS} (至少)')
        if '亮' not in verbs_used:
            e.append('没有 亮 (动词要高亮)')
        if verbs_used and verbs_used <= ATMOS | {'亮'}:
            e.append('只有氛围动作 (照/星/飘), 这一行没有 "我" 在做的事')
        if e:
            errs += [f'L{L.idx:02d}: {x}' for x in e]
    return errs
