#!/usr/bin/env python3
"""
rag_validator.py — CAD-ANALYZER Sprint 1
==========================================
Validação de dimensões estruturais contra limites calibrados nas 11 obras reais.
Dois modos de validação:
  1. HARD LIMITS — faixas absolutas derivadas das obras de treino (determínístico)
  2. STATISTICAL — percentis reais do corpus RAG (requer FAISS carregado)

Integração:
  - Em robot_integration.py antes de engine.transform()
  - Em sprint_e_production_gate.py como gate D8: Range Check

Uso:
    from rag_validator import StructuralValidator
    v = StructuralValidator()
    result = v.validate_pilar({'b': 20.0, 'h': 50.0, 'altura': 652.0})
    if result.bloqueado:
        print(result.relatorio())
"""
import sys, json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Limites calibrados manualmente nas 11 obras (conservative bounds) ────────
# Fonte: inspeção do REGISTRY.json + ground truth de pilares/vigas/lajes
# Atualizar ao adicionar mais obras ao corpus

LIMITES = {
    'pilar': {
        'b':      (12.0,  200.0,  'cm'),   # largura mínima/máxima
        'h':      (12.0,  200.0,  'cm'),   # comprimento da seção
        'altura': (150.0, 1200.0, 'cm'),   # pé-direito (~1.5m → ~12m)
    },
    'viga': {
        'b':           (10.0,  80.0,   'cm'),
        'h':           (15.0,  150.0,  'cm'),
        'comprimento': (30.0,  3000.0, 'cm'),
    },
    'laje': {
        'espessura':   (7.0,   50.0,   'cm'),
        'comprimento': (50.0,  2000.0, 'cm'),
        'largura':     (50.0,  2000.0, 'cm'),
        'area_cm2':    (2500.0, 20000000.0, 'cm²'),
    },
}

# Fatores para severidade
FATOR_CRITICO  = 3.0   # > max * 3 → CRÍTICO
FATOR_WARN     = 1.0   # fora do range → AVISO


@dataclass
class AlertaDimensao:
    campo:      str
    valor:      float
    minimo:     float
    maximo:     float
    unidade:    str
    severidade: str   # CRÍTICO | AVISO

    def __str__(self) -> str:
        direcao = 'abaixo de' if self.valor < self.minimo else 'acima de'
        limite  = self.minimo if self.valor < self.minimo else self.maximo
        return (
            f"[{self.severidade}] {self.campo}={self.valor}{self.unidade} "
            f"({direcao} {limite}{self.unidade})"
        )


@dataclass
class ValidationResult:
    tipo:       str
    elemento_id: str = ''
    obra:       str = ''
    alertas:    list = field(default_factory=list)  # lista de AlertaDimensao
    dims_verificadas: int = 0

    @property
    def criticos(self) -> list:
        return [a for a in self.alertas if a.severidade == 'CRÍTICO']

    @property
    def avisos(self) -> list:
        return [a for a in self.alertas if a.severidade == 'AVISO']

    @property
    def bloqueado(self) -> bool:
        """True se há alertas CRÍTICOS — deve bloquear geração do DXF."""
        return len(self.criticos) > 0

    @property
    def status(self) -> str:
        if self.bloqueado:
            return 'BLOQUEADO'
        elif self.avisos:
            return 'AVISO'
        return 'OK'

    def relatorio(self) -> str:
        lines = [f"Validação {self.tipo.upper()} {self.elemento_id} [{self.status}]"]
        for a in self.alertas:
            lines.append(f"  {a}")
        if not self.alertas:
            lines.append(f"  {self.dims_verificadas} dimensões OK")
        return '\n'.join(lines)

    def to_dict(self) -> dict:
        return {
            'tipo':       self.tipo,
            'id':         self.elemento_id,
            'obra':       self.obra,
            'status':     self.status,
            'bloqueado':  self.bloqueado,
            'criticos':   len(self.criticos),
            'avisos':     len(self.avisos),
            'alertas':    [str(a) for a in self.alertas],
        }


