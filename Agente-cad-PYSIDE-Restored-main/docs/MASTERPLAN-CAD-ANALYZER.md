# MASTERPLAN CAD-ANALYZER v1.0

**Data:** 2026-06-05
**Autor:** Morgan (PM/Strategist) — Synkra AIOS
**Sistema:** CAD-ANALYZER — Automacao de Formas de Concreto Estrutural
**Objetivo Arete:** Score de fidelidade >= 90% sem intervencao humana em qualquer obra nova

---

## 1. Visao Geral

CAD-ANALYZER e um sistema Python/PySide6 que automatiza a producao de formas de concreto
estrutural a partir de DXFs de projetos de engenharia civil. O sistema aprende com a
referencia humana (DXFs STOG finais) para reproduzir automaticamente o que antes era feito
a mao por profissionais especializados.

### Ciclo de Vida Completo

```
Obra Nova (DXFs brutos + PDFs)
    |
    v
[Fase 0] Knowledge Base extraida dos STOGs de referencia
[Fase 1] Ingestao de documentos brutos
[Fase 2] Triagem e classificacao
[Fase 3] Diagnostico visual + Interpretacao/Extracao
[Fase 4] Sincronizacao (JSONs normalizados)
[Fase 5] Geracao de Scripts DXF (Robos PL/LV/FV/LJ)
[Fase 6] Execucao CAD + Validacao granular
[Fase 7] Consolidacao (scores de fidelidade)
[Fase 8] Revisao e Certificacao final
```

---

## 2. Arquitetura do Sistema (8 Fases)

### Estrutura de Pastas por Obra

```
DADOS-OBRAS/Obra_X/
  Fase-0_STOG_KB/                  <- Knowledge Base extraida dos DXFs de referencia
  Fase-1_Ingestao/                 <- Documentos brutos da obra
    Estruturais_*Bruto*/           <- DXFs brutos dos pavimentos
    Documentos_Atas*/              <- PDFs/MDs (specs, atas)
    Detalhes_Estruturais/          <- DXFs de detalhes
    Projetos_Finalizados_para_Engenharia_Reversa/  <- DXFs STOG humanos (referencia)
  Fase-2_Triagem/                  <- Documentos classificados para processamento
    Estruturais_Pavimentos_Limpos/ <- DXFs aprovados para extracao
  Fase-3_Diagnostico/             <- Diagnostico visual (canvas PySide6)
  Fase-3_Interpretacao_Extracao/  <- Extracao estrutural + correction_log.json
    pilares.json                   <- Extratores de pilar (coords, b/h, faces)
    pilares_bh.json                <- B/H com confianca (extrair_bh_pilares.py)
    vigas.json                     <- Extratores de viga (h, b, comp, paineis)
    lajes.json                     <- Extratores de laje (poligono, dims)
    lajes_poligono.json            <- Poligonos com coordenadas absolutas
  Fase-4_Sincronizacao/           <- JSONs normalizados de pecas
    JSON_Pilares/                  <- P*.json (formato PilarFase4)
    JSON_Vigas_Laterais/           <- V*_A.json, V*_B.json
    JSON_Vigas_Fundo/              <- V*_fundo.json
    JSON_Lajes/                    <- L*.json (formato LajeFase4)
  Fase-5_Geracao_Scripts/         <- DXFs gerados pelo robo
    DXF_Pilares/                   <- PL_stog_quality.dxf
    DXF_Vigas/                     <- LV_stog_quality.dxf, FV_stog_quality.dxf
    DXF_Lajes/                     <- LJ_stog_quality.dxf
  Fase-6_Execucao_CAD/            <- Validacao granular
    granular/                      <- PNGs comparativos + relatorio_granular.json
    fichas/                        <- fichas_lv.json, fichas_lv.html
  Fase-7_Consolidacao/            <- fidelidade_pilares.json, fidelidade_vigas.json, ...
  Fase-8_Revisao_Entrega/         <- CERTIFICADO.json, relatorio_fidelidade.json
```

### Diagrama de Fluxo de Dados

```
 +---------------------+      +---------------------+      +--------------------+
 |   FILESYSTEM        |      |    SQLite            |      |   LanceDB          |
 | (DADOS-OBRAS/)      |      | (project_data.vision)|     |                    |
 +----------+----------+      +----------+----------+      +--------+-----------+
            |                            |                           |
            v                            v                           v
 +----+  Fase-1: DXFs brutos  +----+  pilares/vigas/   +----+  stog_rag_db/
 |    |  PDFs, MDs             |    |  lajes records    |    |  (global, 548 KBs)
 |    |  DWG->DXF via         |    |  pipeline state   |    |  4096-dim NVIDIA NIM
 |    |  accoreconsole        |    |  triagem records   |    |  BM25+dense hybrid
 |    |                        |    |                    |    |
 | F  |  Fase-3: Extratores   | D  |  BH badges        | R  |  obra_rag_db/
 | I  |  engenharia_reversa   | B  |  confianca scores  | A  |  (por-obra, futuro)
 | L  |  extrair_bh_pilares   |    |  correction_log    | G  |  PDFs + DXFs
 | E  |                        |    |                    |    |  domain_knowledge
 | S  |  Fase-4: motor_fase4  |    |                    |    |  217 chunks, 9 types
 |    |  -> JSON_Pilares/      |    |                    |    |
 |    |  -> JSON_Vigas/        |    |                    |    |
 |    |  -> JSON_Lajes/        |    |                    |    |
 |    |                        |    |                    |    |
 |    |  Fase-5: Geradores     |    |                    |    |
 |    |  gerar_pl/lv/fv/lj    |    |                    |    |
 |    |  _dxf_stog.py          |    |                    |    |
 |    |                        |    |                    |    |
 |    |  Fase-6: Validacao     |    |                    |    |
 |    |  validar_granular      |    |                    |    |
 |    |  comparar_fichas       |    |                    |    |
 |    |                        |    |                    |    |
 |    |  Fase-7/8: Fidelidade  |    |                    |    |
 |    |  Certificacao          |    |                    |    |
 +----+                        +----+                    +----+

             +-----------+
             | PySide6   |
             | UI (Tabs) |
             +-----------+
             | Tab 0: Diagnostic Hub (canvas DXF + Fase-3 pipeline)
             | Tab 1: Structural Analyser (tree view + BH badges)
             | Tab 2: Comparison Engine (Fase-8, scores, certificacao)
             | Tab 3: Robo Pilares (SCR CIMA/ABCD/GRADES)
             | Tab 4: Robo LV (vigas laterais)
             | Tab 5: Robo FV (fundos de vigas)
             | Tab 6: Robo Lajes (paineis + pontaletes)
             +-----------+
```

---

## 3. Estado Atual do Sistema (Junho 2026)

### Concluido e Operacional

#### Geradores STOG (Fase 5) — 100% certificado em 20 obras

| Gerador | Entidades | Layers | Blocos/Features |
|---------|-----------|--------|-----------------|
| PL (Pilares) | 2.247 | 14 | PONTALETE, MEIO_PONTALETE, COTAS FURACAO, CRIT-BOOST |
| LV (Vigas Laterais) | 8.237 | 21 | Sarrafos automaticos, dois niveis, border strip, codigos_forma |
| FV (Fundos de Vigas) | 686 | 9 | Escoras, reaproveitamento ANSI31, FV filter STOG-aware |
| LJ (Lajes) | 596 | 11 | SmartPanner 244/122/60, pontaletes, layer remap |

**Obra_TREINO_20 CERTIFICADA** (score 100%, fidelidade 87.7) — referencia de qualidade.

