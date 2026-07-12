import type { ReactNode } from "react";
import { AlertTriangle, Clock, Wifi, XCircle } from "lucide-react";
import { Button } from "./Button";
import styles from "./EmptyState.module.css";

export type EmptyStateVariant = "not-found" | "offline" | "blocked" | "svg-error" | "lv-absent";

const ICONE_POR_VARIANTE: Record<EmptyStateVariant, ReactNode> = {
  "not-found": <XCircle size={40} aria-hidden="true" />,
  offline: <Wifi size={40} aria-hidden="true" />,
  blocked: <Clock size={40} aria-hidden="true" />,
  "svg-error": <AlertTriangle size={40} aria-hidden="true" />,
  "lv-absent": <AlertTriangle size={40} aria-hidden="true" />,
};

interface EmptyStateProps {
  variante: EmptyStateVariant;
  titulo: string;
  descricao?: string;
  cta?: { rotulo: string; onClick: () => void };
}

/** Empty/Error state genérico (§8.8) — ícone + 1 frase + 1 CTA grande.
 * Usado pelos 5 cenários documentados (not-found/offline/blocked/svg-error/
 * lv-absent); o texto de cada variante é definido pelo chamador (mensagem
 * de "não encontrado" deve permanecer idêntica em todo lugar — AC8/STORY-08,
 * princípio "Silêncio seguro"). */
export function EmptyState({ variante, titulo, descricao, cta }: EmptyStateProps) {
  return (
    <div className={styles.wrapper} role="alert">
      <span className={styles.icone} aria-hidden="true">
        {ICONE_POR_VARIANTE[variante]}
      </span>
      <p className={styles.titulo}>{titulo}</p>
      {descricao && <p className={styles.descricao}>{descricao}</p>}
      {cta && (
        <Button variant="secondary" onClick={cta.onClick}>
          {cta.rotulo}
        </Button>
      )}
    </div>
  );
}
