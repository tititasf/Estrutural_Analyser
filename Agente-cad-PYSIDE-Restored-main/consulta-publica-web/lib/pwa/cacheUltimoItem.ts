import { API_BASE_URL } from "@/lib/config";
import type { FichaData } from "@/lib/api/ficha";
import { marcarApenasEsteCacheadoOffline } from "@/lib/storage/history";

/** Envia ao service worker (`public/sw.js`) a lista de URLs do item recém
 * carregado para cachear como "último item offline" (STORY-14, AC5) — o SW
 * limpa qualquer cache anterior antes de gravar (escopo: só 1 item por
 * vez). Sem confirmação por `MessageChannel` (simplificação deliberada de
 * escopo, documentada no Dev Agent Record) — marca o histórico como
 * cacheado de forma otimista assim que a mensagem é enviada. */
export function cachearUltimoItem(ficha: FichaData): void {
  if (typeof navigator === "undefined") return;
  const controller = navigator.serviceWorker?.controller;
  if (!controller) return;

  const urls = [`${API_BASE_URL}/api/v1/ficha/${ficha.code}`];
  if (ficha.svg.n1) urls.push(`${API_BASE_URL}${ficha.svg.n1}`);
  if (ficha.svg.n3) urls.push(`${API_BASE_URL}${ficha.svg.n3}`);
  if (ficha.tem_lv) urls.push(`${API_BASE_URL}/api/v1/ficha/${ficha.code}/paineis-lv`);

  controller.postMessage({ type: "CACHE_ULTIMO_ITEM", urls });
  marcarApenasEsteCacheadoOffline(ficha.code);
}
