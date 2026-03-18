"""
QualityVerifier -- Fase 7 do Pipeline CAD-ANALYZER.

Verifica qualidade das fichas geradas comparando com os criterios
documentados nos Processos Internos (PI) das obras.

Score: 0-100 por pavimento
  >= 95: PRODUCAO (verde)   -- pronto para uso direto
  >= 80: REVISAO_MINIMA (amarelo) -- revisar campos de baixa confianca
  < 80:  REVISAO_COMPLETA (vermelho) -- revisao manual obrigatoria

Criterios (baseados nos PIs reais de 6 obras):
  1. Todos os elementos identificados (pilar/viga/laje presentes)
  2. Acuracia das secoes (19/53 mais comum para vigas)
  3. Nomes detectados (TextProximitySearch com conf >= 0.7)
  4. Pe-direito plausivel (2.5m a 6.0m)
  5. Area total coerente com numero de elementos
  6. Garfos estimados (baseado no comprimento total de vigas)
  7. Chapas estimadas (baseado na area total de formas)

Uso:
    verifier = QualityVerifier()
    report = verifier.verificar_pavimento(entities, fichas, pe_direito=2.88, area_m2=450)
    print(report.nivel, report.score)
    # PRODUCAO 97

    obra_reports = verifier.verificar_obra_completa(obra_entities, fichas_por_pav)
    for pav, rpt in obra_reports.items():
        print(f"{pav}: {rpt.nivel} ({rpt.score})")
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes de dominio (extraidas de PIs reais)
# ---------------------------------------------------------------------------

# Pe-direito plausivel (metros)
PE_DIREITO_MIN: float = 2.5
PE_DIREITO_MAX: float = 6.0
PE_DIREITO_TIPICO: float = 2.88  # valor mais frequente nos PIs

# Secao de viga mais comum nos PIs (largura/altura em cm)
SECAO_VIGA_PADRAO: str = "19/53"

# Confianca minima para considerar nome valido
CONFIANCA_NOME_MIN: float = 0.7

# Chapas compensado resinado (dimensoes em cm)
CHAPA_LARGURA_CM: float = 122.0
CHAPA_ALTURA_CM: float = 244.0
CHAPA_ESPESSURA_MM: float = 18.0

# Garfos: frequencia aproximada
GARFO_A_CADA_CM: float = 50.0  # ~1 garfo a cada 50cm de viga

# Niveis de qualidade
NIVEL_PRODUCAO: str = "PRODUCAO"
NIVEL_REVISAO_MINIMA: str = "REVISAO_MINIMA"
NIVEL_REVISAO_COMPLETA: str = "REVISAO_COMPLETA"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class QualityIssue:
    """Problema detectado na verificacao de qualidade."""
    criterio: str           # Identificador do criterio (C1, C2, ...)
    descricao: str          # Descricao legivel do problema
    severidade: str         # 'critico', 'alerta', 'info'
    campo: str = ""         # Campo afetado (opcional)
    valor_atual: Any = None # Valor encontrado
    valor_esperado: Any = None  # Valor esperado


@dataclass
class QualityReport:
    """Relatorio de qualidade de um pavimento."""
    score: float = 0.0                  # 0 a 100
    nivel: str = NIVEL_REVISAO_COMPLETA  # PRODUCAO, REVISAO_MINIMA, REVISAO_COMPLETA
    issues: List[QualityIssue] = field(default_factory=list)
    metricas: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def aprovado(self) -> bool:
        """True se nivel e PRODUCAO."""
        return self.nivel == NIVEL_PRODUCAO

    def resumo(self) -> str:
        """Resumo do relatorio em uma linha."""
        n_criticos = sum(1 for i in self.issues if i.severidade == 'critico')
        n_alertas = sum(1 for i in self.issues if i.severidade == 'alerta')
        return (
            f"Score: {self.score:.1f}/100 [{self.nivel}] "
            f"({n_criticos} criticos, {n_alertas} alertas)"
        )


@dataclass
class QualityConfig:
    """Configuracao do QualityVerifier."""
    # Pesos dos criterios (somam 100)
    peso_elementos_presentes: float = 20.0    # C1
    peso_acuracia_secoes: float = 15.0        # C2
    peso_nomes_detectados: float = 15.0       # C3
    peso_pe_direito: float = 15.0             # C4
    peso_area_coerencia: float = 15.0         # C5
    peso_garfos: float = 10.0                 # C6
    peso_chapas: float = 10.0                 # C7

    # Thresholds
    min_pilares_por_pavimento: int = 2
    min_vigas_por_pavimento: int = 3
    min_lajes_por_pavimento: int = 1
    area_min_por_elemento_m2: float = 5.0     # area minima esperada por elemento
    area_max_por_elemento_m2: float = 200.0   # area maxima esperada por elemento


# ---------------------------------------------------------------------------
# QualityVerifier principal
# ---------------------------------------------------------------------------

class QualityVerifier:
    """
    Verificador de Qualidade -- Fase 7 do Pipeline.

    Compara a saida do sistema (fichas geradas) com criterios
    derivados dos Processos Internos (PI) das obras reais.
    """

    def __init__(self, config: Optional[QualityConfig] = None) -> None:
        self.config = config or QualityConfig()

    # ------------------------------------------------------------------
    # API principal
    # ------------------------------------------------------------------

    def verificar_pavimento(
        self,
        entities: List[Dict[str, Any]],
        fichas: List[Dict[str, Any]],
        pe_direito: float = 0.0,
        area_m2: float = 0.0,
    ) -> QualityReport:
        """
        Verifica qualidade de um pavimento.

        Args:
            entities: Lista de entidades detectadas (StructuralEntity dicts)
            fichas: Lista de fichas geradas pelo pipeline
            pe_direito: Pe-direito informado/estimado (metros)
            area_m2: Area total do pavimento (m^2)

        Returns:
            QualityReport com score, nivel e issues.
        """
        issues: List[QualityIssue] = []
        criterios_scores: Dict[str, float] = {}

        # Contagem por tipo
        contagem = self._contar_por_tipo(entities)
        n_pilares = contagem.get('pilar', 0) + contagem.get('Pilar', 0)
        n_vigas = contagem.get('viga', 0) + contagem.get('Viga', 0)
        n_lajes = contagem.get('laje', 0) + contagem.get('Laje', 0)
        total_elementos = n_pilares + n_vigas + n_lajes

        # C1: Elementos presentes
        c1_score, c1_issues = self._c1_elementos_presentes(
            n_pilares, n_vigas, n_lajes
        )
        criterios_scores['C1_elementos'] = c1_score
        issues.extend(c1_issues)

        # C2: Acuracia das secoes
        c2_score, c2_issues = self._c2_acuracia_secoes(fichas)
        criterios_scores['C2_secoes'] = c2_score
        issues.extend(c2_issues)

        # C3: Nomes detectados
        c3_score, c3_issues = self._c3_nomes_detectados(fichas)
        criterios_scores['C3_nomes'] = c3_score
        issues.extend(c3_issues)

        # C4: Pe-direito
        c4_score, c4_issues = self._c4_pe_direito(pe_direito)
        criterios_scores['C4_pe_direito'] = c4_score
        issues.extend(c4_issues)

        # C5: Area coerente
        c5_score, c5_issues = self._c5_area_coerencia(area_m2, total_elementos)
        criterios_scores['C5_area'] = c5_score
        issues.extend(c5_issues)

        # C6: Garfos estimados
        comprimento_vigas_total = self._estimar_comprimento_vigas(entities)
        garfos = self.estimar_garfos(comprimento_vigas_total)
        c6_score, c6_issues = self._c6_garfos(garfos, n_vigas)
        criterios_scores['C6_garfos'] = c6_score
        issues.extend(c6_issues)

        # C7: Chapas estimadas
        chapas = self.estimar_chapas(area_m2)
        c7_score, c7_issues = self._c7_chapas(chapas, area_m2)
        criterios_scores['C7_chapas'] = c7_score
        issues.extend(c7_issues)

        # Score ponderado (cada criterio retorna 0-1, peso em porcentagem)
        # Ex: score perfeito = 1.0*20 + 1.0*15 + ... = 100
        cfg = self.config
        score = (
            c1_score * cfg.peso_elementos_presentes +
            c2_score * cfg.peso_acuracia_secoes +
            c3_score * cfg.peso_nomes_detectados +
            c4_score * cfg.peso_pe_direito +
            c5_score * cfg.peso_area_coerencia +
            c6_score * cfg.peso_garfos +
            c7_score * cfg.peso_chapas
        )

        score = max(0.0, min(100.0, score))

        # Determinar nivel
        if score >= 95:
            nivel = NIVEL_PRODUCAO
        elif score >= 80:
            nivel = NIVEL_REVISAO_MINIMA
        else:
            nivel = NIVEL_REVISAO_COMPLETA

        metricas = {
            'n_pilares': n_pilares,
            'n_vigas': n_vigas,
            'n_lajes': n_lajes,
            'total_elementos': total_elementos,
            'pe_direito': pe_direito,
            'area_m2': area_m2,
            'garfos_estimados': garfos,
            'chapas_estimadas': chapas,
            'comprimento_vigas_cm': comprimento_vigas_total,
            'criterios': criterios_scores,
        }

        report = QualityReport(
            score=round(score, 1),
            nivel=nivel,
            issues=issues,
            metricas=metricas,
        )

        logger.info(f"Quality check: {report.resumo()}")
        return report

    def verificar_obra_completa(
        self,
        obra_entities: Dict[str, List[Dict[str, Any]]],
        fichas_por_pav: Dict[str, List[Dict[str, Any]]],
        pe_direito_por_pav: Optional[Dict[str, float]] = None,
        area_por_pav: Optional[Dict[str, float]] = None,
    ) -> Dict[str, QualityReport]:
        """
        Verifica qualidade de todos os pavimentos de uma obra.

        Args:
            obra_entities: Dict pavimento -> lista de entidades
            fichas_por_pav: Dict pavimento -> lista de fichas
            pe_direito_por_pav: Dict pavimento -> pe_direito (opcional)
            area_por_pav: Dict pavimento -> area_m2 (opcional)

        Returns:
            Dict pavimento -> QualityReport
        """
        pe_dir = pe_direito_por_pav or {}
        areas = area_por_pav or {}
        reports: Dict[str, QualityReport] = {}

        for pav_name, entities in obra_entities.items():
            fichas = fichas_por_pav.get(pav_name, [])
            pd = pe_dir.get(pav_name, 0.0)
            area = areas.get(pav_name, 0.0)

            report = self.verificar_pavimento(entities, fichas, pd, area)
            reports[pav_name] = report

        # Log resumo da obra
        scores = [r.score for r in reports.values()]
        avg = sum(scores) / len(scores) if scores else 0.0
        n_prod = sum(1 for r in reports.values() if r.nivel == NIVEL_PRODUCAO)
        logger.info(
            f"Obra quality: {len(reports)} pavimentos, "
            f"media={avg:.1f}, producao={n_prod}/{len(reports)}"
        )

        return reports

    # ------------------------------------------------------------------
    # Estimativas de producao
    # ------------------------------------------------------------------

    @staticmethod
    def estimar_chapas(
        area_m2: float,
        tipo_chapa_cm: Tuple[float, float] = (CHAPA_LARGURA_CM, CHAPA_ALTURA_CM),
    ) -> int:
        """
        Estima quantidade de chapas de compensado 18mm necessarias.

        A estimativa considera que a area total de formas
        e aproximadamente proporcional a area do pavimento,
        com fator de multiplicacao para laterais dos elementos.

        Args:
            area_m2: Area total do pavimento em metros quadrados
            tipo_chapa_cm: (largura, altura) da chapa em cm

        Returns:
            Numero estimado de chapas inteiras.
        """
        if area_m2 <= 0:
            return 0

        # Converter area para cm^2
        area_cm2 = area_m2 * 10_000.0

        # Fator de formas: area de compensado ~ 1.2x a area do pavimento
        # (inclui laterais de vigas, pilares, faces de laje)
        fator_formas = 1.2
        area_formas_cm2 = area_cm2 * fator_formas

        # Area de uma chapa
        chapa_area_cm2 = tipo_chapa_cm[0] * tipo_chapa_cm[1]
        if chapa_area_cm2 <= 0:
            return 0

        # Fator de perda (cortes, desperdicio) ~15%
        fator_perda = 0.85

        n_chapas = area_formas_cm2 / (chapa_area_cm2 * fator_perda)
        return max(1, math.ceil(n_chapas))

    @staticmethod
    def estimar_garfos(comprimento_vigas_total: float) -> int:
        """
        Estima quantidade de garfos necessarios.

        Regra pratica: ~1 garfo a cada 50cm de viga.

        Args:
            comprimento_vigas_total: Comprimento total de todas as vigas (cm)

        Returns:
            Numero estimado de garfos.
        """
        if comprimento_vigas_total <= 0:
            return 0

        n_garfos = comprimento_vigas_total / GARFO_A_CADA_CM
        return max(1, math.ceil(n_garfos))

    # ------------------------------------------------------------------
    # Relatorio estilo PI
    # ------------------------------------------------------------------

    def gerar_relatorio_pi(self, obras: List[Dict[str, Any]]) -> str:
        """
        Gera texto em formato de Processo Interno (PI) com areas
        e quantidades estimadas por obra.

        Args:
            obras: Lista de dicts com campos:
                - nome: str
                - pavimentos: List[Dict] com 'nome', 'area_m2', 'pe_direito'
                - entities_por_pav: Dict[str, List]
                - fichas_por_pav: Dict[str, List]

        Returns:
            Texto formatado estilo PI.
        """
        linhas: List[str] = []
        linhas.append("=" * 70)
        linhas.append("PROCESSO INTERNO -- VERIFICACAO DE QUALIDADE CAD-ANALYZER")
        linhas.append(f"Data: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')}")
        linhas.append("=" * 70)
        linhas.append("")

        for obra in obras:
            nome = obra.get('nome', 'Obra Sem Nome')
            pavimentos = obra.get('pavimentos', [])
            entities_por_pav = obra.get('entities_por_pav', {})
            fichas_por_pav = obra.get('fichas_por_pav', {})

            linhas.append(f"OBRA: {nome}")
            linhas.append("-" * 50)

            area_total = 0.0
            chapas_total = 0
            garfos_total = 0

            for pav in pavimentos:
                pav_nome = pav.get('nome', '')
                area = pav.get('area_m2', 0.0)
                pd = pav.get('pe_direito', 0.0)

                entities = entities_por_pav.get(pav_nome, [])
                fichas = fichas_por_pav.get(pav_nome, [])

                report = self.verificar_pavimento(entities, fichas, pd, area)
                chapas = self.estimar_chapas(area)
                comprimento = self._estimar_comprimento_vigas(entities)
                garfos = self.estimar_garfos(comprimento)

                area_total += area
                chapas_total += chapas
                garfos_total += garfos

                status_icon = {
                    NIVEL_PRODUCAO: "[OK]",
                    NIVEL_REVISAO_MINIMA: "[REV]",
                    NIVEL_REVISAO_COMPLETA: "[!!!]",
                }.get(report.nivel, "[?]")

                linhas.append(
                    f"  {pav_nome:20s} | Area: {area:8.1f} m2 | "
                    f"PD: {pd:.2f}m | Chapas: {chapas:4d} | "
                    f"Garfos: {garfos:4d} | Score: {report.score:5.1f} {status_icon}"
                )

            linhas.append(f"  {'TOTAL':20s} | Area: {area_total:8.1f} m2 | "
                          f"Chapas: {chapas_total:4d} | Garfos: {garfos_total:4d}")
            linhas.append("")

        linhas.append("=" * 70)
        linhas.append("Legenda: [OK] = Producao | [REV] = Revisao Minima | [!!!] = Revisao Completa")
        linhas.append("=" * 70)

        return "\n".join(linhas)

    # ------------------------------------------------------------------
    # Criterios individuais (C1 a C7)
    # ------------------------------------------------------------------

    def _c1_elementos_presentes(
        self, n_pilares: int, n_vigas: int, n_lajes: int
    ) -> Tuple[float, List[QualityIssue]]:
        """C1: Verifica se os 3 tipos basicos estao presentes."""
        issues: List[QualityIssue] = []
        cfg = self.config
        score = 1.0

        if n_pilares < cfg.min_pilares_por_pavimento:
            score -= 0.4
            issues.append(QualityIssue(
                criterio='C1', descricao='Pilares insuficientes',
                severidade='critico', campo='n_pilares',
                valor_atual=n_pilares,
                valor_esperado=f">= {cfg.min_pilares_por_pavimento}",
            ))

        if n_vigas < cfg.min_vigas_por_pavimento:
            score -= 0.4
            issues.append(QualityIssue(
                criterio='C1', descricao='Vigas insuficientes',
                severidade='critico', campo='n_vigas',
                valor_atual=n_vigas,
                valor_esperado=f">= {cfg.min_vigas_por_pavimento}",
            ))

        if n_lajes < cfg.min_lajes_por_pavimento:
            score -= 0.2
            issues.append(QualityIssue(
                criterio='C1', descricao='Lajes insuficientes',
                severidade='alerta', campo='n_lajes',
                valor_atual=n_lajes,
                valor_esperado=f">= {cfg.min_lajes_por_pavimento}",
            ))

        return max(0.0, score), issues

    def _c2_acuracia_secoes(
        self, fichas: List[Dict[str, Any]]
    ) -> Tuple[float, List[QualityIssue]]:
        """C2: Verifica se as secoes das fichas sao plausives."""
        issues: List[QualityIssue] = []
        if not fichas:
            return 0.5, [QualityIssue(
                criterio='C2', descricao='Sem fichas para verificar secoes',
                severidade='alerta',
            )]

        total = 0
        validos = 0
        for ficha in fichas:
            dim = ficha.get('dim', '') or ficha.get('Viga_dim', '') or ficha.get('Pilar_dim', '')
            if not dim:
                continue
            total += 1
            # Verificar se e uma secao plausivel (formato NxN ou N/N)
            dim_str = str(dim)
            if '/' in dim_str or 'x' in dim_str.lower():
                try:
                    parts = dim_str.replace('x', '/').replace('X', '/').split('/')
                    w = float(parts[0].strip('() '))
                    h = float(parts[1].strip('() '))
                    # Secoes plausives: 10-100cm largura, 10-200cm altura
                    if 10 <= w <= 100 and 10 <= h <= 200:
                        validos += 1
                except (ValueError, IndexError):
                    pass

        score = validos / total if total > 0 else 0.5
        if total > 0 and score < 0.8:
            issues.append(QualityIssue(
                criterio='C2',
                descricao=f'Secoes invalidas: {total - validos} de {total}',
                severidade='alerta',
                valor_atual=f"{validos}/{total} validas",
            ))

        return score, issues

    def _c3_nomes_detectados(
        self, fichas: List[Dict[str, Any]]
    ) -> Tuple[float, List[QualityIssue]]:
        """C3: Verifica se os nomes foram detectados com confianca."""
        issues: List[QualityIssue] = []
        if not fichas:
            return 0.5, [QualityIssue(
                criterio='C3', descricao='Sem fichas para verificar nomes',
                severidade='alerta',
            )]

        total = 0
        nomes_ok = 0
        for ficha in fichas:
            name = ficha.get('name', '') or ficha.get('Viga_name', '') or ficha.get('Pilar_name', '')
            conf = float(ficha.get('confidence', 0.0) or ficha.get('name_confidence', 0.0))
            if name:
                total += 1
                if conf >= CONFIANCA_NOME_MIN:
                    nomes_ok += 1
                elif conf > 0:
                    # Tem nome mas baixa confianca
                    issues.append(QualityIssue(
                        criterio='C3',
                        descricao=f'Nome "{name}" com confianca baixa',
                        severidade='info', campo='name',
                        valor_atual=f"conf={conf:.2f}",
                        valor_esperado=f">= {CONFIANCA_NOME_MIN}",
                    ))

        score = nomes_ok / total if total > 0 else 0.5
        return score, issues

    def _c4_pe_direito(
        self, pe_direito: float
    ) -> Tuple[float, List[QualityIssue]]:
        """C4: Verifica se o pe-direito e plausivel."""
        issues: List[QualityIssue] = []

        if pe_direito <= 0:
            return 0.5, [QualityIssue(
                criterio='C4', descricao='Pe-direito nao informado',
                severidade='alerta', campo='pe_direito',
            )]

        if PE_DIREITO_MIN <= pe_direito <= PE_DIREITO_MAX:
            # Dentro da faixa: score proporcional a proximidade do tipico
            dist = abs(pe_direito - PE_DIREITO_TIPICO)
            max_dist = PE_DIREITO_MAX - PE_DIREITO_MIN
            score = 1.0 - (dist / max_dist) * 0.3  # Maximo de 30% penalidade
            return max(0.7, score), issues

        # Fora da faixa
        issues.append(QualityIssue(
            criterio='C4',
            descricao=f'Pe-direito fora da faixa: {pe_direito:.2f}m',
            severidade='critico', campo='pe_direito',
            valor_atual=pe_direito,
            valor_esperado=f"{PE_DIREITO_MIN}-{PE_DIREITO_MAX}m",
        ))
        return 0.0, issues

    def _c5_area_coerencia(
        self, area_m2: float, total_elementos: int
    ) -> Tuple[float, List[QualityIssue]]:
        """C5: Verifica se a area e coerente com o numero de elementos."""
        issues: List[QualityIssue] = []

        if area_m2 <= 0 or total_elementos <= 0:
            return 0.5, [QualityIssue(
                criterio='C5',
                descricao='Area ou elementos insuficientes para analise',
                severidade='info',
            )]

        area_por_elem = area_m2 / total_elementos
        cfg = self.config

        if cfg.area_min_por_elemento_m2 <= area_por_elem <= cfg.area_max_por_elemento_m2:
            return 1.0, issues

        if area_por_elem < cfg.area_min_por_elemento_m2:
            issues.append(QualityIssue(
                criterio='C5',
                descricao='Muitos elementos para a area (possivel duplicidade)',
                severidade='alerta', campo='area_por_elemento',
                valor_atual=f"{area_por_elem:.1f} m2/elem",
                valor_esperado=f">= {cfg.area_min_por_elemento_m2} m2/elem",
            ))
            return 0.5, issues

        issues.append(QualityIssue(
            criterio='C5',
            descricao='Poucos elementos para a area (deteccao incompleta)',
            severidade='alerta', campo='area_por_elemento',
            valor_atual=f"{area_por_elem:.1f} m2/elem",
            valor_esperado=f"<= {cfg.area_max_por_elemento_m2} m2/elem",
        ))
        return 0.5, issues

    def _c6_garfos(
        self, garfos: int, n_vigas: int
    ) -> Tuple[float, List[QualityIssue]]:
        """C6: Verifica se a estimativa de garfos e razoavel."""
        issues: List[QualityIssue] = []

        if n_vigas <= 0:
            return 0.5, issues

        # Deve haver pelo menos 1 garfo por viga
        if garfos < n_vigas:
            issues.append(QualityIssue(
                criterio='C6',
                descricao='Garfos insuficientes (vigas muito curtas?)',
                severidade='info', campo='garfos',
                valor_atual=garfos, valor_esperado=f">= {n_vigas}",
            ))
            return 0.7, issues

        return 1.0, issues

    def _c7_chapas(
        self, chapas: int, area_m2: float
    ) -> Tuple[float, List[QualityIssue]]:
        """C7: Verifica se a estimativa de chapas e razoavel."""
        issues: List[QualityIssue] = []

        if area_m2 <= 0:
            return 0.5, issues

        # Sanidade: pelo menos 1 chapa por 30m2
        min_esperado = max(1, int(area_m2 / 30))
        if chapas < min_esperado:
            issues.append(QualityIssue(
                criterio='C7',
                descricao='Chapas abaixo do minimo esperado',
                severidade='info', campo='chapas',
                valor_atual=chapas, valor_esperado=f">= {min_esperado}",
            ))
            return 0.7, issues

        return 1.0, issues

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _contar_por_tipo(entities: List[Dict[str, Any]]) -> Dict[str, int]:
        """Conta entidades por entity_type."""
        contagem: Dict[str, int] = {}
        for e in entities:
            t = e.get('entity_type', e.get('entity_type_hint', 'Outro'))
            contagem[t] = contagem.get(t, 0) + 1
        return contagem

    @staticmethod
    def _estimar_comprimento_vigas(entities: List[Dict[str, Any]]) -> float:
        """
        Estima comprimento total de vigas em cm.

        Usa a maior dimensao do bbox como proxy do comprimento.
        """
        total_cm = 0.0
        for e in entities:
            t = (e.get('entity_type', '') or e.get('entity_type_hint', '')).lower()
            if t not in ('viga', 'beam', 'viga'):
                continue

            w = abs(float(e.get('bbox_xmax', 0)) - float(e.get('bbox_xmin', 0)))
            h = abs(float(e.get('bbox_ymax', 0)) - float(e.get('bbox_ymin', 0)))
            comprimento = max(w, h)

            # Converter de unidades DXF para cm (DXF tipicamente em mm)
            total_cm += comprimento / 10.0

        return total_cm
