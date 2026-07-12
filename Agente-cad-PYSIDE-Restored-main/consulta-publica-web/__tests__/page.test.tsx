import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TelaDeBusca from "@/app/page";
import * as resolveApi from "@/lib/api/resolve";
import { ThemeProvider } from "@/lib/theme/ThemeProvider";

const pushMock = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

jest.mock("@/lib/api/resolve");

function renderTela() {
  return render(
    <ThemeProvider>
      <TelaDeBusca />
    </ThemeProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  pushMock.mockClear();
  jest.restoreAllMocks();
  Object.assign(navigator, { clipboard: { readText: jest.fn() } });
  Object.defineProperty(navigator, "onLine", { value: true, configurable: true });
});

describe("Tela de Busca — botão Colar", () => {
  it("preenche o campo mas NÃO auto-consulta ao colar (AC3)", async () => {
    (navigator.clipboard.readText as jest.Mock).mockResolvedValue("aF3kZ9xQ2m");
    const resolverSpy = jest.spyOn(resolveApi, "resolverCodigo");

    renderTela();
    await userEvent.click(screen.getByRole("button", { name: /colar/i }));

    await waitFor(() => {
      expect(screen.getByDisplayValue("aF3kZ9xQ2m")).toBeInTheDocument();
    });
    expect(screen.getByText(/Consultar agora\?/i)).toBeInTheDocument();
    expect(resolverSpy).not.toHaveBeenCalled();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("mostra aviso quando a permissão de clipboard falha", async () => {
    (navigator.clipboard.readText as jest.Mock).mockRejectedValue(new Error("negado"));

    renderTela();
    await userEvent.click(screen.getByRole("button", { name: /colar/i }));

    expect(await screen.findByText(/cole com o teclado/i)).toBeInTheDocument();
  });
});

describe("Tela de Busca — roteamento por kind de resposta", () => {
  it("navega para /ficha/{code} quando kind=item", async () => {
    jest.spyOn(resolveApi, "resolverCodigo").mockResolvedValue({
      status: "ok", kind: "item", code: "aF3kZ9xQ2m",
    });

    renderTela();
    await userEvent.type(screen.getByLabelText(/código do item ou da obra/i), "aF3kZ9xQ2m");
    await userEvent.click(screen.getByRole("button", { name: /consultar/i }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/ficha/aF3kZ9xQ2m"));
  });

  it("navega para /obra/{code} quando kind=obra", async () => {
    jest.spyOn(resolveApi, "resolverCodigo").mockResolvedValue({
      status: "ok", kind: "obra", code: "OBRACODE1",
    });

    renderTela();
    await userEvent.type(screen.getByLabelText(/código do item ou da obra/i), "OBRACODE1");
    await userEvent.click(screen.getByRole("button", { name: /consultar/i }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/obra/OBRACODE1"));
  });

  it("mostra 'Código não encontrado' para status not_found — mesma mensagem sempre", async () => {
    jest.spyOn(resolveApi, "resolverCodigo").mockResolvedValue({ status: "not_found" });

    renderTela();
    await userEvent.type(screen.getByLabelText(/código do item ou da obra/i), "naoexiste1");
    await userEvent.click(screen.getByRole("button", { name: /consultar/i }));

    expect(await screen.findByText(/Código não encontrado/)).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("mostra estado Bloqueado com contagem para status blocked (429)", async () => {
    jest.spyOn(resolveApi, "resolverCodigo").mockResolvedValue({
      status: "blocked", retryAfterSeconds: 30,
    });

    renderTela();
    await userEvent.type(screen.getByLabelText(/código do item ou da obra/i), "bloqueado1");
    await userEvent.click(screen.getByRole("button", { name: /consultar/i }));

    expect(await screen.findByText(/Muitas tentativas/i)).toBeInTheDocument();
    expect(await screen.findByText(/Aguarde 30s/i)).toBeInTheDocument();
  });
});
