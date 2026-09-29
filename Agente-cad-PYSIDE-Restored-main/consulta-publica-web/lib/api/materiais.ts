import { API_BASE_URL } from "@/lib/config";

/** cm, origem no canto inferior esquerdo do painel, y para cima. */
export interface SarrafoMontagem {
  bitola: string;
  comprimento_cm: number;
  espessura_cm: number;
  /** "tras" = pregado na face oposta (sarrafo de pressão, linha HIDDEN). */
  face?: "frente" | "tras";
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface PainelMedido {
  /** Pilar: face do ABCD (pilha de painéis do gerador). */
  face?: string;
  largura_cm: number;
  altura_cm: number;
  quantidade: number;
  /** Numeração do painel no item (casa com o rótulo no plano de corte). */
  numeros?: number[];
  numero?: number;
  /** ID rastreável do painel: {OBRA}-{PAV}-{CLASSE}-{ITEM}-P{nn}. */
  id?: string;
  /** Laje: "Painel comum" | "Tira de escoramento". */
  classe?: string;
  /** Tira de escoramento não volta ao estoque; painel comum sim. */
  reaproveitavel?: boolean;
  /** Recortado: peças reais (contorno + furos, cm, origem no canto inferior
   * esquerdo do retângulo cortado, y p/ cima). Pilar com viga cruzando a
   * face = 2 partes. */
  partes?: ParteRecortada[];
  /** Sarrafos na posição sobre o painel, na ordem de montagem (aba 3D). */
  montagem?: SarrafoMontagem[];
  /** Sarrafos que correm sobre este painel (associados pela geometria). */
  sarrafos?: CorteSarrafo[];
  /** Célula não retangular (recorte de viga, laje poligonal). */
  recortado: boolean;
}

export interface ParteRecortada {
  contorno: [number, number][];
  furos?: [number, number][][];
}

/** Sobra de chapa: retângulo, ou polígono (recorte de painel, sozinho ou
 * somado à sobra vizinha) com o maior retângulo útil dentro dele. */
export interface SobraChapa {
  rotulo: string;
  id?: string;
  x: number;
  y: number;
  largura_cm: number;
  altura_cm: number;
  contorno?: [number, number][];
  area_cm2?: number;
  util?: { x: number; y: number; largura_cm: number; altura_cm: number };
  /** IDs dos painéis de cujo recorte a sobra veio. */
  recorte_de?: string[];
}

export interface CorteSarrafo {
  /** Grades: "vertical" | "horizontal". */
  sentido?: string;
  bitola: string;
  comprimento_cm: number;
  quantidade: number;
}

/** Grade do pilar (rótulo no desenho, ex. P1.A) e as peças dela. */
export interface GradeMedida {
  rotulo: string;
  face: string;
  pecas: CorteSarrafo[];
}

export interface SarrafoMedido {
  bitola: string;
  pecas: number;
  total_m: number;
  cortes: { comprimento_cm: number; quantidade: number }[];
}

export interface GrupoMateriais {
  titulo: string;
  disponivel: boolean;
  paineis?: PainelMedido[];
  paineis_total?: number;
  paineis_recortados?: number;
  paineis_area_m2?: number;
  /** Pilar: "desenhada" ou aviso de que a largura veio da ficha. */
  largura_da_face?: string;
  sarrafos?: SarrafoMedido[];
  sarrafos_duplicados_ignorados?: number;
  /** Sarrafos que não correm sobre nenhum painel. */
  sarrafos_avulsos?: CorteSarrafo[];
  grades?: GradeMedida[];
}

export interface PecaNaChapa {
  rotulo: string;
  origem: string;
  /** ID do painel (faixa de emenda herda o ID + letra). */
  id?: string;
  x: number;
  y: number;
  largura_cm: number;
  altura_cm: number;
  girado: boolean;
  /** Cortada numa sobra (recorte) de outra chapa, sem abrir chapa nova. */
  em_sobra?: boolean;
}

export interface ChapaLayout {
  chapa: number;
  aproveitamento: number;
  pecas: PecaNaChapa[];
  sobras: SobraChapa[];
}

export interface CompraChapas {
  material: string;
  chapas: number;
  aproveitamento: number;
  emendas: number;
  layout?: ChapaLayout[];
}

/** Sobra do plano de corte com ID rastreável ({OBRA}-{PAV}-{CLS}-{ITEM}-CH02-S1
 * ou …-S7-B03) — estoque para reaproveitamento no próximo pavimento. */
export interface SobraRastreavel {
  id: string;
  tipo: "chapa" | "barra";
  material: string;
  origem: string;
  largura_cm?: number;
  altura_cm?: number;
  comprimento_cm?: number;
  contorno?: [number, number][];
  area_cm2?: number;
  util?: { largura_cm: number; altura_cm: number };
  recorte_de?: string[];
}

export interface CompraBarras {
  material: string;
  pecas: number;
  total_m: number;
  barras: number;
  aproveitamento: number;
  emendas: number;
}

export interface MateriaisData {
  tipo: string;
  fonte?: string;
  prefixo_id?: string;
  grupos: GrupoMateriais[];
  /** Material de compra: plano de corte das peças (chapa 244x122, barra 3 m). */
  compra?: { chapas: CompraChapas | null; barras: CompraBarras[]; sobras?: SobraRastreavel[] };
}

export type MateriaisResult =
  | { status: "ok"; data: MateriaisData }
  | { status: "not_found" }
  | { status: "network_error" };

/** A medição abre e mede o(s) DXF(s) N3 no servidor: mais lenta que um JSON. */
const MATERIAIS_TIMEOUT_MS = 30000;

export async function buscarMateriais(code: string): Promise<MateriaisResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), MATERIAIS_TIMEOUT_MS);
  try {
    const resp = await fetch(`${API_BASE_URL}/api/v1/ficha/${encodeURIComponent(code)}/materiais`, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!resp.ok) return { status: "not_found" };
    return { status: "ok", data: (await resp.json()) as MateriaisData };
  } catch {
    return { status: "network_error" };
  } finally {
    clearTimeout(timeout);
  }
}
