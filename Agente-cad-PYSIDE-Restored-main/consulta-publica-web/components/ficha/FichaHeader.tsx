"use client";

import { useState } from "react";
import { ArrowLeft, Copy } from "lucide-react";
import { TypeIcon, type TipoElemento } from "@/components/ui/TypeIcon";
import styles from "./FichaHeader.module.css";

interface FichaHeaderProps {
  obraRotulo: string | null;
  pavimentoLabel: string;
  tipo: string;
  titulo: string;
  code: string;
  onVoltar: () => void;
}

function ehTipoElemento(tipo: string): tipo is TipoElemento {
  return tipo === "pilar" || tipo === "viga_fundo" || tipo === "viga_lateral" || tipo === "laje";
}

/** Cabeçalho da Ficha — breadcrumb neutro (nunca expõe item_id/pavimento
 * cru, só os rótulos públicos), tipo+título, código + copiar (AC1/AC3). */
export function FichaHeader({ obraRotulo, pavimentoLabel, tipo, titulo, code, onVoltar }: FichaHeaderProps) {
  const [copiado, setCopiado] = useState(false);

  async function copiarCodigo() {
    try {
      await navigator.clipboard.writeText(code);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 1500);
    } catch {
      // Sem permissão de clipboard — falha silenciosa, não é crítico.
    }
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.breadcrumb}>
        <button type="button" className={styles.voltar} onClick={onVoltar} aria-label="Voltar">
          <ArrowLeft size={20} aria-hidden="true" /> Voltar
        </button>
        {obraRotulo && <span> · {obraRotulo}</span>}
        <span> · {pavimentoLabel}</span>
      </div>

      <div className={styles.tituloLinha}>
        {ehTipoElemento(tipo) && <TypeIcon tipo={tipo} />}
        <h1 className={styles.titulo}>{titulo}</h1>
      </div>

      <div className={styles.codigoLinha}>
        <span className={styles.codigo}>código: {code}</span>
        <button type="button" className={styles.copiar} onClick={copiarCodigo} aria-label="Copiar código">
          <Copy size={18} aria-hidden="true" />
        </button>
        {copiado && (
          <span role="status" className={styles.feedback}>
            Copiado!
          </span>
        )}
      </div>
    </div>
  );
}
