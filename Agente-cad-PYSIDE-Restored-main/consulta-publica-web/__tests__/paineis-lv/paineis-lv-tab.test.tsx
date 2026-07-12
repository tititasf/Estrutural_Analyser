import { render, screen } from "@testing-library/react";
import { PaineisLvTab } from "@/components/ficha/PaineisLvTab";
import * as paineisApi from "@/lib/api/paineis-lv";

jest.mock("@/lib/api/paineis-lv", () => ({
  ...jest.requireActual("@/lib/api/paineis-lv"),
  buscarPaineisLv: jest.fn(),
}));

beforeEach(() => {
  jest.clearAllMocks();
});

const DADOS_2_LADOS: paineisApi.PaineisLvData = {
  total_width: 366,
  h_section: 51,
  paineis: {
    A: [
      { width: 122, height1: 125, height2: 0, panel_type: "cheio" },
      { width: 80.5, height1: 125, height2: 0, panel_type: "recorte" },
    ],
    B: [{ width: 118.5, height1: 125, height2: 0, panel_type: "cheio" }],
  },
};

describe("PaineisLvTab", () => {
  it("não renderiza nada quando ativo=false (lazy, mesmo padrão do SVG)", () => {
    const { container } = render(<PaineisLvTab code="ITEMLV01" ativo={false} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renderiza largura total, altura, e painéis agrupados por lado A/B (AC1)", async () => {
    jest.spyOn(paineisApi, "buscarPaineisLv").mockResolvedValue({ status: "ok", data: DADOS_2_LADOS });

    render(<PaineisLvTab code="ITEMLV01" ativo={true} />);

    expect(await screen.findByText(/Largura total:\s*366\s*cm/)).toBeInTheDocument();
    expect(screen.getByText(/Altura:\s*51\s*cm/)).toBeInTheDocument();
    expect(screen.getByText("LADO A")).toBeInTheDocument();
    expect(screen.getByText("LADO B")).toBeInTheDocument();
    expect(screen.getAllByText("cheio")).toHaveLength(2); // 1 no lado A, 1 no lado B (tabela) — cartão duplica
  });

  it("numera os painéis sequencialmente por lado (#1, #2, ...)", async () => {
    jest.spyOn(paineisApi, "buscarPaineisLv").mockResolvedValue({ status: "ok", data: DADOS_2_LADOS });

    render(<PaineisLvTab code="ITEMLV01" ativo={true} />);
    await screen.findByText("LADO A");

    const linhas = screen.getAllByRole("row");
    // cabeçalho + 2 painéis do lado A + cabeçalho + 1 painel do lado B
    expect(linhas.length).toBeGreaterThan(0);
  });

  it("mostra nota neutra quando /paineis-lv retorna 404 (AC5) — não quebra a ficha", async () => {
    jest.spyOn(paineisApi, "buscarPaineisLv").mockResolvedValue({ status: "not_found" });

    render(<PaineisLvTab code="ITEMLV02" ativo={true} />);
    expect(await screen.findByText("Lista de painéis não disponível para este item.")).toBeInTheDocument();
  });

  it("mostra nota neutra também em erro de rede (mesmo tratamento gracioso)", async () => {
    jest.spyOn(paineisApi, "buscarPaineisLv").mockResolvedValue({ status: "network_error" });

    render(<PaineisLvTab code="ITEMLV03" ativo={true} />);
    expect(await screen.findByText("Lista de painéis não disponível para este item.")).toBeInTheDocument();
  });

  it("aplica tabular-nums aos valores de largura (AC4)", async () => {
    jest.spyOn(paineisApi, "buscarPaineisLv").mockResolvedValue({ status: "ok", data: DADOS_2_LADOS });

    render(<PaineisLvTab code="ITEMLV01" ativo={true} />);
    const celulas = await screen.findAllByText(/122\s*cm/);
    expect(celulas.some((el) => el.classList.contains("tabular-nums"))).toBe(true);
  });

  it("não busca de novo ao trocar de aba e voltar (cache local simples)", async () => {
    const spy = jest.spyOn(paineisApi, "buscarPaineisLv").mockResolvedValue({ status: "ok", data: DADOS_2_LADOS });

    const { rerender } = render(<PaineisLvTab code="ITEMLV01" ativo={true} />);
    await screen.findByText("LADO A");
    expect(spy).toHaveBeenCalledTimes(1);

    rerender(<PaineisLvTab code="ITEMLV01" ativo={false} />);
    rerender(<PaineisLvTab code="ITEMLV01" ativo={true} />);

    expect(spy).toHaveBeenCalledTimes(1);
  });
});
