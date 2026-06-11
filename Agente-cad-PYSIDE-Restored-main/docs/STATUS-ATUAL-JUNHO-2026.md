# CAD-ANALYZER — Status Atual & Próximos Passos
**Data:** 2026-06-07 | **Revisado por:** Claude Code (sessão de revisão)

---

## 1. Visão Geral do Sistema

CAD-ANALYZER automatiza a produção de formas de concreto estrutural a partir de DXFs brutos de engenharia civil.
Ciclo completo: `DXF bruto → interpretação → Fase-4 JSON → gerador de DXF STOG → fidelidade vs referência humana`.

### Arquitetura de Abas (8 módulos)

| Tab | Nome | Responsabilidade |
|-----|------|-----------------|
| 0 | Gerenciar Projetos | Onboarding obra, indexação, triagem, DWG→DXF |
| 1 | Diagnostic Hub (Pré) | Recortes DBSCAN, canvas BRUTO/LIMPO/DETALHES, **⚡ Interpretar Obra Toda** |
| 2 | Structural Analyzer | Análise Fase-3 por pavimento, listas Pilar/Viga/Laje, DetailCard |
| 3 | Comparison Engine (Pós) | Validação visual + NIM, scores Forward×Reverse, certificação |
| 4 | Robo Pilares | Gerador SCR CIMA/ABCD/GRADES para AutoCAD |
| 5 | Robo Laterais de Viga | Gerador LV (vigas laterais) |
| 6 | Robo Fundo de Vigas | Gerador FV (fundos de vigas) |
| 7 | Robo Laje | Gerador LJ (lajes + pontaletes) |

### Stack Técnico

| Componente | Tecnologia |
|-----------|-----------|
| UI | PySide6 (Qt6) |
| DXF | ezdxf + accoreconsole (DWG→DXF) |
| DB | SQLite (`D:/Agente-cad-PYSIDE/project_data.vision`) |
| Vector RAG | LanceDB + NVIDIA NIM (4096-dim) |
| Geometria | Shapely |
| Motores Fase-3 | DXFLoader, SpatialIndex, ContextEngine, PillarAnalyzer, BeamTracer, SlabTracer, PillarPerspectiveMapper |

---

## 2. O Que Está CONCLUÍDO E OPERACIONAL

### 2.1 Geradores STOG (Fase 5) — 100% certificados em 20 obras

| Gerador | Script | Entidades | Status |
|---------|--------|-----------|--------|
| Pilares | `gerar_pl_dxf_stog.py` | 2.247/obra | ✅ CERTIFICADO |
| Vigas Laterais | `gerar_lv_dxf_stog.py` | 8.237/obra | ✅ CERTIFICADO |
| Fundos de Vigas | `gerar_fv_dxf_stog.py` | 686/obra | ✅ CERTIFICADO |
| Lajes | `gerar_lj_dxf_stog.py` | 596/obra | ✅ CERTIFICADO |

**Obra_TREINO_20**: score 100%, fidelidade 87.7 — referência de qualidade.

### 2.2 Sistema de Fidelidade (Fase 7) — Todas as classes APROVADAS

| Classe | Aprovados | Threshold |
|--------|-----------|-----------|
| PIL | 15/15 | 85% |
| LAJ | 16/17 | 75% |
| VIG | 19/19 | 82% |
| LV sub | 19/19 | 85% |
| FV sub | 19/19 | 80% |

### 2.3 Comparison Engine (Forward × Reverse)
- `comparar_fichas.py` com score rigoroso: MATCH/(MATCH+DELTA+AUSENTE_REV)
- Mapeamento canônico PIL/VIG/LAJ confirmado em 10 obras
- Scores representativos: TREINO_5=100%, TREINO_16=90.6%, TREINO_1=89.3%

### 2.4 STOG Intelligence / RAG Global
- `stog_intelligence_extractor.py` v1.0 — extrai KB por DXF
- LanceDB `stog_rag_db/stog_kbs` — 548 KBs, 4096-dim NVIDIA NIM
- Hybrid search BM25+dense operacional
- `domain_knowledge` — 217 chunks, 9 doc_types

### 2.5 DWG→DXF Pipeline
- accoreconsole.exe + DXFOUT (sem ODA)
- 22 obras auditadas, 0 erros de conversão
- Fix chars acentuados + UnicodeEncodeError

