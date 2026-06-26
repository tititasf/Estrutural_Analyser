# MASTERPLAN — Engenharia Reversa & Dual-Flow Comparison Engine
**Versão:** 1.2
**Data:** 2026-06-10
**Autor:** Aria (Architect) — Synkra AIOS
**Status:** ATIVO — ER-2 em andamento (Sprint 2/3 concluídos parcialmente)

---

## 1. Visão Estratégica

Este masterplan estende o CAD-ANALYZER com um **segundo fluxo de interpretação** baseado em engenharia reversa dos DXFs STOG humanos. O objetivo é ter dois resultados de interpretação independentes que podem ser comparados, refinados e cruzados no Comparison Engine para convergir para a solução perfeita (Arete ≥ 90%).

### Problema que resolve

O pipeline atual tem apenas **um caminho** de interpretação:
```
DXF bruto → Fase-3 → Fase-4 (N1) → Robô (N3)
```

O novo pipeline adiciona um **segundo caminho paralelo** via engenharia reversa dos STOGs humanos:
```
DXF STOG humano → Motor Reverso (N2) → Robô Granular (N4)
```

### Resultado final: Dual-Flow Comparison Engine

```
                  ┌─────────────────┐
DXF Bruto ───────►│ Motor 1 (Básico)│──────────────► N1 (Structural)
                  └─────────────────┘                │
DXF Bruto ───────►│ Motor 2 (+Ctx)  │──────────────► N1+ctx            ► N3 (Robô)
                  └─────────────────┘                │                      │
DXF STOG humano ─►│ Motor 3 (RevEng)│──────────────► N2 (Granular) ────► N4 (Robô) │
                  └─────────────────┘                                         │
                                        Comparison Engine ◄──────────────────┘
                                        (N1 vs N2 vs N3 vs N4 — score cruzado)
```

---

## 2. Alinhamento com Masterplans Existentes

### Reconciliação de nomenclatura N1–N4

O MASTERPLAN-CAD-ANALYZER.md (EPIC 7) definiu N1-N4 como *níveis progressivos de fidelidade* de um único fluxo. Este masterplan **redefine** N1-N4 como *fluxos e artefatos paralelos*:

| Símbolo | Definição Anterior (EPIC 7) | Nova Definição (este masterplan) |
|---------|----------------------------|----------------------------------|
| N1 | Score básico (IDs, contagens) | **Itens estruturais** do pipeline bruto (Fase-3/4) |
| N2 | Score dimensional | **Itens granulares** do Motor Reverso (NOVO) |
| N3 | Score de geração do Robô | **DXF gerado** pelo Robô a partir de N1 |
| N4 | Score de fidelidade final | **DXF gerado** pelo Robô a partir de N2 (granular) |

> **Nota de compatibilidade:** O EPIC 7 original é absorvido e expandido por este masterplan. As stories E7.1–E7.6 do MASTERPLAN-CAD-ANALYZER.md passam a ser detalhadas aqui com maior granularidade.

### Posição no Roadmap Global

| EPIC | Masterplan Origem | Status | Impacto |
|------|------------------|--------|---------|
| EPIC 1 (RAG Pipeline) | CAD-ANALYZER | ✅ CONCLUÍDO | Pré-requisito de ER-4 |
| EPIC 2 (Triagem) | CAD-ANALYZER | ✅ CONCLUÍDO | Fornece brutos aprovados |
| EPIC 3 (Design Hub) | CAD-ANALYZER | Planejado | Paralelo independente |
| EPIC 4 (Hub Funcionalidades) | CAD-ANALYZER | Planejado | Paralelo independente |
| EPIC 5 (Spec Fase-3) | CAD-ANALYZER | Planejado | Paralelo independente |
| **EPIC ER-1** | **Este doc** | **Planejado** | CE Tab Switcher |
| **EPIC ER-2** | **Este doc** | **🔄 EM ANDAMENTO** | Diagnostic Reverse Hub |
| **EPIC ER-3** | **Este doc** | **Planejado** | Motor Reverso por Classe |
| **EPIC ER-4** | **Este doc** | **Planejado** | RAG Engenharia Reversa |
| **EPIC ER-5** | **Este doc** | **Planejado** | Motor 3 no Structural Analyzer |
| **EPIC ER-6** | **Este doc** | **Planejado** | N4 Pipeline + Comparison Cross |

### Sequência de dependências

```
ER-1 ──────────────────────────────────────────────────────────► CE Tab Switcher (UI)
ER-2 ──────────────────────────────────────────────────────────► Hub + recortes reversos
ER-3 ──► (depende ER-2 UI) ────────────────────────────────────► Motor reverso por classe
ER-4 ──► (depende ER-3) ────────────────────────────────────────► RAG reverso
ER-5 ──► (depende ER-4) ────────────────────────────────────────► Motor 3 Structural Analyzer
ER-6 ──► (depende ER-3 + ER-2) ────────────────────────────────► N4 + Comparison cruzado
```

---

## 3. Nova Arquitetura de Abas (10 tabs)

