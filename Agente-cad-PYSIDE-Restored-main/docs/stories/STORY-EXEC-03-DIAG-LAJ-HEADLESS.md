# STORY-EXEC-03 — Integrar diagnósticos automáticos LAJ/LV/PIL ao headless (como FV já está)

**Pré-requisito:** leia `docs/HANDOFF-PRODUCAO-EXECUTOR.md` primeiro.
Risco baixo-médio: edita SÓ `scripts/arete/headless_sa_analise.py` (harness, não UI).

## Contexto

Os 4 diagnósticos numéricos N1×N2 **já existem** como scripts headless:
`scripts/arete/diagnostico_{pil,fv,lv,laj}_n1_n2.py` + `diagnostico_common.py`
(todos com `run_diagnostic(obra, pavimento, state_path, db_path)`, saída versionada
por run e formato v2 com `marcado_por: "auto"`, `confianca`, `evidencia`).

O gap: `headless_sa_analise.py` só dispara o de **FV** após gerar as fichas
(`_run_fv_diagnostic_postprocess`, ~L457) e só injeta o bloco de diagnóstico nas
páginas de `fundos_viga/` (`_publish_arete_manifest`, ~L507). LAJ, LV e PIL precisam
ser rodados à mão e não aparecem nas fichas.

## Leia antes (só isto)

1. `scripts/arete/headless_sa_analise.py` — `_run_fv_diagnostic_postprocess`,
   `_publish_arete_manifest` e o ponto do `main()` que os chama
2. `scripts/arete/diagnostico_laj_n1_n2.py` — docstring (explica o formato e a
   limitação conhecida de `causa_raiz` genérica em LAJ)

## Entrega

Generalizar o pós-processo em `headless_sa_analise.py`:

1. Uma tabela `{'pilares': diagnostico_pil, 'lajes': diagnostico_laj,
   'fundos_viga': diagnostico_fv, ...}` (LV: confirmar qual seção usa antes —
   se a seção LV não existir no run, pular sem erro).
2. Após gerar os HTMLs, rodar o `run_diagnostic` de CADA classe presente no run,
   no mesmo padrão tolerante a falha do FV (erro em um diagnóstico NÃO derruba a
   geração — só imprime aviso, igual `_run_fv_diagnostic_postprocess` faz hoje).
3. Injetar o bloco de diagnóstico nas páginas de cada seção (mesmo mecanismo
   `_inject_arete_block` / manifesto), não só em `fundos_viga/`.
4. O manifesto `arete_manifest.json` passa a listar os diagnósticos de todas as
   classes rodadas.

## PROIBIDO

- Editar os scripts `diagnostico_*` (eles já funcionam — se algum falhar, reportar,
  não consertar nesta story).
- Editar `pre_validation_dialog.py` ou qualquer arquivo de UI.
- Mudar o conteúdo/estilo das fichas além do bloco injetado (que já existe para FV).

## PASS da story

1. `headless_sa_analise.py --obra Obra_TREINO_1 --pav 13_PAV` roda os 4 diagnósticos
   (ou os que tiverem seção no run) e imprime o resumo de cada um.
2. Página de uma laje (ex.: `lajes/L318.html`) contém o bloco
   "Diagnóstico automático N1×N2" — igual ao que já aparece em `fundos_viga/`.
3. `arete_manifest.json` lista os diagnósticos de todas as classes do run.
4. Falha simulada de um diagnóstico (ex.: DB path errado) NÃO impede a geração das
   fichas (comportamento tolerante preservado).
