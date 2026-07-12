/** @type {import('next').NextConfig} */
// App-shell estático (busca/layout/ícones) — SEM SSR/SSG do conteúdo da
// ficha (dado privado-por-código, nunca pode ser pré-gerado nem cacheado
// por crawler/CDN). Ficha/Índice de Obra buscam dado 100% client-side.
const nextConfig = {
  reactStrictMode: true,
  async headers() {
    return [
      {
        // Nunca indexar nenhuma rota deste app — dado é privado-por-código.
        source: "/:path*",
        headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }],
      },
    ];
  },
};

module.exports = nextConfig;
