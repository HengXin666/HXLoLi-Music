import { useStore } from '../lib/store';
import PlacementPanel from './PlacementPanel';
import s from './Bars.module.css';

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
  const set = useStore((x) => x.set);
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
      <span className={s.grow} />
      <button className={s.chip} data-testid="place-btn" aria-expanded={placeOpen} data-state={place?.job.running ? 'busy' : undefined}
        onClick={() => set({ placeOpen: !placeOpen })} title="歌词位置预设">
        位置{place?.job.running ? ' · 生成中' : ''}
      </button>
      {out && (
        <span className={s.chip} data-state={ok === tot ? 'ready' : 'error'} title="check_fx_profile (只读调用)">
          FX {out.profile.fx_count} · 门禁 {ok}/{tot}
        </span>
      )}
      <PlacementPanel />
    </header>
  );
}
