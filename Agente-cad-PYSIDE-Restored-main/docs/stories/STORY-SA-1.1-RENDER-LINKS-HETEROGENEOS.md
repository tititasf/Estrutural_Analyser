# STORY SA-1.1 - Renderizacao segura de vinculos heterogeneos

**Status:** Ready for Review

## Objetivo

Impedir que metadados semanticos armazenados em `item_data.links` sejam
interpretados como geometrias pelo canvas do Structural Analyzer.

## Acceptance Criteria

- Links canonicos no formato `campo -> slot -> lista[link]` continuam desenhados.
- Link legado direto em um dicionario continua suportado.
- Metadados como `connections.lajes_conectadas.value/details` sao ignorados.
- Entradas string, nulas ou sem `type` nao interrompem o redesenho.
- Nenhum dado F7 ou vinculo e alterado pelo renderer.

## Tasks

- [x] Identificar o payload real que causou a excecao.
- [x] Normalizar somente a leitura dos payloads desenhaveis.
- [x] Adicionar testes de contrato dos formatos aceitos.
- [x] Executar smoke test visual offscreen com o formato do P1.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- `AttributeError: 'str' object has no attribute 'get'` em
  `CADCanvas.draw_item_links`, observado ao selecionar e editar o Pilar P1.

### Completion Notes List

- Causa: `connections.lajes_conectadas` contem metadados sem `type`.
- O renderer agora seleciona somente dicionarios desenhaveis com `type`.
- 11 testes passaram; smoke offscreen criou os itens de cena sem excecao.

### File List

- `Agente-cad-PYSIDE-Restored-main/src/ui/canvas.py`
- `tests/test_canvas_link_payloads.py`
- `Agente-cad-PYSIDE-Restored-main/docs/stories/STORY-SA-1.1-RENDER-LINKS-HETEROGENEOS.md`

### Change Log

- 2026-06-29: renderer tornado tolerante a links heterogeneos.
