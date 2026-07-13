const ROTULOS_CODIGO_ITEM: Record<string, string> = {
  pilar: "Código de Item — Pilar",
  laje: "Código de Item — Laje",
  viga_fundo: "Código de Item — Viga de Fundo",
  viga_lateral: "Código de Item — Viga Lateral",
};

/** Rótulo do tipo de código público de 1 item, pra deixar explícito ao lado
 * de cada código o que ele representa (pedido do dono [2026-07-13]) —
 * mesma taxonomia de 4 valores de `tipo_elemento` mintada em
 * `consulta-publica-api/publisher/publish.py`. */
export function rotuloCodigoItem(tipo: string): string {
  return ROTULOS_CODIGO_ITEM[tipo] ?? "Código de Item";
}
