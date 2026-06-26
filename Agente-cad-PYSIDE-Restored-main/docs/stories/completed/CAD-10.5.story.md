---
id: CAD-10.5
title: "Comparison Engine Renovado"
epic: CAD-10
status: Draft
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: [architecture_review, integration_test, code_review]
effort: 13
priority: MEDIUM
dependencies: [CAD-10.2]
---

# CAD-10.5: Comparison Engine Renovado

## Description

Renovar o Comparison Engine (Tab 2) para ir alem da validacao visual (NVIDIA NIM). Adicionar painel de comparacao tri-fonte (Ground Truth vs Interpretado vs Ficha UI) com drill-down por item, delta visual com campos divergentes destacados, e exportacao de audit report.

## Problem / Need

O Comparison Engine atual (`comparison_engine.py` / `Fase8Panel`) faz apenas validacao visual por tipo (PL, LV, FV, LJ) com score global via NVIDIA NIM. Nao compara dados campo-a-campo, nao permite drill-down por item individual, e nao gera relatorio auditavel de discrepancias.

## Scope

### IN Scope
- Novo layout do Tab 2: manter DualCanvas + Fase8Panel, adicionar painel de comparacao
- Seletor hierarquico: obra -> pavimento -> tipo (Pilar/Viga/Laje) -> item (P1, V101, L101)
- Painel tri-fonte: GT (esquerda) | Interpretado (centro) | Ficha UI (direita)
- Delta visual: campos divergentes destacados em vermelho/amarelo
- Score por tipo: % campos corretos para Pilares / Vigas / Lajes
- Score por item: % campos corretos para item selecionado
- Tabela resumo com todos os itens e seus scores
- Exportacao de audit report (JSON + summary)
- Integracao com Fase-8 existente (scores visuais continuam funcionando)

### OUT of Scope
- Substituicao do sistema visual NVIDIA NIM (complementar, nao substituir)
- Machine learning ou sugestoes automaticas
- Comparacao cross-obra ou cross-pavimento

## Acceptance Criteria

### AC1: Seletor hierarquico funcional
**Given** obra Obra_TREINO_21 selecionada com Fase-3, Fase-4 e DB populados
**When** usuario navega no seletor
**Then** pode selecionar:
- Tipo: Pilares / Vigas Laterais / Vigas Fundo / Lajes
- Item: lista dropdown com todos os itens do tipo (P1..P30, V1_A..V60_B, L1..L20)
- Ao selecionar item, painel tri-fonte atualiza

### AC2: Painel tri-fonte para pilar
**Given** pilar P1 selecionado
**When** painel tri-fonte renderiza
**Then** mostra 3 colunas:
- **GT (Fase-3)**: `pilares_ground_truth.json` — b, h, altura, confidence, faces_encontradas
- **Interpretado (Fase-4)**: `JSON_Pilares/P1.json` — h1_A..h5_H, larg1_A..D, grade_1/2, par_1_2..8_9, comprimento, largura, altura
- **Ficha UI (DB)**: item_data do banco — sides_data, links, validated_fields
- Campos comuns alinhados na mesma linha
- Campos exclusivos de uma fonte aparecem com valor "---" nas outras

### AC3: Delta visual correto
**Given** GT tem `h = 290`, Fase-4 tem `altura = 290`, DB tem `dim = "15x29"` (29 cm interpretado como 290 mm)
**When** painel renderiza
**Then** campos com valores iguais (ou equivalentes apos conversao de unidade) aparecem em verde
**And** campos com valores diferentes aparecem em vermelho
**And** campos presentes em uma fonte mas ausentes em outra aparecem em amarelo
**And** tooltip mostra: "GT: 290 | F4: 290 | DB: 29 (290mm) — MATCH"

