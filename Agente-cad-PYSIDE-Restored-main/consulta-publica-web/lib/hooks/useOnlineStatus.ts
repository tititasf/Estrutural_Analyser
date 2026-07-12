"use client";

import { useEffect, useState } from "react";

/** Status de conectividade — usado pelo `StatusBadge` e pela decisão de
 * consulta offline (STORY-08, AC10). `navigator.onLine` é a melhor
 * aproximação disponível sem round-trip de rede; falsos-positivos (online
 * mas sem rota real à API) são tratados pelo timeout do fetch em
 * `resolverCodigo`. */
export function useOnlineStatus(): boolean {
  const [online, setOnline] = useState(true);

  useEffect(() => {
    setOnline(typeof navigator !== "undefined" ? navigator.onLine : true);
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  return online;
}
