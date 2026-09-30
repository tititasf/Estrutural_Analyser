/** @type {import('next').NextConfig} */
// App-shell estático (busca/layout/ícones) — SEM SSR/SSG do conteúdo da
// ficha (dado privado-por-código, nunca pode ser pré-gerado nem cacheado
// por crawler/CDN). Ficha/Índice de Obra buscam dado 100% client-side.
const nextConfig = {
  reactStrictMode: true,
  // Produção compartilha o domínio do portal sem expor novas portas.
  basePath: process.env.CONSULTA_PUBLICA_BASE_PATH || "",
  // Nginx location /consulta/ exige trailing slash — sem isso Next.js
  // faz 308 /consulta/ → /consulta que cai no location / do portal,
  // criando redirect loop infinito.
  trailingSlash: true,
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
