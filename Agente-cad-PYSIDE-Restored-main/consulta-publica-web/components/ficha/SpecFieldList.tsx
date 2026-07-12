import { SpecField } from "@/components/ui/SpecField";
import { AttentionBanner } from "@/components/ui/AttentionBanner";
import styles from "./SpecFieldList.module.css";

interface SpecFieldListProps {
  campos: Record<string, string>;
  atencao: string;
}

/** Seção "Especificação" — pares chave/valor + banner de atenção condicional
 * (§5.3, AC1). */
export function SpecFieldList({ campos, atencao }: SpecFieldListProps) {
  const entradas = Object.entries(campos);

  return (
    <section className={styles.wrapper}>
      <h2 className={styles.tituloSecao}>Especificação</h2>
      {entradas.length === 0 && <p className={styles.vazio}>Sem campos de especificação.</p>}
      {entradas.map(([chave, valor]) => (
        <SpecField key={chave} chave={chave} valor={valor} />
      ))}
      <AttentionBanner texto={atencao} />
    </section>
  );
}
