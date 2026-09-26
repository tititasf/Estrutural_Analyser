# MASTERPLAN CAD-ANALYZER v2.0 — Estado Real + Gap Analysis para ARETE

**Documento:** CEO-PLANEJAMENTO (Athena) — Auditoria Brownfield + Plano Atualizado
**Data:** 2026-03-05
**Versao:** 2.0 (substitui v1.0 que continha informacoes incorretas)
**Objetivo:** Pipeline end-to-end automatizado — pasta de obra DXF/PDF/fotos → DXFs de entrega prontos
**Status Geral:** EM CONSTRUCAO — Sprint 1 completo, Sprints 2-N pendentes

---

## PARTE 1 — REALIDADE ATUAL (O QUE REALMENTE EXISTE)

### 1.1 Estrutura de Pastas Real

```
D:/Agente-cad-PYSIDE/
├── src/
│   ├── core/
│   │   ├── adapters/          # Vazio (apenas __pycache__)
│   │   ├── auth/              # Autenticacao/DRM
│   │   ├── infra/             # Infraestrutura
│   │   ├── optimizers/        # base_optimizer.py, cutting_plan_optimizer.py
│   │   ├── reverse_engineering/ # Vazio
│   │   ├── schemas/           # Schemas de dados
│   │   ├── security/          # Seguranca/DRM
│   │   ├── services/          # Vazio
│   │   ├── storage/           # Persistencia
│   │   ├── vectorization/     # Vazio (planejado, nao implementado)
│   │   └── verification/      # Validacoes
│   ├── adapters/
│   │   └── fase3_to_fase4_pilares.py    [NOVO - Sprint 1]
│   ├── engines/               # Vazio
│   ├── pipeline/
│   │   ├── ficha_pilares_schema.py      [NOVO - Sprint 1]
│   │   └── ficha_pilares_reviewer.py    [NOVO - Sprint 1]
│   └── ui/                    # Interface PySide6 existente (monolitica)
├── tests/
│   └── test_fase4_adapter.py            [NOVO - Sprint 1] 10/10 PASS
├── project_data.vision                  # SQLite DB principal
├── DADOS-OBRAS/               # 23 obras de treino + formatos
├── _ROBOS_ABAS/               # 4 robos executaveis
│   ├── Robo_Pilares/          # PilarAnalyzer.exe
│   ├── Robo_Laterais_de_Vigas/
│   ├── Robo_Fundos_de_Vigas/
│   └── Robo_Lajes/
└── MASTERPLAN-CAD-ANALYZER-SQUADS.md   # Versao 1.0 (desatualizada)
```

### 1.2 O que foi IMPLEMENTADO no Sprint 1

| Arquivo | Status | Funcionalidade |
|---------|--------|----------------|
| `src/pipeline/ficha_pilares_schema.py` | COMPLETO | FichaFase3Pilar dataclass + validacao + mapeamento para robos |
| `src/adapters/fase3_to_fase4_pilares.py` | COMPLETO | Adapter CLI Fase3→Fase4, gera 4 JSONs para PilarAnalyzer.exe |
| `src/pipeline/ficha_pilares_reviewer.py` | COMPLETO | Revisor interativo CLI com geracao de pares de treino |
| `tests/test_fase4_adapter.py` | 10/10 PASS | Testes unitarios + integracao completos |

**Outputs do adapter (Fase 4):**
- `obras_salvas.json` — formato nativo PilarAnalyzer.exe
- `pilares_salvos.json` — chave composta `{numero}_{pavimento}`
- `pavimentos_lista.json` — lista de pavimentos ordenada
- `relatorio_validacao.json` — relatorio de fichas com erros

### 1.3 Banco de Dados SQLite — Estado Real

**Arquivo:** `project_data.vision`

| Tabela | Registros | Observacao |
|--------|-----------|------------|
| pillars | 6.524 | Pilares interpretados de projetos |
| beams | 7.005 | Vigas interpretadas |
| slabs | 4.637 | Lajes interpretadas |
| projects | 150 | Projetos/obras cadastrados |
| training_events | 805 | Correcoes humanas disponíveis para treino |
| transformation_rules | **0** | VAZIO — PROBLEMA CRITICO |
| transformation_rules_backup_20260214_162533 | 6 | Backup de regras antigas (schema diferente!) |
| generated_scripts | ? | Scripts SCR gerados |
| rule_evaluation_log | ? | Log de avaliacoes de regras |
| rule_index | ? | Indice de regras |

