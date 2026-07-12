import { API_BASE_URL, RESOLVE_TIMEOUT_MS } from "@/lib/config";

export interface ObraItem {
  code: string;
  titulo: string;
  tipo: string;
}

export interface ObraPavimento {
  /** Código próprio do pavimento [2026-07-12] — "ficha do pavimento"/
   * recorte limpo da torre; resolve direto via `/api/v1/pavimento/{code}`
   * sem precisar do código da obra inteira. */
  code: string | null;
  pavimento_label: string;
  itens: ObraItem[];
}

export interface ObraData {
  obra_rotulo: string | null;
  pavimentos: ObraPavimento[];
}

export type ObraResult =
  | { status: "ok"; data: ObraData }
  | { status: "not_found" }
  | { status: "network_error" };

export async function buscarIndiceObra(code: string): Promise<ObraResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), RESOLVE_TIMEOUT_MS);

  try {
    const resp = await fetch(`${API_BASE_URL}/api/v1/obra/${encodeURIComponent(code)}`, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!resp.ok) {
      return { status: "not_found" };
    }
    const data = (await resp.json()) as ObraData;
    return { status: "ok", data };
  } catch {
    return { status: "network_error" };
  } finally {
    clearTimeout(timeout);
  }
}