| Tab | Nome Atual | Mudança |
|-----|-----------|---------|
| 0 | Gerenciar Projetos | Sem mudança |
| 1 | Diagnostic Hub (Pré) | Sem mudança |
| **2** | **Diagnostic Reverse Hub** | **NOVO** |
| 3 | Structural Analyzer | Renumerado (era tab 2) |
| 4 | Comparison Engine | Renumerado (era tab 3) |
| 5 | Robo Pilares | Renumerado (era tab 4) |
| 6 | Robo LV | Renumerado (era tab 5) |
| 7 | Robo FV | Renumerado (era tab 6) |
| 8 | Robo LJ | Renumerado (era tab 7) |

> **Impacto técnico:** `main.py` precisa renumerar tabs. `QTabWidget.insertTab()` na posição 2 é suficiente — não requer reescrita de módulos existentes.

---

## 4. EPIC ER-1: CE Tab Switcher (Comparison Engine)

**Prioridade:** P0 | **Duração:** ~3 dias | **Pré-requisito:** Nenhum
**Objetivo:** Adicionar seletor de abas acima das 4 classes no Comparison Engine para separar o fluxo estrutural do fluxo de engenharia reversa.

### Mudança de UI

```
┌────────────────────────────────────────────────────────┐
│  [Itens Estrutural N1/N3]  [Itens Eng. Reversa N2/N4]  │  ← novo switcher
├────────────────────────────────────────────────────────┤
│  [ Pilares ] [ L. Viga ] [ Fdo. Viga ] [ Lajes ]       │  ← classes (existentes)
├────────────────────────────────────────────────────────┤
│  Lista de itens (muda conforme a aba selecionada)      │
└────────────────────────────────────────────────────────┘
```

**Aba 1 (Itens Estrutural N1/N3):** lista atual — items do pipeline bruto (Fase-3/4)
**Aba 2 (Itens Eng. Reversa N2/N4):** lista vazia até rodar Motor Reverso — populada via `reverse_eng_fichas` DB

### Stories

| ID | Descrição | Arquivo(s) | Complexidade |
|----|-----------|-----------|--------------|
| ER-1.1 | `QTabWidget` acima das classes com 2 abas: "Itens Estrutural N1/N3" e "Itens Eng. Reversa N2/N4" | `comparison_engine.py` | LOW |
| ER-1.2 | Aba 2 busca itens de `reverse_eng_fichas` SQLite ao ser selecionada | `comparison_engine.py` | MEDIUM |
| ER-1.3 | Labels de classe mudam para: Pilares, L.Viga, F.Viga, Lajes (em vez de detalhes/torre1/torre2) | `comparison_engine.py` | LOW |

### Arquivos a modificar

```
src/ui/modules/comparison_engine.py  ← adicionar QTabWidget, conectar slot de mudança de aba
src/core/database.py                 ← query reverse_eng_fichas (tabela criada no ER-2)
```

---

## 5. EPIC ER-2: Diagnostic Reverse Hub (Nova Aba)

**Prioridade:** P0 | **Duração:** ~3 semanas | **Pré-requisito:** EPIC 2 (triagem) concluído
**Objetivo:** Módulo PySide6 completo para visualização, recorte e processamento granular dos DXFs STOG humanos.

