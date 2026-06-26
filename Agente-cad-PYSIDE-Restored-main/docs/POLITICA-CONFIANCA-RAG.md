# Politica de Confianca RAG

Fonte: `D:/Agente-cad-PYSIDE/MASTERPLAN-CEREBRO-RAG-MULTIMODAL-v1.0.md` v2.2.

## Objetivo

Impedir que fichas, recortes e exemplos em desenvolvimento contaminem o RAG global.
O RAG global so pode atuar como professor quando a informacao foi validada por humano
ou consolidada por validacao em mais de uma obra.

## Tiers

| Tier | Nome | Entra no RAG global ativo? | Uso |
|------|------|----------------------------|-----|
| `T0` | Quarentena | Nao | Draft, extracted, hipotese, legado sem validacao explicita |
| `T1` | Validado | Sim | Aprovado por humano em uma obra |
| `T2` | Consolidado | Sim | Validado em duas ou mais obras, candidato a default |
| `TX` | Revogado | Nao | Era valido, mas foi desvalidado por humano |

## Regras

- Consulta global padrao usa `min_tier='T1'`.
- Dados sem metadados de validacao explicita sao `T0`.
- `T0` pode aparecer na Curadoria como pendente, mas nao pode alimentar o RAG global.
- `TX` tem prioridade sobre qualquer validacao anterior.
- Desvalidacao humana nao apaga historico: cria tombstone/evento e exclui das queries.
- Revalidar uma correcao cria nova versao `T1`; nao sobrescreve silenciosamente o vetor antigo.

## Implementacao Atual

- `D:/Agente-cad-PYSIDE/scripts/rag_tier.py`
  - `get_tier(row)`
  - `is_indexable(row)`
  - `revoke_item(...)`
  - tombstones em `D:/Agente-cad-PYSIDE/data/vectors/faiss/rag_tombstones.json`
- `D:/Agente-cad-PYSIDE/scripts/rag_query.py`
  - filtra resultados por `min_tier='T1'` por padrao
  - exclui IDs revogados por tombstone
- `D:/Agente-cad-PYSIDE/scripts/rag_ingestor.py`
  - recusa `T0` antes de adicionar ao FAISS
- `D:/Agente-cad-PYSIDE/scripts/rag_commons.py`
  - aplica o mesmo filtro em queries internas compartilhadas

## Observacao sobre o Corpus Legado

Em 2026-06-26, o corpus FAISS existente tinha 213 vetores sem metadados de validacao
explicita. Pela politica atual, esses vetores sao tratados como `T0`: permanecem
auditaveis nos metadados, mas nao aparecem em queries globais padrao `T1+`.

Para promover qualquer item legado, deve haver validacao humana ou migracao explicita
com evidencia de validacao. Nao fazer promocao em massa.