#### Sistema de Fidelidade (Fase 7) — ALL classes APROVADO

| Classe | Aprovados | Threshold | Score Range |
|--------|-----------|-----------|-------------|
| PIL | 15/15 | 85 | 85-100% |
| LAJ | 16/17 (1 N/A) | 75 | 75-100% |
| VIG | 19/19 | 82 | 82-100% |
| LV sub | 19/19 | 85 | 85-100% |
| FV sub | 19/19 | 80 | 80-100% |

**N/A legitimos:** PIL TREINO_10/17/19 (GT vazio), LAJ TREINO_14 (sem STOG LJ).

#### Comparison Engine (Forward x Reverse)

- `comparar_fichas.py` com score rigoroso = MATCH/(MATCH+DELTA+AUSENTE_REV)
- Pipeline granular LV visual: DXF -> PNG -> scoring programatico
- Mapeamento canonico PIL/VIG/LAJ confirmado em 10 obras
- Scores: TREINO_5=100%, TREINO_16=90.6%, TREINO_1=89.3%

#### STOG Intelligence / RAG

- `stog_intelligence_extractor.py` v1.0 — extrai KB por DXF
- LanceDB `stog_rag_db/stog_kbs` — 548 KBs, 4096-dim NVIDIA NIM
- Hybrid search BM25+dense operacional (`--hybrid`, `--build-fts`)
- `domain_knowledge` — 217 chunks, 9 doc_types
- `cross_obra_baselines.json` — medians por classe (PL=5757, LV=8068, LJ=1736, FV=1831)
- `universal_layers` — layers presentes em 12+ obras recebem peso 1.0

#### DWG->DXF Pipeline

- accoreconsole.exe + DXFOUT (sem ODA)
- 22 obras auditadas: 0 DXFs duplicados, 100% DWGs convertidos
- Fix chars acentuados + UnicodeEncodeError
- Pipelines NAO podem rodar em paralelo (AutoCAD COM lock)

#### Semantica Validada (Sprint 1 — 2026-06-04)

- docs/SEMANTICA-PILAR-NOVA.md (faces A/B=longas, C/D=curtas; grade_1=comp+22)
- docs/SEMANTICA-VIGA-NOVA.md (segmentacao 120cm; pillar_left/right cruzamento)
- docs/SEMANTICA-LAJE-NOVA.md (linhas_verticais CUMULATIVAS; is_union <=30cm)
- Bugs B1+LV-B2 CORRIGIDOS em motor_fase4.py
- 4 extratores Fase-3 agora salvam cx/cy (centroide)

#### Novas Classes Descobertas (STOG Intelligence batch 2026-05-24)

| Classe | Descricao Provavel | Obras |
|--------|-------------------|-------|
| GF | Grelha de Fundo | TREINO_1 (4 arquivos, 11.177 ents) |
| GD | Grade de Distribuicao | TREINO_1, 3, 13 |
| CP | Caixa de Protecao | TREINO_10, 13 |
| VG | Viga Geral | TREINO_10 |
| CB | Cinta de Bordo | TREINO_10 |

#### Pipeline E2E + UI

- `pipeline_e2e.py`: pipeline completo F1->F8, NON_BLOCKING para fases nao-criticas
- 116/116 pavimentos APROVADO em batch
- PySide6 UI com 7 tabs operacionais
- 61 testes logicos + 21 testes visuais Qt = ALL PASS

---

### Em Desenvolvimento Atual

#### Fase 1 — Ingestao e Indexacao (Sprint Junho 2026)

**Status real (Junho 2026):** Infraestrutura de indexacao completa. Pipeline RAG por-obra (embedding) pendente.

- [x] Badge "Indexar Tudo" com contagem disco/DB implementado (project_manager.py)
- [x] `auto_indexer.py` corrigido (DB absoluto, todos os folder aliases, 0 erros em 22 obras)
- [x] Botao "Converter Todos DWG->DXF" com accoreconsole.exe + DXFOUT
- [x] `obra_triagem` populada para 2 obras: TREINO_1 (40 entradas), TREINO_12 (11 entradas)
- [x] Painel IA Triagem colapsavel com badge por item (confidence/status)
- [x] `scripts/obra_triagem_populator.py` — popula via inventario LanceDB (existe, parcial)
- [ ] `scripts/obra_rag_utils.py` — base compartilhada (embed, LanceDB schemas)
- [ ] `scripts/obra_pdf_ingestor.py` — PDFs/MDs -> LanceDB obra_docs (PyMuPDF + pytesseract)
- [ ] `scripts/obra_dxf_classifier.py` — classificacao DXFs em 3 camadas (nome -> ezdxf -> embedding)
- [ ] `scripts/obra_rag_pipeline.py` — orquestrador com progress callback
- [ ] UI: botao "Processar RAG Semantico" com QProgressBar por etapa
- [ ] RAG por-obra isolado em `Obra_X/obra_rag_db/` (LanceDB — criado pelo pipeline acima)

#### Fase 2 — Triagem + Recortes (IMPLEMENTADA — revisao/expansao pendente)

**Status real (Junho 2026):** Fase 2 basica COMPLETA. Recortes com DBSCAN operacional.

**Triagem de DXFs:**
- [x] UI dual-panel no project_manager.py (sugerido pela IA / confirmados)
- [x] Status por item: pending / approved / review_required
- [x] Botao "Aprovar >= 80%" (aprovacao batch alta confianca) — `_approve_all_high_confidence_triagem`
- [x] Aprovacao individual com ajuste de categoria (dropdown + botao confirmar)
- [x] Grid Eng. Reversa injetado na Fase 2 (PM-006)
- [x] Integracao downstream: brutos aprovados aparecem no painel Pre-Processamento

**Recortes (Fase 2b — Pre-Processamento para Diagnostic Hub):**
- [x] `scripts/obra_crop_engine.py` — DBSCAN auto-crop por densidade de entidades
  - Cluster maior (score = area x contagem) = torre principal
  - Clusters menores = detalhes.dxf unificado
  - Output: `Fase-2_Triagem/recortes/{pav_name}/torre_1.dxf`, `detalhes.dxf`
- [x] Diagnostic Hub com 3 canvas tabs: BRUTO | LIMPO | DETALHES
- [x] `obra_recortes` table no SQLite (torre/detalhe, bbox_auto, bbox_approved, score)
- [x] Recorte manual (canvas atual -> novo recorte DXF)
- [x] Recorte automatico com QProgressBar ("Processar Auto")
- [x] "Processar Obra Inteira" — batch de todos os brutos aprovados
- [x] Radio buttons de classificacao: detalhe / torre / torre_2
- [x] Botao "Salvar" — persiste edicoes no DXF do recorte
- [x] Badge de status por bruto no painel (sem recorte / N recortes OK)
- [x] 2 recortes validados em producao (TREINO_1, pavimento FUN, torre+detalhe)
- [ ] Motor semantico de detalhes (extrai anotacoes, notas, cotas de referencia dos detalhes.dxf)

---

## 4. Roadmap de Desenvolvimento — 7 EPICs

### EPIC 1: Fase 1 RAG Pipeline (ATUAL)

**Status:** Em Andamento | **Prioridade:** P0 | **Sprint:** Junho 2026
**Objetivo:** Botao "Processar RAG Semantico da Obra" que pre-processa toda a obra via embedding

**Progresso:** Infraestrutura (indexacao + triagem DB + UI) COMPLETA. Faltam scripts de embedding/classificacao RAG.

#### Entregas

