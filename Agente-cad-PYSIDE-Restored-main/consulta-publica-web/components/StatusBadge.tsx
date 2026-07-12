"use client";

import styles from "./StatusBadge.module.css";

interface StatusBadgeProps {
  online: boolean;
}

/** Badge de status de conexão na app-bar — "●ONLINE" / "●OFFLINE" (âmbar). */
export function StatusBadge({ online }: StatusBadgeProps) {
  return (
    <span
      className={`${styles.badge} ${online ? styles.online : styles.offline}`}
      role="status"
      aria-live="polite"
    >
      ● {online ? "ONLINE" : "OFFLINE"}
    </span>
  );
}
