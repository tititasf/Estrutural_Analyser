# Campanha LAJ multi-pavimento — Obra_TREINO_1

Data: 2026-07-14

## Escopo e integridade

- Execução exclusiva por `scripts/arete/headless_sa_analise.py --wait`, sem
  `--persist-db`; nenhum selo, ficha N1, N2 ou JSON Fase-4 foi alterado.
- PIL/FV/LV foram apenas contexto que o caminho canônico exige.
- O 13_PAV é regressão de controle; N2/N4 não foram usados como entrada do
  SlabTracer.

## Baselines executados

| Fonte | Resultado N1 | Diagnóstico inicial | Leitura correta |
|---|---:|---|---|
| FUNDACAO | 1 LAJ | 1 indeterminado | Não há ficha N2 LAJ correspondente. |
| TERREO | 25 LAJ | 22 RUIM, 3 indeterminado | 22 recortes humanos aprovados, porém campos N2 ainda `draft`. |
| 1_PAV | bloqueado | — | `projects.dxf_path` aponta para `torre_1.dxf` ausente; existe fonte bruta/detalhes, sem troca automática do dado de produção. |
| 2_PAV | 30 LAJ | 30 RUIM | Todos os recortes humanos correspondentes estão aprovados; campos da ficha N2 permanecem `draft`. |
| TIPO | 30 LAJ | 30 indeterminado | N2 está indexado como `12_PAV`, enquanto a fonte do projeto é `TIPO`; é falha de identidade, não do contorno N1. |
| 14_PAV | 23 LAJ | 22 RUIM | 22 recortes humanos aprovados, com campos N2 `draft`. |
| COBERTURA | 41 LAJ | 27 RUIM, 11 indeterminado, 2 excelente | Há 29 N2; os RUIM apontavam para campos locais N2 ainda `draft`. |
| ATICO | 5 LAJ | 5 indeterminado | Não há N2 LAJ para o ático. |

## Causa comprovada e correção aplicada

O comparador usava diretamente `reverse_eng_fichas.campos_json`. Para os
pavimentos acima, esses campos mantêm retângulos locais/dimensões técnicas de
extrações anteriores, mesmo quando o DXF do recorte em
`reverse_eng_recortes` já está `aprovado` por humano. Isso produzia uma onda de
falsos `n1_contorno_divergente` e levaria a um ajuste indevido do motor N1.

`diagnostico_laj_n1_n2.py` agora prova essa proveniência por
`obra + classe + projeto + elemento`. Quando há recorte humano aprovado e ficha
geométrica N2 `draft`, classifica o achado como
`n2_ficha_geometria_desatualizada`: o próximo passo é materializar/revalidar os
campos N2 a partir do recorte, **nunca copiar N2 para N1**.

Após a correção, os 22/30/22/27 casos de TERREO/2_PAV/14_PAV/COBERTURA foram
reclassificados para essa causa, preservando os `schema_gap` verdadeiros e os
2 excelentes da cobertura.

## Regressão 13_PAV

Rodada canônica parcial `L318 L319`, read-only:

- L318: `EXCELENTE`, IoU `0.9999828409` — preservado.
- L319: passou de falso `n1_contorno_divergente` para
  `n2_ficha_geometria_desatualizada`; o recorte humano segue a autoridade
  visual e não houve alteração N1.

## Testes

- `tests/test_diagnostico_laj_n1_n2.py`: **8 passed**.
- O conjunto adicional do `SlabTracer` expôs uma falha pré-existente em
  `test_unclassified_dimension_crossing_does_not_split_slab_face` (4000 em vez
  de 8000), sem alteração de `slab_tracer.py` nesta campanha. Deve ser tratado
  em microciclo próprio, com causa visual e regressão 13_PAV.

## Próximas ações seguras

1. Atualizar/materializar campos N2 somente a partir dos recortes humanos
   aprovados, preservando o histórico append-only.
2. Corrigir o mapeamento de fonte `TIPO` ↔ grupo humano `3º–12º` sem hardcode
   de item, e reparar a origem ausente de 1_PAV por decisão explícita de dados.
3. Só então usar N1×N2 numérico como triagem de motor para os demais
   pavimentos; cada alteração em `slab_tracer.py` exige microciclo e regressão
   visual do 13_PAV.
