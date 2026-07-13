---
task: curate-rag
agent: aegis
inputs: [run_id, human_decision, evidence_hashes]
outputs: [rag-candidate.json]
mutates: false
---

# Preparar candidato RAG

Usar `qa_rag_curation.py materialize`; nunca promover automaticamente. Exigir classe,
família, campo, tier candidato, obra/pavimento, regra universal, evidências e aprovação
humana. T1 = humano; T2 = regra reproduzível aprovada; T3 = hipótese não confirmatória.
