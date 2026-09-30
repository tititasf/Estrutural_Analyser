import { API_BASE_URL, RESOLVE_TIMEOUT_MS } from "@/lib/config";

export interface FichaData {
  code: string;
  tipo: string;
  titulo: string;
  obra_rotulo: string | null;
  pavimento_label: string;
  pavimento_code: string | null;
  campos: Record<string, string>;
  atencao: string;
  svg: { n1: string | null; n3: string | null };
  tem_lv: boolean;
  /** [2026-09-28] "param"/"passa" — pilar tem 1 código por comportamento das vigas. */
  modo?: "param" | "passa" | null;
}

/** Título exibido: pilar ganha o comportamento das vigas no nome. */
export function tituloFicha(f: Pick<FichaData, "tipo" | "titulo" | "modo">): string {
  if (f.tipo === "pilar" && f.modo === "param") return `${f.titulo} - Vigas param no Pilar`;
  if (f.tipo === "pilar" && f.modo === "passa") return `${f.titulo} - Vigas passam no Pilar`;
  return f.titulo;
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

export interface ViewsData {
  tipo: string;
  classe: string;
  views: Record<string, { svg?: string | null; available: boolean } | any>;
}

export type ViewsResult =
  | { status: "ok"; data: ViewsData }
  | { status: "not_found" }
  | { status: "network_error" };

export async function buscarViewsFicha(code: string): Promise<ViewsResult> {
  const controller = new AbortController();
  // As sub-vistas incluem SVGs embutidos e podem exigir renderização no servidor.
  // O prazo curto da ficha básica descartava o N3 de lajes antes de chegar.
  const timeout = setTimeout(() => controller.abort(), 30_000);

  try {
    const resp = await fetch(`${API_BASE_URL}/api/v1/ficha/${encodeURIComponent(code)}/views`, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!resp.ok) {
      return { status: "not_found" };
    }
    const data = (await resp.json()) as ViewsData;
    return { status: "ok", data };
  } catch {
    return { status: "network_error" };
  } finally {
    clearTimeout(timeout);
  }
}

