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
teste focado, regressão e gate visual. Veto para número/ID específico do item.
