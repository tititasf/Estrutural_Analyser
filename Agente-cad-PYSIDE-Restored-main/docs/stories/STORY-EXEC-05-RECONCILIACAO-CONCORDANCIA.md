# STORY-EXEC-05 — Reconciliar diagnósticos auto de PIL/FV/LV + rollup de concordância

**Pré-requisito:** leia `docs/HANDOFF-PRODUCAO-EXECUTOR.md` primeiro. Escopo = SÓ esta story.
Risco baixo: leitura + escrita de logs/relatórios; NÃO toca motor, gerador nem UI.

## Contexto

Os diagnósticos automáticos N1×N2 já rodaram para as 4 classes, mas só LAJ teve os
alertas **cruzados contra o estado real/revisão humana** (reconciliação feita em 03/07
por outra sessão — resultado: 14 alertas já estavam resolvidos sem ninguém confirmar,
2 genuinamente quebrados). PIL (~24 alertas), FV (~34) e LV (~20) estão com alerta
rodado e **nunca cruzado** — provável mesmo padrão: maioria já resolvida, poucos reais.

Sem esse cruzamento, os números de alerta mentem para cima e a métrica de concordância
(§4.2 do procedimento geral) — critério objetivo para autonomia futura — não tem dado.

## Leia antes (só isto)

1. `docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md` §4 (schema do log, regra de precedência
   humano>auto) e §4.2 (métrica de concordância) + item 2 do checklist §6 (como a
   reconciliação de LAJ foi feita — seguir o mesmo padrão)
2. Os logs auto existentes: `scripts/arete/relatorios/triagem_erros/triagem_auto_{pil,fv,lv}.jsonl`
   (nomes/paths podem variar — conferir no diretório, não assumir)
3. O log humano de cada classe, se existir no mesmo diretório

## Entrega (por classe: PIL, FV, LV)

1. Para cada alerta auto: verificar contra o estado ATUAL (regenerar/reler a evidência,
   ou conferir se um fix posterior já resolveu — ver relatórios Arete recentes e git log
   dos motores). Classificar: `resolvido` (fix já aplicado, confirmar e fechar com
   `fix_aplicado`/`verificado_em`), `aberto real` (problema confirmado), ou
   `falso_positivo` (diagnóstico auto errado — registrar, é dado da métrica).
2. Onde existir marcação humana do mesmo item: preencher `concordancia`
   ("concorda"/"diverge") nos DOIS registros, sem apagar nada (append/atualização de
   campos novos apenas, nunca reescrever histórico).
3. **Rollup:** criar `scripts/arete/triagem_concordancia.py` (item 4 do checklist §6):
   lê todos os JSONL de triagem e imprime/salva por classe e por `causa_raiz`:
   nº auto, nº com par humano, taxa de concordância, nº abertos reais.
4. Resumo final em `scripts/arete/relatorios/triagem_erros/RECONCILIACAO-{data}.md`:
   tabela por classe (alertas → resolvidos / reais / falsos positivos) + saída do rollup.

## PROIBIDO

- Corrigir os "abertos reais" encontrados — esta story só TRIA; cada aberto real vira
  candidato a story própria (listar no resumo com evidência).
- Tocar em motor/gerador/UI; inventar slug de `causa_raiz` novo se já existe equivalente.
- Apagar ou reescrever entradas existentes dos logs (append-only; só preencher campos
  de fechamento/concordância conforme §4).

## PASS da story

1. 100% dos alertas auto de PIL, FV e LV classificados (resolvido/real/falso positivo).
2. `triagem_concordancia.py` roda e imprime as taxas por classe/causa.
3. `RECONCILIACAO-{data}.md` escrito com a tabela e a lista de abertos reais.
4. `python scripts/arete/gerar_status.py` rodado ao final.
