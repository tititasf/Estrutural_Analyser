---
id: CAD-10.6
title: "Realimentacao do Interpretador"
epic: CAD-10
status: Draft
executor: "@dev"
quality_gate: "@qa"
quality_gate_tools: [integration_test, data_integrity, code_review]
effort: 5
priority: LOW
dependencies: [CAD-10.4]
---

# CAD-10.6: Realimentacao do Interpretador

## Description

Implementar o ciclo de feedback: quando o usuario corrige um campo no DetailCard e valida, a correcao e gravada de volta no JSON Fase-4 e registrada em um log de correcoes. Este log servira futuramente como dados de treinamento para melhorar os extratores automaticos.

## Problem / Need

Atualmente, correcoes manuais feitas pelo usuario no DetailCard ficam apenas no DB local. Nao existe mecanismo para que essas correcoes retroalimentem o pipeline — os JSONs Fase-4 permanecem com valores originais (possivelmente incorretos), e obras futuras repetem os mesmos erros de extracao.

## Scope

### IN Scope
- Script `scripts/apply_correction.py` que grava correcao no JSON Fase-4
- Log de correcoes em `Fase-3_Interpretacao_Extracao/correction_log.json`
- Hook no DetailCard: ao validar campo com valor diferente do Fase-4, perguntar se quer realimentar
- Backup automatico do JSON antes de gravar correcao
- CLI para aplicar batch de correcoes: `python scripts/apply_correction.py --obra X --from-log`
- Metricas de correcao por tipo de campo (quais campos mais erram)

### OUT of Scope
- Treinamento de ML com correction_log (futuro CAD-11+)
- Ajuste automatico de parametros do motor_fase4.py
- Correcoes cross-obra (cada obra tem seu correction_log)

## Acceptance Criteria

### AC1: Correcao individual via DetailCard
**Given** pilar P1 tem campo `h1_A` com Fase-4=244.0 e usuario corrigiu para 250
**And** usuario clica "VALIDAR (TREINAR IA)" no DetailCard
**When** sistema detecta divergencia entre DB e Fase-4
**Then** dialog pergunta: "Campo 'Face A - H1' diverge da interpretacao automatica (244.0 vs 250). Deseja atualizar o JSON Fase-4?"
**And** opcoes: "Sim, corrigir Fase-4" / "Nao, manter apenas no DB" / "Sim para todos os campos divergentes"

### AC2: Gravacao no JSON Fase-4
**Given** usuario confirma correcao do campo h1_A
**When** `apply_correction.py` e chamado
**Then** `Fase-4/JSON_Pilares/P1.json` e atualizado: `h1_A: 250`
**And** backup criado: `Fase-4/JSON_Pilares/P1.json.bak.{timestamp}`
**And** demais campos do JSON permanecem inalterados

### AC3: Log de correcoes
**Given** correcao aplicada
**When** log e gravado
**Then** `Fase-3_Interpretacao_Extracao/correction_log.json` contem:
```json
[
  {
    "item_id": "P1",
    "item_type": "pilar",
    "field": "h1_A",
    "detail_field_id": "p_sA_l1_h",
    "old_value": 244.0,
    "new_value": 250,
    "correction_type": "manual_validation",
    "obra": "Obra_TREINO_21",
    "pavimento": "12 PAV",
    "timestamp": "2026-05-18T14:30:00",
    "confidence_before": 0.75,
    "confidence_after": 1.0
  }
]
```

### AC4: Batch correction via CLI
**Given** correction_log.json tem 15 correcoes pendentes
**When** `python scripts/apply_correction.py --obra DADOS-OBRAS/Obra_TREINO_21 --from-log` e executado
**Then** todas as 15 correcoes sao aplicadas nos JSONs correspondentes
**And** backups criados para cada JSON modificado
**And** stdout mostra: "Aplicadas 15 correcoes: 10 pilares, 3 vigas, 2 lajes"

