import { act, render, screen, waitFor } from "@testing-library/react";
import FichaPage from "@/app/ficha/[code]/page";
import * as fichaApi from "@/lib/api/ficha";
import * as historico from "@/lib/storage/history";

const pushMock = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

// Mock parcial — preserva `urlAbsolutaSvg` (função pura real) e só troca
// `buscarFicha` por um mock; um `jest.mock()` sem factory substituiria TODO
// export do módulo por `jest.fn()`, quebrando `urlAbsolutaSvg` (retornaria
// `undefined`, e o <img> nunca receberia `src`).
jest.mock("@/lib/api/ficha", () => ({
  ...jest.requireActual("@/lib/api/ficha"),
  buscarFicha: jest.fn(),
}));
jest.mock("@/lib/storage/history");

function fichaBase(overrides: Partial<fichaApi.FichaData> = {}): fichaApi.FichaData {
  return {
    code: "ITEMCODE01",
    tipo: "pilar",
    titulo: "Pilar P1",
    obra_rotulo: "Obra Teste",
    pavimento_label: "Térreo",
    campos: { Classificação: "Pilar de canto", "Dimensões": "30 x 60 cm" },
    atencao: "",
    svg: { n1: "/api/v1/ficha/ITEMCODE01/svg/n1", n3: "/api/v1/ficha/ITEMCODE01/svg/n3" },
    tem_lv: false,
    ...overrides,
  };
}

beforeEach(() => {
  window.localStorage.clear();
  pushMock.mockClear();
  jest.clearAllMocks();
});

describe("Ficha do Item — renderização por combinação de abas", () => {
  it("renderiza com N1 + N3 + LV — todas as 3 abas aparecem", async () => {
    jest.spyOn(fichaApi, "buscarFicha").mockResolvedValue({
      status: "ok",
      data: fichaBase({ tem_lv: true }),
    });

    render(<FichaPage params={{ code: "ITEMCODE01" }} />);

    expect(await screen.findByText("Pilar P1")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "N1" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "N3" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "PAINÉIS" })).toBeInTheDocument();
  });

  it("renderiza só com N1 — segmented control colapsa (AC2)", async () => {
    jest.spyOn(fichaApi, "buscarFicha").mockResolvedValue({
      status: "ok",
      data: fichaBase({ svg: { n1: "/api/v1/ficha/ITEMCODE01/svg/n1", n3: null }, tem_lv: false }),
    });

    render(<FichaPage params={{ code: "ITEMCODE01" }} />);

    await screen.findByText("Pilar P1");
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.getByText("N1")).toBeInTheDocument();
  });

  it("edge case: sem nenhum SVG (svg.n1 e svg.n3 ambos null, tem_lv false)", async () => {
    jest.spyOn(fichaApi, "buscarFicha").mockResolvedValue({
      status: "ok",
      data: fichaBase({ svg: { n1: null, n3: null }, tem_lv: false }),
    });

    render(<FichaPage params={{ code: "ITEMCODE01" }} />);

    // Campos continuam visíveis mesmo sem nenhum desenho.
    expect(await screen.findByText("Classificação")).toBeInTheDocument();
    expect(screen.getByText("Pilar de canto")).toBeInTheDocument();
  });

  it("salva no histórico ao carregar com sucesso (AC6/STORY-08)", async () => {
    jest.spyOn(fichaApi, "buscarFicha").mockResolvedValue({ status: "ok", data: fichaBase() });

    render(<FichaPage params={{ code: "ITEMCODE01" }} />);
    await screen.findByText("Pilar P1");

    expect(historico.adicionarAoHistorico).toHaveBeenCalledWith(
      expect.objectContaining({ code: "ITEMCODE01", titulo: "Pilar P1", tipo: "pilar" }),
    );
  });
});

