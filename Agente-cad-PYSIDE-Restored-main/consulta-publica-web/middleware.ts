import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// O header X-Robots-Tag é setado globalmente via next.config.js headers()
// e também pelo nginx. Middleware mantido apenas para compatibilidade futura
// mas com matcher restrito para não interferir com rotas estáticas.
export function middleware(_request: NextRequest) {
  const response = NextResponse.next();
  response.headers.set("X-Robots-Tag", "noindex, nofollow");
  return response;
}

export const config = {
  // Só aplica em rotas dinâmicas (ficha, obra, pavimento) — nunca na raiz
  matcher: ['/ficha/:path*', '/obra/:path*', '/pavimento/:path*'],
};
