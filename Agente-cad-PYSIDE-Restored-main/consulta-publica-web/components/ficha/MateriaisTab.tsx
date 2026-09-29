"use client";

import { useEffect, useState } from "react";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  buscarMateriais,
  buscarReaproveitamento,
  type CorteSarrafo,
  type GrupoMateriais,
  type MateriaisData,
  type ReaproveitamentoData,
} from "@/lib/api/materiais";
import { ChapasViewer } from "./ChapasViewer";
import { MontagemPaineis } from "./MontagemPaineis";
import { MateriaisDisponiveis, PreparacaoReaproveitada } from "./Reaproveitamento";
import styles from "./MateriaisTab.module.css";

/** [1,2,3,5] → "1–3, 5" */
function faixas(nums?: number[]): string {
  if (!nums || nums.length === 0) return "—";
  const out: string[] = [];
  let ini = nums[0];
  let ant = nums[0];
  for (const n of [...nums.slice(1), NaN]) {
    if (n === ant + 1) {
      ant = n;
      continue;
    }
    out.push(ini === ant ? `${ini}` : `${ini}–${ant}`);
    ini = ant = n;
  }
  return out.join(", ");
}

type Estado = "loading" | "ok" | "ausente";
type Preparacao = "novos" | "reaproveitados" | "disponiveis";
const PREPARACAO: [Preparacao, string][] = [
  ["novos", "Preparação com Materiais Novos"],
  ["reaproveitados", "Preparação com Materiais Reaproveitados e Novos"],
  ["disponiveis", "Materiais Disponíveis dos Pavimentos Anteriores"],
];
export type MateriaisSubAba = "pecas" | "compra" | "montagem";
type SubAba = MateriaisSubAba;

export const MATERIAIS_SUB_ABAS: [MateriaisSubAba, string][] = [
  ["pecas", "Painéis e sarrafos"],
  ["compra", "Material necessário, preparação e reaproveitamento"],
  ["montagem", "Montagem painéis"],
];

interface MateriaisTabProps {
  code: string;
  ativo: boolean;
  /** Sub-aba vinda da faixa da ficha (aba única Desenho Técnico + Materiais):
   * controlada de fora, sem as mini-abas internas. */
  sub?: MateriaisSubAba;
}

const fmt = (n: number, casas = 1) =>
  n.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: casas });

/** "Sarrafo 2.2 x 7 cm" → "2,2 x 7"; pressão fica por extenso. */
const bitolaCurta = (b: string) =>
  /press/i.test(b) ? "Pressão 2,2 x 7" : b.replace(/^Sarrafo\s*/i, "").replace(/\s*cm$/i, "").replace(/\./g, ",");

function ListaSarrafos({ itens }: { itens?: CorteSarrafo[] }) {
  if (!itens || itens.length === 0) return <span className={styles.sub}>—</span>;
  return (
    <ul className={styles.listaSarr}>
      {itens.map((c) => (
        <li key={`${c.bitola}-${c.comprimento_cm}`}>
          {c.quantidade} × {fmt(c.comprimento_cm)} cm <span className={styles.bitola}>{bitolaCurta(c.bitola)}</span>
        </li>
      ))}
    </ul>
  );
}

