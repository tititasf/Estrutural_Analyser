# Microciclo PIL P35 — N1 → N3 PARA/PASSA

## Escopo

- Obra: `Obra_TREINO_1`
- Pavimento: `13_PAV`
- Item: `P35`
- Rota: interpretação N1 granular, persistência no DB real e geração N3 das variantes `PARA` e `PASSA`

## Causa e correção

O vínculo topológico canônico já identificava a viga `V308 19/55` nas faces A/B,
mas a adaptação N3 usava a lista genérica de vigas passantes e não consumia a
classificação `behavior=para` nem o canto consolidado em `face_beams`.

A correção geral:

- preserva a viga na categoria N1 `passa`;
- expõe separadamente a categoria de comportamento `param` para o modo PARA;
- resolve AC/AD/BC/BD primeiro pelo vínculo canônico de fundo de viga;
- mantém o fallback geométrico para snapshots legados.

## Evidências verificadas

- Headless canônico com `--wait` e commit: `40,63 s`.
- P35 persistido:
  - A: `V308 19/55`;
  - B: `V308 19/55`;
  - C: chegada `V308 19/55`;
  - D: passagem `V328 19/55`;
  - nenhuma ocorrência de `V327` nos campos da face D.
- Oito campos nome/dim possuem `evidence_source=beam_bottom_geometry` e quatro
  segmentos geométricos por vínculo.
- N3 PARA:
  - `abertura_A_1`: AC, V308, `11 x 59`;
  - `abertura_B_1`: BC, V308, `11 x 59`.
- N3 PASSA:
  - `abertura_A_1`: AC, V308, `11 x 59`;
  - `abertura_B_1`: BC, V308, `11 x 59`.
- HTML descreve explicitamente:
  - AC: `Ini 7,5 x 59 / Nova 11 x 59`;
  - BC: `Ini 7,5 x 59 / Nova 11 x 59`.
- Smoke estrutural N3: `PASS` nas duas variantes, 10/10 checks.
- Regressão focada: `65 passed`.

## Autoridade e pendência

O grafo fonte → vínculo N1 → contrato → payload → DXF → HTML está confirmado
numericamente e por proveniência. Isto não substitui veredito visual humano/G2-V.
A próxima ação é a conferência humana do desenho PARA/PASSA na ficha P35; nenhum
golden foi selado nesta rodada.
