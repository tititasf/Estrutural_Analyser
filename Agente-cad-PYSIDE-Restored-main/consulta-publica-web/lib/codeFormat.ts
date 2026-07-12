// Normalização e heurística de "formato plausível" de código (STORY-08,
// AC3/AC4). Nunca altera o case — base62 é case-sensitive (STORY-01).

const BASE62_RE = /^[0-9A-Za-z]+$/;
const CODE_LEN = 10;

/** Remove espaços/quebras de linha, aspas e wrapper de URL acidentais —
 * sem alterar o case dos caracteres restantes. */
export function normalizarCodigo(bruto: string): string {
  let s = bruto.trim();
  // Wrapper de URL acidental (ex.: colou "https://.../ficha/aF3kZ9xQ2m").
  const match = s.match(/\/([0-9A-Za-z]{6,20})\/?(?:[?#].*)?$/);
  if (s.includes("://") && match) {
    s = match[1];
  }
  // Remove aspas acidentais e espaços internos (nunca mudar maiúsc/minúsc).
  s = s.replace(/["'`]/g, "").replace(/\s+/g, "");
  return s;
}

/** Heurística de "formato plausível de código" — usada só para decidir se
 * o botão Colar oferece "Consultar agora?"; nunca é validação de verdade
 * (isso é o backend, /resolve). */
export function pareceCodigoValido(codigo: string): boolean {
  return codigo.length >= CODE_LEN - 2 && codigo.length <= CODE_LEN + 4 && BASE62_RE.test(codigo);
}
