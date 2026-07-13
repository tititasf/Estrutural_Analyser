import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import IndiceObraPage from "@/app/obra/[code]/page";
import * as obraApi from "@/lib/api/obra";

const pushMock = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

jest.mock("@/lib/api/obra");

function obraBase(overrides: Partial<obraApi.ObraData> = {}): obraApi.ObraData {
  return {
    obra_rotulo: "Obra ·· A3F",
    pavimentos: [
      {
        code: "PAVCODE_TERREO",
        pavimento_label: "Térreo",
        itens: [
          { code: "ITEM_P1", titulo: "Pilar P1", tipo: "pilar" },
          { code: "ITEM_V301", titulo: "Viga V301", tipo: "viga_lateral" },
        ],
      },
      { code: "PAVCODE_COBERTURA", pavimento_label: "Cobertura", itens: [] },
    ],
    ...overrides,
  };
}

beforeEach(() => {
  pushMock.mockClear();
  jest.clearAllMocks();
});

describe("Índice de Obra", () => {
  it("renderiza pavimentos com contagem de itens", async () => {
    jest.spyOn(obraApi, "buscarIndiceObra").mockResolvedValue({ status: "ok", data: obraBase() });

    render(<IndiceObraPage params={{ code: "OBRACODE1" }} />);

    expect(await screen.findByText("Obra ·· A3F")).toBeInTheDocument();
    expect(screen.getByText("TÉRREO")).toBeInTheDocument();
    expect(screen.getByText("(2)")).toBeInTheDocument();
    expect(screen.getByText("COBERTURA")).toBeInTheDocument();
    expect(screen.getByText("(0)")).toBeInTheDocument();
  });

  it("pavimento sem itens mostra estado vazio ao expandir (AC7)", async () => {
    jest.spyOn(obraApi, "buscarIndiceObra").mockResolvedValue({ status: "ok", data: obraBase() });

    render(<IndiceObraPage params={{ code: "OBRACODE1" }} />);
    await screen.findByText("COBERTURA");

    await userEvent.click(screen.getByText("COBERTURA"));
    expect(await screen.findByText("Nenhum item publicado neste pavimento.")).toBeInTheDocument();
  });

  it("clicar em um item navega para /ficha/{code do item} (AC9)", async () => {
    jest.spyOn(obraApi, "buscarIndiceObra").mockResolvedValue({ status: "ok", data: obraBase() });

    render(<IndiceObraPage params={{ code: "OBRACODE1" }} />);
    // 1º pavimento com itens começa expandido.
    await userEvent.click(await screen.findByText("Pilar P1"));

    expect(pushMock).toHaveBeenCalledWith("/ficha/ITEM_P1");
  });

  it("filtro local client-side não dispara nova requisição (AC8)", async () => {
    const spy = jest.spyOn(obraApi, "buscarIndiceObra").mockResolvedValue({ status: "ok", data: obraBase() });

    render(<IndiceObraPage params={{ code: "OBRACODE1" }} />);
    await screen.findByText("Pilar P1");
    expect(spy).toHaveBeenCalledTimes(1);

    await userEvent.type(screen.getByLabelText(/buscar item/i), "Viga");

    expect(screen.queryByText("Pilar P1")).not.toBeInTheDocument();
    expect(screen.getByText("Viga V301")).toBeInTheDocument();
    expect(spy).toHaveBeenCalledTimes(1); // ainda 1 — filtro é 100% local
  });

  it("404 genérico para código de item enviado a /obra/{code}", async () => {
    jest.spyOn(obraApi, "buscarIndiceObra").mockResolvedValue({ status: "not_found" });

    render(<IndiceObraPage params={{ code: "ITEMCODE1" }} />);
    expect(await screen.findByText("Código não encontrado")).toBeInTheDocument();
  });

  it("mostra link 'abrir ficha do pavimento' com o código próprio de cada pavimento [2026-07-12]", async () => {
    jest.spyOn(obraApi, "buscarIndiceObra").mockResolvedValue({ status: "ok", data: obraBase() });

    render(<IndiceObraPage params={{ code: "OBRACODE1" }} />);
    await screen.findByText("TÉRREO");

    const link = screen.getByRole("link", { name: /Abrir ficha do pavimento Térreo/i });
    expect(link).toHaveAttribute("href", "/pavimento/PAVCODE_TERREO");
    expect(link).toHaveTextContent("Pavimento: PAVCODE_TERREO");
  });
});
