# STORY-EXEC-02 — Flag `--secao` no headless (gerar só uma classe)

**Pré-requisito:** leia `docs/HANDOFF-PRODUCAO-EXECUTOR.md` primeiro.

> ⚠️ **SESSÃO DEDICADA OBRIGATÓRIA.** Esta story edita
> `src/ui/widgets/pre_validation_dialog.py`, arquivo compartilhado por todas as classes.
> Antes de começar, o dono deve confirmar que NENHUMA outra sessão/chat está mexendo
> nesse arquivo. Se não houver essa confirmação explícita, não comece.

## Contexto

`headless_sa_analise.py --obra X --pav Y` gera fichas HTML de TODAS as classes
(pilares + lajes + fundos_viga), ~3min por rodada, mesmo quando só uma classe está em
loop. Gap de performance conhecido (procedimento geral §6, item 6). A geração das
seções acontece dentro de `_export_html_snapshot()` em
`src/ui/widgets/pre_validation_dialog.py` (~L5550), que hoje não recebe parâmetros.

## Leia antes (só isto)

1. `scripts/arete/headless_sa_analise.py` — função `main()` (~L781) e o ponto que chama
   `dlg._export_html_snapshot()` (~L437)
2. `src/ui/widgets/pre_validation_dialog.py` — só a função `_export_html_snapshot`
   (~L5550 em diante), onde a lista `reports` de seções é montada

## Mudanças (exatamente estas)

1. `_export_html_snapshot(self, sections: set[str] | None = None)`:
   - `None` (default) = comportamento IDÊNTICO ao atual (todas as seções). Quem chama
     sem argumento não percebe diferença nenhuma.
   - Com valor (subconjunto de `{'pilares', 'lajes', 'fundos_viga'}`): pular a montagem
     e a escrita das seções fora do conjunto.
2. `headless_sa_analise.py`: argumento `--secao` (repetível ou lista separada por
   vírgula; choices: `pilares`, `lajes`, `fundos_viga`), repassado ao
   `_export_html_snapshot`. Sem a flag = tudo, como hoje.
3. O pós-processamento de diagnóstico FV (`_run_fv_diagnostic_postprocess` /
   `_publish_arete_manifest`) só roda quando `fundos_viga` está incluída.

## PROIBIDO

- Alterar QUALQUER outra função de `pre_validation_dialog.py`.
- Mudar o formato/conteúdo das fichas geradas.
- "Aproveitar" para refatorar, renomear ou mover código.

## PASS da story

1. `--secao lajes` gera APENAS a pasta `lajes/` no run novo (provar com `ls`).
2. Rodada SEM flag: mesmo conjunto de pastas/arquivos de uma rodada de referência
   anterior (comparar listagem) — zero mudança de comportamento.
3. Testes existentes passam: `test_preficha_laje_html.py`, `test_preficha_fundo_html.py`.
4. Medir e reportar o tempo com/sem flag (a justificativa da story é performance).
