# ARQUITETURA DB — CAD-ANALYZER
**Data:** 2026-06-06 | **Autores:** Dara (Data Engineer) + Dex (Dev) — Synkra AIOS
**Referência:** MASTERPLAN-CAD-ANALYZER.md + auditoria completa do project_data.vision

---

## 1. Visão Geral: Um DB, Três Stores

```
project_data.vision (SQLite 1.3 GB)
├── Store 1: Metadados estruturados (obras, triagem, recortes, fichas, robôs)
├── Store 2: Cache de DXF + Entidades (dxf_entidades 1.9M rows — maior fatia)
└── Store 3: Pipeline state, logs, métricas

stog_rag_db/ (LanceDB — global)
└── STOG Knowledge Base: 548 KBs, 4096-dim NVIDIA NIM
    ├── stog_kbs (embeddings de DXFs STOG de referência)
    ├── domain_knowledge (217 chunks, 9 doc_types)
    └── cross_obra_baselines (medians PIL/LV/LJ/FV)

DADOS-OBRAS/Obra_X/obra_rag_db/ (LanceDB — por-obra, EPIC 1)
└── obra_docs (PDFs/MDs ingeridos)
└── obra_dxfs (classificação DXFs)
```

**Regra clara:**
- SQLite = **fatos estruturados** (o que é, onde está, qual status, qual score)
- LanceDB = **semântica vetorial** (o que significa, como se parece, o que é similar)

---

## 2. Pipeline Completo × Camadas de Dados

```
FASE 0  ──────────────────────────────────────────────────────────────────
  STOG KB Extraction
  Input:  DXFs STOG humanos (Projetos_Finalizados_para_Engenharia_Reversa/)
  Output: stog_rag_db/ (LanceDB global)
  DB:     cross_obra_baselines.json, universal_layers
  Status: OPERACIONAL ✅

FASE 1  ──────────────────────────────────────────────────────────────────
  Ingestão & Triagem de Documentos
  Input:  DWGs/DXFs/PDFs brutos da obra
  Output: obra_triagem (SQLite), obra_rag_db/ (LanceDB por-obra)
  DB:     obras, obra_triagem, project_documents, ingestao_metadata
  Status: PARCIAL — auto_indexer OK, RAG pipeline EPIC 1 em andamento

FASE 2  ──────────────────────────────────────────────────────────────────
  Triagem com IA + Recortes
  Input:  obra_triagem (approved brutos)
  Output: obra_recortes (SQLite), DXFs em Fase-2_Triagem/
  DB:     obra_recortes, dxf_entidades
  Status: PARCIAL — recortes manuais OK, crop engine OK, IA automática pendente

FASE 3  ──────────────────────────────────────────────────────────────────
  Diagnóstico Visual + Interpretação/Extração (N1)
  Input:  DXFs recortados aprovados
  Output: fase3_fichas N1, pilares.json, vigas.json, lajes.json
  DB:     fase3_fichas, pillars, beams, slabs, validation_log
  Status: OPERACIONAL (motor_fase4.py) — bugs B1+LV-B2 corrigidos ✅

FASE 4  ──────────────────────────────────────────────────────────────────
  Sincronização / Conversão para Robô (N3)
  Input:  fase3_fichas N1
  Output: fase4_fichas N3, JSON_Pilares/, JSON_Vigas/, JSON_Lajes/
  DB:     fase4_fichas (AUSENTE — hoje só JSONs em disco)
  Status: OPERACIONAL via filesystem — sem tabela SQLite formal

FASE 5/6  ────────────────────────────────────────────────────────────────
  Geração de Scripts + Execução CAD (Robôs)
  Input:  fase4_fichas N3 (JSONs)
  Output: DXF/SCR por robô, PNGs de validação
  DB:     generated_scripts, robot_outputs (AUSENTE — expandir)
  Status: OPERACIONAL — PL/LV/FV/LJ certificados em 20 obras ✅

FASE 7  ──────────────────────────────────────────────────────────────────
  Consolidação + Comparison Engine
  Input:  DXF gerado (N3/N4) vs STOG reverso (N2)
  Output: scores de fidelidade, training_signals
  DB:     comparison_runs (AUSENTE), comparison_deltas (AUSENTE),
          training_signals (AUSENTE — hoje parcial em training_events)
  Status: PARCIAL — comparar_fichas.py OK, DB formal ausente

FASE 8  ──────────────────────────────────────────────────────────────────
  Revisão e Certificação
  Input:  scores Fase 7
  Output: CERTIFICADO.json
  DB:     (nenhum específico ainda)
  Status: OPERACIONAL via filesystem ✅
```

