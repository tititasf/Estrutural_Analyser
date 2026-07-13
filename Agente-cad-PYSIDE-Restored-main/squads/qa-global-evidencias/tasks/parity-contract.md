---
task: parity-contract
agent: aegis
inputs: [contract, payload, dxf, html]
outputs: [parity-report.json]
mutates: false
---

# Verificar paridade de contrato

Comparar contrato → payload → DXF → HTML sem reinterpretar a semântica. Cobrir slots,
dimensões, vazio de topo, espelho, neutralização, partes e variante. Uma abertura ativa
no payload deve ter representação rastreável no DXF e no card correspondente.

Usar `qa_artifact_parity.py --spec ...` para os campos declarados e
`ficha_motor_item.py --contract ...` para hashes/render. Metadado DXF ausente é
divergência explícita; nunca inferir o DXF a partir do HTML.

Aceite: todo elo tem `contract_id`, fonte e hash; divergência vira achado específico.
