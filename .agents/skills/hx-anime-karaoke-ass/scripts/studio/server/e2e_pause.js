// 暂停回归: 点播放 -> 走一段 -> 点暂停, 暂停后 video.paused 必须为 true 且 currentTime 不再前进. 用法见 e2e_pause.py.
const [pw, cfgPath] = process.argv.slice(2);
const { chromium } = require(require('path').join(pw, 'node_modules', 'playwright'));
const cfg = JSON.parse(require('fs').readFileSync(cfgPath, 'utf8'));
(async () => {
  const b = await chromium.launch({ executablePath: cfg.chrome || undefined, args: ['--no-sandbox', '--disable-dev-shm-usage', '--autoplay-policy=no-user-gesture-required'] });
  const pg = await b.newPage({ viewport: { width: 1600, height: 900 } });
  await pg.goto(cfg.url);
  await pg.waitForSelector('[data-testid=video-out]', { timeout: 30000 });
  await pg.waitForFunction(() => document.querySelector('[data-testid=video-out]').readyState >= 2, null, { timeout: 30000 });
  const st = () => pg.evaluate(() => { const v = document.querySelector('[data-testid=video-out]'); return { paused: v.paused, ct: +v.currentTime.toFixed(3) }; });
  const res = [];
  for (let round = 0; round < (cfg.rounds || 5); round++) {
    await pg.click('[data-testid=play]');
    await pg.waitForTimeout(1500 + round * 137);
    const play = await st();
    await pg.click('[data-testid=play]');
    await pg.waitForTimeout(150);
    const a = await st();
    await pg.waitForTimeout(1500);
    const c = await st();
    res.push({ round, play, a150: a, a1650: c, ok: !play.paused && a.paused && c.paused && Math.abs(c.ct - a.ct) < 0.001 });
  }
  console.log('RESULT ' + JSON.stringify({ ok: res.every((r) => r.ok), res }));
  await b.close();
})().catch((e) => { console.log('RESULT ' + JSON.stringify({ ok: false, err: String(e) })); process.exit(1); });