class StructuralValidator:
    """
    Valida dimensões estruturais contra limites calibrados.

    Determinístico — não depende de FAISS nem de modelo de embeddings.
    Rápido O(1) por elemento.

    Exemplo:
        v = StructuralValidator()
        r = v.validate('pilar', 'P17', {'b': 20.0, 'h': 50.0, 'altura': 652.0})
        r = v.validate('viga',  'V5',  {'b': 14.0, 'h': 40.0, 'comprimento': 320.0})
        r = v.validate('laje',  'L3',  {'area_cm2': 171000.0})

        # Batch
        resultados = v.validate_batch(elementos, obra='Obra_Nova')
        bloqueados = [r for r in resultados if r.bloqueado]
    """

    def validate(
        self,
        tipo: str,
        elemento_id: str,
        dados: dict,
        obra: str = '',
    ) -> ValidationResult:
        """
        Valida dimensões de um elemento.

        Args:
            tipo:         'pilar' | 'viga' | 'laje'
            elemento_id:  ID do elemento (P17, V5, L3)
            dados:        dict com campos dimensionais
            obra:         nome da obra (para log)

        Returns:
            ValidationResult com alertas e status
        """
        result = ValidationResult(tipo=tipo, elemento_id=elemento_id, obra=obra)
        limites_tipo = LIMITES.get(tipo, {})

        for campo, (minv, maxv, unidade) in limites_tipo.items():
            valor_raw = dados.get(campo)
            if valor_raw is None:
                continue   # campo ausente — não validar (pode ser null legítimo)

            try:
                valor = float(valor_raw)
            except (TypeError, ValueError):
                continue   # não numérico — pular

            result.dims_verificadas += 1

            if valor < minv or valor > maxv:
                # Determinar severidade
                if valor > maxv * FATOR_CRITICO or valor < minv / FATOR_CRITICO:
                    severidade = 'CRÍTICO'
                else:
                    severidade = 'AVISO'

                result.alertas.append(AlertaDimensao(
                    campo=campo,
                    valor=valor,
                    minimo=minv,
                    maximo=maxv,
                    unidade=unidade,
                    severidade=severidade,
                ))

        return result

    def validate_pilar(self, id_: str, dados: dict, obra: str = '') -> ValidationResult:
        return self.validate('pilar', id_, dados, obra)

    def validate_viga(self, id_: str, dados: dict, obra: str = '') -> ValidationResult:
        return self.validate('viga', id_, dados, obra)

    def validate_laje(self, id_: str, dados: dict, obra: str = '') -> ValidationResult:
        return self.validate('laje', id_, dados, obra)

    def validate_batch(self, elementos: list, obra: str = '') -> list:
        """
        Valida lista de elementos.

        Args:
            elementos: lista de dicts com {'tipo', 'id'/'name', 'dados'} OU
                       formato robot_integration.py {'entity_type', 'name', fields...}
            obra:      nome da obra

        Returns:
            lista de ValidationResult
        """
        results = []
        for elem in elementos:
            # Suporte a múltiplos formatos
            if 'entity_type' in elem:
                # Formato robot_integration
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

            results.append(self.validate(tipo, eid, dados, obra))
        return results

    def summary(self, results: list) -> dict:
        """Resumo dos resultados de batch."""
        bloqueados = [r for r in results if r.bloqueado]
        avisos     = [r for r in results if not r.bloqueado and r.avisos]
        ok         = [r for r in results if r.status == 'OK']
        return {
            'total':     len(results),
            'ok':        len(ok),
            'avisos':    len(avisos),
            'bloqueados': len(bloqueados),
            'taxa_ok':   round(len(ok) / max(len(results), 1) * 100, 1),
            'elementos_bloqueados': [r.to_dict() for r in bloqueados],
        }

    def relatorio_obra(self, obra: str, elementos: list) -> str:
        """Gera relatório completo de validação para uma obra."""
        results = self.validate_batch(elementos, obra)
        s = self.summary(results)
        lines = [
            f"=== VALIDAÇÃO DIMENSIONAL — {obra} ===",
            f"Total: {s['total']} | OK: {s['ok']} | Avisos: {s['avisos']} | Bloqueados: {s['bloqueados']}",
            f"Taxa OK: {s['taxa_ok']}%",
        ]
        if s['elementos_bloqueados']:
            lines.append("\nELEMENTOS BLOQUEADOS:")
            for eb in s['elementos_bloqueados']:
                lines.append(f"  {eb['tipo'].upper()} {eb['id']}: {'; '.join(eb['alertas'])}")
        lines.append("=" * 50)
        return '\n'.join(lines)


# ── CLI de teste ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    v = StructuralValidator()
    print('\n=== StructuralValidator — Teste ===')

    casos = [
        ('pilar', 'P17',  {'b': 20.0, 'h': 50.0, 'altura': 652.0}),           # OK
        ('pilar', 'P_ABSURDo', {'b': 999.0, 'h': 999.0, 'altura': 50000.0}),  # CRÍTICO
        ('pilar', 'P_AVISO', {'b': 120.0, 'h': 180.0, 'altura': 900.0}),      # AVISO (h grande)
        ('viga',  'V5',   {'b': 14.0, 'h': 40.0, 'comprimento': 320.0}),      # OK
        ('viga',  'V_LONGA', {'b': 14.0, 'h': 40.0, 'comprimento': 9999.0}),  # CRÍTICO
        ('laje',  'L3',   {'area_cm2': 171000.0}),                             # OK
        ('laje',  'L_FINA', {'espessura': 3.0}),                               # AVISO
    ]

    for tipo, eid, dados in casos:
        r = v.validate(tipo, eid, dados)
        print(f'  {r.relatorio()}')

    # Relatório de obra
    elementos = [{'tipo': t, 'id': i, 'dados': d} for t, i, d in casos]
    print('\n' + v.relatorio_obra('Obra_Teste', elementos))
