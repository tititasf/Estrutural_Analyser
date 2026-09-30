# STORY RAG-3.2 - Memoria de Artefatos N3/N4

**Status:** Registro e render canonico concluidos em 2026-06-27; embeddings pendentes.

## Objetivo

Registrar exatamente qual versao de N3 ou N4 foi validada pelo humano no
Comparison Engine, sem copiar dados entre niveis.

## Implementacao

- Tabela `rag_artifact_validations`.
- Identidade versionada pelo SHA-256 do DXF carregado.
- Proveniencia: obra, pavimento, classe, item e nivel N3/N4.
- Estado `validated` ou `revoked`.
- Desvalidacao cria tombstone somente para o hash atual.
- Evento de treino continua sendo gravado separadamente.
- Curadoria/Pipelines de Treino mostra `N3/N4 visuais`.
- Validacao gera PNG canonico 1024x768 e manifesto JSON.
- DXF e PNG possuem hashes independentes no registro.
- Renderer: `dxf-canonical-v1`, fundo CAD escuro e todas as layers visiveis.

## Protecoes

- Origem precisa ser `validation_origin="human_ui"`.
- CLI e loopers geram apenas candidato em quarentena.
- N3 nao recebe campos N2/N4.
- Validar N4 nao valida a ficha F5 automaticamente.
- Nenhum embedding visual e criado antes de haver corpus humano suficiente.

## Validacao

```powershell
python -m pytest tests\test_curadoria_rag_metrics.py tests\test_rag_validation_events.py tests\test_rag_tier_synthetic_guard.py
```

Resultado: 14 testes aprovados, incluindo dimensoes/hash/manifesto do PNG,
e compilacao dos modulos PySide aprovada.

## Pendente

- Indexar somente artefatos `validated`.
- Medir similaridade N3/N4 sem transformar o juiz N4 em entrada do N3.