**DESCOBERTA CRITICA:** A tabela `transformation_rules` foi esvaziada em algum momento. Ha um backup de 14/02/2026 com 6 regras, mas o schema mudou — as 6 regras do backup nao podem ser simplesmente copiadas.

### 1.4 Training Events — Estrutura Real

```json
{
  "level_1_project": {
    "id": "uuid",
    "pavement": "P-1",
    "work_name": "Unknown"
  },
  "level_2_item": {
    "type": "Pilar",
    "name": "P1",
    "geometry": null,
    "pos": null,
    "neighbors": [],
    "dna_vector": [1.0, 5.0, 496.0, 80.47]
  },
  "level_3_field": {
    "field_name": "name",
    "link_type": "label",
    "local_geometry": null
  },
  "target_label": "P1"
}
```

**Distribuicao por tipo de campo (805 eventos):**
| Campo (role) | Eventos | Prioridade |
|-------------|---------|-----------|
| Laje_laje_outline_segs | 187 | ALTA |
| Laje_laje_dim | 130 | ALTA |
| Laje_name | 88 | ALTA |
| Viga_viga_segs | 77 | ALTA |
| Pilar_name | 58 | MEDIA |
| Pilar_dim | 55 | MEDIA |
| Pilar_pilar_segs | 41 | MEDIA |
| Laje_laje_nivel | 36 | MEDIA |
| Viga_name | 31 | MEDIA |
| Viga_dim | 28 | MEDIA |
| Pilar_p_sA/sB/sC/sD_* (connections) | 70+ | ALTA — accuracy baixa |

### 1.5 Robos — Estado Real Descoberto

**PilarAnalyzer.exe:**
- NAO tem modo CLI headless — abre janela GUI de login obrigatoriamente
- Possui sistema de DRM/creditos (`CreditSystem`)
- Le dados de arquivos `.pkl` (pickle) e `.json` na mesma pasta
- A integracao atual requer passar pela GUI do executavel

**Implicacao:** A Fase 5 (execucao dos robos) NAO pode ser 100% automatizada por CLI sem modificar/reconstruir os robos ou encontrar forma de interagir com a GUI programaticamente.

### 1.6 Estrutura Real das Obras (8 Fases, nao 7)

A estrutura real das pastas de obra revela **8 fases**, nao 7 como planejado:

```
DADOS-OBRAS/{nome_obra}/
  Fase-1_Ingestao/
  Fase-2_Triagem/
  Fase-3_Interpretacao_Extracao/
  Fase-4_Sincronizacao/           <- "Dados_Sync_Robos" no formato exemplo
  Fase-5_Geracao_Scripts/
  Fase-6_Execucao_CAD/            <- Execucao no AutoCAD via scripts .scr
  Fase-7_Consolidacao/
  Fase-8_Revisao_Entrega/         <- FASE EXTRA nao documentada na v1.0
```

---

## PARTE 2 — GAPS CRITICOS PARA ARETE (GAP ANALYSIS)

### GAP-1: TransformationEngine [BLOQUEADOR CRITICO]
**Impacto:** Sem regras de transformacao, o sistema nao consegue converter interpretacoes para formato dos robos
**Status atual:** transformation_rules VAZIO; backup tem schema antigo incompativel
**O que precisa ser feito:**
- Criar `src/pipeline/transformation_engine.py` — le 805 training_events, deriva regras por campo/entidade
- Popula `transformation_rules` com `rule_logic` JSON estatistico (frequency map por DNA vector)
- Schema correto: `name, entity_type, description, rule_logic (JSON), version, coverage_pct, accuracy_pct, status, is_production`

### GAP-2: Interpretacao Fase 3 — Accuracy Real Desconhecida [CRITICO]
**Impacto:** Usuario confirmou que "a interpretacao ta toda errada" apesar de confidence scores altos
**Status atual:** Codigo de interpretacao esta OFUSCADO (DRM) em `src_raw_backup/core/`
**Campos com accuracy mais baixa:**
- Conexoes laterais (`p_sB/sC confidence 0.22–0.47`) — vigas/lajes adjacentes ao pilar
- Laje outline segments (187 correcoes — mais problematico)
- Nomes de lajes e vigas nos lados do pilar
**O que precisa ser feito:**
- TransformationEngine (GAP-1) e pre-requisito
- Revisor interativo (ja implementado no Sprint 1) precisa ser integrado ao fluxo
- Dataset de ground truth por obra treinamento
- Pipeline de retreinamento baseado em correcoes

