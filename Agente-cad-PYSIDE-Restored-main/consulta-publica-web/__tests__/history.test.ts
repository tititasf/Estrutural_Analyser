import {
  adicionarAoHistorico,
  listarHistorico,
  marcarApenasEsteCacheadoOffline,
  removerDoHistorico,
} from "@/lib/storage/history";

function entrada(code: string) {
  return { code, titulo: `Item ${code}`, tipo: "pilar", obra_rotulo: "Obra Teste", cached_offline: false };
}

describe("histórico local", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("adiciona e lista entradas, mais recente primeiro", () => {
    adicionarAoHistorico(entrada("A1"));
    adicionarAoHistorico(entrada("A2"));
    const lista = listarHistorico();
    expect(lista.map((e) => e.code)).toEqual(["A2", "A1"]);
  });

  it("respeita o limite de 8 entradas", () => {
    for (let i = 0; i < 10; i += 1) {
      adicionarAoHistorico(entrada(`C${i}`));
    }
    expect(listarHistorico()).toHaveLength(8);
    expect(listarHistorico().map((e) => e.code)).toEqual([
      "C9", "C8", "C7", "C6", "C5", "C4", "C3", "C2",
    ]);
  });

  it("reconsultar um código já existente move para o topo sem duplicar", () => {
    adicionarAoHistorico(entrada("X1"));
    adicionarAoHistorico(entrada("X2"));
    adicionarAoHistorico(entrada("X1"));
    const lista = listarHistorico();
    expect(lista.map((e) => e.code)).toEqual(["X1", "X2"]);
  });

  it("remove uma entrada específica", () => {
    adicionarAoHistorico(entrada("R1"));
    adicionarAoHistorico(entrada("R2"));
    removerDoHistorico("R1");
    expect(listarHistorico().map((e) => e.code)).toEqual(["R2"]);
  });

  it("marcarApenasEsteCacheadoOffline garante só 1 entrada com cached_offline=true (STORY-14, AC5)", () => {
    adicionarAoHistorico(entrada("O1"));
    adicionarAoHistorico(entrada("O2"));
    adicionarAoHistorico(entrada("O3"));

    marcarApenasEsteCacheadoOffline("O1");
    let lista = listarHistorico();
    expect(lista.find((e) => e.code === "O1")?.cached_offline).toBe(true);
    expect(lista.filter((e) => e.cached_offline)).toHaveLength(1);

    // Cachear um item diferente desmarca o anterior — escopo é "só o
    // último item", nunca cache acumulado (AC5).
    marcarApenasEsteCacheadoOffline("O2");
    lista = listarHistorico();
    expect(lista.find((e) => e.code === "O1")?.cached_offline).toBe(false);
    expect(lista.find((e) => e.code === "O2")?.cached_offline).toBe(true);
    expect(lista.filter((e) => e.cached_offline)).toHaveLength(1);
  });
});
