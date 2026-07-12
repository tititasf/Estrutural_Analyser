import { readFileSync } from "fs";
import { join } from "path";

// Verificação estática (CSS puro, sem JS de resize) do reflow tabela↔cartão
// abaixo de 380px — mesma limitação de JSDOM já documentada nas stories
// anteriores (não computa layout real). AC2/AC3.
describe("PanelTable — reflow sem scroll horizontal (AC2/AC3)", () => {
  it("tem breakpoint em 380px que esconde a tabela e mostra os cartões", () => {
    const css = readFileSync(
      join(__dirname, "..", "..", "components", "ui", "PanelTable.module.css"),
      "utf-8",
    );
    expect(css).toMatch(/@media \(max-width:\s*380px\)/);
    const blocoBreakpoint = css.match(/@media \(max-width:\s*380px\)\s*{([\s\S]*)}/)?.[1] ?? "";
    expect(blocoBreakpoint).toMatch(/\.tabela\s*{[^}]*display:\s*none/);
    expect(blocoBreakpoint).toMatch(/\.cartoes\s*{[^}]*display:\s*flex/);
  });
});