- [ ] **E1.1** `scripts/obra_rag_utils.py` — Base compartilhada
  - Funcoes de embedding (NVIDIA NIM 4096-dim)
  - Schemas LanceDB para `obra_docs` e `obra_dxfs`
  - Helpers de chunking (secao/paragrafo + sliding window fallback)

- [ ] **E1.2** `scripts/obra_pdf_ingestor.py` — PDFs/MDs -> LanceDB
  - PyMuPDF para PDFs digitais
  - pytesseract fallback para PDFs escaneados
  - Chunking por secao/paragrafo + sliding window fallback
  - Metadata: obra_name, file_name, page, chunk_id, doc_type

- [ ] **E1.3** `scripts/obra_dxf_classifier.py` — Classificacao DXFs em 3 camadas
  - Camada 1: nome do arquivo (padroes de pavimento, STOG PL/LV/FV/LJ)
  - Camada 2: analise ezdxf (layers, contagem entidades, blocks)
  - Camada 3: embedding similarity vs domain_knowledge (fallback para ambiguos)
  - Output: `{file_path, suggested_category, confidence, evidence[]}`

- [x] **E1.4** `scripts/obra_triagem_populator.py` — Sugestoes -> SQLite
  - Tabela SQLite `obra_triagem` existente (id, obra_name, file_path, suggested_category, confidence, status, classifier, notes, created_at)
  - 2 obras com dados: TREINO_1 (40 entradas), TREINO_12 (11 entradas)
  - Status: pending / approved / review_required
  - *Pendente: integrar output do classificador E1.3 como fonte primaria*

- [ ] **E1.5** `scripts/obra_rag_pipeline.py` — Orquestrador
  - Chama E1.2 (PDFs) -> E1.3 (DXFs) -> E1.4 (triagem)
  - Progress callback para UI (QProgressBar por etapa)
  - Retry e error handling por arquivo
  - Salva DB em `DADOS-OBRAS/Obra_X/obra_rag_db/` (LanceDB isolado)

- [ ] **E1.6** UI: Botao "Processar RAG Semantico" na Fase 1
  - QProgressBar por etapa (PDFs -> DXFs -> Triagem)
  - Badge com contagem disco/DB atualizado apos execucao
  - Log de erros visivel
  - *Nota: badge "Indexar Tudo" e botao DWG->DXF ja existem — este botao e adicional*

#### Decisoes

| # | Pergunta | Status | Decisao |
|---|----------|--------|---------|
| D1 | RAG por-obra vs global? | DECIDIDO | RAG por-obra isolado em `Obra_X/obra_rag_db/` |
| D2 | Embedding model? | DECIDIDO | NVIDIA NIM 4096-dim (mesmo do STOG RAG) |
| D3 | OCR para PDFs escaneados? | DECIDIDO | pytesseract fallback |
| D4 | Chunking strategy? | DECIDIDO | Secao/paragrafo primario + sliding window fallback |
| D5 | Classificacao em quantas camadas? | DECIDIDO | 3 camadas (nome -> ezdxf -> embedding) |
| D6 | Storage triagem? | DECIDIDO | SQLite (mesma DB do projeto) |

#### Nota Arquitetural

```
RAG por-obra: Obra_X/obra_rag_db/    <- isolado, criado pela Fase 1
RAG global:   stog_rag_db/            <- alimentado pela Fase 0 (STOG KB)
Futuro:       Fase-3 validated_extractions -> global RAG (EPIC 5)
```

---

### EPIC 2: Fase 2 — Triagem + Recortes com IA

**Status:** MAJORITARIAMENTE COMPLETO | **Prioridade:** P1 | **Pre-requisito:** EPIC 1 (parcial)
**Objetivo:** Dual-panel Fase 2 com sugestoes automaticas + motor de recortes DBSCAN

**Progresso:** UI de triagem e recortes IMPLEMENTADOS. Pendente: integrar classificador E1.3 como fonte de sugestoes de confianca, e motor semantico de detalhes.

#### Entregas

- [x] **E2.1** Tabela SQLite `obra_triagem` integrada
  - Schema atual: id, obra_name, file_path, file_name, file_ext, suggested_category, suggested_order, confidence, status, classifier, notes, created_at
  - 2 obras com dados: TREINO_1 (40 entradas), TREINO_12 (11 entradas)
  - *Pendente: adicionar user_category, approved_at, evidence_json (ver migracao DB)*

- [x] **E2.2** UI dual-panel na aba Fase 2 (project_manager.py)
  - Painel colapsavel "Sugestoes IA" (status=pending/review_required)
  - Painel "Confirmados" (status=approved)
  - Badge de confianca por item

- [x] **E2.3** Aprovacao individual com ajuste
  - Aprovacao por item com mudanca de status
  - Botao "Aprovar" -> move para painel confirmados

- [x] **E2.4** Botao "Aprovar Todos >= 80%"
  - Implementado como `_approve_all_high_confidence_triagem`
  - Aprovacao batch para itens com confianca alta

- [x] **E2.5** Integracao downstream
  - Brutos aprovados aparecem no painel "Pre-Processamento"
  - Disponiveis para Diagnostic Hub (Tab 0) via `request_open_bruto` signal

- [x] **E2.6** Motor de Recortes DBSCAN (obra_crop_engine.py)
  - DBSCAN por densidade de entidades -> clusters
  - Maior cluster = torre_1.dxf; clusters menores = detalhes.dxf
  - Suporte a torre_2 (obras com 2 blocos principais)
  - Output: `Fase-2_Triagem/recortes/{pav_name}/`

- [x] **E2.7** Diagnostic Hub — 3 canvas BRUTO | LIMPO | DETALHES
  - Recorte manual: salvar canvas atual como novo recorte
  - Recorte automatico com QProgressBar
  - Batch "Processar Obra Inteira"
  - Radio: detalhe / torre / torre_2
  - `obra_recortes` table (bbox_auto, bbox_approved, entity_count, score, status)

- [ ] **E2.8** Motor semantico de detalhes
  - Extrai anotacoes, notas do projetista, cotas de referencia, legendas dos detalhes.dxf
  - Input: saida de E2.6 (detalhes.dxf)
  - *Nota: FUTURO — apos validacao dos recortes manuais em mais obras*

#### Decisoes

| # | Pergunta | Status | Decisao |
|---|----------|--------|---------|
| D1 | Como lidar com DXFs sem categoria? | DECIDIDO | status=review_required + badge vermelho |
| D2 | Reaproveitar aprovacoes quando obra e reprocessada? | ABERTO | Sugestao: hash do arquivo + decisao |
| D3 | Threshold minimo para auto-sugestao? | ABERTO | Sugestao: 30% (abaixo = "Nao classificado") |
| D4 | Motor semantico de detalhes quando? | DECIDIDO | Apos validacao manual em 5+ obras |

---

### EPIC 3: Design System — Diagnostic Hub

**Status:** Planejado | **Prioridade:** P1 | **Pre-requisito:** EPIC 2
**Objetivo:** Redesenhar a UI do Diagnostic Hub (Fase 3) para melhor usabilidade
**Referencia:** `docs/DESIGN-SYSTEM-PYSIDE.md`

#### Entregas

- [ ] **E3.1** Sidebar redesenhada com contexto da obra
  - Info do RAG por-obra (documentos ingeridos, classificacao)
  - Arvore de pavimentos com badges de status
  - Mini-mapa da obra (quantos DXFs por tipo)

- [ ] **E3.2** Canvas toolbar com modos de renderizacao
  - Botoes BMP Unicode (ja migrado de emojis em v4.2)
  - Modos: layers, entidades, heatmap, sobreposicao reverso/gerado
  - Zoom/pan/fit com shortcuts de teclado

