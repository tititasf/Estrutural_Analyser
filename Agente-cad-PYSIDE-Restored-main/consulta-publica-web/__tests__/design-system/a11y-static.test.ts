import { readFileSync, readdirSync } from "fs";
import { join, extname } from "path";

const RAIZ_PROJETO = join(__dirname, "..", "..");

function listarArquivosCss(dir: string): string[] {
  const resultado: string[] = [];
  for (const entrada of readdirSync(dir, { withFileTypes: true })) {
    if (entrada.name === "node_modules" || entrada.name === ".next") continue;
    const caminho = join(dir, entrada.name);
    if (entrada.isDirectory()) {
      resultado.push(...listarArquivosCss(caminho));
    } else if (extname(entrada.name) === ".css") {
      resultado.push(caminho);
    }
  }
  return resultado;
}

describe("Foco visível — nunca outline:none sem substituto (AC7/9.2)", () => {
  it("nenhum arquivo CSS remove outline sem um :focus-visible correspondente no mesmo arquivo", () => {
    const arquivos = listarArquivosCss(RAIZ_PROJETO);
    for (const arquivo of arquivos) {
      const conteudo = readFileSync(arquivo, "utf-8");
      const removeOutline = /outline\s*:\s*none/i.test(conteudo);
      if (removeOutline) {
        const temSubstituto = /:focus-visible/.test(conteudo);
        expect(temSubstituto).toBe(true);
      }
    }
  });

  it("tokens.css define um anel de foco global (:focus-visible)", () => {
    const tokens = readFileSync(join(RAIZ_PROJETO, "styles", "tokens.css"), "utf-8");
    expect(tokens).toMatch(/:focus-visible\s*{[^}]*outline:\s*3px solid var\(--primary\)/);
  });
});

describe("prefers-reduced-motion respeitado globalmente (AC9)", () => {
  it("tokens.css tem bloco @media (prefers-reduced-motion: reduce)", () => {
    const tokens = readFileSync(join(RAIZ_PROJETO, "styles", "tokens.css"), "utf-8");
    expect(tokens).toMatch(/@media \(prefers-reduced-motion: reduce\)/);
  });
});

describe("--paper nunca muda entre temas (front-end-spec §6.1)", () => {
  it("apenas :root define --paper — nenhum override em [data-theme='dark']", () => {
    const tokens = readFileSync(join(RAIZ_PROJETO, "styles", "tokens.css"), "utf-8");
    const blocoDark = tokens.match(/:root\[data-theme="dark"\]\s*{([^}]*)}/);
    expect(blocoDark).not.toBeNull();
    // Só barra uma DECLARAÇÃO real (--paper: ...); o bloco tem um comentário
    // mencionando --paper de propósito (documenta que ele é herdado).
    expect(blocoDark![1]).not.toMatch(/--paper\s*:/);
  });
});
