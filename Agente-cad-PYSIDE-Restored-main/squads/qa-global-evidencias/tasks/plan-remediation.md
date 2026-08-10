---
task: plan-remediation
agent: aegis
inputs: [finding, provenance-graph.json]
outputs: [fix-request.md]
mutates: false
---

# Planejar remediação

Classificar `schema_gap`, `extractor_bug`, `converter_bug`, `generator_bug`,
`comparator_config_gap` ou `ambiguous`. Propor uma causa geral, arquivo responsável,
teste focado, regressão e gate visual.

## Aceite positivo

- Fórmula geral reutilizável + teste representativo + critério de saída.

## Aceite negativo

- Veto para hardcode de item, obra ou pavimento.
- HTML **não** substitui correção no motor/extrator.
