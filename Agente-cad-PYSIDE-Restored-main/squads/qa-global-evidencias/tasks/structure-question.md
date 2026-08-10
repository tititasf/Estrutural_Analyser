---
task: structure-question
agent: aegis
inputs: [scope.json, unresolved_impasse]
outputs: [structured-question.json]
mutates: false
scripts:
  - scripts/arete/qa_loop_executor.py
templates:
  - templates/structured-question-template.md
---

# Estruturar dúvida humana

Perguntar somente após esgotar fonte local, teste e regra documentada.
Usar o template (observação → evidência → tentativas → excluídas → alternativas →
resposta necessária → impacto). Preferir `qa_loop_executor.py question` + `teach`.

## Aceite positivo

- Resposta pedida no vocabulário da ficha; estado `PENDENTE` até resposta.

## Aceite negativo

- Não perguntar "está certo?" genérico.
- Não pedir ao dono para diagnosticar o código no lugar da regra de produto.
