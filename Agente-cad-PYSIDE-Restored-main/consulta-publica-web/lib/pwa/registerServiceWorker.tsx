"use client";

import { useEffect } from "react";

/** Registra `public/sw.js` (STORY-14) — montado 1x no `RootLayout`. Falha
 * silenciosa se o browser não suporta service workers (não é crítico para
 * o funcionamento online do app). */
export function RegisterServiceWorker() {
  useEffect(() => {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }, []);

  return null;
}
