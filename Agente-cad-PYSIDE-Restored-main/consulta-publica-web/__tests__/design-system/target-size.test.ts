import { readFileSync } from "fs";
import { join } from "path";

// Verificação ESTÁTICA (varredura de fonte) de que os componentes-núcleo
// tocáveis declaram o alvo mínimo de 56px (`--target-min`) — AC6/AC12.
// JSDOM não computa layout real (CSS Modules não geram valores de pixel em
// teste), então esta é uma verificação de INTENÇÃO no código-fonte, não uma
// medição de `getBoundingClientRect` real; a confirmação visual final foi
// feita manualmente no Browser pane (ver Dev Agent Record da STORY-08).
const RAIZ = join(__dirname, "..", "..", "components");

const ARQUIVOS_COM_ALVO_TOCAVEL = [
  "CodeInput.module.css",
  "HistoryChip.module.css",
  "ui/Button.module.css",
  "ui/Segmented.module.css",
  "ui/SvgViewer.module.css",
];

describe("Alvo tocável mínimo (56px) — verificação estática de fonte", () => {
  it.each(ARQUIVOS_COM_ALVO_TOCAVEL)("%s declara --target-min (56px) em pelo menos um seletor", (caminho) => {
    const conteudo = readFileSync(join(RAIZ, caminho), "utf-8");
    const declaraAlvo = /var\(--target-min\)|var\(--target-primary\)|\b56px\b|\b64px\b/.test(conteudo);
    expect(declaraAlvo).toBe(true);
  });
});

describe("Token --target-min está definido como 56px", () => {
  it("tokens.css define --target-min: 56px e --target-primary: 64px", () => {
    const tokens = readFileSync(join(__dirname, "..", "..", "styles", "tokens.css"), "utf-8");
    expect(tokens).toMatch(/--target-min:\s*56px/);
    expect(tokens).toMatch(/--target-primary:\s*64px/);
  });
});
