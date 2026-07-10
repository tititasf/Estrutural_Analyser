# Relatorio Arete - LAJ 13_PAV - L319 cotas e paginacao

Data: 2026-07-07

## Escopo

- Classe: LAJ
- Pavimento: 13_PAV
- Item focado: L319
- Contexto: dono aprovou L318 visualmente, mas apontou em L319 excesso de cotas e falta de preferencia pela media dos paineis.

## Resultado

- L319 nao foi selado como PASS visual.
- G2-V atualizado como `SUSPEITO` em `scripts/arete/relatorios/g2v/20260707_015247/relatorio.json`.
- Triagem append-only registrada em `scripts/arete/relatorios/triagem_erros/Obra_TREINO_1_13_PAV_lajes.jsonl`.

## Correcao aplicada

- Em poligonos de laje com aresta diagonal, o gerador nao cria familias repetidas de cotas verticais secundarias.
- Em poligonos diagonais, o gerador cota a aresta diagonal de recorte e evita cotar todas as arestas locais horizontais/verticais como se fossem recortes independentes.
- Efeito observado em L319: reducao de 24 para 11 entidades `DIMENSION`, mantendo a cota diagonal do chanfro.

## Pendencia mantida

A preferencia de paginacao media no eixo Y foi testada, mas foi revertida porque altera `linhas_horizontais` contra a ficha N2/Fase-4 oficial:

- Fonte oficial atual: `179.0 / 331.1 / 423.0 / 505.0`
- Distribuicao desejada testada: `122 / 244 / 366 / 488`

Como JSONs Fase-4 sao intocaveis, forcar isso no gerador faria G1 falhar e mascararia a fonte oficial. A solucao correta e reextracao/reselo da ficha N2 antes de mudar essa paginacao como verdade.

## Validacoes executadas

- `python -m pytest tests\test_laj_visual_reference_contract.py tests\test_motor_reverso_laj_dynamic_layers.py tests\test_smart_panner_general_rules.py -q --basetemp .pytest-tmp-laj-l319-cotas` -> 22 passed.
- `python -m py_compile scripts\gerar_lj_dxf_stog.py scripts\motor_reverso_laj.py` -> OK.
- `python scripts\arete\arete_runner.py --classe LAJ --pav 13_PAV --item L319` -> G1/G2 PASS numerico.
- `python scripts\arete\arete_runner.py --classe LAJ --pav 13_PAV` -> 31P / 0F / 0B, relatorio `scripts/arete/relatorios/20260707_015724/RELATORIO.md`.
- `python scripts\arete\g2v_harness.py --classe LAJ --pav 13_PAV --par n2xn4 --backend cli --item L319` -> veredito manual `SUSPEITO`.
- `python scripts\arete\gerar_status.py` -> `docs/STATUS.md` atualizado.

## Veredito de engenharia

L318 permanece como referencia visual boa. L319 melhorou no problema de cotagem excessiva, mas ainda nao cumpre PASS visual porque a paginacao/gestalt do eixo Y depende da fonte N2 oficial antiga.
