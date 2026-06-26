---
id: CAD-10.4
title: "Comparison Panel na Ficha"
epic: CAD-10
status: Draft
executor: "@dev"
quality_gate: "@qa"
quality_gate_tools: [ui_test, integration_test, code_review]
effort: 8
priority: MEDIUM
dependencies: [CAD-10.2]
---

# CAD-10.4: Comparison Panel na Ficha

## Description

Adicionar aba/botao "Comparar" dentro do DetailCard que mostra side-by-side os valores do Ground Truth (Fase-3), da Interpretacao (Fase-4 JSON), e do DB atual. Cada campo recebe um score de concordancia. O usuario pode aceitar a interpretacao automatica ou salvar correcoes.

## Problem / Need

Apos a importacao Fase-4 (CAD-10.2), o usuario nao tem visibilidade sobre quais campos foram auto-populados, quais diferem do ground truth, e quais tem conflito com valores manuais. Nao existe mecanismo para aceitar/rejeitar interpretacoes campo-a-campo.

## Scope

### IN Scope
- Nova aba "Comparar" no TabWidget do DetailCard (ao lado das abas de face/lado)
- Tabela comparativa: campo | GT value | Fase-4 value | DB value | Status
- Status icons: IGUAL, DIFERENTE, AUSENTE_GT, AUSENTE_F4, CONFLITO
- Score de completude: % campos com match, % campos preenchidos
- Botao "Aceitar interpretacao" por campo (popula DB com valor Fase-4)
- Botao "Aceitar todos" (batch accept de campos sem conflito)
- Botao "Salvar correcao" (grava valor DB de volta ao JSON Fase-4)
- Visual: highlight vermelho para divergencias, verde para matches

### OUT of Scope
- Comparison Engine renovado (CAD-10.5 — que compara entre obras)
- Machine learning de correcoes (CAD-10.6 e futuro)
- Edicao direta do JSON Fase-4 pela UI

## Acceptance Criteria

### AC1: Aba "Comparar" aparece no DetailCard
**Given** DetailCard de pilar P1 esta aberto
**And** Fase-4 JSON existe para P1
**When** usuario clica na aba "Comparar"
**Then** tabela comparativa aparece com colunas:
- "Campo" — nome legivel (ex: "Face A - Hachura H1")
- "Ground Truth" — valor de pilares_ground_truth.json (se existir)
- "Interpretado (Fase-4)" — valor do JSON_Pilares/P1.json
- "Ficha Atual (DB)" — valor corrente no banco
- "Status" — icone de concordancia

### AC2: Status de concordancia correto
**Given** tabela comparativa esta visivel
**Then** status de cada campo segue logica:
- `IGUAL` (verde): GT == Fase-4 == DB (ou GT ausente e Fase-4 == DB)
- `DIFERENTE` (amarelo): Fase-4 != DB e nenhum esta vazio
- `AUSENTE_GT` (cinza): Ground truth nao tem este campo
- `AUSENTE_F4` (cinza): Fase-4 nao tem este campo
- `CONFLITO` (vermelho): campo validado manualmente com valor diferente do Fase-4

### AC3: Score de completude
**Given** pilar P1 tem 40 campos mapeaveis
**And** 30 campos tem valor no Fase-4
**And** 25 desses concordam com DB
**When** aba "Comparar" e aberta
**Then** score mostra: "Completude: 75% (30/40) | Match: 83% (25/30)"

### AC4: Aceitar interpretacao individual
**Given** campo "Face A - H1" tem Fase-4=244.0 e DB=vazio
**When** usuario clica icone "Aceitar" neste campo
**Then** DB e atualizado com valor 244.0
**And** campo muda status para IGUAL
**And** field no DetailCard principal tambem atualiza visualmente
**And** campo NAO e adicionado a validated_fields (aceitar != validar)

### AC5: Aceitar todos sem conflito
**Given** 20 campos tem status DIFERENTE ou AUSENTE com valor Fase-4 disponivel
**And** 3 campos tem status CONFLITO
**When** usuario clica "Aceitar Todos (Sem Conflito)"
**Then** 20 campos sao atualizados no DB
**And** 3 campos com CONFLITO permanecem inalterados
**And** toast: "20 campos aceitos, 3 conflitos preservados"

### AC6: Salvar correcao
**Given** campo "Face A - H1" tem DB=250 (corrigido manualmente) e Fase-4=244.0
**When** usuario clica "Salvar Correcao -> Fase-4"
**Then** JSON_Pilares/P1.json e atualizado: `h1_A = 250`
**And** backup do JSON original e criado (P1.json.bak)
**And** entrada em `Fase-3/correction_log.json`:
```json
{
  "item": "P1",
  "field": "h1_A",
  "old_value": 244.0,
  "new_value": 250,
  "source": "manual_correction",
  "timestamp": "2026-05-18T14:30:00",
  "user": "operator"
}
```

### AC7: Sem Fase-4 disponivel
**Given** DetailCard de pilar P1 esta aberto
**And** nao existe JSON_Pilares/P1.json
**When** usuario clica na aba "Comparar"
**Then** mensagem: "Fase-4 nao processada para este item. Execute 'Analise Geral' primeiro."
**And** botao direto: "Executar Analise Geral"

### AC8: Funciona para vigas e lajes
**Given** DetailCard de viga V7 esta aberto
**When** aba "Comparar" e clicada
**Then** tabela mostra campos por segmento: Seg1 width, Seg1 h1, Seg1 h2, etc.
**And** mesma logica de aceitar/corrigir funciona

**Given** DetailCard de laje L1 esta aberto
**When** aba "Comparar" e clicada
**Then** tabela mostra campos de dimensao, pontaletes, grid

## Technical Notes

### UI Layout

```
DetailCard TabWidget:
  [Lado A] [Lado B] [Lado C] [Lado D] [Comparar]
                                          ^
                                    nova aba (esta story)
```

Para vigas:
```
  [Lado A] [Lado B] [Fundo] [Comparar]
```

### Data Sources

```python
# Ground Truth
gt_path = obra / "Fase-3_Interpretacao_Extracao" / "Pilares" / "pilares_ground_truth.json"

# Fase-4 Interpretado
f4_path = obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{item_id}.json"

# DB (current)
db_value = self.item_data.get(field_id)
```

### Comparison Table Widget

Usar QTableWidget com delegate personalizado para icones de status. Colunas fixas: Campo (stretch), GT (120px), Fase-4 (120px), DB (120px), Status (60px), Acao (80px).

## File List

| File | Action | Description |
|------|--------|-------------|
| `src/ui/widgets/detail_card.py` | MODIFY | Add "Comparar" tab |
| `src/ui/widgets/comparison_tab.py` | CREATE | Comparison table widget |
| `src/core/services/comparison_service.py` | CREATE | Data comparison logic |
| `tests/test_comparison_tab.py` | CREATE | Unit tests |

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-18 | @pm | Story created |
