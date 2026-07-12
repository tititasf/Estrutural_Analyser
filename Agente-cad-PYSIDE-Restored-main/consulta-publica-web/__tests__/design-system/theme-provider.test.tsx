import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, useTheme } from "@/lib/theme/ThemeProvider";

function Consumidor() {
  const { tema, solForte, alternarTema, alternarSolForte } = useTheme();
  return (
    <div>
      <span data-testid="tema">{tema}</span>
      <span data-testid="sol-forte">{String(solForte)}</span>
      <button onClick={alternarTema}>alternar tema</button>
      <button onClick={alternarSolForte}>alternar sol forte</button>
    </div>
  );
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("ThemeProvider", () => {
  it("inicia em light, sem sol forte", () => {
    render(
      <ThemeProvider>
        <Consumidor />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("tema")).toHaveTextContent("light");
    expect(screen.getByTestId("sol-forte")).toHaveTextContent("false");
  });

  it("alterna para dark e persiste em localStorage", async () => {
    render(
      <ThemeProvider>
        <Consumidor />
      </ThemeProvider>,
    );
    await userEvent.click(screen.getByText("alternar tema"));
    expect(screen.getByTestId("tema")).toHaveTextContent("dark");
    expect(window.localStorage.getItem("consulta-publica:tema")).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("ativa Sol forte como override — não é um 3º tema", async () => {
    render(
      <ThemeProvider>
        <Consumidor />
      </ThemeProvider>,
    );
    await userEvent.click(screen.getByText("alternar sol forte"));
    expect(screen.getByTestId("sol-forte")).toHaveTextContent("true");
    expect(document.documentElement.getAttribute("data-contrast")).toBe("sol-forte");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
});
