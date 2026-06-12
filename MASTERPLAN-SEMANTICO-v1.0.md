# MASTERPLAN SEMÂNTICO — Vision-Estrutural AI
## Objetivo: Compreensão Semântica Global Flexível + ML Operacional
## CEO-PLANEJAMENTO (Athena) | 2026-05-24

---

## DIAGNÓSTICO DO ESTADO ATUAL

### O que JÁ existe (mais avançado do que parecia):

| Componente | Status | Localização |
|-----------|--------|-------------|
| FAISS indexes (pilares/vigas/lajes/estruturais) | ✅ OPERACIONAL | `data/vectors/faiss/` |
| SentenceTransformers (all-MiniLM-L6-v2) | ✅ DISPONÍVEL | `rag_commons.py` |
| PlausibilityChecker (similarity threshold) | ✅ IMPLEMENTADO | `rag_plausibility.py` |
| AnomalyDetector | ✅ IMPLEMENTADO | `rag_anomaly_detector.py` |
| PreStogGate (gate pré-geração DXF) | ✅ IMPLEMENTADO | `rag_pre_stog_gate.py` |
| parse_pi_pdfs.py (parser PDFs PI) | ✅ FUNCIONANDO | `scripts/parse_pi_pdfs.py` |
| FAISS corpus: 832 elementos estruturais, 11 obras | ✅ POPULADO | `estruturais.index` |
| pavimento_pi: 128 registros (6 obras) | ✅ POPULADO | `scripts/project_data.vision` |

### O que ESTÁ QUEBRADO:

| Componente | Problema | Prioridade |
|-----------|---------|-----------|
| ChromaDB | pydantic v1 incompatível Python 3.14 | HIGH |
| `src/cognitive/` (rag_dialectic, vector_trajectory, causal_engine) | Stubs sem implementação | MEDIUM |
| `transformation_rules` accuracy | Laje_name=6.9%, Pilar=32.8% | HIGH |
| `training_events` (805 eventos) | Armazenados mas NUNCA usados para reaprender | HIGH |
| `semantic_index.json` | Apenas 5 items, não consultado em decisões | MEDIUM |
| PreStogGate não integrado ao pipeline | Gate existe mas não é chamado | HIGH |
| pavimento_pi na DB errada | Scripts DB ≠ Main DB | MEDIUM |

### Filosofia confirmada (pelo usuário):
- Compreensão semântica **FLEXÍVEL** — cada obra é um caso
- Aprender com **possibilidades**, não impor regras rígidas
- **Proof-of-contamination** — robusto a outliers
- Gate semântico baseado em **área m²** (do PI/NSC), não contagem de elementos

---

## SPRINT A — Integrar PreStogGate + Unificar DBs (+5pts de maturidade)

**Objetivo:** Tornar o gate RAG existente parte obrigatória do pipeline

**Tarefas:**
1. Criar tabela `pavimento_pi` no DB principal (`Agente-cad-PYSIDE-Restored-main/project_data.vision`)
2. Migrar 128 registros do scripts DB para o principal
3. Integrar `PreStogGate.approve()` no `pipeline_e2e.py` antes da Fase 7 (geração DXF)
4. Adicionar --skip-gate flag para debug
5. Testar gate em 5 obras TREINO

**Gate:** `pipeline_e2e.py Obra_TREINO_1` passa pelo gate com resultado PASS

---

## SPRINT B — Knowledge Base Global Acumulativa

**Objetivo:** Toda obra processada enriquece o corpus semântico global

**Tarefas:**
1. Criar `data/knowledge_base.json` com estrutura:
   ```json
   {
     "meta": {"total_obras": 23, "ultima_atualizacao": "2026-05-24"},
     "por_tipo": {
       "pilar": {"pd_range": [2600, 5400], "area_range": [50, 800], "count": 228},
       "viga": {"pd_range": [2600, 5400], "area_range": [100, 1200], "count": 351},
       "laje": {"pd_range": [2600, 5400], "area_range": [50, 600], "count": 253}
     },
     "obras_indexadas": ["Obra_TREINO_1", ..., "Obra_TREINO_23"]
   }
   ```