---

## 3. Estado Atual vs Arquitetura Ideal

### 3.1 Tabelas Existentes — Diagnóstico

| Tabela | Rows | Estado | Problema Principal |
|--------|------|--------|-------------------|
| `obras` | 7 | ✅ OK | Subpopulada (29 obras no disco) |
| `obra_triagem` | 51 | ⚠️ PARCIAL | Sem FK para obras, sem updated_at, sem dxf_version |
| `project_documents` | 4.265 | ⚠️ DUPLICATA | Sobrepõe com obra_triagem — dois indexes para a mesma coisa |
| `obra_recortes` | 2 | ⚠️ PARCIAL | Sem FK para obra_triagem, UNIQUE constraint frágil |
| `fase3_fichas` | 405 | ⚠️ PARCIAL | Sem FK para obra_recortes, sem link para fase4 |
| `pillars` | 6.524 | ✅ OK | FK para projects (não para obras — diferente) |
| `beams` | 7.005 | ✅ OK | Idem |
| `slabs` | 4.637 | ✅ OK | Idem |
| `dxf_entidades` | 1.928.880 | ✅ OK | Maior tabela, bem indexada |
| `transformation_rules` | 23 | ✅ OK | Schema maduro, versionado, A/B test |
| `validation_log` | 381 | ✅ OK | Bom schema de auditoria |
| `cache_dxf` | 157 | ✅ OK | Hash + mtime + hit_count corretos |
| `ab_test_batch` | 0 | 🔴 BUG | FK aponta para tabela BACKUP, não para transformation_rules |
| `fase4_fichas` | — | 🔴 AUSENTE | N3 existe só como JSONs no disco |
| `eng_reversa_fichas` | — | 🔴 AUSENTE | N2 ground truth disperso/implícito |
| `robots` | — | 🔴 AUSENTE | Catálogo de robôs não existe no DB |
| `robot_field_map` | — | 🔴 AUSENTE | Mapeamento campo→SCR não existe |
| `comparison_runs` | — | 🔴 AUSENTE | Comparison Engine sem tabela formal |
| `comparison_deltas` | — | 🔴 AUSENTE | Divergências N1/N2/N3 não rastreadas |
| `training_signals` | — | 🔴 AUSENTE | Loop de treino não fechado |
| `robot_outputs` | — | 🔴 AUSENTE | generated_scripts insuficiente |

### 3.2 Tabelas a Eliminar / Consolidar

| Tabela | Destino |
|--------|---------|
| `project_documents` | Absorver em `obra_triagem` expandida — são a mesma coisa |
| `beams_backup_legacy` | Exportar para arquivo .sql separado, deletar do DB |
| `pillars_backup_legacy` | Idem |
| `slabs_backup_legacy` | Idem |
| `transformation_rules_backup_20260214_162533` | Idem — corrigir FK de ab_test_batch |
| `works` | Unificar com `obras` — dois conceitos para a mesma entidade |
| `projects` | Avaliar — pode virar `obra_pavimentos_dxf` (cada row = 1 DXF por pavimento) |

---

## 4. Schema Ideal — Arquitetura Proposta

