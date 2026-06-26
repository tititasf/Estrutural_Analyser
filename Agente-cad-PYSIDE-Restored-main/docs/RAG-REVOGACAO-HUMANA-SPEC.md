# RAG Revogacao Humana Spec

Fonte: `D:/Agente-cad-PYSIDE/MASTERPLAN-CEREBRO-RAG-MULTIMODAL-v1.0.md` v2.2.

## Decisao

Quando o humano desvalida uma informacao que estava validada no RAG, o sistema deve
revogar logicamente a informacao imediatamente. Nao deve apagar nem sobrescrever sem
historico.

## Fluxo

```text
T1/T2 validado
  -> humano desvalida
  -> TX / REVOGADO
  -> tombstone impede retorno em query RAG
  -> evento human_invalidated registra motivo e proveniencia
  -> nova correcao, se houver, entra como nova versao T1
```

## Metadados Recomendados

- `source_id`: ID estavel do item no RAG.
- `revoked_at`: data/hora UTC da desvalidacao.
- `revoked_by`: humano/agente que desvalidou.
- `revoked_reason`: motivo textual.
- `superseded_by_id`: nova versao que substitui a anterior, quando houver.

## Tombstones

Arquivo atual:

```text
D:/Agente-cad-PYSIDE/data/vectors/faiss/rag_tombstones.json
```

Toda query global deve consultar tombstones. Mesmo se o vetor antigo ainda existir em
FAISS/Chroma, ele nao pode retornar enquanto estiver revogado.

## Limpeza Fisica

Limpeza fisica e posterior:

- Chroma: remover/atualizar vetor se a API permitir, mantendo auditoria em SQLite/eventos.
- FAISS: nao confiar em delete in-place; usar tombstone na query e fazer rebuild periodico
  dos indices para compactar.

## Criterio de Aceite

- Item revogado nao retorna em `rag_query.py` com `min_tier=T1`.
- `rag_tier.py --selftest` passa.
- Evento de revogacao permanece auditavel.
- Nova versao corrigida tem ID/versao propria e nao sobrescreve silenciosamente a antiga.

