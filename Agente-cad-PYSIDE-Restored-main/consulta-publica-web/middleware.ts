import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Reforço do header X-Robots-Tag (já setado globalmente via next.config.js
// headers() — este middleware garante o mesmo header mesmo em cenários de
// runtime/edge onde o config de headers estático não se aplicaria, ex.:
// respostas geradas dinamicamente fora do pipeline normal do Next).
export function middleware(_request: NextRequest) {
  const response = NextResponse.next();
  response.headers.set("X-Robots-Tag", "noindex, nofollow");
  return response;
}

export const config = {
  matcher: "/:path*",
};
