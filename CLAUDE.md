# CLAUDE.md — Workspace CAD-ANALYZER (raiz de dados + app)

## Layout deste workspace

| Path | O que é |
|------|---------|
| `Agente-cad-PYSIDE-Restored-main/` | **Código da app** (PySide6, scripts, docs) — repo git. Tem CLAUDE.md próprio com missão e regras detalhadas. |
| `project_data.vision` | **DB SQLite REAL** (fichas N2, recortes, triagem). É ESTE que a app usa — o de dentro do repo é stale. |
| `DADOS-OBRAS/` | Dados das obras (Fases 0–8, recortes reversos, RAG por-obra). Os paths gravados no DB apontam para cá. |
| `SCRIPTS_ROBOS/`, `_ROBOS_ABAS/` | Robôs geradores SCR legados (referência de semântica). |
| `BASE_DWG_PARA_COMANDOS_SCRIPTS.dwg` | MOLDE correto para automação AutoCAD COM. |

## Missão atual — Arete Quality Gates (2026-06)

Leia antes de agir:
1. `Agente-cad-PYSIDE-Restored-main/CLAUDE.md` — regras inegociáveis + fatos do ambiente
2. `Agente-cad-PYSIDE-Restored-main/docs/HANDOFF-ARETE-EXECUTOR.md` — missão + protocolo
3. `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-ARETE-QUALITY-GATES.md` — gates G0–G6

Progresso/retomada: `Agente-cad-PYSIDE-Restored-main/scripts/arete/relatorios/` (mais recente).

## Regras deste nível

- Git: o repo é `Agente-cad-PYSIDE-Restored-main/` — rodar comandos git lá dentro.
- `project_data.vision` e `DADOS-OBRAS/` são DADOS DE PRODUÇÃO: ler à vontade;
  escrever apenas o que o plano Arete prevê (novas linhas em tabelas reverse_eng_*,
  saídas em pastas novas). NUNCA deletar/sobrescrever DXFs de obras ou JSONs Fase-4.
- Backups `.bak`, logs e pastas Output_* na raiz são históricos — não limpar sem ordem.
