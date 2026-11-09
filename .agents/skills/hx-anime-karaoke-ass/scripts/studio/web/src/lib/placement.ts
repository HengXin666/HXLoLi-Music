/* 位置预设的前端动作: 只调服务端 (GET 预览 / POST 应用), 不算坐标. */
import { api, type Preset } from './api';
import { toast, useStore } from './store';

const same = (a: Preset | null | undefined, b: Preset | null | undefined) =>
  !!a && !!b && a.v === b.v && a.h === b.h && a.order === b.order && a.gap === b.gap;

export async function refreshPlacement() {
  const place = await api.placement();
  useStore.setState({ place });
  return place;
}

let seq = 0;
/** 选一个候选: 与当前相同 = 关预览; 否则向服务端要每句块位移, 监视器立刻按它画. */
export async function pickPlacement(cand: Preset) {
  const st = useStore.getState();
  const cur = st.place?.current;
  const my = ++seq;
  if (same(cand, cur)) { useStore.setState({ placeCand: null, placeLines: null }); return; }
  useStore.setState({ placeCand: cand });
  const r = await api.placement(cand);
  if (my !== seq) return; // 连点时只认最后一次
  useStore.setState({ place: { ...r, candidate: undefined, lines: undefined }, placeLines: r.lines ?? [] });
}

export function clearPreview() {
  seq++;
  useStore.setState({ placeCand: null, placeLines: null });
}

/** 应用: POST 后立刻读服务端状态 (running=true 由服务端给, 前端不计时); 结束由 /api/watch 的 job 变化通知. */
export async function applyPlacement() {
  const st = useStore.getState();
  const cand = st.placeCand;
  if (!cand || st.place?.job.running) return;
  try {
    await api.applyPlacement(cand);
  } catch (e) {
    toast(`应用失败: ${(e as Error).message}`);
  }
  await refreshPlacement();
}

/** /api/watch 推来 job/placement 变化: 刷新状态; 任务刚结束则关预览 (成功) 或提示错误 (失败, 预览保留). */
export async function onPlacementChanged() {
  const prev = useStore.getState().place?.job;
  const place = await refreshPlacement();
  if (prev?.running && !place.job.running) {
    if (place.job.ok) { clearPreview(); toast('位置已应用, 成品已重跑'); }
    else toast(`生成失败, 已保持原配置: ${(place.job.error || '').slice(0, 80)}`);
  }
}

export { same as samePreset };