### 2.6 Semântica Validada (Sprint 1 — 2026-06-04)
- `docs/SEMANTICA-PILAR-NOVA.md` — faces A/B=longas, C/D=curtas, grade_1=comp+22
- `docs/SEMANTICA-VIGA-NOVA.md` — segmentação 120cm, pillar_left/right cruzamento
- `docs/SEMANTICA-LAJE-NOVA.md` — linhas_verticais CUMULATIVAS, is_union ≤30cm
- Bugs B1+LV-B2 corrigidos em `motor_fase4.py`

### 2.7 Pipeline E2E
- `pipeline_e2e.py`: pipeline completo F1→F8, NON_BLOCKING para fases não-críticas
- 116/116 pavimentos APROVADO em batch
- `pipeline_batch.py`: processamento multi-obra

### 2.8 Triagem + Recortes (Fase 2) — MAJORITARIAMENTE COMPLETO

**Triagem:**
- UI dual-panel: sugestões IA + confirmados
- `obra_triagem` DB populada: TREINO_1 (40 entradas), TREINO_12 (11 entradas)
- Aprovação individual + batch "≥80%" implementada
- Downstream: brutos aprovados → Diagnostic Hub

**Recortes (Fase 2b):**
- `scripts/obra_crop_engine.py` — DBSCAN auto-crop
- `obra_recortes` DB: 18 rows (Obra_TREINO_1, 9 pavimentos × 2 tipos = torre+detalhe)
- Diagnostic Hub: 3 canvas tabs (BRUTO | LIMPO | DETALHES)
- Recorte manual + automático com QProgressBar

### 2.9 DB Status (project_data.vision)

| Tabela | Linhas | Descrição |
|--------|--------|-----------|
| `pillars` | 6.524 | Pilares com sides_data, links, fields |
| `beams` | 7.005 | Vigas com segmentos e fields |
| `slabs` | 4.637 | Lajes com contorno e fields |
| `projects` | 10 | Projetos (1 por pavimento da obra) |
| `works` | 24 | Obras indexadas |
| `obra_recortes` | 18 | Recortes aprovados Obra_TREINO_1 |
| `obra_triagem` | 51 | Triagem TREINO_1 + TREINO_12 |
| `fase3_fichas` | 405 | Fichas Fase-3 (dado estrutural extraído) |
| `dxf_entidades` | 1.928.880 | Cache de entidades DXF |

### 2.10 EPIC CAD-10 — Ficha Integrada (COMPLETO 2026-05-19)

Todas as 6 stories completadas:
- CAD-10.1: `field_mapping.py` — mapeamento Fase-4 → DetailCard ✅
- CAD-10.2: `_import_fase4_to_db()` — importação automática ✅
- CAD-10.3: Botão "🚀 Iniciar Análise Geral" expandido ✅
- CAD-10.4: Comparison Panel na Ficha ✅
- CAD-10.5: Comparison Engine renovado ✅
- CAD-10.6: Realimentação do Interpretador ✅

### 2.11 Diagnostic Hub Sprint 1 (2026-06-05) — CONCLUÍDO

Hub redesenhado com:
- 3 painéis: ComboBox + canvas BRUTO/LIMPO/DETALHES + painel recortes
- DBSCAN crop engine operacional
- `obra_recortes` DB
- `request_open_bruto` signal
- 38 recortes validados em produção

### 2.12 ⚡ Interpretar Obra Toda (implementado 2026-06-07 — ESTA SESSÃO)

**`PreProcessAllWorker._process()` expandido para Caminho A completo:**

```
Por torre (DXF aprovado):
  1. DXFLoader → texts + polylines + lines
  2. SpatialIndex
  3. detect_pilares_from_polylines() → Shapely + nome/dim por proximidade + PillarPerspectiveMapper
  4. BeamTracer.detect_beams() + process_beam_intelligent() → 12 campos semânticos
  5. SlabTracer.detect_slabs_from_texts() + process_slab_intelligent() → dim/nível/contorno

Por pavimento (após todas torres):
  6. correlate_sides_data() → vigas ↔ lados A/B/C/D de cada pilar
  7. run_sanity_checks() → issues de dimensão/nível por pilar
  8. _get_or_create_project_id() → lookup projects por (obra, pav) ou cria novo
  9. db.save_pillar() + db.save_beam() + db.save_slab()
 10. Ficha completa com contagens reais + resumo semântico
 11. pre_processamento_estado.json salvo em DADOS-OBRAS/{obra}/
```

