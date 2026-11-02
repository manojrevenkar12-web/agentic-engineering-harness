import type { ReactNode } from "react";
import type { Load } from "../lib/useResults";
import { EmptyState, ErrorState, Skeleton } from "./states";
import s from "./ui.module.css";

interface Props<T> {
  id: string;
  title: string;
  intro?: ReactNode;
  load: Load<T | null>;
  onRetry: () => void;
  empty: { title: string; body: ReactNode };
  skeletonRows?: number;
  children: (data: T) => ReactNode;
}

/** Every section renders one of four states: loading, error (with retry), empty, or its content. */
export function Section<T>({ id, title, intro, load, onRetry, empty, skeletonRows, children }: Props<T>) {
  return (
    <section className={s.section} aria-labelledby={`${id}-title`} id={id}>
      <header className={s.head}>
        <h2 className={s.title} id={`${id}-title`}>
          {title}
        </h2>
        {intro ? <p className={s.intro}>{intro}</p> : null}
      </header>
      {load.status === "loading" ? (
        <Skeleton rows={skeletonRows} label={title} />
      ) : load.status === "error" ? (
        <ErrorState message={load.message} onRetry={onRetry} />
      ) : load.data === null ? (
        <EmptyState title={empty.title}>{empty.body}</EmptyState>
      ) : (
        children(load.data)
      )}
    </section>
  );
}

export function slice<A, B>(load: Load<A>, pick: (a: A) => B | null | undefined): Load<B | null> {
  return load.status === "ready" ? { status: "ready", data: pick(load.data) ?? null } : load;
}