function Grupo({ grupo, laje }: { grupo: GrupoMateriais; laje: boolean }) {
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
                <tr>
                  <th>Nº</th>
                  <th className={styles.esq}>ID Painel</th>
                  {temFace && <th>Face</th>}
                  <th>Largura (cm)</th>
                  <th>Altura (cm)</th>
                  {laje && <th className={styles.esq}>Classe de painel</th>}
                  {laje && <th>Pode ser reaproveitado</th>}
                  {!laje && <th className={styles.esq}>Sarrafos do painel</th>}
                </tr>
              </thead>
              <tbody>
                {paineis.map((p, i) => (
                  <tr key={p.id ?? i}>
                    <td>{p.numero ?? faixas(p.numeros)}</td>
                    <td className={`${styles.esq} ${styles.idPainel}`}>{p.id ?? "—"}</td>
                    {temFace && <td>{p.face}</td>}
                    <td>{fmt(p.largura_cm)}</td>
                    <td>
                      {fmt(p.altura_cm)}
                      {p.recortado && <span className={styles.tag} title="Painel com recorte: medida é o retângulo envolvente">recortado</span>}
                    </td>
                    {laje && <td className={styles.esq}>{p.classe}</td>}
                    {laje && <td>{p.reaproveitavel ? "Sim" : "Não"}</td>}
                    {!laje && (
                      <td className={styles.esq}>
                        <ListaSarrafos itens={p.sarrafos} />
                      </td>
                    )}
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

      {paineis.length > 0 && (grupo.sarrafos_avulsos?.length ?? 0) > 0 && (
        <div className={styles.avulsos}>
          <p className={styles.resumo}>Sarrafos fora de painel</p>
          <ListaSarrafos itens={grupo.sarrafos_avulsos} />
        </div>
      )}

      {paineis.length === 0 &&
        (grupo.grades && grupo.grades.length > 0
          ? grupo.grades.map((g) => (
              <div key={g.rotulo} className={styles.grade}>
                <p className={`${styles.resumo} tabular-nums`}>
                  Grade {g.rotulo} · lado {g.face}: {g.pecas.reduce((n, c) => n + c.quantidade, 0)} peças
                </p>
                <div className={styles.tabelaWrap}>
                  <table className={`${styles.tabela} tabular-nums`}>
                    <thead>
                      <tr><th className={styles.esq}>Material</th><th>Comprimento (cm)</th><th>Qtd</th></tr>
                    </thead>
                    <tbody>
                      {g.pecas.map((c, i) => [
                        c.sentido && c.sentido !== g.pecas[i - 1]?.sentido && (
                          <tr key={`h-${c.sentido}`} className={styles.linhaSentido}>
                            <td colSpan={3} className={styles.esq}>
                              {c.sentido === "vertical" ? "Sarrafos verticais" : "Sarrafos horizontais"}
                            </td>
                          </tr>
                        ),
                        <tr key={`${c.sentido}-${c.bitola}-${c.comprimento_cm}`}>
                          <td className={styles.esq}>{c.bitola.replace(/\./g, ",").replace(/3,5 x 7 cm/, "3,5 x 7 cm (meio pontalete)")}</td>
                          <td>{fmt(c.comprimento_cm)}</td>
                          <td>{c.quantidade}</td>
                        </tr>,
                      ])}
                    </tbody>
                  </table>
                </div>
              </div>
            ))
          : sarrafos.map((s) => (
              <div key={s.bitola}>
                <p className={`${styles.resumo} tabular-nums`}>{s.bitola}: {s.pecas} peças · {fmt(s.total_m, 2)} m</p>
                <ListaSarrafos itens={s.cortes.map((c) => ({ ...c, bitola: s.bitola }))} />
              </div>
            )))}

      {paineis.length === 0 && sarrafos.length === 0 && (
        <p className={styles.nota}>Nenhum painel ou sarrafo desenhado.</p>
      )}
    </section>
  );
}

const pct = (a: number) => `${Math.round(a * 100)}%`;

function Compra({
  compra,
  grupos,
  titulo = "Material de compra",
}: {
  compra: NonNullable<MateriaisData["compra"]>;
  grupos: GrupoMateriais[];
  titulo?: string;
}) {
  const paineis = Object.fromEntries(grupos.flatMap((g) => (g.paineis ?? []).filter((p) => p.id).map((p) => [p.id!, p])));
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
      <h3 className={styles.tituloGrupo}>{titulo}</h3>
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
      {compra.chapas?.layout && compra.chapas.layout.length > 0 && (
        <ChapasViewer layout={compra.chapas.layout} paineis={paineis} />
      )}
      {(compra.sobras?.length ?? 0) > 0 && (
        <div className={styles.avulsos}>
          <p className={`${styles.resumo} tabular-nums`}>Sobras para reaproveitamento: {compra.sobras!.length}</p>
          <div className={styles.tabelaWrap}>
            <table className={`${styles.tabela} tabular-nums`}>
              <thead>
                <tr><th className={styles.esq}>ID Sobra</th><th className={styles.esq}>Material</th><th className={styles.esq}>De</th><th>Medida (cm)</th></tr>
              </thead>
              <tbody>
                {compra.sobras!.map((s) => (
                  <tr key={s.id}>
                    <td className={`${styles.esq} ${styles.idPainel}`}>{s.id}</td>
                    <td className={styles.esq}>{s.material}</td>
                    <td className={styles.esq}>
                      {s.origem}
                      {s.recorte_de && (
                        <span className={styles.sub}>recorte de {s.recorte_de.map((i) => i.split("-").pop()).join(", ")}</span>
                      )}
                    </td>
                    <td>
                      {s.tipo === "chapa"
                        ? `${fmt(s.largura_cm ?? 0)} × ${fmt(s.altura_cm ?? 0)}`
                        : fmt(s.comprimento_cm ?? 0)}
                      {s.util && <span className={styles.sub}>útil {fmt(s.util.largura_cm)} × {fmt(s.util.altura_cm)}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

/** Aba "Materiais e Construção" [2026-09-28] — painéis e sarrafos medidos
 * no desenho técnico (N3) que a equipe recebe. Pilar: ABCD + Grades (Cima
 * é só perspectiva); LV: laterais por lado (Corte é só perspectiva); fundo:
 * painéis + sarrafos; laje: só painéis. Fetch só quando a aba abre. */
export function MateriaisTab({ code, ativo, sub: subExterna }: MateriaisTabProps) {
  const [estado, setEstado] = useState<Estado>("loading");
  const [dados, setDados] = useState<MateriaisData | null>(null);
  const [subInterna, setSub] = useState<SubAba>("pecas");
  const sub = subExterna ?? subInterna;
  const [prep, setPrep] = useState<Preparacao>("novos");
  const [reap, setReap] = useState<ReaproveitamentoData | null>(null);
  const [estadoReap, setEstadoReap] = useState<Estado>("loading");
  const precisaReap = ativo && sub === "compra" && prep !== "novos";

  useEffect(() => {
    if (!precisaReap || reap !== null) return;
    let cancelado = false;
    let espera: ReturnType<typeof setTimeout> | undefined;
    setEstadoReap("loading");
    const buscar = () =>
      buscarReaproveitamento(code).then((r) => {
        if (cancelado) return;
        if (r.status === "ok") {
          setReap(r.data);
          setEstadoReap("ok");
        } else if (r.status === "calculando") {
          espera = setTimeout(buscar, 5000); // o cenário inteiro é medido em segundo plano
        } else {
          setEstadoReap("ausente");
        }
      });
    buscar();
    return () => {
      cancelado = true;
      clearTimeout(espera);
    };
  }, [precisaReap, code, reap]);

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
      {!subExterna && <div className={styles.miniAbas} role="tablist" aria-label="Materiais">
        {MATERIAIS_SUB_ABAS.map(([v, r]) => (
          <button
            key={v}
            role="tab"
            aria-selected={sub === v}
            className={`${styles.miniAba} ${sub === v ? styles.miniAbaAtiva : ""}`}
            onClick={() => setSub(v)}
          >
            {r}
          </button>
        ))}
      </div>}
      {sub === "pecas" && (
        <>
          <p className={styles.fonte}>Quantidades medidas no desenho técnico (N3).</p>
          {dados.grupos.map((g) => (
            <Grupo key={g.titulo} grupo={g} laje={dados.tipo === "laje"} />
          ))}
        </>
      )}
      {sub === "compra" && (
        <>
          <div className={styles.miniAbas} role="tablist" aria-label="Preparação">
            {PREPARACAO.map(([v, r]) => (
              <button
                key={v}
                role="tab"
                aria-selected={prep === v}
                className={`${styles.miniAba} ${prep === v ? styles.miniAbaAtiva : ""}`}
                onClick={() => setPrep(v)}
              >
                {r}
              </button>
            ))}
          </div>
          {prep === "novos" &&
            (dados.compra ? <Compra compra={dados.compra} grupos={dados.grupos} /> : <p className={styles.nota}>Sem material de compra.</p>)}
          {prep !== "novos" && estadoReap === "loading" && (
            <div role="status" aria-live="polite">
              <Skeleton variant="block" rotulo="cruzando todas as classes do pavimento com o estoque dos anteriores (pode levar alguns minutos na primeira vez)" />
            </div>
          )}
          {prep !== "novos" && estadoReap === "ausente" && (
            <p className={styles.nota}>Reaproveitamento não disponível para este item.</p>
          )}
          {prep === "reaproveitados" && reap && (
            <PreparacaoReaproveitada
              dados={reap}
              renderCompra={(c) =>
                c.chapas || c.barras.length > 0 ? (
                  <Compra compra={c} grupos={dados.grupos} titulo="Material novo (só o que faltou)" />
                ) : null
              }
            />
          )}
          {prep === "disponiveis" && reap && <MateriaisDisponiveis dados={reap} />}
        </>
      )}
      {sub === "montagem" && <MontagemPaineis grupos={dados.grupos} />}
    </div>
  );
}
