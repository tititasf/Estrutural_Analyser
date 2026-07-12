import { Grid2x2, RectangleHorizontal, Square } from "lucide-react";
import styles from "./TypeIcon.module.css";

export type TipoElemento = "pilar" | "viga_fundo" | "viga_lateral" | "laje";

const CONFIG: Record<TipoElemento, { Icone: typeof Square; cor: string; rotulo: string }> = {
  pilar: { Icone: Square, cor: "var(--type-pilar)", rotulo: "Pilar" },
  viga_fundo: { Icone: RectangleHorizontal, cor: "var(--type-viga)", rotulo: "Viga" },
  viga_lateral: { Icone: RectangleHorizontal, cor: "var(--type-viga)", rotulo: "Viga" },
  laje: { Icone: Grid2x2, cor: "var(--type-laje)", rotulo: "Laje" },
};

interface TypeIconProps {
  tipo: TipoElemento;
  comRotulo?: boolean;
}

/** Ícone de tipo de elemento — cor sólida de fundo por tipo (§8.7), sempre
 * acompanhado de rótulo textual ou `aria-label` (nunca ícone sozinho como
 * único significado — AC8/9.2 "não depender só de cor"). */
export function TypeIcon({ tipo, comRotulo = false }: TypeIconProps) {
  const { Icone, cor, rotulo } = CONFIG[tipo] ?? CONFIG.pilar;
  return (
    <span className={styles.wrapper}>
      <span className={styles.badge} style={{ backgroundColor: cor }} aria-label={rotulo} role="img">
        <Icone size={24} color="#ffffff" aria-hidden="true" />
      </span>
      {comRotulo && <span>{rotulo}</span>}
    </span>
  );
}
