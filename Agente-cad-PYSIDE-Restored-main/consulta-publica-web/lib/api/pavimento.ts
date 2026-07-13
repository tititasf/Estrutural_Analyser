import { API_BASE_URL, RESOLVE_TIMEOUT_MS } from "@/lib/config";
import type { ObraItem } from "@/lib/api/obra";

export interface PavimentoData {
  obra_rotulo: string | null;
  obra_code: string | null;
  pavimento_label: string;
  itens: ObraItem[];
}

export type PavimentoResult =
  | { status: "ok"; data: PavimentoData }
  | { status: "not_found" }
  | { status: "network_error" };

/** "Ficha do pavimento"/recorte limpo da torre [2026-07-12] — busca
 * `GET /api/v1/pavimento/{code}`, mesma forma de 1 entrada de
 * `ObraData.pavimentos[]`, mas resolvida direto pelo código do pavimento. */
export async function buscarPavimento(code: string): Promise<PavimentoResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), RESOLVE_TIMEOUT_MS);

  try {
    const resp = await fetch(`${API_BASE_URL}/api/v1/pavimento/${encodeURIComponent(code)}`, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!resp.ok) {
      return { status: "not_found" };
    }
    const data = (await resp.json()) as PavimentoData;
    return { status: "ok", data };
  } catch {
    return { status: "network_error" };
  } finally {
    clearTimeout(timeout);
  }
}
