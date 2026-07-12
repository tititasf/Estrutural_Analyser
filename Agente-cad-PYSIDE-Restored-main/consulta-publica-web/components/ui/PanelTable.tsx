import styles from "./PanelTable.module.css";

export interface PanelItem {
  numero: number;
  larguraCm: number;
  tipo: string;
  /** A API pública (STORY-12) não expõe o módulo STOG — esse dado vive só
   * no motor desktop interno e não faz parte do contrato público (Art. IV
   * "No Invention" — nunca inventar um valor aqui). `undefined` renderiza
   * "—". */
  moduloStog?: string;
}

interface PanelTableProps {
  lado: string;
  paineis: PanelItem[];
}

/** Lista de painéis LV — tabela em telas largas, cartões empilhados em
 * telas estreitas (< 380px), via CSS puro (§8.8, front-end-spec §5.4).
 * Conteúdo completo (STORY-13); aqui só o componente-núcleo/shell. */
export function PanelTable({ lado, paineis }: PanelTableProps) {
  return (
    <section aria-label={`Painéis — Lado ${lado}`}>
      <h3 className={styles.ladoTitulo}>LADO {lado}</h3>

      <table className={styles.tabela}>
        <thead>
          <tr>
            <th>#</th>
            <th>Largura</th>
            <th>Tipo</th>
            <th>Módulo STOG</th>
          </tr>
        </thead>
        <tbody>
          {paineis.map((p) => (
            <tr key={p.numero}>
              <td>{p.numero}</td>
              <td className="tabular-nums">{p.larguraCm} cm</td>
              <td>{p.tipo}</td>
              <td className="tabular-nums">{p.moduloStog ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul className={styles.cartoes}>
        {paineis.map((p) => (
          <li key={p.numero} className={styles.cartao}>
            <span className={`${styles.larguraDestaque} tabular-nums`}>{p.larguraCm} cm</span>
            <span>
              {p.tipo} · módulo {p.moduloStog ?? "—"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
