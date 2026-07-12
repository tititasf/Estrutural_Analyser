"use client";

import { useEffect, useState } from "react";
import { Skeleton } from "@/components/ui/Skeleton";
import { PanelTable, type PanelItem } from "@/components/ui/PanelTable";
import { buscarPaineisLv, type PaineisLvData, type PainelBruto } from "@/lib/api/paineis-lv";
import styles from "./PaineisLvTab.module.css";

type Estado = "loading" | "ok" | "ausente";

interface PaineisLvTabProps {
  code: string;
  ativo: boolean;
}

function converterPaineis(brutos: PainelBruto[]): PanelItem[] {
  return brutos.map((p, indice) => ({
    numero: indice + 1,
    larguraCm: p.width,
    tipo: p.panel_type,
  }));
}

/** Aba Painéis LV dentro da Ficha (STORY-13) — fetch sob demanda de
 * `/paineis-lv` (STORY-12) só quando a aba está `ativo` (mesmo padrão lazy
 * do SVG, STORY-11). 404 vira nota neutra, nunca quebra as demais abas
 * (AC5). `PanelTable` já cuida do reflow tabela↔cartão via CSS puro
 * (STORY-09, AC2/AC3). */
export function PaineisLvTab({ code, ativo }: PaineisLvTabProps) {
  const [estado, setEstado] = useState<Estado>("loading");
  const [dados, setDados] = useState<PaineisLvData | null>(null);

  useEffect(() => {
    if (!ativo || dados !== null) return;
    let cancelado = false;

    async function carregar() {
      const resultado = await buscarPaineisLv(code);
      if (cancelado) return;
      if (resultado.status === "ok") {
        setDados(resultado.data);
        setEstado("ok");
      } else {
        setEstado("ausente");
      }
    }

    carregar();
    return () => {
      cancelado = true;
    };
  }, [ativo, code, dados]);

  if (!ativo) return null;

  if (estado === "loading") {
    return (
      <div className={styles.wrapper} role="status" aria-live="polite">
        <Skeleton variant="block" rotulo="carregando painéis" />
        <Skeleton variant="block" />
      </div>
    );
  }

  if (estado === "ausente" || !dados) {
    return <p className={styles.notaAusente}>Lista de painéis não disponível para este item.</p>;
  }

  return (
    <div className={styles.wrapper}>
      <p className={`${styles.resumo} tabular-nums`}>
        {dados.total_width !== null && <>Largura total: {dados.total_width} cm</>}
        {dados.total_width !== null && dados.h_section !== null && "   ·   "}
        {dados.h_section !== null && <>Altura: {dados.h_section} cm</>}
      </p>

      {Object.entries(dados.paineis).map(([lado, brutos]) => (
        <PanelTable key={lado} lado={lado} paineis={converterPaineis(brutos)} />
      ))}
    </div>
  );
}