### AC5: Metricas de correcao
**Given** correction_log.json tem 50+ entradas
**When** `python scripts/apply_correction.py --obra DADOS-OBRAS/Obra_TREINO_21 --stats` e executado
**Then** mostra:
```
Metricas de Correcao — Obra_TREINO_21
=====================================
Total de correcoes: 53
Por tipo:
  Pilares: 35 (66%)
  Vigas:   12 (23%)
  Lajes:    6 (11%)

Campos mais corrigidos:
  h1_A:  8 correcoes (delta medio: +3.2)
  h2_A:  6 correcoes (delta medio: -1.8)
  larg1_B: 5 correcoes (delta medio: +2.0)
  panels[0].width: 4 correcoes (delta medio: +5.5)

Tendencia: motor_fase4.py subestima h1 em 60% dos casos
```

### AC6: Nao corrompe JSONs
**Given** JSON Fase-4 tem 50 campos
**And** correcao altera 1 campo
**When** correcao e aplicada
**Then** os 49 campos restantes permanecem identicos (bit-perfect)
**And** encoding UTF-8 preservado
**And** indentacao JSON preservada (indent=2)

### AC7: Idempotencia
**Given** mesma correcao ja foi aplicada
**When** CLI tenta aplicar novamente
**Then** pula a correcao com log: "SKIP: P1.h1_A ja tem valor 250"
**And** nao cria backup duplicado
**And** correction_log nao duplica entrada

### AC8: Correcao de viga e laje
**Given** viga V7 tem panel[0].width = 120 no Fase-4 e usuario corrigiu para 125
**When** correcao e aplicada via DetailCard
**Then** `JSON_Vigas_Laterais/V7_A.json` atualizado: `panels[0].width = 125`
**And** log registra com field = "panels[0].width"

**Given** laje L1 tem `comprimento = 500` e usuario corrigiu para 510
**When** correcao e aplicada
**Then** `JSON_Lajes/L1.json` atualizado: `comprimento = 510`

## Technical Notes

### Apply Correction Script

```python
def apply_correction(json_path: Path, field: str, new_value, create_backup=True):
    """Aplica correcao atômica em JSON Fase-4."""
    if create_backup:
        backup = json_path.with_suffix(f'.json.bak.{int(time.time())}')
        shutil.copy2(json_path, backup)
    
    data = json.loads(json_path.read_text(encoding='utf-8'))
    
    # Suportar nested fields: "panels[0].width"
    if '[' in field:
        # Parse array access
        parts = re.match(r'(\w+)\[(\d+)\]\.(\w+)', field)
        if parts:
            arr_name, idx, key = parts.groups()
            data[arr_name][int(idx)][key] = new_value
    else:
        data[field] = new_value
    
    json_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )
```

### Hook no DetailCard

No `on_validate()` do detail_card.py, apos salvar no DB, comparar com Fase-4:

```python
from src.core.field_mapping import map_detail_to_fase4

for field_id, value in validated_fields.items():
    fase4_key, _ = map_detail_to_fase4(field_id, value)
    if fase4_key:
        fase4_value = self._get_fase4_value(fase4_key)
        if fase4_value is not None and str(fase4_value) != str(value):
            # Divergencia detectada — oferecer realimentacao
            self._offer_correction(field_id, fase4_key, fase4_value, value)
```

## File List

| File | Action | Description |
|------|--------|-------------|
| `scripts/apply_correction.py` | CREATE | Correction application script |
| `src/core/services/correction_service.py` | CREATE | Correction logic for UI |
| `src/ui/widgets/detail_card.py` | MODIFY | Hook on validate to detect divergence |
| `src/ui/dialogs/correction_dialog.py` | CREATE | Dialog asking about feedback |
| `tests/test_apply_correction.py` | CREATE | Unit and integration tests |
| `tests/fixtures/fase4_correction/` | CREATE | Test fixtures |

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-18 | @pm | Story created |
