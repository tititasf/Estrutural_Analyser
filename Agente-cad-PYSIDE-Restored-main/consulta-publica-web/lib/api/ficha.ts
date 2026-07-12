import { API_BASE_URL, RESOLVE_TIMEOUT_MS } from "@/lib/config";

export interface FichaData {
  code: string;
  tipo: string;
  titulo: string;
  obra_rotulo: string | null;
  pavimento_label: string;
  campos: Record<string, string>;
  atencao: string;
  svg: { n1: string | null; n3: string | null };
  tem_lv: boolean;
}

export type FichaResult =
  | { status: "ok"; data: FichaData }
  | { status: "not_found" }
  | { status: "network_error" };

/** URL absoluta pronta pra usar em `<img src>` — o campo `svg.n1`/`svg.n3`
 * da resposta já vem como path relativo (`/api/v1/ficha/{code}/svg/n1`). */
export function urlAbsolutaSvg(pathRelativo: string): string {
  return `${API_BASE_URL}${pathRelativo}`;
}

export async function buscarFicha(code: string): Promise<FichaResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), RESOLVE_TIMEOUT_MS);

  try {
    const resp = await fetch(`${API_BASE_URL}/api/v1/ficha/${encodeURIComponent(code)}`, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!resp.ok) {
      return { status: "not_found" };
    }
    const data = (await resp.json()) as FichaData;
    return { status: "ok", data };
  } catch {
    return { status: "network_error" };
  } finally {
    clearTimeout(timeout);
  }
}
