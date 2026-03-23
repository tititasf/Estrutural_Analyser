#!/usr/bin/env python3
"""
rag_plausibility.py — CAD-ANALYZER Sprint 1
=============================================
Valida plausibilidade de elementos estruturais contra o corpus RAG de 11 obras.
Usado pelo agente_estrutural.py após extração de cada elemento.

Lógica:
  - similarity >= 0.85 → ACEITAR (elemento bem conhecido no corpus)
  - similarity >= 0.65 → ACEITAR_COM_AVISO (elemento plausível, mas incomum)
  - similarity >= 0.40 → REVISAR (elemento suspeito, revisar manualmente)
  - similarity <  0.40 → REJEITAR (sem similar no corpus, alto risco)

Uso:
    from rag_plausibility import PlausibilityChecker
    checker = PlausibilityChecker()
    result = checker.check_pilar('P17', {'b': 20, 'h': 50, 'altura': 652}, 'Obra_Nova')
    # result.acao in ('ACEITAR', 'ACEITAR_COM_AVISO', 'REVISAR', 'REJEITAR')
"""
import sys
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rag_commons import (
    load_model, normalize, load_index,
    fmt_pilar, fmt_viga, fmt_laje, fmt_element, query
)

# ── Thresholds calibrados no corpus de 11 obras ─────────────────────────────
THRESH_ACEITAR       = 0.85
THRESH_AVISO         = 0.65
THRESH_REVISAR       = 0.40


@dataclass
class PlausibilityResult:
    """Resultado de verificação de plausibilidade."""
    elemento_id: str
    tipo: str
    obra: str
    similarity: float          # 0.0 – 1.0 (cosine similarity top-1)
    acao: str                  # ACEITAR | ACEITAR_COM_AVISO | REVISAR | REJEITAR
    similares: list = field(default_factory=list)   # top-3 elementos similares
    nota_rag: str = ""         # nota adicionada à entidade

    @property
    def confidence_delta(self) -> float:
        """Quanto adicionar ao confidence original baseado no RAG."""
        if self.acao == 'ACEITAR':
            return +0.15
        elif self.acao == 'ACEITAR_COM_AVISO':
            return +0.05
        elif self.acao == 'REVISAR':
            return -0.05
        else:  # REJEITAR
            return -0.20

    def __str__(self) -> str:
        top = self.similares[0] if self.similares else None
        top_str = ""
        if top:
            m = top['meta']
            top_str = f" | top_similar={m.get('obra')}/{m.get('tipo')}/{m.get('id')} sim={top['score']:.3f}"
        return (
            f"RAG [{self.acao}] {self.tipo.upper()} {self.elemento_id}"
            f" sim={self.similarity:.3f}{top_str}"
        )


