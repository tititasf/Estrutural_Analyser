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

Sem recorte, `--persist-db` exige execução completa e os quatro diagnósticos
PIL/LAJ/FV/LV com status `ok`. Já um microciclo com exatamente uma `--secao` e
`--item` pode usar `--persist-db`: exige o diagnóstico dessa seção e grava somente
o lote solicitado por upsert (`delete_missing=False`). Os dois modos abrem o banco só
depois dos respectivos gates. Cada commit usa uma transação `BEGIN IMMEDIATE`; qualquer
erro provoca rollback integral.

O microciclo persistente mantém a fila de sua classe (`headless_sa_laj`, por exemplo),
não o lock global. LAJ grava apenas `slabs` e pode avançar em paralelo com outra classe.
PIL, FV e LV, além de suas filas, reservam `headless_sa_beams` durante a análise porque
podem gravar o mesmo `beams.data_json`; `headless_sa_db_commit` é adquirido apenas no
trecho curto de `BEGIN/COMMIT` SQLite. A rodada sem item/multiclasse segue global para
proteger o snapshot integral.

### Fast path modular de LAJ

O único entry point continua sendo `scripts/arete/headless_sa_analise.py --wait`.
"Modular" não significa criar um segundo headless nem uma rota alternativa de dados:
um microciclo `--secao lajes --item ...` seleciona o fast path LAJ **dentro** do
mesmo executor canônico. Ele materializa o `SlabTracer` e o contexto efetivamente
consumido (pilares, níveis e vigas), aplica o mesmo filtro granular, gera a mesma
ficha/diagnóstico e persiste pelo mesmo upsert parcial. A diferença é exclusivamente
operacional: não instancia `MainWindow` nem sincroniza a UI; widgets offscreen
estritamente necessários ao pacote canônico podem existir sem abrir a aplicação.

O cache continua content-addressed pelas entradas e motores consumidos. Logo, um
microciclo LAJ não disputa a fila de PIL/FV/LV, mas uma alteração em dependência
cross-classe ou no próprio motor LAJ invalida a entrada correta. Qualquer execução
multiclasse, sem `--secao`, ou persistente sem identidade de item permanece global e
exclusiva para preservar a integridade do snapshot.

## Leitura da fila e conflito legítimo

Os arquivos `.headless_sa_*.lock` são telemetria, não uma fila baseada em
arquivo-PID: a autoridade é a trava exclusiva mantida pelo SO. Por isso um
arquivo com `event=released` é histórico normal e **não** deve ser apagado.
O comando com `--wait` informa o recurso exato ocupado e aguarda sem encerrar
o dono. Durante a rodada, a telemetria da trava mostra a etapa real
(`análise N1`, `exportação`, `diagnósticos`, `commit` ou `prévias N3`), renovada
por heartbeat; não existe TTL que solte uma análise ainda viva nem uma espera
baseada em arquivo histórico.

| Pedido novo | Pode coexistir com | Deve aguardar |
|---|---|---|
| `--secao lajes` read-only ou item persistente | PIL, FV e LV; o commit só aguarda o curto `headless_sa_db_commit` | outro LAJ; rodada global |
| `--secao fundos_viga` read-only | PIL, LAJ e LV read-only | outro FV; rodada global |
| FV com `--persist-db --item` | LAJ | outro FV, PIL ou LV persistente, pois todos reservam `headless_sa_beams`; rodada global |
| PIL/LV com `--persist-db --item` | LAJ | qualquer outro writer de `beams.data_json`; rodada global |
| sem `--secao`, múltiplas seções ou persistência sem identidade | nenhum microciclo | todas as filas de classe e recurso |

Assim, a regra é granular por dono de dados, e não apenas pelo nome da
classe: PIL/FV/LV são interpretadores separados, mas seu commit compartilha
o snapshot inteiro `beams.data_json`; LAJ não o compartilha. A separação
preserva paralelismo sem permitir que um snapshot antigo sobrescreva o outro.

### Comando modular canônico por classe

Continua existindo **um único entry point**, para que todas as classes usem o
mesmo contrato, logs, diagnósticos e `--wait`. A granularidade vem de
`--secao` e `--item`, não de CLIs paralelas ou atalhos de dados:

| Dono N1 | Investigação/read-only | Upsert parcial seguro | Fila durante a análise |
|---|---|---|---|
| PIL | `--secao pilares --item Pxxx --wait` | mesmo comando + `--persist-db` | `headless_sa_pil` + `headless_sa_beams` ao persistir |
| LAJ | `--secao lajes --item Lxxx --wait` | mesmo comando + `--persist-db` | `headless_sa_laj`; commit SQLite apenas no final |
| FV | `--secao fundos_viga --item Vxxx --wait` | mesmo comando + `--persist-db` | `headless_sa_fv` + `headless_sa_beams` ao persistir |
| LV | `--secao laterais_viga --item Vxxx --wait` | mesmo comando + `--persist-db` | `headless_sa_lv` + `headless_sa_beams` ao persistir |

Sem `--persist-db`, os quatro são leitura e podem coexistir se as filas de
classe forem distintas. O fast path é uma otimização interna dos quatro donos:
PIL/LAJ/FV/LV. LV continua materializando o contrato próprio A/B + PARA/PASSA
depois do snapshot canônico; portanto o ganho de bootstrap não autoriza
reutilizar semântica de faces ou fundos. Continua existindo um único entry
point, sem uma segunda CLI e sem misturar interpretadores.

### Auditoria reproduzível de concorrência (2026-07-16)

Foi observado um job vivo de leitura `--secao laterais_viga --wait` no
13_PAV. Ele detinha somente `headless_sa_lv`. Durante a execução, um
microciclo FV read-only (`--secao fundos_viga --item V305 --wait`) adquiriu
somente `headless_sa_fv`, finalizou em 19,63 s e declarou `DB: READ_ONLY`.
Logo, a fila estava concorrente, mas não em conflito. O teste de regressão
`test_fv_and_lv_readonly_are_independent_class_queues` fixa este contrato.

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
