# CLAUDE.md — Workspace CAD-ANALYZER (raiz de dados + app)

## Layout deste workspace

| Path | O que é |
|------|---------|
| `Agente-cad-PYSIDE-Restored-main/` | **Código da app** (PySide6, scripts, docs) — repo git. Tem CLAUDE.md próprio com missão e regras detalhadas. |
| `project_data.vision` | **DB SQLite REAL** (fichas N2, recortes, triagem). É ESTE que a app usa — o de dentro do repo é stale. |
| `DADOS-OBRAS/` | Dados das obras (Fases 0–8, recortes reversos, RAG por-obra). Os paths gravados no DB apontam para cá. |
| `SCRIPTS_ROBOS/`, `_ROBOS_ABAS/` | Robôs geradores SCR legados (referência de semântica). |
| `BASE_DWG_PARA_COMANDOS_SCRIPTS.dwg` | MOLDE correto para automação AutoCAD COM. |

## Missões ativas (duas, intercaladas — qualidade manda)

**1. Arete Quality Gates (2026-06 →)** — qualidade dos motores. Leia antes de agir:
1. `Agente-cad-PYSIDE-Restored-main/CLAUDE.md` — regras inegociáveis + fatos do ambiente
2. `Agente-cad-PYSIDE-Restored-main/docs/HANDOFF-ARETE-EXECUTOR.md` — missão + protocolo
3. `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-ARETE-QUALITY-GATES.md` — gates G0–G6

**2. Produção & Soberania (2026-07 →)** — levar o sistema ao uso real da equipe (3–5),
sem distribuir binário: servidor na workstation do dono + VPN + portal web mínimo.
Plano, gates P0–P6 e decisões DP-1..9:
`Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-PRODUCAO-SOBERANIA.md`.

Progresso/retomada: `Agente-cad-PYSIDE-Restored-main/scripts/arete/relatorios/` (mais recente).

Visão (G2-V / N1-V / G5-V, todas as classes): dual-mode em
`Agente-cad-PYSIDE-Restored-main/docs/QA-VISAO-EVIDENCIA-CANONICA.md` —
**agente = PNG**; **persist/app/portal web = SVG**; headless sem DB = imagem dinâmica.
**SVG web pan/zoom:** somente **viewBox** (padrão FV V302) — proibido CSS scale.
Ver `Agente-cad-PYSIDE-Restored-main/docs/PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md`.

## Regras deste nível

- Git: o repo é `Agente-cad-PYSIDE-Restored-main/` — rodar comandos git lá dentro.
- `project_data.vision` e `DADOS-OBRAS/` são DADOS DE PRODUÇÃO: ler à vontade;
  escrever apenas o que o plano Arete prevê (novas linhas em tabelas reverse_eng_*,
  saídas em pastas novas). NUNCA deletar/sobrescrever DXFs de obras ou JSONs Fase-4.
- Backups `.bak`, logs e pastas Output_* na raiz são históricos — não limpar sem ordem.
- **Entrega E2E (2026-07-19):** se o dono pediu validar/gerar/fechar um escopo
  (ex. *todos* os segmentos de uma viga), o agente executa o protocolo **completo**
  ponta a ponta na qualidade máxima — inventário+set-diff+evidência+veredito **por
  unidade** — nunca só regen/HTML/smoke.  
  `Agente-cad-PYSIDE-Restored-main/docs/REGRA-ENTREGA-E2E-QUALIDADE-MAXIMA.md`
