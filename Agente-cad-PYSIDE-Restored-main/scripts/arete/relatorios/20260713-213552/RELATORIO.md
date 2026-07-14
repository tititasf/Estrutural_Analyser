# Microciclo — recortes LV com múltiplos itens por folha

Data: 2026-07-13

## Causa comprovada

A descoberta já produzia caixas distintas para os itens da mesma folha, porém
`RecorteMotor._collect_in_bboxes()` mantinha LINE/LWPOLYLINE completas quando apenas
uma extremidade ou vértice entrava na caixa. A segunda passagem de refinamento LV
voltava a expandir a coleta. Hachuras eram selecionadas somente pelo centro e também
podiam atravessar o divisor.

Evidência anterior no 14º pavimento:

- V416: caixa de busca começava em `x=8358.70`, mas o recorte final começava em
  `x=8002.67`, dentro do item V415.
- A descoberta de V415/V416 e VF401/VF402 já era distinta; a contaminação acontecia
  na coleta/salvamento das entidades.

## Correção universal

- Marcação explícita das caixas LV que são partições de frame compartilhado.
- Clipping de LINE, LWPOLYLINE e contornos HATCH na caixa do item.
- Segunda passagem expansiva desativada somente para LV particionada.
- Fronteira horizontal calculada pelos anchors vizinhos, mantendo a folga direita
  solicitada sem reincorporar as cotas do item anterior.
- Zona neutra proporcional para itens empilhados, removendo títulos/linhas do vizinho.
- Frames com um único item continuam no comportamento anterior.
- Nenhum recorte aprovado humano e nenhum registro do banco de produção foi alterado.

## Validação

- `python -m py_compile src/core/recorte_motor.py`: PASS.
- `pytest tests/test_recorte_motor_lv_partition.py -q`: `2 passed`.
- Auditoria seca dos 23 itens particionados do DXF LV do 14º pavimento: zero ponto de
  LINE/LWPOLYLINE/HATCH/TEXT fora da caixa atribuída.
- Leitura visual dos pares V415/V416 (lado a lado) e VF401/VF402 (empilhados): cada
  recorte contém somente suas seções A/B, corte, cotas e apoios; não há cópia integral
  do vizinho nem faixa de título da outra metade.

Artefatos temporários de inspeção:
`scripts/arete/tmp/lv_partition_final2/`.

