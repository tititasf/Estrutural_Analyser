#!/usr/bin/env python3
"""
rag_anomaly_detector.py — CAD-ANALYZER Sprint 1
=================================================
Detecta anomalias semânticas em elementos estruturais via distância do corpus RAG.
Combina PlausibilityChecker (semântico) + StructuralValidator (dimensional) em
um score unificado de anomalia.

Score de anomalia (0.0 = totalmente normal, 1.0 = totalmente anômalo):
  - 0.0 – 0.30 → NORMAL         (elemento típico das obras de treino)
  - 0.30 – 0.55 → INCOMUM       (aceitar com atenção)
  - 0.55 – 0.75 → SUSPEITO      (revisar antes de gerar DXF)
  - 0.75 – 1.0  → ANÔMALO       (bloquear geração, notificar revisor)

Fórmula:
  anomaly = 0.5 * (1 - semantic_similarity) + 0.5 * dim_penalty

  dim_penalty:
    - 0.0 se todas dimensões OK
    - 0.5 se apenas AVISO
    - 1.0 se pelo menos 1 CRÍTICO

Integração:
  - sprint_e_production_gate.py — gate por obra completa
  - robot_integration.py — por elemento antes de transform()

Uso:
    from rag_anomaly_detector import AnomalyDetector
    detector = AnomalyDetector()
    score = detector.score_element('pilar', 'P17', dados, 'Obra_Nova')
    report = detector.report_obra('Obra_TREINO_1', elementos)
"""
import sys, json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from rag_commons import fmt_element, query
from rag_plausibility import PlausibilityChecker
from rag_validator   import StructuralValidator

# ── Thresholds de anomalia ───────────────────────────────────────────────────
THRESH_NORMAL   = 0.30
THRESH_INCOMUM  = 0.55
THRESH_SUSPEITO = 0.75
# acima de THRESH_SUSPEITO → ANÔMALO


@dataclass
class AnomalyScore:
    """Score completo de anomalia para um elemento."""
    elemento_id:     str
    tipo:            str
    obra:            str
    anomaly_score:   float   # 0.0 – 1.0
    semantic_sim:    float   # similaridade top-1 no corpus
    dim_penalty:     float   # 0.0 / 0.5 / 1.0
    categoria:       str     # NORMAL | INCOMUM | SUSPEITO | ANÔMALO
    plausibility_acao: str   # ACEITAR | ACEITAR_COM_AVISO | REVISAR | REJEITAR
    dim_status:      str     # OK | AVISO | BLOQUEADO
    alertas_dim:     list = field(default_factory=list)
    similares:       list = field(default_factory=list)   # top similares

    @property
    def deve_bloquear(self) -> bool:
        return self.categoria == 'ANÔMALO' or self.dim_status == 'BLOQUEADO'

    @property
    def deve_revisar(self) -> bool:
        return self.categoria in ('SUSPEITO', 'INCOMUM') or self.dim_status == 'AVISO'

    def __str__(self) -> str:
        return (
            f"[{self.categoria}] {self.tipo.upper()} {self.elemento_id}"
            f"  anomaly={self.anomaly_score:.3f}"
            f"  sem={self.semantic_sim:.3f}  dim={self.dim_status}"
        )

    def to_dict(self) -> dict:
        return {
            'id':             self.elemento_id,
            'tipo':           self.tipo,
            'obra':           self.obra,
            'anomaly_score':  round(self.anomaly_score, 4),
            'categoria':      self.categoria,
            'semantic_sim':   round(self.semantic_sim, 4),
            'dim_penalty':    self.dim_penalty,
            'plausibility':   self.plausibility_acao,
            'dim_status':     self.dim_status,
            'deve_bloquear':  self.deve_bloquear,
            'alertas':        [str(a) for a in self.alertas_dim],
        }


