# Documentação — CAD-ANALYZER / Estrutural Analyzer

**Atualizado:** 2026-07-03. Este índice aponta os documentos canônicos por tema.
Regra de leitura: em conflito entre docs, vale a hierarquia da seção
"Missões ativas" e, para status/números, SEMPRE o relatório mais recente em
`scripts/arete/relatorios/` (números escritos à mão envelhecem).

## ⭐ Ponto de entrada (ler primeiro)

| Documento | O que é |
|-----------|---------|
| `../CLAUDE.md` (raiz do workspace) | Layout dados vs código, regras do workspace |
| `../../CLAUDE.md` → [CLAUDE.md do repo](../CLAUDE.md) | Regras inegociáveis da app + missões ativas |
| [MASTERPLAN-ARETE-QUALITY-GATES.md](./MASTERPLAN-ARETE-QUALITY-GATES.md) | Missão de QUALIDADE: gates G0–G6, definição de Arete |
| [MASTERPLAN-PRODUCAO-SOBERANIA.md](./MASTERPLAN-PRODUCAO-SOBERANIA.md) | Missão de PRODUTO (2026-07): portal da equipe, gates P0–P6, decisões DP-1..9 |
| [ARETE-LOOP-PROCEDIMENTO-GERAL.md](./ARETE-LOOP-PROCEDIMENTO-GERAL.md) | Procedimento canônico de execução do loop por classe |
| [STATUS.md](./STATUS.md) | **Status GERADO por script** (`scripts/arete/gerar_status.py`) — fonte de verdade de números; regenerar antes de citar |
| [HANDOFF-PRODUCAO-EXECUTOR.md](./HANDOFF-PRODUCAO-EXECUTOR.md) | Handoff para sessão executora (modelo menor) + stories em `stories/STORY-EXEC-*.md` |

## Missão Arete (execução)

| Documento | O que é |
|-----------|---------|
| [HANDOFF-ARETE-EXECUTOR.md](./HANDOFF-ARETE-EXECUTOR.md) | Protocolo de autonomia, restrições rígidas |
| [ARETE-TRIAGEM-ERROS.md](./ARETE-TRIAGEM-ERROS.md) | Ciclo marcar→logar→corrigir→reverificar |
| [ARETE-PLAYWRIGHT-QA-VISUAL.md](./ARETE-PLAYWRIGHT-QA-VISUAL.md) | Leitura de fichas via Playwright/SVG |
| [ARETE-ARQUITETURA-VALIDACAO.md](./ARETE-ARQUITETURA-VALIDACAO.md) | Problema/alvo da validação (24/06) |
| MASTERPLAN-ARETE-{LAJE,FUNDO-VIGA,LATERAL-VIGA,PILAR}.md | Plano por classe |
| [QUALITY-GATE-MASTERPLANS-FICHAS-LOOP.md](./QUALITY-GATE-MASTERPLANS-FICHAS-LOOP.md) | Auto-revisão de qualidade dos planos |

## Dados, MCP e RAG (contrato de harmonização)

| Documento | O que é |
|-----------|---------|
| [ARETE-MCP-RAG-HARMONIZACAO.md](./ARETE-MCP-RAG-HARMONIZACAO.md) | Contrato Arete/MCP/SQLite/RAG: tiers T0–T2/TX, gates de ativação |
| `../../docs/MCP-ACTIVE-LEARNING-SPEC.md` (raiz workspace) | Servidor MCP próprio — preparação futura, INATIVO hoje |
| [POLITICA-CONFIANCA-RAG.md](./POLITICA-CONFIANCA-RAG.md) | Tiers de confiança |
| [RAG-REVOGACAO-HUMANA-SPEC.md](./RAG-REVOGACAO-HUMANA-SPEC.md) | Revogação/tombstones |

## Arquitetura geral e pipeline

