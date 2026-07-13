# LAJ — seleção local de contorno N2

## Objetivo

Corrigir o recorte N2 que absorvia malha de lajes/vigas vizinhas ao escolher
simplesmente as linhas mais longas do DXF.

## Regra implementada

`motor_reverso_laj.py` agora aceita a ilha estrutural local somente quando:

1. encontra o rótulo exato da laje no próprio recorte;
2. encontra um componente de linhas estruturais que contém esse rótulo;
3. a ilha é compacta (até 75% da área da malha global), evitando trocar uma
   borda já certificada por uma submalha;
4. o rótulo não está encostado na ponta horizontal da componente.

As bordas interrompidas por apoio só são completadas para ilhas estreitas. Sem
essas evidências, o caminho histórico continua inalterado.

## Prova de melhoria — 2_PAV, sem escrita no banco

Comparação geométrica apenas como diagnóstico N1×N2; N1 não alimentou a
extração N2. Erro médio relativo em comprimento, largura e área:

| Item | Erro anterior | Erro com ilha local | Resultado |
|---|---:|---:|---|
| L51 | 2.163 | 0.063 | melhora de 97.1% |
| L58 | 2.233 | 0.072 | melhora de 96.8% |
| L75 | 2.143 | 0.074 | melhora de 96.5% |

Dimensões N2 novas: L51 `395 × 66`, L58 `371 × 66`, L75 `233.74 × 71`.
Elas substituem os bboxes contaminados de `611 × 226`, `626.06 × 216.58` e
`394.5 × 179.39`, respectivamente. Ainda requerem veredito visual antes de
promover os três itens para PASS.

## Regressão

- `pytest tests/test_motor_reverso_laj_dynamic_layers.py tests/test_motor_reverso_laj_obstacles.py tests/test_diagnostico_laj_n1_n2.py -q`: **22 passed**.
- Novo teste sintético: rótulo local não absorve grade vizinha maior na mesma
  layer.
- Reextração em memória dos 31 recortes LAJ 13_PAV: **0** ativações da nova
  ramificação local; o golden certificado não foi regravado.
- `gerar_status.py` executado após a verificação.

## Limite deliberado

Os três itens de 2_PAV continuam `SUSPEITO` até regeneração controlada e leitura
visual G2-V. Nenhum JSON Fase-4, DXF de obra ou registro N2 existente foi
alterado nesta rodada.
