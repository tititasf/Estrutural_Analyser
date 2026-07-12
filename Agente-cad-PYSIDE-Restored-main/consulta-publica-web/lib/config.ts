// URL base da API pública de Consulta (consulta-publica-api, :21390) —
// processo FISICAMENTE separado deste frontend. Nunca hardcoda o domínio de
// produção aqui; sempre via env pública (exposta ao client de propósito,
// não é segredo — é só o endpoint público).
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:21390";

export const RESOLVE_TIMEOUT_MS = 8000;
