# Persistência transacional do headless SA

**Status:** ATIVO  
**Entrada única:** `scripts/arete/headless_sa_analise.py`

## Comandos

O padrão permanece somente leitura:

```powershell
python scripts/arete/headless_sa_analise.py --obra Obra_TREINO_1 --pav 13_PAV --wait
```

Para atualizar o banco:

```powershell
python scripts/arete/headless_sa_analise.py --obra Obra_TREINO_1 --pav 13_PAV --persist-db --wait
```

`--persist-db` exige execução completa, sem `--secao`, e os quatro diagnósticos
PIL/LAJ/FV/LV com status `ok`. O banco só é aberto para escrita depois desses
gates. PIL, LAJ e vigas são gravados em uma única transação `BEGIN IMMEDIATE`;
qualquer erro provoca rollback integral.

## Autoridade de validação

Pré-ficha e `preficha_reviewed` são triagem, não ground truth. Só são autoridade:

- `is_validated`;
- entrada em `validated_fields`;
- slot em `validated_link_classes`;
- vínculo com `validated=true`.

| Classe | Regra na reanálise |
|---|---|
| PIL | Campo validado preserva seu valor e vínculos; slots validados são preservados isoladamente. Todo restante é substituído pelo candidato novo. `pilar_segs` validado também preserva `points` e derivados geométricos. |
| LAJ | Mesma granularidade de PIL. `laje_outline_segs` validado preserva contorno/`points`; nível, dimensão, pilares, visão de corte e demais campos evoluem independentemente enquanto não validados. |
| FV | A primeira validação real de geometria de segmento congela o conjunto nos segmentos efetivamente validados. Não adiciona nem remove segmentos depois disso. A geometria validada permanece; campos internos ainda não validados são recalculados. Antes do diagnóstico/commit, todo contorno automático FV deve ser polígono explicitamente fechado e de área positiva; linha/parede e área zero abortam a transação. |
| LV A Para | Topologia congelada somente para este contrato. |
| LV B Para | Topologia congelada somente para este contrato. |
| LV A Passa | Topologia congelada somente para este contrato. |
| LV B Passa | Topologia congelada somente para este contrato. |

Um item integralmente validado é preservado por completo. Um item validado que
deixa de ser detectado permanece como órfão validado; itens órfãos sem validação
real são removidos.

## Rastreabilidade

Cada commit cria uma linha em `sa_persistence_runs` contendo:

- projeto e run;
- caminho do DXF e pack HTML;
- contagens antes/depois;
- itens com ground truth preservado;
- estado `COMMITTED`.

O pack HTML e os diagnósticos são produzidos a partir do mesmo snapshot mesclado
que será gravado. Assim, o gate não inspeciona dados diferentes dos persistidos.