@dataclass
class ObraAnomalyReport:
    """Relatório de anomalias de uma obra completa."""
    obra:       str
    total:      int
    scores:     list = field(default_factory=list)  # lista de AnomalyScore

    @property
    def normais(self)   -> list: return [s for s in self.scores if s.categoria == 'NORMAL']
    @property
    def incomuns(self)  -> list: return [s for s in self.scores if s.categoria == 'INCOMUM']
    @property
    def suspeitos(self) -> list: return [s for s in self.scores if s.categoria == 'SUSPEITO']
    @property
    def anomalos(self)  -> list: return [s for s in self.scores if s.categoria == 'ANÔMALO']
    @property
    def bloqueados(self)-> list: return [s for s in self.scores if s.deve_bloquear]

    @property
    def gate_status(self) -> str:
        """PASS se sem bloqueados, FAIL caso contrário."""
        return 'FAIL' if self.bloqueados else 'PASS'

    @property
    def score_medio(self) -> float:
        if not self.scores:
            return 0.0
        return round(sum(s.anomaly_score for s in self.scores) / len(self.scores), 4)

    def relatorio(self, verbose: bool = False) -> str:
        lines = [
            f"{'='*60}",
            f"ANOMALY REPORT — {self.obra}",
            f"{'='*60}",
            f"Total: {self.total} | Score médio: {self.score_medio:.3f}",
            f"Normal: {len(self.normais)} | Incomum: {len(self.incomuns)} | "
            f"Suspeito: {len(self.suspeitos)} | Anomalo: {len(self.anomalos)}",
            f"Gate: {self.gate_status} | Bloqueados: {len(self.bloqueados)}",
        ]

        if self.bloqueados:
            lines.append("\nELEMENTOS BLOQUEADOS:")
            for s in self.bloqueados:
                lines.append(f"  {s}")
                for a in s.alertas_dim:
                    lines.append(f"    dim: {a}")

        if verbose and self.suspeitos:
            lines.append("\nELEMENTOS SUSPEITOS:")
            for s in self.suspeitos:
                lines.append(f"  {s}")

        lines.append('=' * 60)
        return '\n'.join(lines)

    def to_dict(self) -> dict:
        return {
            'obra':         self.obra,
            'total':        self.total,
            'score_medio':  self.score_medio,
            'gate_status':  self.gate_status,
            'normais':      len(self.normais),
            'incomuns':     len(self.incomuns),
            'suspeitos':    len(self.suspeitos),
            'anomalos':     len(self.anomalos),
            'bloqueados':   len(self.bloqueados),
            'elementos':    [s.to_dict() for s in self.scores],
        }


