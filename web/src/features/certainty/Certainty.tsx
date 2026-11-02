import { points } from "../../shared/lib/format";
import { setupName } from "../../shared/lib/labels";
import type { Diff, Results } from "../../shared/lib/results";
import { linear } from "../../shared/lib/scale";
import s from "./certainty.module.css";

function Rows({ items, label, scale }: { items: [string, Diff][]; label: (k: string) => string; scale: ReturnType<typeof linear> }) {
  return (
    <>
      {items.map(([k, d]) => {
        const lo = d.lo ?? 0;
        const hi = d.hi ?? 0;
        const tone = lo > 0 ? s.up : hi < 0 ? s.down : "";
        return (
          <div className={s.row} key={k} data-testid={`diff-${k}`}>
            <span className={s.label}>{label(k)}</span>
            <div className={s.track} aria-hidden="true">
              <div className={s.zero} style={{ left: `${scale.at(0)}%` }} />
              <div className={`${s.bar} ${tone}`} style={{ left: `${scale.at(lo)}%`, width: `${scale.at(hi) - scale.at(lo)}%` }} />
              <div className={s.dot} style={{ left: `${scale.at(d.diff ?? 0)}%` }} />
            </div>
            <span className={s.num}>
              {points(d.diff ?? 0)}
              <span className={s.range}>
                {Math.round(100 * lo)} to {Math.round(100 * hi)}
              </span>
            </span>
          </div>
        );
      })}
    </>
  );
}

/** How much of each difference could be noise: lifts over the baseline next to the same setup against itself. */
export function Certainty({ r }: { r: Results }) {
  const dev = r.dev!;
  const vs = Object.entries(dev.vs_baseline).filter(([, d]) => d.tasks > 0);
  const aa = Object.entries(dev.aa).filter(([, d]) => d.tasks > 0);
  const scale = linear([...vs, ...aa].flatMap(([, d]) => [d.lo ?? 0, d.hi ?? 0]));
  const base = r.decision_rule.baseline;
  return (
    <figure className={s.wrap} aria-label="Differences in merged changes, with intervals">
      <h3 className={s.group}>Merged changes against {setupName(base, r.setups[base])}, same tasks</h3>
      <Rows items={vs} label={(k) => setupName(k, r.setups[k])} scale={scale} />
      {aa.length ? (
        <>
          <hr className={s.sep} />
          <h3 className={s.group}>Each setup against itself: the second run minus the first</h3>
          <Rows items={aa} label={(k) => setupName(k, r.setups[k])} scale={scale} />
        </>
      ) : null}
      <p className={s.note}>
        Points are percentage points of tasks; bars are {Math.round(dev.confidence * 100)}% bootstrap intervals over tasks. A bar that
        crosses zero is a difference this many tasks cannot tell from noise.
      </p>
    </figure>
  );
}