- [ ] **E3.3** Painel "Contexto RAG" colapsavel
  - Informacoes do obra_rag_db sobre o DXF aberto no canvas
  - Documentos relacionados (PDFs ingeridos que mencionam elementos do DXF)
  - Regras de dominio relevantes (do domain_knowledge)

- [ ] **E3.4** Barra inferior Pipeline refatorada
  - Estado atual de cada fase com icones de status
  - Acao rapida para avancar pipeline (botao "Proximo Passo")
  - Tempo estimado para processos pesados

- [ ] **E3.5** Consistencia visual com design system
  - Paleta de cores unificada
  - Componentes reutilizaveis (ScoreLabel, BadgeTree, ProgressBar)
  - Tooltips descritivos em todos os botoes

#### Decisoes Abertas

| # | Pergunta | Status | Notas |
|---|----------|--------|-------|
| D1 | Sidebar permanente ou colapsavel? | ABERTO | Trade-off: espaco canvas vs contexto sempre visivel |
| D2 | Canvas em QGraphicsView ou OpenGL? | ABERTO | QGraphicsView atual funciona; OpenGL para DXFs >50k entities |
| D3 | Manter 7 tabs ou consolidar? | ABERTO | Sugestao: manter, mas com navegacao melhorada |

---

### EPIC 4: Diagnostic Hub — Funcionalidades

**Status:** Planejado | **Prioridade:** P2 | **Pre-requisito:** EPIC 3
**Objetivo:** Melhorar as capacidades de interpretacao do Diagnostic Hub

#### Entregas

- [ ] **E4.1** Integracao RAG no carregamento de DXF
  - `obra_rag_query.get_obra_rag_context()` chamado ao abrir DXF
  - Sidebar mostra documentos relevantes (chunks com highest similarity)
  - Regras de dominio aplicaveis ao tipo do DXF

- [ ] **E4.2** Sugestao automatica de modo de renderizacao
  - Baseada no tipo do DXF (PL -> modo "faces"; LV -> modo "elevacao")
  - RAG por-obra pode sugerir layers prioritarios
  - Historico de modos usados por tipo

- [ ] **E4.3** Pre-interpretacao automatica
  - Mostrar campos esperados baseados em obras similares (RAG global)
  - Template de extracao pre-populado com valores esperados
  - Highlight de anomalias (valores fora do range esperado)

- [ ] **E4.4** Pipeline automatico para DXFs simples
  - Se confianca alta (>= 90%) em todos os campos -> pular revisao manual
  - Flag "auto-processed" no correction_log
  - Revisao humana ainda acessivel (botao "Revisar" por item)

- [ ] **E4.5** Batch processing
  - Processar todos os DXFs de uma obra em sequencia
  - Dashboard de progresso (quantos processados, quantos pendentes, quantos com erro)
  - Priorizar DXFs com alta confianca (processar automatico primeiro)

#### Decisoes Abertas

| # | Pergunta | Status | Notas |
|---|----------|--------|-------|
| D1 | Threshold para auto-process? | ABERTO | Sugestao: 90% todos campos; 85% se obra similar ja validada |
| D2 | Batch sequencial ou paralelo? | ABERTO | Sugestao: sequencial (ezdxf nao e thread-safe) |
| D3 | Como lidar com DXFs que falham na pre-interpretacao? | ABERTO | Sugestao: queue para revisao manual |

---

### EPIC 5: Masterplan Fase 3 + Structural Analyser

**Status:** Planejado | **Prioridade:** P2 | **Pre-requisito:** EPIC 4
**Objetivo:** Definir a visao completa da Fase 3 e como o Structural Analyser funciona

#### Entregas

- [ ] **E5.1** Documento de especificacao do Structural Analyser
  - O que cada campo deve mostrar (pilares: b/h/faces/grades; vigas: h/b/comp/paineis; lajes: comp/larg/poligono)
  - Fluxo de validacao campo-a-campo
  - Criterios de aceitacao por campo

- [ ] **E5.2** Granularidade de validacao
  - Cada campo validado individualmente (verde/amarelo/vermelho)
  - Score composto por elemento (media ponderada dos campos)
  - Score por tipo (media dos elementos)
  - Score por obra (media dos tipos)

- [ ] **E5.3** Ciclo correction_log -> RAG global
  - Quando: apos validacao humana de um elemento
  - O que: campo corrigido + valor original + valor correto + contexto
  - Destino: `stog_rag_db/corrections` (nova tabela LanceDB)
  - Retroalimentacao: futuras extracoes consultam correcoes de obras similares

- [ ] **E5.4** RAG global retroalimenta interpretacoes
  - Na Fase-3, consultar correcoes de obras anteriores
  - Se campo X da obra Y foi corrigido de A para B, e obra nova e similar a Y -> sugerir B
  - Confianca da sugestao = f(similaridade da obra, frequencia da correcao)

- [ ] **E5.5** Criterios de Arete para Fase 3
  - Definicao formal: "100% Fase 3" = todos os campos de todos os elementos extraidos com confianca >= 0.8
  - Metricas: precision (campos corretos / campos extraidos), recall (campos extraidos / campos esperados)
  - Target: precision >= 95%, recall >= 90%

#### Decisoes Abertas

| # | Pergunta | Status | Notas |
|---|----------|--------|-------|
| D1 | RAG global retroalimentado automaticamente ou com aprovacao? | ABERTO | Risco: propagar erros |
| D2 | correction_log em JSON ou SQLite? | ABERTO | JSON atual funciona; SQLite para queries complexas |
| D3 | Peso de cada campo no score composto? | ABERTO | Sugestao: b/h peso 3, comp peso 2, outros peso 1 |
| D4 | Como medir "obra similar"? | ABERTO | Opcoes: embedding similarity, mesmo construtor, mesma regiao |

---

### EPIC 6: Design System — Structural Analyser

**Status:** Planejado | **Prioridade:** P2 | **Pre-requisito:** EPIC 5
**Objetivo:** Aplicar o design system a aba do Structural Analyser (Tab 1)

#### Entregas

- [ ] **E6.1** Layout otimizado para validacao granular
  - Tabela campo-a-campo com colunas: Campo | Extraido | Esperado (RAG) | Status | Acao
  - Filtro por tipo de elemento (pilares/vigas/lajes)
  - Filtro por status (todos/verde/amarelo/vermelho)

- [ ] **E6.2** Feedback visual claro
  - Verde: confianca >= 0.8 e valor dentro do range esperado
  - Amarelo: confianca 0.4-0.8 ou valor borderline
  - Vermelho: confianca < 0.4 ou valor fora do range
  - Icone de "historico" quando campo ja foi corrigido em obra anterior

- [ ] **E6.3** Painel de contexto RAG global integrado
  - Ao selecionar um campo, mostra evidencias do RAG global
  - Obras similares e seus valores para o mesmo campo
  - Correcoes anteriores relevantes

- [ ] **E6.4** Historico de correcoes visivel
  - Timeline de correcoes por elemento
  - Diff visual (antes/depois)
  - Autor da correcao (humano vs automatico)

- [ ] **E6.5** Comparativo visual lado-a-lado
  - Canvas dividido: reverso (STOG humano) vs gerado (robo)
  - Sincronizacao de zoom/pan entre os dois paineis
  - Overlay mode (sobreposicao com transparencia)

#### Decisoes Abertas

| # | Pergunta | Status | Notas |
|---|----------|--------|-------|
| D1 | Edicao inline na tabela ou formulario separado? | ABERTO | Sugestao: inline para campos simples, form para complexos |
| D2 | Historico de correcoes no DB principal ou separado? | ABERTO | Sugestao: SQLite separado para auditoria |

