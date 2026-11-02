/** A linear scale onto 0..100 (percent of a track) with round ticks. */
export interface Scale {
  domain: [number, number];
  ticks: number[];
  at: (v: number) => number;
}

export function niceStep(span: number, count: number): number {
  const raw = span / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const f = raw / mag;
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
  return nice * mag;
}

export function linear(values: number[], tickCount = 5): Scale {
  const finite = values.filter(Number.isFinite);
  let lo = Math.min(0, ...finite);
  let hi = Math.max(0, ...finite);
  if (lo === hi) {
    lo -= 1;
    hi += 1;
  }
  const step = niceStep(hi - lo, tickCount);
  lo = Math.floor(lo / step) * step;
  hi = Math.ceil(hi / step) * step;
  const ticks: number[] = [];
  for (let t = lo; t <= hi + step / 2; t += step) ticks.push(Math.abs(t) < step / 1e6 ? 0 : t);
  return { domain: [lo, hi], ticks, at: (v: number) => ((v - lo) / (hi - lo)) * 100 };
}