### GAP-3: Fichas de Vigas e Lajes [IMPORTANTE]
**Status atual:** Sprint 1 implementou apenas pilares (FichaFase3Pilar)
**O que precisa ser feito:**
- `FichaFase3Viga` dataclass + adapter + testes
- `FichaFase3Laje` dataclass + adapter + testes
- Reviewers equivalentes para vigas e lajes
- Os robos de vigas e lajes tem formatos proprios (a mapear)

### GAP-4: Robos sem CLI Headless [BLOQUEADOR para automacao total]
**Status atual:** PilarAnalyzer.exe requer GUI + DRM login
**Opcoes:**
1. Pyautogui/win32com para interagir com a GUI (fragil, ja existe precedente no codigo)
2. Reconstruir logica dos robos em Python puro (complexo, bypassa DRM)
3. Criar wrapper que pre-popula os PKL e aciona o EXE com GUI automatizada
4. Investigar se existe modo batch/CLI nao documentado nos parametros do EXE

### GAP-5: Fases 1, 2, 5, 6, 7, 8 — Nao Implementadas [BACKLOG]
**Status atual:** Nenhuma das fases de pipeline tem codigo Python funcional
**O que precisa ser feito por fase:**

| Fase | O que construir |
|------|----------------|
| Fase 1 | Ingestor DXF (ezdxf) + extrator PDF (pdfminer) + extrator foto (vision API) |
| Fase 2 | Separador de pavimentos + limpeza de layers + nomeacao |
| Fase 5 | Executor de robos (wrapper GUI ou CLI se descoberto) |
| Fase 6 | Executor AutoCAD via scripts .scr ou DXF merger direto |
| Fase 7 | Unificador DXF por classe (ezdxf merge) |
| Fase 8 | Validador geometrico + relatorio de qualidade |

### GAP-6: Vectorizacao e ChromaDB — Nao Existe
**Status atual:** `src/core/vectorization/` esta VAZIO; nenhuma colecao ChromaDB existe
**Impacto:** O masterplan v1.0 planejou extenso uso de ChromaDB, mas o sistema real usa apenas SQLite
**Decisao necessaria:** Manter plano ChromaDB ou simplificar para SQLite puro?

### GAP-7: Pipeline Orchestrator — Nao Existe
**Status atual:** Nao ha estado de pipeline persistente por obra
**O que precisa ser feito:**
- Tabela `obras` e `pipeline_state` no SQLite
- CLI: `python main.py --obra /caminho/obra --fase N` (retomavel)
- Monitor de progresso

### GAP-8: Squads AIOS — Nao Criados no Repositorio CAD
**Status atual:** Os 17 squads foram planejados na Diana Corporacao Senciente, mas nao existem arquivos de squad no repositorio `D:/Agente-cad-PYSIDE/`
**O que precisa ser feito:** Criar `squads/` no repo CAD com definicoes AIOS dos agentes

---

## PARTE 3 — ARQUITETURA CORRIGIDA

### 3.1 Pipeline de 8 Fases (Versao Correta)

```
OBRA (pasta DXFs/PDFs/fotos/eng-reversa)
        |
        v
[FASE 1] Ingestao — ezdxf + pdfminer + vision
        |
        v
[FASE 2] Triagem — separar pavimentos / detalhes / docs
        |
        v
[FASE 3] Interpretacao e Extracao — pilares, vigas, lajes (CRITICO)
         + TransformationEngine (GAP-1)
         + Revisao Humana (ja implementada)
        |
        v
[FASE 4] Sincronizacao — fichas -> formato especifico de cada robo
         FichaFase3Pilar -> obras_salvas.json (Sprint 1 COMPLETO para pilares)
        |
        v
[FASE 5] Geracao de Scripts .SCR — robos geram scripts AutoCAD
         (requer resolver GAP-4: robos sem CLI headless)
        |
        v
[FASE 6] Execucao CAD — rodar scripts no AutoCAD (win32com ou DXF direto)
        |
        v
[FASE 7] Consolidacao — unificar DXFs por classe
        |
        v
[FASE 8] Revisao e Entrega — validacao geometrica + aprovacao humana
        |
        v
DXFs FINAIS: Pilares | Vigas-Laterais | Vigas-Fundos | Garfos | Lajes
```