### Layout da Nova Aba

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                          Diagnostic Reverse Hub                               │
├──────────────────┬─────────────────────────────────────┬─────────────────────┤
│  PAINEL ESQUERDO │           CENTRO (4 tabs)           │  PAINEL DIREITO     │
│                  │                                     │                     │
│  Projetos        │  [Viz.Completo][Viz.Granular]       │  [ Recortar ]       │
│  Finalizados     │  [Ficha Gran.][Ficha Obra ER]       │                     │
│  Reversos        │                                     │  ─────────────────  │
│  Aprovados       │  ┌─────────────────────────────┐   │  Pilares   [ Proc ] │
│                  │  │                             │   │  L.Vigas   [ Proc ] │
│  ┌───────────┐   │  │    Visualizador DXF         │   │  F.Vigas   [ Proc ] │
│  │ P001-TERR │   │  │    (canvas ezdxf)           │   │  Lajes     [ Proc ] │
│  │ V101-TERR │   │  │                             │   │                     │
│  │ L101-TERR │   │  └─────────────────────────────┘   │  ─────────────────  │
│  │ ...       │   │                                     │  [ Salvar  ]        │
│  └───────────┘   │                                     │  [ Aprovar ]        │
│                  │                                     │  [ Excluir ]        │
│  Classes:        │                                     │                     │
│  [PIL][LV][FV][LJ]│                                   │  ─────────────────  │
│                  │                                     │  [ Processar todos  │
│                  │                                     │    itens granulares │
│                  │                                     │    da Obra ]        │
└──────────────────┴─────────────────────────────────────┴─────────────────────┘
```

### Centro — 4 Tabs

| Tab Centro | Conteúdo | Fonte de dados |
|------------|----------|----------------|
| Visualizador Projeto Completo | Canvas DXF do STOG inteiro | `Projetos_Finalizados_para_Engenharia_Reversa/` |
| Visualizador Granular | Canvas recortado do item selecionado | `reverse_eng_recortes` |
| Ficha Granular | Tabela campos extraídos do item (N2) | `reverse_eng_fichas` |
| Ficha Obra Eng. Reversa | Consolidação de todos os itens da obra | `reverse_eng_obra_ficha` |

### Stories

| ID | Descrição | Arquivo(s) | Complexidade |
|----|-----------|-----------|--------------|
| ER-2.1 | Criar `src/ui/modules/diagnostic_reverse_hub.py` — esqueleto do módulo (baseado em `diagnostic_hub.py`) | `diagnostic_reverse_hub.py` (NEW) | HIGH |
| ER-2.2 | Inserir nova aba no `main.py` na posição 2 (`QTabWidget.insertTab`) | `main.py` | LOW |
| ER-2.3 | Painel esquerdo: lista "Projetos Finalizados Reversos Aprovados" com classes Pilares/L.Viga/F.Viga/Lajes | `diagnostic_reverse_hub.py` | MEDIUM |
| ER-2.4 | Canvas centro tab 1: Visualizador Projeto Completo (DXFVectorView existente) | `diagnostic_reverse_hub.py` | MEDIUM |
| ER-2.5 | Canvas centro tab 2: Visualizador Granular (recorte do item) | `diagnostic_reverse_hub.py` | MEDIUM |
| ER-2.6 | Centro tab 3: Ficha Granular (QTableWidget campos N2) | `diagnostic_reverse_hub.py` | MEDIUM |
| ER-2.7 | Centro tab 4: Ficha Obra Eng. Reversa (QTextEdit/QTable consolidado) | `diagnostic_reverse_hub.py` | MEDIUM |
| ER-2.8 | Painel direito: Botão Recortar + 4 botões Processar Granulares por classe | `diagnostic_reverse_hub.py` | MEDIUM |
| ER-2.9 | Botões Salvar/Aprovar/Excluir (mesma lógica do DiagnosticHub) | `diagnostic_reverse_hub.py` | LOW |
| ER-2.10 | Botão "Processar todos itens granulares da Obra" — aciona todos os 4 motores em batch | `diagnostic_reverse_hub.py` | HIGH |
| ER-2.11 | DB schema: `reverse_eng_projetos`, `reverse_eng_fichas`, `reverse_eng_recortes`, `reverse_eng_obra_ficha` | `src/core/database.py` | MEDIUM |

### DB Schema para Engenharia Reversa

```sql
-- Projetos STOG aprovados para engenharia reversa
CREATE TABLE reverse_eng_projetos (
  id           INTEGER PRIMARY KEY,
  obra_name    TEXT NOT NULL REFERENCES obras(obra_name),
  pavimento    TEXT NOT NULL,
  classe       TEXT NOT NULL,   -- PIL|LV|FV|LAJ
  dxf_path     TEXT NOT NULL,   -- caminho do STOG DXF humano
  status       TEXT DEFAULT 'pending', -- pending|approved|excluded
  approved_at  DATETIME,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(obra_name, pavimento, classe, dxf_path)
);

-- Fichas granulares de cada item (N2)
CREATE TABLE reverse_eng_fichas (
  id              INTEGER PRIMARY KEY,
  projeto_id      INTEGER REFERENCES reverse_eng_projetos(id),
  obra_name       TEXT NOT NULL,
  pavimento       TEXT NOT NULL,
  classe          TEXT NOT NULL,    -- PIL|LV|FV|LAJ
  elemento_id     TEXT NOT NULL,    -- P001, V101_A, L101, etc.
  campos_json     TEXT NOT NULL,    -- ficha granular completa (JSON)
  recorte_path    TEXT,             -- caminho do DXF recortado
  confianca       REAL DEFAULT 0.0,
  status          TEXT DEFAULT 'draft', -- draft|approved|excluded
  aprovado_at     DATETIME,
  rag_indexed     INTEGER DEFAULT 0,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME,
  UNIQUE(obra_name, pavimento, elemento_id)
);
CREATE INDEX idx_ref_obra_classe ON reverse_eng_fichas(obra_name, classe);
CREATE INDEX idx_ref_status      ON reverse_eng_fichas(obra_name, status);

