# Índice de Documentação QA — Roteamento para Agente e Humano

**Status:** canônico (2026-08-01)
**Propósito:** guia de carga documental — qual doc carregar para qual tarefa, por classe.

> **Regra:** o agente QA deve carregar este índice + `LOOPING-CANONICO.md` em toda
> sessão. Para tarefas específicas, seguir a tabela abaixo.

---

## 1. Carga OBRIGATÓRIA (toda sessão QA)

| Doc | Papel |
|-----|-------|
| `docs/LOOPING-CANONICO.md` | Mapa mestre dos Eixos A/B, scripts canônicos, quarentena |
| Skill `qa-global-evidencias` | Orquestrador de microciclos |
| Este índice | Roteamento documental |

---

## 2. Tabela de Roteamento por Tarefa

### 2A. Interpretação N1 (por classe)

| Classe | Docs a carregar |
|--------|-----------------|
| **PIL** | `SA-ANALISE/CLASSES/PIL.md` · `QA-PERFIS-CLASSES-SA-N1-N3.md` §PIL · `PROVENIENCIA-CAMPOS-PIL.md` · `PROCEDIMENTO-QA-PIL-N1-CONTEXTUAL.md` · `INTERPRETACAO-PILARES-ABCD.md` |
| **LAJ** | `SA-ANALISE/CLASSES/LAJ.md` · `QA-PERFIS-CLASSES-SA-N1-N3.md` §LAJ · `PROVENIENCIA-CAMPOS-LAJ.md` · `PROCEDIMENTO-QA-LAJ-N1-CONTEXTUAL.md` · `SEMANTICA-LAJE-NOVA.md` |
| **FV** | `SA-ANALISE/CLASSES/FV.md` · `QA-PERFIS-CLASSES-SA-N1-N3.md` §FV · `PROVENIENCIA-CAMPOS-FV.md` · `PROCEDIMENTO-QA-FV-N1-CONTEXTUAL.md` · `CONTEXTUALIZACAO_VIGAS_SEGMENTOS_FUNDOS.md` |
| **LV** | `SA-ANALISE/CLASSES/LV.md` · `QA-PERFIS-CLASSES-SA-N1-N3.md` §LV · `PROVENIENCIA-CAMPOS-LV.md` · `PROCEDIMENTO-QA-LV-N1-CONTEXTUAL.md` · `LV-COMPREENDER-INTERPRETACAO-FICHAS-N2-N4.md` |
| **FV/LV (roteamento fix)** | + `ARQUITETURA-INTERPRETADORES-VIGA-N1-ISOLADOS.md` |

### 2B. Geração / Desenho N3/N4

| Tarefa | Docs |
|--------|------|
| Pipeline anti-alucinação (camadas G/R/P) | `PIPELINE-VISAO-N2-N3-N4-ANTIALUCINACAO.md` |
| Masterplan de classe | `MASTERPLAN-ARETE-{PIL,LAJ,FUNDO-VIGA,LATERAL-VIGA}.md` |
| Set-diff geométrico | `GEOMETRY-INDEX-N2-N3-N4.md` |
| Motor LV N3/N4 | + `CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md` |

### 2C. Gates Visuais (G2-V / N1-V / G5-V)

| Tarefa | Docs |
|--------|------|
| Dual-mode PNG/SVG | `QA-VISAO-EVIDENCIA-CANONICA.md` |
| Backends de visão (decisão CLI) | `VISION-VALIDACAO-CAMINHOS.md` |
| Inventário mínimo | `QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md` |
| Definição G0–G6 | `MASTERPLAN-ARETE-QUALITY-GATES.md` |

### 2D. Selos, Autoridade e Aplicação

| Tarefa | Docs |
|--------|------|
| Selos 🔵🌸🟠✅ | `CONVENCAO-SELOS-VALIDACAO.md` |
| Permitido vs Proibido | `QA-CICLO-EFICIENCIA-E-AUTORIDADE.md` |
| Autoridade por classe | `MASTERPLAN-AGENTE-QA-GLOBAL.md` §2 |
| Capacidade por classe | `QA-CAPACIDADE-POR-CLASSE.md` |

### 2E. Entrega, Triagem e RAG

| Tarefa | Docs |
|--------|------|
| Entrega multi-item E2E | `REGRA-ENTREGA-E2E-QUALIDADE-MAXIMA.md` |
| Triagem humana | `ARETE-TRIAGEM-ERROS.md` |
| RAG / curadoria | `CONTRATO-QA-RAG-LOOPINGS.md` |
| Quadros de estado | `QA-QUADROS-ESTADO-POR-CLASSE.md` |
| Probes e fast paths | `QA-FASTPATHS-CAMPOS-ARTEFATOS.md` |

### 2F. Referência e Histórico

| Tarefa | Docs |
|--------|------|
| Diários de progresso | `SA-ANALISE/HISTORICO/{PIL,LAJ,FV,LV}.md` |
| Pós-mortem (anti-padrões) | `POSTMORTEM-PIL-P35-MICROCICLO-20260713.md` |
| Persistência headless | `PERSISTENCIA-HEADLESS-SA.md` |

---

## 3. Docs LEGADOS (NÃO usar como procedimento)

Listados em `LOOPING-CANONICO.md` §2. Preservados como histórico de decisões:

- `MASTERPLAN-LOOP-TREINO-MOTOR.md` → substituído por `LOOPING-CANONICO.md`
- `MASTERPLAN-LOOP-LV-N2-VISION-N4.md` → substituído por `LOOPING-CANONICO.md`
- `LOOPING-EVOLUCAO-N2-VISAO-FICHA.md` → substituído por `ARETE-LOOP-PROCEDIMENTO-GERAL.md`
- `QUALITY-GATE-MASTERPLANS-FICHAS-LOOP.md` → substituído por `MASTERPLAN-ARETE-QUALITY-GATES.md`
- `MASTER_PLAN.md` / `MASTER_PLAN_V2.md` → substituídos por `MASTERPLAN-CAD-ANALYZER.md`

---

## 4. Manutenção deste índice

Ao criar ou renomear doc de QA/procedimento, atualizar este índice na mesma entrega.
Fonte de verdade de scripts: `LOOPING-CANONICO.md` §1.
Fonte de verdade de gates: `MASTERPLAN-ARETE-QUALITY-GATES.md`.
