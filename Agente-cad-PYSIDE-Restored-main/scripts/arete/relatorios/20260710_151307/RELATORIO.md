# ARETE — ajuste N1 de quatro lajes, 13_PAV

Data: 2026-07-10

## Escopo

Correção estrutural no `src/core/slab_tracer.py` para L303, L319, L327 e L331,
sem dados de N2/N4 como entrada do motor e sem alteração de JSONs Fase-4.

## Causas e correções

- L303: uma refinagem posterior reintroduzia um pequeno rasgo de vista/corte.
  A limpeza geométrica agora encerra o traçado completo.
- L319: uma linha de viga paralela era escolhida como o maior topo da extensão.
  O motor agora exige continuidade da face vertical e escolhe o topo conectado.
- L327: o eixo de apoio externo da ponta da fileira era transformado em rebaixo
  do contorno. Rebaixos externos agora exigem vizinho na mesma fileira.
- L331: a normalização de uma ponta truncada era centrada pelo texto. Agora ela
  ancora na célula precedente e no vão repetido da malha.

## Validação

- Compilação: `python -m py_compile src/core/slab_tracer.py` — PASS.
- Reprodução geométrica direta do DXF: os quatro contornos corrigidos — PASS.
- Headless canônico completo: `headless_sa_analise.py --obra Obra_TREINO_1 --pav 13_PAV --wait` — concluído em `20260710_150615`, DB somente leitura.
- Regressão dos quatro diagnósticos: PIL 24/22, FV 30/6, LAJ 1/30 e LV 18/18
  (aberto/não reproduzido), idêntica à rodada `20260710_145906`; nenhum alerta novo.
- N1-V CLI dos quatro itens: `g2v/20260710_151307/relatorio.json` preenchido.
  Contorno/área interna confirmados visualmente; veredito `SUSPEITO` porque o
  cartão N1 não contém as cotas, HLAZ e linhas de painel necessárias para PASS
  visual integral. Nenhum gate foi selado.

## Observação de teste legado

`tests/test_slab_tracer_overlap_guard.py` possui três falhas pré-existentes em
cenários de long strip/FV, fora dos métodos alterados nesta rodada. Elas não se
alteraram no escopo desta correção e requerem triagem separada.
