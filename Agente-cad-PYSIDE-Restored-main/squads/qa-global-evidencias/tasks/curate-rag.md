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


### Consolidação de níveis — 2026-10-01

Regra integrada: `docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md` (canônico). Indexar regras documentadas aprovadas e decisões locais com escopo/revisão; exemplo L317 não é constante nem regra por nome. Não promover as 68 estimativas do pacote de 01/10 a T1 por estarem preenchidas. A confirmação de fundo contínuo é limitada às seis regiões examinadas; registrar SHA e UID. A indexação textual/vetorial de documentos não altera validação N1 nem tier de hipóteses na semantic_rag_kb.