-- Recortes visuais dos itens granulares
CREATE TABLE reverse_eng_recortes (
  id            INTEGER PRIMARY KEY,
  ficha_id      INTEGER REFERENCES reverse_eng_fichas(id),
  obra_name     TEXT NOT NULL,
  elemento_id   TEXT NOT NULL,
  recorte_path  TEXT NOT NULL,      -- DXF recortado
  bbox_json     TEXT,               -- bbox do recorte
  entity_count  INTEGER,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Ficha consolidada da obra (visão engenharia reversa)
CREATE TABLE reverse_eng_obra_ficha (
  id                   INTEGER PRIMARY KEY,
  obra_name            TEXT NOT NULL REFERENCES obras(obra_name),
  pavimento            TEXT NOT NULL,
  total_pil            INTEGER DEFAULT 0,
  total_lv             INTEGER DEFAULT 0,
  total_fv             INTEGER DEFAULT 0,
  total_laj            INTEGER DEFAULT 0,
  confianca_media      REAL DEFAULT 0.0,
  resumo_json          TEXT,         -- estatísticas e padrões detectados
  rag_indexed          INTEGER DEFAULT 0,
  gerado_at            DATETIME,
  created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(obra_name, pavimento)
);
```

### LanceDB — Coleções RAG Reverso

```
obra_rag_db/ (por-obra, extensão do EPIC 1)
  ├── obra_docs/           ← EPIC 1 (PDFs/MDs)
  ├── obra_dxfs/           ← EPIC 1 (DXFs brutos)
  ├── reverse_eng_fichas/  ← NOVO (ER-4) — fichas granulares N2 como chunks
  └── reverse_eng_obra/    ← NOVO (ER-4) — ficha obra engenharia reversa
```

---

## 6. EPIC ER-3: Motor Engenharia Reversa por Classe

**Prioridade:** P1 | **Duração:** ~4 semanas | **Pré-requisito:** ER-2 (UI + DB schema)
**Objetivo:** 4 motores de extração granular específicos por classe, que lêem DXFs STOG humanos e geram fichas N2.

### Princípio de funcionamento

O Motor Reverso faz a operação inversa do Robô:
- **Robô:** `ficha (JSON)` → `DXF STOG`
- **Motor Reverso:** `DXF STOG` → `ficha granular (JSON)`

A ficha granular tem o mesmo schema dos JSONs Fase-4 (`JSON_Pilares/`, `JSON_Vigas_Laterais/`, etc.) — mas extraída do STOG humano, não do DXF bruto.

### Stories por Classe

#### Motor Pilares (PIL)

| ID | Descrição | Arquivo(s) | Complexidade |
|----|-----------|-----------|--------------|
| ER-3.1 | `scripts/motor_reverso_pil.py` — extrai campos PIL do STOG PL DXF: comprimento, largura, faces A-H (h1/h2/h3/h4/larg1), grades, distâncias | `scripts/motor_reverso_pil.py` (NEW) | HIGH |
| ER-3.2 | Worker PySide6 `ReversoGranularWorker` — QThread para ER-3.1 com signal `finished(str)` (temp file) | `diagnostic_reverse_hub.py` | MEDIUM |
| ER-3.3 | Salvar fichas PIL no `reverse_eng_fichas` SQLite | `scripts/motor_reverso_pil.py`, `database.py` | LOW |

#### Motor L.Vigas (LV)

| ID | Descrição | Arquivo(s) | Complexidade |
|----|-----------|-----------|--------------|
| ER-3.4 | `scripts/motor_reverso_lv.py` — extrai panels (width/height1/height2), holes, pillar_left/right, sarrafos do STOG LV DXF | `scripts/motor_reverso_lv.py` (NEW) | HIGH |
| ER-3.5 | Worker para motor LV | `diagnostic_reverse_hub.py` | LOW |

#### Motor F.Vigas (FV)

| ID | Descrição | Arquivo(s) | Complexidade |
|----|-----------|-----------|--------------|
| ER-3.6 | `scripts/motor_reverso_fv.py` — extrai estrutura FV (total_height, panels, escoras) | `scripts/motor_reverso_fv.py` (NEW) | MEDIUM |
| ER-3.7 | Worker para motor FV | `diagnostic_reverse_hub.py` | LOW |

#### Motor Lajes (LAJ)

| ID | Descrição | Arquivo(s) | Complexidade |
|----|-----------|-----------|--------------|
| ER-3.8 | `scripts/motor_reverso_laj.py` — extrai dimensões, linhas_verticais, pontaletes do STOG LJ DXF | `scripts/motor_reverso_laj.py` (NEW) | HIGH |
| ER-3.9 | Worker para motor LAJ | `diagnostic_reverse_hub.py` | LOW |

#### Fichas Consolidadas

| ID | Descrição | Arquivo(s) | Complexidade |
|----|-----------|-----------|--------------|
| ER-3.10 | `scripts/motor_reverso_obra.py` — agrega fichas de todos os itens em `reverse_eng_obra_ficha` (estatísticas, padrões, resumo) | `scripts/motor_reverso_obra.py` (NEW) | MEDIUM |
| ER-3.11 | Botão "Processar todos itens granulares da Obra" aciona ER-3.1→ER-3.10 em sequência (QThread, sem Qt bloqueado) | `diagnostic_reverse_hub.py` | MEDIUM |

### Algoritmo do Motor Reverso PIL (referência)

```python
# motor_reverso_pil.py — lógica central
def extrair_ficha_pilar(dxf_path: str, elemento_id: str) -> dict:
    """
    Lê DXF STOG PIL e extrai campos no formato JSON_Pilares/P*.json.
    
    Estratégia:
    1. Carregar entidades do layer NOMENCLATURA → identificar ID (P001, P002...)
    2. Localizar entidades próximas ao centróide do label
    3. Layer Hachura → delimitar bbox do pilar → extrair comprimento/largura
    4. Layer COTA → extrair h1/h2/h3/h4 das faces
    5. Layer COTA FURACAO → extrair grade_1, distancia_1, par_1_2...par_N_M
    6. Contar faces ativas (A-D obrigatórias, E-H se houver entidades)
    
    Semântica confirmada (docs/SEMANTICA-PILAR-NOVA.md):
    - Faces A/B = longas (comprimento), C/D = curtas (largura)
    - grade_1 = comprimento + 22
    - h1=2(fixo), h2=244(chapa), h3=280-2-244=34 (típico)
    """
    ...
```

### Algoritmo do Motor Reverso LV (referência)

```python
# motor_reverso_lv.py — lógica central
def extrair_ficha_lateral_viga(dxf_path: str, elemento_id: str) -> dict:
    """
    Lê DXF STOG LV e extrai campos no formato JSON_Vigas_Laterais/V*_A.json.
    
    Estratégia:
    1. Layer NOMENCLATURA → identificar V{n}_A / V{n}_B
    2. Entidades _MLINE/PLINE por segmento → identificar painéis
    3. Medir cada painel: width, height1 (esq), height2 (dir)
    4. Layer SAR3 → detectar sarrafos (tipo, posição)
    5. Aberturas: entidades HATCH em área da viga → holes
    6. Extremidades: pilar left/right via pilares adjacentes no canvas
    
    Semântica confirmada (docs/SEMANTICA-VIGA-NOVA.md):
    - Segmentação padrão 122cm (pode variar por obra)
    - Side A = face mais próxima ao eixo X positivo
    """
    ...
```

---

## 7. EPIC ER-4: RAG Engenharia Reversa

**Prioridade:** P1 | **Duração:** ~1.5 semanas | **Pré-requisito:** ER-3 operacional
**Objetivo:** Ingerir fichas granulares N2 e ficha de obra no LanceDB para que o Motor 3 possa consultá-las.

### Stories

| ID | Descrição | Arquivo(s) | Complexidade |
|----|-----------|-----------|--------------|
| ER-4.1 | Criar coleções `reverse_eng_fichas` e `reverse_eng_obra` no LanceDB por-obra (extensão de `obra_rag_utils.py`) | `scripts/obra_rag_utils.py` | MEDIUM |
| ER-4.2 | `scripts/reverse_eng_rag_ingestor.py` — lê `reverse_eng_fichas` aprovadas → embed → LanceDB | `scripts/reverse_eng_rag_ingestor.py` (NEW) | MEDIUM |
| ER-4.3 | Chunking das fichas: cada campo = 1 chunk com metadados (obra, pav, classe, elemento_id, campo) | `scripts/reverse_eng_rag_ingestor.py` | LOW |
| ER-4.4 | Botão "Indexar RAG Reverso" no Diagnostic Reverse Hub (dispara ER-4.2) com QProgressBar | `diagnostic_reverse_hub.py` | LOW |
| ER-4.5 | `scripts/reverse_eng_rag_query.py` — interface de query para o Motor 3: `get_reverse_context(obra, pav, classe, query)` | `scripts/reverse_eng_rag_query.py` (NEW) | MEDIUM |

---

## 8. EPIC ER-5: Motor 3 no Structural Analyzer

**Prioridade:** P2 | **Duração:** ~2 semanas | **Pré-requisito:** ER-4 operacional
**Objetivo:** Terceiro botão de interpretação no Structural Analyzer que usa Motores 1+2+3 para gerar resultado enriquecido com contexto de engenharia reversa.

### Mudança de UI no Structural Analyzer

```
Botões de interpretação (atual):
  [ ▶ Análise Geral ]  [ ▶ Interpretar com Contexto ]

Botões de interpretação (novo):
  [ ▶ Análise Geral ]  [ ▶ Interpretar com Contexto ]  [ ▶ Eng.Reversa+Ctx ]
                                                              ↑ NOVO
```

**Motor 3 = Motor 2 + contexto RAG reverso**:
- Motor 1: análise estrutural básica do DXF bruto (Fase-3 existente)
- Motor 2: Motor 1 + contexto RAG da obra (PDFs, DXFs indexados) — existente
- Motor 3: Motor 2 + fichas granulares N2 do RAG reverso (NOVO)

Os 3 resultados ficam disponíveis como tabs separadas no DetailCard do Structural Analyzer.

### Stories

| ID | Descrição | Arquivo(s) | Complexidade |
|----|-----------|-----------|--------------|
| ER-5.1 | Botão "Interpretar com Eng.Reversa+Contexto" na UI do Structural Analyzer | `src/ui/modules/structural_analyzer.py` (ou `organisms.py`) | LOW |
| ER-5.2 | `ReversoContextWorker` — QThread que chama Motor 2 + `reverse_eng_rag_query.get_reverse_context()` | `src/ui/modules/structural_analyzer.py` | MEDIUM |
| ER-5.3 | Resultado Motor 3 salvo em `reverse_eng_fichas` (status=`motor3_draft`) para comparação | `database.py` | LOW |
| ER-5.4 | DetailCard com 3 tabs de resultado: "Motor 1", "Motor 2 (+Ctx)", "Motor 3 (+RevEng+Ctx)" | `src/ui/widgets/detail_card.py` | MEDIUM |

---

## 9. EPIC ER-6: N4 Pipeline + Comparison Cruzado

**Prioridade:** P2 | **Duração:** ~3 semanas | **Pré-requisito:** ER-3 + ER-2
**Objetivo:** Usar fichas granulares N2 para alimentar os Robôs e gerar DXFs N4; implementar comparação cruzada N1/N3 vs N2/N4 no Comparison Engine.

### Stories

| ID | Descrição | Arquivo(s) | Complexidade |
|----|-----------|-----------|--------------|
| ER-6.1 | Robôs aceitam fichas N2 como entrada alternativa: flag `--source n2` nos scripts geradores | `scripts/gerar_*_dxf_stog.py` | MEDIUM |
| ER-6.2 | `scripts/gerar_n4_batch.py` — gera DXFs N4 para todos os itens com ficha N2 aprovada | `scripts/gerar_n4_batch.py` (NEW) | HIGH |
| ER-6.3 | Salvar DXFs N4 em `Fase-5_Geracao_Scripts/DXF_*/N4/` e registrar em `generation_runs` | `scripts/gerar_n4_batch.py`, `database.py` | MEDIUM |
| ER-6.4 | CE: aba "Itens Eng. Reversa N2/N4" mostra DXF N2 (canvas esquerdo) e DXF N4 (canvas direito) | `comparison_engine.py` | HIGH |
| ER-6.5 | Score de comparação N2 vs N4: `comparar_fichas.py` com flag `--modo n2n4` | `scripts/comparar_fichas.py` | MEDIUM |
| ER-6.6 | Score cruzado N1/N3 vs N2/N4: dashboard de comparação no CE com 4 métricas | `comparison_engine.py` | HIGH |
| ER-6.7 | Alimentar `comparison_runs` e `comparison_deltas` com dados N1-N4 | `database.py` | MEDIUM |

---

## 10. Decisões de Arquitetura

### DA-1: Schema dos Motores Reversos — Mesmo formato JSON_Pilares/

**Decisão:** As fichas N2 usam o mesmo schema dos JSONs Fase-4 (`JSON_Pilares/P*.json`, etc.), armazenadas em `reverse_eng_fichas.campos_json`.

**Por quê:** Zero custo de adaptação para os Robôs (N4 usa os mesmos geradores). Motor Reverso é a "inversa perfeita" do Robô.

**Trade-off:** A extração reversa precisa ser precisa o suficiente para reproduzir o mesmo schema. Bugs na extração reversa propagam para N4.

**Mitigação:** Campo `confianca` por item. Status `draft` → `approved` via validação humana obrigatória antes de gerar N4.

---

### DA-2: RAG Reverso — Partição separada no mesmo `obra_rag_db/`

**Decisão:** Fichas N2 indexadas em coleções separadas (`reverse_eng_fichas`, `reverse_eng_obra`) dentro do mesmo `obra_rag_db/` LanceDB por-obra.

**Por quê:** Isolamento semântico (bruto ≠ reverso) sem fragmentar o armazenamento. Motor 3 pode consultar AMBAS as partições (bruto + reverso) com pesos diferentes.

**Não fazer:** Misturar chunks de fichas N2 com chunks de DXFs brutos (`obra_dxfs`) — causaria degradação da qualidade de busca.

---

### DA-3: Diagnostic Reverse Hub — Módulo separado (não herança)

**Decisão:** `diagnostic_reverse_hub.py` é um módulo novo (cópia adaptada de `diagnostic_hub.py`), não subclasse.

**Por quê:** Os dois módulos têm responsabilidades distintas (bruto vs. reverso). Herança forçaria coupling entre dois conceitos que evoluirão de forma independente.

**Trade-off:** Duplicação de ~200 linhas de boilerplate UI. Aceitável dado que os layouts divergem nas 4 tabs centrais e no painel direito.

---

### DA-4: Motores Reversos — Scripts Python puros (não QThread direto)

**Decisão:** Lógica de extração em `scripts/motor_reverso_*.py` (Python puro, sem Qt). Workers Qt em `diagnostic_reverse_hub.py` apenas orquestram os scripts via subprocess ou QThread + import direto.

**Por quê:** Testabilidade (scripts podem ser testados sem Qt). Consistência com arquitetura existente (`scripts/engenharia_reversa_dxf.py`, `motor_fase4.py`).

**Padrão de comunicação:** Workers usam `Signal(str)` com temp file (pickle) — mesmo padrão do `DXFLoadWorker` no CE — para evitar crash Python 3.14 com payloads grandes em QThread.

---

### DA-5: N4 — Reutilizar geradores existentes com flag

**Decisão:** Os 4 geradores STOG (`gerar_pl/lv/fv/lj_dxf_stog.py`) recebem flag `--source n2` que lê de `reverse_eng_fichas` em vez de `JSON_Pilares/` etc.

**Por quê:** Zero duplicação de lógica de geração. N4 tem fidelidade ≥ N3 pois a ficha N2 vem de um DXF STOG humano real.

**Nota crítica:** JSONs Fase-4 originais NUNCA são modificados. N2 é caminho paralelo independente.

---

### DA-6: 3 Resultados Structural Analyzer — Tabs separadas (não comparação inline)

**Decisão:** DetailCard mostra 3 tabs ("Motor 1", "Motor 2 (+Ctx)", "Motor 3 (+RevEng+Ctx)") ao lado de onde hoje há 1 resultado.

**Por quê:** Permite ao usuário ler cada resultado isoladamente antes de comparar. Evita confusão visual com diff inline entre 3 fontes.

**Fase 2 (futura):** Adicionar tab "Comparação" com diff automático dos 3 resultados (fora do escopo deste masterplan).

---

## 11. Roadmap por Sprints

### Sprint 1 (Jun 2026) — CONCLUÍDO ✅
- ✅ Crash fix QThread CE
- ✅ ER-2.1 — `diagnostic_reverse_hub.py` criado (módulo completo, não apenas esqueleto)
- ✅ ER-2.2 — Tab 2 inserida no `main.py`
- ✅ ER-2.3 — Painel esquerdo: lista com ComboBox obra + filtro por classe (PIL/LV/FV/LAJ)
- ✅ ER-2.4 — Canvas Tab 1: Visualizador DXF completo (DXFVectorView)
- ✅ ER-2.5 — Canvas Tab 2: Visualizador granular (recorte do item)
- ✅ ER-2.8 — Painel direito: botão Recortar + 4 botões ▶ PIL/LV/FV/LAJ
- ✅ ER-2.9 — Botões Salvar/Aprovar/Excluir implementados
- ✅ ER-2.10 — "⚡ Processar toda a Obra (todos pavimentos × classes)" implementado
- ✅ ER-2.11 — DB schema `reverse_eng_recortes` + `obra_triagem` operacionais
- ✅ RecorteMotor (src/core/recorte_motor.py) — 4 motores PIL/LV/FV/LAJ implementados e validados
- ✅ Fix `pline.closed = False` → `bool(e.get('closed', False))` — retângulos completos
- ✅ Métricas de confiança (0–100%) por recorte (type_score + count_score)
- ✅ Status taxonomy: `motor` / `aprovado` (treino) / `auto_aprovado` (bulk, não-treino) / `manual`
- ✅ Botão "Aprovar todos ≥ 90%" separado do Aprovar humano
- ✅ Fix qualidade "processar toda a obra": fallback `_extract_geometry_from_dxf` agora completo (closed, hatches, texts) + PKL auto-gerado

### Sprint 2 (Jun 2026) — PENDENTE ⏳
**ER-2 restante:**
- ⏳ ER-2.6 — Tab 3: Ficha Granular (campos N2 em QTableWidget)
- ⏳ ER-2.7 — Tab 4: Ficha Obra Eng. Reversa (consolidado)
- ⏳ ER-1.1 a ER-1.3 — CE Tab Switcher (N1/N3 vs N2/N4)

### Sprint 3 (Jul 2026) — PLANEJADO
- **ER-3.1 a ER-3.5** — Motor Reverso PIL + LV (scripts Python puros que extraem fichas JSON do STOG)
- ER-3 é a **próxima frente estratégica** — transforma recortes aprovados em fichas N2

### Sprint 4 (Ago 2026)
- **ER-3.6 a ER-3.11** — Motor Reverso FV + LAJ + obra consolidada

### Sprint 5 (Ago 2026)
- **ER-4.1 a ER-4.5** — RAG Reverso (fichas N2 → LanceDB)

### Sprint 6 (Set 2026)
- **ER-5.1 a ER-5.4** — Motor 3 Structural Analyzer

### Sprint 7 (Out 2026)
- **ER-6.1 a ER-6.7** — N4 Pipeline + Comparison Engine cruzado

### Cronograma consolidado (atualizado 2026-06-10)

| Sprint | Período | EPICs | Status | Entrega Principal |
|--------|---------|-------|--------|-------------------|
| S1 | Jun '26 | ER-2 (núcleo) | ✅ CONCLUÍDO | Hub operacional + motores recorte |
| S2 | Jun '26 | ER-2 (fichas) + ER-1 | ⏳ Pendente | Fichas granulares UI + CE Tab Switcher |
| S3 | Jul '26 | ER-3 (PIL+LV) | Planejado | Fichas N2 PIL+LV |
| S4 | Ago '26 | ER-3 (FV+LAJ) | Planejado | Fichas N2 completas |
| S5 | Ago '26 | ER-4 | Planejado | RAG reverso indexado |
| S6 | Set '26 | ER-5 | Planejado | Motor 3 + 3 resultados SA |
| S7 | Out '26 | ER-6 | Planejado | N4 + Comparison cruzado completo |

**Duração total restante:** ~4 meses (Jun–Out 2026)

---

## 12. Estado Atual dos Recortes (2026-06-10)

### O que está operacional
- Motor extrai recortes PIL/LV/FV/LAJ de qualquer DXF STOG aprovado na triagem
- Recortes ficam em `Fase-2_Triagem/recortes_reversos/{dxf_stem}/`
- DB `reverse_eng_recortes`: `id, obra_name, projeto_id, elemento_id, classe, recorte_path, entity_count, status, confidence`
- Visualização 3 canvas: DXF bruto / recorte granular / canvas de seleção manual
- Aprovação humana 1-a-1 (`aprovado`) vs bulk automático (`auto_aprovado`) — **só `aprovado` entra no treino**

### Limitação atual da métrica de confiança
> ⚠️ **A % de confiança é genérica enquanto não tivermos volume de recortes aprovados.**
>
> A fórmula atual (`0.6 × type_score + 0.4 × count_score`) usa critérios estáticos baseados em
> presença de entidades (lines, polylines fechadas, hatches, textos) e ranges de contagem por classe.
>
> **O que está pendente:**
> - Calibrar thresholds de confiança por classe (PIL, LV, FV, LAJ) com base em recortes humanos aprovados
> - Implementar feedback loop: recortes aprovados → ajuste automático dos pesos type_score/count_score
> - Score 90% hoje pode não ser equivalente a 90% após calibração com 200+ recortes aprovados
>
> **Decisão consciente:** Usar a % atual para triagem e avanço rápido. Recalibrar quando tiver ≥ 50 aprovados por classe.

### Próxima frente estratégica (Sprint 2)
Antes de começar ER-3 (motor de fichas N2), completar:
1. **ER-2.6** — Tab "Ficha Granular" mostrando campos extraídos do recorte em QTableWidget
2. **ER-2.7** — Tab "Ficha Obra ER" consolidando todos os itens da obra
3. **ER-1.x** — CE Tab Switcher (N1 vs N2) para visualizar comparação

---

## 13. Métricas de Sucesso

| Métrica | Target | Mede o quê |
|---------|--------|-----------|
| Fichas N2 com confiança ≥ 0.85 | ≥ 80% dos itens | Qualidade do Motor Reverso |
| Score N4 vs STOG humano | ≥ 90% | N4 reproduz o STOG corretamente |
| Delta N1 vs N2 (mesmos campos) | ≤ 10% divergência média | Convergência dos dois fluxos |
| Tempo de processamento reverso por obra | < 5 min | Usabilidade do "Processar todos" |
| Motor 3 melhora sobre Motor 2 | ≥ 5 pp em score Structural Analyzer | Valor do contexto reverso |

---

## 13. Riscos

| # | Risco | Prob. | Impacto | Mitigação |
|---|-------|-------|---------|-----------|
| R1 | Motor Reverso PIL extrai campos errados por variação de DXF entre obras | Alta | Alto | Validar em 5+ obras antes de marcar como CONCLUÍDO; campo `confianca` bloqueia N4 se < 0.7 |
| R2 | DXFs STOG humanos de obras antigas têm layers divergentes do padrão NOVA | Média | Médio | Motor Reverso com fallback por camadas alternativas; `SEMANTICA-*.md` como referência |
| R3 | Inserção de Tab 2 quebra indexação das tabs existentes nos testes | Baixa | Médio | `QTabWidget.insertTab(2, ...)` é não-destrutivo; renumerar referências em testes |
| R4 | Fichas N2 e N1 divergem muito → Comparison Engine mostra confusão em vez de insight | Média | Alto | Dashboard de divergência com explicação de cada delta; não esconder divergências |
| R5 | Motor 3 (SA) aumenta latência de interpretação inaceitavelmente | Baixa | Médio | QThread + Signal assíncrono — botão separado (não substitui Motores 1+2) |
| R6 | RAG reverso contamina RAG bruto | Baixa | Alto | Coleções separadas (DA-2) — impossível contaminação por design |

---

## 14. Arquivos — Mapa Completo de Criação/Modificação

### Arquivos Novos (criar)
```
src/ui/modules/diagnostic_reverse_hub.py   ← ER-2 — módulo principal da nova aba
scripts/motor_reverso_pil.py               ← ER-3 — extração granular pilares
scripts/motor_reverso_lv.py                ← ER-3 — extração granular L.Vigas
scripts/motor_reverso_fv.py                ← ER-3 — extração granular F.Vigas
scripts/motor_reverso_laj.py               ← ER-3 — extração granular Lajes
scripts/motor_reverso_obra.py              ← ER-3 — consolidação ficha obra
scripts/reverse_eng_rag_ingestor.py        ← ER-4 — ingestão fichas N2 → LanceDB
scripts/reverse_eng_rag_query.py           ← ER-4 — interface query Motor 3
scripts/gerar_n4_batch.py                  ← ER-6 — geração batch DXFs N4
```

### Arquivos Modificados
```
main.py                                    ← ER-2.2 — inserir Tab 2 (insertTab)
src/ui/modules/comparison_engine.py        ← ER-1 — Tab Switcher N1/N3 vs N2/N4; ER-6 — N4 canvas
src/ui/modules/structural_analyzer.py     ← ER-5 — botão Motor 3 + DetailCard 3 tabs
src/ui/widgets/detail_card.py              ← ER-5.4 — 3 tabs resultado
src/core/database.py                       ← ER-2.11 — schema reverse_eng_*
scripts/obra_rag_utils.py                  ← ER-4.1 — novas coleções LanceDB
scripts/comparar_fichas.py                 ← ER-6.5 — modo --n2n4
scripts/gerar_pl_dxf_stog.py              ← ER-6.1 — flag --source n2
scripts/gerar_lv_dxf_stog.py              ← ER-6.1 — flag --source n2
scripts/gerar_fv_dxf_stog.py              ← ER-6.1 — flag --source n2
scripts/gerar_lj_dxf_stog.py              ← ER-6.1 — flag --source n2
```

---

## 15. Glossário de Novos Termos

| Termo | Significado |
|-------|------------|
| N2 | Ficha granular extraída do STOG humano pelo Motor Reverso |
| N4 | DXF gerado pelo Robô usando ficha N2 como entrada |
| Motor Reverso | Script de extração que lê DXF STOG → produz ficha (inverso do Robô) |
| Motor 3 | Structural Analyzer com contexto RAG reverso + RAG obra |
| Diagnostic Reverse Hub | Nova aba (Tab 2) para visualizar, recortar e processar STOGs humanos |
| Ficha Granular | JSON no mesmo schema dos Fase-4 JSONs, mas extraído do STOG |
| Ficha Obra ER | Consolidação de todas as fichas granulares de uma obra em visão engenharia reversa |
| N1/N3 | Fluxo bruto: N1=itens Fase-3/4, N3=DXF gerado pelo Robô a partir de N1 |
| N2/N4 | Fluxo reverso: N2=itens do Motor Reverso, N4=DXF gerado pelo Robô a partir de N2 |
| dual-flow | Os dois pipelines paralelos (bruto e reverso) que convergem no Comparison Engine |

---

*Documento gerado por Aria (Architect) — Synkra AIOS | 2026-06-08*
*Revisão recomendada após Sprint 2 (conclusão do Diagnostic Reverse Hub).*