```sql
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CAMADA 0 — ÂNCORAS GLOBAIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

obras
  id TEXT PK
  nome TEXT UNIQUE NOT NULL          ← chave de negócio
  pasta_origem TEXT NOT NULL
  cliente TEXT
  fase_atual INTEGER DEFAULT 1
  status TEXT DEFAULT 'iniciado'
  created_at TIMESTAMP DEFAULT NOW
  updated_at TIMESTAMP DEFAULT NOW

robots                               ← NOVO — catálogo dos robôs
  id TEXT PK
  nome TEXT UNIQUE NOT NULL          ← 'pilar-abcd', 'laje-hlaz', 'viga-lv'
  tipo_peca TEXT NOT NULL            ← PIL | VIG | LAJ | FV | LV | GF
  versao TEXT NOT NULL
  output_format TEXT NOT NULL        ← DXF | SCR | LISP
  template_path TEXT
  schema_ficha_json TEXT             ← campos N3 que este robô consome
  descricao TEXT
  created_at TIMESTAMP DEFAULT NOW

robot_field_map                      ← NOVO — relação campo↔linha SCR
  id TEXT PK
  robot_id TEXT FK → robots.id
  campo_n3 TEXT NOT NULL             ← 'comp', 'grade_1', 'laje_pos'
  campo_scr TEXT NOT NULL            ← variável no template SCR
  linha_scr_aprox INTEGER            ← linha do template onde afeta
  formula TEXT                       ← 'comp + 22' (grade_1 = comp + 22)
  impacto TEXT                       ← 'grade topo pilar, erro = pilar sem armação'
  tipo_dado TEXT                     ← REAL | INT | ENUM
  obrigatorio BOOLEAN DEFAULT TRUE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CAMADA 1 — FASE 1: TRIAGEM (consolidada)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

obra_triagem                         ← absorve project_documents
  id TEXT PK
  obra_id TEXT FK → obras.id         ← FK real (hoje string solta)
  file_path TEXT NOT NULL UNIQUE
  file_name TEXT NOT NULL
  file_ext TEXT
  dxf_version TEXT                   ← NOVO: AC1009/AC1032 (detecta Aspose)
  entity_count INTEGER               ← NOVO: contagem rápida ao indexar
  suggested_category TEXT
  suggested_order INTEGER DEFAULT 0
  confidence REAL DEFAULT 0.0
  status TEXT DEFAULT 'pending'      ← pending|approved|rejected|reclassified
  classifier TEXT                    ← 'rag_layer1'|'rag_layer2'|'rag_layer3'|'human'
  evidence_json TEXT                 ← evidências da classificação
  notes TEXT
  created_at TIMESTAMP DEFAULT NOW
  updated_at TIMESTAMP DEFAULT NOW   ← NOVO

INDEX: obra_triagem(obra_id, status)
INDEX: obra_triagem(file_path)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CAMADA 2 — FASE 2: RECORTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

obra_recortes
  id TEXT PK
  obra_triagem_id TEXT FK → obra_triagem.id  ← FK real (hoje path string)
  obra_id TEXT FK → obras.id
  pavimento_name TEXT NOT NULL
  recorte_type TEXT NOT NULL         ← PIL|VIG|LAJ|FV|LV|GF
  recorte_index INTEGER DEFAULT 0
  output_path TEXT
  bbox_auto TEXT
  bbox_approved TEXT
  entity_count INTEGER DEFAULT 0
  score REAL DEFAULT 0.0
  status TEXT DEFAULT 'auto'
  n_torres INTEGER DEFAULT 1
  created_at TIMESTAMP DEFAULT NOW
  updated_at TIMESTAMP DEFAULT NOW   ← NOVO

UNIQUE(obra_id, pavimento_name, recorte_type, recorte_index)
INDEX: obra_recortes(obra_id, recorte_type, status)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CAMADA 3 — FASE 3: INTERPRETAÇÃO (N1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

fase3_fichas  (N1)
  id TEXT PK
  recorte_id TEXT FK → obra_recortes.id   ← FK real (hoje orphan)
  obra_id TEXT FK → obras.id
  pavimento TEXT NOT NULL
  tipo TEXT NOT NULL                 ← PIL|VIG|LAJ|FV|LV|GF
  codigo TEXT NOT NULL               ← P01, V03, L07
  dados_json TEXT                    ← campos semânticos extraídos
  confidence REAL DEFAULT 0.0
  dna_vector TEXT                    ← embedding desta peça (RAG layer 2)
  revisado BOOLEAN DEFAULT FALSE
  revisado_por TEXT
  data_revisao TIMESTAMP
  created_at TIMESTAMP DEFAULT NOW
  updated_at TIMESTAMP DEFAULT NOW

INDEX: fase3_fichas(obra_id, pavimento, tipo)
UNIQUE(obra_id, pavimento, tipo, codigo)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CAMADA 4 — GROUND TRUTH (N2 — Engenharia Reversa)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

eng_reversa_fichas  (N2)             ← NOVO — hoje disperso em JSONs
  id TEXT PK
  obra_id TEXT FK → obras.id
  pavimento TEXT NOT NULL
  tipo TEXT NOT NULL
  codigo TEXT NOT NULL
  dados_json TEXT                    ← verdade absoluta do engenheiro STOG
  dxf_origem_path TEXT               ← DXF de eng. reversa de onde veio
  extraido_por TEXT DEFAULT 'stog_extractor'  ← 'human'|'motor'|'stog_extractor'
  created_at TIMESTAMP DEFAULT NOW

UNIQUE(obra_id, pavimento, tipo, codigo)
INDEX: eng_reversa_fichas(obra_id, tipo)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CAMADA 5 — FASE 4: CONVERSÃO PARA ROBÔ (N3)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

fase4_fichas  (N3)                   ← NOVO — hoje só JSONs no disco
  id TEXT PK
  ficha_n1_id TEXT FK → fase3_fichas.id
  robot_id TEXT FK → robots.id       ← qual robô vai consumir
  obra_id TEXT FK → obras.id
  pavimento TEXT NOT NULL
  tipo TEXT NOT NULL
  codigo TEXT NOT NULL
  dados_robot_json TEXT              ← campos no formato esperado pelo robô
  campos_faltantes_json TEXT         ← campos obrigatórios não preenchidos
  status TEXT DEFAULT 'ready'        ← ready|incomplete|error
  created_at TIMESTAMP DEFAULT NOW
  updated_at TIMESTAMP DEFAULT NOW

INDEX: fase4_fichas(obra_id, robot_id, status)
UNIQUE(obra_id, pavimento, tipo, codigo, robot_id)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CAMADA 6 — COMPARISON ENGINE (N1+N3 vs N2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

comparison_runs                      ← NOVO
  id TEXT PK
  obra_id TEXT FK → obras.id
  run_at TIMESTAMP DEFAULT NOW
  modo TEXT DEFAULT 'full'           ← 'full'|'incremental'
  n1_count INTEGER DEFAULT 0
  n2_count INTEGER DEFAULT 0
  n3_count INTEGER DEFAULT 0
  match_rate_n1_n2 REAL              ← % campos corretos N1 vs N2
  match_rate_n3_n2 REAL              ← % campos corretos N3 vs N2
  status TEXT DEFAULT 'running'      ← running|done|error

comparison_deltas                    ← NOVO — divergências granulares
  id TEXT PK
  run_id TEXT FK → comparison_runs.id
  obra_id TEXT FK → obras.id
  pavimento TEXT NOT NULL
  tipo TEXT NOT NULL
  codigo TEXT NOT NULL
  ficha_n1_id TEXT FK → fase3_fichas.id
  ficha_n3_id TEXT FK → fase4_fichas.id
  ficha_n2_id TEXT FK → eng_reversa_fichas.id
  campo TEXT NOT NULL                ← 'laje_pos', 'grade_1', 'comp'
  valor_n1 TEXT
  valor_n3 TEXT
  valor_n2 TEXT                      ← ground truth
  delta_tipo TEXT NOT NULL           ← WRONG|MISSING|EXTRA
  severidade TEXT DEFAULT 'MEDIUM'   ← HIGH|MEDIUM|LOW
  robot_impacto_json TEXT            ← quais robôs/linhas SCR são afetados

INDEX: comparison_deltas(run_id, severidade)
INDEX: comparison_deltas(obra_id, campo, delta_tipo)

training_signals                     ← NOVO — loop de aprendizado fechado
  id TEXT PK
  delta_id TEXT FK → comparison_deltas.id
  campo TEXT NOT NULL
  valor_errado TEXT
  valor_correto TEXT
  contexto_json TEXT                 ← entidades DXF vizinhas relevantes
  tipo_correcao TEXT                 ← RULE_UPDATE|THRESHOLD|MANUAL
  aplicado BOOLEAN DEFAULT FALSE
  aplicado_em TIMESTAMP
  aplicado_por TEXT
  melhora_accuracy REAL              ← delta accuracy antes/depois

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CAMADA 7 — FASES 5/6: OUTPUTS DOS ROBÔS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

robot_outputs                        ← expansão de generated_scripts
  id TEXT PK
  ficha_n3_id TEXT FK → fase4_fichas.id
  robot_id TEXT FK → robots.id
  obra_id TEXT FK → obras.id
  pavimento TEXT NOT NULL
  tipo TEXT NOT NULL
  codigo TEXT NOT NULL
  output_path TEXT NOT NULL          ← arquivo SCR/DXF gerado
  output_format TEXT NOT NULL        ← SCR|DXF|LISP
  campos_usados_json TEXT            ← snapshot dos valores N3 usados
  linhas_geradas INTEGER             ← tamanho do SCR
  status TEXT DEFAULT 'generated'    ← generated|validated|error
  validation_dxf_path TEXT           ← DXF resultante para visual QA
  generated_at TIMESTAMP DEFAULT NOW
  validated_at TIMESTAMP

INDEX: robot_outputs(obra_id, robot_id, status)
```

