# HANDOFF-C: Roadmap para Produção
**Data:** 2026-03-18 | **Score Atual:** 52/100 → **Meta:** 85/100 | **Athena → Blueprint CEO-CAD-ANALYZER**

---

## 1. SCORE DE PRODUÇÃO ATUAL

### Avaliação Dimensional (10 dimensões × 10 pts)

| Dimensão | Score | Status | Evidência |
|----------|-------|--------|-----------|
| D1: Ingestão DXF | 8/10 | ✅ | TQS/BIM/METHODUS/EBERICK detectados |
| D2: Grafo Estrutural | 7/10 | ✅ | Adjacência, lados A/B/C/D, herança dim |
| D3: Interpretação Pilares | 9/10 | ✅ | 6 regras PROD 100%, sides_data |
| D4: Interpretação Vigas | 6/10 | ⚠️ | viga_segs PROD, dim/name DEV 32-46% |
| D5: Interpretação Lajes | 4/10 | ❌ | Laje_name 6.9%, h= cluster funciona |
| D6: Motor Fase4 (cálculo) | 7/10 | ✅ | CalculationResult, DNA transform |
| D7: Geração DXF | 6/10 | ⚠️ | Robôs funcionam, cambotados ausentes |
| D8: Curadoria/QA | 5/10 | ⚠️ | Motor curadoria reconstruído |
| D9: Elementos Especiais | 2/10 | ❌ | Cambotado detector novo, não testado |
| D10: Pipeline Completo | 5/10 | ⚠️ | Orchestrator reconstruído |

**Score Total: 59/100** (era ~42 antes da recuperação)

---

## 2. GAPS CRÍTICOS (P0 — Bloqueadores de Produção)

### GAP-1: Laje_name accuracy = 6.9%
**Problema:** ML não funciona para nomes de laje (51 nomes únicos por projeto)
**Solução implementada:** `text_proximity_search.py` — busca bbox + regex
**Status:** Código escrito, não testado em produção
**Ação:** Executar `python -c "from core.vectorization.text_proximity_search import TextProximitySearch; ..."` em obras de treino

### GAP-2: Pilar_name accuracy = 32.8%
**Problema:** Nomes de pilares não detectados corretamente
**Hipótese:** Regex `^P\.?\d+[A-Z]?\b` muito restritiva para variantes como `P1.1`, `P-1`
**Solução:** Expandir regex no `ExtratorDXF.extrair()`
**Ação:** Adicionar `'^P\d+[\.\-]\d+'` e `'^P\-?\d+'` ao extrator

### GAP-3: Viga_dim accuracy = 46.4%
**Problema:** Dimensão de viga não é detectada em 53.6% dos casos
**Hipótese:** DXFs BIM têm dimensão em MTEXT com formato diferente
**Solução:** Expandir regex de dim no `GrafoEstrutural.construir()`

---

## 3. PRÓXIMAS SPRINTS

### SPRINT-A: TextProximitySearch em Produção (1-2 dias)
```
[ ] Testar TextProximitySearch nas 23 obras de treino
[ ] Medir % lajes com nome resolvido (meta: > 60%)
[ ] Integrar no agente_estrutural.py (Fase 3 → Fase 5 de lajes)
[ ] Commit resultados
```

### SPRINT-B: Expansão de Regex e DNA (2-3 dias)
```
[ ] Expandir regex de pilares (5 variantes novas)
[ ] Expandir regex de dimensões de vigas (MTEXT multilinha)
[ ] DNA key v2: testar normalização vs v1 em transformation_engine
[ ] Meta: Pilar_name > 60%, Viga_dim > 70%
```

### SPRINT-C: Elementos Especiais (2-3 dias)
```
[ ] Testar special_element_detector em obras com cambotados
[ ] Implementar forma de Pilar Cambotado no Bolt robot
[ ] Regras de transformação para PC, VC, MS
[ ] Documentar ficha do Pilar Cambotado
```

### SPRINT-D: Pavimento PI Integration (3-5 dias)
```
[ ] Criar parser de PDF para arquivos PI
[ ] Importar P.D., cota_saída, delimitação para pavimento_pi table
[ ] Integrar pe_direito_real no motor_fase4
[ ] Validar estimativas contra valores reais dos PDFs
```