---

### EPIC 7: Comparison Engine — Engenharia Reversa + Validacao N1/N2/N3/N4

**Status:** Planejado | **Prioridade:** P3 | **Pre-requisito:** EPICs 5+6
**Objetivo:** Ciclo completo de validacao cruzada usando Comparison Engine + robos

#### Niveis de Comparacao

| Nivel | Descricao | O que compara | Fonte vs Referencia |
|-------|-----------|---------------|---------------------|
| N1 | Estrutural basico | IDs presentes, contagens | Fase-4 JSON vs reverso |
| N2 | Dimensional | Comprimentos, alturas, larguras | Fase-4 JSON vs reverso |
| N3 | Geracao | Robo produz resultado certo? | Fase-5 DXF vs Fase-4 JSON |
| N4 | Fidelidade final | DXF gerado vs DXF STOG humano | Fase-5 vs Projetos_Finalizados |

#### Entregas

- [ ] **E7.1** Score N1/N2/N3/N4 por elemento e por obra
  - N1: `comparar_fichas.py` expandido com flag `--nivel N1`
  - N2: dimensional comparison com tolerancias por campo
  - N3: `validar_geracao.py` expandido com metricas por campo
  - N4: `fidelidade_*.py` ja existente (integrar no dashboard)

- [ ] **E7.2** Ciclo completo automatizado
  - Fase 3 interpreta -> Fase 4 normaliza -> Fase 5 gera -> N4 valida vs STOG
  - Pipeline automatico com flag `--full-cycle`
  - Report consolidado por obra com todos os 4 niveis

- [ ] **E7.3** Dashboard de progresso por obra
  - Tabela: Obra | N1 | N2 | N3 | N4 | Status Global
  - Drill-down por elemento (qual pilar/viga/laje falhou em qual nivel?)
  - Tendencia ao longo do tempo (como o score evolui com fixes)

- [ ] **E7.4** Identificacao automatica de padroes novos
  - Quando N4 falha para um tipo de elemento -> analisar delta
  - Se delta e sistematico (mesmo tipo de erro em multiplas obras) -> candidato a fix no gerador
  - Se delta e anomalia (unica obra) -> candidato a regra especial no RAG

- [ ] **E7.5** Classes novas integradas ao pipeline
  - GF (Grelha de Fundo): gerador + extrator + fidelidade
  - GD (Grade de Distribuicao): idem
  - CP (Caixa de Protecao): idem
  - VG (Viga Geral): idem
  - CB (Cinta de Bordo): idem
  - Cada classe nova requer: analista + extrator + gerador + scorer + testes

- [ ] **E7.6** Modo NOVA vs INI integrado
  - Selecao no inicio do pipeline (UI dropdown ou config por-obra)
  - Geradores usam config key correta (use_mline, modo_sarrafos, tipo_linha)
  - Validacao adapta thresholds por modo (INI tem MLINE entities diferentes)

#### Decisoes Abertas

| # | Pergunta | Status | Notas |
|---|----------|--------|-------|
| D1 | Prioridade das classes novas? | ABERTO | Sugestao: GF primeiro (mais dados), depois GD, CP |
| D2 | Score N1 blocking para N2? | ABERTO | Sugestao: N1 >= 70% para avancar para N2 |
| D3 | Como lidar com obras sem STOG humano? | ABERTO | N4 impossivel; usar N1-N3 como proxy |
| D4 | Modo NOVA/INI detectado automaticamente? | ABERTO | Sugestao: analisar layers do STOG (MLINE -> INI, PLINE -> NOVA) |
| D5 | Quando uma classe nova esta "pronta"? | ABERTO | Sugestao: >= 5 obras com score N4 >= 80% |

---

## 5. Pilares Conhecidos / Limitacoes Estruturais

### Tetos de Score por Obra (nao fixaveis sem novos DXFs)

| Obra | Limitacao | Impacto |
|------|-----------|---------|
| TREINO_1 | P41-P50 ausentes do STOG PL; V250-V410 ausentes (12PAV) | ~50 AUSENTE_REV |
| TREINO_6 | 10PV/11PV/12PV/ATC sem FV DXF | 80 VIG.b AUSENTE_AMBOS |
| TREINO_8 | V3051-V3201 ausentes do 1PAV LV; 65 lajes sem cobertura | ~82 AUSENTE |
| TREINO_11 | V301-V303 compound labels no CARIMBO | 34 VIG AUSENTE_AMBOS |
| TREINO_12 | Zero STOGs em Projetos_Finalizados | BLOQUEADO_FORMATO |
| TREINO_24 | Zero STOGs em Projetos_Finalizados | BLOQUEADO_FORMATO |

### Limitacoes Tecnicas Conhecidas

| Area | Limitacao | Workaround |
|------|-----------|------------|
| ezdxf | Nao le DWG (binario) | accoreconsole.exe DXFOUT |
| MLINE | Robot real usa _CMLSTYLE SAR3 | Gerador usa PLINE (aparencia diferente) |
| DIMSTYLE | BASE_DWG com DIMSTYLE "COTA" real | ezdxf aproximacao manual |
| AutoCAD COM | Drawing Recovery bloqueia | Doc ativo sem dialogs |
| Pipelines paralelas | accoreconsole nao suporta | Execucao sequencial |
| RAM | DXFs grandes (>50k ents) | safe_readfile() com psutil guard 600MB |

---

## 6. Stack Tecnico

| Componente | Tecnologia | Versao |
|------------|-----------|--------|
| Linguagem | Python | 3.11+ |
| UI Framework | PySide6 (Qt6) | 6.6+ |
| DXF Processing | ezdxf | 0.19+ |
| Vector DB (RAG) | LanceDB | 0.8+ |
| Embedding | NVIDIA NIM | meta/llama-3.2-90b-vision + text-embedding-4096 |
| OCR | pytesseract | 0.3.10 |
| PDF | PyMuPDF (fitz) | 1.24+ |
| DB relacional | SQLite | 3.45+ (via project_data.vision) |
| DXF Rendering | ezdxf + matplotlib | backend para PNGs |
| Testes | pytest + pywinauto | 61 logicos + 21 visuais |

### Scripts Criticos

```
D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/
  scripts/
    engenharia_reversa_dxf.py      # Fase-3: extrator principal
    extrair_bh_pilares.py          # Fase-3b: B/H com confianca
    extrair_poligono_lajes.py      # Fase-3: poligonos de laje
    motor_fase4.py                 # Fase-4: normaliza JSON
    gerar_pl_dxf_stog.py           # Fase-5: gerador pilares
    gerar_lv_dxf_stog.py           # Fase-5: gerador vigas laterais
    gerar_fv_dxf_stog.py           # Fase-5: gerador fundos de vigas
    gerar_lj_dxf_stog.py           # Fase-5: gerador lajes
    validar_visual_dxf.py          # Fase-6: validacao visual + NIM
    validar_granular_nim.py        # Fase-6: validacao granular LV
    comparar_fichas.py             # Fase-6: Forward x Reverse
    validar_geracao.py             # Fase-6: validacao de geracao
    fidelidade_pilares.py          # Fase-7: fidelidade PIL
    fidelidade_vigas.py            # Fase-7: fidelidade VIG (LV+FV)
    fidelidade_lajes.py            # Fase-7: fidelidade LAJ
    fidelidade_kb_scorer.py        # Fase-7: KB-blended scorer
    pipeline_e2e.py                # Pipeline completo F1->F8
    pipeline_batch.py              # Batch multi-obra
    certificar_obra.py             # Fase-8: certificacao (C1-C6)
    stog_intelligence_extractor.py # Fase-0: KB extrator
    auto_indexer.py                # RAG: indexador LanceDB
  src/ui/modules/
    diagnostic_hub.py              # Tab 0: Diagnostic Hub
    comparison_engine.py           # Tab 2: Comparison Engine
  main.py                          # App principal PySide6
```

