import { motion } from "motion/react";
import { useId } from "react";
import { motionTokens } from "../theme/tokens";
import s from "./ui.module.css";

interface Props<K extends string> {
  label: string;
  options: { key: K; label: string }[];
  value: K;
  onChange: (k: K) => void;
}

/** Native radio buttons drawn as a segmented control, so arrow keys and screen readers work as usual. */
export function Segmented<K extends string>({ label, options, value, onChange }: Props<K>) {
  const id = useId();
  return (
    <fieldset className={s.segmented}>
      <legend className="visually-hidden">{label}</legend>
      {options.map((o) => {
        const on = o.key === value;
        return (
          <label key={o.key} className={s.segment} data-on={on}>
            <input className={s.radio} type="radio" name={id} value={o.key} checked={on} onChange={() => onChange(o.key)} />
            {on ? <motion.span layoutId={`${id}-pill`} className={s.segmentPill} transition={motionTokens.change} /> : null}
            <span className={s.segmentLabel}>{o.label}</span>
          </label>
        );
      })}
    </fieldset>
  );
}
