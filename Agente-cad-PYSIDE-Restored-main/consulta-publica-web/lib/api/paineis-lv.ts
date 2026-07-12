import { API_BASE_URL, RESOLVE_TIMEOUT_MS } from "@/lib/config";

export interface PainelBruto {
  width: number;
  height1: number;
  height2: number;
  panel_type: string;
}

export interface PaineisLvData {
  total_width: number | null;
  h_section: number | null;
  paineis: Record<string, PainelBruto[]>;
}

export type PaineisLvResult =
  | { status: "ok"; data: PaineisLvData }
  | { status: "not_found" }
  | { status: "network_error" };

export async function buscarPaineisLv(code: string): Promise<PaineisLvResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), RESOLVE_TIMEOUT_MS);

  try {
    const resp = await fetch(`${API_BASE_URL}/api/v1/ficha/${encodeURIComponent(code)}/paineis-lv`, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!resp.ok) {
      return { status: "not_found" };
    }
    const data = (await resp.json()) as PaineisLvData;
    return { status: "ok", data };
  } catch {
    return { status: "network_error" };
  } finally {
    clearTimeout(timeout);
  }
}