**`src/core/analysis_helpers.py` criado** com funções puras standalone:
- `extract_float()`, `run_sanity_checks()`, `process_beam_intelligent()`
- `process_slab_intelligent()`, `correlate_sides_data()`, `detect_pilares_from_polylines()`

**Botão "🧠 Interpretar com Contexto"** adicionado ao Structural Analyzer:
- Lê `pre_processamento_estado.json` da obra ativa
- Injeta contexto (totais, dados por pavimento, resumo) antes da análise
- Chama `process_pillars_action()` com contexto pré-carregado

---

## 3. O Que Está PENDENTE

### 3.1 Fase 1 — RAG Pipeline por-Obra (EPIC 1 — P0)

**Infraestrutura**: COMPLETA. Faltam apenas os scripts de embedding/classificação.

| Item | Script | Status |
|------|--------|--------|
| E1.1 | `obra_rag_utils.py` (base compartilhada embed + schemas) | ❌ PENDENTE |
| E1.2 | `obra_pdf_ingestor.py` (PDFs/MDs → LanceDB por-obra) | ❌ PENDENTE |
| E1.3 | `obra_dxf_classifier.py` (3 camadas: nome→ezdxf→embedding) | ❌ PENDENTE |
| E1.4 | `obra_triagem_populator.py` (integrar output E1.3) | ⚠️ PARCIAL — existe mas sem E1.3 como fonte |
| E1.5 | `obra_rag_pipeline.py` (orquestrador com progress callback) | ❌ PENDENTE |
| E1.6 | UI: botão "Processar RAG Semântico" na Fase 1 | ❌ PENDENTE |

**Impacto**: Sem RAG por-obra, EPIC 3 (Design System) e EPIC 4 (Hub RAG-aware) ficam bloqueados.

### 3.2 Fase 2 — Itens Residuais

| Item | Status |
|------|--------|
| E2.8 Motor semântico de detalhes (extrai anotações dos detalhes.dxf) | ❌ FUTURO |
| D2 Reaproveitar aprovações (hash + cache) | ❌ ABERTO |

### 3.3 Diagnostic Hub — Melhorias

- `PreProcessAllWorker` não tem flag `force=True` atualmente — processa sempre tudo
- Sem skip de pavimentos já processados (verificar se `pre_processamento_estado.json` existe)
- `pavement_name` no DB usa o nome do arquivo DXF inteiro, não um nome limpo (ex: "FUN", "TER")

### 3.4 EPIC 3 — Design System Diagnostic Hub (P1 — planejado)

Entregas pendentes: sidebar redesenhada, canvas toolbar, painel RAG colapsável, barra pipeline.
**Bloqueado por:** EPIC 1 (RAG por-obra necessário para painel de contexto).

### 3.5 EPIC 4 — Diagnostic Hub Funcionalidades RAG (P2 — planejado)

Integração RAG no carregamento DXF, sugestão de renderização, pré-interpretação automática,
auto-pipeline para DXFs de alta confiança, batch processing.
**Bloqueado por:** EPIC 3.

### 3.6 EPIC 5 — Masterplan Fase 3 + Structural Analyser (P2 — planejado)

Especificação completa Fase 3, granularidade de validação, ciclo correction_log → RAG global,
RAG retroalimenta interpretações, critérios Areté (precision ≥95%, recall ≥90%).

### 3.7 EPIC 6 — Design System Structural Analyser (P2 — planejado)

Layout campo-a-campo, feedback visual (verde/amarelo/vermelho), painel RAG global,
histórico de correções, comparativo visual lado-a-lado.

### 3.8 EPIC 7 — Comparison Engine N1/N2/N3/N4 + Classes Novas (P3 — planejado)

| Sub-item | Status |
|---------|--------|
| Score N1/N2/N3/N4 por elemento | ❌ PENDENTE |
| Dashboard por obra (todos os níveis) | ❌ PENDENTE |
| Identificação automática de padrões novos | ❌ PENDENTE |
| GF (Grelha de Fundo) — extrator+gerador+scorer | ❌ PENDENTE |
| GD (Grade de Distribuição) | ❌ PENDENTE |
| CP (Caixa de Proteção) | ❌ PENDENTE |
| VG (Viga Geral) | ❌ PENDENTE |
| CB (Cinta de Bordo) | ❌ PENDENTE |
| Modo NOVA vs INI integrado (UI + pipeline) | ❌ PENDENTE |

