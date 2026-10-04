"use client";

import { CadViewer } from "@/components/viewer/CadViewer";
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

export function SvgViewer({ status, svgUrl, descricao, onAmpliar, onErro }: SvgViewerProps) {
  if (status === "loading") {
    return (
      <div className={styles.wrapper}>
        <Skeleton variant="drawing" />
      </div>
    );
  }

  if (status === "error" || !svgUrl) {
    return (
      <div className={styles.wrapper}>
        <div className={styles.erro} role="alert">
          Não foi possível carregar o desenho CAD.
        </div>
      </div>
    );
  }

  return (
    <div className={styles.wrapper}>
      <CadViewer
        svgUrl={svgUrl}
        descricao={descricao}
        onAmpliar={onAmpliar}
        onErro={onErro}
        showFullscreenButton={true}
      />
    </div>
  );
}