---

## 5. RAG — Três Collections, Responsabilidades Claras

```
stog_rag_db/                         GLOBAL — Fase 0
├── stog_kbs                         DXFs STOG humanos embedados
├── domain_knowledge                 217 chunks semânticos (SEMANTICA-*.md)
│   ├── SEMANTICA-PILAR-NOVA.md      faces A/B=longas C/D=curtas, grade_1=comp+22
│   ├── SEMANTICA-VIGA-NOVA.md       segmentação 122cm, pillar_left/right
│   └── SEMANTICA-LAJE-NOVA.md       linhas cumulativas, is_union <=30cm
├── cross_obra_baselines             medians PIL/LV/LJ/FV
└── robot_dna  ← NOVO               como cada campo N3 afeta SCR/DXF
    ├── pilar-abcd: "grade_1=comp+22, linha 187 SCR, erro=pilar sem armação topo"
    ├── pilar-grades: "h1=244cm define chapas, parafusos=comp+24"
    └── laje-hlaz: "laje_pos=nº painel NOVA (não índice), erro=laje deslocada 1 vão"

DADOS-OBRAS/Obra_X/obra_rag_db/      POR-OBRA — Fase 1 (EPIC 1)
├── obra_docs                        PDFs/MDs da obra embedados
└── obra_dxfs                        classificação DXFs (3 camadas)

stog_rag_db/corrections  ← NOVO     GLOBAL — Fase 5 (EPIC 5)
└── validated_extractions            campo corrigido + contexto → retroalimenta Fase 3
```

