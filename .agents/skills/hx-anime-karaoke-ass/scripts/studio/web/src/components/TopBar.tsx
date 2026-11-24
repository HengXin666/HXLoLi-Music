import { sync, useStore } from '../lib/store';
import { baseName, REF_SRC } from '../lib/actions';
import PlacementPanel from './PlacementPanel';
import RefPanel from './RefPanel';
import LoopPanel from './LoopPanel';
import s from './Bars.module.css';

// 门禁没有阈值时写明为什么 (三种不同: 根本没有 / 有几份没定 / 来源出错)
const GATE_WHY: Record<string, string> = { none: '无参考', ambiguous: '参考未定', error: '参考出错' };
const SYNC_LABEL: Record<string, string> = { ass: '监视器字幕', data: '歌词/门禁', review: '标注', edl: 'EDL', place: '位置状态', ref: '参考 ASS' };

const fmtT = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`;

export default function TopBar() {
  const p = useStore((x) => x.project);
  const out = useStore((x) => x.out);
  const edl = useStore((x) => x.edl);
  const octo = useStore((x) => x.octo);
  const octoErr = useStore((x) => x.octoErr);
  const octoMissing = useStore((x) => x.octoMissing);
  const octoAt = useStore((x) => x.octoAt);
  const fontsMissing = useStore((x) => x.fontsMissing);
  const fontsUnparsed = useStore((x) => x.fontsUnparsed);
  const place = useStore((x) => x.place);
  const placeOpen = useStore((x) => x.placeOpen);
  const refOpen = useStore((x) => x.refOpen);
  const loopOpen = useStore((x) => x.loopOpen);
  const loopSt = useStore((x) => x.loopState);
  const pending = loopSt ? loopSt.reviews.filter((r) => !['done', 'dropped', 'noted'].includes(r.status)).length : 0;
  const set = useStore((x) => x.set);
  const live = useStore((x) => x.live);
  const syncErr = useStore((x) => x.syncErr);
  const errKeys = Object.keys(syncErr);
  const ok = out?.judge?.filter((r) => r.state === 'OK').length ?? 0;
  const tot = out?.judge?.length ?? 0;
  const mv = !edl || edl.segments.length === 0 ? '黑底' : edl.source === 'file' ? 'EDL' : '原画';
  return (
    <header className={s.top}>
      <span className={s.brand}>HX Studio</span>
      <span className={s.sep} />
      <span className={s.item} title={p?.dir}>{p ? `${p.anime} / ${p.song}` : '载入中'}</span>
      <span className={s.sep} />
      <span className={s.chip} data-k="mv">画面 {mv}</span>
      {octo === 'crashed' || octo === 'stalled' ? (
        // 就绪后崩了 / 没回应: 画面里的字幕已经不可信 (监视器已藏起旧帧). 点击重建实例; 不自动重载, 免得崩溃循环被掩盖
        <button className={s.chip} data-testid="octo-chip" data-state="error" data-octo={octo}
          title={`${octoErr}\n最后同步时刻 ${fmtT(octoAt)}. 点击重载 libass`}
          onClick={() => set({ octoGen: useStore.getState().octoGen + 1, octo: 'loading', octoErr: '' })}>
          {octo === 'crashed' ? `libass 崩溃 @${fmtT(octoAt)} · 点击重载` : 'libass 无响应 · 点击重载'}
        </button>
      ) : (
        <span className={s.chip} data-testid="octo-chip" data-state={octo === 'partial' ? 'error' : octo} data-octo={octo} title={octoErr || undefined}>
          libass {octo === 'ready' ? '就绪' : octo === 'partial' ? `缺图 ${octoMissing.length} 张` : octo === 'error' ? '失败' : octo === 'off' ? '无' : '载入'}
        </span>
      )}
      {(fontsMissing.length > 0 || fontsUnparsed.length > 0) && (
        // 不是失败: libass 用后备字体照样画, 只是字形可能和出片不同. 所以是 warn 色, 不并进 octo 状态
        <span className={s.chip} data-testid="font-chip" data-state="warn" data-missing={fontsMissing.map((f) => f.name).join('|')}
          title={[
            ...(fontsMissing.length ? ['fonts 目录里找不到, libass 会用后备字体画, 字形可能和出片不同:',
              ...fontsMissing.map((f) => `  ${f.name}  (${f.uses} 处, 首见第 ${f.line} 行, 来自 ${f.via.join(' / ')})`)] : []),
            ...(fontsUnparsed.length ? [`读不出名字表的字体文件 (无法比对, 上面可能误报): ${fontsUnparsed.join(', ')}`] : []),
          ].join('\n')}>
          {fontsMissing.length ? `字形可能不对 · ${fontsMissing.length} 个字体未找到` : `字体文件读不出 ${fontsUnparsed.length} 个`}
        </span>
      )}
      {live === 'down' ? (
        // 文件变化推送断了: 磁盘上的改动不会进界面. 重连后按服务端状态自动补刷
        <span className={s.chip} data-testid="sync-chip" data-state="warn" data-sync="offline"
          title="与 studio 服务的连接断开, 正在重连. 期间 out.ass / 标注 / EDL 的改动不会显示; 重连后自动补刷">
          未连接 · 改动不会自动刷新
        </span>
      ) : errKeys.length > 0 && (
        <button className={s.chip} data-testid="sync-chip" data-state="warn" data-sync="stale" data-keys={errKeys.join(',')}
          title={['以下内容热更新失败, 界面显示的还是旧版:', ...errKeys.map((k) => `  ${SYNC_LABEL[k] ?? k}: ${syncErr[k]}`), '点击重试'].join('\n')}
          onClick={() => sync.retry()}>
          {SYNC_LABEL[errKeys[0]] ?? errKeys[0]}{errKeys.length > 1 ? ` 等 ${errKeys.length} 项` : ''}未刷新 · 点击重试
        </button>
      )}
      <span className={s.grow} />
      {p && p.audio_error && (
        <span className={s.chip} data-testid="audio-chip" data-state="error" title={p.audio_error}>音频未定 · {p.audio_error}</span>
      )}
      {p && (
        // 参考 ASS 用的是哪份 + 怎么定的, 一直写在顶栏 (原来前端完全不显示, 选错了 A/B 和门禁全错也看不出). 未定 / 出错 = error 色
        <button className={s.chip} data-testid="ref-chip" data-source={p.ref.source} aria-expanded={refOpen}
          data-state={p.ref.source === 'ambiguous' || p.ref.source === 'error' ? 'error' : p.ref.source === 'none' ? 'warn' : undefined}
          title={[`参考 ASS: ${p.ref_path ?? '(未选)'}`, `来源: ${REF_SRC[p.ref.source]}${p.ref.set_at ? ` (指定于 ${p.ref.set_at})` : ''}`, ...(p.ref.error ? [p.ref.error] : []), '点击查看全部候选 / 指定'].join('\n')}
          onClick={() => set({ refOpen: !refOpen, placeOpen: false })}>
          {p.ref.source === 'ambiguous' ? `参考 ASS 未定 · ${p.ref.candidates.length} 份候选`
            : p.ref.source === 'error' ? '参考 ASS 出错 · 未选'
            : p.ref.source === 'none' ? `无参考 ASS${p.cmp && (p.cmp.kind === 'prev' || p.cmp.kind === 'cand') ? ` · 对比${p.cmp.label}` : ' · 目录里没有同名 .ass'}`
            : `参考 ${baseName(p.ref_path)} · ${REF_SRC[p.ref.source]}`}
        </button>
      )}
      <button className={s.chip} data-testid="loop-chip" aria-expanded={loopOpen} data-state={loopSt?.job.running ? 'busy' : pending ? 'warn' : undefined}
        onClick={() => set({ loopOpen: !loopOpen, refOpen: false, placeOpen: false })}
        title="看, 挑, 改, 证: 每条标注的处理状态, 换一个构想的候选 (看 / 冻结), 对比对象">
        闭环{loopSt?.job.running ? ' · 运行中' : ` · ${pending} 未结`}
      </button>
      <button className={s.chip} data-testid="place-btn" aria-expanded={placeOpen} data-state={place?.job.running ? 'busy' : undefined}
        onClick={() => set({ placeOpen: !placeOpen, refOpen: false })} title="歌词位置预设">
        位置{place?.job.running ? ' · 生成中' : ''}
      </button>
      {out && (
        // 没有参考就没有阈值: 原来显示 "门禁 0/0" 且是绿色 (ok === tot), 像全部通过. 现在写 "未判定"
        <span className={s.chip} data-testid="gate-chip" data-judge={out.judge ? `${ok}/${tot}` : 'none'}
          data-state={!out.judge ? 'warn' : ok === tot ? 'ready' : 'error'} data-stale={syncErr.data ? 'y' : undefined}
          title={[syncErr.data ? `门禁数据刷新失败, 显示的是上一次成功的结果: ${syncErr.data}` : 'check_fx_profile (只读调用)',
            out.judge ? `阈值来自参考: ${p?.ref_path} (${REF_SRC[p?.ref.source ?? 'none']})` : `没有阈值: 参考 ASS ${REF_SRC[p?.ref.source ?? 'none']}${p?.ref.error ? ` · ${p.ref.error}` : ''}`].join('\n')}>
          FX {out.profile.fx_count} · 门禁 {out.judge ? `${ok}/${tot}` : `未判定 · ${GATE_WHY[p?.ref.source ?? 'none'] ?? '无参考'}`}{syncErr.data ? ' (旧)' : ''}
        </span>
      )}
      <PlacementPanel />
      <RefPanel />
      <LoopPanel />
    </header>
  );
}
