// Service worker vanilla (STORY-14) — sem Workbox/next-pwa, decisão de
// kickoff documentada no Dev Agent Record: estratégias exigidas são só 2
// (cache-first / network-first-com-fallback) e o escopo do cache offline é
// deliberadamente pequeno (app-shell + só o ÚLTIMO item consultado, nunca
// histórico ilimitado) — não justifica a complexidade/peso de uma lib de
// terceiros para este MVP.

const APP_SHELL_CACHE = "consulta-publica-app-shell-v1";
const ULTIMO_ITEM_CACHE = "consulta-publica-ultimo-item-v1";

const SVG_RE = /\/api\/v1\/ficha\/[^/]+\/svg\/(n1|n3)$/;
const JSON_FICHA_OU_OBRA_RE = /\/api\/v1\/(ficha|obra)\//;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(APP_SHELL_CACHE).then((cache) => cache.addAll(["/", "/manifest.json"])),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// Escopo do cache offline: só o ÚLTIMO item consultado com sucesso (AC5) —
// a página envia a lista de URLs (JSON da ficha + SVGs n1/n3 + painéis-lv
// se aplicável) via postMessage depois de carregar com sucesso; o SW limpa
// TUDO que já estava em `ULTIMO_ITEM_CACHE` antes de gravar o novo item,
// nunca acumula histórico.
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "CACHE_ULTIMO_ITEM") {
    const urls = event.data.urls || [];
    event.waitUntil(
      caches.open(ULTIMO_ITEM_CACHE).then(async (cache) => {
        const chavesAntigas = await cache.keys();
        await Promise.all(chavesAntigas.map((chave) => cache.delete(chave)));
        await Promise.all(
          urls.map((url) =>
            fetch(url)
              .then((resp) => {
                if (resp.ok) return cache.put(url, resp.clone());
              })
              .catch(() => {}),
          ),
        );
      }),
    );
  }
});

async function cacheFirst(request, cacheName) {
  const cacheado = await caches.match(request);
  if (cacheado) return cacheado;
  try {
    const resposta = await fetch(request);
    if (resposta.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, resposta.clone());
    }
    return resposta;
  } catch (erro) {
    if (cacheado) return cacheado;
    throw erro;
  }
}

async function networkFirstComFallback(request) {
  try {
    return await fetch(request);
  } catch (erro) {
    const cacheado = await caches.match(request);
    if (cacheado) return cacheado;
    throw erro;
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // SVG servido pela API — imutável por content-hash, cache-first (AC3).
  if (SVG_RE.test(url.pathname)) {
    event.respondWith(cacheFirst(request, ULTIMO_ITEM_CACHE));
    return;
  }

  // JSON de ficha/obra/painéis — network-first com fallback pro cache do
  // último item (AC4/AC6): dado pode ter mudado, tenta rede primeiro.
  if (JSON_FICHA_OU_OBRA_RE.test(url.pathname)) {
    event.respondWith(networkFirstComFallback(request));
    return;
  }

  // App-shell same-origin (busca, layout, ícones, chunks estáticos) —
  // cache-first (AC2).
  if (url.origin === self.location.origin) {
    event.respondWith(cacheFirst(request, APP_SHELL_CACHE));
  }
});