---

## 7. Cronograma Estimado

| EPIC | Titulo | Duracao Estimada | Pre-requisito | Sprint | Status |
|------|--------|-----------------|---------------|--------|--------|
| 1 | Fase 1 RAG Pipeline (embedding) | 1-2 semanas | Nenhum | Jun 2026 | Em Andamento |
| 2 | Fase 2 Triagem + Recortes | — | EPIC 1 (parcial) | — | MAJORITARIAMENTE COMPLETO |
| 3 | Design System Diagnostic Hub | 2-3 semanas | EPIC 1 completo | Jul 2026 | Planejado |
| 4 | Diagnostic Hub Funcionalidades RAG | 3 semanas | EPIC 3 | Jul-Ago 2026 | Planejado |
| 5 | Masterplan Fase 3 + Structural Analyser | 2 semanas (spec) | EPIC 4 | Ago-Set 2026 | Planejado |
| 6 | Design System Structural Analyser | 3 semanas | EPIC 5 | Set 2026 | Planejado |
| 7 | Comparison Engine N1-N4 + Classes Novas | 6-8 semanas | EPICs 5+6 | Out-Dez 2026 | Planejado |

**Revisao Jun 2026:** EPIC 2 ja entregue. EPIC 1 reduzido (infraestrutura pronta, apenas embedding pendente).
**Total restante estimado:** ~4-5 meses.

---

## 8. Metricas de Sucesso

### Arete Target (objetivo final)

| Metrica | Target | Atual | Gap |
|---------|--------|-------|-----|
| Fidelidade media (N4) | >= 90% | 85-100% (20 obras TREINO) | Atingido para classes PL/LV/FV/LJ |
| Cobertura de classes | 9 classes (PL/LV/FV/LJ/GF/GD/CP/VG/CB) | 4 classes (PL/LV/FV/LJ) | 5 classes pendentes |
| Obras certificaveis sem intervencao | >= 80% | 19/20 (95%) para classes existentes | OK para PL/LV/FV/LJ |
| Tempo medio por obra nova | < 30 minutos | ~2-4 horas (pipeline semi-manual) | Requer EPIC 1-4 |
| Precisao Fase-3 (extracao) | >= 95% | ~85% estimado | Requer EPIC 5 |
| Recall Fase-3 (extracao) | >= 90% | ~75% estimado | Requer EPIC 5 |
| RAG retrieval accuracy | >= 85% | BM25+dense operacional | Baseline a medir |

### KPIs por EPIC

| EPIC | KPI | Target |
|------|-----|--------|
| 1 | PDFs ingeridos com sucesso | >= 95% dos PDFs da obra |
| 1 | DXFs classificados corretamente | >= 85% camada 1+2 |
| 2 | Triagem com 1 clique (auto-approve) | >= 70% dos DXFs |
| 3 | Tempo de carregamento canvas | < 3s para DXFs < 20k ents |
| 4 | Campos pre-interpretados corretamente | >= 80% |
| 5 | Spec review aprovado pelo usuario | GO em primeira revisao |
| 6 | Usabilidade (campos validados/minuto) | >= 10 campos/min |
| 7 | Classes novas com N4 >= 80% | >= 3 classes em 5+ obras |

---

## 9. Riscos e Mitigacoes

| # | Risco | Probabilidade | Impacto | Mitigacao |
|---|-------|---------------|---------|-----------|
| R1 | NVIDIA NIM API fica indisponivel/cara | Media | Alto | Fallback para embeddings locais (sentence-transformers) |
| R2 | DXFs de obras novas com formato muito diferente | Alta | Medio | STOG Intelligence detecta anomalias; universal_layers como baseline |
| R3 | Classificacao Fase-1 errada propaga erros | Media | Alto | 3 camadas de classificacao + revisao humana obrigatoria |
| R4 | RAM insuficiente para obras grandes | Baixa | Medio | psutil guard 600MB + lazy loading |
| R5 | Novas classes (GF/GD/CP) requerem geradores completamente novos | Alta | Alto | Reutilizar arquitetura dos geradores PL/LV/FV/LJ; adaptar |
| R6 | correction_log propaga erros entre obras | Media | Alto | Validacao humana obrigatoria antes de adicionar ao RAG global |
| R7 | Modo INI requer testes em obras reais | Media | Medio | Coletar obras INI antes de implementar; flag por-obra |
| R8 | Qt6/PySide6 performance com muitos paineis | Baixa | Baixo | Virtual scrolling; renderizacao sob demanda |

---

## 10. Glossario

| Termo | Significado |
|-------|------------|
| STOG | Sistema de formas (gabarito) — desenho final das pecas de madeira |
| PIL / PL | Pilares — elementos verticais |
| VIG | Vigas — elementos horizontais (genericos) |
| LV | Laterais de Vigas — faces laterais das formas |
| FV | Fundos de Vigas — base/fundo das formas |
| LJ / LAJ | Lajes — elementos horizontais planos |
| GF | Grelha de Fundo — nova classe descoberta |
| GD | Grade de Distribuicao — nova classe |
| CP | Caixa de Protecao — nova classe |
| VG | Viga Geral — nova classe |
| CB | Cinta de Bordo — nova classe |
| NOVA | Modo de geracao com PLINE (geometria explicita) |
| INI | Modo de geracao com MLINE (AutoCAD multi-line) |
| KB | Knowledge Base — base de conhecimento extraida dos STOGs |
| RAG | Retrieval-Augmented Generation — busca semantica |
| N1-N4 | Niveis de validacao progressiva (basico -> fidelidade final) |
| CRIT-BOOST | Mecanismo de boost para layers criticos deficientes |
| ARETE | Score maximo / excelencia (target >= 90%) |
| Comparison Engine | Motor de comparacao Forward (TQS) vs Reverse (STOG) |
| motor_fase4 | Normalizador que converte Fase-3 -> JSONs Fase-4 |
| correction_log | Log de correcoes feitas pelo humano na Fase-3 |

---

## 11. Referencias

| Documento | Localizacao |
|-----------|------------|
| Semantica Pilar NOVA | `docs/SEMANTICA-PILAR-NOVA.md` |
| Semantica Viga NOVA | `docs/SEMANTICA-VIGA-NOVA.md` |
| Semantica Laje NOVA | `docs/SEMANTICA-LAJE-NOVA.md` |
| Design System PySide | `docs/DESIGN-SYSTEM-PYSIDE.md` |
| Calculos e Algoritmos | `docs/CALCULOS_ALGORITMOS.md` |
| Padroes SCR Robos | `docs/ROBO_SCR_PATTERNS.md` |
| Masterplan UI | `docs/MASTERPLAN-CAD-UI.md` |
| Masterplan Interpretacao | `docs/MASTERPLAN-INTERPRETACAO-VALIDACAO.md` |
| Data Flow | `docs/DATA_FLOW.md` |
| Architecture | `docs/ARCHITECTURE.md` |
| Developer Onboarding | `docs/DEVELOPER_ONBOARDING.md` |
| Arquitetura DB Completa (detalhada) | `docs/ARQUITETURA-DB-COMPLETA.md` |

---

## 12. Arquitetura de Banco de Dados

