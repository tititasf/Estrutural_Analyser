import { cachearUltimoItem } from "@/lib/pwa/cacheUltimoItem";
import * as historico from "@/lib/storage/history";
import type { FichaData } from "@/lib/api/ficha";

jest.mock("@/lib/storage/history");

function ficha(overrides: Partial<FichaData> = {}): FichaData {
  return {
    code: "ITEMCODE01", tipo: "pilar", titulo: "Pilar P1", obra_rotulo: "Obra Teste",
    pavimento_label: "Térreo", campos: {}, atencao: "",
    svg: { n1: "/api/v1/ficha/ITEMCODE01/svg/n1", n3: "/api/v1/ficha/ITEMCODE01/svg/n3" },
    tem_lv: false,
    ...overrides,
  };
}

describe("cachearUltimoItem", () => {
  let postMessage: jest.Mock;

  beforeEach(() => {
    postMessage = jest.fn();
    jest.clearAllMocks();
    Object.defineProperty(navigator, "serviceWorker", {
      value: { controller: { postMessage } },
      configurable: true,
    });
  });

  it("não faz nada se não há service worker controlando a página (ex.: dev sem SW ativo)", () => {
    Object.defineProperty(navigator, "serviceWorker", { value: { controller: null }, configurable: true });
    cachearUltimoItem(ficha());
    expect(postMessage).not.toHaveBeenCalled();
  });

  it("envia CACHE_ULTIMO_ITEM com JSON da ficha + svg n1 + svg n3", () => {
    cachearUltimoItem(ficha());
    expect(postMessage).toHaveBeenCalledWith({
      type: "CACHE_ULTIMO_ITEM",
      urls: [
        "http://127.0.0.1:21390/api/v1/ficha/ITEMCODE01",
        "http://127.0.0.1:21390/api/v1/ficha/ITEMCODE01/svg/n1",
        "http://127.0.0.1:21390/api/v1/ficha/ITEMCODE01/svg/n3",
      ],
    });
  });

  it("inclui /paineis-lv quando tem_lv=true", () => {
    cachearUltimoItem(ficha({ tem_lv: true }));
    const chamada = postMessage.mock.calls[0][0];
    expect(chamada.urls).toContain("http://127.0.0.1:21390/api/v1/ficha/ITEMCODE01/paineis-lv");
  });

  it("omite svg.n3 quando ausente (item só tem N1)", () => {
    cachearUltimoItem(ficha({ svg: { n1: "/api/v1/ficha/ITEMCODE01/svg/n1", n3: null } }));
    const chamada = postMessage.mock.calls[0][0];
    expect(chamada.urls).not.toContain(expect.stringContaining("svg/n3"));
    expect(chamada.urls).toHaveLength(2);
  });

  it("marca o histórico local como cacheado (e só este item)", () => {
    cachearUltimoItem(ficha());
    expect(historico.marcarApenasEsteCacheadoOffline).toHaveBeenCalledWith("ITEMCODE01");
  });
});
