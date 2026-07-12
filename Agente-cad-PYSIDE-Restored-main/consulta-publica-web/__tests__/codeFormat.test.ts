import { normalizarCodigo, pareceCodigoValido } from "@/lib/codeFormat";

describe("normalizarCodigo", () => {
  it("remove espaços e quebras de linha sem alterar o case", () => {
    expect(normalizarCodigo("  aF3kZ9\nxQ2m  ")).toBe("aF3kZ9xQ2m");
  });

  it("remove aspas acidentais", () => {
    expect(normalizarCodigo('"aF3kZ9xQ2m"')).toBe("aF3kZ9xQ2m");
  });

  it("extrai o código de um wrapper de URL acidental", () => {
    expect(normalizarCodigo("https://consulta.exemplo.com/ficha/aF3kZ9xQ2m")).toBe("aF3kZ9xQ2m");
  });

  it("preserva maiúsculas e minúsculas (base62 é case-sensitive)", () => {
    expect(normalizarCodigo("AbCdEf1234")).toBe("AbCdEf1234");
  });
});

describe("pareceCodigoValido", () => {
  it("aceita string base62 de comprimento plausível", () => {
    expect(pareceCodigoValido("aF3kZ9xQ2m")).toBe(true);
  });

  it("rejeita string com caracteres fora de base62", () => {
    expect(pareceCodigoValido("aF3kZ9-xQ2")).toBe(false);
  });

  it("rejeita string muito curta", () => {
    expect(pareceCodigoValido("abc")).toBe(false);
  });
});
