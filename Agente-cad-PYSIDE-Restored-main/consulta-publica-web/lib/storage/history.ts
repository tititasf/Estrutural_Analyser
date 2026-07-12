// Histórico local de itens consultados (STORY-08, AC6/AC11) — 100%
// client-side (`localStorage`), nunca sincronizado com o backend. Máximo 8
// entradas, mais recente primeiro.

export interface HistoryEntry {
  code: string;
  titulo: string;
  tipo: string;
  obra_rotulo: string | null;
  timestamp: number;
  cached_offline: boolean;
}

const STORAGE_KEY = "consulta-publica:historico";
const MAX_ENTRIES = 8;

function lerBruto(): HistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function salvarBruto(entradas: HistoryEntry[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entradas));
  } catch {
    // Quota excedida ou localStorage indisponível (modo privado) — falha
    // silenciosa, histórico é conveniência, não dado crítico.
  }
}

export function listarHistorico(): HistoryEntry[] {
  return lerBruto().sort((a, b) => b.timestamp - a.timestamp);
}

export function adicionarAoHistorico(entrada: Omit<HistoryEntry, "timestamp">): void {
  const atuais = lerBruto().filter((e) => e.code !== entrada.code);
  const nova: HistoryEntry = { ...entrada, timestamp: Date.now() };
  const atualizadas = [nova, ...atuais].slice(0, MAX_ENTRIES);
  salvarBruto(atualizadas);
}

export function removerDoHistorico(code: string): void {
  salvarBruto(lerBruto().filter((e) => e.code !== code));
}

export function marcarCacheadoOffline(code: string, cached: boolean): void {
  const atuais = lerBruto();
  const idx = atuais.findIndex((e) => e.code === code);
  if (idx === -1) return;
  atuais[idx] = { ...atuais[idx], cached_offline: cached };
  salvarBruto(atuais);
}

/** O service worker (STORY-14) cacheia só o ÚLTIMO item consultado, nunca
 * histórico ilimitado (AC5) — então o badge `⭳off` do histórico local
 * também deve refletir isso: só 1 entrada por vez pode estar marcada. */
export function marcarApenasEsteCacheadoOffline(code: string): void {
  const atuais = lerBruto().map((e) => ({ ...e, cached_offline: e.code === code }));
  salvarBruto(atuais);
}
