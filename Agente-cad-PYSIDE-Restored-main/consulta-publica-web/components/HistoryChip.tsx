"use client";

import { useRef } from "react";
import type { HistoryEntry } from "@/lib/storage/history";
import { TypeIcon, type TipoElemento } from "./ui/TypeIcon";
import styles from "./HistoryChip.module.css";

function ehTipoElemento(tipo: string): tipo is TipoElemento {
  return tipo === "pilar" || tipo === "viga_fundo" || tipo === "viga_lateral" || tipo === "laje";
}

interface HistoryChipProps {
  entry: HistoryEntry;
  onSelect: (code: string) => void;
  onRemove: (code: string) => void;
}

/** Chip de histórico — 56px, ícone por tipo, marca `⭳off` se cacheado
 * offline. Long-press (touch) remove; botão "×" visível cobre o mesmo caso
 * para teclado/leitor de tela (AC11 + acessibilidade — swipe puro excluiria
 * quem não usa touch). */
export function HistoryChip({ entry, onSelect, onRemove }: HistoryChipProps) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const iniciarLongPress = () => {
    timerRef.current = setTimeout(() => onRemove(entry.code), 600);
  };
  const cancelarLongPress = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  };

  return (
    <div
      className={styles.chip}
      onPointerDown={iniciarLongPress}
      onPointerUp={cancelarLongPress}
      onPointerLeave={cancelarLongPress}
    >
      <button type="button" className={styles.chipBody} onClick={() => onSelect(entry.code)}>
        {ehTipoElemento(entry.tipo) && <TypeIcon tipo={entry.tipo} />}
        <span className={styles.titulo}>{entry.titulo}</span>
        {entry.obra_rotulo && <span className={styles.obraRotulo}> · {entry.obra_rotulo}</span>}
        {entry.cached_offline && (
          <span className={styles.offBadge} aria-label="Disponível offline">
            ⭳off
          </span>
        )}
      </button>
      <button
        type="button"
        className={styles.removeButton}
        onClick={() => onRemove(entry.code)}
        aria-label={`Remover ${entry.titulo} do histórico`}
      >
        ×
      </button>
    </div>
  );
}
