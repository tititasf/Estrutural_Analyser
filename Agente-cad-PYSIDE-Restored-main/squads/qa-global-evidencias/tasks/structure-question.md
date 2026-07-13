---
task: structure-question
agent: aegis
inputs: [unresolved_finding, evidence-index.json]
outputs: [pergunta-estruturada.md]
mutates: false
---

# Estruturar dúvida humana

Preencher `templates/structured-question-template.md`. Incluir observação, evidências,
tentativas, hipóteses excluídas, alternativas, resposta específica e impacto. Não perguntar
“está certo?”. Se a resposta puder ser obtida por fonte local ou teste, continuar investigando.
