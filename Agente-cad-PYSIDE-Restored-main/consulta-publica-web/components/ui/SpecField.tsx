import styles from "./SpecField.module.css";

interface SpecFieldProps {
  chave: string;
  valor: string;
}

/** Par chave/valor de especificação (§8.8) — valor peso 700, tabular-nums
 * para números/dimensões. */
export function SpecField({ chave, valor }: SpecFieldProps) {
  return (
    <div className={styles.linha}>
      <span className={styles.chave}>{chave}</span>
      <span className={`${styles.valor} tabular-nums`}>{valor}</span>
    </div>
  );
}
