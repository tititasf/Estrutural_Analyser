"use client";

import type { ReactNode } from "react";
import type {
  EtapaReaproveitamento,
  ReaproveitamentoData,
  SobraDisponivel,
} from "@/lib/api/materiais";
import styles from "./MateriaisTab.module.css";

const fmt = (n: number, casas = 1) =>
  n.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: casas });

/** "TREINO_1-13PAV-LV-V309.PARA-P02" → "V309.PARA-P02" */
const idCurto = (id?: string | null) => (id ? id.split("-").slice(3).join("-") : "");

const PONTAS: Record<string, string> = { "true,false": "esq.", "false,true": "dir.", "true,true": "ambas", "false,false": "—" };
const pontas = (p: [boolean, boolean]) => PONTAS[p.join(",")];

/** Classe de origem sem citar Para/Passa (o cenário já é o da ficha). */
const CLASSE: Record<string, string> = {
  pilares_n3_para: "pilar", pilares_n3_passa: "pilar", lateral_a_para: "lateral de viga",
  lateral_a_passa: "lateral de viga", fundo: "fundo de viga", lajes: "laje",
};

const ORDEM: EtapaReaproveitamento[] = ["1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "novo"];

function Etapa({ etapa, rotulo }: { etapa: EtapaReaproveitamento; rotulo?: string }) {
  return (
    <span className={`${styles.etapa} ${etapa === "novo" ? styles.etapaNovo : ""}`} title={rotulo}>
      {etapa === "novo" ? "Novo" : `Etapa ${etapa.replace(".", ",")}`}
    </span>
  );
}

function SemAnterior({ dados }: { dados: ReaproveitamentoData }) {
  return (
    <p className={styles.nota}>
      Nenhum pavimento abaixo do {dados.pavimento} na obra:
      tudo é preparado com material novo.
    </p>
  );
}

/** "Preparação com Materiais Reaproveitados e Novos": de onde vem cada painel
 * (etapas 1…4,5) e a compra só do que faltou. */
export function PreparacaoReaproveitada({
  dados,
  renderCompra,
}: {
  dados: ReaproveitamentoData;
  renderCompra: (compra: ReaproveitamentoData["compra"]) => ReactNode;
}) {
  const total = dados.paineis.length;
  const reusados = dados.paineis.filter((p) => p.etapa !== "novo").length;
  const deSobra = dados.compra.barras_de_sobra ?? [];
  return (
    <>
      {!dados.pavimento_anterior && <SemAnterior dados={dados} />}
      <section className={styles.grupo}>
        <h3 className={styles.tituloGrupo}>Origem de cada painel</h3>
        <p className={`${styles.resumo} tabular-nums`}>
          {reusados} de {total} painéis reaproveitados
          {dados.pavimento_anterior ? ` (estoque do ${dados.pavimento_anterior}${dados.pavimentos_cadeia.length > 2 ? " e abaixo" : ""})` : ""}.
        </p>
        <div className={styles.chips}>
          {ORDEM.filter((e) => dados.resumo_item[e]).map((e) => (
            <span key={e} className={`${styles.etapa} ${e === "novo" ? styles.etapaNovo : ""}`}>
              {dados.etapas[e]}: {dados.resumo_item[e]}
            </span>
          ))}
        </div>
        <div className={styles.tabelaWrap}>
          <table className={`${styles.tabela} tabular-nums`}>
            <thead>
              <tr>
                <th className={styles.esq}>Painel</th>
                <th>Medida (cm)</th>
                <th>Ponta c/ sarrafo</th>
                <th className={styles.esq}>Etapa</th>
                <th className={styles.esq}>Vem de</th>
                <th className={styles.esq}>Corte</th>
              </tr>
            </thead>
            <tbody>
              {dados.paineis.map((p) => (
                <tr key={p.id}>
                  <td className={`${styles.esq} ${styles.idPainel}`}>
                    {idCurto(p.id)}
                    <span className={styles.sub}>{p.grupo}</span>
                  </td>
                  <td>{fmt(p.largura_cm)} × {fmt(p.altura_cm)}</td>
                  <td>{pontas(p.pontas)}</td>
                  <td className={styles.esq}><Etapa etapa={p.etapa} rotulo={dados.etapas[p.etapa]} /></td>
                  <td className={styles.esq}>
                    {p.fonte_id ? (
                      <>
                        <span className={styles.idPainel}>{idCurto(p.fonte_id)}</span>
                        <span className={styles.sub}>
                          {p.fonte_tipo === "sobra" ? "sobra de chapa" : "painel montado"}
                          {p.fonte_pavimento ? ` · ${p.fonte_pavimento}` : ""}
                          {p.fonte_classe && p.fonte_tipo === "sobra" ? ` · ${CLASSE[p.fonte_classe] ?? p.fonte_classe}` : ""}
                          {p.fonte_medida ? ` · ${fmt(p.fonte_medida[0])} × ${fmt(p.fonte_medida[1])}` : ""}
                        </span>
                      </>
                    ) : (
                      "Material novo"
                    )}
                  </td>
                  <td className={styles.esq}>{p.corte ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {deSobra.length > 0 && (
        <section className={styles.grupo}>
          <h3 className={styles.tituloGrupo}>Sarrafos cortados de sobras de barra</h3>
          <p className={`${styles.resumo} tabular-nums`}>{deSobra.length} peças sem comprar barra nova.</p>
          <div className={styles.tabelaWrap}>
            <table className={`${styles.tabela} tabular-nums`}>
              <thead>
                <tr><th className={styles.esq}>Sobra</th><th className={styles.esq}>Peça</th><th>Comprimento (cm)</th></tr>
              </thead>
              <tbody>
                {deSobra.map((b, i) => (
                  <tr key={`${b.sobra_id}-${i}`}>
                    <td className={`${styles.esq} ${styles.idPainel}`}>{idCurto(b.sobra_id)}</td>
                    <td className={styles.esq}>{b.bitola}</td>
                    <td>{fmt(b.comprimento_cm)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {renderCompra(dados.compra) ?? <p className={styles.nota}>Nada a comprar: todo o material vem do reaproveitamento.</p>}
    </>
  );
}

function medidaSobra(s: SobraDisponivel): string {
  if (s.tipo === "barra") return `${fmt(s.comprimento_cm ?? 0)}`;
  const u = s.util;
  return u && (u.largura_cm !== s.largura_cm || u.altura_cm !== s.altura_cm)
    ? `${fmt(u.largura_cm)} × ${fmt(u.altura_cm)} (útil)`
    : `${fmt(s.largura_cm ?? 0)} × ${fmt(s.altura_cm ?? 0)}`;
}

/** "Materiais Disponíveis dos Pavimentos Anteriores": sobras todas juntas
 * (sem proveniência) + painéis montados separados por item. */
export function MateriaisDisponiveis({ dados }: { dados: ReaproveitamentoData }) {
  if (!dados.pavimento_anterior) return <SemAnterior dados={dados} />;
  const grupos = new Map<string, { tipo: string; material: string; medida: string; qtd: number; usadas: number }>();
  for (const s of dados.disponiveis.sobras) {
    const medida = medidaSobra(s);
    const material = s.tipo === "chapa" && !s.limpa ? `${s.material ?? "Chapa"} (com sarrafo)` : s.material ?? "";
    const k = `${s.tipo}|${material}|${medida}`;
    const g = grupos.get(k) ?? { tipo: s.tipo, material, medida, qtd: 0, usadas: 0 };
    g.qtd += 1;
    if (s.usado_por) g.usadas += 1;
    grupos.set(k, g);
  }
  const sobras = [...grupos.values()].sort(
    (a, b) => a.tipo.localeCompare(b.tipo) || a.material.localeCompare(b.material) || b.medida.localeCompare(a.medida, "pt-BR", { numeric: true }),
  );
  return (
    <>
      <section className={styles.grupo}>
        <h3 className={styles.tituloGrupo}>Painéis montados por item</h3>
        <p className={`${styles.resumo} tabular-nums`}>
          {dados.disponiveis.itens.length} itens da mesma classe · a coluna “Usado por” mostra o painel do {dados.pavimento} que recebe cada um.
        </p>
        {dados.disponiveis.itens.map((it) => (
          <details
            key={`${it.pavimento}-${it.item}`}
            className={`${styles.itemDisp} ${it.proprio ? styles.itemProprio : ""}`}
            open={it.proprio}
          >
            <summary>
              {it.titulo} <span className={styles.usado}>({it.pavimento} · {it.paineis.length} painéis, {it.paineis.filter((p) => p.usado_por).length} usados)</span>
            </summary>
            <div className={styles.tabelaWrap}>
              <table className={`${styles.tabela} tabular-nums`}>
                <thead>
                  <tr>
                    <th className={styles.esq}>Painel</th>
                    <th>Medida (cm)</th>
                    <th>Ponta c/ sarrafo</th>
                    <th>Tipo</th>
                    <th className={styles.esq}>Usado por</th>
                  </tr>
                </thead>
                <tbody>
                  {it.paineis.map((p) => (
                    <tr key={p.id} className={p.usado_por ? styles.usado : undefined}>
                      <td className={`${styles.esq} ${styles.idPainel}`}>
                        {idCurto(p.id)}
                        <span className={styles.sub}>{p.grupo}</span>
                      </td>
                      <td>{fmt(p.largura_cm)} × {fmt(p.altura_cm)}</td>
                      <td>{pontas(p.pontas)}</td>
                      <td>{p.tipo}</td>
                      <td className={`${styles.esq} ${styles.idPainel}`}>{p.usado_por ? idCurto(p.usado_por) : "disponível"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        ))}
      </section>
      <section className={styles.grupo}>
        <h3 className={styles.tituloGrupo}>Sobras (chapas, recortes e barras)</h3>
        <p className={`${styles.resumo} tabular-nums`}>{dados.disponiveis.sobras.length} sobras · chapas limpas servem a qualquer classe; retalhos com sarrafo e barras, só a esta.</p>
        <div className={styles.tabelaWrap}>
          <table className={`${styles.tabela} tabular-nums`}>
            <thead>
              <tr><th className={styles.esq}>Material</th><th>Medida (cm)</th><th>Qtd</th><th>Usadas no {dados.pavimento}</th></tr>
            </thead>
            <tbody>
              {sobras.map((g) => (
                <tr key={`${g.tipo}|${g.material}|${g.medida}`}>
                  <td className={styles.esq}>{g.material}</td>
                  <td>{g.medida}</td>
                  <td>{g.qtd}</td>
                  <td>{g.usadas || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
