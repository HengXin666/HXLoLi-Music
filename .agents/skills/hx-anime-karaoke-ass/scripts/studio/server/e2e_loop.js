/* 看, 挑, 改, 证 全程在台上: 选一句 -> R 换一个构想 -> 闭环面板 "生成候选" -> 看 A / 看 B (A/B 切换) -> 冻结 B
 * -> 服务端 accept pick (picks.json -> 整首重跑 -> G2 三条 + 隔离核对 -> 冻结) -> 面板与 review.jsonl 写明状态.
 *   node e2e_loop.js <playwright 所在目录> <cfg.json>     (由 e2e_loop.py 在工程副本上起服务后调用)
 * 操作一律真实鼠标/键盘; window.__hx 只读状态做断言.
 */
const fs = require('fs');
const { createRequire } = require('node:module');
const req = createRequire(process.argv[2] + '/x.js');
const { chromium } = req('playwright');
const cfg = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const results = [];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function assert(c, msg) { if (!c) throw new Error(msg); }

(async () => {
  const b = await chromium.launch({ executablePath: cfg.chrome, args: ['--no-sandbox', '--disable-dev-shm-usage', '--autoplay-policy=no-user-gesture-required'] });
  const p = await (await b.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
  const errors = [];
  p.on('pageerror', (e) => errors.push(String(e).slice(0, 300)));
  const S = (expr) => p.evaluate(`(() => { const s = window.__hx.store.getState(); return ${expr}; })()`);
  const loop = async () => (await (await p.request.get(cfg.url + 'api/loop')).json());
  const test = async (id, row, fn) => {
    const t0 = Date.now();
    try { await fn(); results.push({ id, row, ok: true, ms: Date.now() - t0 }); }
    catch (e) { results.push({ id, row, ok: false, ms: Date.now() - t0, err: String(e.message || e).slice(0, 400) }); }
  };
  const waitJob = async (kind, ms = 240000) => {
    const t0 = Date.now();
    for (;;) {
      const j = (await loop()).job;
      if (j.kind === kind && !j.running && j.ok !== null) return j;
      if (Date.now() - t0 > ms) throw new Error(`${kind} 超时: ${JSON.stringify(j).slice(0, 300)}`);
      await sleep(400);
    }
  };
  let rid = null, iid = null;
  try {
    await p.goto(cfg.url, { waitUntil: 'load' });
    await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 30000 });
    await p.waitForFunction(() => window.__hx.store.getState().lines.length > 0, null, { timeout: 30000 });
    const LI = await S(`s.lines.findIndex((l, i) => i >= ${cfg.line} && l.chars.length >= 3)`);

    await test('L1', '无参考时对比对象自动退到上一版 / 有参考时是参考; 顶栏有 "闭环" 入口', async () => {
      const pj = await S('s.project');
      assert(pj.cmp, '服务端没给 cmp');
      if (cfg.expect_ref) assert(pj.cmp.kind === 'ref', 'cmp 应为参考: ' + pj.cmp.kind);
      else assert(['prev', 'none'].includes(pj.cmp.kind), '无参考时 cmp 应为上一版/无: ' + pj.cmp.kind);
      assert(await p.locator('[data-testid=loop-chip]').isVisible(), '没有闭环入口');
    });

    await test('L2', '选整句 -> R 换一个构想: 标注落盘带 status=open', async () => {
      const t = await S(`s.lines[${LI}].t[0] + 0.05`);
      await p.evaluate((t) => window.__hx.clock.seek(t), t);
      await sleep(600);
      await p.locator(`[data-i="${LI}"] [data-testid=lineno]`).click();
      assert((await S('s.ranges.length')) > 0, '行号没选中整句');
      await p.keyboard.press('r');
      await p.waitForFunction(() => window.__hx.store.getState().reviews.some((r) => r.kind === 'redo'), null, { timeout: 5000 });
      const r = (await S('s.reviews')).filter((x) => x.kind === 'redo').pop();
      rid = r.id;
      assert(r.status === 'open', 'status 不是 open: ' + r.status);
    });

    await test('L3', '闭环面板列出这条标注与状态; 点 "生成候选" -> 只重跑本单元出 2-3 个候选', async () => {
      await p.locator('[data-testid=loop-chip]').click();
      const row = p.locator(`[data-testid=loop-row][data-id="${rid}"]`);
      await row.waitFor({ timeout: 8000 });
      assert((await row.getAttribute('data-status')) === 'open', '面板状态不是 open');
      await row.locator('[data-testid=cand-gen]').click();
      const j = await waitJob('cands');
      assert(j.ok, '生成候选失败: ' + j.error + '\n' + j.out.slice(-800));
      await p.waitForFunction((rid) => { const st = window.__hx.store.getState().loopState; const r = st && st.reviews.find((x) => x.id === rid); return r && r.issue && st.cands[r.issue]; }, rid, { timeout: 10000 });
      const st = await S('s.loopState');
      const r = st.reviews.find((x) => x.id === rid);
      iid = r.issue;
      const cs = st.cands[iid];
      assert(cs.items.length >= 2 && cs.items.length <= 3, '候选数 ' + cs.items.length);
      assert(r.status === 'proposed', '有候选后状态应为 proposed: ' + r.status);
      assert(j.out.includes('只重跑单元'), '不是只重跑单元');
      await row.locator('[data-testid=cand-show-A]').waitFor({ timeout: 5000 });
    });

    await test('L4', '看 A / 看 B: 监视器对比对象换成候选并进 A/B, 角标写明候选', async () => {
      const row = p.locator(`[data-testid=loop-row][data-id="${rid}"]`);
      for (const c of ['A', 'B']) {
        await row.locator(`[data-testid=cand-show-${c}]`).click();
        await p.waitForFunction((c) => { const s = window.__hx.store.getState(); return s.project.cmp && s.project.cmp.kind === 'cand' && s.project.cmp.c === c && s.compare === 'ab'; }, c, { timeout: 8000 });
        await p.waitForFunction(() => document.querySelector('[data-testid=monitor]')?.dataset.refReady, null, { timeout: 20000 });
        const badge = await p.locator('[data-testid=ab-badge]').textContent();
        assert(badge.includes('候选 ' + c), '角标不是候选 ' + c + ': ' + badge);
        const txt = await (await p.request.get(cfg.url + 'api/ass/ref')).text();
        const cand = await (await p.request.get(cfg.url + `api/ass/cand?issue=${iid}&c=${c}`)).text();
        assert(txt === cand, '/api/ass/ref 不是候选 ' + c);
      }
    });

    await test('L5', '冻结 B: accept pick -> G2 通过 + 隔离核对 -> 状态 done, 未选的进构想记录, out.ass 变了只在本单元', async () => {
      const before = await (await p.request.get(cfg.url + 'api/ass/out')).text();
      const row = p.locator(`[data-testid=loop-row][data-id="${rid}"]`);
      await row.locator('[data-testid=cand-pick-B]').click();
      const j = await waitJob('pick');
      assert(j.ok, 'pick 失败: ' + j.error + '\n' + j.out.slice(-1500));
      assert(/PICK OK/.test(j.out), '没有 PICK OK');
      const st = await loop();
      const r = st.reviews.find((x) => x.id === rid);
      assert(r.status === 'done', '状态应为 done: ' + r.status);
      const last = r.changes[r.changes.length - 1];
      assert(last.g2 && last.g2.ok && last.g2.isolation === 'ok', 'changes 里没有 G2/隔离核对: ' + JSON.stringify(last));
      assert(JSON.stringify(last.g2.changed) === JSON.stringify([st.cands[iid].unit]), 'G2 实际变了的单元不只本单元: ' + JSON.stringify(last.g2.changed));
      assert(st.cands[iid].picked === 'B', 'picked != B');
      const left = st.ideas.filter((x) => x.issue === iid).map((x) => x.cand).sort();
      assert(left.length === st.cands[iid].items.length - 1 && !left.includes('B'), '构想记录不对: ' + left);
      assert(st.picks[st.cands[iid].unit], 'picks.json 没有本单元');
      const after = await (await p.request.get(cfg.url + 'api/ass/out')).text();
      assert(after !== before, 'out.ass 没变');
      await p.waitForFunction((rid) => { const st = window.__hx.store.getState().loopState; return st && st.reviews.find((x) => x.id === rid)?.status === 'done'; }, rid, { timeout: 10000 });
      assert((await row.getAttribute('data-status')) === 'done', '面板没显示 done');
    });

    await test('L6', '冻结后对比对象回到自动 (无参考 = 上一版); review.jsonl 每条都有 status', async () => {
      await p.waitForFunction((ref) => { const c = window.__hx.store.getState().project.cmp; return c && c.kind === (ref ? 'ref' : 'prev'); }, cfg.expect_ref, { timeout: 10000 });
      const lines = fs.readFileSync(cfg.review, 'utf8').split('\n').filter((x) => x.trim()).map((x) => JSON.parse(x));
      assert(lines.length > 0 && lines.every((x) => typeof x.status === 'string' && Array.isArray(x.changes)), 'review.jsonl 有记录缺 status/changes');
    });
  } catch (e) {
    results.push({ id: 'FATAL', row: 'fatal', ok: false, ms: 0, err: String(e.stack || e).slice(0, 1500) });
  }
  console.log('RESULT' + JSON.stringify({ results, errors }));
  await b.close();
})();