### 3.2 Componentes Core a Construir

```
src/
├── pipeline/
│   ├── ficha_pilares_schema.py      [EXISTE - Sprint 1]
│   ├── ficha_pilares_reviewer.py    [EXISTE - Sprint 1]
│   ├── ficha_vigas_schema.py        [FALTA - GAP-3]
│   ├── ficha_vigas_reviewer.py      [FALTA - GAP-3]
│   ├── ficha_lajes_schema.py        [FALTA - GAP-3]
│   ├── ficha_lajes_reviewer.py      [FALTA - GAP-3]
│   └── transformation_engine.py    [FALTA - GAP-1 CRITICO]
├── adapters/
│   ├── fase3_to_fase4_pilares.py    [EXISTE - Sprint 1]
│   ├── fase3_to_fase4_vigas.py      [FALTA - GAP-3]
│   └── fase3_to_fase4_lajes.py      [FALTA - GAP-3]
├── phases/
│   ├── fase1_ingestao.py            [FALTA]
│   ├── fase2_triagem.py             [FALTA]
│   ├── fase3_interpretacao.py       [FALTA - codigo obfuscado]
│   ├── fase4_sincronizacao.py       [FALTA - parcialmente via adapter]
│   ├── fase5_geracao_scripts.py     [FALTA - requer GAP-4]
│   ├── fase6_execucao_cad.py        [FALTA]
│   ├── fase7_consolidacao.py        [FALTA]
│   └── fase8_revisao.py             [FALTA]
├── robos/
│   ├── robo_pilares_wrapper.py      [FALTA - GAP-4]
│   ├── robo_vigas_laterais_wrapper.py [FALTA]
│   ├── robo_vigas_fundos_wrapper.py [FALTA]
│   └── robo_lajes_wrapper.py        [FALTA]
└── orchestrator/
    └── pipeline_orchestrator.py     [FALTA - GAP-7]
```

### 3.3 SQLite — Tabelas a Criar/Corrigir

```sql
-- OBRAS (nao existe ainda)
CREATE TABLE obras (
    id TEXT PRIMARY KEY,
    nome TEXT,
    pasta_origem TEXT,
    data_ingestao TIMESTAMP,
    fase_atual INTEGER DEFAULT 1,
    status TEXT DEFAULT 'iniciado'  -- iniciado|em_processamento|pausado|completo|erro
);

-- PIPELINE STATE (nao existe ainda)
CREATE TABLE pipeline_state (
    obra_id TEXT PRIMARY KEY,
    fase_atual INTEGER DEFAULT 1,
    fases_completas TEXT DEFAULT '[]',  -- JSON array
    fase_em_andamento TEXT,             -- JSON com detalhes
    ultima_atualizacao TIMESTAMP,
    FOREIGN KEY (obra_id) REFERENCES obras(id)
);

-- FICHAS FASE 3 (nao existe ainda - dados estao em pillars/beams/slabs)
CREATE TABLE fase3_fichas (
    id TEXT PRIMARY KEY,
    obra_id TEXT,
    pavimento TEXT,
    tipo TEXT,  -- pilar|viga|laje
    codigo TEXT,
    dados_json TEXT,
    confidence REAL,
    revisado BOOLEAN DEFAULT FALSE,
    revisado_por TEXT,
    data_revisao TIMESTAMP
);
```

---

## PARTE 4 — BACKLOG PRIORIZADO PARA ARETE

### SPRINT 2 (PROXIMO) — TransformationEngine [BLOQUEADOR CRITICO]

**Objetivo:** Derivar e persistir regras de transformacao a partir dos 805 training_events

**Story 2.1 — TransformationEngine Core** (Complexidade: 8)
- Criar `src/pipeline/transformation_engine.py`
- Le todos os training_events do SQLite
- Agrupa por `role` (tipo de campo)
- Para cada role, cria frequency map: DNA vector → target_value mais frequente
- Calcula `coverage_pct` e `accuracy_pct` por regra
- Persiste na tabela `transformation_rules` com `rule_logic` JSON
- Threshold minimo: regra publicada so se coverage >= 10 eventos

