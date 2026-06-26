# QUALITY GATE — Masterplans Fichas F1-F9 & Loop de Treino

**Avaliador:** Athena (CEO-Planejamento) · `*quality-check`
**Data:** 2026-06-20
**Alvo:** `MASTERPLAN-FICHAS-F1-F9-HARMONIZACAO.md` v2.0 + `MASTERPLAN-LOOP-TREINO-MOTOR.md` v1.0
**Rubrica:** Arete 10 dimensões (reinterpretadas para masterplan técnico — ver coluna "Lente")

---

## Scorecard

| # | Dimensão | Lente (contexto deste plano) | Peso | Nota | Threshold | OK |
|---|----------|------------------------------|------|------|-----------|----|
| 1 | Security | **Segurança de dados** — sem op destrutiva de DB, "não recriar", validados nunca sobrepostos | 10 | 9 | ≥8 | ✅ |
| 2 | UX Excellence | **Clareza para o executor** (modelo menor) — passos apontam tabela/arquivo real | 10 | 8 | ≥7 | ✅ |
| 3 | Performance | **Eficiência do loop** — métricas definidas; falta budget de runtime/query no DB 1.35GB | 9 | 7 | ≥7 | ✅ |
| 4 | Scalability | **Multi-obra / multi-classe** — partição por classe, promoção ≥2 obras, replicação de pattern | 9 | 8 | ≥7 | ✅ |
| 5 | UI Polish | **Harmonização de UI** das abas de ficha (R1-R7, design system) | 8 | 7 | ≥7 | ✅ |
| 6 | Accessibility | **Acessibilidade do conhecimento** — docs cross-linkados + indexáveis no domain_knowledge | 8 | 7 | ≥7 | ✅ |
| 7 | Maintainability | **Reuso da infra existente** — zero estrutura nova; regras versionadas | 7 | 9 | ≥6 | ✅ |
| 8 | Testability | **Quality gates** — G-Item/Campo/Semântico/Generalização/Regressão + autovalidate_v3; falta nomear suíte concreta | 7 | 7 | ≥6 | ✅ |
| 9 | Time to Market | **Entrega incremental** — por classe, S0 pequeno, obra-piloto definida | 7 | 8 | ≥6 | ✅ |
| 10 | Cost Efficiency | **Zero-waste / no rework** — ancorado no DB real (evitou erro do learned_params.json) | 6 | 8 | ≥5 | ✅ |

**Média ponderada = 633 / 81 = 7.81 / 10** → acima do mínimo (7.0). Todos os thresholds individuais atingidos.

**VERDITO: PASS (GO) — classe S.** Plano selado para execução incremental, sob gating do dono.

---

## Pontos fortes (o que puxa a nota)

- **Maintainability 9 / Security 9:** o plano reusa `transformation_rules` + Chroma + `engrev_*_learning.vision` e proíbe op destrutiva — risco de perder trabalho já feito é baixo.
- **Alinhamento N1-N4** com `MASTERPLAN-ENGENHARIA-REVERSA` confirmado (F7=N1, F5=N2, F8=N3, F9=N4).
- **Ataque por classe** com gates de promoção cross-obra → generaliza sem overfit.

## Gaps a fechar (não bloqueiam o gate, mas reduzem nota)

| Gap | Dimensão afetada | Ação | Quando |
|-----|------------------|------|--------|
| `SCHEMA-FICHA-GRANULAR.md` citado mas inexistente | UX/Maintainability | criar na Fase 1 (a partir do `campos_json` real) | antes da Fase B |
| Suíte de não-regressão não nomeada | Testability | nomear script/conjunto de obras-treino | S0 |
| Sem budget de runtime/query (DB 1.35GB) | Performance | definir alvo de tempo por classe/pavimento | S0 |
| Vínculo geométrico de LV/PIL não descrito | Scalability | **dono descreve → Athena formaliza** | antes de LV/PIL entrarem no loop |
| "Análise com Contexto" sem extração suficiente | (escopo futuro) | manter como FUTURO documentado | pós-Arete |

---

## Recomendação

Não acionar squad a frio nesta fase (planejamento puro, já ancorado no DB/RAG real). Os 5 gaps acima são fechados **dentro de S0/Fase 1** pelos squads já alocados (§7/§9 do loop). O gate de plano está **aprovado**.