---

## 6. Relação Fases Masterplan × Camadas DB

| Fase Masterplan | EPIC | Tabelas Principais | RAG Envolvido |
|-----------------|------|--------------------|---------------|
| Fase 0 — STOG KB | — | — | stog_kbs, domain_knowledge |
| Fase 1 — Ingestão | EPIC 1 | obras, obra_triagem | obra_rag_db (por-obra) |
| Fase 2 — Triagem | EPIC 2 | obra_triagem, obra_recortes | obra_rag_db → classifica |
| Fase 3 — Interpretação | EPIC 4/5 | fase3_fichas (N1) | domain_knowledge + robot_dna |
| Fase 4 — Sincronização | EPIC 7 | fase4_fichas (N3) | — |
| Fase 5/6 — Robôs | EPIC 7 | robot_outputs, robots, robot_field_map | robot_dna |
| Fase 7 — Comparison | EPIC 7 | comparison_runs, comparison_deltas, training_signals | corrections |
| Fase 8 — Certificação | EPIC 7 | (via Fase 7 scores) | — |

---

## 7. Plano de Migração — O Que Fazer e Quando

### Prioridade IMEDIATA (zero risco, agora)
```sql
-- 1. Índices faltando em obra_triagem
CREATE INDEX IF NOT EXISTS idx_triagem_obra_status
  ON obra_triagem(obra_name, status);

-- 2. Coluna dxf_version em obra_triagem
ALTER TABLE obra_triagem ADD COLUMN dxf_version TEXT;
ALTER TABLE obra_triagem ADD COLUMN entity_count INTEGER;
ALTER TABLE obra_triagem ADD COLUMN updated_at TEXT;

-- 3. Coluna updated_at em obra_recortes
ALTER TABLE obra_recortes ADD COLUMN updated_at TEXT;

-- 4. Corrigir bug FK ab_test_batch → transformation_rules (não backup)
-- (requer recriar a tabela pois SQLite não suporta ALTER CONSTRAINT)
```