**Story 2.2 — Tests TransformationEngine** (Complexidade: 3)
- `tests/test_transformation_engine.py`
- Teste: engine deriva pelo menos 10 regras dos 805 eventos
- Teste: regras para campos mais frequentes (Laje_name, Pilar_name, etc.)
- Teste: `apply_rule()` retorna valor correto para DNA vector conhecido

**Story 2.3 — Integracao no Adapter** (Complexidade: 5)
- Atualizar `fase3_to_fase4_pilares.py` para consultar TransformationEngine
- Quando confidence < 0.7 E regra existe: aplicar regra automaticamente
- Quando confidence < 0.7 E nenhuma regra: marcar para revisao humana
- Teste: adapter com obra real Obra_TREINO_1

### SPRINT 3 — Fichas de Vigas e Lajes [IMPORTANTE]

**Story 3.1 — FichaFase3Viga** (Complexidade: 5)
- Schema de viga: codigo, tipo (retangular/L/T), secao, comprimento, tramos, armadura positiva/negativa, estribos, garfos
- Validacao: largura >= 12cm, altura >= 25cm
- Adapter fase3→fase4 para formato Robo_Laterais e Robo_Fundos
- Testes equivalentes aos de pilares

**Story 3.2 — FichaFase3Laje** (Complexidade: 5)
- Schema de laje: codigo, tipo, dimensoes, espessura, armadura, direcao
- Adapter fase3→fase4 para formato Robo_Lajes
- Testes equivalentes

### SPRINT 4 — Pipeline Orchestrator [IMPORTANTE]

**Story 4.1 — Tabelas SQLite** (Complexidade: 3)
- Migration para criar `obras` e `pipeline_state`
- Script: `migrations/003_pipeline_state.sql`

**Story 4.2 — Orchestrator Core** (Complexidade: 8)
- `src/orchestrator/pipeline_orchestrator.py`
- Resume pipeline de onde parou por obra
- CLI: `python -m src.orchestrator.pipeline_orchestrator --obra Obra_TREINO_1 --fase 3`

### SPRINT 5 — Robos Wrapper [BLOQUEADOR para automacao total]

**Story 5.1 — Investigar PilarAnalyzer.exe** (Complexidade: 5)
- Testar se existe modo batch/silent via flags nao documentadas
- Analisar o .pkl format — entender se da pra substituir a leitura de PKL por JSON
- Testar pyautogui wrapper para login automatico (DRM)
- Documentar: qual a forma mais viavel de automatizar?

**Story 5.2 — Wrapper de Pilares** (Complexidade: 8)
- Baseado no resultado de 5.1, implementar `src/robos/robo_pilares_wrapper.py`
- Input: obras_salvas.json + pilares_salvos.json (ja gerados pelo adapter)
- Output: DXF/SCR de pilares
- Com retry em caso de falha

### SPRINT 6 — Fases 1 e 2

**Story 6.1 — Ingestor DXF** (Complexidade: 8)
- `src/phases/fase1_ingestao.py`
- Usa ezdxf para extrair entities de DXFs
- Cataloga: pilares (blocks/text), vigas (lines/polylines), lajes (hatches/polylines)
- Salva entities no SQLite

**Story 6.2 — Triagem de Pavimentos** (Complexidade: 8)
- `src/phases/fase2_triagem.py`
- Detecta e nomeia pavimentos automaticamente
- Separa detalhes de pavimentos estruturais
- Cria indice espacial por pavimento

### SPRINTS 7-10 — Fases 5, 6, 7, 8

(Dependem da resolucao de GAP-4 — robos sem CLI headless)

---

## PARTE 5 — DECISOES PENDENTES (REQUEREM INPUT HUMANO)

