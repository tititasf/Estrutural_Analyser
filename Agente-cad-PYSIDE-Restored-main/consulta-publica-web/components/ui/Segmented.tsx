"use client";

import styles from "./Segmented.module.css";

export interface SegmentedOption {
  value: string;
  label: string;
}

interface SegmentedProps {
  options: SegmentedOption[];
  selected: string;
  onSelect: (value: string) => void;
  label: string;
}

/** Segmented control (abas N1/N3/Painéis) — 56px por segmento; se só há 1
 * opção, colapsa para rótulo estático (§8.8, front-end-spec §5.3 nota). */
export function Segmented({ options, selected, onSelect, label }: SegmentedProps) {
  if (options.length <= 1) {
    return <div className={styles.rotuloEstatico}>{options[0]?.label ?? ""}</div>;
  }

  return (
    <div className={styles.wrapper} role="tablist" aria-label={label}>
      {options.map((opt) => {
        const isSelected = opt.value === selected;
        return (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={isSelected}
            className={`${styles.segmento} ${isSelected ? styles.selecionado : ""}`}
            onClick={() => onSelect(opt.value)}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