> Documento detalhado: `docs/ARQUITETURA-DB-COMPLETA.md`
> Auditoria realizada por Dara (data-engineer) — Jun 2026

### 12.1 Visao Geral do Storage

```
D:/Agente-cad-PYSIDE/
  project_data.vision          <- SQLite 1.3GB, 40+ tabelas, ~1.9M rows
  DADOS-OBRAS/Obra_X/
    obra_rag_db/               <- LanceDB por-obra (FUTURO — EPIC 1)
  Agente-cad-PYSIDE-Restored-main/
    stog_rag_db/               <- LanceDB global (OPERACIONAL)
      stog_kbs/                <- 548 KBs, 4096-dim NVIDIA NIM
      domain_knowledge/        <- 217 chunks, 9 doc_types
      corrections/             <- FUTURO (EPIC 5)
```

**Regra fundamental:** SQLite armazena METADADOS e resultados estruturados. LanceDB armazena VETORES para busca semantica. Nao ha duplicacao: SQLite nao tem embeddings, LanceDB nao tem campos de negocio.

### 12.2 Estado Atual do SQLite (Junho 2026)

| Tabela | Rows | Fase | Status |
|--------|------|------|--------|
| obras | 7 | Global | OK — fonte de verdade |
| obra_triagem | 51 | F1/F2 | OK — 20 approved, 27 pending, 4 review |
| obra_recortes | 2 | F2b | OK — expandir com mais obras |
| project_documents | 1.752 | F1 | OK — 22 obras indexadas |
| dxf_entidades | 1.928.880 | F1 | OK — maior tabela |
| fase3_fichas | 405 | F3 | OK |
| pillars | 6.524 | F3 | OK |
| beams | 7.005 | F3 | OK |
| slabs | 4.637 | F3 | OK |
| transformation_rules | 23 | F4 | OK |
| ab_test_batch | — | F4 | **BUG:** FK aponta para backup table |

**Bug critico:** `ab_test_batch.control_rule_id` referencia `transformation_rules_backup_20260214_162533` em vez de `transformation_rules`.

### 12.3 Schema Proposto — Camadas 0-7

#### Camada 0 — Catalogo Global
```sql
-- Fonte de verdade de obras (JA EXISTE, OK)
obras (id PK, obra_name UNIQUE, modo TEXT, status TEXT, created_at, updated_at)
```

#### Camada 1 — Ingestao (Fase 1)
```sql
-- Indexacao de documentos fisicos (JA EXISTE como project_documents)
project_documents (
  id PK, obra_name TEXT REFERENCES obras(obra_name),
  file_path TEXT UNIQUE, file_name TEXT, file_ext TEXT,
  file_size INTEGER, file_hash TEXT,         -- ADICIONAR
  dxf_version TEXT, entity_count INTEGER,   -- ADICIONAR
  phase INTEGER, doc_type TEXT, status TEXT,
  created_at DATETIME, updated_at DATETIME  -- ADICIONAR updated_at
)

-- Indice: CREATE INDEX idx_pd_work_phase ON project_documents(work_name, phase)
-- Nota: coluna e work_name (nao obra_name) nesta tabela
```

#### Camada 2 — Triagem (Fase 2)
```sql
-- Classificacao de DXFs (JA EXISTE como obra_triagem)
obra_triagem (
  id PK, obra_name TEXT REFERENCES obras(obra_name),
  file_path TEXT, file_name TEXT, file_ext TEXT,
  suggested_category TEXT, suggested_order INTEGER,
  confidence REAL, status TEXT,              -- pending|approved|review_required
  classifier TEXT, notes TEXT,
  user_category TEXT,                        -- ADICIONAR: categoria ajustada pelo usuario
  evidence_json TEXT,                        -- ADICIONAR: evidencias do classificador
  approved_at DATETIME,                      -- ADICIONAR
  created_at DATETIME, updated_at DATETIME  -- ADICIONAR updated_at
)

-- Indice: CREATE INDEX idx_ot_obra_status ON obra_triagem(obra_name, status)
```

#### Camada 2b — Recortes (Fase 2b)
```sql
-- Recortes DXF por pavimento (JA EXISTE como obra_recortes)
obra_recortes (
  id PK, obra_name TEXT, pavimento_name TEXT,
  dxf_bruto_path TEXT, recorte_type TEXT,   -- torre|torre_2|detalhe
  recorte_index INTEGER, output_path TEXT,
  bbox_auto TEXT, bbox_approved TEXT,
  entity_count INTEGER, score REAL,
  status TEXT, n_torres INTEGER,
  created_at DATETIME, approved_at DATETIME,
  updated_at DATETIME                        -- ADICIONAR
)
```

#### Camada 3 — Interpretacao (Fase 3)
```sql
-- Fichas brutas interpretadas pelo motor_fase4 (JA EXISTE como fase3_fichas)
fase3_fichas (id PK, obra_name, pavimento, elemento_id, tipo, dados_json, confianca, correction_log_json, created_at)

-- Pilares, vigas, lajes individuais (JA EXISTEM)
pillars (id PK, obra_name, pavimento, pilar_id, b, h, faces_json, grades_json, cx, cy, created_at)
beams   (id PK, obra_name, pavimento, viga_id, h, b, comp, paineis_json, side, cx, cy, created_at)
slabs   (id PK, obra_name, pavimento, laje_id, comp, larg, poligono_json, linhas_json, created_at)
```

#### Camada 4 — Sincronizacao (Fase 4)

**Estrategia dual (JSONs + DB em paralelo — sem conflito):**

```
motor_fase4.py
  |
  +---> JSON_Pilares/P*.json          <- FONTE DOS ROBOS (intocavel)
  |     JSON_Vigas_Laterais/V*_A.json    gerar_pl/lv/fv/lj_dxf_stog.py leem daqui
  |     JSON_Lajes/L*.json
  |
  +---> SQLite fase4_fichas           <- FONTE DO COMPARISON ENGINE (novo, paralelo)
              queries N1/N2/N3 feitas aqui sem tocar nos JSONs
```

Os robos NUNCA lerão do SQLite — continuam lendo JSON do disco como sempre.
O Comparison Engine NUNCA precisará parsear JSONs — fará queries SQL direto.
Dupla escrita em `motor_fase4.py`: salva JSON + INSERT/UPSERT na tabela.

```sql
-- Fichas normalizadas espelhando os JSONs (CRIAR NO EPIC 7)
fase4_fichas (
  id PK,
  obra_name TEXT REFERENCES obras(obra_name),
  pavimento TEXT,
  elemento_id TEXT,                    -- P001, V002_A, L003, etc.
  elemento_tipo TEXT,                  -- PIL|VIG_LAT|VIG_FUNDO|LAJ
  json_path TEXT,                      -- caminho do JSON no disco (referencia)
  dados_json TEXT,                     -- espelho do conteudo do JSON
  versao INTEGER DEFAULT 1,            -- incrementa a cada regeneracao
  created_at DATETIME,
  updated_at DATETIME,
  UNIQUE(obra_name, pavimento, elemento_id)
)

-- Indice para queries do Comparison Engine
CREATE INDEX idx_f4_obra_pav  ON fase4_fichas(obra_name, pavimento);
CREATE INDEX idx_f4_tipo      ON fase4_fichas(obra_name, elemento_tipo);
```

```sql
-- Regras de transformacao (JA EXISTE)
transformation_rules (id PK, rule_name UNIQUE, rule_type, params_json, created_at)
-- CORRECAO PENDENTE: ab_test_batch.control_rule_id aponta para backup table
```