| # | Decisao | Opcoes | Impacto |
|---|---------|--------|---------|
| D1 | Como automatizar robos sem CLI headless? | (a) pyautogui wrapper; (b) reconstruir em Python; (c) interagir via AutoCAD COM diretamente | Bloqueia Fases 5-8 |
| D2 | Usar ChromaDB ou SQLite puro? | (a) ChromaDB para vetorizacao semantica; (b) SQLite simples com JSON | Impacta Fase 1-3 |
| D3 | Interpretacao Fase 3 — LLM ou regras? | (a) LLM com prompts otimizados; (b) regras deterministicas do TransformationEngine; (c) hibrido | Core do negocio |
| D4 | Dataset de ground truth — como criar? | (a) revisor interativo (ja implementado); (b) importar dados das 23 obras de treino direto do SQLite | Velocidade do treino |

---

## PARTE 6 — ARETE SCORECARD (ESTADO ATUAL)

| Dimensao | Peso | Score Atual | Meta | Gap |
|----------|------|-------------|------|-----|
| Funcionalidade E2E | 10 | 1/10 | 9/10 | CRITICO |
| Accuracy Interpretacao (F3) | 10 | 2/10 | 8/10 | CRITICO |
| Automacao (sem intervencao humana) | 9 | 1/10 | 7/10 | ALTO |
| Robustez / Tratamento de Erros | 8 | 4/10 | 7/10 | MEDIO |
| Cobertura de Testes | 7 | 3/10 | 7/10 | MEDIO |
| Qualidade do Codigo | 7 | 5/10 | 7/10 | MEDIO |
| Performance / Velocidade | 6 | 5/10 | 7/10 | MEDIO |
| Documentacao | 5 | 3/10 | 6/10 | BAIXO |
| **MEDIA PONDERADA** | | **2.8/10** | **7.5/10** | **CRITICO** |

**Diagnose ARETE:** Sistema em estado inicial de construcao. Os 3 sprints proximos (TransformationEngine + Fichas V/L + Pipeline Orchestrator) devem elevar o score para ~5.5/10. Automacao completa so possivel apos resolver GAP-4 (robos headless).

---

## PARTE 7 — PROXIMOS PASSOS IMEDIATOS

### Esta Sessao / Proximo Sprint

```
PRIORIDADE 1 (CRITICO — desbloqueia tudo):
  CEO-DESENVOLVIMENTO -> @dev:
    Criar src/pipeline/transformation_engine.py
    - Le 805 training_events
    - Deriva regras por role/campo
    - Persiste em transformation_rules
    - Testa com obra real

PRIORIDADE 2 (Logo apos P1):
  CEO-DESENVOLVIMENTO -> @dev:
    Criar FichaFase3Viga + FichaFase3Laje
    Adapters equivalentes aos de pilares
    Testes 10/10 PASS

PRIORIDADE 3 (Paralelo):
  Investigar PilarAnalyzer.exe — modos de automacao
  Testar obras reais pelo revisor interativo (gerar dataset ground truth)
```

---

## PARTE 8 — RASTREAMENTO DE DESCOBERTAS

### Descobertas Criticas da Sessao de Pesquisa (2026-03-05)

| # | Descoberta | Impacto | Acao |
|---|-----------|---------|------|
| D1 | transformation_rules VAZIO (0 regras) | Accuracy Fase 3 ruim tem causa raiz aqui | Implementar TransformationEngine |
| D2 | Backup de regras com schema antigo (6 regras de fev/2026) | Schema mudou, nao da pra restaurar direto | Usar training_events para derivar novas regras |
| D3 | PilarAnalyzer.exe requer GUI + DRM login | Automacao total bloqueada | Investigar opcoes (pyautogui/win32com) |
| D4 | Obra tem 8 fases, nao 7 | Masterplan v1.0 errado | Corrigido neste documento |
| D5 | src/core/vectorization/ esta VAZIO | ChromaDB nunca foi implementado | Decidir se usa ChromaDB ou SQLite |
| D6 | 805 training_events ja existem com DNA vectors | Base para TransformationEngine esta pronta | Sprint 2 priority |
| D7 | Confidence baixa em conexoes (sides B/C) | lajes/vigas adjacentes ao pilar falham mais | Focar TransformationEngine nestes campos |
| D8 | Codigo de interpretacao (Fase 3) e ofuscado/DRM | Nao editavel diretamente | Melhorar via TransformationEngine que e chamado externamente |

---

*Masterplan v2.0 — CEO-PLANEJAMENTO (Athena) — Diana Corporacao Senciente*
*Atualizado: 2026-03-05 | Substitui: MASTERPLAN-CAD-ANALYZER-SQUADS.md*
