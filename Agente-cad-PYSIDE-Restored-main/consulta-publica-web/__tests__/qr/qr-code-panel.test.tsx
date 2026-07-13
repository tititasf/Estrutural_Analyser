import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QrCodePanel } from "@/components/ui/QrCodePanel";

jest.mock("qrcode", () => ({
  toDataURL: jest.fn().mockResolvedValue("data:image/png;base64,fake"),
}));

describe("QrCodePanel [2026-07-12]", () => {
  it("gera o QR a partir da URL informada e mostra título/código", async () => {
    render(
      <QrCodePanel
        url="http://localhost:21391/ficha/ABC1234567"
        titulo="Pilar P1"
        code="ABC1234567"
        rotuloTipo="Código de Item — Pilar"
      />,
    );

    const img = await screen.findByAltText(/QR code de acesso — Pilar P1/i);
    expect(img).toHaveAttribute("src", "data:image/png;base64,fake");
    expect(screen.getByText("Pilar P1")).toBeInTheDocument();
    expect(screen.getByText("Código de Item — Pilar")).toBeInTheDocument();
    expect(screen.getByText("ABC1234567")).toBeInTheDocument();
  });

  it("botão Imprimir chama window.print()", async () => {
    const printMock = jest.fn();
    window.print = printMock;

    render(
      <QrCodePanel
        url="http://localhost:21391/ficha/ABC1234567"
        titulo="Pilar P1"
        code="ABC1234567"
        rotuloTipo="Código de Item — Pilar"
      />,
    );
    await screen.findByAltText(/QR code de acesso/i);

    await userEvent.click(screen.getByRole("button", { name: /imprimir qr/i }));
    expect(printMock).toHaveBeenCalledTimes(1);
  });

  it("mostra a referência legível quando informada [2026-07-13]", async () => {
    render(
      <QrCodePanel
        url="http://localhost:21391/ficha/ABC1234567"
        titulo="Pilar P1"
        code="ABC1234567"
        rotuloTipo="Código de Item — Pilar"
        referencia="Obra Teste › Térreo › Pilar P1"
      />,
    );
    expect(await screen.findByText("Obra Teste › Térreo › Pilar P1")).toBeInTheDocument();
  });

  it("sem referência, não renderiza a linha extra", async () => {
    render(
      <QrCodePanel
        url="http://localhost:21391/ficha/ABC1234567"
        titulo="Pilar P1"
        code="ABC1234567"
        rotuloTipo="Código de Item — Pilar"
      />,
    );
    await screen.findByAltText(/QR code de acesso/i);
    expect(screen.queryByText(/›/)).not.toBeInTheDocument();
  });
});