### SPRINT-E: Production Gate (5-7 dias)
```
[ ] Score alvo: 85/100
[ ] E2E test: obra completa do ingestão ao DXF gerado
[ ] Comparar output vs ground truth (LEAF LOEFGREN / INDIANÓPOLIS)
[ ] Deploy em produção com Claude Code checkpoint
```

---

## 4. ARQUITETURA ALVO (v2.0)

```
DXF Input
    ↓
[TriadorDXF] Fase1→Fase2 (classifica e copia FORMAs)
    ↓
[AgenteEstrutural] Fase3 (ExtratorDXF → GrafoEstrutural → InterpretadorEstrutural)
    ↓
[TextProximitySearch] Fase3b (resolve Laje_name por proximidade)
    ↓
[SpecialElementDetector] Fase3c (detecta cambotados, misulas)
    ↓
[TransformationEngine] Fase4 (DNA prediction → campos preenchidos)
    ↓
[MotorFase4Enhanced] Fase4b (CalculationResult → pilar/viga/laje configs)
    ↓
[ObraKnowledge] Fase5 (salva no SQLite da obra)
    ↓
[PipelineOrchestrator] Fase6 (ThreadPool → Bolt/Crane/Slab robots)
    ↓
[QualityVerifier] Fase7 (valida DXFs gerados)
    ↓
DXF Output + RelatorioPI
```

---

## 5. MÉTRICAS DE SUCESSO

| Métrica | Atual | Meta | Medição |
|---------|-------|------|---------|
| Laje_name accuracy | 6.9% | 65% | test nas 23 obras |
| Pilar_name accuracy | 32.8% | 70% | test nas 23 obras |
| Viga_dim accuracy | 46.4% | 75% | test nas 23 obras |
| Chapas estimadas vs real | ±35% | ±15% | PI validation |
| Garfos estimados vs real | ±40% | ±20% | PI validation |
| Pipeline E2E success | ~60% | 90% | E2E test suite |
| Production score | 59/100 | 85/100 | CEO-AUDIT rubric |

---

## 6. HANDOFFS POR SQUAD

| Squad | Tarefa | Prioridade |
|-------|--------|------------|
| **CAD:CadFase3Interpretacao-AIOS** | Sprint-A: TextProximitySearch + Sprint-B: Regex | P0 |
| **CAD:ConcreteFormwork-AIOS** | Sprint-C: Cambotados + Spring-D: PI Integration | P1 |
| **CAD:CadPipelineOrchestrator-AIOS** | Sprint-E: Production Gate E2E | P2 |
| **CAD:FormworkEngineering-AIOS** | Validação estimativas vs PDFs reais | P1 |
| **Desenvolvimento:QA-AIOS** | Test suite E2E para cada fase | P2 |

---

## 7. DECISÕES ARQUITETURAIS (ADRs)

### ADR-001: SQLite por Obra (ObraKnowledge)
**Decisão:** Cada obra tem seu próprio SQLite, NÃO ChromaDB
**Razão:** Performance em acesso a dados estruturados, compatibilidade com pipeline offline
**Status:** CONFIRMADO

### ADR-002: DNA Key para Transformation Engine
**Decisão:** String de floats derivada de features geométricas → dna_frequency_map → most_common
**Razão:** Comprovadamente funciona para 8 regras PROD com accuracy 85-100%
**Status:** CONFIRMADO

### ADR-003: TextProximitySearch para Laje_name
**Decisão:** Bbox expansion + regex para resolver nomes, NÃO ML
**Razão:** ML atingiu máximo de 6.9% (51 nomes únicos por projeto — dados insuficientes por classe)
**Status:** IMPLEMENTADO, aguarda validação

### ADR-004: Elementos Especiais via SpecialElementDetector
**Decisão:** Módulo separado para cambotados/misulas, não integrado no regex principal
**Razão:** Frequência baixa (~3%) não justifica complexidade no extrator principal
**Status:** IMPLEMENTADO, aguarda validação
