"use client";

import { ChevronDown, ChevronRight, QrCode } from "lucide-react";
import Link from "next/link";
import type { ObraPavimento } from "@/lib/api/obra";
import { ItemListRow } from "./ItemListRow";
import styles from "./PavimentoAccordion.module.css";

interface PavimentoAccordionProps {
  pavimento: ObraPavimento;
  expandido: boolean;
  onAlternar: () => void;
  onSelecionarItem: (code: string) => void;
}

/** Acordeão de 1 pavimento (§5.5) — 56px por linha (cabeçalho e itens).
 * Pavimento sem itens publicados mostra estado vazio, não erro (AC7). */
export function PavimentoAccordion({ pavimento, expandido, onAlternar, onSelecionarItem }: PavimentoAccordionProps) {
  return (
    <div className={styles.wrapper}>
      <button
        type="button"
        className={styles.cabecalho}
        onClick={onAlternar}
        aria-expanded={expandido}
      >
        {expandido ? <ChevronDown size={20} aria-hidden="true" /> : <ChevronRight size={20} aria-hidden="true" />}
        <span className={styles.rotulo}>{pavimento.pavimento_label.toUpperCase()}</span>
        <span className={styles.contagem}>({pavimento.itens.length})</span>
      </button>

      {pavimento.code && (
        <Link
          href={`/pavimento/${pavimento.code}`}
          className={styles.abrirFicha}
          aria-label={`Abrir ficha do pavimento ${pavimento.pavimento_label} (código ${pavimento.code})`}
          onClick={(e) => e.stopPropagation()}
        >
          <QrCode size={16} aria-hidden="true" /> Pavimento: {pavimento.code}
        </Link>
      )}

      {expandido && (
        <div className={styles.itens}>
          {pavimento.itens.length === 0 ? (
            <p className={styles.vazio}>Nenhum item publicado neste pavimento.</p>
          ) : (
            pavimento.itens.map((item) => (
              <ItemListRow key={item.code} item={item} onSelecionar={onSelecionarItem} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
