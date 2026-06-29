# STORY RAG-3.1b - Validacao Humana da F5/N2

**Status:** Ficha completa concluida em 2026-06-27; campo a campo pendente.

## Objetivo

Separar definitivamente a aprovacao do recorte da validacao do conteudo da
ficha N2/F5.

## Implementacao

- A aba `Fichas Granulares [F5]` exibe estado T0, T1 ou TX.
- `Validar F5` exige confirmacao de que todos os campos exibidos foram revisados.
- Somente a ficha selecionada e promovida e indexada.
- `Revogar F5` exige motivo e cria tombstone TX auditavel.
- Chamadas sem `validation_origin="human_ui"` ficam em quarentena.
- Revalidacao humana pode restaurar a versao correta.

## Integridade e versionamento

- F5 aprovada e imutavel.
- Para corrigir: revogar, reextrair, revisar e revalidar.
- Reextracao de ficha revogada preserva TX e redefine `rag_indexed=0`.
- `source_id` vetorial inclui hash do conteudo.
- Tombstone da versao antiga nao e removido ao validar conteudo novo.
- IDs legados `reverse_eng_fichas:{id}` tambem sao tombstonados.

## Nao fazer

- Aprovacao de recorte nao valida F5.
- Autoaprovacao de recorte nao valida F5.
- Looper ou CLI nao podem promover nem revogar como humano.
- Reextracao nao pode sobrescrever F5 aprovada.
- Validacao da ficha nao valida N4.

## Validacao

```powershell
python -m pytest tests\test_rag_validation_events.py tests\test_indexar_validados.py tests\test_rag_tier.py tests\test_rag_tier_synthetic_guard.py
python -m pytest tests\test_reverse_f5_validation_ui.py tests\test_reverse_f5_integrity.py tests\test_crop_learning_store.py tests\test_item_attention_store.py
```

Resultado: 20 testes no RAG raiz e 10 testes no app aprovados.

## Pendente

Validacao por campo depende da formalizacao do conjunto obrigatorio/opcional
de campos para cada classe. Ate isso existir, a UI nao deve simular cobertura
granular com checkboxes genericos.
