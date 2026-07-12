"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

type Tema = "light" | "dark";

interface ThemeContextValue {
  tema: Tema;
  solForte: boolean;
  alternarTema: () => void;
  alternarSolForte: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY_TEMA = "consulta-publica:tema";
const STORAGE_KEY_SOL_FORTE = "consulta-publica:sol-forte";

function aplicarAtributos(tema: Tema, solForte: boolean) {
  const root = document.documentElement;
  root.setAttribute("data-theme", tema);
  if (solForte) {
    root.setAttribute("data-contrast", "sol-forte");
  } else {
    root.removeAttribute("data-contrast");
  }
}

/** Provider de tema (Light/Dark) + toggle "Sol forte" (STORY-09, AC2/AC3).
 * "Sol forte" é um override de tokens sobre o tema atual, não um 3º tema
 * independente — front-end-spec §8.4. Persistido em `localStorage`. */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [tema, setTema] = useState<Tema>("light");
  const [solForte, setSolForte] = useState(false);

  useEffect(() => {
    const temaSalvo = window.localStorage.getItem(STORAGE_KEY_TEMA);
    const solForteSalvo = window.localStorage.getItem(STORAGE_KEY_SOL_FORTE);
    const temaInicial: Tema = temaSalvo === "dark" ? "dark" : "light";
    const solForteInicial = solForteSalvo === "true";
    setTema(temaInicial);
    setSolForte(solForteInicial);
    aplicarAtributos(temaInicial, solForteInicial);
  }, []);

  const alternarTema = useCallback(() => {
    setTema((atual) => {
      const novo: Tema = atual === "light" ? "dark" : "light";
      window.localStorage.setItem(STORAGE_KEY_TEMA, novo);
      aplicarAtributos(novo, solForte);
      return novo;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [solForte]);

  const alternarSolForte = useCallback(() => {
    setSolForte((atual) => {
      const novo = !atual;
      window.localStorage.setItem(STORAGE_KEY_SOL_FORTE, String(novo));
      aplicarAtributos(tema, novo);
      return novo;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tema]);

  const valor = useMemo(
    () => ({ tema, solForte, alternarTema, alternarSolForte }),
    [tema, solForte, alternarTema, alternarSolForte],
  );

  return <ThemeContext.Provider value={valor}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const contexto = useContext(ThemeContext);
  if (!contexto) {
    throw new Error("useTheme deve ser usado dentro de <ThemeProvider>");
  }
  return contexto;
}