| Documento | O que é |
|-----------|---------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Arquitetura geral (motores, robôs, pipeline) |
| [DATA_FLOW.md](./DATA_FLOW.md) | Fluxo de dados completo |
| [ARQUITETURA-DB-COMPLETA.md](./ARQUITETURA-DB-COMPLETA.md) | Schema do SQLite real |
| [MASTERPLAN-CAD-ANALYZER.md](./MASTERPLAN-CAD-ANALYZER.md) / [MASTERPLAN-CAD-UI.md](./MASTERPLAN-CAD-UI.md) | Visão app/UI |
| [MASTERPLAN-ENGENHARIA-REVERSA.md](./MASTERPLAN-ENGENHARIA-REVERSA.md) | Pipeline N1–N4 reverso |
| [SCHEMA-FICHA-GRANULAR.md](./SCHEMA-FICHA-GRANULAR.md) | Schema das fichas |
| [SPEC-GERADORES-DXF.md](./SPEC-GERADORES-DXF.md) / [SPEC-VIGA-SPLIT-FV-LV.md](./SPEC-VIGA-SPLIT-FV-LV.md) | Geradores |
| [ARTIFACT_GOVERNANCE_N3_N4.md](./ARTIFACT_GOVERNANCE_N3_N4.md) | Governança de artefatos |
| [DEVELOPER_ONBOARDING.md](./DEVELOPER_ONBOARDING.md) | Onboarding |

## Semântica por classe

| Documento | O que é |
|-----------|---------|
| SEMANTICA-{LAJE,PILAR,VIGA}-NOVA.md | Interpretação de cada elemento |
| [INTERPRETACAO-PILARES-ABCD.md](./INTERPRETACAO-PILARES-ABCD.md) | Faces ABCD |
| [LV-COMPREENDER-INTERPRETACAO-FICHAS-N2-N4.md](./LV-COMPREENDER-INTERPRETACAO-FICHAS-N2-N4.md) | LV N2/N4 |
| interviews/{LAJES,PILARES,VIGAS}.md | Entrevistas de domínio |
| [ROBO_SCR_PATTERNS.md](./ROBO_SCR_PATTERNS.md) / [CALCULOS_ALGORITMOS.md](./CALCULOS_ALGORITMOS.md) | Semântica dos robôs SCR legados |

## Histórico / superseded (não usar como procedimento; válidos como registro)

- [LOOPING-EVOLUCAO-N2-VISAO-FICHA.md](./LOOPING-EVOLUCAO-N2-VISAO-FICHA.md) e
  [MASTERPLAN-LOOP-TREINO-MOTOR.md](./MASTERPLAN-LOOP-TREINO-MOTOR.md) — superseded na
  execução pelo ARETE-LOOP-PROCEDIMENTO-GERAL.md; infra de dados citada continua válida.
- [STATUS-ATUAL-JUNHO-2026.md](./STATUS-ATUAL-JUNHO-2026.md), CAD-10-VALIDATION-REPORT.md,
  TEST_GAP_ANALYSIS.md — snapshots no tempo.
- MASTER_PLAN.md / MASTER_PLAN_V2.md — visão ampla de autoria anterior ("Antigravity");
  pode divergir do enquadramento atual.
- stories/ — changelog/backlog de construção (RAG e app).

## Stack real (2026-07)

| Componente | Tecnologia |
|-----------|-----------|
| UI (cabine do dono) | PySide6 (Qt6) — **Python 3.12 obrigatório** |
| DXF | ezdxf (+ accoreconsole na entrada, em migração para ODA File Converter — DP-5) |
| DB | SQLite `D:/Agente-cad-PYSIDE/project_data.vision` |
| Vector RAG | LanceDB + NVIDIA NIM 4096-dim (consolidação em LanceDB — WS-C) |
| Geometria | Shapely |
| QA visual | Fichas HTML headless + SVG inline + Playwright |

> Nota: referências antigas a "Supabase" e "ChromaDB" neste índice eram de uma fase
> anterior e não refletem o sistema atual.
