---
task: review-artifact
agent: aegis
inputs: [scope.json, nivel, parte, variante]
outputs: [manifesto.json, index.html]
mutates: false
---

# Revisar artefato N3/N4

1. Não rodar headless por ajuste somente visual/de gerador.
2. Gerar o item pela rota individual da classe.
3. Montar ficha com `scripts/arete/ficha_motor_item.py` e artefatos/JSON exatos.
4. Para PIL, mostrar PARA e PASSA como payloads e DXFs independentes.
5. Registrar hash do contrato, payload, DXF e HTML; nenhum card pode misturar variantes.

Aceite: ficha focada reproduzível, sem Qt/DB/lock e com proveniência explícita.
