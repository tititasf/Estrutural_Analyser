"use client";

import { useState, type ReactNode } from "react";
import { ArrowLeft, Check, CheckCircle2, Copy, Layers } from "lucide-react";
import Link from "next/link";
import { TypeIcon, type TipoElemento } from "@/components/ui/TypeIcon";
import { rotuloCodigoItem } from "@/lib/tipoElementoLabels";
import styles from "./FichaHeader.module.css";

interface FichaHeaderProps {
  obraRotulo: string | null;
  pavimentoLabel: string;
  pavimentoCode: string | null;
  tipo: string;
  titulo: string;
  code: string;
  onVoltar: () => void;
  /** Ações de canteiro (compartilhar, QR) na linha do código. */
  acoes?: ReactNode;
}

function ehTipoElemento(tipo: string): tipo is TipoElemento {
  return tipo === "pilar" || tipo === "viga_fundo" || tipo === "viga_lateral" || tipo === "laje";
}

export function FichaHeader({
  obraRotulo,
  pavimentoLabel,
  pavimentoCode,
  tipo,
  titulo,
  code,
  onVoltar,
  acoes,
}: FichaHeaderProps) {
  const [copiado, setCopiado] = useState(false);

  async function copiarCodigo() {
    try {
      await navigator.clipboard.writeText(code);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      // Fallback silencioso se clipboard for restrito
    }
  }

  return (
    <div className={styles.wrapper}>
      {/* Breadcrumb unificado */}
      <div className={styles.breadcrumb}>
        <button type="button" className={styles.voltar} onClick={onVoltar} aria-label="Sair">
          <ArrowLeft size={16} aria-hidden="true" />
          <span>Sair</span>
        </button>

        {obraRotulo && (
          <div className={styles.crumbTab}>
            <span>{obraRotulo}</span>
          </div>
        )}

        {pavimentoCode ? (
          <Link
            href={`/pavimento/${pavimentoCode}`}
            className={styles.crumbTabLink}
            aria-label={`Abrir ficha do pavimento ${pavimentoLabel}`}
          >
            <Layers size={13} aria-hidden="true" />
            <span>{pavimentoLabel}</span>
          </Link>
        ) : (
          <div className={styles.crumbTab}>
            <Layers size={13} aria-hidden="true" />
            <span>{pavimentoLabel}</span>
          </div>
        )}

        {pavimentoCode && (
          <Link
            href={`/pavimento/${pavimentoCode}#${tipo}`}
            className={styles.crumbTabLink}
          >
            <span>{tipo === 'pilar' ? 'Pilares' : tipo === 'laje' ? 'Lajes' : tipo === 'viga_fundo' ? 'Fundo de Vigas' : tipo === 'viga_lateral' ? 'Laterais de Viga' : 'Itens'}</span>
          </Link>
        )}
      </div>

      {/* Título Principal & Badges */}
      <div className={styles.tituloLinha}>
        <div className={styles.tituloGroup}>
          {ehTipoElemento(tipo) && <TypeIcon tipo={tipo} />}
          <h1 className={styles.titulo}>{titulo}</h1>
        </div>
        <span className={styles.statusPill}>
          <CheckCircle2 size={13} /> Auditado Arete
        </span>
      </div>

      {/* Código Base62 com cópia rápida + ações de canteiro ao lado */}
      <div className={styles.codigoRow}>
      <div className={styles.codigoLinha}>
        <span className={styles.codigo}>
          {rotuloCodigoItem(tipo)}: <strong>{code}</strong>
        </span>
        <button
          type="button"
          className={styles.copiar}
          onClick={copiarCodigo}
          aria-label="Copiar código"
          title="Copiar código"
        >
          {copiado ? <Check size={16} color="#34d399" /> : <Copy size={16} />}
        </button>
        {copiado && (
          <span role="status" className={styles.feedback}>
            Copiado!
          </span>
        )}
      </div>
      {acoes && <div className={styles.acoes}>{acoes}</div>}
      </div>

      <p className={styles.referencia}>
        {[obraRotulo, pavimentoLabel, titulo].filter(Boolean).join(" › ")}
      </p>
    </div>
  );
}
