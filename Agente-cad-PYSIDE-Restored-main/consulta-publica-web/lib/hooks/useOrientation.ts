"use client";

import { useEffect, useState } from "react";

export type Orientacao = "portrait" | "landscape";

/** Orientação atual do viewport (STORY-11, AC7) — usada só para permitir o
 * reflow de layout (app-bar encolhe em landscape); o nível de zoom em si é
 * um valor absoluto de escala que não é resetado por mudança de
 * orientação, então já "se preserva" naturalmente sem lógica adicional. */
export function useOrientation(): Orientacao {
  const [orientacao, setOrientacao] = useState<Orientacao>("portrait");

  useEffect(() => {
    const mq = window.matchMedia("(orientation: landscape)");
    setOrientacao(mq.matches ? "landscape" : "portrait");
    const handler = (e: MediaQueryListEvent) => setOrientacao(e.matches ? "landscape" : "portrait");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  return orientacao;
}
