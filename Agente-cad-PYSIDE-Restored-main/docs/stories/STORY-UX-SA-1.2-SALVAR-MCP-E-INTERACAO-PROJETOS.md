# STORY-UX-SA-1.2 - Salvar item SA, evidencia MCP e interacao do Gerenciar Projetos

**Status:** Ready for Review  
**Responsavel:** Dev  
**Contexto:** Structural Analyzer, Curadoria RAG/MCP e Gerenciar Projetos

## Objetivo

Dar ao operador um salvamento explicito por item no painel direito do Structural
Analyzer, com persistencia da ficha N1 e captura auditavel da edicao como evidencia
MCP T0. Restaurar tambem a interacao por mouse do Gerenciar Projetos e tornar a aba
de evidencias facil de localizar.

## Criterios de aceite

- O painel direito de PIL, LV, FV e LAJ mostra `Salvar item` acima de `ATENCAO`.
- O clique persiste o item atual e a nota de atencao.
- Uma alteracao real gera `human_event_logs.status=CAPTURED` e `tier=T0`.
- Salvar nunca valida, aprova, promove ou indexa o evento no RAG global.
- Salvamento sem diferenca nao cria evento MCP duplicado.
- Existe atalho para `Gerenciar Projetos > Curadoria RAG/MCP > Evidencias MCP`.
- `Consultar Contexto RAG` continua somente leitura, filtrado em T1/T2.
- O ProjectManager e construido como widget embutido e suas abas respondem a clique.
- A subaba `Evidencias MCP` fica visivel no inicio da navegacao da Curadoria.

## Tarefas

- [x] Criar barra de acoes do item no Structural Analyzer.
- [x] Persistir PIL/LV/FV/LAJ pelo repositorio existente.
- [x] Comparar snapshot anterior/novo e registrar evidencia T0 via MCP.
- [x] Adicionar navegacao direta para Evidencias MCP.
- [x] Corrigir flags de janela do ProjectManager embutido.
- [x] Reordenar/rotular Curadoria para expor RAG e MCP.
- [x] Adicionar testes de contrato e smoke de interacao Qt.
- [x] Executar testes relevantes e registrar resultado.

## Regras de seguranca

- `Salvar item` e um evento de edicao, nao uma validacao humana.
- Somente a acao explicita `Aprovar proposta`, na Curadoria, pode promover T0 para T1.
- Nao consultar nem indexar T0 como conhecimento confiavel.
- Nao alterar o comportamento do motor puro `Analise Geral`.

## Validacao

- `py_compile`: `main.py`, `project_manager.py` e bridge MCP de runtime.
- Smoke Qt offscreen: clique em `CURADORIA RAG/MCP` e `Evidencias MCP` confirmado.
- Contrato MCP: edicao do SA persistida como `CAPTURED/T0`.
- Testes focados: 7 aprovados (`test_sa_mcp_controls` + render de links).
- Suite RAG/MCP relacionada: 33 aprovados.