class AnomalyDetector:
    """
    Detecta anomalias em elementos estruturais combinando
    validação semântica (RAG) e validação dimensional (hard limits).

    Singleton: reutilizar para múltiplas obras.

    Exemplo:
        detector = AnomalyDetector()

        # Elemento único
        s = detector.score_element('pilar', 'P17', {'b': 20, 'h': 50, 'altura': 652}, 'Obra_Nova')
        print(s)  # [NORMAL] PILAR P17  anomaly=0.148

        # Obra completa
        report = detector.report_obra('Obra_X', elementos_json)
        if report.gate_status == 'FAIL':
            print(report.relatorio())
    """

    def __init__(self):
        self.plausibility = PlausibilityChecker(k_similares=3)
        self.validator    = StructuralValidator()

    # Tipos com embeddings confiáveis (têm dimensões reais nos JSONs Fase-3)
    # Vigas e lajes têm b=None/comprimento=None → embeddings todos iguais → sem discriminação
    _SEMANTIC_RELIABLE = {'pilar'}

    def score_element(
        self,
        tipo:        str,
        elemento_id: str,
        dados:       dict,
        obra:        str,
        pavimento:   str = '1_PAV',
    ) -> AnomalyScore:
        """
        Calcula score de anomalia para um elemento.

        Nota: Para vigas e lajes os embeddings FAISS têm b=None (dados ausentes na Fase-3),
        por isso a camada semântica é desabilitada nesses tipos — usa apenas validação
        dimensional (StructuralValidator), que é determinística e confiável.

        Returns:
            AnomalyScore com todos os detalhes
        """
        # 1. Validação dimensional (hard limits) — sempre ativa
        val = self.validator.validate(tipo, elemento_id, dados, obra)

        if val.bloqueado:
            dim_penalty = 1.0
        elif val.avisos:
            dim_penalty = 0.5
        else:
            dim_penalty = 0.0

        # 2. Plausibilidade semântica (RAG) — apenas para tipos com dados confiáveis
        if tipo in self._SEMANTIC_RELIABLE:
            plaus = self.plausibility.check(elemento_id, tipo, dados, obra, pavimento)
            semantic_sim = plaus.similarity
            plausibility_acao = plaus.acao
        else:
            # Sem semântica confiável — score neutro (0.5 = sem evidência)
            semantic_sim = 0.5
            plausibility_acao = 'SEM_SEMANTICA'

        # 3. Score combinado
        if tipo in self._SEMANTIC_RELIABLE:
            # Combina semântico + dimensional
            anomaly = 0.5 * (1.0 - semantic_sim) + 0.5 * dim_penalty
        else:
            # Apenas dimensional
            anomaly = dim_penalty
        anomaly = max(0.0, min(1.0, anomaly))

        # 4. Categoria
        if anomaly <= THRESH_NORMAL:
            categoria = 'NORMAL'
        elif anomaly <= THRESH_INCOMUM:
            categoria = 'INCOMUM'
        elif anomaly <= THRESH_SUSPEITO:
            categoria = 'SUSPEITO'
        else:
            categoria = 'ANÔMALO'

        return AnomalyScore(
            elemento_id=elemento_id,
            tipo=tipo,
            obra=obra,
            anomaly_score=anomaly,
            semantic_sim=semantic_sim,
            dim_penalty=dim_penalty,
            categoria=categoria,
            plausibility_acao=plausibility_acao,
            dim_status=val.status,
            alertas_dim=val.alertas,
            similares=plaus.similares if tipo in self._SEMANTIC_RELIABLE else [],
        )

    def score_batch(self, elementos: list, obra: str) -> list:
        """Calcula scores para lista de elementos."""
        results = []
        for elem in elementos:
            if 'entity_type' in elem:
                tipo_map = {'Pilar': 'pilar', 'Viga': 'viga', 'Laje': 'laje',
                            'pilar': 'pilar', 'viga': 'viga', 'laje': 'laje'}
                tipo = tipo_map.get(elem.get('entity_type', ''), 'pilar')
                eid  = elem.get('name', elem.get('id', '?'))
                dados = elem
            elif 'tipo' in elem:
                tipo  = elem['tipo']
                eid   = elem.get('id', elem.get('name', '?'))
                dados = elem.get('dados', elem)
            else:
                continue
            results.append(self.score_element(tipo, eid, dados, obra))
        return results

    def report_obra(self, obra: str, elementos: list) -> ObraAnomalyReport:
        """Gera relatório completo de anomalias para uma obra."""
        scores = self.score_batch(elementos, obra)
        return ObraAnomalyReport(obra=obra, total=len(elementos), scores=scores)

    def report_from_json(self, json_path: str, obra: str) -> ObraAnomalyReport:
        """Carrega elementos de arquivo JSON e gera relatório."""
        import json
        with open(json_path, encoding='utf-8', errors='replace') as f:
            dados = json.load(f)

        # Tentar auto-detectar formato
        if isinstance(dados, dict):
            elementos = []
            for eid, edata in dados.items():
                if isinstance(edata, dict):
                    tipo = edata.get('tipo', 'pilar')
                    elementos.append({'tipo': tipo, 'id': eid, 'dados': edata})
        elif isinstance(dados, list):
            elementos = dados
        else:
            elementos = []

        return self.report_obra(obra, elementos)


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='RAG Anomaly Detector — CAD-ANALYZER')
    parser.add_argument('--obra', help='Nome da obra para testar')
    parser.add_argument('--test', action='store_true', help='Executar teste interno')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    detector = AnomalyDetector()

    if args.test or not args.obra:
        print('\n=== AnomalyDetector — Teste ===')

        elementos = [
            {'tipo': 'pilar', 'id': 'P17',  'dados': {'b': 20.0, 'h': 50.0, 'altura': 652.0}},
            {'tipo': 'pilar', 'id': 'P_ABS','dados': {'b': 999.0,'h': 999.0, 'altura': 50000.0}},
            {'tipo': 'pilar', 'id': 'P25',  'dados': {'b': 45.0, 'h': 96.0, 'altura': 652.0}},
            {'tipo': 'viga',  'id': 'V5',   'dados': {'b': 14.0, 'h': 40.0, 'comprimento': 320.0}},
            {'tipo': 'viga',  'id': 'V_XL', 'dados': {'b': 14.0, 'h': 40.0, 'comprimento': 9999.0}},
            {'tipo': 'laje',  'id': 'L3',   'dados': {'area_cm2': 171000.0}},
        ]

        report = detector.report_obra('Obra_Teste', elementos)
        print(report.relatorio(verbose=args.verbose))

        # JSON output
        import json
        print('\nJSON summary:')
        d = report.to_dict()
        del d['elementos']  # skip detalhe
        print(json.dumps(d, ensure_ascii=False, indent=2))