describe("Ficha do Item — banner de atenção condicional", () => {
  it("mostra o banner só quando atencao != ''", async () => {
    jest.spyOn(fichaApi, "buscarFicha").mockResolvedValue({
      status: "ok",
      data: fichaBase({ atencao: "conferir cota do topo" }),
    });

    render(<FichaPage params={{ code: "ITEMCODE01" }} />);
    expect(await screen.findByText(/conferir cota do topo/i)).toBeInTheDocument();
  });

  it("não mostra banner quando atencao é vazio", async () => {
    jest.spyOn(fichaApi, "buscarFicha").mockResolvedValue({ status: "ok", data: fichaBase({ atencao: "" }) });

    render(<FichaPage params={{ code: "ITEMCODE01" }} />);
    await screen.findByText("Pilar P1");
    expect(screen.queryByRole("alert", { name: /atenção/i })).not.toBeInTheDocument();
  });
});

describe("Ficha do Item — falha de SVG não quebra o resto (AC4)", () => {
  it("erro no <img> do SVG mostra EmptyState mas mantém campos visíveis", async () => {
    jest.spyOn(fichaApi, "buscarFicha").mockResolvedValue({ status: "ok", data: fichaBase() });

    render(<FichaPage params={{ code: "ITEMCODE01" }} />);
    await screen.findByText("Pilar P1");

    const img = document.querySelector("img") as HTMLImageElement;
    expect(img).toBeTruthy();
    act(() => {
      img.dispatchEvent(new Event("error"));
    });

    await waitFor(() => {
      expect(screen.getByText(/Não foi possível carregar o desenho/i)).toBeInTheDocument();
    });
    // Especificação continua visível — a falha não derruba a ficha inteira.
    expect(screen.getByText("Classificação")).toBeInTheDocument();
  });
});

describe("Ficha do Item — banner offline (STORY-14, AC6)", () => {
  it("mostra 'Offline — última versão salva' quando navigator.onLine=false", async () => {
    Object.defineProperty(navigator, "onLine", { value: false, configurable: true });
    jest.spyOn(fichaApi, "buscarFicha").mockResolvedValue({ status: "ok", data: fichaBase() });

    render(<FichaPage params={{ code: "ITEMCODE01" }} />);
    expect(await screen.findByText(/Offline — última versão salva/)).toBeInTheDocument();

    Object.defineProperty(navigator, "onLine", { value: true, configurable: true });
  });

  it("não mostra o banner quando online", async () => {
    Object.defineProperty(navigator, "onLine", { value: true, configurable: true });
    jest.spyOn(fichaApi, "buscarFicha").mockResolvedValue({ status: "ok", data: fichaBase() });

    render(<FichaPage params={{ code: "ITEMCODE01" }} />);
    await screen.findByText("Pilar P1");
    expect(screen.queryByText(/Offline — última versão salva/)).not.toBeInTheDocument();
  });

  it("não tenta cachear via SW quando offline (dado já veio do cache)", async () => {
    Object.defineProperty(navigator, "onLine", { value: false, configurable: true });
    const postMessage = jest.fn();
    Object.defineProperty(navigator, "serviceWorker", {
      value: { controller: { postMessage } },
      configurable: true,
    });
    jest.spyOn(fichaApi, "buscarFicha").mockResolvedValue({ status: "ok", data: fichaBase() });

    render(<FichaPage params={{ code: "ITEMCODE01" }} />);
    await screen.findByText("Pilar P1");

    expect(postMessage).not.toHaveBeenCalled();
    Object.defineProperty(navigator, "onLine", { value: true, configurable: true });
  });
});

describe("Ficha do Item — 404 genérico", () => {
  it("mostra 'Código não encontrado' quando status=not_found", async () => {
    jest.spyOn(fichaApi, "buscarFicha").mockResolvedValue({ status: "not_found" });

    render(<FichaPage params={{ code: "NAOEXISTE1" }} />);
    expect(await screen.findByText("Código não encontrado")).toBeInTheDocument();
  });
});
