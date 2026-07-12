"use client";

import type { ButtonHTMLAttributes } from "react";
import styles from "./Button.module.css";

type Variant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
}

/** Botão-núcleo (§8.8) — ≥56px (primary 64px); `loading` mostra spinner e
 * trava re-tap (disabled durante loading). */
export function Button({ variant = "primary", loading = false, disabled, children, className, ...rest }: ButtonProps) {
  const classes = [styles.base, styles[variant], variant === "primary" ? styles.primarySize : "", className]
    .filter(Boolean)
    .join(" ");

  return (
    <button type="button" className={classes} disabled={disabled || loading} aria-busy={loading} {...rest}>
      {loading && (
        <span className={styles.spinner} aria-hidden="true" />
      )}
      {children}
    </button>
  );
}