class PlausibilityChecker:
    """
    Verifica plausibilidade de elementos estruturais vs corpus RAG.

    Singleton por tipo: carrega índice FAISS uma vez e mantém em cache.
    Thread-safe apenas para leitura (FAISS é read-safe).

    Exemplo:
        checker = PlausibilityChecker()

        # Verificar pilar
        r = checker.check('P17', 'pilar', {'b': 20, 'h': 50, 'altura': 652}, 'Obra_X')
        if r.acao in ('ACEITAR', 'ACEITAR_COM_AVISO'):
            elem.confidence = min(1.0, elem.confidence + r.confidence_delta)
            elem.nota += f" | {r.nota_rag}"

        # Verificar com dict completo de dados
        r = checker.check_from_dict({'tipo': 'viga', 'id': 'V5', 'dados': {...}, 'obra': 'Obra_1'})
    """

    def __init__(self, k_similares: int = 3):
        self.k = k_similares
        self._model = None   # lazy — carregado na primeira chamada

    def _ensure_model(self):
        if self._model is None:
            self._model = load_model()

    def check(
        self,
        elemento_id: str,
        tipo: str,
        dados: dict,
        obra: str,
        pavimento: str = '1_PAV',
    ) -> PlausibilityResult:
        """
        Verifica plausibilidade de qualquer elemento.

        Args:
            elemento_id: ID do elemento (P17, V5, L3)
            tipo:         'pilar' | 'viga' | 'laje'
            dados:        dict com campos do elemento (b, h, comprimento, etc.)
            obra:         nome da obra sendo processada
            pavimento:    pavimento (default '1_PAV')

        Returns:
            PlausibilityResult com acao e similares
        """
        self._ensure_model()
        texto = fmt_element(elemento_id, tipo, dados, obra, pavimento)
        similares = query(texto, tipo=tipo, k=self.k, threshold=0.0)

        similarity = similares[0]['score'] if similares else 0.0

        if similarity >= THRESH_ACEITAR:
            acao = 'ACEITAR'
            nota = f"RAG-OK: similar a {similares[0]['meta']['obra']}/{similares[0]['meta']['id']} ({similarity:.2f})"
        elif similarity >= THRESH_AVISO:
            acao = 'ACEITAR_COM_AVISO'
            nota = f"RAG-AVISO: elemento incomum no corpus (sim={similarity:.2f})"
        elif similarity >= THRESH_REVISAR:
            acao = 'REVISAR'
            nota = f"RAG-REVISAR: pouco similar ao corpus (sim={similarity:.2f})"
        else:
            acao = 'REJEITAR'
            nota = f"RAG-ANOMALIA: sem similar no corpus (sim={similarity:.2f})"

        return PlausibilityResult(
            elemento_id=elemento_id,
            tipo=tipo,
            obra=obra,
            similarity=similarity,
            acao=acao,
            similares=similares,
            nota_rag=nota,
        )

    def check_pilar(self, id_: str, dados: dict, obra: str, **kw) -> PlausibilityResult:
        return self.check(id_, 'pilar', dados, obra, **kw)

    def check_viga(self, id_: str, dados: dict, obra: str, **kw) -> PlausibilityResult:
        return self.check(id_, 'viga', dados, obra, **kw)

    def check_laje(self, id_: str, dados: dict, obra: str, **kw) -> PlausibilityResult:
        return self.check(id_, 'laje', dados, obra, **kw)

    def check_from_dict(self, meta: dict) -> PlausibilityResult:
        """
        Verifica a partir de um dict no formato do corpus RAG.
        Útil para re-verificar elementos já ingeridos.
        """
        return self.check(
            elemento_id=meta.get('id', '?'),
            tipo=meta.get('tipo', 'pilar'),
            dados=meta.get('dados', {}),
            obra=meta.get('obra', '?'),
            pavimento=meta.get('pavimento', '1_PAV'),
        )

    def check_batch(self, elementos: list, obra: str) -> list:
        """
        Verifica lista de elementos em batch.

        Args:
            elementos: lista de dicts com {'id', 'tipo', 'dados'} ou formato corpus
            obra:      nome da obra

        Returns:
            lista de PlausibilityResult
        """
        results = []
        for elem in elementos:
            if 'tipo' in elem and 'dados' in elem:
                r = self.check_from_dict({**elem, 'obra': obra})
            elif 'entity_type' in elem:
                # Formato do robot_integration.py
                tipo_map = {'Pilar': 'pilar', 'Viga': 'viga', 'Laje': 'laje'}
                tipo = tipo_map.get(elem.get('entity_type', ''), 'pilar')
                r = self.check(
                    elemento_id=elem.get('name', elem.get('id', '?')),
                    tipo=tipo,
                    dados=elem,
                    obra=obra,
                )
            else:
                continue
            results.append(r)
        return results

    def summary(self, results: list) -> dict:
        """Resumo de resultados de batch."""
        contagem = {'ACEITAR': 0, 'ACEITAR_COM_AVISO': 0, 'REVISAR': 0, 'REJEITAR': 0}
        for r in results:
            contagem[r.acao] = contagem.get(r.acao, 0) + 1
        total = len(results)
        return {
            'total': total,
            'contagem': contagem,
            'taxa_aceite': round((contagem['ACEITAR'] + contagem['ACEITAR_COM_AVISO']) / max(total, 1) * 100, 1),
            'taxa_revisao': round((contagem['REVISAR'] + contagem['REJEITAR']) / max(total, 1) * 100, 1),
        }


# ── CLI de teste ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import json, sys
    checker = PlausibilityChecker()

    # Teste com dados reais do corpus
    casos = [
        ('P17', 'pilar', {'b': 20.0, 'h': 50.0, 'altura': 652.0, 'confidence': 0.80}, 'Obra_TREINO_1'),
        ('P99', 'pilar', {'b': 999.0, 'h': 999.0, 'altura': 50000.0}, 'Obra_Nova'),
        ('V5',  'viga',  {'b': 14.0, 'h': 40.0, 'comprimento': 320.0}, 'Obra_TREINO_3'),
        ('L3',  'laje',  {'comprimento': 450.0, 'largura': 380.0, 'area_cm2': 171000.0}, 'Obra_TREINO_6'),
    ]

    print('\n=== PlausibilityChecker — Teste ===')
    for eid, tipo, dados, obra in casos:
        r = checker.check(eid, tipo, dados, obra)
        print(f'  {r}')

    # Batch summary
    elementos = [{'tipo': t, 'id': i, 'dados': d, 'obra': o} for i, t, d, o in casos]
    results = checker.check_batch(elementos, 'batch_test')
    s = checker.summary(results)
    print(f'\n  Batch: {s["total"]} elementos | aceite={s["taxa_aceite"]}% revisão={s["taxa_revisao"]}%')
    print('=== OK ===\n')
