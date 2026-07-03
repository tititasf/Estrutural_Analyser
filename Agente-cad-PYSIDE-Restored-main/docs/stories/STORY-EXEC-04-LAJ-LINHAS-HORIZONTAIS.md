# STORY-EXEC-04 — LAJ 13_PAV: round-trip de `linhas_horizontais` quebrado (23 itens FAIL)

**Pré-requisito:** leia `docs/HANDOFF-PRODUCAO-EXECUTOR.md` primeiro. Escopo = SÓ esta story.

> ⚠️ **COORDENAÇÃO:** o motor LAJ recebeu trabalho pesado em 01-02/07 (commits
> `d9982b355`, `a1b95f8eb`) e há triagem N1 de lajes em curso (17 achados no JSONL).
> Antes de começar, o dono confirma que nenhuma outra sessão está mexendo em
> `motor_reverso_laj.py` / `gerar_lj_dxf_stog.py`.

## Contexto (descoberto na regressão de 03/07/2026, run `20260703_102513`)

LAJ 13_PAV estava 31/31 (golden 24/06). A regressão de 03/07 deu **8/31**, com
**23 FAILs de UMA causa**: G1 round-trip do campo `linhas_horizontais`.

Evidência medida (L301): N2 extraído do recorte tem `linhas_horizontais` com **2 itens**;
N2′ re-extraído do N4 tem **0**. Ou seja: ou o gerador não desenha as linhas, ou os
filtros novos do motor (`_filter_internal_lines` ~L1114-1115,
`_fill_oversized_panel_spans` ~L1187-1192, filtro de proximidade de borda
`min(v, larg-v) >= 30` ~L1131-1134 em `motor_reverso_laj.py`) as eliminam quando a
fonte é o N4 — instabilidade de round-trip introduzida pelas mudanças de 01-02/07
(a mesma família de mudanças que causou o caso FV `SARR_5cm`, já corrigido).

Nota de exibição: o RELATORIO.md mostra "N2=None N2′=None [list_len]" — o diff real
está em `n2_len`/`n2p_len` no relatorio.json (bug menor de formatação do MD; pode
corrigir de passagem em `arete_runner.py` se for trivial, senão ignorar).

## Leia antes (só isto)

1. `scripts/arete/relatorios/20260703_102513/RELATORIO.md` — os 23 FAILs
2. `scripts/motor_reverso_laj.py` ~L1090-1205 — os filtros novos
3. `scripts/gerar_lj_dxf_stog.py` — onde `linhas_horizontais` vira desenho (~L659, 719, 934, 981, 1112)

## Arquivos que PODE tocar (conforme a causa comprovada)

- `scripts/motor_reverso_laj.py` · `scripts/gerar_lj_dxf_stog.py` · `scripts/arete/`

## PROIBIDO

- Hardcode por item; relaxar tolerância do G1 para "passar"; adicionar
  `linhas_horizontais` ao skip do round-trip sem prova de que o campo é
  não-round-trippável por natureza (não parece ser — era estável até 24/06).
- Tocar em outras classes, UI, ou nos 17 achados N1 da triagem de lajes (outro fio).

## Passos

1. Reproduzir em 1 item: round-trip do L301 (`roundtrip_ficha.roundtrip_item('LAJ','L301')`).
2. Determinar de onde vêm os 2 itens no N2 e por que somem no N2′: o gerador desenha
   as linhas? (abrir o N4 DXF com ezdxf e procurar as entidades). Se desenha, qual
   filtro do motor as descarta na re-extração? Se não desenha, por quê?
3. Fix por fórmula geral no lado comprovadamente errado (gerador OU motor) — round-trip
   deve ser estável: extrair → gerar → re-extrair = mesmo conteúdo.
4. Rerodar LAJ 13_PAV → meta 31/31. Regressão: FV 26/26 e PIL 35/35 devem se manter.
5. Golden re-selado, entrada no JSONL de lajes (`fix_aplicado`/`status`),
   `python scripts/arete/gerar_status.py`.

## PASS da story

- LAJ 13_PAV = 31/31 PASS; FV e PIL 13_PAV sem regressão.
- `docs/STATUS.md` regenerado sem o FAIL de LAJ.
- Relatório final: causa nomeada (gerador vs motor) + arquivo/linhas + comandos de prova.
