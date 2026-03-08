# Story CAD-6.8 — Comparador DXF Gerado vs. Ground Truth

**Epic:** 6 — Robô-Driven DXF Generation + Comparação
**Sprint:** 3
**Status:** Done
**Criado:** 2026-03-08
**Assignee:** @dev (aios-dev)

---

## Objetivo

Criar `scripts/comparar_dxf.py` — comparador que valida os DXFs gerados (Fase 5)
contra os dados extraídos do STOG (Fase 3 / ground truth).

## Métricas

| Categoria | Tolerância | Meta |
|-----------|-----------|------|
| Dimensões B/H/comprimento | ±5% | 75% match rate |
| Score geral | — | >= 75% |

## Resultado Final (2026-03-08)

| Elemento | Match Rate | Erro Médio | Status |
|----------|-----------|-----------|--------|
| **Pilares** | 100.0% (33/33) | 0.0% | PASS |
| **Vigas** | 100.0% (33/33) | 0.0% | PASS |
| **Lajes** | 100.0% (19/19) | 0.0% | PASS |
| **GERAL** | **100.0%** | — | **PASS** |

**Meta: 75.0% — ATINGIDA COM SCORE PERFEITO** ✅

*Nota: Resultado 100% após fix do motor_fase4.py (CAD-6.9 integrado nesta story).*

## Acceptance Criteria

- [x] **AC-1:** Script `scripts/comparar_dxf.py` criado
- [x] **AC-2:** Compara pilares (B/H) com pilares_bh.json
- [x] **AC-3:** Compara vigas (h/L) com vigas.json
- [x] **AC-4:** Compara lajes (comprimento/largura) com lajes.json
- [x] **AC-5:** Score geral >= 75% calculado e reportado
- [x] **AC-6:** Relatório `_relatorio_comparacao.json` salvo

## Fix Aplicado (motor_fase4.py — linha 180)

Bug: `range(6)` limitava a 6 painéis máx (720cm). 6 vigas eram truncadas.
Fix: `n_panels = max(1, math.ceil(comprimento/120))` — calculado dinamicamente.
- V2: 10 painéis (1184.5cm) | V7: 11 painéis (1205.0cm) | V15: 8 painéis (892.5cm)
- Resultado após fix: score sobe para 100%

## Arquivos

- `scripts/comparar_dxf.py`
- `DADOS-OBRAS/Obra_TREINO_21/Fase-5_Geracao_Scripts/_relatorio_comparacao.json`

---

*Story CAD-6.8 | Sprint 3 | DXF Comparison | CAD-ANALYZER v3.0*
