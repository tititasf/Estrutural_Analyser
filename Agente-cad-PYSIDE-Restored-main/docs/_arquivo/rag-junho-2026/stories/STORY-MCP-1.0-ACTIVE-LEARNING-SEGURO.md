# STORY MCP-1.0 - Active Learning seguro

**Status:** Ready for Review

## Objetivo

Transformar o MCP em barramento auditavel de evidencias humanas sem permitir
que uma edicao, nota ou clique em Salvar seja confundido com validacao.

## Acceptance Criteria

- Eventos de edicao nascem `CAPTURED`, tier `T0` e nunca entram no RAG global.
- Apenas uma decisao humana explicita pode aprovar uma proposta derivada.
- Daemon usa claim atomico, retry e uma unica coluna de estado.
- FAISS de candidatos e separado dos indices produtivos e gravado atomicamente.
- Hooks registram estado antes/depois somente depois do salvamento bem-sucedido.
- MCP stdio permanece operacional; transporte de rede usa porta permitida e
  ferramentas de escrita exigem token.
- Evento de teste existente fica em quarentena, sem exclusao de historico.
- Curadoria mostra evidencias e estados sem promover conhecimento.

## Tasks

- [x] Migrar schema e implementar servico de eventos.
- [x] Corrigir hooks UI.
- [x] Refatorar daemon e indexador.
- [x] Endurecer MCP e concorrencia.
- [x] Expor observabilidade na Curadoria.
- [x] Harmonizar documentacao.
- [x] Executar testes.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- Auditoria de 2026-06-29: import quebrado, dois campos de processamento,
  indice FAISS incorreto e evento de teste no banco real.

### Completion Notes List

- Edicoes, notas e salvamentos geram apenas evidencias `CAPTURED/T0`.
- Promocao exige decisao humana explicita, autor e justificativa.
- Propostas, candidatos e conhecimento aprovado possuem stores separados.
- Indices ativos usam geracoes imutaveis, hashes e troca atomica do ponteiro.
- O indice legado `estruturais.index` nao e alterado pelo active learning.
- O evento sintetico P15 foi preservado como `TEST_QUARANTINED`.
- Curadoria ganhou painel MCP para observar, aprovar, rejeitar e indexar.
- Contexto do Structural Analyzer consulta somente licoes aprovadas.
- Validacao: regressao com 52 testes passou; apos o ajuste de importacao,
  7 testes MCP passaram, junto com Ruff e importacao real de `main.py`.
- Smoke visual offscreen da Curadoria passou sem overflow horizontal.
- Corrigida a resolucao de `src.mcp` quando o desktop inicia pelo diretorio da app.
- Runtime fixado em Python 3.12 com `.venv`, guard de inicializacao e verificacao
  de ChromaDB/NumPy.
- Ambiente verificado com Python 3.12.2, NumPy 1.26.4, ChromaDB 1.5.9 e
  Nuitka 4.1.3; `pip check`, import de `main.py` e 7 testes MCP passaram.

### File List

- `src/mcp/db_bridge.py`
- `src/mcp/cad_analyzer_mcp.py`
- `Agente-cad-PYSIDE-Restored-main/src/mcp/__init__.py`
- `Agente-cad-PYSIDE-Restored-main/scripts/verify_python_runtime.py`
- `Agente-cad-PYSIDE-Restored-main/iniciar_dashboard.bat`
- `Agente-cad-PYSIDE-Restored-main/install_all.ps1`
- `Agente-cad-PYSIDE-Restored-main/build_nuitka.bat`
- `Agente-cad-PYSIDE-Restored-main/main.py`
- `Agente-cad-PYSIDE-Restored-main/pyproject.toml`
- `Agente-cad-PYSIDE-Restored-main/requirements.txt`
- `Agente-cad-PYSIDE-Restored-main/.vscode/settings.json`
- `Agente-cad-PYSIDE-Restored-main/CLAUDE.md`
- `.python-version`
- `.vscode/settings.json`
- `.gitignore`
- `docs/PYTHON-3.12-RUNTIME.md`
- `docs/GETTING_STARTED.md`
- `Agente-cad-PYSIDE-Restored-main/src/ui/modules/comparison_engine.py`
- `Agente-cad-PYSIDE-Restored-main/src/ui/modules/diagnostic_reverse_hub.py`
- `Agente-cad-PYSIDE-Restored-main/src/ui/widgets/project_manager.py`
- `Agente-cad-PYSIDE-Restored-main/_ROBOS_ABAS/Robo_Laterais_de_Vigas/robo_laterais_viga_pyside.py`
- `scripts/mcp_active_learning_daemon.py`
- `scripts/rag_active_trainer.py`
- `scripts/active_learning_query.py`
- `scripts/active_learning_patterns.py`
- `scripts/rag_context_service.py`
- `scripts/rag_health.py`
- `scripts/rag_export.py`
- `tests/test_mcp_active_learning_safe.py`
- `docs/MCP-ACTIVE-LEARNING-SPEC.md`
- `docs/stories/STORY-MCP-1.0-ACTIVE-LEARNING-SEGURO.md`
- `MASTERPLAN-CEREBRO-RAG-MULTIMODAL-v1.0.md`
- `docs/MASTERPLAN-RAG-INTEGRACAO-COMPLETA.md`
- `docs/MASTERPLAN-RAG-VECTORIZACAO.md`

### Change Log

- 2026-06-29: story criada e aprovada para desenvolvimento pelo pedido direto do usuario.
- 2026-06-29: implementacao concluida e movida para revisao.
- 2026-06-29: pacote MCP compartilhado exposto ao runtime da aplicacao desktop.
- 2026-06-29: ambiente oficial fixado em Python 3.12 e NumPy 1.x para ChromaDB.