#### Camada 5 — Geracao (Fase 5)
```sql
-- Rastreamento dos DXFs gerados pelos robos (atualmente implicito no filesystem)
-- RECOMENDACAO: criar tabela gerations no EPIC 7 para rastrear ciclos de geracao
generation_runs (
  id PK, obra_name, pavimento, robo_type TEXT,  -- PL|LV|FV|LJ
  input_json_path TEXT, output_dxf_path TEXT,
  entity_count INTEGER, duration_s REAL,
  status TEXT, error_msg TEXT,
  created_at DATETIME
)
```

#### Camada 6 — Validacao / Comparison Engine (Fase 6 — EPIC 7)
```sql
-- Runs de comparacao Forward x Reverse
comparison_runs (
  id PK, obra_name TEXT, pavimento TEXT,
  n1_score REAL, n2_score REAL, n3_score REAL, n4_score REAL,
  nivel TEXT,                          -- N1|N2|N3|N4
  run_at DATETIME, run_by TEXT        -- humano|auto
)

-- Deltas campo-a-campo
comparison_deltas (
  id PK,
  run_id INTEGER REFERENCES comparison_runs(id),
  elemento_id TEXT, elemento_tipo TEXT,
  campo TEXT, valor_n1 TEXT, valor_n2 TEXT,
  match INTEGER,                       -- 1=MATCH, 0=DELTA
  delta_abs REAL, delta_pct REAL,
  ausente_fwd INTEGER, ausente_rev INTEGER
)

-- Mapeamento campo -> robo -> SCR (inteligencia dos robos)
robot_field_map (
  id PK, elemento_tipo TEXT,          -- PIL|VIG|LAJ
  campo TEXT,                          -- grade_1, comp, h, ...
  robo_script TEXT,                    -- gerar_pl_dxf_stog.py
  scr_variable TEXT,                   -- COMP_TOTAL
  scr_line_approx INTEGER,             -- ~linha 47
  formula TEXT,                        -- grade_1 = comp + 22
  visual_impact TEXT,                  -- "comprimento total do painel no DXF"
  versao TEXT
)

-- Sinais de treinamento para retroalimentacao do RAG
training_signals (
  id PK,
  delta_id INTEGER REFERENCES comparison_deltas(id),
  sinal_tipo TEXT,                     -- SISTEMATICO|ANOMALIA|OK
  acao_sugerida TEXT,                  -- FIX_GERADOR|REGRA_RAG|IGNORAR
  obra_similar_json TEXT,              -- obras com padrao similar
  incorporado INTEGER DEFAULT 0,       -- 0=pendente, 1=aplicado
  created_at DATETIME
)
```

#### Camada 7 — Certificacao (Fase 7-8)
```sql
-- Certificados por obra (atualmente em CERTIFICADO.json no disco)
-- RECOMENDACAO: manter JSON + adicionar linha na tabela para queries rapidas
obra_certifications (
  id PK, obra_name TEXT REFERENCES obras(obra_name),
  score_pil REAL, score_lv REAL, score_fv REAL, score_laj REAL,
  score_global REAL, certificado_path TEXT,
  status TEXT,                         -- CERTIFICADO|REPROVADO|PENDENTE
  certified_at DATETIME, certified_by TEXT
)
```

### 12.4 RAG Collections (LanceDB)

| Collection | Store | Dimensao | Status | Fase |
|------------|-------|----------|--------|------|
| `stog_kbs` | stog_rag_db | 4096 (NVIDIA NIM) | OPERACIONAL | F0 |
| `domain_knowledge` | stog_rag_db | 4096 | OPERACIONAL (217 chunks) | F0 |
| `universal_layers` | stog_rag_db | — | OPERACIONAL | F0 |
| `obra_docs` | obra_rag_db (por-obra) | 4096 | FUTURO — EPIC 1 | F1 |
| `obra_dxfs` | obra_rag_db (por-obra) | 4096 | FUTURO — EPIC 1 | F1 |
| `corrections` | stog_rag_db | 4096 | FUTURO — EPIC 5 | F6 |

### 12.5 Mapeamento Fases x DB x EPIC

| Fase | O que persiste | Storage | EPIC que implementa |
|------|---------------|---------|---------------------|
| F0 (STOG KB) | stog_kbs, domain_knowledge | LanceDB global | Concluido |
| F1 (Ingestao) | project_documents, obra_triagem | SQLite | EPIC 1 (parcial) |
| F1 (RAG) | obra_docs, obra_dxfs | LanceDB por-obra | EPIC 1 (pendente) |
| F2 (Triagem) | obra_triagem (status updates) | SQLite | EPIC 2 (concluido) |
| F2b (Recortes) | obra_recortes | SQLite | EPIC 2 (concluido) |
| F3 (Interpretacao) | fase3_fichas, pillars, beams, slabs | SQLite | Concluido |
| F4 (Sincronizacao) | JSONs no disco (robos) + fase4_fichas espelho (queries) | Filesystem + SQLite | EPIC 7 (dupla escrita em motor_fase4.py) |
| F5 (Geracao) | generation_runs (a criar) | SQLite | EPIC 7 |
| F6 (Validacao) | comparison_runs, comparison_deltas | SQLite | EPIC 7 |
| F7/F8 (Fidelidade) | obra_certifications | SQLite + JSON | EPIC 7 |
| Feedback loop | corrections, training_signals, robot_field_map | LanceDB + SQLite | EPIC 5+7 |

### 12.6 Migracoes Imediatas (Zero Risco — Fazer Agora)

```sql
-- 1. Indices faltantes (zero downtime)
CREATE INDEX IF NOT EXISTS idx_ot_obra_status ON obra_triagem(obra_name, status);
CREATE INDEX IF NOT EXISTS idx_pd_obra_phase  ON project_documents(obra_name, phase);

-- 2. Colunas adicionais em obra_triagem
ALTER TABLE obra_triagem ADD COLUMN user_category TEXT;
ALTER TABLE obra_triagem ADD COLUMN evidence_json TEXT;
ALTER TABLE obra_triagem ADD COLUMN approved_at DATETIME;
ALTER TABLE obra_triagem ADD COLUMN updated_at  DATETIME;

-- 3. Colunas adicionais em project_documents
ALTER TABLE project_documents ADD COLUMN file_hash   TEXT;
ALTER TABLE project_documents ADD COLUMN dxf_version TEXT;
ALTER TABLE project_documents ADD COLUMN entity_count INTEGER;
ALTER TABLE project_documents ADD COLUMN updated_at  DATETIME;

-- 4. Coluna updated_at em obra_recortes
ALTER TABLE obra_recortes ADD COLUMN updated_at DATETIME;

-- 5. Correcao do bug FK em ab_test_batch
-- VERIFICAR: qual e a tabela correta antes de executar
-- UPDATE ab_test_batch SET control_rule_id = (SELECT id FROM transformation_rules WHERE ...)
```

### 12.7 O Que NAO Mudar

- **dxf_entidades** — 1.9M rows, schema correto, nao tocar
- **fase3_fichas, pillars, beams, slabs** — operacionais, nao refatorar
- **stog_rag_db/** — LanceDB operacional, nao migrar para outro storage
- **JSONs Fase-4** (JSON_Pilares/, JSON_Vigas/, JSON_Lajes/) — os geradores dependem diretamente; NUNCA substituir. A tabela `fase4_fichas` existe em PARALELO como espelho para queries do Comparison Engine. Dupla escrita em `motor_fase4.py`: salva JSON (robos) + UPSERT SQLite (engine). Zero conflito.

---

*Documento gerado por Morgan (PM/Strategist) — Synkra AIOS. Revisao recomendada a cada sprint.*
