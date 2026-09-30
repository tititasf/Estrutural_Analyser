"use client";

import { useMemo } from "react";
import styles from "./FichaTabs.module.css";
import { MATERIAIS_SUB_ABAS, type MateriaisSubAba } from "./MateriaisTab";

export type FichaTabValue = "estrutural" | "n1" | "n3" | "paineis" | "materiais";

interface SubTabOption {
  id: string;
  label: string;
}

interface FichaTabsProps {
  temN1: boolean;
  temN3: boolean;
  temLv: boolean;
  aba: FichaTabValue;
  onSelecionar: (aba: FichaTabValue) => void;
  tipo?: string;
  /** Pilar: "param"/"passa" — só as vistas N3 desse comportamento. */
  modo?: string | null;
  subAba?: string;
  onSelecionarSubAba?: (sub: string) => void;
  /** Sub-aba de Materiais (na mesma faixa das vistas do desenho). */
  subMateriais?: MateriaisSubAba;
  onSelecionarMateriais?: (sub: MateriaisSubAba) => void;
}

export function FichaTabs({
  temN1,
  temN3,
  temLv,
  aba,
  onSelecionar,
  tipo,
  modo,
  subAba,
  onSelecionarSubAba,
  subMateriais = "pecas",
  onSelecionarMateriais,
}: FichaTabsProps) {
  // Desenho Técnico e Materiais e Construção = 1 aba; as sub-abas dos dois
  // aparecem juntas na faixa de baixo.
  const desenhoOuMateriais = aba === "n3" || aba === "materiais";
  const opcoes = useMemo(() => {
    return [
      { value: "estrutural" as const, label: "Estrutural Limpo" },
      ...(temN1 ? [{ value: "n1" as const, label: "Destaque no Estrutural" }] : []),
      ...(temN3 ? [{ value: "n3" as const, label: "Desenho Técnico, Materiais e Construção" }] : []),
    ];
  }, [temN1, temN3, temLv]);

  // Sub-tabs per element class (identical to the portal)
  const subAbasDisponiveis = useMemo<SubTabOption[]>(() => {
    if (!desenhoOuMateriais) return [];

    switch (tipo) {
      case "pilar":
        // [2026-09-28] Cada código de pilar é de 1 comportamento (param/passa):
        // só as vistas N3 dele. Sem modo (publicação antiga) mostra as duas.
        if (modo === "param" || modo === "passa") {
          const sufixo = modo === "param" ? "para" : "passa";
          const rotulo = modo === "param" ? "Para" : "Passa";
          return [
            { id: "cima", label: "Cima (Seção)" },
            { id: `abcd-${sufixo}`, label: `ABCD ${rotulo}` },
            { id: `grades-${sufixo}`, label: `Grades ${rotulo}` },
          ];
        }
        return [
          { id: "cima", label: "Cima (Seção)" },
          { id: "abcd-para", label: "ABCD Para" },
          { id: "abcd-passa", label: "ABCD Passa" },
          { id: "grades-para", label: "Grades Para" },
          { id: "grades-passa", label: "Grades Passa" },
        ];
      case "laje":
        return [
          { id: "geral", label: "Fôrma N3" },
          { id: "paineis", label: "Painéis & Cotas" },
        ];
      case "viga_fundo":
        return [
          { id: "geral", label: "Fundo Consolidado" },
          { id: "segmentos", label: "Segmentos (S1, S2...)" },
        ];
      case "viga_lateral":
        return [
          { id: "para", label: "Lateral Para" },
          { id: "passa", label: "Lateral Passa" },
          { id: "paineis", label: "Painéis LV" },
        ];
      default:
        return [
          { id: "geral", label: "Detalhamento N3" },
        ];
    }
  }, [desenhoOuMateriais, tipo, modo]);

  // Se sobrou apenas 1 opção, não renderiza tablist (comportamento AC2)
  if (opcoes.length <= 1) {
    return (
      <div className={styles.tabsContainer}>
        {opcoes[0] && <span>{opcoes[0].label}</span>}
      </div>
    );
  }

  return (
    <div className={styles.tabsContainer}>
      <div className={styles.mainTabs} role="tablist" aria-label="Visualização do item">
        {opcoes.map((opcao) => {
          const ativo = aba === opcao.value || (opcao.value === "n3" && desenhoOuMateriais);
          return (
            <button
              key={opcao.value}
              type="button"
              role="tab"
              aria-selected={ativo}
              className={`${styles.tabButton} ${ativo ? styles.active : ""}`}
              onClick={() => !(ativo && opcao.value === "n3") && onSelecionar(opcao.value)}
            >
              {opcao.label}
            </button>
          );
        })}
      </div>

      {subAbasDisponiveis.length > 0 && (
        <div className={styles.subTabsStrip} role="region" aria-label="Sub-visualizações N3">
          {subAbasDisponiveis.map((sub) => {
            const ativo = aba === "n3" && (subAba || subAbasDisponiveis[0].id) === sub.id;
            return (
              <button
                key={sub.id}
                type="button"
                className={`${styles.subTabButton} ${ativo ? styles.subActive : ""}`}
                onClick={() => {
                  if (aba !== "n3") onSelecionar("n3");
                  onSelecionarSubAba?.(sub.id);
                }}
              >
                <span>{sub.label}</span>
              </button>
            );
          })}
          <span className={styles.subSeparador} aria-hidden="true" />
          {MATERIAIS_SUB_ABAS.map(([id, label]) => {
            const ativo = aba === "materiais" && subMateriais === id;
            return (
              <button
                key={id}
                type="button"
                className={`${styles.subTabButton} ${ativo ? styles.subActive : ""}`}
                onClick={() => {
                  if (aba !== "materiais") onSelecionar("materiais");
                  onSelecionarMateriais?.(id);
                }}
              >
                <span>{label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
