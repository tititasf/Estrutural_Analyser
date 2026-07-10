# Verificação FV N1×N2 — quantidade e medidas dos segmentos

**Data da verificação:** 2026-07-05
**Estado N1:** run `20260705_192302`
**Escopo:** Obra_TREINO_1 / 13_PAV / 26 fichas FV N2
**Tolerância por medida:** ±0,05 cm (0,10 cm reprova)
**Status:** NÃO CONVERGIU

## Resultado

| Gate | PASS | FAIL | Observação |
|---|---:|---:|---|
| Quantidade física de segmentos | 13 | 13 | 24 comparáveis + 2 itens sem N1 correspondente |
| Medidas individuais | 7 | 19 | PASS exige mesma quantidade e todas as medidas dentro da tolerância |
| Quantidade + medidas | 7 | 19 | Gate conjunto atual |

Itens que passam integralmente: `V305`, `V308`, `V312`, `V320`, `V321`, `V325`,
`V332`.

## Matriz por item

| Item | Qtd N1 | Qtd N2 | Qtd | Medidas | N1 (cm) | N2 (cm) |
|---|---:|---:|---|---|---|---|
| V301 | 2 | 16 | FAIL | FAIL | 1264; 1713,5 | 305,5; 100; 100; 318; 318; 100; 100; 318; 318; 100; 100; 318; 311,5; 106; 41,5; 247,5 |
| V302 | 3 | 6 | FAIL | FAIL | 375; 2522; 374 | 375; 387,5; 418; 735; 238,5; 97,5 |
| V303 | 6 | 5 | FAIL | FAIL | 1971; 387,5; 418; 418; 418; 418 | 192,5; 387,5; 418; 437; 437 |
| V304 | 3 | 3 | PASS | FAIL | 129; 286; 49 | 129; 578; 49 |
| V305 | 1 | 1 | PASS | PASS | 286 | 286 |
| V306 | 6 | 2 | FAIL | FAIL | 251,6; 413; 413; 413; 413; 415,5 | 254; 418 |
| V307 | 1 | 1 | PASS | FAIL | 30,71 | 255,7 |
| V308 | 2 | 2 | PASS | PASS | 253; 291 | 253; 291 |
| V309 | 2 | 1 | FAIL | FAIL | 320; 461 | 320 |
| V309A | — | 1 | FAIL | FAIL | — | 461 |
| V310 | 2 | 1 | FAIL | FAIL | 19; 152 | 152 |
| V311 | 1 | 1 | PASS | FAIL | 423 | 447 |
| V312 | 1 | 1 | PASS | PASS | 461 | 461 |
| V319 | 1 | 1 | PASS | FAIL | 313 | 351 |
| V320 | 2 | 2 | PASS | PASS | 120,5; 259,5 | 120,5; 259,5 |
| V321 | 1 | 1 | PASS | PASS | 398 | 398 |
| V322 | 3 | 2 | FAIL | FAIL | 49; 118; 262 | 118; 262 |
| V325 | 1 | 1 | PASS | PASS | 461 | 461 |
| V327 | 1 | 1 | PASS | FAIL | 160 | 260 |
| V329 | 1 | 1 | PASS | FAIL | 160 | 141 |
| V330 | 1 | 2 | FAIL | FAIL | 280 | 311; 183 |
| V331 | 2 | 1 | FAIL | FAIL | 19; 201 | 201 |
| V332 | 1 | 1 | PASS | PASS | 442 | 442 |
| VF202 | 6 | 1 | FAIL | FAIL | 251,6; 413; 413; 413; 413; 415,5 | 123,6 |
| VF203 | — | 3 | FAIL | FAIL | — | 161,8; 413; 415,5 |
| VF301 | 2 | 3 | FAIL | FAIL | 19,1; 61,9 | 405,5; 418; 405,5 |

## Padrões de causa para a próxima rodada

1. **Subsegmentação forte:** V301, V302, V330 e VF301.
2. **Agregação/contaminação:** V303 e V306 possuem trechos repetidos ou um contorno
   agregado que não pertence à decomposição N2.
3. **Alias/atribuição:** N1 agrega `V309A` dentro de `V309`; `VF202` recebeu o mesmo
   conjunto de comprimentos observado em V306; `VF203` não existe no N1.
4. **Quantidade correta, medida errada:** V304, V307, V311, V319, V327 e V329.
5. **Dimensão transversal capturada como comprimento:** candidatos V310 e V331
   apresentam segmento extra de aproximadamente 19 cm.
6. **Segmento residual:** V322 contém 49 cm adicionais antes dos dois segmentos que
   coincidem com o N2.

## Próximo gate técnico

Inspecionar, para cada grupo acima, os candidatos brutos em `bottom_runs` antes da
materialização de `segmentos.fundo`:

- se os candidatos corretos já existem, o fix pertence a `FundoVigaInterpreter`;
- se a geometria bruta está ausente ou atribuída à viga errada, o fix é de topologia
  compartilhada no `BeamTracer` e exige regressão completa das quatro classes;
- nenhum fix pode usar valores N2/N4 como entrada ou criar exceção por nome de viga.

O diagnóstico numérico continua subordinado ao N1-V obrigatório via backend CLI.

## Evidência

- `diagnostico_fv_n1_n2.json`
- `triagem_auto_fv.jsonl`
- `scripts/arete/diagnostico_fv_n1_n2.py`