2. Script `update_knowledge_base.py` — roda após cada obra certificada
3. Gate de plausibilidade usa `knowledge_base.json` como referência flexível (±2σ)
4. **NÃO rígido:** outliers são registrados, não bloqueados na primeira ocorrência

**Gate:** knowledge_base.json tem dados de >= 10 obras, gate funciona com tolerância configurável

---

## SPRINT C — Melhorar Accuracy das transformation_rules

**Objetivo:** Corrigir as regras de transformação com baixa accuracy

**Problema:**
- `Laje_name`: 6.9% accuracy → inutilizável
- `Pilar_name`: 32.8% → precário
- `Viga_name`: 32.3% → precário

**Tarefas:**
1. Extrair amostras corretas dos 805 `training_events`
2. Criar dataset limpo por tipo (pilar/viga/laje) com exemplos positivos/negativos
3. Re-treinar regras usando sklearn `DecisionTree` ou heurística baseada em padrões reais
4. Atualizar `transformation_rules` table com novas regras
5. Validar em obras held-out (TREINO_21/22/23)

**Gate:** Accuracy >= 70% em todos os tipos

---

## SPRINT D — Ingestão PDF NSC → Gate de Área

**Objetivo:** Usar dados NSC para validar que área gerada ≈ área vendida

**Dados disponíveis:**
- NSC339-24 (TREINO_1/Alimonti Paraiso)
- NSC 158-24 (TREINO_11/NIK Sunset) 
- NSC170-23 (TREINO_20/Arraia)
- NSC255-23 (TREINO_9/Nurban)
- NSC293-23 (TREINO_13/SKR Leaf) — 21 pavimentos
- NSC111-25 (TREINO_1/Quattri Indianopolis)

**Tarefas:**
1. Criar `parse_nsc_pdfs.py` (similar ao parse_pi_pdfs.py)
   - Extrair: `pd_por_pavimento`, `area_pilar_m2`, `area_viga_m2`, `area_laje_m2`, `referencia_projeto`
2. Criar gate de validação: `area_dxf_gerado / area_nsc_vendida` deve estar em range [0.70, 1.30]
3. Este range cresce com aprendizado — cada obra calibra o modelo
4. VP (fotos) = baixa prioridade, requer NIM vision — não neste sprint

**Gate:** Para TREINO_1, o gate de área valida com tolerância 30%

---

## SPRINT E — Fix ChromaDB + Migração Python 3.11

**Objetivo:** Corrigir stubs cognitivos quebrados

**Opções:**
1. **Opção A (recomendada):** Substituir ChromaDB por FAISS (já funciona) em memory_store.py
2. **Opção B:** Criar venv Python 3.11 separado só para ChromaDB
3. **Opção C:** Remover ChromaDB, usar apenas FAISS que já está operacional

**Tarefas (Opção A):**
1. Reescrever `memory_store.py` usando FAISS ao invés de ChromaDB
2. Implementar `src/cognitive/causal_engine.py` — correlações causais simples entre obras
3. `semantic_index.json`: crescer automaticamente após cada obra processada

**Gate:** memory_store.py funciona sem ChromaDB

---

## ORDEM RECOMENDADA

```
Sprint A (gate + DB unification) → imediato, desbloqueador
Sprint B (knowledge base) → depois do A, constrói base
Sprint C (transformation rules) → paralelo ao B
Sprint D (NSC ingestão) → depois do B
Sprint E (ChromaDB fix) → depois de ter A+B funcionando
```

---

## O que NÃO fazer

- Implementar regras rígidas de contagem (pilares por pavimento = X) — cada obra é um caso
- Usar ChromaDB sem resolver a incompatibilidade de pydantic
- Ignorar os 805 training_events que já foram coletados
- Criar nova infraestrutura RAG — já existe FAISS operacional com 832 elementos

---

*MASTERPLAN-SEMANTICO v1.0 | CEO-PLANEJAMENTO | 2026-05-24*
*Base: audit RAG completo do projeto, 6 obras com PDFs, FAISS 832 elementos*
