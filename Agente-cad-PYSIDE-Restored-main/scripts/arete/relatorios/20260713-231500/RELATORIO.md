# Ciclo LV — folga direita de cotas

Data: 2026-07-13

## Alteração

Na partição dinâmica de múltiplas Laterais de Viga por folha, a folga direita
após a fronteira entre rótulos passou de `65.0` para `125.0` unidades CAD.
Isso acrescenta exatamente 60 unidades para preservar a última cota/linha na
direita sem remover a separação geométrica entre itens.

## Validação

- `tests/test_recorte_motor_lv_partition.py`: `2 passed`.
- `python -m py_compile src/core/recorte_motor.py`: PASS.
- Extração seca da folha 14_PAV LV:
  - V415: borda direita calculada em `8483.7`;
  - V416: borda direita calculada em `9306.0`;
  - VF401/VF402 continuam separados verticalmente, sem expansão em Y.

Nenhum DXF de produção, recorte humano ou registro do banco foi alterado.
