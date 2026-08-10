---
task: curate-rag
agent: aegis
inputs: [run_id, human_decision, evidence_hashes]
outputs: [rag-candidate.json]
mutates: false
scripts:
  - scripts/arete/qa_rag_curation.py
---

# Preparar candidato RAG

Usar `qa_rag_curation.py materialize`; nunca promover automaticamente. Exigir classe,
família, campo, tier candidato, obra/pavimento, regra universal, evidências e aprovação
humana. T1 = humano; T2 = regra reproduzível aprovada; T3 = hipótese não confirmatória.

Promoção: `qa_rag_curation.py promote --approved-by ...` apenas após decisão humana.
Tier nativo de coluna pode estar ausente no DB legado: o tier vive no JSON da regra e
é filtrado por `qa_rag_evidence` (parse fail-closed quando `--rag-evidence required`
com tier).

## Aceite positivo

- Candidato com `requer_aprovacao_humana` / status T1_CANDIDATE e hashes.

## Aceite negativo

- Materialize **não** escreve memória confiável.
- T3 **nunca** confirma campo.
- RAG **nunca** é prova única do item atual.
