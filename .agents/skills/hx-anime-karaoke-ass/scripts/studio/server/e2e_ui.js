/* 阶段 E 交互用例 (plan 3.5 / 3.6 / 3.7 的每一行操作). 由 e2e_ui.py 启动服务后调用:
 *   node e2e_ui.js <playwright 所在目录> <cfg.json>
 * 操作一律走真实鼠标/键盘; window.__hx 只用来读状态做断言.
 */
const fs = require('fs');
const { createRequire } = require('node:module');
const req = createRequire(process.argv[2] + '/x.js');
const { chromium } = req('playwright');
const cfg = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));

const results = [];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function assert(c, msg) { if (!c) throw new Error(msg); }
const near = (a, b, tol) => Math.abs(a - b) <= tol;

(async () => {
  const b = await chromium.launch({ executablePath: cfg.chrome, args: ['--no-sandbox', '--disable-dev-shm-usage', '--autoplay-policy=no-user-gesture-required'] });
  const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1, acceptDownloads: true });
  await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: cfg.url.replace(/\/$/, '') });
  const p = await ctx.newPage();
  // OC2/OC3 造崩溃用: 只记下页面里创建的 Worker (libass 的), 不改行为
  await p.addInitScript(() => { const W = window.Worker; window.__hxW = []; window.Worker = function (u, o) { const w = new W(u, o); window.__hxW.push(w); return w; }; window.Worker.prototype = W.prototype; });
  const errors = [];
  p.on('pageerror', (e) => errors.push(String(e).slice(0, 300)));
  await p.goto(cfg.url, { waitUntil: 'load' });
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 30000 });
  await p.waitForFunction(() => window.__hx.store.getState().octo === 'ready', null, { timeout: 40000 });
  await p.waitForFunction(() => window.__hx.store.getState().clips.length > 0 && window.__hx.store.getState().ref, null, { timeout: 30000 });
  await sleep(500);

  const st = (fn) => p.evaluate(fn);
  const S = (expr) => p.evaluate(`(() => { const s = window.__hx.store.getState(); return ${expr}; })()`);
  const T = () => p.evaluate(() => window.__hx.clock.t());
  const seek = (t) => p.evaluate((t) => window.__hx.clock.seek(t), t);
  const pause = () => p.evaluate(() => { window.__hx.clock.pause(); window.__hx.store.setState({ loop: null, stopAt: null }); });
  const reset = async () => {
    await p.keyboard.press('Escape').catch(() => {});
    // 上一条留下的浏览模式: 用真实点击胶囊退出 (跟用户一样), 不改内部状态
    const back = p.locator('[data-testid=back-to-current]');
    if (await back.isVisible().catch(() => false)) { await back.click(); await sleep(500); }
    await p.evaluate(() => {
      const h = window.__hx;
      h.clock.pause();
      h.clock.setRate(1);
      h.store.setState({ ranges: [], caret: null, anchor: null, menu: null, noteBox: null, loop: null, stopAt: null, rate: 1, inspector: false, compare: 'off', abShow: 'out', onlyUnits: null });
      const v = { ...h.store.getState().vis };
      for (const k of Object.keys(v)) v[k] = { eye: true, solo: false, lock: false };
      h.store.setState({ vis: v, trackH: {}, collapsed: { fx: false }, view: { v0: 0, v1: h.store.getState().duration } });
    });
    await sleep(120);
  };
  const g0 = (li) => S(`s.ix.start[${li}]`);
  const charBox = async (g) => (await p.locator(`[data-g="${g}"]`).boundingBox());
  // mouse.click 没有 modifiers 选项: 修饰键用 keyboard.down/up 真按住
  const clickChar = async (g, opts = {}) => {
    const { modifiers = [], ...o } = opts;
    const bb = await charBox(g);
    for (const m of modifiers) await p.keyboard.down(m);
    await p.mouse.click(bb.x + bb.width / 2, bb.y + bb.height * 0.7, o);
    for (const m of modifiers) await p.keyboard.up(m);
  };
  const showLine = async (li) => {
    const t = await S(`s.lines[${li}].t[0] + 0.05`);
    await seek(t);
    await sleep(700);
  };
  const reviewsCount = async () => (await (await p.request.get(cfg.url + 'api/review')).json()).items.length;
  const lastReview = async () => { const it = (await (await p.request.get(cfg.url + 'api/review')).json()).items; return it[it.length - 1]; };
  // 等服务端 review 条数到 n (最多 ms), 再稍等看有没有多写, 返回实际条数; 调用方用 === 判, 少写多写都红
  const waitReviewsCount = async (n, ms = 3000) => { const t0 = Date.now(); let c = await reviewsCount(); while (c < n && Date.now() - t0 < ms) { await sleep(100); c = await reviewsCount(); } await sleep(150); return reviewsCount(); };
  // 否定断言用: ms 窗口内每 step 取一次 fn(), 任何一次 !== want 立即返回 {ok:false}; 状态必须全程不变, 而不是固定 sleep 后某一刻碰巧不变
  const holdFor = async (fn, want, ms = 800, step = 50) => { const t0 = Date.now(); let n = 0; while (Date.now() - t0 < ms) { const v = await fn(); n++; if (v !== want) return { ok: false, v, at: Date.now() - t0 }; await sleep(step); } return { ok: true, n }; };
  const openMenuOnChar = async (g) => { const bb = await charBox(g); await p.mouse.click(bb.x + bb.width / 2, bb.y + bb.height * 0.7, { button: 'right' }); await p.waitForSelector('[data-testid=ctx-menu]'); };
  const item = (id) => p.locator(`[role=menuitem][data-id="${id}"]`);
  const rows = async () => Object.fromEntries((await p.getAttribute('[data-testid=timeline]', 'data-rows')).split(' ').map((x) => { const q = x.split(':'); const h = q.pop(), y = q.pop(); return [q.join(':'), { y: +y, h: +h }]; })); // 组行 id 本身带冒号 (g:fx)
  const laneXY = async (t, rowId) => {
    const lane = await p.locator('[data-hidpi=timeline-static]').boundingBox();
    const v = await S('s.view');
    const r = (await rows())[rowId];
    return { x: lane.x + ((t - v.v0) / (v.v1 - v.v0)) * lane.width, y: lane.y + r.y + r.h / 2 };
  };
  const counts = await p.evaluate(async () => {
    const t = await (await fetch('/api/ass/out')).text();
    const c = { all: 0, text: 0, fx: 0, card: 0, jp: 0, l7: 0 };
    const CARD = new Set(['CARD', 'CARDCN', 'TITLE', 'TLAT', 'PRO', 'PROCN']);
    for (const l of t.split(/\r?\n/)) {
      if (!l.startsWith('Dialogue:')) continue;
      c.all++;
      const q = l.slice(9).split(',', 5);
      const lay = parseInt(q[0], 10), sty = q[3].trim(), nm = q[4].trim();
      const card = CARD.has(sty) || (sty === 'FX' && (nm.startsWith('card:') || ['fx:title', 'fx:pro', 'fx:mid', 'fx:out'].includes(nm)));
      if (card) c.card++;
      else if (sty === 'FX') { c.fx++; if (lay === 7) c.l7++; }
      else if (['JP', 'RB', 'CN', 'LAT'].includes(sty)) { c.text++; if (sty === 'JP' || sty === 'LAT') c.jp++; }
    }
    return c;
  });
  const kept = async () => +(await p.getAttribute('[data-testid=monitor]', 'data-kept'));
  const waitKept = async (want) => { for (let i = 0; i < 40; i++) { if ((await kept()) === want) return want; await sleep(100); } return kept(); };

  async function test(id, row, fn) {
    if (cfg.only && cfg.only.length && !cfg.only.includes(id)) return;
    const t0 = Date.now();
    try { await reset(); await fn(); results.push({ id, row, ok: true, ms: Date.now() - t0 }); }
    catch (e) { results.push({ id, row, ok: false, err: String(e.message || e).slice(0, 300), ms: Date.now() - t0 }); }
  }
  const LI = 3; // p03 (If you do) なんだって怖くないから: 有振假名
  // ======================= 字体 (后备字体提示) =======================
  await test('FN1', '缺字体只提示 "字形可能不对": 顶栏 font-chip 与 /api/project.fonts_missing 一致 (空则不出现), 不影响 octo 状态', async () => {
    const pj = await (await p.request.get(cfg.url + 'api/project')).json();
    assert(Array.isArray(pj.fonts_missing) && Array.isArray(pj.fonts_unparsed), 'api/project 缺 fonts_missing / fonts_unparsed');
    const names = pj.fonts_missing.map((f) => f.name).join('|');
    const chip = p.locator('[data-testid=font-chip]');
    const n = await chip.count();
    if (!pj.fonts_missing.length && !pj.fonts_unparsed.length) assert(n === 0, '没缺字体却出了 font-chip');
    else {
      assert(n === 1, '缺字体但没有 font-chip: ' + names);
      assert((await chip.getAttribute('data-state')) === 'warn', 'font-chip 不是 warn');
      assert((await chip.getAttribute('data-missing')) === names, 'font-chip 名单和接口不一致');
    }
    const octo = await S('s.octo');
    assert(octo === 'ready', 'octo 应为 ready (缺字体不算失败), 实际 ' + octo);
    console.log('PROBE FN1 fonts_missing=' + JSON.stringify(pj.fonts_missing) + ' unparsed=' + JSON.stringify(pj.fonts_unparsed));
  });

  const L2 = 4;

  // ======================= 3.5 显示 =======================
  await test('U9', '轨高: FX 组默认折叠 (组行 18-20px, 写明 9 层); 点开后 9 条 FX 原高 26px, 时间线总高与监视器画面都不变, 放不下就在时间线内纵向滚动 (自绘细条), 页面零滚动条', async () => {
    const tlh = () => p.evaluate(() => document.querySelector('[data-testid=timeline]').clientHeight);
    const vid = () => p.evaluate(() => { const b = document.querySelector('[data-testid=monitor] video').getBoundingClientRect(); return `${Math.round(b.width)}x${Math.round(b.height)}`; });
    const fxrows = async () => (await p.getAttribute('[data-testid=timeline]', 'data-fxrows')).split(' ').filter(Boolean).map((x) => +x.split(':')[1]);
    const fxwin = async () => { const a = await p.getAttribute('[data-testid=timeline]', 'data-fxwin'); if (!a) return null; const [y, h, content, scroll] = a.split(':').map(Number); return { y, h, content, scroll }; };
    // 默认态在全新页面里看 (主页面已被 reset 展开过)
    const c2 = await b.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
    const p2 = await c2.newPage();
    await p2.goto(cfg.url, { waitUntil: 'load' });
    await p2.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 30000 });
    const d0 = await p2.getAttribute('[data-testid=timeline]', 'data-rows');
    await c2.close();
    const g = /(?:^| )g:fx:\d+:(\d+)/.exec(d0);
    assert(g && !/(^| )fx0:/.test(d0) && +g[1] >= 18 && +g[1] <= 20, '新页面默认没折叠 FX 或组行不是 18-20px: ' + d0);
    if (!(await rows())['g:fx']) { await p.click('[data-testid=group-fx]'); await sleep(300); }
    const pill = await p.textContent('[data-testid=group-pill-fx]');
    assert(pill.includes('FX 0-8 (9 层, 字后→字前)'), 'pill: ' + pill);
    const h0 = await tlh(), v0 = await vid();
    await p.click('[data-testid=group-pill-fx]');
    await sleep(300);
    const fx = await fxrows();
    assert(fx.length === 9 && fx.every((h) => h === 26), 'FX 高 ' + fx);
    const h1 = await tlh(), v1 = await vid();
    assert(h1 === h0 && v1 === v0, `展开改变了时间线/画面: 时间线 ${h0}->${h1} 画面 ${v0}->${v1}`);
    assert(await p.evaluate(() => document.documentElement.scrollHeight === innerHeight && document.documentElement.scrollWidth === innerWidth), '展开后出页面滚动条');
    const w = await fxwin();
    assert(w && w.content === 234, 'FX 窗口 ' + JSON.stringify(w));
    if (w.content > w.h) {
      assert(await p.locator('[data-testid=fx-vbar]').count() === 1, '放不下但没有滚动条');
      const hb = await p.locator('[data-testid=fx-win-heads]').boundingBox();
      await p.mouse.move(hb.x + 40, hb.y + hb.height / 2);
      await p.mouse.wheel(0, 200);
      await sleep(200);
      const w2 = await fxwin();
      assert(w2.scroll === w.content - w.h, `轨头列滚轮没滚到底 ${JSON.stringify(w2)}`);
      assert(await p.evaluate(() => document.documentElement.scrollHeight === innerHeight), '滚动后出页面滚动条');
      await p.mouse.wheel(0, -400);
      await sleep(200);
      assert((await fxwin()).scroll === 0, '滚不回顶');
    }
    await p.click('[data-testid=group-fx]');
    await sleep(300);
    assert((await rows())['g:fx'] && (await tlh()) === h0 && (await vid()) === v0, '再折叠后时间线/画面变了');
    await p.click('[data-testid=group-pill-fx]'); // 后面的用例要 FX 展开
    await sleep(300);
  });
  await test('D1', '3.5 每句: 行号 | JP 带振假名 | CN', async () => {
    const n = await S('s.lines.length');
    assert(await p.locator('[data-testid=lineno]').count() === n, '行号数 != 句数');
    const rt = await p.locator('[data-testid=lyrics] rt').count();
    const want = await S('s.lines.reduce((a, l) => a + l.chars.filter((c) => c.ruby).length, 0)');
    assert(rt === want && rt > 0, `ruby ${rt} != ${want}`);
    const ruby = await p.locator(`[data-i="${LI}"] rt`).first().textContent();
    assert(ruby === 'こわ', `L03 振假名 ${ruby}`);
    const cn = await p.locator(`[data-i="${LI}"] [class*=cn]`).first().textContent();
    assert(cn && cn.length > 2, 'CN 缺');
  });
  await test('D2', '3.5 句右侧徽标: 角色 / FX 条数 / 迷你密度条 (out 对参考)', async () => {
    const n = await S('s.lines.length');
    assert(await p.locator('[data-testid=lyrics] svg[aria-label^="out"]').count() === n, '迷你密度条数');
    const role = await p.locator(`[data-i="${LI}"] [class*=role]`).textContent();
    assert(['高光', '承载', '留白'].includes(role), `角色 ${role}`);
    const fx = await p.locator(`[data-i="${LI}"] [class*=fx]`).first().textContent();
    assert(fx === `FX ${await S(`s.lines[${LI}].fx`)}`, `FX 徽标 ${fx}`);
  });
  await test('D3', '3.5 当前句放大居中, 其它句降透明度', async () => {
    await showLine(LI);
    const r = await p.evaluate((li) => {
      const cur = document.querySelector(`[data-i="${li}"]`), oth = document.querySelector(`[data-i="${li + 2}"]`);
      const f = (e) => parseFloat(getComputedStyle(e.querySelector('[class*=jp]')).fontSize);
      return { cur: !!cur.dataset.cur, fc: f(cur), fo: f(oth), oc: +getComputedStyle(cur).opacity, oo: +getComputedStyle(oth).opacity, align: getComputedStyle(cur.querySelector('[class*=texts]')).textAlign };
    }, LI);
    assert(r.cur && r.fc > r.fo * 1.2 && r.oc === 1 && r.oo < 0.5 && r.align === 'center', JSON.stringify(r));
  });
  await test('D4', '3.5 逐字填色按 timing 的字时间走', async () => {
    const g = (await g0(LI)) + 6; // 怖
    const c = await S(`s.lines[${LI}].chars[6]`);
    await seek(c.s + (c.e - c.s) * 0.5);
    await sleep(300);
    const v = await p.evaluate((g) => {
      const q = (x) => document.querySelector(`[data-g="${x}"]`).style.getPropertyValue('--p');
      return [q(g - 1), q(g), q(g + 1)].map(Number);
    }, g);
    assert(v[0] === 1 && near(v[1], 0.5, 0.12) && v[2] === 0, `--p ${v}`);
  });
  await test('D5', '3.5 冻结(好)的字下划绿线, 有问题的字下划橙线 (review 数据)', async () => {
    const line = await S(`s.lines[${LI}].line`);
    const post = (kind, from, to) => p.request.post(cfg.url + 'api/review', { data: { sel: [{ line, from, to }], t0: 1, t1: 2, kind, tags: [] } });
    await post('good', 1, 2);
    await post('bad', 4, 5);
    const g = await g0(LI);
    await p.waitForFunction((g) => document.querySelector(`[data-g="${g + 1}"]`).dataset.rv === 'good' && document.querySelector(`[data-g="${g + 4}"]`).dataset.rv === 'bad', g, { timeout: 5000 });
    const sh = await p.evaluate((g) => [g + 1, g + 4].map((x) => getComputedStyle(document.querySelector(`[data-g="${x}"]`)).boxShadow), g);
    assert(sh[0].includes('89, 195, 138') && sh[1].includes('240, 162, 74'), `下划线颜色 ${sh}`);
  });

  // ======================= 3.5 跟随与浏览 =======================
  const centerRatio = () => p.evaluate(() => {
    const s = window.__hx.store.getState();
    const vp = document.querySelector('[data-testid=lyrics]').getBoundingClientRect();
    const el = document.querySelector(`[data-i="${s.curLine}"]`).getBoundingClientRect();
    return (el.top + el.height / 2 - vp.top) / vp.height;
  });
  await test('F1', '3.5 播放时自动滚动, 当前句平滑停在 40% 高度 (transform, 非 scrollTop)', async () => {
    await showLine(10);
    const r = await centerRatio();
    const m = await p.evaluate(() => { const v = document.querySelector('[data-testid=lyrics]'); const i = document.querySelector('[data-testid=lyrics-inner]'); return { st: v.scrollTop, tf: getComputedStyle(i).transform, tr: i.style.transition }; });
    assert(near(r, 0.4, 0.03) && m.st === 0 && m.tf !== 'none' && m.tr.includes('transform'), `ratio ${r.toFixed(3)} ${JSON.stringify(m)}`);
  });
  await test('F2', '3.5 滚轮进入浏览模式: 停止跟随, 浮出 "回到当前句" 胶囊', async () => {
    await showLine(5);
    const bb = await p.locator('[data-testid=lyrics]').boundingBox();
    await p.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
    await p.mouse.wheel(0, 300);
    await sleep(200);
    assert(await p.getAttribute('[data-testid=lyrics]', 'data-mode') === 'browse', '没进浏览');
    assert(await p.locator('[data-testid=back-to-current]').isVisible(), '无胶囊');
    const tf0 = await p.evaluate(() => document.querySelector('[data-testid=lyrics-inner]').style.transform);
    const cur0 = await S('s.curLine');
    await seek(await S('s.lines[12].t[0] + 0.05'));
    // 正向: seek 确实把当前句换掉了 (跟随模式下这一步会让 transform 变), 否则下面的 "不变" 不说明任何事
    await p.waitForFunction((c0) => window.__hx.store.getState().curLine !== c0, cur0, { timeout: 2000 });
    const h = await holdFor(() => p.evaluate(() => document.querySelector('[data-testid=lyrics-inner]').style.transform), tf0, 900);
    assert(h.ok, `浏览模式下仍在跟随: ${tf0} -> ${h.v} @${h.at}ms`);
  });
  await test('F3', '3.5 点胶囊恢复跟随', async () => {
    const bb = await p.locator('[data-testid=lyrics]').boundingBox();
    await p.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
    await p.mouse.wheel(0, 400);
    await seek(await S('s.lines[14].t[0] + 0.05'));
    await sleep(150);
    await p.click('[data-testid=back-to-current]');
    await sleep(700);
    assert(await p.getAttribute('[data-testid=lyrics]', 'data-mode') === 'follow', '没恢复');
    const r = await centerRatio();
    assert(near(r, 0.4, 0.03), `ratio ${r}`);
  });
  await test('F4', '3.5 浏览模式 3s 无操作自动恢复跟随', async () => {
    await showLine(6);
    const bb = await p.locator('[data-testid=lyrics]').boundingBox();
    await p.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
    await p.mouse.wheel(0, 300);
    await sleep(2500);
    assert(await p.getAttribute('[data-testid=lyrics]', 'data-mode') === 'browse', '提前恢复');
    await sleep(900);
    assert(await p.getAttribute('[data-testid=lyrics]', 'data-mode') === 'follow', '3s 后没恢复');
  });
  await test('F5', '3.5 拖动进入浏览模式', async () => {
    await showLine(6);
    const bb = await p.locator('[data-testid=lyrics]').boundingBox();
    const x = bb.x + bb.width - 6; // 右侧徽标外的空白
    await p.mouse.move(x, bb.y + bb.height * 0.7);
    await p.mouse.down();
    await p.mouse.move(x, bb.y + bb.height * 0.4, { steps: 6 });
    await p.mouse.up();
    assert(await p.getAttribute('[data-testid=lyrics]', 'data-mode') === 'browse', '拖动没进浏览');
  });
  await test('F6', '3.5 浏览模式下悬停某句, 时间线同步高亮该句时段 (不跳播放头)', async () => {
    await showLine(6);
    const bb = await p.locator('[data-testid=lyrics]').boundingBox();
    await p.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
    await p.mouse.wheel(0, 120);
    await sleep(100);
    const t0 = await T();
    const lb = await p.locator('[data-i="9"]').boundingBox();
    assert(lb && lb.y > bb.y && lb.y < bb.y + bb.height, '第 9 句不在视野');
    await p.mouse.move(lb.x + 4, lb.y + lb.height / 2);
    await sleep(150);
    assert(await p.getAttribute('[data-testid=timeline]', 'data-hover-line') === '9', 'data-hover-line');
    assert(near(await T(), t0, 0.01), '播放头动了');
  });

  // ======================= 3.5 选字 =======================
  await test('S1', '3.5 单击字: 放光标并 seek 到该字起音', async () => {
    await showLine(LI);
    const g = (await g0(LI)) + 7;
    await clickChar(g);
    const c = await S(`s.lines[${LI}].chars[7].s`);
    assert(await S('s.caret') === g && (await S('s.ranges.length')) === 0, '光标/选区');
    assert(near(await T(), c, 0.02), `seek ${await T()} != ${c}`);
    assert(await p.locator(`[data-g="${g}"][data-caret]`).count() === 1, '无光标标记');
  });
  await test('S2', '3.5 拖动选连续若干字, 可跨句', async () => {
    await showLine(LI);
    const a = (await g0(LI)) + 8, bg = (await g0(L2)) + 2;
    const A = await charBox(a), B = await charBox(bg);
    await p.mouse.move(A.x + A.width / 2, A.y + A.height * 0.7);
    await p.mouse.down();
    await p.mouse.move(B.x + B.width / 2, B.y + B.height * 0.7, { steps: 8 });
    await p.mouse.up();
    const r = await S('s.ranges');
    assert(r.length === 1 && r[0][0] === a && r[0][1] === bg, `ranges ${JSON.stringify(r)}`);
    await sleep(300);
    assert(/L03-L04/.test(await p.textContent('[data-testid=status-sel]')), '状态栏跨句');
  });
  await test('S3', '3.5 Shift+单击: 从光标扩展到该字', async () => {
    await showLine(LI);
    const g = await g0(LI);
    await clickChar(g + 2);
    await clickChar(g + 9, { modifiers: ['Shift'] });
    const r = await S('s.ranges');
    assert(r.length === 1 && r[0][0] === g + 2 && r[0][1] === g + 9, JSON.stringify(r));
  });
  await test('S4', '3.5 Ctrl/Cmd+拖动: 追加一段 (多段选区)', async () => {
    await showLine(LI);
    const g = await g0(LI);
    const drag = async (a, z, mods) => {
      const A = await charBox(a), Z = await charBox(z);
      for (const m of mods) await p.keyboard.down(m);
      await p.mouse.move(A.x + A.width / 2, A.y + A.height * 0.7);
      await p.mouse.down();
      await p.mouse.move(Z.x + Z.width / 2, Z.y + Z.height * 0.7, { steps: 5 });
      await p.mouse.up();
      for (const m of mods) await p.keyboard.up(m);
    };
    await drag(g + 1, g + 3, []);
    await drag(g + 7, g + 9, ['Control']);
    const r = await S('s.ranges');
    assert(r.length === 2 && r[0][0] === g + 1 && r[0][1] === g + 3 && r[1][0] === g + 7 && r[1][1] === g + 9, JSON.stringify(r));
  });
  await test('S5', '3.5 双击: 选该词 (timing 的 unit)', async () => {
    // 找第一个含多字词 (相邻字同 unit) 的句; オンリー 里 p03 每个 unit 只有一个字, 所以不能写死 LI
    const info = await S(`(() => { for (let li = 0; li < s.lines.length; li++) { const ch = s.lines[li].chars; for (let i = 1; i < ch.length; i++) { if (ch[i].unit != null && ch[i-1].unit === ch[i].unit) { const u = ch[i].unit; let a = i, b = i; while (a > 0 && ch[a-1].unit === u) a--; while (b < ch.length-1 && ch[b+1].unit === u) b++; return { li, i, a, b }; } } } return null; })()`);
    assert(info, '没有多字词');
    await showLine(info.li);
    const g = await g0(info.li);
    await clickChar(g + info.i, { clickCount: 2 });
    const r = await S('s.ranges');
    assert(r.length === 1 && r[0][0] === g + info.a && r[0][1] === g + info.b, `${JSON.stringify(r)} want ${g + info.a}-${g + info.b}`);
  });
  await test('S6', '3.5 单击行号: 选整句', async () => {
    await showLine(LI);
    await p.locator(`[data-i="${LI}"] [data-testid=lineno]`).click();
    const g = await g0(LI), n = await S(`s.lines[${LI}].chars.length`);
    const r = await S('s.ranges');
    assert(r.length === 1 && r[0][0] === g && r[0][1] === g + n - 1, JSON.stringify(r));
  });
  await test('S7', '3.5 三击: 选整句', async () => {
    await showLine(LI);
    const g = await g0(LI), n = await S(`s.lines[${LI}].chars.length`);
    await clickChar(g + 5, { clickCount: 3 });
    const r = await S('s.ranges');
    assert(r.length === 1 && r[0][0] === g && r[0][1] === g + n - 1, JSON.stringify(r));
  });
  await test('S8', '3.5 左右键 / Shift+左右: 光标按字移动 / 扩展', async () => {
    await showLine(LI);
    const g = await g0(LI);
    await clickChar(g + 3);
    await p.keyboard.press('ArrowRight');
    assert(await S('s.caret') === g + 4, '右移');
    await p.keyboard.press('ArrowLeft');
    await p.keyboard.press('ArrowLeft');
    assert(await S('s.caret') === g + 2, '左移');
    await p.keyboard.press('Shift+ArrowRight');
    await p.keyboard.press('Shift+ArrowRight');
    await p.keyboard.press('Shift+ArrowRight');
    const r = await S('s.ranges');
    assert(r.length === 1 && r[0][0] === g + 2 && r[0][1] === g + 5, JSON.stringify(r));
    await p.keyboard.press('Shift+ArrowLeft');
    const r2 = await S('s.ranges');
    assert(r2[0][1] === g + 4, 'Shift+左收缩');
  });
  await test('S9', '3.5 上下键: 换句', async () => {
    await showLine(LI);
    const g = await g0(LI);
    await clickChar(g + 2);
    await p.keyboard.press('ArrowDown');
    const c = await S('s.caret');
    assert(c === (await g0(L2)) + 2, `下 ${c}`);
    await p.keyboard.press('ArrowUp');
    assert(await S('s.caret') === g + 2, '上');
  });
  await test('S10', '3.5 Esc: 清选区', async () => {
    await showLine(LI);
    await p.locator(`[data-i="${LI}"] [data-testid=lineno]`).click();
    assert((await S('s.ranges.length')) === 1, '先有选区');
    await p.keyboard.press('Escape');
    assert((await S('s.ranges.length')) === 0, 'Esc 后仍有选区');
  });
  await test('S11', '3.5 选区联动: 时间线高亮对应时段与涉及轨道', async () => {
    await showLine(LI);
    const g = await g0(LI);
    await clickChar(g + 6);
    await clickChar(g + 8, { modifiers: ['Shift'] });
    await p.waitForFunction(() => document.querySelector('[data-testid=timeline]').dataset.sel, null, { timeout: 3000 });
    const sel = JSON.parse(await p.getAttribute('[data-testid=timeline]', 'data-sel'));
    const c6 = await S(`s.lines[${LI}].chars[6].s`), c8 = await S(`s.lines[${LI}].chars[8].e`);
    assert(near(sel[0][0], c6, 0.002) && near(sel[0][1], c8, 0.002), `时段 ${sel[0]}`);
    assert(sel[0][2].includes('jp') && sel[0][2].some((k) => k.startsWith('fx')), `涉及轨 ${sel[0][2]}`);
    // 动态画布在选区中点, 涉及的 jp 轨上有蓝色高亮
    const { x, y } = await laneXY((c6 + c8) / 2, 'jp');
    const px = await p.evaluate(({ x, y }) => {
      const c = document.querySelector('[data-hidpi=timeline-dynamic]');
      const r = c.getBoundingClientRect();
      const d = c.getContext('2d').getImageData(Math.round((x - r.left) * devicePixelRatio), Math.round((y - r.top) * devicePixelRatio), 1, 1).data;
      return [...d];
    }, { x, y });
    assert(px[2] > 100 && px[3] > 50, `像素 ${px}`);
  });
  await test('S12', '3.5 选区联动: 监视器画所选字的字框和该句 band 框', async () => {
    await showLine(LI);
    const g = await g0(LI);
    await clickChar(g + 6);
    await clickChar(g + 8, { modifiers: ['Shift'] });
    assert(await p.locator('[data-testid=sel-ink]').count() === 3, '字框数');
    assert(await p.locator('[data-testid=sel-band]').count() === 1, 'band 框数');
    const ink = await p.locator('[data-testid=sel-ink]').first().boundingBox();
    const fr = await p.locator('[data-testid=frame-out]').boundingBox();
    assert(ink.x > fr.x && ink.x < fr.x + fr.width && ink.y > fr.y + fr.height * 0.6, '字框位置');
  });
  await test('S13', '3.5 选区联动: 状态栏 "3 字 L03 t0-t1s, 涉及 FX n / JP n"', async () => {
    await showLine(LI);
    const g = await g0(LI);
    await clickChar(g + 6);
    await clickChar(g + 8, { modifiers: ['Shift'] });
    await p.waitForFunction(() => /涉及 FX/.test(document.querySelector('[data-testid=status-sel]')?.textContent || ''), null, { timeout: 3000 });
    const t = await p.textContent('[data-testid=status-sel]');
    assert(/^3 字 L03 \d+\.\d\d-\d+\.\d\ds, 涉及 FX \d+ \/ JP \d+$/.test(t), t);
  });

  // ======================= 3.6 右键菜单 =======================
  await test('M1', '3.6 入口 1: 歌词选区右键, 顶部灰字是选区摘要', async () => {
    await showLine(LI);
    const g = await g0(LI);
    await clickChar(g + 6);
    await clickChar(g + 8, { modifiers: ['Shift'] });
    await openMenuOnChar(g + 7);
    const h = await p.textContent('[data-testid=ctx-header]');
    assert(/^3 字 · L03 怖くな · \d+\.\d\d-\d+\.\d\ds$/.test(h), h);
  });
  await test('M2', '3.6 入口 2: 时间线片段右键 (选中该片段的句)', async () => {
    const t = await S(`(s.lines[${LI}].t[0] + s.lines[${LI}].t[1]) / 2`);
    const { x, y } = await laneXY(t, 'fx0');
    await p.mouse.click(x, y, { button: 'right' });
    await p.waitForSelector('[data-testid=ctx-menu]');
    const g = await g0(LI), n = await S(`s.lines[${LI}].chars.length`);
    const r = await S('s.ranges');
    assert(r.length === 1 && r[0][0] === g && r[0][1] === g + n - 1, JSON.stringify(r));
    assert((await p.textContent('[data-testid=ctx-header]')).includes('L03'), 'header');
  });
  await test('M3', '3.6 入口 3: 监视器画面右键, 按包围盒命中, 显示 "此处 N 个事件"', async () => {
    const c = await S(`s.lines[${LI}].chars[6]`);
    await seek(c.s + 0.05);
    await sleep(400);
    const fr = await p.locator('[data-testid=frame-out]').boundingBox();
    const box = c.box;
    const x = fr.x + ((box[0] + box[2]) / 2 / 1920) * fr.width, y = fr.y + ((box[1] + box[3]) / 2 / 1080) * fr.height;
    await p.mouse.click(x, y, { button: 'right' });
    await p.waitForSelector('[data-testid=ctx-menu]');
    const h = await p.textContent('[data-testid=ctx-header]');
    const m = /^此处 (\d+) 个事件/.exec(h);
    assert(m && +m[1] > 0, h);
    assert(await p.locator('[data-testid=hit-box]').count() === +m[1], '命中框数');
    assert(await S('s.ranges.length') === 1 && (await S('s.ranges[0][0]')) === (await g0(LI)) + 6, '右键处的字未成为选区');
  });
  await test('M4', '3.6 右键点在选区外: 先把选区换成被点的字; 点在选区内保持', async () => {
    await showLine(LI);
    const g = await g0(LI);
    await clickChar(g + 1);
    await clickChar(g + 3, { modifiers: ['Shift'] });
    await openMenuOnChar(g + 2);
    let r = await S('s.ranges');
    assert(r[0][0] === g + 1 && r[0][1] === g + 3, '选区内右键改了选区');
    await p.keyboard.press('Escape');
    await openMenuOnChar(g + 8);
    r = await S('s.ranges');
    assert(r.length === 1 && r[0][0] === g + 8 && r[0][1] === g + 8, `选区外右键 ${JSON.stringify(r)}`);
  });
  await test('M5', '3.6 菜单结构与右侧快捷键', async () => {
    await showLine(LI);
    await openMenuOnChar((await g0(LI)) + 6);
    const ids = await p.$$eval('[data-testid=ctx-menu] [role=menuitem]', (els) => els.map((e) => e.dataset.id));
    const want = ['play', 'loop', 'loop-half', 'explain', 'note', 'bad', 'good', 'redo', 'compare', 'only', 'locate', 'copy-tc', 'copy-ass', 'export'];
    assert(JSON.stringify(ids) === JSON.stringify(want), ids.join(','));
    const kbd = await p.$$eval('[data-testid=ctx-menu] [class*=kbd]', (els) => els.map((e) => e.textContent));
    for (const k of ['Space', 'L', 'Shift+L', 'E', 'N', 'G', 'R', 'F', 'Ctrl+Shift+C']) assert(kbd.includes(k), `缺快捷键 ${k}`);
    assert(await p.locator('[data-testid=ctx-menu] [role=separator]').count() === 5, '分隔线数');
  });
  await test('M6', '3.6 不可用项置灰并在 tooltip 说原因', async () => {
    await seek(110.0);
    await sleep(300);
    const fr = await p.locator('[data-testid=frame-out]').boundingBox();
    await p.mouse.click(fr.x + 8, fr.y + 8, { button: 'right' });
    await p.waitForSelector('[data-testid=ctx-menu]');
    assert(await item('play').getAttribute('aria-disabled') === 'true', '播放选区未置灰');
    await item('play').hover();
    await p.waitForSelector('[data-testid=ctx-tip]', { timeout: 2000 });
    const tip = await p.textContent('[data-testid=ctx-tip]');
    assert(tip.includes('没有选区'), tip);
    // aria-disabled 的项 locator.click 会一直等它可用; 用真实鼠标点它的中心
    await p.evaluate(() => { window.__m6clicks = 0; document.querySelector('[role=menuitem][data-id="play"]').addEventListener('click', () => { window.__m6clicks++; }, { capture: true }); });
    const pb = await item('play').boundingBox();
    await p.mouse.click(pb.x + pb.width / 2, pb.y + pb.height / 2);
    // 正向: 点击确实落在置灰项上 (capture 监听收到), 否则 "菜单还在" 可能只是没点中
    await p.waitForFunction(() => window.__m6clicks > 0, null, { timeout: 1000 });
    const h = await holdFor(() => p.locator('[data-testid=ctx-menu]').count(), 1, 600);
    assert(h.ok, `点置灰项关了菜单 (count=${h.v} @${h.at}ms)`);
  });
  await test('M7', '3.6 播放选区 (Space): 播完选区自动停', async () => {
    await showLine(LI);
    const g = await g0(LI);
    await clickChar(g + 6);
    await clickChar(g + 8, { modifiers: ['Shift'] });
    await openMenuOnChar(g + 7);
    await item('play').click();
    await sleep(200);
    assert(await p.evaluate(() => window.__hx.clock.playing), '没在播');
    const e = await S(`s.lines[${LI}].chars[8].e`);
    const s0 = await S(`s.lines[${LI}].chars[6].s`);
    await sleep((e - s0) * 1000 + 600);
    assert(!(await p.evaluate(() => window.__hx.clock.playing)), '没停');
    assert(near(await T(), e, 0.06), `停在 ${await T()} != ${e}`);
    // 快捷键 Space 同样播放选区
    await p.locator('[data-testid=lyrics]').focus();
    await p.keyboard.press('Space');
    await sleep(150);
    const t = await T();
    assert(await p.evaluate(() => window.__hx.clock.playing) && t >= s0 - 0.01 && t < e, `Space ${t}`);
  });
  await test('M8', '3.6 循环选区 (L)', async () => {
    await showLine(LI);
    const g = await g0(LI);
    await clickChar(g + 6);
    await clickChar(g + 8, { modifiers: ['Shift'] });
    await p.keyboard.press('l');
    const lp = await S('s.loop');
    assert(lp, '无循环区');
    await sleep((lp.t1 - lp.t0) * 1000 + 700);
    const t = await T();
    assert(await p.evaluate(() => window.__hx.clock.playing) && t >= lp.t0 - 0.02 && t <= lp.t1 + 0.05, `循环外 ${t}`);
    await p.keyboard.press('l');
    assert(!(await S('s.loop')), 'L 再按没取消');
    // 菜单项
    await openMenuOnChar(g + 7);
    await item('loop').click();
    assert(await S('s.loop'), '菜单循环');
  });
  await test('M9', '3.6 0.5x 循环 (Shift+L)', async () => {
    await showLine(LI);
    await p.locator(`[data-i="${LI}"] [data-testid=lineno]`).click();
    await p.keyboard.press('Shift+L');
    await sleep(200);
    const r = await p.evaluate(() => ({ rate: window.__hx.clock.audio.playbackRate, loop: window.__hx.store.getState().loop }));
    assert(r.rate === 0.5 && r.loop, JSON.stringify(r));
    await p.keyboard.press('l');
    await openMenuOnChar((await g0(LI)) + 2);
    await item('loop-half').click();
    assert(await p.evaluate(() => window.__hx.clock.audio.playbackRate) === 0.5, '菜单 0.5x');
  });
  await test('M10', '3.6 说明这里 (E) -> 检查器: fx 函数 + 源码位置, 层号, 标签; arc; 音乐事件; 参考对比', async () => {
    await showLine(LI);
    const g = await g0(LI);
    await clickChar(g + 6);
    await clickChar(g + 8, { modifiers: ['Shift'] });
    await openMenuOnChar(g + 7);
    await item('explain').click();
    await p.waitForSelector('[data-testid=inspector] [data-testid=ins-groups]', { timeout: 5000 });
    const groups = await p.textContent('[data-testid=ins-groups]');
    assert(/fx_bed\.py:\d+/.test(groups) && /hits/.test(groups), 'fx 函数/源码位置');
    const arc = await p.textContent('[data-testid=ins-arc]');
    assert(arc.includes('carrier') && arc.includes('chorus-float'), 'arc');
    const mu = await p.textContent('[data-testid=ins-music]');
    assert(/节拍 \d+ 拍/.test(mu) && /起音 \d+/.test(mu), 'music');
    const rf = await p.textContent('[data-testid=ins-ref]');
    assert(rf.includes('合计') && rf.includes('FX'), 'ref');
    await p.waitForFunction(() => +(document.querySelector('[data-testid=ins-events]')?.dataset.total || 0) > 0, null, { timeout: 5000 });
    await p.click('[data-testid=inspector-close]');
    // 先等旧检查器真的卸载, 否则 count===1 数到的是没关掉的那个
    await p.waitForFunction(() => !document.querySelector('[data-testid=inspector]'), null, { timeout: 3000 });
    assert((await S('s.ranges.length')) > 0, '关检查器后选区没了, E 没有对象');
    await p.keyboard.press('e');
    await p.waitForSelector('[data-testid=inspector]', { timeout: 3000 });
    assert(await p.locator('[data-testid=inspector]').count() === 1, 'E 快捷键');
  });
  await test('M11', '3.6 写批注 (N): 行内输入框, 记入 review', async () => {
    await showLine(LI);
    const n0 = await reviewsCount();
    await openMenuOnChar((await g0(LI)) + 6);
    await item('note').click();
    await p.waitForSelector('[data-testid=note-box] input');
    await p.keyboard.type('这里字太挤');
    await p.keyboard.press('Enter');
    await sleep(300);
    const r = await lastReview();
    assert((await reviewsCount()) === n0 + 1 && r.kind === 'note' && r.text === '这里字太挤' && r.sel[0].line === 3, JSON.stringify(r));
  });
  await test('M12', '3.6 不行 > 看不清 / 太吵 / 太素 / 出戏 / 卡点不准 / 盖字', async () => {
    await showLine(LI);
    const g = await g0(LI);
    for (const tag of ['看不清', '太吵', '太素', '出戏', '卡点不准', '盖字']) {
      await openMenuOnChar(g + 6);
      await item('bad').hover();
      await p.waitForSelector('[data-testid=ctx-sub-1]');
      await item(`bad:${tag}`).click();
      await sleep(200);
      const r = await lastReview();
      assert(r.kind === 'bad' && r.tags[0] === tag, `${tag}: ${JSON.stringify(r)}`);
    }
  });
  await test('M13', '3.6 不行 > 自定义...', async () => {
    await showLine(LI);
    await openMenuOnChar((await g0(LI)) + 6);
    await item('bad').hover();
    await p.waitForSelector('[data-testid=ctx-sub-1]');
    await item('bad:custom').click();
    await p.waitForSelector('[data-testid=note-box] input');
    await p.keyboard.type('光斑抢字');
    await p.keyboard.press('Enter');
    await sleep(300);
    const r = await lastReview();
    assert(r.kind === 'bad' && r.tags[0] === '光斑抢字', JSON.stringify(r));
  });
  await test('M14', '3.6 好 (冻结) G', async () => {
    await showLine(LI);
    const g = await g0(LI);
    // 快捷键先测: 前一步 (M13) 写的是 bad, 不是 good; 判定用 "条数 +1 且新增那条是 good", 不看可能残留的 lastReview
    await clickChar(g + 6);
    await clickChar(g + 8, { modifiers: ['Shift'] });
    assert((await S('s.ranges.length')) > 0, '没有选区, G 没有对象');
    const prev = await lastReview();
    assert(!prev || prev.kind !== 'good', '前一条已是 good, 判不出 G: ' + JSON.stringify(prev));
    const n0 = await reviewsCount();
    await p.keyboard.press('g');
    const n1 = await waitReviewsCount(n0 + 1);
    const rk = await lastReview();
    assert(n1 === n0 + 1 && rk.kind === 'good', `快捷键 G: 条数 ${n0}->${n1} ${JSON.stringify(rk)}`);
    await p.waitForFunction((g) => document.querySelector(`[data-g="${g + 6}"]`).dataset.rv === 'good', g, { timeout: 3000 });
    await openMenuOnChar(g + 6);
    await item('good').click();
    const n2 = await waitReviewsCount(n1 + 1);
    const rm = await lastReview();
    assert(n2 === n1 + 1 && rm.kind === 'good', `菜单 good: 条数 ${n1}->${n2} ${JSON.stringify(rm)}`);
  });
  await test('M15', '3.6 换一个构想 R', async () => {
    await showLine(LI);
    const g = await g0(LI);
    // 快捷键先测: 前一步 (M14 菜单) 写的是 good, 不是 redo; 判定同 M14
    await clickChar(g + 6);
    await clickChar(g + 8, { modifiers: ['Shift'] });
    assert((await S('s.ranges.length')) > 0, '没有选区, R 没有对象');
    const prev = await lastReview();
    assert(!prev || prev.kind !== 'redo', '前一条已是 redo, 判不出 R: ' + JSON.stringify(prev));
    const n0 = await reviewsCount();
    await p.keyboard.press('r');
    const n1 = await waitReviewsCount(n0 + 1);
    const rk = await lastReview();
    assert(n1 === n0 + 1 && rk.kind === 'redo', `快捷键 R: 条数 ${n0}->${n1} ${JSON.stringify(rk)}`);
    await openMenuOnChar(g + 6);
    await item('redo').click();
    const n2 = await waitReviewsCount(n1 + 1);
    const rm = await lastReview();
    assert(n2 === n1 + 1 && rm.kind === 'redo', `菜单 redo: 条数 ${n1}->${n2} ${JSON.stringify(rm)}`);
  });
  const openSub = async (g, parent) => { await openMenuOnChar(g); await item(parent).hover(); await p.waitForSelector('[data-testid=ctx-sub-1]'); };
  await test('M16', '3.6 与参考对比 > A/B 切换', async () => {
    await showLine(LI);
    const g = (await g0(LI)) + 6;
    await openSub(g, 'compare');
    await item('cmp:ab').click();
    await p.waitForSelector('[data-testid=monitor][data-ref-ready]', { timeout: 30000 });
    assert(await p.getAttribute('[data-testid=monitor]', 'data-compare') === 'ab' && await p.getAttribute('[data-testid=monitor]', 'data-ab') === 'ref', 'A/B 未切到参考');
    const vis = await p.evaluate(() => [getComputedStyle(document.querySelector('[data-hidpi=monitor]')).visibility, getComputedStyle(document.querySelector('[data-hidpi=monitor-ref]')).visibility]);
    assert(vis[0] === 'hidden' && vis[1] === 'visible', `可见性 ${vis}`);
    await openSub(g, 'compare');
    await item('cmp:ab').click();
    assert(await p.getAttribute('[data-testid=monitor]', 'data-ab') === 'out', '再点未切回 out');
  });
  await test('M17', '3.6 与参考对比 > 划变对比', async () => {
    await showLine(LI);
    await openSub((await g0(LI)) + 6, 'compare');
    await item('cmp:wipe').click();
    await p.waitForSelector('[data-testid=wipe-handle]');
    const h = await p.locator('[data-testid=wipe-handle]').boundingBox();
    const fr = await p.locator('[data-testid=frame-out]').boundingBox();
    await p.mouse.move(h.x + h.width / 2, h.y + h.height / 2);
    await p.mouse.down();
    await p.mouse.move(fr.x + fr.width * 0.25, h.y + h.height / 2, { steps: 5 });
    await p.mouse.up();
    const w = await S('s.wipe');
    assert(near(w, 0.25, 0.02), `wipe ${w}`);
    const cp = await p.evaluate(() => document.querySelector('[data-hidpi=monitor-ref]').style.clipPath);
    assert(cp.startsWith('inset(0px 0px 0px 2') || cp.includes('25'), cp);
  });
  await test('M18', '3.6 与参考对比 > 左右并排', async () => {
    await showLine(LI);
    await openSub((await g0(LI)) + 6, 'compare');
    await item('cmp:side').click();
    await p.waitForSelector('[data-testid=frame-ref] canvas[data-hidpi=monitor-ref]');
    await sleep(500);
    const a = await p.locator('[data-testid=frame-out]').boundingBox(), b2 = await p.locator('[data-testid=frame-ref]').boundingBox();
    assert(b2.x >= a.x + a.width && near(a.width, b2.width, 2) && near(a.width / a.height, 16 / 9, 0.02), '并排布局');
    const px = await p.evaluate(() => [...document.querySelectorAll('[data-testid=monitor] canvas')].map((c) => [c.width, Math.round(c.getBoundingClientRect().width * devicePixelRatio)]));
    assert(px.every(([w, e]) => Math.abs(w - e) <= 1), `画布像素 ${JSON.stringify(px)}`);
    await p.waitForSelector('[data-testid=monitor][data-ref-ready]', { timeout: 30000 });
  });
  await test('M19', '3.6 只看 > 字层 / FX / 卡片 / 本句事件', async () => {
    await showLine(LI);
    const g = (await g0(LI)) + 6;
    const pick = async (id) => { await openSub(g, 'only'); await item(id).click(); };
    await pick('only:text');
    assert(await waitKept(counts.text) === counts.text, `字层 ${await kept()} != ${counts.text}`);
    await pick('only:fx');
    assert(await waitKept(counts.fx) === counts.fx, `FX ${await kept()} != ${counts.fx}`);
    await pick('only:card');
    assert(await waitKept(counts.card) === counts.card, `卡片 ${await kept()} != ${counts.card}`);
    await pick('only:card'); // 再点取消
    assert(await waitKept(counts.all) === counts.all, '取消只看');
    await pick('only:line');
    const want = await p.evaluate(async () => { const t = await (await fetch('/api/ass/out')).text(); return t.split(/\r?\n/).filter((l) => l.startsWith('Dialogue:') && /,(ly|fx):p03,/.test(l)).length; });
    assert(await waitKept(want) === want, `本句 ${await kept()} != ${want}`);
  });
  await test('M20', '3.6 在时间线中定位 F', async () => {
    await showLine(LI);
    await p.locator(`[data-i="${LI}"] [data-testid=lineno]`).click();
    await openMenuOnChar((await g0(LI)) + 3);
    await item('locate').click();
    const v = await S('s.view');
    const L = await S(`s.lines[${LI}].t`);
    assert(v.v0 <= L[0] && v.v1 >= L[1] && v.v1 - v.v0 < (L[1] - L[0]) * 2, JSON.stringify(v));
    await reset();
    await showLine(LI);
    await p.locator(`[data-i="${LI}"] [data-testid=lineno]`).click();
    await p.keyboard.press('f');
    const v2 = await S('s.view');
    assert(v2.v1 - v2.v0 < 20, 'F 快捷键');
  });
  await test('M21', '3.6 复制时间码 Ctrl+Shift+C', async () => {
    await showLine(LI);
    const g = await g0(LI);
    await clickChar(g + 6);
    await clickChar(g + 8, { modifiers: ['Shift'] });
    await openMenuOnChar(g + 7);
    await item('copy-tc').click();
    await sleep(200);
    const c = await p.evaluate(() => navigator.clipboard.readText());
    assert(/^\d\d:\d\d\.\d\d-\d\d:\d\d\.\d\d$/.test(c), c);
    await p.evaluate(() => navigator.clipboard.writeText(''));
    await p.keyboard.press('Control+Shift+C');
    await sleep(200);
    assert((await p.evaluate(() => navigator.clipboard.readText())) === c, '快捷键');
  });
  await test('M22', '3.6 复制所选事件 (ASS 原文)', async () => {
    await showLine(LI);
    const g = await g0(LI);
    await clickChar(g + 6);
    await clickChar(g + 8, { modifiers: ['Shift'] });
    await p.waitForFunction(() => window.__hx.store.getState().explain, null, { timeout: 3000 });
    const n = await S('s.explain.reduce((a, it) => a + it.n, 0)');
    await openMenuOnChar(g + 7);
    await item('copy-ass').click();
    await sleep(500);
    const c = await p.evaluate(() => navigator.clipboard.readText());
    const ls = c.split('\n');
    assert(ls.length === n && ls.every((l) => l.startsWith('Dialogue:')), `${ls.length} != ${n}`);
  });
  await test('M23', '3.6 导出当前帧 PNG', async () => {
    await showLine(LI);
    await openMenuOnChar((await g0(LI)) + 6);
    const [dl] = await Promise.all([p.waitForEvent('download'), item('export').click()]);
    const f = cfg.tmp + '/' + dl.suggestedFilename();
    await dl.saveAs(f);
    const head = fs.readFileSync(f).subarray(0, 8).toString('hex');
    assert(/^frame_\d+\.\d\d\.png$/.test(dl.suggestedFilename()) && head === '89504e470d0a1a0a' && fs.statSync(f).size > 10000, `${dl.suggestedFilename()} ${head}`);
  });
  await test('K1', '3.6 键盘全程操作: 上下选项, 右键进子菜单, Esc 逐级退出, Enter 执行', async () => {
    await showLine(LI);
    await openMenuOnChar((await g0(LI)) + 6);
    const act = () => p.$eval('[data-testid=ctx-menu] [data-active]', (e) => e.dataset.id).catch(() => null);
    await p.keyboard.press('ArrowDown');
    assert(await act() === 'play', `1 ${await act()}`);
    await p.keyboard.press('ArrowDown');
    await p.keyboard.press('ArrowDown');
    await p.keyboard.press('ArrowDown');
    assert(await act() === 'explain', `跳过分隔 ${await act()}`);
    await p.keyboard.press('ArrowUp');
    assert(await act() === 'loop-half', '上');
    for (let i = 0; i < 3; i++) await p.keyboard.press('ArrowDown');
    assert(await act() === 'bad', `到 不行 ${await act()}`);
    await p.keyboard.press('ArrowRight');
    await p.waitForSelector('[data-testid=ctx-sub-1]');
    assert((await p.$eval('[data-testid=ctx-sub-1] [data-active]', (e) => e.dataset.id)) === 'bad:看不清', '子菜单首项');
    await p.keyboard.press('ArrowDown');
    await p.keyboard.press('Escape');
    assert(await p.locator('[data-testid=ctx-sub-1]').count() === 0 && await p.locator('[data-testid=ctx-menu]').count() === 1, 'Esc 退一级');
    await p.keyboard.press('ArrowRight');
    await p.keyboard.press('ArrowLeft');
    assert(await p.locator('[data-testid=ctx-sub-1]').count() === 0, '左键退一级');
    const n0 = await reviewsCount();
    await p.keyboard.press('ArrowDown'); // good
    assert(await act() === 'good', `good ${await act()}`);
    await p.keyboard.press('Enter');
    await sleep(300);
    assert((await reviewsCount()) === n0 + 1 && (await lastReview()).kind === 'good' && await p.locator('[data-testid=ctx-menu]').count() === 0, 'Enter 执行');
    await openMenuOnChar((await g0(LI)) + 6);
    await p.keyboard.press('Escape');
    assert(await p.locator('[data-testid=ctx-menu]').count() === 0, 'Esc 关菜单');
  });
  await test('K2', '3.6 子菜单悬停延迟 150ms', async () => {
    await showLine(LI);
    await openMenuOnChar((await g0(LI)) + 6);
    const bb = await item('compare').boundingBox();
    await p.mouse.move(bb.x + 20, bb.y + bb.height / 2);
    await sleep(60);
    const early = await p.locator('[data-testid=ctx-sub-1]').count();
    await sleep(220);
    const late = await p.locator('[data-testid=ctx-sub-1]').count();
    assert(early === 0 && late === 1, `60ms:${early} 280ms:${late}`);
  });
  await test('K3', '3.6 子菜单安全三角防误关', async () => {
    await showLine(LI);
    await openMenuOnChar((await g0(LI)) + 6);
    const bad = await item('bad').boundingBox();
    await p.mouse.move(bad.x + bad.width - 30, bad.y + bad.height / 2);
    await p.waitForSelector('[data-testid=ctx-sub-1]');
    const sub = await p.locator('[data-testid=ctx-sub-1]').boundingBox();
    const target = await item('bad:盖字').boundingBox(); // 子菜单靠下的项: 斜穿过 "好 (冻结)" 一行
    const sx = bad.x + bad.width - 30, sy = bad.y + bad.height / 2;
    const tx = target.x + 30, ty = target.y + target.height / 2;
    for (let k = 1; k <= 6; k++) { await p.mouse.move(sx + (tx - sx) * k / 6, sy + (ty - sy) * k / 6); await sleep(15); }
    await sleep(80);
    assert(await p.locator('[data-testid=ctx-sub-1]').count() === 1, '穿过下一项时子菜单被关');
    // 子菜单在父项旁边: 右侧, 或贴右边翻到左侧 (都不能盖住父项)
    assert(sub.x >= bad.x + bad.width - 4 || sub.x + sub.width <= bad.x + 4, `sub 位置 ${JSON.stringify(sub)} bad ${JSON.stringify(bad)}`);
    await p.mouse.click(tx, ty);
    await sleep(200);
    assert((await lastReview()).tags[0] === '盖字', '没点中子菜单项');
  });
  await test('K4', '3.6 菜单贴边自动翻转, 永远在视口内 (含子菜单)', async () => {
    await showLine(LI);
    await p.locator(`[data-i="${LI}"] [data-testid=lineno]`).click();
    const vw = 1920, vh = 1080;
    await p.mouse.click(vw - 4, vh - 40, { button: 'right' });
    await p.waitForSelector('[data-testid=ctx-menu]');
    const m = await p.locator('[data-testid=ctx-menu]').boundingBox();
    assert(m.x >= 0 && m.y >= 0 && m.x + m.width <= vw && m.y + m.height <= vh, JSON.stringify(m));
    assert(await p.getAttribute('[data-testid=ctx-menu]', 'data-flip-x') === '1' && await p.getAttribute('[data-testid=ctx-menu]', 'data-flip-y') === '1', '未翻转');
    await item('compare').hover();
    await p.waitForSelector('[data-testid=ctx-sub-1]');
    const s1 = await p.locator('[data-testid=ctx-sub-1]').boundingBox();
    assert(s1.x + s1.width <= vw && s1.x < m.x, `子菜单 ${JSON.stringify(s1)}`);
    assert(await p.evaluate(() => document.querySelector('[data-testid=ctx-menu]').parentElement === document.body), '未 portal 到 body');
    const sh = await p.evaluate(() => [document.documentElement.scrollHeight, innerHeight, document.documentElement.scrollWidth, innerWidth]);
    assert(sh[0] === sh[1] && sh[2] === sh[3], `菜单撑出滚动条 ${sh}`);
  });
  await test('K5', '3.6 写动作全部走 POST /api/review (服务端追加)', async () => {
    const items = (await (await p.request.get(cfg.url + 'api/review')).json()).items;
    const kinds = new Set(items.map((r) => r.kind));
    assert(['bad', 'good', 'redo', 'note'].every((k) => kinds.has(k)), [...kinds].join(','));
    assert(items.every((r) => r.id && r.created && Array.isArray(r.sel) && typeof r.t0 === 'number'), 'schema');
  });

  // ======================= 3.7 时间线轨 =======================
  await test('T1', '3.7 FX 层 0-8 与卡片轨, 片段悬停显示 fx 名/条数/层号', async () => {
    const r = await rows();
    for (const id of ['mv', 'wave', 'beat', 'jp', 'rb', 'cn', 'fx0', 'fx1', 'fx2', 'fx3', 'fx4', 'fx5', 'fx6', 'fx7', 'fx8', 'card', 'density']) assert(r[id], `缺轨 ${id}`);
    const t = await S(`(s.lines[${LI}].t[0] + s.lines[${LI}].t[1]) / 2`);
    const { x, y } = await laneXY(t, 'fx7');
    await p.mouse.move(x, y);
    await p.waitForSelector('[data-testid=clip-tip]');
    const tip = await p.textContent('[data-testid=clip-tip]');
    assert(/^p03 · fx7 · \d+ 条 · 层 7/.test(tip) && tip.includes('hits'), tip);
    const c = await laneXY(3, 'card');
    await p.mouse.move(c.x, c.y);
    await p.waitForSelector('[data-testid=clip-tip]');
    assert((await p.textContent('[data-testid=clip-tip]')).startsWith('title · card'), '卡片轨');
  });
  await test('T2', '3.7 轨头眼睛: 隐藏该轨 (监视器不渲染)', async () => {
    assert(await waitKept(counts.all) === counts.all, '初始');
    await p.click('[data-track=fx7] [data-act=eye]');
    assert(await waitKept(counts.all - counts.l7) === counts.all - counts.l7, `眼 ${await kept()}`);
    await p.click('[data-track=fx7] [data-act=eye]');
    assert(await waitKept(counts.all) === counts.all, '恢复');
  });
  await test('T3', '3.7 轨头 S 独显', async () => {
    await p.click('[data-track=jp] [data-act=solo]');
    assert(await waitKept(counts.jp) === counts.jp, `S ${await kept()} != ${counts.jp}`);
    assert(await p.getAttribute('[data-track=jp] [data-act=solo]', 'aria-pressed') === 'true', 'aria');
  });
  await test('T4', '3.7 轨头锁: 锁定轨上不能选取 / 右键', async () => {
    await p.click('[data-track=fx0] [data-act=lock]');
    const t = await S(`(s.lines[${LI}].t[0] + s.lines[${LI}].t[1]) / 2`);
    const { x, y } = await laneXY(t, 'fx0');
    await p.evaluate(() => { window.__t4ctx = 0; document.addEventListener('contextmenu', () => { window.__t4ctx++; }, { capture: true, once: true }); });
    await p.mouse.click(x, y, { button: 'right' });
    // 正向: 右键确实发到了页面 (capture 监听收到), 否则 "没菜单没选区" 可能只是没点到
    await p.waitForFunction(() => window.__t4ctx > 0, null, { timeout: 1000 });
    const h = await holdFor(() => S(`document.querySelector('[data-testid=ctx-menu]') ? 'menu' : s.ranges.length`), 0, 600);
    assert(h.ok, `锁定轨仍可选 (${h.v} @${h.at}ms)`);
    // 正向: 锁定防护本身跑过 (它会弹 toast)
    await p.waitForFunction(() => (document.querySelector('[data-testid=toast]')?.textContent || '').includes('锁定'), null, { timeout: 1000 });
    const u = await laneXY(t, 'fx1');
    await p.mouse.click(u.x, u.y, { button: 'right' });
    await p.waitForSelector('[data-testid=ctx-menu]');
  });
  await test('T5', '3.7 轨高可拖', async () => {
    const r0 = await rows();
    const h = await p.locator('[data-testid=resize-wave]').boundingBox();
    await p.mouse.move(h.x + 20, h.y + h.height / 2);
    await p.mouse.down();
    await p.mouse.move(h.x + 20, h.y + h.height / 2 + 24, { steps: 4 });
    await p.mouse.up();
    const r1 = await rows();
    assert(r1.wave.h === r0.wave.h + 24, `${r0.wave.h} -> ${r1.wave.h}`);
    assert(JSON.parse(await p.evaluate(() => localStorage.getItem('hxstudio.trackH'))).wave === r1.wave.h, '没写 localStorage');
    const sh = await p.evaluate(() => document.documentElement.scrollHeight === innerHeight);
    assert(sh, '拖高后出滚动条');
  });
  await test('T6', '3.7 轨组可折叠 (字层组, FX 组)', async () => {
    await p.click('[data-testid=group-fx]');
    let r = await rows();
    assert(r['g:fx'] && !r.fx3, '没折叠 FX: ' + Object.keys(r).join(',') + ' btn=' + await p.getAttribute('[data-testid=group-fx]', 'data-collapsed') + ' st=' + JSON.stringify(await S('s.collapsed')));
    await p.click('[data-testid=group-text]');
    r = await rows();
    assert(r['g:text'] && !r.rb, '没折叠字层');
    await p.click('[data-testid=group-fx]');
    r = await rows();
    assert(r.fx3 && !r['g:fx'], '没展开');
  });
  await test('T7', '3.7 双击片段 = 选中该句并循环', async () => {
    const t = await S(`(s.lines[${LI}].t[0] + s.lines[${LI}].t[1]) / 2`);
    const { x, y } = await laneXY(t, 'cn');
    await p.mouse.dblclick(x, y);
    await sleep(200);
    const g = await g0(LI), n = await S(`s.lines[${LI}].chars.length`);
    const r = await S('s.ranges');
    const lp = await S('s.loop');
    assert(r.length === 1 && r[0][0] === g && r[0][1] === g + n - 1 && lp, JSON.stringify({ r, lp }));
  });

  // ======================= 2026-11-09 交互修正 (老板复核) =======================
  await test('U1', '时间线: 普通滚轮 = 以指针为中心缩放, Shift+滚轮 = 平移 (不按 Ctrl)', async () => {
    const lane = await p.locator('[data-hidpi=timeline-static]').boundingBox();
    const x = lane.x + lane.width * 0.5, y = lane.y + 30;
    const v0 = await S('s.view');
    await p.mouse.move(x, y);
    const tAt = v0.v0 + 0.5 * (v0.v1 - v0.v0);
    await p.mouse.wheel(0, -300);
    await sleep(150);
    const v1 = await S('s.view');
    assert(v1.v1 - v1.v0 < (v0.v1 - v0.v0) * 0.8, `没缩放 ${JSON.stringify([v0, v1])}`);
    const c = (tAt - v1.v0) / (v1.v1 - v1.v0);
    assert(near(c, 0.5, 0.02), `缩放中心偏了 ${c}`);
    await p.keyboard.down('Shift');
    await p.mouse.wheel(0, 200);
    await p.keyboard.up('Shift');
    await sleep(150);
    const v2 = await S('s.view');
    assert(near(v2.v1 - v2.v0, v1.v1 - v1.v0, 0.01) && v2.v0 > v1.v0 + 0.01, `Shift 没平移 ${JSON.stringify([v1, v2])}`);
  });
  await test('U2', 'FX 0-8 轨名带语义 (按 assfx 层序), 轨头 hover 说明该层职责', async () => {
    const names = await p.$$eval('[data-track^=fx]', (els) => els.map((e) => [e.dataset.track, e.querySelector('[class*=hname]').textContent, e.querySelector('[class*=hname]').title]));
    const m = Object.fromEntries(names.map(([id, n, t]) => [id, [n, t]]));
    const want = { fx0: '字后底光', fx3: '跳字', fx4: '辉光', fx7: '前景主体', fx8: '顶层闪光' };
    for (const [id, w] of Object.entries(want)) assert(m[id] && m[id][0].includes(w) && m[id][1].includes('FX 层'), `${id} ${JSON.stringify(m[id])}`);
    // 名字不被截断: 文字宽度 <= 容器
    const clip = await p.$$eval('[data-track^=fx] [class*=hname]', (els) => els.filter((e) => e.scrollWidth > e.clientWidth + 1).map((e) => e.textContent));
    assert(!clip.length, `轨名被截断 ${clip}`);
  });
  const postReview = (kind, li, from, to, tags = [], text = '') => S(`[s.lines[${li}].line, s.lines[${li}].chars[${from}].s, s.lines[${li}].chars[${to}].e]`).then(([line, t0, t1]) =>
    p.request.post(cfg.url + 'api/review', { data: { sel: [{ line, from, to }], t0, t1, kind, tags, text } }));
  await test('U3', '时间线标注轨: 显示已有标注, 按类型着色 (不行橙/好绿/换一个紫/备注蓝), hover 说明, 点击选中所标的字', async () => {
    const kinds = [['bad', 10, [240, 162, 74]], ['good', 11, [89, 195, 138]], ['redo', 12, [180, 140, 255]], ['note', 13, [110, 168, 255]]];
    // 用 POST 返回的 id 定位自己写入的那 4 条; 之前 M11-M15 早已写过同类, 不能用 "条数 >= 4" 或 "该类最后一条"
    const n0 = await S('s.reviews.length');
    const ids = [];
    for (const [k, li] of kinds) {
      const res = await postReview(k, li, 0, 2, k === 'bad' ? ['太吵'] : [], k === 'note' ? '测试备注' : '');
      assert(res.status() === 201, `POST ${k} -> ${res.status()}`);
      ids.push((await res.json()).id);
    }
    await p.waitForFunction(([ids, ks, n]) => { const r = window.__hx.store.getState().reviews; return r.length === n + ids.length && ids.every((id, i) => r.some((x) => x.id === id && x.kind === ks[i])); }, [ids, kinds.map((x) => x[0]), n0], { timeout: 5000 });
    const r = (await rows()).review;
    assert(r && r.h >= 10, '没有标注轨');
    const lane = await p.locator('[data-hidpi=timeline-static]').boundingBox();
    const got = [];
    for (const [k, li, rgb] of kinds) {
      const rv = await S(`s.reviews.find((x) => x.id === '${ids[kinds.findIndex((q) => q[0] === k)]}' && x.kind === '${k}')`);
      assert(rv, `${k}: store 里找不到自己写入的那条`);
      const { x } = await laneXY((rv.t0 + rv.t1) / 2, 'review');
      const ki = ['bad', 'good', 'redo', 'note'].indexOf(k);
      const lh = Math.max(2, (r.h - 2) / 4);
      const yy = r.y + 1 + ki * lh + lh / 2 - 0.5;
      const px = await p.evaluate(({ x, y }) => { const c = document.querySelector('[data-hidpi=timeline-static]'); const b = c.getBoundingClientRect(); return [...c.getContext('2d').getImageData(Math.round((x - b.left) * devicePixelRatio), Math.round(y * devicePixelRatio), 1, 1).data]; }, { x, y: yy });
      got.push([k, px]);
      assert(Math.abs(px[0] - rgb[0]) < 12 && Math.abs(px[1] - rgb[1]) < 12 && Math.abs(px[2] - rgb[2]) < 12, `${k} 颜色 ${px}`);
      if (k === 'bad') {
        await p.mouse.move(5, 5); // 先移开, 免得读到上一次 hover 留下的 tip
        await p.waitForSelector('[data-testid=clip-tip]', { state: 'detached', timeout: 2000 }).catch(() => {});
        await p.mouse.move(x, lane.y + yy);
        await p.waitForSelector('[data-testid=clip-tip]', { timeout: 2000 });
        const tip = await p.textContent('[data-testid=clip-tip]');
        // 同一时刻可能叠着前面用例写的 "不行" 标注; UI 取指针所在类型格里最短的那条. 期望值按同口径算
        const hv = (rv.t0 + rv.t1) / 2;
        const exp = await S(`s.reviews.filter((x) => x.kind === 'bad' && x.t0 <= ${hv} && x.t1 >= ${hv}).sort((a, b) => (a.t1 - a.t0) - (b.t1 - b.t0))[0]`);
        const expTag = [exp.tags.join(' / '), exp.text].filter(Boolean).join(' · ');
        assert(tip.startsWith('不行') && tip.includes(expTag), `tip ${tip} 期望含 ${expTag}`);
        await p.mouse.click(x, lane.y + yy);
        await sleep(200);
        const sel = await S('s.ranges');
        const g = await S(`(() => { const sr = s.reviews.filter((x) => x.kind === 'bad' && x.t0 <= ${hv} && x.t1 >= ${hv}).sort((a, b) => (a.t1 - a.t0) - (b.t1 - b.t0))[0].sel[0]; return [s.lines.findIndex((l) => l.line === sr.line), sr.from, sr.to]; })()`);
        const base = await g0(g[0]);
        assert(sel.length === 1 && sel[0][0] === base + g[1] && sel[0][1] === base + g[2], `点标注没选中 ${JSON.stringify(sel)} 期望 ${JSON.stringify(g)}`);
      }
    }
  });
  await test('U4', '歌词下划线区分四种标注 (不行橙/好绿/换一个紫/备注蓝)', async () => {
    const out = [];
    for (const [k, li, rgb] of [['bad', 10, '240, 162, 74'], ['good', 11, '89, 195, 138'], ['redo', 12, '180, 140, 255'], ['note', 13, '110, 168, 255']]) {
      const g = await g0(li);
      await p.waitForFunction(([g, k]) => document.querySelector(`[data-g="${g}"]`)?.dataset.rv === k, [g, k], { timeout: 4000 });
      const sh = await p.evaluate((g) => getComputedStyle(document.querySelector(`[data-g="${g}"]`)).boxShadow, g);
      out.push(sh);
      assert(sh.includes(rgb), `${k} ${sh}`);
    }
  });
  await test('U5', 'A/B 按钮自解释: "对比: 成品 / 参考", hover 说明两边各是什么; 点开后是 成品|参考 两段 + 关闭', async () => {
    const t = (await p.textContent('[data-testid=ab-btn]')).trim();
    const tip = await p.getAttribute('[data-testid=ab-btn]', 'title');
    assert(t === '对比: 成品 / 参考', t);
    assert(tip.includes('成品 = 本工程生成的 out.ass') && tip.includes('参考 = ') && tip.includes('.ass'), tip);
    await p.click('[data-testid=ab-btn]');
    await p.waitForSelector('[data-testid=ab-ref][data-on]');
    assert(await p.getAttribute('[data-testid=monitor]', 'data-ab') === 'ref', '没切到参考');
    assert((await p.textContent('[data-testid=ab-badge]')).includes('参考'), '角标');
    await p.click('[data-testid=ab-out]');
    assert(await p.getAttribute('[data-testid=monitor]', 'data-ab') === 'out', '没切回成品');
    assert((await p.textContent('[data-testid=ab-badge]')).includes('成品'), '角标成品');
    await p.click('[data-testid=ab-close]');
    assert(await p.getAttribute('[data-testid=monitor]', 'data-compare') === 'off', '没关掉');
  });
  await test('U6', '说明这里: 检查器顶部有 "一句话说明" (条数/按层语义名/fx 出处/角色/参考倍数) + 这里的标注', async () => {
    // M12/K3 已写过 "盖字": 用 POST 返回的 id + 条数 +1 定位自己写入的那条, POST 失败必须红
    const n0 = await S('s.reviews.length');
    const res = await postReview('bad', LI, 6, 8, ['盖字']);
    assert(res.status() === 201, `POST -> ${res.status()}`);
    const id = (await res.json()).id;
    await p.waitForFunction(([id, n]) => { const r = window.__hx.store.getState().reviews; return r.length === n + 1 && r.some((x) => x.id === id && x.tags.includes('盖字')); }, [id, n0], { timeout: 5000 });
    await showLine(LI);
    const g = await g0(LI);
    await clickChar(g + 6);
    await clickChar(g + 8, { modifiers: ['Shift'] });
    await openMenuOnChar(g + 7);
    await item('explain').click();
    await p.waitForSelector('[data-testid=ins-plain]', { timeout: 5000 });
    const t = await p.textContent('[data-testid=ins-plain]');
    assert(/共 \d+ 条事件: 字层 \d+ 条, 特效 \d+ 条/.test(t) && /按层: .*(字后底光|前景主体|近字粒子)/.test(t) && /特效主要出自 fx_/.test(t) && /参考 ASS 同一时段 \d+ 条/.test(t), t.slice(0, 300));
    const rv = await p.textContent('[data-testid=ins-reviews]');
    assert(/这里的标注 [1-9]\d* 条/.test(rv) && rv.includes('盖字'), rv.slice(0, 200));
  });
  await test('U7', '视频只出画不出声: 播放时除 clock 音频外没有在响的媒体 (setSrc 1 次, EDL 同刻 1 段, 倍速一致)', async () => {
    await p.locator('[data-testid=lyrics]').focus();
    await p.evaluate(() => window.__hx.clock.seek(40));
    await p.keyboard.press('Space');
    await sleep(1200);
    const r = await p.evaluate(() => {
      const st = window.__hx.store.getState();
      const t = window.__hx.clock.t();
      const segs = (st.edl?.segments || []).filter((g) => t >= g.t0 && (g.t1 == null || t < g.t1)).length;
      const vids = [...document.querySelectorAll('video')].map((v) => ({ paused: v.paused, muted: v.muted, vol: v.volume, rate: v.playbackRate }));
      return { segs, vids, arate: window.__hx.clock.audio.playbackRate, aPaused: window.__hx.clock.audio.paused };
    });
    await p.keyboard.press('Space');
    const loud = r.vids.filter((v) => !v.paused && (!v.muted || v.vol > 0));
    assert(!r.aPaused && r.segs === 1 && !loud.length && r.vids.every((v) => v.rate === r.arate), JSON.stringify(r));
  });

  await test('U8', '轨高: 1920x1080 下 FX 每条原高 26 (放不下就滚动, 不压); 字层 JP >= 24, 密度 28-80; 拖矮时间线时 FX 不变, 先少的是密度/波形和 FX 窗口', async () => {
    const fxrows = async () => (await p.getAttribute('[data-testid=timeline]', 'data-fxrows')).split(' ').filter(Boolean).map((x) => +x.split(':')[1]);
    const r = await rows();
    const fx = await fxrows();
    assert(fx.length === 9 && fx.every((h) => h === 26), `FX 高 ${fx}`);
    assert(r.jp.h >= 24 && r.rb.h >= 18 && r.cn.h >= 18, `字层 ${r.jp.h}/${r.rb.h}/${r.cn.h}`);
    assert(r.density.h <= 80 && r.density.h >= 28, `密度 ${r.density.h}`);
    const sp = await p.locator('[role=separator][aria-orientation=horizontal]').boundingBox();
    await p.mouse.move(sp.x + sp.width / 2, sp.y + sp.height / 2);
    await p.mouse.down();
    await p.mouse.move(sp.x + sp.width / 2, sp.y + sp.height / 2 + 60, { steps: 4 });
    await p.mouse.up();
    await sleep(200);
    const r2 = await rows();
    const fx2 = await fxrows();
    const tot = (o) => Object.values(o).reduce((a, v) => Math.max(a, v.y + v.h), 0);
    assert(tot(r2) < tot(r), `时间线没变矮 ${tot(r)} -> ${tot(r2)}`);
    assert(fx2.every((h) => h === 26), `拖矮后 FX 被压了 ${fx2}`);
    assert(r2.density.h <= 30 && r2.wave.h <= 20, `密度/波形没先压: 密度 ${r.density.h}->${r2.density.h} 波形 ${r.wave.h}->${r2.wave.h}`);
    assert(r2.jp.h === r.jp.h && r2.mv.h === r.mv.h, `FX 能滚动时不该压其它轨: jp ${r.jp.h}->${r2.jp.h} mv ${r.mv.h}->${r2.mv.h}`);
    await p.mouse.move(sp.x + sp.width / 2, sp.y + sp.height / 2 + 60);
    await p.mouse.down();
    await p.mouse.move(sp.x + sp.width / 2, sp.y + sp.height / 2, { steps: 4 });
    await p.mouse.up();
  });

  // ======================= 热更新 (HR): 只改 out.ass 的 mtime (内容不动), 服务端 watch 据此推 changed; 结束时还原 mtime =======================
  const outAss = require('path').join(cfg.project, 'out.ass');
  const mt0 = fs.statSync(outAss);
  const touch = () => { const t = new Date(); fs.utimesSync(outAss, t, t); };
  let assReq = 0;
  p.on('request', (r) => { if (r.url().includes('/api/ass/out')) assReq++; });
  const until = async (f, ms, msg) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (await f()) return; await sleep(100); } throw new Error(msg); };
  const chip = () => p.locator('[data-testid=sync-chip]');
  await test('HR1', 'out.ass 在磁盘上变了: 监视器重取 out.ass, 无告警标签', async () => {
    const n0 = assReq;
    touch();
    await until(() => assReq > n0, 6000, '6s 内监视器没重取 out.ass');
    await sleep(800);
    assert((await chip().count()) === 0, '不该有热更新告警标签');
  });
  await test('HR2', '热更新部分失败: lyrics 500 时监视器照样重载, 顶栏黄标签 "歌词/门禁未刷新"; out.ass 读失败保留旧轨并报; 点击重试恢复', async () => {
    const e0 = errors.length;   // 各处 500 都必须被接住: 不许有未处理的 rejection (那就是又一个静默失败)
    await p.route('**/api/lyrics', (r) => r.fulfill({ status: 500, contentType: 'application/json', body: '{"error":"HR2"}' }));
    try {
      const n0 = assReq;
      touch();
      await until(() => assReq > n0, 6000, 'lyrics 失败时监视器没重取 out.ass (仍被 lyrics 卡住)');
      await p.waitForSelector('[data-testid=sync-chip][data-sync=stale]', { timeout: 6000 });
      assert((await chip().getAttribute('data-keys')) === 'data', 'keys: ' + await chip().getAttribute('data-keys'));
      assert((await chip().getAttribute('data-state')) === 'warn', '应为 warn 黄色');
      assert((await chip().textContent()).trim() === '歌词/门禁未刷新 · 点击重试', 'chip 文字: ' + await chip().textContent());
      // 就地标记 (带文字, 不只靠颜色): 歌词面板标题旁 + 门禁 chip
      assert((await p.textContent('[data-testid=stale-lyrics]')).trim() === '上次刷新失败 · 旧版', '歌词面板没标旧版');
      assert((await p.textContent('[data-testid=gate-chip]')).trim().endsWith('(旧)'), '门禁 chip 没标 (旧)');
      assert((await p.locator('[data-testid=stale-tag]').count()) === 0, 'out.ass 已刷新, 监视器不该标旧');
    } finally { await p.unroute('**/api/lyrics'); }
    await p.route('**/api/ass/out', (r) => r.fulfill({ status: 500, contentType: 'application/json', body: '{"error":"HR2"}' }));
    try {
      const k0 = await S('s.monitorKept');
      touch();
      await until(async () => (await chip().getAttribute('data-keys', { timeout: 500 }).catch(() => '')) === 'ass', 6000, 'out.ass 500 后 keys 应只剩 ass (data 已刷新成功)');
      assert((await chip().textContent()).trim() === '监视器字幕未刷新 · 点击重试', 'chip 文字: ' + await chip().textContent());
      assert((await S('s.monitorKept')) === k0 && k0 > 0, '读失败时不该换掉旧轨');
      assert((await p.textContent('[data-testid=stale-tag]')).trim() === '字幕是旧版 · 刷新失败', '监视器没标旧版');
      assert((await p.getAttribute('[data-testid=frame-out]', 'data-stale')) === 'y', '画框没标 stale');
      assert((await p.locator('[data-testid=stale-lyrics]').count()) === 0, '歌词已刷新成功, 不该再标旧');
      assert(!(await p.textContent('[data-testid=gate-chip]')).includes('(旧)'), '门禁已刷新成功, 不该再标 (旧)');
    } finally { await p.unroute('**/api/ass/out'); }
    const n1 = assReq;
    await chip().click();
    await until(() => assReq > n1, 4000, '点击重试没重取 out.ass');
    await p.waitForSelector('[data-testid=sync-chip]', { state: 'detached', timeout: 6000 });
    assert((await p.locator('[data-testid=stale-tag]').count()) === 0, '重试成功后监视器还标着旧版');
    // 标注刷新失败: 标注轨头写 "(旧)". 测试的批注文件在 cfg.tmp, 动它的 mtime 触发 review 变化
    const rv = require('path').join(cfg.tmp, 'review.jsonl');
    if (!fs.existsSync(rv)) fs.writeFileSync(rv, '');
    const bump = () => { const t = new Date(Date.now() + 2000); fs.utimesSync(rv, t, t); };
    const rname = p.locator('[data-track=review] [data-stale]');
    await p.route('**/api/review', (r) => (r.request().method() === 'GET' ? r.fulfill({ status: 500, contentType: 'application/json', body: '{"error":"HR2"}' }) : r.continue()));
    try {
      bump();
      await rname.waitFor({ timeout: 6000 });
      assert((await rname.textContent()).trim() === '标注 (旧)', '标注轨头: ' + await rname.textContent());
    } finally { await p.unroute('**/api/review'); }
    bump();
    await rname.waitFor({ state: 'detached', timeout: 6000 });
    await p.waitForSelector('[data-testid=sync-chip]', { state: 'detached', timeout: 4000 });
    // 位置状态刷新失败: 打开位置面板时 GET /api/placement 500 -> 面板提示行写明可能是旧状态
    await p.route('**/api/placement', (r) => (r.request().method() === 'GET' ? r.fulfill({ status: 500, contentType: 'application/json', body: '{"error":"HR2"}' }) : r.continue()));
    try {
      await p.click('[data-testid=place-btn]');
      await p.waitForSelector('[data-testid=place-msg][data-stale]', { timeout: 6000 });
      assert((await p.textContent('[data-testid=place-msg]')).startsWith('状态刷新失败, 下面可能是旧状态'), '位置面板: ' + await p.textContent('[data-testid=place-msg]'));
    } finally { await p.unroute('**/api/placement'); }
    await p.click('[data-testid=place-btn]');   // 关
    await p.click('[data-testid=place-btn]');   // 再开: 刷新成功, 提示消失
    await p.waitForSelector('[data-testid=place-msg]:not([data-stale])', { timeout: 6000 });
    await p.click('[data-testid=place-btn]');
    await p.waitForSelector('[data-testid=sync-chip]', { state: 'detached', timeout: 4000 });
    assert(errors.length === e0, '有未处理的错误: ' + errors.slice(e0).join(' | '));
  });
  await test('HR3', '连接断开: 顶栏 "未连接"; 断开期间 out.ass 改了不刷新; 重连后按 hello 补刷', async () => {
    await p.evaluate(() => window.__hxWatch.drop());
    await p.waitForSelector('[data-testid=sync-chip][data-sync=offline]', { timeout: 4000 });
    assert((await chip().textContent()).trim() === '未连接 · 改动不会自动刷新', 'chip 文字: ' + await chip().textContent());
    assert((await p.textContent('[data-testid=stale-lyrics]')).trim() === '未连接 · 可能不是最新', '歌词面板没标未连接');
    assert((await p.textContent('[data-testid=stale-tag]')).trim() === '未连接 · 字幕可能不是最新', '监视器没标未连接');
    const n0 = assReq;
    touch();
    await sleep(1500);
    assert(assReq === n0, '断开时不该收到变化');
    await p.evaluate(() => window.__hxWatch.release());
    await until(() => assReq > n0, 6000, '重连后没按 hello 补刷 out.ass');
    await p.waitForSelector('[data-testid=sync-chip]', { state: 'detached', timeout: 4000 });
    assert((await p.locator('[data-testid=stale-lyrics], [data-testid=stale-tag]').count()) === 0, '重连后就地标记没消');
    const n1 = assReq;
    fs.utimesSync(outAss, mt0.atimeMs / 1000, mt0.mtimeMs / 1000);   // 还原 mtime
    await until(() => assReq > n1, 6000, '还原 mtime 后没刷新');
    await sleep(500);
  });

  // ======================= 参考 ASS 选择 (RF): 新开页面, route 模拟 /api/project 的候选状态 + POST /api/ref (不写真实 ref.json) =======================
  const refPage = async (state) => {
    const c2 = await b.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
    const p2 = await c2.newPage();
    const errs = [];
    p2.on('pageerror', (e) => errs.push(String(e).slice(0, 300)));
    const A = '_歌 - 曲.ass', B = '歌 - 曲.ass', dir = 'static/music/番/';
    const cands = [{ path: dir + A, dialogues: 18475, mtime: '2026-11-01 10:00:00' }, { path: dir + B, dialogues: 16510, mtime: '2026-10-20 09:30:00' }];
    const posts = [];
    await p2.route('**/api/project', async (r) => {
      if (state.projFail && state.posted) return r.fulfill({ status: 500, json: { error: 'boom (模拟)' } });   // RF5: 写成了但重取失败
      const real = await (await r.fetch()).json();
      const pick = state.pick;
      Object.assign(real, state.mode === 'none'
        ? { ref_ass: null, ref_path: null, ref: { source: 'none', error: null, set_at: null, candidates: [] } }
        : state.mode === 'refjson'   // RF6/RF7: 错误文字故意不以 "ref.json" 开头, 证明按 err_kind 而不是文字判断
        ? { ref_ass: null, ref_path: null, ref: { source: 'error', err_kind: 'ref_json', error: '手动指定的文件不存在: static/music/番/gone.ass', set_at: null, candidates: cands } }
        : state.mode === 'error'
        ? { ref_ass: null, ref_path: null, ref: { source: 'error', error: 'playlist.json 的 assUrl 不在 static/music/番/ 的候选里 (跨目录或文件不存在): static/music/别的/歌 - 曲.ass', set_at: null, candidates: cands } }
        : pick
        ? { ref_ass: '/api/ass/ref', ref_path: pick, ref: { source: 'manual', error: null, set_at: 'Sun 2026-11-15 11:50 PM CST (UTC+08:00)', candidates: cands } }
        : { ref_ass: null, ref_path: null, ref: { source: 'ambiguous', error: '2 份候选, 没有明确来源 (ref.json / playlist.json), 未指定', set_at: null, candidates: cands } });
      await r.fulfill({ json: real });
    });
    // 门禁 judge 来自真实工程的参考; mock 成 "没有参考" (未选 / none / error / refjson) 时也要从 out profile 里去掉, 否则两边打架 (门禁显示真实 10/10)
    await p2.route((u) => u.pathname === '/api/profile' && u.searchParams.get('which') === 'out', async (r) => {
      const real = await (await r.fetch()).json();
      if (!state.pick) delete real.judge;
      await r.fulfill({ json: real });
    });
    // ref profile: 用 route.fetch() 取真实响应 (p2.request 会再走一遍路由, 和上面的 out mock 互相递归, 直接卡死)
    await p2.route((u) => u.pathname === '/api/profile' && u.searchParams.get('which') === 'ref', async (r) => {
      const real = await (await r.fetch()).json();
      if (!state.pick) delete real.judge;
      await r.fulfill({ json: real });
    });
    await p2.route('**/api/ref', async (r) => {
      const body = JSON.parse(r.request().postData() || '{}');
      posts.push(body);
      if (state.fail) return r.fulfill({ status: 400, json: { error: '不是候选文件: ' + body.ass } });
      state.pick = body.ass;
      state.posted = true;
      if (body.ass === null) state.mode = undefined;   // 清除 -> 回到 "未定"
      return r.fulfill({ json: {} });
    });
    await p2.goto(cfg.url, { waitUntil: 'load' });
    await p2.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 30000 });
    return { c2, p2, errs, posts, A, B, dir };
  };
  await test('RF1', '参考 ASS 多份候选且无明确来源: 不选; 顶栏 error 标签写明 "未定 · 2 份候选"; A/B 停用并说明; 门禁写 "未判定" 而不是 0/0 绿', async () => {
    const { c2, p2, errs } = await refPage({});
    try {
      const chip = p2.locator('[data-testid=ref-chip]');
      assert((await chip.textContent()).trim() === '参考 ASS 未定 · 2 份候选', 'ref-chip: ' + await chip.textContent());
      assert((await chip.getAttribute('data-state')) === 'error', 'ref-chip 应为 error');
      assert(await p2.locator('[data-testid=ab-btn]').isDisabled(), 'A/B 应停用');
      assert((await p2.getAttribute('[data-testid=ab-btn]', 'title')).includes('参考 ASS 未定'), 'A/B 提示没说明未定');
      const gate = await p2.textContent('[data-testid=gate-chip]');
      assert(gate.includes('门禁 未判定 · 参考未定'), '门禁: ' + gate);
      assert((await p2.getAttribute('[data-testid=gate-chip]', 'data-judge')) === 'none', '门禁 data-judge 应为 none (未判定)');
      assert((await p2.getAttribute('[data-testid=gate-chip]', 'data-state')) !== 'ready', '门禁无参考不该是 ready (绿)');
      assert(errs.length === 0, '页面错误: ' + errs.join(' | '));
    } finally { await c2.close(); }
  });
  await test('RF4', '三种 "没有参考" 文字互不相同: 无 (目录里没有) / 未定 (多份候选) / 出错 (来源有问题); 门禁写明对应原因, data-judge 都是 none', async () => {
    const seen = {};
    for (const mode of ['none', 'error', 'ambiguous']) {
      const { c2, p2, errs } = await refPage({ mode });
      try {
        const chip = (await p2.textContent('[data-testid=ref-chip]')).trim();
        const gate = await p2.textContent('[data-testid=gate-chip]');
        const tip = await p2.getAttribute('[data-testid=ab-btn]', 'title');
        assert((await p2.getAttribute('[data-testid=ref-chip]', 'data-source')) === mode, mode + ' data-source');
        assert((await p2.getAttribute('[data-testid=gate-chip]', 'data-judge')) === 'none', mode + ' data-judge');
        assert(await p2.locator('[data-testid=ab-btn]').isDisabled(), mode + ' A/B 应停用');
        seen[mode] = { chip, gate, tip };
        assert(errs.length === 0, '页面错误: ' + errs.join(' | '));
      } finally { await c2.close(); }
    }
    assert(seen.none.chip === '无参考 ASS · 目录里没有同名 .ass' && seen.none.gate.includes('未判定 · 无参考') && seen.none.tip.includes('没有文件名含歌名的 .ass'), 'none: ' + JSON.stringify(seen.none));
    assert(seen.error.chip === '参考 ASS 出错 · 未选' && seen.error.gate.includes('未判定 · 参考出错') && seen.error.tip.includes('跨目录'), 'error: ' + JSON.stringify(seen.error));
    assert(seen.ambiguous.chip === '参考 ASS 未定 · 2 份候选' && seen.ambiguous.gate.includes('未判定 · 参考未定'), 'ambiguous: ' + JSON.stringify(seen.ambiguous));
    for (const k of ['chip', 'gate', 'tip']) assert(new Set(Object.values(seen).map((x) => x[k])).size === 3, k + ' 三种状态有重复文字');
  });
  await test('RF2', '候选面板列出文件名/条数/修改时间; 点 "用这份" -> POST /api/ref; 之后顶栏/面板写明 "手动指定" 与指定时间, A/B 提示写真实文件名 (不再是 "ref")', async () => {
    const { c2, p2, errs, posts, B, dir } = await refPage({});
    try {
      await p2.click('[data-testid=ref-chip]');
      await p2.waitForSelector('[data-testid=ref-panel]');
      const rows = p2.locator('[data-testid=ref-cand]');
      assert((await rows.count()) === 2, '候选行数 ' + await rows.count());
      const t1 = await rows.nth(1).textContent();
      assert(t1.includes(B) && t1.includes('16510 条') && t1.includes('改于 2026-10-20 09:30:00'), '候选行: ' + t1);
      assert((await p2.textContent('[data-testid=ref-why]')).includes('2 份候选'), '面板没写原因');
      await rows.nth(1).locator('[data-testid=ref-use]').click();
      await p2.waitForSelector('[data-testid=ref-chip][data-source=manual]', { timeout: 6000 });
      assert(JSON.stringify(posts) === JSON.stringify([{ ass: dir + B }]), 'POST: ' + JSON.stringify(posts));
      assert((await p2.textContent('[data-testid=ref-chip]')).trim() === `参考 ${B} · 手动指定`, 'ref-chip: ' + await p2.textContent('[data-testid=ref-chip]'));
      assert((await p2.textContent('[data-testid=ref-why]')).includes('指定于 Sun 2026-11-15 11:50 PM CST (UTC+08:00)'), '没留指定时间');
      assert((await rows.nth(1).textContent()).includes('当前'), '选中行没标当前');
      const tip = await p2.getAttribute('[data-testid=ab-btn]', 'title');
      assert(!(await p2.locator('[data-testid=ab-btn]').isDisabled()) && tip.includes(`参考 = ${B} (手动指定)`), 'A/B 提示: ' + tip);
      assert(errs.length === 0, '页面错误: ' + errs.join(' | '));
    } finally { await c2.close(); }
  });
  await test('RF3', '指定失败 (POST 400): 面板写出服务端原因, 顶栏仍是 "未定", 无未处理错误', async () => {
    const { c2, p2, errs } = await refPage({ fail: true });
    try {
      await p2.click('[data-testid=ref-chip]');
      await p2.locator('[data-testid=ref-cand]').nth(0).locator('[data-testid=ref-use]').click();
      await p2.waitForSelector('[data-testid=ref-msg][data-error]', { timeout: 6000 });
      assert((await p2.textContent('[data-testid=ref-msg]')).startsWith('指定失败: 不是候选文件'), 'ref-msg: ' + await p2.textContent('[data-testid=ref-msg]'));
      assert((await p2.textContent('[data-testid=ref-chip]')).trim() === '参考 ASS 未定 · 2 份候选', '失败后顶栏变了');
      assert(errs.length === 0, '页面错误: ' + errs.join(' | '));
    } finally { await c2.close(); }
  });
  await test('RF5', '写入成功但重取 /api/project 失败: 面板不说 "指定失败", 而写明 "选择已保存 … 但界面刷新失败"; 顶栏 sync 标签 "参考 ASS 未刷新"; 界面保留旧的一致状态', async () => {
    const st = { projFail: true };
    const { c2, p2, errs, posts } = await refPage(st);
    try {
      await p2.click('[data-testid=ref-chip]');
      await p2.locator('[data-testid=ref-cand]').nth(1).locator('[data-testid=ref-use]').click();
      await p2.waitForSelector('[data-testid=ref-msg][data-error]', { timeout: 6000 });
      const msg = await p2.textContent('[data-testid=ref-msg]');
      assert(posts.length === 1 && msg.startsWith('选择已保存 (已写入 ref.json), 不用再点') && msg.includes('界面刷新失败') && !msg.includes('指定失败'), 'ref-msg: ' + msg);
      const sc = await p2.textContent('[data-testid=sync-chip]');
      assert(sc.includes('参考 ASS') && sc.includes('未刷新'), 'sync-chip: ' + sc);
      assert((await p2.textContent('[data-testid=ref-chip]')).trim() === '参考 ASS 未定 · 2 份候选', '重取失败时顶栏不该变 (旧状态保持一致)');
      st.projFail = false;   // 恢复后点重试 -> 变成手动指定, sync 标签消失
      await p2.click('[data-testid=sync-chip]');
      await p2.waitForSelector('[data-testid=ref-chip][data-source=manual]', { timeout: 6000 });
      await p2.waitForSelector('[data-testid=sync-chip]', { state: 'detached', timeout: 4000 });
      assert(errs.length === 0, '页面错误: ' + errs.join(' | '));
    } finally { await c2.close(); }
  });
  await test('RF8', '音频来源出错时顶栏 audio-chip 截断长错误 (宽度 <= 380px, 不撑开顶栏), 全文在 title', async () => {
    const c2 = await b.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
    const p2 = await c2.newPage();
    const long = 'playlist.json 的 audioUrl 不在 static/music/番/ 的候选里 (跨目录或文件不存在): ' + 'static/music/很长的目录名/'.repeat(8) + '歌.flac';
    await p2.route('**/api/project', async (r) => { const real = await (await r.fetch()).json(); real.audio_error = long; await r.fulfill({ json: real }); });
    try {
      await p2.goto(cfg.url, { waitUntil: 'load' });
      await p2.waitForSelector('[data-testid=audio-chip]', { timeout: 30000 });
      const w = await p2.evaluate(() => document.querySelector('[data-testid=audio-chip]').getBoundingClientRect().width);
      const tip = await p2.getAttribute('[data-testid=audio-chip]', 'title');
      assert(w <= 380 && tip.endsWith('歌.flac'), `宽 ${w}, title: ${tip}`);
      assert(await p2.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), '顶栏把页面撑出横向滚动');
    } finally { await c2.close(); }
  });
  await test('RF6', 'ref.json 出错 (err_kind=ref_json, 错误文字不以 "ref.json" 开头): 面板给出清除按钮; 点了 POST {ass:null}, 之后回到 "未定"; playlist 类错误不给清除按钮', async () => {
    const st = { mode: 'refjson' };
    const { c2, p2, errs, posts } = await refPage(st);
    try {
      await p2.click('[data-testid=ref-chip]');
      await p2.waitForSelector('[data-testid=ref-clear]', { timeout: 4000 });
      await p2.click('[data-testid=ref-clear]');
      await p2.waitForSelector('[data-testid=ref-chip][data-source=ambiguous]', { timeout: 6000 });
      assert(JSON.stringify(posts) === JSON.stringify([{ ass: null }]), 'POST: ' + JSON.stringify(posts));
      assert((await p2.locator('[data-testid=ref-clear]').count()) === 0, '清除后按钮还在');
      assert(!(await p2.getAttribute('[data-testid=ref-msg]', 'data-error')), 'ref-msg: ' + await p2.textContent('[data-testid=ref-msg]'));
      assert(errs.length === 0, '页面错误: ' + errs.join(' | '));
    } finally { await c2.close(); }
    const e = await refPage({ mode: 'error' });   // playlist 类错误: ref.json 里没东西可清, 不给按钮
    try {
      await e.p2.click('[data-testid=ref-chip]');
      await e.p2.waitForSelector('[data-testid=ref-panel]');
      assert((await e.p2.locator('[data-testid=ref-clear]').count()) === 0, 'playlist 错误不该有清除按钮');
    } finally { await e.c2.close(); }
  });
  await test('RF7', '清除成功但重取失败: 文案写 "已清除手动指定 (已从 ref.json 移除)", 不写 "已写入"', async () => {
    const st = { mode: 'refjson', projFail: true };
    const { c2, p2, errs } = await refPage(st);
    try {
      await p2.click('[data-testid=ref-chip]');
      await p2.click('[data-testid=ref-clear]');
      await p2.waitForSelector('[data-testid=ref-msg][data-error]', { timeout: 6000 });
      const msg = await p2.textContent('[data-testid=ref-msg]');
      assert(msg.startsWith('已清除手动指定 (已从 ref.json 移除), 不用再点') && msg.includes('界面刷新失败') && !msg.includes('已写入'), 'ref-msg: ' + msg);
      assert(errs.length === 0, '页面错误: ' + errs.join(' | '));
    } finally { await c2.close(); }
  });

  // ======================= libass 崩溃 / 无响应 (放最后: 会杀掉 worker, 用例内点重载恢复) =======================
  const ink = () => p.evaluate(() => { const c = document.querySelector('[data-testid=subs-out]'); const g = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < g.length; i += 4) if (g[i]) n++; return n; });
  const inkAt = async (t) => { await seek(t); await sleep(700); return ink(); };
  // 找一个有字的时刻: 句中点
  const tInk = async () => { for (const li of [LI, L2, 0, 8, 12]) { const t = await S(`s.lines[${li}] ? (s.lines[${li}].t[0] + s.lines[${li}].t[1]) / 2 : -1`); if (t > 0 && (await inkAt(t)) > 0) return t; } for (let t = 20; t < 200; t += 9) if ((await inkAt(t)) > 0) return t; throw new Error('找不到有字的时刻'); };
  const probeCalls = async (ms) => p.evaluate(async (ms) => { let n = 0; const un = window.__hx.clock.subscribe(() => { n++; }); const c = window.__hx.clock; for (let i = 0; i < 4; i++) { c.seek(10 + i * 7); await new Promise((r) => setTimeout(r, ms / 4)); } un(); return n; }, ms);
  const reloadChip = async () => {
    await p.click('[data-testid=octo-chip]');
    await p.waitForFunction(() => ['ready', 'partial'].includes(window.__hx.store.getState().octo), null, { timeout: 30000 });
    await sleep(300);
  };
  await test('OC1', 'clock 订阅者抛错被隔离: 其它订阅者照常收到回调, rAF 不断, 每个坏订阅者只报一次', async () => {
    const r = await p.evaluate(async () => {
      const c = window.__hx.clock; const e0 = window.__clockErrors || 0; let n = 0;
      const u1 = c.subscribe(() => { throw new Error('OC1 boom'); });
      const u2 = c.subscribe(() => { n++; });
      for (const t of [11, 22, 33]) { c.seek(t); await new Promise((r) => setTimeout(r, 120)); }
      let f = 0; const t0 = performance.now(); await new Promise((res) => { const g = () => { f++; if (performance.now() - t0 < 500) requestAnimationFrame(g); else res(); }; requestAnimationFrame(g); });
      u1(); u2();
      return { n, errs: (window.__clockErrors || 0) - e0, f };
    });
    assert(r.n >= 4, `好订阅者只收到 ${r.n} 次 (订阅 1 + seek 3)`);
    assert(r.errs >= 4, `坏订阅者抛错没被计数: ${r.errs}`);
    assert(r.f >= 20, `rAF 500ms 只跑了 ${r.f} 帧`);
  });
  await test('OC2', 'worker 抛错 (就绪后): octo=crashed, 顶栏红标签带时刻可点重载, 旧帧藏起 + 角标 "字幕渲染已停", clock 不死; 点重载后恢复出字', async () => {
    const t = await tInk();
    const before = await ink();
    const e0 = errors.length;
    await p.evaluate(() => window.__hxW.forEach((w) => w.postMessage({ target: 'OC2-bogus' })));
    await p.waitForFunction(() => window.__hx.store.getState().octo === 'crashed', null, { timeout: 5000 });
    const chip = p.locator('[data-testid=octo-chip]');
    assert((await chip.getAttribute('data-state')) === 'error', 'chip 不是 error');
    assert(/^libass 崩溃 @\d+:\d\d\.\d · 点击重载$/.test((await chip.textContent()).trim()), 'chip 文字: ' + await chip.textContent());
    assert((await p.getAttribute('[data-testid=subs-out]', 'data-halt')) === 'crashed', '画布没标 halt');
    assert(await p.evaluate(() => getComputedStyle(document.querySelector('[data-testid=subs-out]')).opacity) === '0', '旧帧没藏');
    const tag = p.locator('[data-testid=halt-tag]');
    assert((await tag.count()) === 1 && (await tag.textContent()) === '字幕渲染已停', '角标');
    assert(await tag.evaluate((e) => getComputedStyle(e).backgroundColor) === 'rgba(0, 0, 0, 0)', '角标不该有底框');
    const n = await probeCalls(800);
    assert(n >= 4, `崩溃后 clock 订阅者只收到 ${n} 次 (clock 被弄死)`);
    const newErr = errors.slice(e0);
    assert(newErr.every((x) => /Worker error/.test(x)), '除 SubtitlesOctopus 自己的 throw 外不该有页面错误 (尤其 TypeError): ' + newErr.join(' | '));
    errors.splice(e0);   // 那一条是库里 workerError 的 throw, 预期内
    await reloadChip();
    assert(!(await p.getAttribute('[data-testid=subs-out]', 'data-halt')), '重载后 halt 没清');
    assert((await p.locator('[data-testid=halt-tag]').count()) === 0, '重载后角标没消');
    const after = await inkAt(t);
    assert(after > 0, `重载后 t=${t.toFixed(2)} 没出字 (崩前 ${before})`);
  });
  await test('OC4', '监视器尺寸 0 -> 恢复 (useOcto 依赖变化但实例不重建) 之后, worker 崩溃仍能被发现: octo=crashed (不是静默)', async () => {
    await tInk();
    const box = '[data-testid=monitor]';
    await p.evaluate((q) => { document.querySelector(q).style.display = 'none'; }, box);
    await p.waitForFunction(() => document.querySelector('[data-testid=frame-out]') === null || document.querySelector('[data-testid=frame-out]').getBoundingClientRect().width === 0, null, { timeout: 3000 }).catch(() => {});
    await sleep(400);
    await p.evaluate((q) => { document.querySelector(q).style.display = ''; }, box);
    await sleep(800);
    assert(['ready', 'partial'].includes(await S('s.octo')), '恢复尺寸后 octo 应仍就绪: ' + await S('s.octo'));
    const e0 = errors.length;
    await p.evaluate(() => window.__hxW.forEach((w) => w.postMessage({ target: 'OC4-bogus' })));
    await p.waitForFunction(() => window.__hx.store.getState().octo === 'crashed', null, { timeout: 5000 }).catch(() => {});
    assert((await S('s.octo')) === 'crashed', '尺寸变化后崩溃回调被吞: octo=' + await S('s.octo'));
    errors.splice(e0);
    await reloadChip();
  });
  await test('OC3', 'worker 被终止 (无任何事件): 看门狗判 stalled, 顶栏 "libass 无响应 · 点击重载", 旧帧藏起 + 角标; 点重载恢复', async () => {
    const t = await tInk();
    await p.evaluate(() => window.__hxW.forEach((w) => w.terminate()));
    await p.waitForFunction(() => window.__hx.store.getState().octo === 'stalled', null, { timeout: 8000 });
    assert((await p.textContent('[data-testid=octo-chip]')).trim() === 'libass 无响应 · 点击重载', 'chip 文字');
    assert((await p.getAttribute('[data-testid=subs-out]', 'data-halt')) === 'stalled', '画布没标 halt');
    assert((await p.textContent('[data-testid=halt-tag]')) === '字幕渲染已停', '角标');
    const n = await probeCalls(800);
    assert(n >= 4, `clock 订阅者只收到 ${n} 次`);
    await reloadChip();
    assert((await inkAt(t)) > 0, '重载后没出字');
    console.log('PROBE OC3 frame_max_ms=' + (await p.getAttribute('[data-testid=subs-out]', 'data-octo-frame-max-ms')) + ' ping_max_ms=' + (await p.getAttribute('[data-testid=subs-out]', 'data-octo-ping-max-ms')));
  });

  await reset();
  const sh = await p.evaluate(() => [document.documentElement.scrollHeight, innerHeight]);
  console.log('RESULT' + JSON.stringify({ results, errors, scroll: sh }));
  await b.close();
})().catch((e) => { console.log('RESULT' + JSON.stringify({ fatal: String(e && e.stack || e), results })); process.exit(1); });
