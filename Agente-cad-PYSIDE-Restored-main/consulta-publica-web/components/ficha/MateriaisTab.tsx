"use client";

import { useEffect, useState } from "react";
import { Skeleton } from "@/components/ui/Skeleton";
import { buscarMateriais, type GrupoMateriais, type MateriaisData } from "@/lib/api/materiais";
import styles from "./MateriaisTab.module.css";

type Estado = "loading" | "ok" | "ausente";

interface MateriaisTabProps {
  code: string;
  ativo: boolean;
}

const fmt = (n: number, casas = 1) =>
  n.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: casas });

function Grupo({ grupo }: { grupo: GrupoMateriais }) {
  if (!grupo.disponivel) {
    return (
      <section className={styles.grupo}>
        <h3 className={styles.tituloGrupo}>{grupo.titulo}</h3>
        <p className={styles.nota}>Desenho técnico não disponível para medir.</p>
      </section>
    );
  }
  const paineis = grupo.paineis ?? [];
  const sarrafos = grupo.sarrafos ?? [];
  const temFace = paineis.some((p) => p.face);
  return (
    <section className={styles.grupo}>
      <h3 className={styles.tituloGrupo}>{grupo.titulo}</h3>

      {paineis.length > 0 && (
        <>
          <p className={`${styles.resumo} tabular-nums`}>
            Painéis: {grupo.paineis_total} un · {fmt(grupo.paineis_area_m2 ?? 0, 2)} m²
          </p>
          <div className={styles.tabelaWrap}>
            <table className={`${styles.tabela} tabular-nums`}>
              <thead>
                <tr>{temFace && <th>Face</th>}<th>Largura (cm)</th><th>Altura (cm)</th><th>Qtd</th></tr>
              </thead>
              <tbody>
                {paineis.map((p, i) => (
                  <tr key={i}>
                    {temFace && <td>{p.face}</td>}
                    <td>{fmt(p.largura_cm)}</td>
                    <td>{fmt(p.altura_cm)}</td>
                    <td>
                      {p.quantidade}
                      {p.recortado && <span className={styles.tag} title="Painel com recorte: medida é o retângulo envolvente">recortado</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {grupo.largura_da_face && grupo.largura_da_face !== "desenhada" && (
            <p className={styles.nota}>Largura das faces pela {grupo.largura_da_face}.</p>
          )}
        </>
      )}

      {sarrafos.map((s) => (
        <div key={s.bitola}>
          <p className={`${styles.resumo} tabular-nums`}>
            {s.bitola}: {s.pecas} peças · {fmt(s.total_m, 2)} m
          </p>
          <div className={styles.tabelaWrap}>
            <table className={`${styles.tabela} tabular-nums`}>
              <thead>
                <tr><th>Comprimento (cm)</th><th>Qtd</th></tr>
              </thead>
              <tbody>
                {s.cortes.map((c) => (
                  <tr key={c.comprimento_cm}>
                    <td>{fmt(c.comprimento_cm)}</td>
                    <td>{c.quantidade}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {paineis.length === 0 && sarrafos.length === 0 && (
        <p className={styles.nota}>Nenhum painel ou sarrafo desenhado.</p>
      )}
    </section>
  );
}

const pct = (a: number) => `${Math.round(a * 100)}%`;

function Compra({ compra }: { compra: NonNullable<MateriaisData["compra"]> }) {
  const linhas = [
    ...(compra.chapas ? [{ ...compra.chapas, qtd: compra.chapas.chapas, un: "chapas", detalhe: "" }] : []),
    ...compra.barras.map((b) => ({
      ...b,
      qtd: b.barras,
      un: "barras",
      detalhe: `${b.pecas} peças · ${fmt(b.total_m, 2)} m`,
    })),
  ];
  if (linhas.length === 0) return null;
  return (
    <section className={`${styles.grupo} ${styles.compra}`}>
      <h3 className={styles.tituloGrupo}>Material de compra</h3>
      <div className={styles.tabelaWrap}>
        <table className={`${styles.tabela} tabular-nums`}>
          <thead>
            <tr><th className={styles.esq}>Material</th><th>Qtd</th><th>Aproveitamento</th><th>Emendas</th></tr>
          </thead>
          <tbody>
            {linhas.map((l) => (
              <tr key={l.material}>
                <td className={styles.esq}>
                  {l.material}
                  {l.detalhe && <span className={styles.sub}>{l.detalhe}</span>}
                </td>
                <td>{l.qtd} {l.un}</td>
                <td>{pct(l.aproveitamento)}</td>
                <td>{l.emendas || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={styles.nota}>
        Plano de corte das peças abaixo: painéis de chapa 244 × 122 cm, sarrafos de barra de 3 m.
        Sem perda de serra nem quebra — é o mínimo para cortar o que está desenhado.
      </p>
    </section>
  );
}

/** Aba "Materiais e Construção" [2026-09-28] — painéis e sarrafos medidos
 * no desenho técnico (N3) que a equipe recebe. Pilar: ABCD + Grades (Cima
 * é só perspectiva); LV: laterais por lado (Corte é só perspectiva); fundo:
 * painéis + sarrafos; laje: só painéis. Fetch só quando a aba abre. */
export function MateriaisTab({ code, ativo }: MateriaisTabProps) {
  const [estado, setEstado] = useState<Estado>("loading");
  const [dados, setDados] = useState<MateriaisData | null>(null);

  useEffect(() => {
    if (!ativo || dados !== null) return;
    let cancelado = false;
    buscarMateriais(code).then((r) => {
      if (cancelado) return;
      if (r.status === "ok") {
        setDados(r.data);
        setEstado("ok");
      } else {
        setEstado("ausente");
      }
    });
    return () => {
      cancelado = true;
    };
  }, [ativo, code, dados]);

  if (!ativo) return null;
  if (estado === "loading") {
    return (
      <div className={styles.wrapper} role="status" aria-live="polite">
        <Skeleton variant="block" rotulo="medindo o desenho técnico" />
        <Skeleton variant="block" />
      </div>
    );
  }
  if (estado === "ausente" || !dados || dados.grupos.length === 0) {
    return <p className={styles.nota}>Lista de materiais não disponível para este item.</p>;
  }
  return (
    <div className={styles.wrapper}>
      <p className={styles.fonte}>Quantidades medidas no desenho técnico (N3).</p>
      {dados.compra && <Compra compra={dados.compra} />}
      {dados.grupos.map((g) => (
        <Grupo key={g.titulo} grupo={g} />
      ))}
    </div>
  );
}
