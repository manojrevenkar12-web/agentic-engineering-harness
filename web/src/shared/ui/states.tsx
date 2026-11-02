import type { ReactNode } from "react";
import s from "./ui.module.css";

export function Skeleton({ rows = 4, label }: { rows?: number; label: string }) {
  return (
    <div className={s.skeleton} role="status" aria-live="polite">
      <span className="visually-hidden">Loading {label}</span>
      {Array.from({ length: rows }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: placeholder rows have no identity
        <div key={i} className={s.bar} aria-hidden="true" />
      ))}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className={`${s.notice} ${s.noticeError}`} role="alert">
      <h3>The results could not be loaded</h3>
      <p>{message}</p>
      <button type="button" className={s.button} onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className={s.notice}>
      <h3>{title}</h3>
      {children}
    </div>
  );
}
