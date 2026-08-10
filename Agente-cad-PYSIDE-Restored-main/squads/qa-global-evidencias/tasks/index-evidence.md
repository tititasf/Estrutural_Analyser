---
task: index-evidence
agent: aegis
inputs: [scope.json]
outputs: [evidence-index.json, provenance-graph.json]
mutates: false
---

# Indexar evidências

Calcular SHA-256 e autoridade de snapshot N1, entidade CAD/fonte, contrato, payload,
DXF, HTML, PNG e entradas RAG citadas. Marcar elo ausente sem inventar substituto.

O grafo deve provar quem alimenta quem. Veto imediato se N2/N4 entrar no caminho de N3.
Cache só é reutilizado quando todos os hashes e a versão do adaptador permanecem iguais.

## Aceite positivo

- Cada nó com fonte, hash (ou `missing`), autoridade e consumidor.
- HTML/checkbox etiquetados como `presentation_only`.

## Aceite negativo

- Não completar elo ausente por inferência silenciosa.
- Não usar N2/N4 como input de N1/N3.
