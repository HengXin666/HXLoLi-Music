/* 歌词位置预设用例. 由 e2e_placement.py 起服务 (指向工程的临时拷贝) 后调用:
 *   node e2e_placement.js <playwright 所在目录> <cfg.json>
 * 操作走真实点击; window.__hx 只读状态做断言. 一致性: 同一时刻 "预览画布" 对 "应用重跑后的真实画布" 比 8px 网格墨迹 (IoU) 与包围盒.
 */
const fs = require('fs');
const crypto = require('crypto');
const { createRequire } = require('node:module');
const req = createRequire(process.argv[2] + '/x.js');
const { chromium } = req('playwright');
const cfg = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));

const results = [];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function assert(c, msg) { if (!c) throw new Error(msg); }
const sha = (f) => (fs.existsSync(f) ? crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex').slice(0, 12) : null);
const OUT = cfg.proj + '/out.ass', PJ = cfg.proj + '/placement.json', FXA = cfg.proj + '/fx_alt.py';

(async () => {
  const b = await chromium.launch({ executablePath: cfg.chrome, args: ['--no-sandbox', '--disable-dev-shm-usage', '--autoplay-policy=no-user-gesture-required'] });
  const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', (e) => errors.push(String(e).slice(0, 300)));
  await p.goto(cfg.url, { waitUntil: 'load' });
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 30000 });
  await p.waitForFunction(() => window.__hx.store.getState().octo === 'ready', null, { timeout: 40000 });
  await p.waitForFunction(() => !!window.__hx.store.getState().place, null, { timeout: 10000 });
  await sleep(500);
  const S = (expr) => p.evaluate(`(() => { const s = window.__hx.store.getState(); return ${expr}; })()`);
  const seek = async (t) => { await p.evaluate((t) => { window.__hx.clock.pause(); window.__hx.clock.seek(t); }, t); await sleep(900); };
  const openPanel = async () => { if (!(await p.locator('[data-testid=placement-panel]').isVisible().catch(() => false))) await p.click('[data-testid=place-btn]'); await p.waitForSelector('[data-testid=placement-panel]'); };
  const pick = async (v, h) => { await p.click(`[data-testid=place-${v}-${h}]`); await p.waitForFunction(() => { const s = window.__hx.store.getState(); return !s.placeCand || (s.placeLines && s.placeLines.length); }); await sleep(400); };
  const OUT0 = sha(OUT);
  const applyAndWait = async () => {
    const seq0 = await S('s.place.job.seq');
    await p.click('[data-testid=place-apply]');
    await p.waitForFunction((q) => { const s = window.__hx.store.getState(); return s.place.job.seq > q && !s.place.job.running; }, seq0, { timeout: 120000 });
    await sleep(600);
  };
  const waitIdle = async (ms = 120000) => { await p.waitForFunction(() => { const s = window.__hx.store.getState(); return s.place && !s.place.job.running; }, null, { timeout: ms }); await sleep(600); };
  // 画布墨迹: 1920 坐标下 8px 网格, alpha > 40 的格子; 返回格子集合与包围盒
  const ink = (sel) => p.evaluate((sel) => {
    const c = document.querySelector(sel); if (!c) return null;
    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    const kx = c.width / 1920, ky = c.height / 1080, G = 8, cells = new Set();
    let x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1;
    for (let y = 0; y < c.height; y += 2) for (let x = 0; x < c.width; x += 2) {
      if (d[(y * c.width + x) * 4 + 3] <= 40) continue;
      const X = x / kx, Y = y / ky;
      cells.add(((Y / G) | 0) * 1000 + ((X / G) | 0));
      if (X < x0) x0 = X; if (X > x1) x1 = X; if (Y < y0) y0 = Y; if (Y > y1) y1 = Y;
    }
    return { cells: [...cells], box: [Math.round(x0), Math.round(y0), Math.round(x1), Math.round(y1)], n: cells.size };
  }, sel);
  const iou = (a, b) => { const A = new Set(a.cells), B = new Set(b.cells); let i = 0; for (const x of A) if (B.has(x)) i++; return +(i / (A.size + B.size - i)).toFixed(3); };
  const shot = async (name) => { if (cfg.shots) await p.locator('[data-testid=frame-out]').screenshot({ path: `${cfg.shots}/${name}.png` }); };

  async function test(id, row, fn) {
    if (cfg.only && cfg.only.length && !cfg.only.includes(id)) return;
    const t0 = Date.now();
    const r = { id, row };
    try { r.info = await fn(); r.ok = true; }
    catch (e) { r.ok = false; r.err = String(e.message || e).slice(0, 300); }
    r.ms = Date.now() - t0; results.push(r);
  }
  const T31 = await S("(() => { const l = s.lines.find((x) => x.name === 'p31'); return +(l.chars[Math.floor(l.chars.length / 2)].s + 0.3).toFixed(2); })()");

  await test('P1', '面板: 顶栏"位置"打开; 显示"现在生效"及来源 (无 placement.json = 默认); 未选时不预览', async () => {
    await openPanel();
    const now = await p.textContent('[data-testid=place-current]');
    const src = await p.getAttribute('[data-testid=place-current]', 'data-source');
    assert(/现在生效/.test(now) && /底中/.test(now) && src === 'default' && /默认/.test(now), now + ' ' + src);
    assert(!(await p.locator('[data-testid=monitor-preview]').count()), '未选就出了预览');
    assert((await p.locator('[data-testid=place-apply]').isDisabled()), '未改就能应用');
    return { now: now.trim() };
  });

  await test('P2', '选 底右: 立即预览 (预览画布 + 醒目提示条含"跨区域特效不跟随"), 面板标"正在预览", 33 句位移来自服务端', async () => {
    await openPanel(); await seek(T31);
    await pick('bottom', 'right');
    await p.waitForSelector('[data-testid=monitor-preview]');
    const note = await p.locator('[data-testid=preview-note]');
    const bb = await note.boundingBox(); const fr = await p.locator('[data-testid=frame-out]').boundingBox();
    const txt = await note.textContent();
    assert(/近似预览/.test(txt) && /跨区域特效不跟随/.test(txt) && /以应用后重跑为准/.test(txt), txt);
    assert(bb.width > fr.width * 0.9 && bb.height >= 24, `提示条不够醒目 ${JSON.stringify(bb)} / 画面 ${fr.width}`);
    const fs_ = await note.evaluate((e) => parseFloat(getComputedStyle(e).fontSize));
    const cand = await p.textContent('[data-testid=place-cand]');
    assert(/正在预览/.test(cand) && /底右/.test(cand), cand);
    const n = await S('s.placeLines.length');
    assert(n === 33, '句数 ' + n);
    const blocks = +(await p.getAttribute('[data-testid=monitor-preview]', 'data-blocks'));
    assert(blocks >= 2, '当前时刻没有块被平移: ' + blocks);
    // 预览确实把字右移: 预览墨迹左沿 > 原画布墨迹左沿
    const a = await ink('canvas[data-hidpi=monitor]'), pv = await ink('canvas[data-hidpi=monitor-preview]');
    assert(pv.box[0] > a.box[0] + 150, `预览没右移: 原 ${a.box} 预览 ${pv.box}`);
    await shot('p2_preview_bottom_right');
    return { note_h: Math.round(bb.height), note_w: Math.round(bb.width), frame_w: Math.round(fr.width), font: fs_, blocks, orig_box: a.box, prev_box: pv.box };
  });

  await test('P3', '选回 底中 (= 现在生效): 预览关闭, 提示条消失, 原画布可见', async () => {
    await openPanel(); await pick('bottom', 'center');
    await sleep(300);
    assert(!(await p.locator('[data-testid=monitor-preview]').count()) && !(await p.locator('[data-testid=preview-note]').count()), '预览没关');
    const vis = await p.evaluate(() => document.querySelector('canvas[data-hidpi=monitor]').style.visibility);
    assert(vis === 'visible', vis);
  });

  // 一致性: 记预览墨迹 -> 应用 -> 同一时刻量真实画布
  const consist = async (v, h, order) => {
    await openPanel(); await seek(T31);
    const real0 = await ink('canvas[data-hidpi=monitor]');
    if (order) {
      await pick(v, h);
      const sig0 = await S('JSON.stringify(s.placeLines || null)');
      await p.click(`[data-testid=place-order-${order}]`);
      await p.waitForFunction(([o, sg]) => { const s = window.__hx.store.getState(); return s.placeCand && s.placeCand.order === o && s.placeLines && s.placeLines.length === 33 && JSON.stringify(s.placeLines) !== sg; }, [order, sig0], { timeout: 10000 });
    } else await pick(v, h);
    await seek(T31);
    const pv = await ink('canvas[data-hidpi=monitor-preview]');
    await shot(`cmp_${v}_${h}${order ? '_' + order : ''}_preview`);
    const rev0 = await S('s.assRev');
    await applyAndWait();
    await p.waitForFunction((r) => window.__hx.store.getState().assRev > r, rev0, { timeout: 30000 });
    await seek(T31); await sleep(500);
    const real = await ink('canvas[data-hidpi=monitor]');
    await shot(`cmp_${v}_${h}${order ? '_' + order : ''}_real`);
    const r = { iou: iou(pv, real), prev_box: pv.box, real_box: real.box, real0_box: real0.box, box_diff: pv.box.map((x, i) => x - real.box[i]) };
    assert(r.iou >= 0.70, `IoU ${r.iou} < 0.70`);
    const ctr = (b) => [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
    const dist = (a, b) => Math.hypot(ctr(a)[0] - ctr(b)[0], ctr(a)[1] - ctr(b)[1]);
    // closer: 二级兜底. 实践中最先失败的是前面的 assRev 等待 (应用没生效 -> 30s 超时) 或 IoU (内容变了但位置不对);
    // 保留是因为它能区分 "真实墨迹靠近了预览" 和 "只是碰巧重叠". 别删.
    // 变异验证 2026-11-10: app.py placement_apply 注掉三条 os.replace -> 全套 5/13, P8-P10 卡在上面的 assRev 等待 (30s 超时), 未走到 IoU/closer.
    r.closer = Math.round(dist(real0.box, pv.box) - dist(real.box, pv.box));
    assert(r.closer > 150, `应用后真实墨迹没靠近预览: ${real0.box} -> ${real.box}, 预览 ${pv.box}`);
    return r;
  };

  await test('P4', '应用中: 按钮/九宫格禁用, 顶栏显示生成中, 第二次 POST 被 409 拒; 状态来自服务端', async () => {
    await openPanel(); await pick('bottom', 'right');
    const o0 = sha(OUT);
    await p.click('[data-testid=place-apply]');
    await p.waitForFunction(() => window.__hx.store.getState().place.job.running, null, { timeout: 5000 });
    const dis = await p.evaluate(() => ['place-apply', 'place-top-left', 'place-order-cn_top', 'place-gap-tight'].map((id) => document.querySelector(`[data-testid=${id}]`).disabled));
    const top = await p.textContent('[data-testid=place-btn]');
    const second = await p.evaluate(async () => (await fetch('/api/placement', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ v: 'top' }) })).status);
    assert(dis.every(Boolean), '生成中未禁用: ' + dis);
    assert(/生成中/.test(top) && second === 409, `顶栏 ${top} / 第二次 POST ${second}`);
    await waitIdle();
    return { disabled: dis, second_post: second, out_before: o0 };
  });

  await test('P5', '应用后经 /api/watch 拿到新成品: 现在生效=底右 (placement.json), 预览自动关闭, out.ass 已换, 画布重载', async () => {
    const st = await S('({ cur: s.place.current, src: s.place.source, ok: s.place.job.ok, cand: s.placeCand, rev: s.assRev })');
    const now = await p.textContent('[data-testid=place-current]');
    const pj = fs.existsSync(PJ) ? JSON.parse(fs.readFileSync(PJ, 'utf8')) : null;
    assert(st.ok === true && st.cur.h === 'right' && st.src === 'file' && !st.cand, JSON.stringify(st));
    assert(/底右/.test(now) && /placement\.json/.test(now), now);
    assert(pj && pj.h === 'right', JSON.stringify(pj));
    assert(st.rev >= 1, 'assRev 没涨, 画布没重载');
    return { now: now.trim(), out: sha(OUT), assRev: st.rev };
  });

  await test('P6', '失败回滚: 生成器写坏后应用 顶中 -> 提示失败, 现在生效仍是底右, placement.json 与 out.ass sha 不变', async () => {
    const o0 = sha(OUT), p0 = sha(PJ);
    const bak = fs.readFileSync(FXA);
    fs.appendFileSync(FXA, '\nthis is not python(\n');
    try {
      await openPanel(); await pick('top', 'center');
      await p.click('[data-testid=place-apply]');
      await p.waitForFunction(() => window.__hx.store.getState().place.job.running, null, { timeout: 5000 }).catch(() => {});
      await waitIdle();
    } finally { fs.writeFileSync(FXA, bak); }
    const st = await S('({ cur: s.place.current, ok: s.place.job.ok, err: s.place.job.error })');
    const msg = await p.textContent('[data-testid=place-msg]');
    assert(st.ok === false && /生成器失败/.test(st.err || ''), JSON.stringify(st).slice(0, 200));
    assert(st.cur.v === 'bottom' && st.cur.h === 'right', '现在生效被改了 ' + JSON.stringify(st.cur));
    assert(sha(OUT) === o0 && sha(PJ) === p0, `out ${o0}->${sha(OUT)} placement ${p0}->${sha(PJ)}`);
    assert(/失败/.test(msg), msg);
    assert(!fs.existsSync(cfg.proj + '/.placement-run') || fs.readdirSync(cfg.proj + '/.placement-run').length === 0, '临时目录有残留');
    return { out: o0, placement: p0, msg: msg.trim().slice(0, 60) };
  });

  await test('P7', '九个位置各点一遍: 每次 33 句位移, 预览画布在场块 >= 2, 提示条在; 页面无报错', async () => {
    await openPanel(); await seek(T31);
    const seen = [];
    for (const v of ['top', 'middle', 'bottom']) for (const h of ['left', 'center', 'right']) {
      await pick(v, h);
      const cur = await S('s.place.current');
      if (cur.v === v && cur.h === h) { seen.push(`${v}-${h}:当前`); continue; }
      const n = await S('s.placeLines.length');
      const blocks = +(await p.getAttribute('[data-testid=monitor-preview]', 'data-blocks'));
      assert(n === 33 && blocks >= 2 && (await p.locator('[data-testid=preview-note]').count()) === 1, `${v}-${h}: n=${n} blocks=${blocks}`);
      const pv = await ink('canvas[data-hidpi=monitor-preview]');
      seen.push(`${v}-${h}:${pv.box.join(',')}`);
      await shot(`p7_${v}_${h}`);
    }
    assert(!errors.length, errors.join(' | '));
    return { seen };
  });

  const C = {};
  await test('P8', '一致性 顶左: 预览 vs 应用重跑后真实画布 (同一时刻, 8px 网格 IoU, 包围盒差)', async () => (C.tl = await consist('top', 'left')));
  await test('P9', '一致性 中中: 同上', async () => (C.mc = await consist('middle', 'center')));
  await test('P10', '一致性 底右 中上日下: 同上 (语言顺序互换)', async () => (C.br = await consist('bottom', 'right', 'cn_top')));
  // 行距: 预览 -> 应用 -> placement.json 的 gap 生效, 新 out.ass 与基线不同, p31 时刻真实墨迹落在 out.ass 自己写的 p31 band 内 (8px 容差)
  const bandOf = (name) => { const m = fs.readFileSync(OUT, 'utf8').match(new RegExp('; assfx-band: ' + name + ' ([\\d.]+) ([\\d.]+) ([\\d.]+) ([\\d.]+)')); return m ? m.slice(1, 5).map(Number) : null; };
  const gapCase = async (v, h, gap, order = 'jp_top') => {
    await openPanel(); await seek(T31);
    await pick(v, h);
    await p.click(`[data-testid=place-order-${order}]`);   // 显式定语言顺序, 不继承上一条用例的状态
    await p.click(`[data-testid=place-gap-${gap}]`);
    await p.waitForFunction(([g, o]) => { const s = window.__hx.store.getState(); return s.placeCand && s.placeCand.gap === g && s.placeCand.order === o && s.placeLines && s.placeLines.length === 33; }, [gap, order], { timeout: 10000 });
    assert((await p.locator('[data-testid=preview-note]').count()) === 1, '行距预览没出提示条');
    const rev0 = await S('s.assRev');
    await applyAndWait();
    await p.waitForFunction((r) => window.__hx.store.getState().assRev > r, rev0, { timeout: 30000 });
    const st = await S('({ ok: s.place.job.ok, cur: s.place.current, src: s.place.source })');
    const pj = JSON.parse(fs.readFileSync(PJ, 'utf8'));
    assert(st.ok === true && st.src === 'file' && st.cur.v === v && st.cur.h === h && st.cur.gap === gap && st.cur.order === order, JSON.stringify(st));
    assert(pj.v === v && pj.h === h && pj.gap === gap && pj.order === order, JSON.stringify(pj));
    const now = await p.textContent('[data-testid=place-current]');
    assert(new RegExp(gap === 'tight' ? '紧' : '松').test(now), '现在生效没显示行距 ' + now);
    const out = sha(OUT); assert(out !== OUT0, '行距没进成品, sha 仍是基线');
    await seek(T31); await sleep(500);
    const real = await ink('canvas[data-hidpi=monitor]'); const band = bandOf('p31');
    assert(band, 'out.ass 里没有 p31 band');
    assert(real.n > 0 && real.box[1] >= band[1] - 8 && real.box[3] <= band[3] + 8, `墨迹出 band: ink ${real.box} band ${band}`);
    await shot(`gap_${gap}_${v}_${h}_real`);
    return { out, band, ink: real.box, now: now.trim() };
  };
  await test('P12', '行距 紧 + 底中: 预览 -> 应用, placement.json gap=tight, 现在生效显示"紧", p31 真实墨迹在 band 内', async () => gapCase('bottom', 'center', 'tight'));
  // P13 用非默认的 cn_top: jp_top 是默认值, 点它 onClick 坏了状态也不变, 抓不住; 换 cn_top 后 P13 与之后 P11 切回 jp_top 都是真切换.
  // 变异验证 2026-11-10: place-order-* onClick 置空时 P11-P13 仍全绿 (当时只点默认 jp_top), 只有 P10 红; 改用 cn_top 的结果见本轮报告.
  await test('P13', '行距 松 + 顶中 + 中上日下: 同上 (gap=loose, 顶部撞边方向, 非默认语言顺序)', async () => gapCase('top', 'center', 'loose', 'cn_top'));
  await test('P11', '回默认 (底中 日上中下): 应用后 out.ass 回到初始 sha', async () => {
    await openPanel(); await pick('bottom', 'center');
    await p.click('[data-testid=place-order-jp_top]'); await p.click('[data-testid=place-gap-normal]');
    await p.waitForFunction(() => { const s = window.__hx.store.getState(); return s.placeCand && s.placeCand.order === 'jp_top' && s.placeCand.gap === 'normal'; }, null, { timeout: 10000 });
    const cand = await S('s.placeCand');
    assert(cand && cand.v === 'bottom' && cand.h === 'center' && cand.order === 'jp_top' && cand.gap === 'normal', '候选不是默认 ' + JSON.stringify(cand));
    await applyAndWait();
    const out = sha(OUT);
    assert(out === OUT0, `out.ass 没回到初始 ${OUT0} -> ${out}`);
    return { out, out0: OUT0, placement: fs.readFileSync(PJ, 'utf8').replace(/\s/g, '') };
  });

  const sh = await p.evaluate(() => [document.documentElement.scrollHeight, innerHeight, document.documentElement.scrollWidth, innerWidth]);
  console.log('RESULT' + JSON.stringify({ results, errors, scroll: sh }));
  await b.close();
})().catch((e) => { console.log('RESULT' + JSON.stringify({ fatal: String(e && e.stack || e), results })); process.exit(1); });
