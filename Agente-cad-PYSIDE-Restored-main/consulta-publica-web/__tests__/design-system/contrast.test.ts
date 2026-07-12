import { razaoDeContraste } from "@/lib/theme/contrast";

// Verifica 2 coisas por par de tokens: (1) a REGRA WCAG real que o par deve
// satisfazer (4.5:1 texto normal / 3:1 componente de UI — a garantia que
// front-end-spec.md §9.1 promete cumprir "com folga"), e (2) que o número
// calculado aqui não diverge grosseiramente do documentado em §8.2/§8.3/§8.4
// (SANITY_TOLERANCE larga — pequenas diferenças de arredondamento entre
// ferramentas de cálculo de contraste são esperadas e não são bug).
const WCAG_TEXTO = 4.5;
const WCAG_UI = 3.0;
const SANITY_TOLERANCE = 1.5;

interface CasoContraste {
  nome: string;
  corA: string;
  corB: string;
  documentado: number;
  pisoWcag: number;
  /** Alguns valores da spec são notados como piso aberto ("7:1+"), não um
   * número exato — nesses casos o valor real pode superar bastante o
   * documentado sem que isso seja divergência/bug. */
  documentadoEhPisoAberto?: boolean;
}

function checar({ nome, corA, corB, documentado, pisoWcag, documentadoEhPisoAberto }: CasoContraste) {
  it(`${nome}: atende WCAG ≥${pisoWcag}:1 e está próximo do documentado (${documentado}:1)`, () => {
    const ratio = razaoDeContraste(corA, corB);
    expect(ratio).toBeGreaterThanOrEqual(pisoWcag);
    if (documentadoEhPisoAberto) {
      expect(ratio).toBeGreaterThanOrEqual(documentado - SANITY_TOLERANCE);
    } else {
      expect(Math.abs(ratio - documentado)).toBeLessThanOrEqual(SANITY_TOLERANCE);
    }
  });
}

describe("Contraste — Light 'Canteiro' (§8.2)", () => {
  const casos: CasoContraste[] = [
    { nome: "--fg vs --bg", corA: "#0A0E14", corB: "#FFFFFF", documentado: 19.3, pisoWcag: WCAG_TEXTO },
    { nome: "--fg-muted vs --bg", corA: "#3A4453", corB: "#FFFFFF", documentado: 9.1, pisoWcag: WCAG_TEXTO },
    { nome: "--border vs --bg", corA: "#5B6675", corB: "#FFFFFF", documentado: 4.9, pisoWcag: WCAG_UI },
    { nome: "--primary (texto branco)", corA: "#0B4DA2", corB: "#FFFFFF", documentado: 8.2, pisoWcag: WCAG_TEXTO },
    { nome: "--success (texto branco)", corA: "#0B6B29", corB: "#FFFFFF", documentado: 5.9, pisoWcag: WCAG_TEXTO },
    { nome: "--warning-bg vs texto preto", corA: "#FBBF24", corB: "#0A0E14", documentado: 10.8, pisoWcag: WCAG_TEXTO },
    { nome: "--error (texto branco)", corA: "#B4231C", corB: "#FFFFFF", documentado: 6.3, pisoWcag: WCAG_TEXTO },
  ];
  casos.forEach(checar);
});

describe("Contraste — Dark (§8.3)", () => {
  const casos: CasoContraste[] = [
    { nome: "--fg vs --bg", corA: "#F5F7FA", corB: "#0A0E14", documentado: 17.8, pisoWcag: WCAG_TEXTO },
    { nome: "--fg-muted vs --bg", corA: "#AEB9C7", corB: "#0A0E14", documentado: 8.4, pisoWcag: WCAG_TEXTO },
    { nome: "--border vs --bg", corA: "#5C6A7C", corB: "#0A0E14", documentado: 4.6, pisoWcag: WCAG_UI },
    { nome: "--primary vs --bg", corA: "#5DA0FF", corB: "#0A0E14", documentado: 8.7, pisoWcag: WCAG_TEXTO },
    { nome: "--success vs --bg", corA: "#34D06A", corB: "#0A0E14", documentado: 9.1, pisoWcag: WCAG_TEXTO },
    { nome: "--warning-bg vs texto preto", corA: "#F5B301", corB: "#0A0E14", documentado: 11, pisoWcag: WCAG_TEXTO },
    { nome: "--error vs --bg", corA: "#FF6B60", corB: "#0A0E14", documentado: 6.0, pisoWcag: WCAG_TEXTO },
  ];
  casos.forEach(checar);
});

describe("Contraste — 'Sol forte' (§8.4, extremo)", () => {
  const casos: CasoContraste[] = [
    { nome: "--fg preto vs --bg branco", corA: "#000000", corB: "#FFFFFF", documentado: 21, pisoWcag: WCAG_TEXTO },
    {
      nome: "--fg-muted vs --bg", corA: "#1A1A1A", corB: "#FFFFFF", documentado: 7, pisoWcag: WCAG_TEXTO,
      documentadoEhPisoAberto: true, // spec anota "7:1+" — piso, não valor exato
    },
    { nome: "--primary (texto branco)", corA: "#003A87", corB: "#FFFFFF", documentado: 10, pisoWcag: WCAG_TEXTO },
  ];
  casos.forEach(checar);
});
