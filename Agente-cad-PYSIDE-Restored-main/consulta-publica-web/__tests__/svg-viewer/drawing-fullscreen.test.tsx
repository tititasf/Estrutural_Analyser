import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DrawingFullscreen } from "@/components/ficha/DrawingFullscreen";

function Wrapper(props: Partial<React.ComponentProps<typeof DrawingFullscreen>>) {
  const defaults: React.ComponentProps<typeof DrawingFullscreen> = {
    aberto: true,
    svgUrl: "http://example.com/x.svg",
    descricao: "Desenho N1 de Pilar P1 — leitura por CAD",
    nivelAtivo: "n1",
    temN1: true,
    temN3: true,
    onFechar: jest.fn(),
    onAlternarNivel: jest.fn(),
  };
  return <DrawingFullscreen {...defaults} {...props} />;
}

describe("DrawingFullscreen — shell e controles", () => {
  it("não renderiza nada quando aberto=false", () => {
    const { container } = render(<Wrapper aberto={false} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renderiza a imagem com aria-label descritivo (AC10)", () => {
    render(<Wrapper />);
    expect(screen.getByRole("img", { name: /Desenho N1 de Pilar P1/i })).toBeInTheDocument();
  });

  it("mostra 100% inicialmente (fit)", () => {
    render(<Wrapper />);
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("botão + aumenta o zoom (paridade com pinch, AC5/AC6)", async () => {
    render(<Wrapper />);
    await userEvent.click(screen.getByLabelText("Aumentar zoom"));
    expect(screen.getByText("125%")).toBeInTheDocument();
  });

  it("botão − nunca desce abaixo de 100% (limite mínimo fit, AC6)", async () => {
    render(<Wrapper />);
    await userEvent.click(screen.getByLabelText("Diminuir zoom"));
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("botão + repetido trava no limite máximo de 8× (800%, AC6)", async () => {
    render(<Wrapper />);
    const botaoMais = screen.getByLabelText("Aumentar zoom");
    for (let i = 0; i < 20; i += 1) {
      await userEvent.click(botaoMais);
    }
    expect(screen.getByText("800%")).toBeInTheDocument();
  });

  it("botão Ajustar volta para 100% (fit)", async () => {
    render(<Wrapper />);
    await userEvent.click(screen.getByLabelText("Aumentar zoom"));
    await userEvent.click(screen.getByLabelText("Ajustar à tela"));
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("botão fechar chama onFechar (AC5)", async () => {
    const onFechar = jest.fn();
    render(<Wrapper onFechar={onFechar} />);
    await userEvent.click(screen.getByLabelText("Fechar"));
    expect(onFechar).toHaveBeenCalledTimes(1);
  });

  it("toggle N1/N3 chama onAlternarNivel", async () => {
    const onAlternarNivel = jest.fn();
    render(<Wrapper onAlternarNivel={onAlternarNivel} />);
    await userEvent.click(screen.getByText("N3"));
    expect(onAlternarNivel).toHaveBeenCalledWith("n3");
  });

  it("não mostra toggle de nível quando só há N1 (sem N3)", () => {
    render(<Wrapper temN3={false} />);
    expect(screen.queryByText("N3")).not.toBeInTheDocument();
  });
});

describe("DrawingFullscreen — atalhos de teclado (AC8)", () => {
  it("Esc fecha o visualizador", async () => {
    const onFechar = jest.fn();
    render(<Wrapper onFechar={onFechar} />);
    await userEvent.keyboard("{Escape}");
    expect(onFechar).toHaveBeenCalledTimes(1);
  });

  it("+ e - alteram o zoom, 0 reseta para fit", async () => {
    render(<Wrapper />);
    await userEvent.keyboard("+");
    expect(screen.getByText("125%")).toBeInTheDocument();
    await userEvent.keyboard("0");
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("N alterna entre N1 e N3 quando ambos existem", async () => {
    const onAlternarNivel = jest.fn();
    render(<Wrapper onAlternarNivel={onAlternarNivel} nivelAtivo="n1" />);
    await userEvent.keyboard("n");
    expect(onAlternarNivel).toHaveBeenCalledWith("n3");
  });
});

describe("DrawingFullscreen — focus trap (AC9)", () => {
  it("foca o primeiro elemento focável ao abrir", () => {
    render(<Wrapper />);
    expect(document.activeElement).toHaveAttribute("aria-label", "Fechar");
  });

  it("devolve o foco ao elemento anterior ao fechar", () => {
    const botaoExterno = document.createElement("button");
    botaoExterno.textContent = "Ampliar";
    document.body.appendChild(botaoExterno);
    botaoExterno.focus();
    expect(document.activeElement).toBe(botaoExterno);

    const { rerender } = render(<Wrapper aberto={true} />);
    rerender(<Wrapper aberto={false} />);

    expect(document.activeElement).toBe(botaoExterno);
    botaoExterno.remove();
  });
});
