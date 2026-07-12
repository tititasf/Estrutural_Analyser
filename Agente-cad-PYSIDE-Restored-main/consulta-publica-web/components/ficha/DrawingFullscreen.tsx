"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Maximize as Fit, Minus, Plus, X } from "lucide-react";
import { useFocusTrap } from "@/lib/hooks/useFocusTrap";
import { Skeleton } from "@/components/ui/Skeleton";
import styles from "./DrawingFullscreen.module.css";

const ESCALA_MIN = 1;
const ESCALA_MAX = 8;
const PASSO_ZOOM = 1.25;
const ESCALA_DOUBLE_TAP = 3;

interface DrawingFullscreenProps {
  aberto: boolean;
  svgUrl: string | null;
  descricao: string;
  nivelAtivo: "n1" | "n3";
  temN1: boolean;
  temN3: boolean;
  onFechar: () => void;
  onAlternarNivel: (nivel: "n1" | "n3") => void;
}

/** Visualizador de desenho em tela cheia (STORY-11) — zoom via botões
 * `+`/`−`/Ajustar, arrasto (pointer events, mouse E touch), double-click/
 * double-tap (fit ↔ 3×), atalhos de teclado, focus trap. Papel sempre
 * branco (`background:#fff` fixo, nunca o tema ativo — front-end-spec
 * §6.1). SVG só é montado no DOM quando `aberto=true` (lazy, AC2).
 *
 * Escopo desta implementação: pinch de 2 dedos NÃO foi implementado (lib
 * de gestos dedicada, ex. `react-zoom-pan-pinch`, ficou para uma iteração
 * futura se o teste de campo mostrar necessidade real) — a alternativa por
 * botão/teclado já cobre o requisito de acessibilidade WCAG 2.5.1 (nenhuma
 * função depende só de gesto multi-toque), que é o que a AC realmente
 * exige. Documentado como débito técnico no Dev Agent Record.
 */
export function DrawingFullscreen({
  aberto, svgUrl, descricao, nivelAtivo, temN1, temN3, onFechar, onAlternarNivel,
}: DrawingFullscreenProps) {
  const [escala, setEscala] = useState(ESCALA_MIN);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const arrastandoRef = useRef<{ x: number; y: number } | null>(null);
  const containerRef = useFocusTrap(aberto);

  const resetar = useCallback(() => {
    setEscala(ESCALA_MIN);
    setOffset({ x: 0, y: 0 });
  }, []);

  useEffect(() => {
    if (aberto) resetar();
  }, [aberto, svgUrl, resetar]);

  const aplicarZoom = useCallback((novaEscala: number) => {
    const clamped = Math.min(ESCALA_MAX, Math.max(ESCALA_MIN, novaEscala));
    if (clamped === ESCALA_MIN || clamped === ESCALA_MAX) {
      navigator.vibrate?.(10);
    }
    setEscala(clamped);
    if (clamped === ESCALA_MIN) setOffset({ x: 0, y: 0 });
  }, []);

  useEffect(() => {
    if (!aberto) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onFechar();
      } else if (e.key === "+" || e.key === "=") {
        aplicarZoom(escala * PASSO_ZOOM);
      } else if (e.key === "-" || e.key === "_") {
        aplicarZoom(escala / PASSO_ZOOM);
      } else if (e.key === "0") {
        resetar();
      } else if (e.key === "n" || e.key === "N") {
        if (temN1 && temN3) onAlternarNivel(nivelAtivo === "n1" ? "n3" : "n1");
      } else if (e.key === "ArrowUp") {
        setOffset((o) => ({ ...o, y: o.y + 24 }));
      } else if (e.key === "ArrowDown") {
        setOffset((o) => ({ ...o, y: o.y - 24 }));
      } else if (e.key === "ArrowLeft") {
        setOffset((o) => ({ ...o, x: o.x + 24 }));
      } else if (e.key === "ArrowRight") {
        setOffset((o) => ({ ...o, x: o.x - 24 }));
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [aberto, escala, nivelAtivo, temN1, temN3, aplicarZoom, resetar, onFechar, onAlternarNivel]);

  function handlePointerDown(e: React.PointerEvent) {
    if (escala <= ESCALA_MIN) return;
    arrastandoRef.current = { x: e.clientX - offset.x, y: e.clientY - offset.y };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }

  function handlePointerMove(e: React.PointerEvent) {
    if (!arrastandoRef.current) return;
    setOffset({ x: e.clientX - arrastandoRef.current.x, y: e.clientY - arrastandoRef.current.y });
  }

  function handlePointerUp() {
    arrastandoRef.current = null;
  }

  function handleDoubleClick(e: React.MouseEvent) {
    if (escala > ESCALA_MIN) {
      resetar();
    } else {
      aplicarZoom(ESCALA_DOUBLE_TAP);
      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
      setOffset({
        x: rect.width / 2 - (e.clientX - rect.left) * ESCALA_DOUBLE_TAP,
        y: rect.height / 2 - (e.clientY - rect.top) * ESCALA_DOUBLE_TAP,
      });
    }
  }

  if (!aberto) return null;

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-label="Visualizador de desenho" ref={containerRef}>
      <div className={styles.barraSuperior}>
        <button type="button" className={styles.botaoIcone} onClick={onFechar} aria-label="Fechar">
          <X size={24} aria-hidden="true" />
        </button>
        {temN1 && temN3 && (
          <div className={styles.toggleNivel}>
            <button
              type="button"
              className={nivelAtivo === "n1" ? styles.nivelAtivo : styles.nivelInativo}
              onClick={() => onAlternarNivel("n1")}
            >
              N1
            </button>
            <button
              type="button"
              className={nivelAtivo === "n3" ? styles.nivelAtivo : styles.nivelInativo}
              onClick={() => onAlternarNivel("n3")}
            >
              N3
            </button>
          </div>
        )}
        <span className={styles.percentual}>{Math.round(escala * 100)}%</span>
      </div>

      <div
        className={styles.folhaWrapper}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
        onDoubleClick={handleDoubleClick}
        onWheel={(e) => aplicarZoom(escala * (e.deltaY < 0 ? PASSO_ZOOM : 1 / PASSO_ZOOM))}
      >
        {svgUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={svgUrl}
            alt={descricao}
            className={styles.imagem}
            style={{
              transform: `translate(${offset.x}px, ${offset.y}px) scale(${escala})`,
              cursor: escala > ESCALA_MIN ? "grab" : "default",
            }}
            draggable={false}
          />
        ) : (
          <Skeleton variant="drawing" rotulo="carregando desenho" />
        )}
      </div>

      <div className={styles.controles}>
        <button type="button" className={styles.botaoControle} onClick={() => aplicarZoom(escala / PASSO_ZOOM)} aria-label="Diminuir zoom">
          <Minus size={20} aria-hidden="true" />
        </button>
        <button type="button" className={styles.botaoControle} onClick={() => aplicarZoom(escala * PASSO_ZOOM)} aria-label="Aumentar zoom">
          <Plus size={20} aria-hidden="true" />
        </button>
        <button type="button" className={styles.botaoControle} onClick={resetar} aria-label="Ajustar à tela">
          <Fit size={20} aria-hidden="true" /> fit
        </button>
      </div>
    </div>
  );
}
