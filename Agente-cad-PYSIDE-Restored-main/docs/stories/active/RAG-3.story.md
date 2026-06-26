# RAG-3 - Validacao Humana Event-Driven

## Objetivo

Conectar o ato humano de validar/desvalidar ao ciclo RAG sem indexacao em massa.

## Escopo

- Diagnostic Reverse Hub: aprovar recorte humano registra evento RAG e, se a F5 ja existir, promove a ficha para T1.
- Comparison Engine: marcar/desmarcar "Validado Humano" registra evento em `training_events`.
- Desvalidacao humana cria tombstone TX para remover o item das consultas futuras sem apagar historico.

## Politica

- Validar humano = pode promover para T1 e indexar somente aquele item, se existir.
- Desvalidar humano = TX/tombstone. Nao limpar silenciosamente. Nao sobrescrever com novo dado sem manter lineage.
- Novo dado validado depois entra como novo `source_id` e pode apontar para o antigo via `superseded_by_id` em evolucao futura.

## Fora de Escopo

- Nao indexar T0.
- Nao treinar transformation_rules automaticamente.
- Nao alterar geometria N3 com dado N2/N4.

## Gate

- Aprovar recorte chama hook RAG sem quebrar fluxo existente.
- Desmarcar validacao humana no Comparison Engine grava evento de revogacao/tombstone.
- Testes focados passam.
