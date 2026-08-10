---
task: parity-contract
agent: aegis
inputs: [scope.json, contract, payload, dxf, html]
outputs: [parity-report.json]
mutates: false
scripts:
  - scripts/arete/qa_artifact_parity.py
  - scripts/arete/qa_n3_smoke.py
---

# Paridade e smoke de artefatos

1. Paridade declarativa: `qa_artifact_parity.py --spec ...` (contrato→payload→DXF→HTML).
2. Smoke N3: `qa_n3_smoke.py` por variante (identidade, texto, camadas mínimas).
3. Metadado DXF ausente deve aparecer como gap explícito, não como PASS silencioso.

## Aceite positivo

- Relatório lista cada campo/check com PASS/FAIL/PENDENTE e path/hash.

## Aceite negativo

- Paridade **não** é veredito visual nem equivalência geométrica.
- Smoke **não** fecha abertura/vazio/recorte/anticolisão.
- Paridade vazia **não** produz PASS.
