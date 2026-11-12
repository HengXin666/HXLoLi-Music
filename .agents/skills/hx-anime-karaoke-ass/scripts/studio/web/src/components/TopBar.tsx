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
