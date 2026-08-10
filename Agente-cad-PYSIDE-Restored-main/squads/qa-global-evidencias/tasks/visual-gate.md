---
task: visual-gate
agent: aegis
inputs: [scope.json, pair, generated_pngs]
outputs: [visual-verdict.json]
mutates: [relatorio_json_only]
scripts:
  - scripts/arete/g2v_harness.py
---

# Executar gate visual

Usar exclusivamente `scripts/arete/g2v_harness.py --backend cli`. Nunca usar backend de
API nem `--permitir-api` sem ordem explícita. Ler cada PNG/SVG e registrar veredito,
confiança e achados por parte/direção/motor suspeito.

## Aceite positivo

- Veredito registrado com paths dos artefatos lidos.

## Aceite negativo

- G2 numérico sozinho **não** fecha Arete.
- Backend API **não** é gate canônico.
- Similaridade de bbox **não** substitui geometria de fôrmas.
