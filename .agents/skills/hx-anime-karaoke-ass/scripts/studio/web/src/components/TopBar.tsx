import { useStore } from '../lib/store';
import PlacementPanel from './PlacementPanel';
import s from './Bars.module.css';

export default function TopBar() {
  const p = useStore((x) => x.project);
  const out = useStore((x) => x.out);
  const edl = useStore((x) => x.edl);
  const octo = useStore((x) => x.octo);
  const octoErr = useStore((x) => x.octoErr);
  const octoMissing = useStore((x) => x.octoMissing);
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
      <span className={s.chip} data-testid="octo-chip" data-state={octo === 'partial' ? 'error' : octo} data-octo={octo} title={octoErr || undefined}>
        libass {octo === 'ready' ? '就绪' : octo === 'partial' ? `缺图 ${octoMissing.length} 张` : octo === 'error' ? '失败' : octo === 'off' ? '无' : '载入'}
      </span>
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