### Prioridade EPIC 1 (junto com RAG pipeline)
```
+ Criar tabela robots (catálogo dos 6 robôs existentes)
+ Criar tabela robot_field_map (mapear campos N3 → linhas SCR)
+ Adicionar obra_triagem_id FK em obra_recortes (nullable, preencher em novos)
+ Popular tabela obras com todas as 29 obras do disco
```

### Prioridade EPIC 7 (Comparison Engine)
```
+ Criar eng_reversa_fichas (N2) — migrar de JSONs em disco
+ Criar fase4_fichas (N3) — migrar de JSONs em disco
+ Criar comparison_runs + comparison_deltas + training_signals
+ Criar robot_outputs — expandir generated_scripts
+ Adicionar recorte_id FK em fase3_fichas
```

### Futuro (após volume > 100 obras)
```
+ Migrar obra_name strings → obra_id FKs em todas as tabelas
+ Extrair dxf_entidades para DB separado (está crescendo ~200MB/obra)
+ Consolidar project_documents + obra_triagem em uma só tabela
+ Mover backup tables para arquivos .sql externos
```

---

## 8. O Que Não Mudar

| Item | Por quê manter |
|------|---------------|
| `transformation_rules` + `validation_log` | Schema maduro, bem indexado, em produção |
| `cache_dxf` + `cache_fichas` | Arquitetura de cache correta (hash + mtime) |
| `performance_metrics` + `pipeline_state` | Infraestrutura de observabilidade funcional |
| `dxf_entidades` (1.9M rows) | Core do sistema, bem indexado — só mover quando >500M rows |
| `pillars`/`beams`/`slabs` | Resultado final estruturado — FK para projects mantida por compatibilidade |
| `fase3_fichas.dna_vector` | Embrião do RAG layer 2 — preservar e expandir |

---

*Gerado por Dara (Data Engineer) + análise do MASTERPLAN-CAD-ANALYZER.md*
*Próxima revisão: ao iniciar EPIC 7 (Comparison Engine)*
