import { API_BASE_URL, RESOLVE_TIMEOUT_MS } from "@/lib/config";

export type ResolveResult =
  | { status: "ok"; kind: "item" | "obra" | "pavimento"; code: string }
  | { status: "not_found" }
  | { status: "blocked"; retryAfterSeconds: number }
  | { status: "network_error" };

/** Chama `GET /api/v1/resolve/{code}` (STORY-03). Nunca diferencia os
 * motivos de "não encontrado" no retorno — só `not_found` genérico (AC8,
 * princípio de design "Silêncio seguro"). */
export async function resolverCodigo(codigo: string): Promise<ResolveResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), RESOLVE_TIMEOUT_MS);

  try {
    const resp = await fetch(`${API_BASE_URL}/api/v1/resolve/${encodeURIComponent(codigo)}`, {
      signal: controller.signal,
      cache: "no-store",
    });

    if (resp.status === 429) {
      const corpo = await resp.json().catch(() => ({}));
      const retry = Number(corpo?.retry_after_seconds ?? 30);
      return { status: "blocked", retryAfterSeconds: Number.isFinite(retry) ? retry : 30 };
    }

    if (resp.status === 404) {
      return { status: "not_found" };
    }

    if (!resp.ok) {
      return { status: "not_found" };
    }

    const corpo = await resp.json();
    if (corpo?.kind !== "item" && corpo?.kind !== "obra" && corpo?.kind !== "pavimento") {
      return { status: "not_found" };
    }
    return { status: "ok", kind: corpo.kind, code: corpo.code ?? codigo };
  } catch {
    return { status: "network_error" };
  } finally {
    clearTimeout(timeout);
  }
}
