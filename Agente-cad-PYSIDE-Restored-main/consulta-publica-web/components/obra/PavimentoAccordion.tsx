"use client";

import { useState, useMemo, useEffect } from "react";
import { ChevronDown, ChevronRight, QrCode } from "lucide-react";
import Link from "next/link";
import type { ObraPavimento } from "@/lib/api/obra";
import { TypeIcon, type TipoElemento } from "@/components/ui/TypeIcon";
import styles from "./PavimentoAccordion.module.css";

interface PavimentoAccordionProps {
  pavimento: ObraPavimento;
  expandido: boolean;
  onAlternar: () => void;
  onSelecionarItem: (code: string) => void;
}

type TabPrincipal = "pilar" | "viga_fundo" | "viga_lateral" | "laje";
type SubTabModo = "param" | "passa";

function ehTipoElemento(tipo: string): tipo is TipoElemento {
  return tipo === "pilar" || tipo === "viga_fundo" || tipo === "viga_lateral" || tipo === "laje";
}

/** AcordeÃ£o de 1 pavimento â€” cabecalho expansÃ­vel com abas internas. */
export function PavimentoAccordion({ pavimento, expandido, onAlternar, onSelecionarItem }: PavimentoAccordionProps) {
  const [aba, setAba] = useState<TabPrincipal>("pilar");
  const [subAba, setSubAba] = useState<SubTabModo>("param");

  // Quando abre o acordeÃ£o pela primeira vez, foca na primeira aba que tem itens
  useEffect(() => {
    if (expandido && pavimento.itens.length > 0) {
      if (pavimento.itens.some(i => i.tipo === "pilar")) setAba("pilar");
      else if (pavimento.itens.some(i => i.tipo === "viga_fundo")) setAba("viga_fundo");
      else if (pavimento.itens.some(i => i.tipo === "viga_lateral")) setAba("viga_lateral");
      else if (pavimento.itens.some(i => i.tipo === "laje")) setAba("laje");
    }
  }, [expandido, pavimento.itens]);

  const itensFiltrados = useMemo(() => {
    return pavimento.itens.filter(item => {
      if (item.tipo !== aba) return false;
      if (aba === "pilar" || aba === "viga_lateral") {
        const itemModo = item.modo || "param"; // Fallback se backend nÃ£o enviou modo
        if (itemModo !== subAba) return false;
      }
      return true;
    });
  }, [pavimento.itens, aba, subAba]);

  return (
    <div className={styles.wrapper}>
      <button
        type="button"
        className={styles.cabecalho}
        onClick={onAlternar}
        aria-expanded={expandido}
      >
        {expandido ? <ChevronDown size={20} aria-hidden="true" /> : <ChevronRight size={20} aria-hidden="true" />}
        <span className={styles.rotulo}>{pavimento.pavimento_label.toUpperCase()}</span>
        <span className={styles.contagem}>({pavimento.itens.length})</span>
      </button>

      {pavimento.code && (
        <Link
          href={`/pavimento/${pavimento.code}`}
          className={styles.abrirFicha}
          aria-label={`Abrir ficha do pavimento ${pavimento.pavimento_label} (cÃ³digo ${pavimento.code})`}
          onClick={(e) => e.stopPropagation()}
        >
          <QrCode size={16} aria-hidden="true" /> Ver todos os itens deste pavimento em uma tela cheia
        </Link>
      )}

      {expandido && (
        <div className={styles.itens}>
          {pavimento.itens.length === 0 ? (
            <p className={styles.vazio}>Nenhum item publicado neste pavimento.</p>
          ) : (
            <>
              <div className={styles.abasPrincipais}>
                <button 
                  className={`${styles.abaBtn} ${aba === 'pilar' ? styles.abaAtiva : ''}`}
                  onClick={() => setAba('pilar')}
                >
                  Pilares
                </button>
                <button 
                  className={`${styles.abaBtn} ${aba === 'viga_fundo' ? styles.abaAtiva : ''}`}
                  onClick={() => setAba('viga_fundo')}
                >
                  Fundos de Vigas
                </button>
                <button 
                  className={`${styles.abaBtn} ${aba === 'viga_lateral' ? styles.abaAtiva : ''}`}
                  onClick={() => setAba('viga_lateral')}
                >
                  Laterais de Vigas
                </button>
                <button 
                  className={`${styles.abaBtn} ${aba === 'laje' ? styles.abaAtiva : ''}`}
                  onClick={() => setAba('laje')}
                >
                  Lajes
                </button>
              </div>

              {(aba === "pilar" || aba === "viga_lateral") && (
                <div className={styles.subAbasContainer}>
                  <button 
                    className={`${styles.subAbaBtn} ${subAba === 'param' ? styles.subAbaAtiva : ''}`}
                    onClick={() => setSubAba('param')}
                  >
                    Vigas Param
                  </button>
                  <button 
                    className={`${styles.subAbaBtn} ${subAba === 'passa' ? styles.subAbaAtiva : ''}`}
                    onClick={() => setSubAba('passa')}
                  >
                    Vigas Passam
                  </button>
                </div>
              )}

              <div className={styles.listaGrid}>
                {itensFiltrados.length === 0 ? (
                  <p className={styles.vazio} style={{ gridColumn: '1 / -1' }}>Nenhum item para esta seleÃ§Ã£o.</p>
                ) : (
                  itensFiltrados.map((item) => {
                    const isVigaFundoOuLateral = item.tipo === "viga_fundo" || item.tipo === "viga_lateral";
                    const tituloLimpo = isVigaFundoOuLateral ? item.titulo.split(" (segmento")[0] : item.titulo;

                    return (
                      <button key={item.code} type="button" className={styles.cardItem} onClick={() => onSelecionarItem(item.code)}>
                        <div className={styles.cardIcon}>
                          {ehTipoElemento(item.tipo) && <TypeIcon tipo={item.tipo} />}
                        </div>
                        <span className={styles.cardTitulo}>{tituloLimpo}</span>
                      </button>
                    );
                  })
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

