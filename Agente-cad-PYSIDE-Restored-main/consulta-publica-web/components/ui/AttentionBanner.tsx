import { AlertTriangle } from "lucide-react";
import styles from "./AttentionBanner.module.css";

interface AttentionBannerProps {
  texto: string;
}

/** Banner de atenção — fundo âmbar + texto preto (`--warning-bg`/
 * `--warning-fg`), só renderizado se `atencao != ""` (§8.8, §5.3). */
export function AttentionBanner({ texto }: AttentionBannerProps) {
  if (!texto) return null;
  return (
    <div className={styles.banner} role="alert">
      <AlertTriangle size={24} aria-hidden="true" />
      <span>
        <strong>ATENÇÃO:</strong> {texto}
      </span>
    </div>
  );
}
