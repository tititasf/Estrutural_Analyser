import { readFileSync } from "fs";
import { join } from "path";

// service worker roda num escopo global diferente (self, não window/jsdom)
// — não é executável diretamente em Jest. Verificação estática de que as
// estratégias exigidas (AC2/AC3/AC4/AC5) estão de fato presentes no
// arquivo publicado, mesma abordagem já usada para CSS nas STORY-09/13.
const SW_PATH = join(__dirname, "..", "..", "public", "sw.js");

describe("public/sw.js — estratégias de cache (STORY-14)", () => {
  const conteudo = readFileSync(SW_PATH, "utf-8");

  it("SVG (/svg/n1 ou /svg/n3) usa cache-first (AC3)", () => {
    expect(conteudo).toMatch(/SVG_RE[\s\S]*svg\\\/\(n1\|n3\)/);
    expect(conteudo).toMatch(/SVG_RE\.test\(url\.pathname\)/);
  });

  it("JSON de ficha/obra usa network-first com fallback (AC4)", () => {
    expect(conteudo).toMatch(/JSON_FICHA_OU_OBRA_RE/);
    expect(conteudo).toMatch(/networkFirstComFallback/);
  });

  it("app-shell same-origin usa cache-first (AC2)", () => {
    expect(conteudo).toMatch(/url\.origin === self\.location\.origin/);
  });

  it("escopo do cache do último item é limpo antes de cada novo item (AC5 — nunca acumula)", () => {
    expect(conteudo).toMatch(/CACHE_ULTIMO_ITEM/);
    expect(conteudo).toMatch(/cache\.delete\(chave\)/);
  });

  it("não intercepta requisições que não são GET (nunca cacheia mutações)", () => {
    expect(conteudo).toMatch(/request\.method !== "GET"/);
  });
});

describe("public/manifest.json — installability (AC1/AC9)", () => {
  const manifest = JSON.parse(
    readFileSync(join(__dirname, "..", "..", "public", "manifest.json"), "utf-8"),
  );

  it("tem os campos obrigatórios de um manifest PWA válido", () => {
    expect(manifest.name).toBeTruthy();
    expect(manifest.short_name).toBeTruthy();
    expect(manifest.display).toBe("standalone");
    expect(manifest.start_url).toBeTruthy();
    expect(manifest.theme_color).toBeTruthy();
    expect(manifest.background_color).toBeTruthy();
  });

  it("tem pelo menos 1 ícone 'any' e 1 'maskable'", () => {
    const propositos = manifest.icons.map((i: { purpose: string }) => i.purpose);
    expect(propositos).toContain("any");
    expect(propositos).toContain("maskable");
  });
});
