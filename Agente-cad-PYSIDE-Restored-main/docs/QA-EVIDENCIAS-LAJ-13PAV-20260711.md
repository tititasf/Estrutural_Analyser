# QA de Evidências — LAJ 13_PAV — 2026-07-11

## Resultado

- Projeto: `dd238e47-1dc6-4f63-a760-4e7ce19a7386` (`Obra_TREINO_1`, `13_PAV`).
- Banco: `31/31` lajes com selo azul.
- Piloto aplicado: `L319` a `L331`, com snapshot e rollback transacional.
- Veredito visual obrigatório: `13/13 PASS` pelo `g2v_harness --backend cli`.
- Testes automatizados: `10/10 PASS`.
- Gate global desta entrega: **CONCERNS**, porque dúvidas históricas foram
  corretamente preservadas para decisão humana.

## Execuções auditáveis

- Aplicação: `scripts/arete/relatorios/qa_evidencias/20260711_laj_remaining_apply_candidate/`
- Pós-auditoria: `scripts/arete/relatorios/qa_evidencias/20260711_laj_all_postfix_audit/`
- G2-V: `scripts/arete/relatorios/qa_evidencias/20260711_laj_remaining_apply_candidate/g2v/relatorio.json`

O rollback do lote aplicado está em `rollback.jsonl` dentro da execução de
aplicação e exige o mesmo `project_id`.

## Dúvidas que o agente não deve decidir sozinho

1. `L303`: campo `845.19`; root e rótulo `852.19`.
2. `L314`: campo `852.12`; root `852.19`, sem rótulo independente conclusivo.
3. `L306`, `L313` e `L315`: níveis de vizinhança dependem da decisão de `L314`.
4. `L318`: campo `822.19`; root e rótulo `852.19`.

O agente bloqueia propagação horizontal de um nível selado ambíguo. Quando root
e rótulo independentes concordam, esse valor pode limpar uma dimensão obviamente
contaminante de um vizinho, mas não corrige o próprio campo sem o dono.

## Achados legados preservados

A pós-auditoria encontrou 15 achados: dimensões usadas como níveis vizinhos e
apoios de pilar antigos sem contato/face completa. Como pertencem a itens já
selados, foram relatados, não removidos automaticamente.

## Headless canônico

Uma execução direcionada percorreu análise, merge e exportou os 13 HTMLs, porém
falhou depois da exportação por `manifest_path` durante uma alteração concorrente
do script. Duas novas tentativas respeitaram `--wait`, mas outro processo
`--persist-db` reteve o lock. Portanto não há falso PASS: o headless direcionado
fica pendente de uma janela sem concorrência.

## Próximo gate

1. O dono responde os níveis de `L303`, `L314` e `L318`.
2. Reexecutar auditoria read-only e aplicar somente as decisões resultantes.
3. Repetir o headless direcionado com `--wait` sem outro persistente concorrente.
4. Promover o corpus LAJ ao RAG somente após essas respostas e nova auditoria.