### AC4: Score por tipo
**Given** obra com 30 pilares processados
**When** tipo "Pilares" selecionado (sem item especifico)
**Then** tabela mostra:
| Item | Campos Totais | Match GT-F4 | Match F4-DB | Score |
|------|--------------|-------------|-------------|-------|
| P1   | 40           | 35          | 30          | 75%   |
| P2   | 40           | 38          | 38          | 95%   |
| ...  | ...          | ...         | ...         | ...   |
| **Media** | **40** | **36** | **33** | **83%** |

### AC5: Score por item
**Given** pilar P1 selecionado
**When** painel tri-fonte renderiza
**Then** cabecalho mostra:
- "P1 — Completude: 75% | Match GT-F4: 87% | Match F4-DB: 75%"
- Barra de progresso visual para cada score

### AC6: Exportacao de audit report
**Given** obra completa processada
**When** usuario clica "Exportar Relatorio"
**Then** gera `Fase-8_Revisao_Entrega/comparison_audit_{timestamp}.json`:
```json
{
  "obra": "Obra_TREINO_21",
  "pavimento": "12 PAV",
  "timestamp": "2026-05-18T14:30:00",
  "summary": {
    "pilares": {"total": 30, "avg_score": 83.2},
    "vigas_laterais": {"total": 60, "avg_score": 71.5},
    "vigas_fundo": {"total": 30, "avg_score": 68.0},
    "lajes": {"total": 20, "avg_score": 90.1}
  },
  "items": [
    {"id": "P1", "type": "pilar", "score": 75.0, "conflicts": ["h1_A", "larg1_B"], ...},
    ...
  ]
}
```
**And** summary legivel em markdown tambem exportado

### AC7: Integracao com Fase-8 existente
**Given** Fase8Panel (validacao visual) esta ativo
**When** novo painel de comparacao e adicionado
**Then** layout do Tab 2 preserva:
- DualCanvas no lado esquerdo (inalterado)
- Fase8Panel no lado direito (inalterado)
- Novo painel acessivel via aba/toggle no Fase8Panel OU como aba adicional

### AC8: Performance
**Given** obra com 30 pilares, 60 vigas, 20 lajes
**When** tipo "Pilares" selecionado
**Then** tabela de scores renderiza em < 2 segundos
**When** item P1 selecionado
**Then** painel tri-fonte renderiza em < 500ms

## Technical Notes

### Layout Options

Opcao recomendada: Adicionar aba "Comparacao" no QTabWidget que ja existe dentro do Fase8Panel (ao lado de "Historico" e "Tendencia"):

```
Fase8Panel:
  [Obra & Tipo]
  [Botao Validar]
  [Scores]
  [Certificar]
  [Historico | Tendencia | Comparacao]  <-- nova aba aqui
                               ^
```

Isso evita quebrar o layout existente e reutiliza o seletor de obra/pavimento.

### Data Loading

```python
# Carregar as 3 fontes
gt = load_ground_truth(obra, tipo)     # Fase-3/{Pilares,Vigas,Lajes}/*_ground_truth.json
f4 = load_fase4_data(obra, tipo)       # Fase-4/JSON_{tipo}/*.json
db = load_db_data(obra, pavimento)     # Database items

# Usar field_mapping.py (CAD-10.1) para normalizar
normalized_gt = normalize_to_canonical(gt, 'gt')
normalized_f4 = normalize_to_canonical(f4, 'f4')
normalized_db = normalize_to_canonical(db, 'db')

# Computar deltas
deltas = compute_deltas(normalized_gt, normalized_f4, normalized_db)
```

## File List

| File | Action | Description |
|------|--------|-------------|
| `src/ui/modules/comparison_engine.py` | MODIFY | Add comparison tab to Fase8Panel |
| `src/ui/widgets/comparison_panel.py` | CREATE | Tri-source comparison widget |
| `src/ui/widgets/item_score_table.py` | CREATE | Score summary table widget |
| `src/core/services/comparison_service.py` | MODIFY | Add tri-source comparison logic |
| `src/core/services/audit_exporter.py` | CREATE | Export audit report |
| `tests/test_comparison_engine_v2.py` | CREATE | Integration tests |

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-18 | @pm | Story created |