### 3.9 Débitos Técnicos Conhecidos

| Débito | Impacto | Prioridade |
|--------|---------|-----------|
| DB `pillars`/`beams`/`slabs` = 0 para obras novas via worker | `PreProcessAllWorker` salva, mas `projects.pavement_name` usa nome de arquivo DXF completo | P1 |
| `_process_slab_intelligent` não usa ContextEngine (busca bruta O(n)) | Performance em DXFs grandes | P2 |
| `sides_data` correlation usa raio fixo 1200u — pode falhar em escalas diferentes | Falsos negativos | P2 |
| `PillarAnalyzer.analyze()` não chamado no worker (apenas PillarPerspectiveMapper) | Dados de laje/viga por face incompletos | P2 |
| `obra_global_scanner.py` existe mas não integrado à UI | Pipeline manual para descobrir obras | P2 |
| `obra_rag_pipeline.py` criado mas ainda esqueleto | RAG por-obra bloqueado | P0 |

---

## 4. Próximos Passos Naturais (Prioridade)

### P0 — Sprint Imediato (Esta Semana)

**1. Testar PreProcessAllWorker em produção (Obra_TREINO_1)**

A obra tem 9 pavimentos com torres aprovadas. Executar "⚡ Interpretar Obra Toda" e verificar:
- Ficha gerada com contagens reais (não proxy)
- `pillars`/`beams`/`slabs` populados para cada `project_id` correto
- `pre_processamento_estado.json` salvo em `DADOS-OBRAS/Obra_TREINO_1/`
- Nenhum crash em QThread

**2. Corrigir `pavement_name` no lookup de project_id**

No worker, `pav_name` é o nome completo do arquivo DXF (ex: `TMC-EST-EX-1000-FUN-R01_...`).
No DB, `projects.pavement_name` armazena o mesmo nome. OK para lookup, mas dificulta leitura humana.
Considerar normalização: extrair sufixo semântico (FUN, TER, 1PV, etc.).

**3. Adicionar skip de pavimentos já processados**

No início do loop por pavimento, verificar se `pre_processamento_estado.json` existe e tem
`status=completed` para esse pavimento. Respeitar flag `force=False`.

### P1 — EPIC 1 RAG Pipeline (Próximas 1-2 Semanas)

**Foco único:** completar E1.1 → E1.3 → E1.5 → E1.6 nessa ordem.

```
E1.1 obra_rag_utils.py (2 dias)
  - NVIDIA NIM embed helper
  - LanceDB schema: obra_docs, obra_dxfs
  - chunking utils

E1.3 obra_dxf_classifier.py (3 dias)
  - Camada 1: regex nome de arquivo
  - Camada 2: ezdxf layers + entity counts
  - Camada 3: similarity vs domain_knowledge

E1.5 obra_rag_pipeline.py (2 dias)
  - Orquestrador E1.2 → E1.3 → E1.4
  - Progress callback para UI

E1.6 UI botão (1 dia)
  - QProgressBar por etapa no Tab 0
```

### P2 — Melhorias no Diagnostic Hub (Após EPIC 1)

**A. Integrar ContextEngine + PillarAnalyzer ao worker**

O `PreProcessAllWorker` hoje usa `PillarPerspectiveMapper` + busca bruta de texto.
Para campos de lado (`p_sA_l1_n`, `p_sA_v_esq_n`, etc.) que o DetailCard espera,
precisamos do `ContextEngine.perform_search()` + `PillarAnalyzer.analyze()` por pilar.

Isso preencheria `sides_data` com dados semânticos reais (laje por face, viga por face)
além da correlação geométrica atual.

**B. Motor semântico de detalhes (E2.8)**

`detalhes.dxf` contém anotações, cotas de referência, legendas.
Extrair via `ezdxf` + regex → dicionário estruturado → disponível ao Structural Analyzer.

**C. Normalização de `pavement_name`**

Criar mapeamento `{nome_arquivo_dxf → nome_pavimento_limpo}` (ex: `FUN`, `TER`, `1PV`).
Usar em `projects.pavement_name` e na ficha de saída.

### P3 — Classes Novas (Após EPIC 5)

Prioridade: **GF** (Grelha de Fundo) — maior volume de dados de treino (4 arquivos, 11.177 ents em TREINO_1).

