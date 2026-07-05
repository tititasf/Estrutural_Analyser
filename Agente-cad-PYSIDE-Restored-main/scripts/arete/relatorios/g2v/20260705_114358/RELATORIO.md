# RELATÓRIO — PIL 13_PAV G2-V

**Run:** 20260705_114358  
**Par:** N2 × N4 (`n2xn4`)  
**Backend:** CLI local; nenhuma API de visão usada.

## Resultado visual

- 35/35 itens inspecionados nos PNGs da ficha HTML.
- 33 PASS visual.
- 2 FAIL visual: P26 e P27.
- GRADES não apareceu nas subpartes CIMA+ABCD.
- Estado do gate: **FAIL aberto**. O G2 numérico 35/35 continua sendo apenas Nível 1 e não fecha Arete.

## Achados reais

### P26 e P27 — subtipo em L perdido

O card N2/HTML identifica ambos como `Formato em L`. O N4, porém, desenha CIMA retangular e somente ABCD; não materializa EFGH.

Evidência adicional no DB/ficha:

- campos `h*_E..H`, `larg*_E..H` e correlatos estão zerados;
- `reverse_eng_recortes` não possui coluna persistida de subtipo;
- o comparador G2 numérico não cobre subtipo/EFGH, por isso reportou PASS falso para estes dois itens.

Classificação: `schema_gap_subtipo_efgh`; direção `n4_a_menos`; suspeito principal `extrator_n2`; severidade alta.

## Lacuna do guia

`interpretacao_abcd.html` especifica ABCD, mas não define a extensão EFGH nem a fórmula de aceite para pilares em L. A extensão depende de decisão do dono. Nenhum motor/gerador foi alterado.

## Ajustes no harness

- resolvedor passou a encontrar fichas PIL nas subpastas `NASCE/SEGUE/MORRE/INDETERMINADO` e `pilares_especiais`;
- runs headless sem `arete_manifest.json` são ignorados para evitar ler arquivos concorrentes incompletos;
- no par `n2xn4`, a subvista GRADES é removida da captura transitória; no par `grades`, somente N4 GRADES é exibido.

Os HTMLs originais, incluindo `interpretacao_abcd.html`, não foram modificados.

## GRADES

Run separado: `20260705_115344`. Foram geradas 35 imagens N4 GRADES. Como o 13_PAV não possui recorte de grades, todas aguardam revisão Nível 3 do dono em `REVISAO-DONO-GRADES.md`.

## Regressão

Não executada: nenhum motor, gerador ou comparador canônico PIL foi alterado. Apenas o harness visual foi corrigido. A regressão nos 7 pavimentos torna-se obrigatória após eventual fix de P26/P27.
