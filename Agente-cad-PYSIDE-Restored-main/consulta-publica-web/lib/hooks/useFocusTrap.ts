"use client";

import { useEffect, useRef } from "react";

/** Focus trap simples (STORY-11, AC9) — quando `ativo`, prende Tab/Shift+Tab
 * dentro do container e devolve o foco ao elemento que estava focado antes
 * de abrir, ao fechar. */
export function useFocusTrap(ativo: boolean) {
  const containerRef = useRef<HTMLDivElement>(null);
  const elementoAnteriorRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!ativo) return;

    elementoAnteriorRef.current = document.activeElement as HTMLElement | null;
    const container = containerRef.current;
    const focaveisSelector =
      'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

    function obterFocaveis(): HTMLElement[] {
      if (!container) return [];
      return Array.from(container.querySelectorAll<HTMLElement>(focaveisSelector));
    }

    const primeiro = obterFocaveis()[0];
    primeiro?.focus();

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key !== "Tab") return;
      const focaveis = obterFocaveis();
      if (focaveis.length === 0) return;
      const primeiro = focaveis[0];
      const ultimo = focaveis[focaveis.length - 1];

      if (e.shiftKey && document.activeElement === primeiro) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && document.activeElement === ultimo) {
        e.preventDefault();
        primeiro.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      elementoAnteriorRef.current?.focus();
    };
  }, [ativo]);

  return containerRef;
}
