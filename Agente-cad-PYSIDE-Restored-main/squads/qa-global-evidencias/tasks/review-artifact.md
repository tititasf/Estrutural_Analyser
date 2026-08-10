---
task: review-artifact
agent: aegis
inputs: [scope.json, nivel, variante, artefato_dxf]
outputs: [ficha_index.html, manifesto.json]
mutates: false
scripts:
  - scripts/arete/ficha_motor_item.py
---

# Revisar artefato N3/N4

Gerar/inspecionar com gerador individual da classe + `ficha_motor_item.py`.
Ler manifesto com SHA-256 de contrato/DXF/JSON/SVG/HTML.

## Aceite positivo

- Ficha com banner "apresentação ≠ prova".
- Hashes gravados no manifesto.

## Aceite negativo

- Ficha **não** interpreta N1 e **não** grava DB.
- Ficha **não** substitui G2-V/G5-V quando o gate exigir comparação canônica.
