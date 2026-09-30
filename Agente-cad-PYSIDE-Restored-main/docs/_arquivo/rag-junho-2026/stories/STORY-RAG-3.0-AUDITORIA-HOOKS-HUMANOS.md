# STORY RAG-3.0 - Auditoria dos Hooks Humanos

**Status:** Concluida em 2026-06-27.

## Objetivo

Comprovar quais gatilhos do EPIC RAG-3 estao realmente conectados e impedir que
loopers, CLI ou automacoes sejam tratados como validacao humana.

## Resultado

- Aprovacao de recorte grava apenas `crop_learning_events`.
- Aprovacao de recorte nao promove F5/N2, nao valida campos e nao valida N4.
- Exclusao/desvalidacao de recorte revoga seus exemplos de crop e preserva historico.
- Comparison Engine envia explicitamente `validation_origin="human_ui"`.
- Chamadas sem essa origem gravam somente candidato em quarentena.
- Desvalidacao no Comparison cria tombstone TX do evento de validacao.

## Pendencias mantidas abertas

- RAG-3.1b: validacao humana granular dos campos F5/N2.
- RAG-3.2: indexacao separada dos artefatos visuais N1/N3/N4 validados.
- RAG-3.2b: desvalidacao granular da F5, dependente do RAG-3.1b.
- RAG-3.3: promocao T1 para T2 somente apos duas obras independentes.
- Smoke visual dos botoes no aplicativo.

## Validacao

```powershell
python -m pytest tests\test_crop_learning_store.py tests\test_item_attention_store.py
python -m pytest tests\test_rag_validation_events.py tests\test_rag_tier.py tests\test_rag_tier_synthetic_guard.py
```

Resultado: 20 testes aprovados.
