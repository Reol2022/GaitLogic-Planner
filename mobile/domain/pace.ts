/** Arithmetic port of web/src/utils/paceConversion.ts. Not a race prediction. */
export type PaceTarget = 'pace' | 'time' | 'distance' | 'lap';
export const distancePresets = [{ label: '全马', km: 42.195 }, { label: '半马', km: 21.0975 }, { label: '10 公里', km: 10 }, { label: '5 公里', km: 5 }];
export function convert(target: PaceTarget, distance: number, total: number, pace: number, lap: number): { km: number; time: number; pace: number; lap: number } | null {
  let km = distance, time = total, speed = pace;
  if (target === 'pace') speed = time / km;
  if (target === 'time') time = km * speed;
  if (target === 'distance') km = time / speed;
  if (target === 'lap') { speed = lap / 0.4; time = km * speed; }
  if (![km, time, speed].every(value => Number.isFinite(value) && value > 0)) return null;
  return { km, time, pace: speed, lap: speed * 0.4 };
}
export function clock(seconds: number, hours = false): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '—';
  const rounded = Math.round(seconds), tail = String(rounded % 60).padStart(2, '0');
  return hours ? String(Math.floor(rounded / 3600)).padStart(2, '0') + ':' + String(Math.floor(rounded / 60) % 60).padStart(2, '0') + ':' + tail : Math.floor(rounded / 60) + ':' + tail;
}
