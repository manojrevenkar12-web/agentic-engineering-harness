import { motion } from "motion/react";
import { share, usd } from "../../shared/lib/format";
import { setupName } from "../../shared/lib/labels";
import type { Results } from "../../shared/lib/results";
import { motionTokens } from "../../shared/theme/tokens";
import s from "./verdict.module.css";

const pct = (v: number | null | undefined) => `${Math.max(0, Math.min(1, v ?? 0)) * 100}%`;

/** Per setup: how often its change passed the tests, how often a maintainer would merge it, and the cost of each merged change. */
export function Verdict({ r }: { r: Results }) {
  const dev = r.dev!;
  const rows = Object.entries(dev.setups).sort((a, b) => (b[1].accepted.rate ?? 0) - (a[1].accepted.rate ?? 0));
  const choice = dev.decision.choice;
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  return (
    <div className={s.hero}>
      <p className={s.decision}>{choice ? `Adopt ${setupName(choice, r.setups[choice])}.` : "No decision yet."}</p>
      <p className={s.why}>
        {dev.decision.why.charAt(0).toUpperCase() + dev.decision.why.slice(1)}. Rule: {r.decision_rule.baseline} stays unless a setup is
        better on the same tasks, or as good and cheaper per merged change.
      </p>
      <figure className={s.chart} aria-labelledby="verdict-caption">
        <figcaption id="verdict-caption" className="visually-hidden">
          For each setup, the share of tasks where its change passed the tests and the share a maintainer would merge, with the cost per
          merged change.
        </figcaption>
        <div className={s.head} aria-hidden="true">
          <span>Setup</span>
          <span>Share of attempts</span>
          <span className={s.right}>Per merged change</span>
        </div>
        {rows.map(([key, x], i) => {
          const pass = x.tests_pass.rate ?? 0;
          const acc = x.accepted.rate ?? 0;
          return (
            <div key={key} className={`${s.row} ${key === choice ? s.chosen : ""}`} data-testid={`setup-${key}`}>
              <div>
                <span className={s.name}>{setupName(key, r.setups[key])}</span>
                <span className={s.sub}>
                  {share(acc)} merged, {share(pass)} pass tests ({x.attempts} attempts)
                  {x.format_only ? `; ${x.format_only} stopped only by formatting` : ""}
                </span>
              </div>
              <div className={s.track} aria-hidden="true">
                <div className={s.base} />
                <div className={s.ci} style={{ left: pct(x.accepted.lo), width: `calc(${pct(x.accepted.hi)} - ${pct(x.accepted.lo)})` }} />
                <motion.div
                  className={s.gap}
                  style={{ left: pct(Math.min(acc, pass)) }}
                  initial={{ width: 0 }}
                  animate={{ width: pct(Math.abs(pass - acc)) }}
                  transition={{ ...motionTokens.reveal, delay: 0.3 + i * motionTokens.stagger }}
                />
                <div className={s.pass} style={{ left: pct(pass) }} />
                <motion.div
                  className={s.acc}
                  initial={{ left: pct(pass), opacity: 0 }}
                  animate={{ left: pct(acc), opacity: 1 }}
                  transition={{ ...motionTokens.reveal, delay: 0.3 + i * motionTokens.stagger }}
                />
              </div>
              <div className={s.cost}>
                <b>{usd(x.cost_per_accepted.point)}</b>
                <span>${x.cost_usd_per_attempt.toFixed(2)} per attempt</span>
              </div>
            </div>
          );
        })}
        <div className={s.axis} aria-hidden="true">
          <span />
          <div className={s.axisTrack}>
            {ticks.map((t) => (
              <span key={t} className={s.tick} style={{ left: pct(t) }}>
                {share(t)}
              </span>
            ))}
          </div>
          <span />
        </div>
        <ul className={s.legend}>
          <li>
            <span className={`${s.k} ${s.kPass}`} aria-hidden="true" />
            Passes the hidden tests
          </li>
          <li>
            <span className={`${s.k} ${s.kAcc}`} aria-hidden="true" />A maintainer would merge it (line: {Math.round(dev.confidence * 100)}%
            interval)
          </li>
          <li>
            <span className={`${s.k} ${s.kGap}`} aria-hidden="true" />
            Passed the tests, stopped in review
          </li>
        </ul>
      </figure>
    </div>
  );
}
