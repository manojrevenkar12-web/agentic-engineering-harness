const nf = (digits: number) => new Intl.NumberFormat("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const int = (v: number) => new Intl.NumberFormat("en-GB").format(Math.round(v));
export const fixed = (v: number, digits = 2) => nf(digits).format(v);
export const share = (v: number | null | undefined, digits = 0) =>
  v == null || Number.isNaN(v) ? "n/a" : `${nf(digits).format(100 * v)}%`;
export const usd = (v: number | null | undefined, digits = 2) =>
  v == null || !Number.isFinite(v) ? "none accepted" : `$${nf(digits).format(v)}`;

/** Signed values use a true minus sign so columns line up and screen readers say "minus". */
const signed = (s: string, v: number) => (v > 0 ? `+${s}` : v < 0 ? `−${s}` : s);
export const points = (v: number, digits = 0) => signed(`${nf(digits).format(100 * Math.abs(v))} pts`, v);
