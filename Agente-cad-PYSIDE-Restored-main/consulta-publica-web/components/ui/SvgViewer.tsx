"use client";

import { Maximize2 } from "lucide-react";
import { Skeleton } from "./Skeleton";
import styles from "./SvgViewer.module.css";

type SvgViewerStatus = "loading" | "loaded" | "error";

interface SvgViewerProps {
  status: SvgViewerStatus;
  svgUrl?: string;
  descricao: string;
  onAmpliar?: () => void;
  onErro?: () => void;
}

/** Shell do visualizador de SVG (§8.8) — papel branco sempre (`--paper`,
 * nunca inverte em dark mode). Zoom/pan/fullscreen real é a STORY-11; aqui
 * só os 3 estados de carregamento e o botão "Ampliar". `onErro` é chamado
 * se o `<img>` falhar ao carregar o recurso mesmo com `status="loaded"`
 * (AC4/STORY-10 — o chamador decide o que fazer, ex.: trocar pro EmptyState
 * "svg-error"). */
export function SvgViewer({ status, svgUrl, descricao, onAmpliar, onErro }: SvgViewerProps) {
  return (
    <div className={styles.wrapper}>
      {status === "loading" && <Skeleton variant="drawing" />}

      {status === "error" && (
        <div className={styles.erro} role="alert">
          Não foi possível carregar o desenho.
        </div>
      )}

      {status === "loaded" && svgUrl && (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={svgUrl} alt={descricao} className={styles.imagem} onError={onErro} />
          {onAmpliar && (
            <button type="button" className={styles.botaoAmpliar} onClick={onAmpliar} aria-label="Ampliar desenho">
              <Maximize2 size={20} aria-hidden="true" /> AMPLIAR
            </button>
          )}
        </>
      )}
    </div>
  );
}
