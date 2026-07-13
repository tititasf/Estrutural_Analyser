---
task: visual-gate
agent: aegis
inputs: [scope.json, pair, generated_pngs]
outputs: [visual-verdict.json]
mutates: [relatorio_json_only]
---

# Executar gate visual

Usar exclusivamente `scripts/arete/g2v_harness.py --backend cli`. Nunca usar backend de
API nem `--permitir-api` sem ordem explícita. Ler cada PNG e registrar veredito, confiança
e achados por parte/direção/motor suspeito. G2 numérico sozinho não fecha Arete.
