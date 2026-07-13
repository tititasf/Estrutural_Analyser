import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PavimentoPage from "@/app/pavimento/[code]/page";
import * as pavimentoApi from "@/lib/api/pavimento";

const pushMock = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

jest.mock("@/lib/api/pavimento");

function pavimentoBase(overrides: Partial<pavimentoApi.PavimentoData> = {}): pavimentoApi.PavimentoData {
  return {
    obra_rotulo: "Obra ·· A3F",
    obra_code: null,
    pavimento_label: "Térreo",
    itens: [
      { code: "ITEM_P1", titulo: "Pilar P1", tipo: "pilar" },
      { code: "ITEM_V301", titulo: "Viga V301", tipo: "viga_lateral" },
    ],
    ...overrides,
  };
}

beforeEach(() => {
  pushMock.mockClear();
  jest.clearAllMocks();
});

describe("Ficha do Pavimento", () => {
  it("renderiza o rótulo do pavimento, obra e itens", async () => {
    jest.spyOn(pavimentoApi, "buscarPavimento").mockResolvedValue({ status: "ok", data: pavimentoBase() });

    render(<PavimentoPage params={{ code: "PAVCODE1" }} />);

    expect(await screen.findByText("Térreo")).toBeInTheDocument();
    expect(screen.getByText("Obra ·· A3F")).toBeInTheDocument();
    expect(screen.getByText("Pilar P1")).toBeInTheDocument();
    expect(screen.getByText("Viga V301")).toBeInTheDocument();
  });

  it("pavimento sem itens mostra estado vazio, não erro", async () => {
    jest.spyOn(pavimentoApi, "buscarPavimento").mockResolvedValue({
      status: "ok", data: pavimentoBase({ itens: [] }),
    });

    render(<PavimentoPage params={{ code: "PAVCODE1" }} />);
    expect(await screen.findByText("Nenhum item publicado neste pavimento.")).toBeInTheDocument();
  });

  it("clicar em um item navega para /ficha/{code do item}", async () => {
    jest.spyOn(pavimentoApi, "buscarPavimento").mockResolvedValue({ status: "ok", data: pavimentoBase() });

    render(<PavimentoPage params={{ code: "PAVCODE1" }} />);
    await userEvent.click(await screen.findByText("Pilar P1"));

    expect(pushMock).toHaveBeenCalledWith("/ficha/ITEM_P1");
  });

  it("filtro local client-side filtra sem nova requisição", async () => {
    const spy = jest.spyOn(pavimentoApi, "buscarPavimento").mockResolvedValue({
      status: "ok", data: pavimentoBase(),
    });

    render(<PavimentoPage params={{ code: "PAVCODE1" }} />);
    await screen.findByText("Pilar P1");
    expect(spy).toHaveBeenCalledTimes(1);

    await userEvent.type(screen.getByLabelText(/buscar item/i), "Viga");

    expect(screen.queryByText("Pilar P1")).not.toBeInTheDocument();
    expect(screen.getByText("Viga V301")).toBeInTheDocument();
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("404 genérico para código inválido/de outro tipo", async () => {
    jest.spyOn(pavimentoApi, "buscarPavimento").mockResolvedValue({ status: "not_found" });

    render(<PavimentoPage params={{ code: "OBRACODE1" }} />);
    expect(await screen.findByText("Código não encontrado")).toBeInTheDocument();
  });

  it("mostra link pra obra quando obra_code vem preenchido [2026-07-13]", async () => {
    jest.spyOn(pavimentoApi, "buscarPavimento").mockResolvedValue({
      status: "ok", data: pavimentoBase({ obra_code: "OBRACODEP" }),
    });

    render(<PavimentoPage params={{ code: "PAVCODE1" }} />);
    const link = await screen.findByRole("link", { name: /abrir índice da obra/i });
    expect(link).toHaveAttribute("href", "/obra/OBRACODEP");
  });

  it("sem link quando obra_code é null (obra ainda não publicada)", async () => {
    jest.spyOn(pavimentoApi, "buscarPavimento").mockResolvedValue({
      status: "ok", data: pavimentoBase({ obra_code: null }),
    });

    render(<PavimentoPage params={{ code: "PAVCODE1" }} />);
    await screen.findByText("Obra ·· A3F");
    expect(screen.queryByRole("link", { name: /abrir índice da obra/i })).not.toBeInTheDocument();
  });
});
