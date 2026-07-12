import styles from "./Skeleton.module.css";

interface SkeletonProps {
  variant?: "line" | "block" | "drawing";
  rotulo?: string;
}

/** Skeleton pulsante (§8.8) — usado em loading de `/resolve` e de SVG.
 * Com `prefers-reduced-motion`, o pulso vira estático (tokens.css) e o
 * `rotulo` (via `aria-live`) garante que o estado ainda é comunicado. */
export function Skeleton({ variant = "line", rotulo = "carregando" }: SkeletonProps) {
  return (
    <div className={`${styles.base} ${styles[variant]}`} role="status" aria-live="polite">
      <span className={styles.srOnly}>{rotulo}</span>
    </div>
  );
}