Por classe nova: analisar → extrair → `motor_fase4.py` suporte → gerador → scorer → testes.
Estimativa: 3-4 semanas por classe (GF primeiro, depois GD, CP).

---

## 5. Arquitetura de Dados — Estado Real (Junho 2026)

```
DADOS-OBRAS/Obra_X/
  Fase-1_Ingestao/
    Estruturais_*Bruto*/          [DXFs brutos originais]
    Projetos_Finalizados*/        [DXFs STOG humanos — referência]
  Fase-2_Triagem/
    recortes/{pav_name}/
      torre_1.dxf                 [recorte aprovado — fonte para worker]
      detalhes.dxf                [detalhes agregados]
  Fase-3_Interpretacao_Extracao/
    pilares.json / vigas.json / lajes.json
    pilares_bh.json
  Fase-4_Sincronizacao/
    JSON_Pilares/P*.json          [formato PilarFase4 — rico]
    JSON_Vigas_Laterais/V*_A/B.json
    JSON_Vigas_Fundo/V*_fundo.json
    JSON_Lajes/L*.json
  Fase-5_Geracao_Scripts/
    DXF_Pilares/PL_stog_quality.dxf
    DXF_Vigas/LV_stog_quality.dxf  FV_stog_quality.dxf
    DXF_Lajes/LJ_stog_quality.dxf
  pre_processamento_estado.json   [gerado pelo ⚡ Interpretar Obra Toda — NOVO]

SQLite (project_data.vision):
  pillars (6.524) + beams (7.005) + slabs (4.637)   [SA database]
  obra_recortes (18)                                   [recortes aprovados]
  obra_triagem (51)                                    [triagem DXFs]
  fase3_fichas (405)                                   [fichas estruturais]
  projects (10)                                        [1 por (obra, pavimento)]
  works (24)                                           [obras indexadas]
  dxf_entidades (1.928.880)                            [cache entities DXF]

LanceDB:
  stog_rag_db/stog_kbs            [548 KBs, RAG global STOG]
  stog_rag_db/domain_knowledge    [217 chunks, 9 doc_types]
  [Obra_X/obra_rag_db/]           [RAG por-obra — PENDENTE EPIC 1]
```

---

## 6. Métricas de Sucesso — Estado Atual vs Target

| Métrica | Target Areté | Atual | Gap |
|---------|-------------|-------|-----|
| Fidelidade média N4 | ≥ 90% | 85-100% (20 obras, classes PL/LV/FV/LJ) | Atingido para 4 classes |
| Cobertura de classes | 9 (PL/LV/FV/LJ/GF/GD/CP/VG/CB) | 4 classes | 5 classes pendentes |
| Obras certificáveis sem intervenção | ≥ 80% | 19/20 (95%) | OK para PL/LV/FV/LJ |
| Tempo por obra nova | < 30 min | ~2-4h (semi-manual) | Requer EPICs 1-4 |
| Campos preenchidos automaticamente | ≥ 70% por item | ~40% (Fase-4 → DetailCard) | EPICs 5-6 |
| Tempo para ficha de pilar | < 3 min | ~15 min (manual) | EPIC 5-6 |

---

## 7. Cronograma Revisado (Junho 2026)

| EPIC | Título | Duração | Status |
|------|--------|---------|--------|
| — | PreProcessWorker testes + fixes | 2-3 dias | IMEDIATO |
| 1 | Fase 1 RAG Pipeline | 1-2 semanas | P0 — próxima sprint |
| 2 | Triagem+Recortes (residual) | — | MAJORITARIAMENTE COMPLETO |
| 3 | Design System Diagnostic Hub | 2-3 semanas | Bloqueado por EPIC 1 |
| 4 | Hub Funcionalidades RAG | 3 semanas | Bloqueado por EPIC 3 |
| 5 | Masterplan Fase 3 + SA spec | 2 semanas | Jul-Ago 2026 |
| 6 | Design System SA | 3 semanas | Set 2026 |
| 7 | Comparison Engine N1-N4 + Classes Novas | 6-8 semanas | Out-Dez 2026 |

**Total restante estimado:** ~4-5 meses para Areté completo.
**Marco mais próximo:** EPIC 1 completo (2 semanas) → desbloqueia RAG por-obra e Design System.

---

*Documento gerado em 2026-06-07 por revisão de sessão.*
*Fontes: docs/MASTERPLAN-CAD-ANALYZER.md, docs/EPIC-CAD-10.md, estado real do DB, código fonte.*
