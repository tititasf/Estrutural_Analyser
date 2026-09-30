# MASTERPLAN — CAD-ANALYZER: Team Completo + Pipeline End-to-End

**Documento:** CEO-PLANEJAMENTO (Athena) — Planejamento Comprehensive
**Data:** 2026-03-05
**Objetivo:** Transformar AgenteCAD num sistema end-to-end automatizado via AIOS squads
**Meta Final:** Enviar uma pasta de obra → receber DXFs de entrega prontos

---

## VISAO GERAL DO SISTEMA

```
OBRA (pasta DXFs/PDFs/fotos)
        |
        v
[FASE 1] Ingestao e Vetorizacao
        |
        v
[FASE 2] Limpeza e Separacao de Pavimentos
        |
        v
[FASE 3] Interpretacao Semantica (Fichas PIL/VIG/LAJ)  ← CRITICO / MAIS DIFICIL
        |
        v
[FASE 4] Transformacao para Fichas dos Robos
        |
        v
[FASE 5] Geracao DXF por Item por Pavimento
        |
        v
[FASE 6] Unificacao DXF em Produtos de Entrega
        |
        v
[FASE 7] Revisao de Qualidade
        |
        v
DXFs FINAIS: Pilares | Vigas Laterais | Vigas Fundos | Garfos | Lajes
```

---

## PARTE 1 — SQUADS DOS ROBOS (Geradores DXF/SCR)

> Estes squads operam sobre fichas preenchidas (saida da Fase 3/4) e produzem DXFs.
> Interface: chat AIOS simplificado — usuario passa ficha, squad retorna DXF/SCR.

### squad-robo-pilares

**Responsabilidade:** Receber ficha de pilar preenchida → gerar DXF/SCR de pilares
**Submodulos:** Visao de cima | Paineis ABCD | Grades
**Robo fonte:** `_ROBOS_ABAS/Robo_Pilares/`

**Agentes:**
| Agente | Funcao |
|--------|--------|
| pilar-interpreter | Valida e normaliza ficha de pilar recebida |
| pilar-renderer | Executa o Robo_Pilares e gera DXF/SCR |
| pilar-reviewer | Valida geometria do DXF gerado |

**Workflow principal:** `ficha-pilar → validar → executar-robo → verificar-output → entregar-dxf`

**Inputs esperados:**
```json
{
  "codigo": "P1",
  "secao": {"largura": 20, "altura": 50},
  "altura_total": 280,
  "painel_A": {...},
  "painel_B": {...},
  "painel_C": {...},
  "painel_D": {...},
  "grade_horizontal": {...},
  "grade_vertical": {...}
}
```

**Outputs:** `pilares_ENTREGA.dxf`, `pilares_ENTREGA.scr`

---

### squad-robo-vigas

**Responsabilidade:** Ficha de viga preenchida → DXF/SCR de vigas
**Submodulos:** Laterais | Fundos | Visao de Corte | Garfos
**Robos fonte:** `_ROBOS_ABAS/Robo_Laterais_de_Vigas/` + `_ROBOS_ABAS/Robo_Fundos_de_Vigas/`

**Agentes:**
| Agente | Funcao |
|--------|--------|
| viga-interpreter | Valida ficha de viga, detecta tipo (lateral/fundo/garfo) |
| viga-lateral-renderer | Executa Robo_Laterais |
| viga-fundo-renderer | Executa Robo_Fundos |
| viga-garfo-renderer | Processa garfos de ligacao |
| viga-reviewer | Valida geometria e sobreposicoes |

**Workflow principal:** `ficha-viga → classificar-tipo → executar-robo-correto → unificar → entregar-dxf`

**Inputs esperados:**
```json
{
  "codigo": "V1",
  "tipo": "retangular|L|T",
  "secao": {"largura": 14, "altura": 45},
  "comprimento": 600,
  "armadura_positiva": {...},
  "armadura_negativa": {...},
  "estribos": {...},
  "garfos": [...]
}
```

**Outputs:** `vigas_laterais_ENTREGA.dxf`, `vigas_fundos_ENTREGA.dxf`, `garfos_ENTREGA.dxf`

---

### squad-robo-lajes

**Responsabilidade:** Ficha de laje preenchida → DXF/SCR de lajes
**Robo fonte:** `_ROBOS_ABAS/Robo_Lajes/`

**Agentes:**
| Agente | Funcao |
|--------|--------|
| laje-interpreter | Valida ficha, detecta direcao e tipo de laje |
| laje-renderer | Executa Robo_Lajes |
| laje-reviewer | Valida malha e cobertura |

**Workflow principal:** `ficha-laje → validar → executar-robo → verificar-malha → entregar-dxf`

**Inputs esperados:**
```json
{
  "codigo": "L1",
  "tipo": "macica|nervurada|pre-moldada",
  "dimensoes": {"lx": 450, "ly": 600},
  "espessura": 12,
  "armadura_principal": {...},
  "armadura_distribuicao": {...},
  "laje_inferior": {...}
}
```

**Outputs:** `lajes_ENTREGA.dxf`

---

## PARTE 2 — SQUADS DAS 7 FASES DO PIPELINE

### squad-fase1-ingestao

**Objetivo:** Receber pasta de obra bruta → extrair e vetorizar tudo
**Responsavel por:** Processamento de DXFs, PDFs, fotos; separacao de tipos de documento

**Agentes:**
| Agente | Funcao |
|--------|--------|
| obra-receptor | Valida e cataloga pasta de obra recebida |
| dxf-extractor | Processa DXFs com ezdxf, extrai entities |
| pdf-extractor | OCR e extrai texto/tabelas de PDFs e atas |
| foto-extractor | Vision AI para extrair dados de fotos de obra |
| obra-classifier | Classifica cada arquivo: estrutural/detalhe/ata/engrev |
| vetorizador-fase1 | Cria vetores fase 1 no ChromaDB |

**Dados vetoriais produzidos:**
```
chroma_collection: "fase1_obra_{obra_id}"
  - dxf_entities: geometria bruta por arquivo
  - pdf_text: texto extraido de PDFs
  - foto_data: dados extraidos de fotos
  - obra_metadata: nome, data, tipo de obra
```

**Inputs:** `/caminho/para/pasta/obra/` contendo:
- `*.dxf` — projetos estruturais
- `*.pdf` — atas, memoriais, planilhas
- `*.jpg/*.png` — fotos de obra executada
- Opcionalmente: DXFs ja feitos (para engenharia reversa)

**Outputs:**
```
data/obras/{obra_id}/
  fase1/
    catalogo.json        # inventario de todos os arquivos
    dxf_entities.json    # entities extraidas de cada DXF
    pdf_extracts/        # textos de PDFs
    foto_extracts/       # dados de fotos
    vetores_fase1.json   # resumo dos vetores criados
```

**Qualidade gate:** >= 90% dos arquivos processados sem erro; ChromaDB populado

---

### squad-fase2-limpeza

**Objetivo:** Separar pavimentos estruturais dos detalhes; preparar dados limpos para fase 3

**Agentes:**
| Agente | Funcao |
|--------|--------|
| pavimento-separator | Identifica e separa DXFs de pavimentos x detalhes |
| layer-cleaner | Filtra layers relevantes, remove ruido |
| detalhe-extractor | Isola detalhes construtivos separadamente |
| pavimento-namer | Nomeia e ordena pavimentos (TERREO, 1_PAV, etc) |
| vetorizador-fase2 | Popula vetores limpos fase 2 |

**Logica de separacao:**
- Pavimento: DXF com planta de forma completa (vigas, pilares, lajes em planta)
- Detalhe: DXF com corte, armacao especifica, detalhes de no
- Ata/memorial: PDF com informacoes de execucao

**Dados vetoriais produzidos:**
```
chroma_collection: "fase2_obra_{obra_id}"
  - pavimentos_limpos: por pavimento, entities filtradas
  - detalhes: detalhes construtivos catalogados
  - spatial_index: indice espacial de cada pavimento
```

**Outputs:**
```
data/obras/{obra_id}/
  fase2/
    pavimentos/
      TERREO/entities_limpos.json
      1_PAV/entities_limpos.json
      ...
    detalhes/
      detalhe_no_pilar.json
      ...
    vetores_fase2.json
```

**Qualidade gate:** Todos os pavimentos identificados e nomeados; 0 entidades duplicadas entre pavimentos

---

### squad-fase3-interpretacao (CRITICO)

**Objetivo:** Interpretacao semantica das plants limpas → preencher fichas estruturais

> **PROBLEMA ATUAL:** Interpretacao retorna % altas mas resultado esta errado.
> Necessita revisao humana + loop de correcao + treinamento supervisionado.

**Agentes:**
| Agente | Funcao |
|--------|--------|
| pilar-reader | Le e interpreta pilares no pavimento (secao, posicao, codigo) |
| viga-reader | Le e interpreta vigas (tipo, secao, comprimento, tramos) |
| laje-reader | Le e interpreta lajes (tipo, dimensoes, direcao) |
| ficha-validator | Valida ficha preenchida com regras de negocio estrutural |
| human-reviewer | Interface para revisao e correcao humana de fichas |
| trainer | Aprende com correcoes para melhorar proximas interpretacoes |

**ESTRATEGIA PARA RESOLVER O PROBLEMA DE INTERPRETACAO:**

1. **Modo Assistido (atual):** Agente interpreta + humano revisa cada ficha
   - Interface de revisao mostra: campo interpretado vs campo esperado
   - Humano corrige campos errados
   - Sistema aprende com cada correcao

2. **Dataset de Treinamento:**
   - Cada correcao humana alimenta `training_data/fase3/corrections.json`
   - Formato: `{input_entities, predicted_ficha, corrected_ficha, obra_id, pavimento}`
   - Acumular minimo 50 fichas corrigidas por tipo (pilar/viga/laje)

3. **Regras de Validacao Estrutural (intransigentes):**
   ```
   Pilar: secao.largura >= 14cm, secao.altura >= 14cm
   Viga: secao.largura >= 12cm, secao.altura >= 25cm
   Laje: espessura >= 8cm
   Codigo: formato P{n}, V{n}, L{n} (obrigatorio)
   Posicao: coordenadas XY obrigatorias
   ```

4. **Score de Confianca por Campo:**
   - Cada campo tem score 0-1 de confianca
   - Campos com score < 0.7 sao marcados para revisao humana obrigatoria

**Dados vetoriais produzidos:**
```
chroma_collection: "fase3_obra_{obra_id}"
  - fichas_pilares: ficha completa por pilar
  - fichas_vigas: ficha completa por viga
  - fichas_lajes: ficha completa por laje

sqlite: project_data.vision
  tabela: fase3_fichas (id, obra, pavimento, tipo, codigo, dados_json, confidence, revisado)
  tabela: fase3_corrections (id, ficha_id, campo, valor_original, valor_correto, data)
```

**Outputs:**
```
data/obras/{obra_id}/
  fase3/
    pilares/
      TERREO/fichas_pilares.json   # lista de fichas por pavimento
      1_PAV/fichas_pilares.json
    vigas/
      TERREO/fichas_vigas.json
    lajes/
      TERREO/fichas_lajes.json
    revisao_pendente.json          # fichas com low confidence para revisao
    correcoes_aplicadas.json       # log de correcoes humanas
```

**Qualidade gate:** 100% das fichas com campos obrigatorios preenchidos; 0 fichas sem revisao quando confidence < 0.7

---

### squad-fase4-transformacao

**Objetivo:** Converter fichas genericas da Fase 3 no formato exato de cada robo

> Usa o `TransformationEngine` ja implementado em `src/core/transformation_engine.py`
> e `src/core/robot_integration.py` (100% testado, score potencial +5%)

**Agentes:**
| Agente | Funcao |
|--------|--------|
| pilar-transformer | Converte ficha-pilar → formato Robo_Pilares |
| viga-transformer | Converte ficha-viga → formato Robo_Laterais e Robo_Fundos |
| laje-transformer | Converte ficha-laje → formato Robo_Lajes |
| transformation-auditor | Valida transformacao, detecta campos faltantes |
| cache-manager | Gerencia cache de transformacoes (100% hit rate apos warming) |

**Integracao critica (PROXIMA ACAO IMEDIATA):**
```python
# motor_fase4.py — adicionar:
from core.robot_integration import RobotIntegration

class MotorFase4:
    def __init__(self, ...):
        self._transformation_engine = RobotIntegration(db_path)
        self._use_transformation_engine = True  # JA TESTADO E FUNCIONAL
```

**Dados vetoriais produzidos:**
```
sqlite: project_data.vision
  tabela: transformation_cache (ja existe)
  tabela: transformation_log (ja existe)
  tabela: transformation_rules (6 regras base ja existem)
```

**Outputs:**
```
data/obras/{obra_id}/
  fase4/
    pilares/
      TERREO/fichas_robo_pilares.json
    vigas_laterais/
      TERREO/fichas_robo_laterais.json
    vigas_fundos/
      TERREO/fichas_robo_fundos.json
    lajes/
      TERREO/fichas_robo_lajes.json
    garfos/
      TERREO/fichas_robo_garfos.json
```

**Qualidade gate:** Score TransformationEngine >= 75%; 0 campos obrigatorios ausentes nos outputs

---

### squad-fase5-geracao

**Objetivo:** Executar robos para gerar DXF individual de cada item de cada pavimento

**Agentes:**
| Agente | Funcao |
|--------|--------|
| geracao-orchestrator | Coordena execucao dos 4 robos em paralelo |
| robo-executor | Wrapper que executa qualquer robo com ficha entrada |
| dxf-organizer | Organiza DXFs gerados por tipo/pavimento |
| falha-handler | Detecta e re-executa items com falha |

**Paralelismo:** Robos executam em paralelo por pavimento

**Outputs:**
```
data/obras/{obra_id}/
  fase5/
    pilares/
      TERREO/
        P1.dxf
        P2.dxf
        ...
      1_PAV/
        P1.dxf
    vigas_laterais/
      TERREO/V1_lateral.dxf ...
    vigas_fundos/
      TERREO/V1_fundo.dxf ...
    garfos/
      TERREO/G1.dxf ...
    lajes/
      TERREO/L1.dxf ...
```

**Qualidade gate:** >= 95% dos items geraram DXF sem erro; todos os DXFs abrem sem erro no ezdxf

---

### squad-fase6-unificacao

**Objetivo:** Unificar DXFs individuais em produtos de entrega por classe

**Agentes:**
| Agente | Funcao |
|--------|--------|
| dxf-merger | Unifica multiplos DXFs num unico arquivo |
| layer-organizer | Organiza layers por classe no DXF unificado |
| scr-generator | Gera scripts SCR correspondentes |
| entrega-packager | Empacota produto final para entrega |

**Regras de unificacao:**
- Um DXF de entrega por classe (Pilares, Vigas-Laterais, Vigas-Fundos, Garfos, Lajes)
- Todos os pavimentos numa unica folha, com offset de posicao
- Layers nomeados por classe + pavimento: `PILAR-TERREO`, `PILAR-1PAV`
- SCR gerado para cada DXF de entrega

**Outputs:**
```
data/obras/{obra_id}/
  ENTREGA/
    {obra_id}_PILARES.dxf
    {obra_id}_PILARES.scr
    {obra_id}_VIGAS_LATERAIS.dxf
    {obra_id}_VIGAS_LATERAIS.scr
    {obra_id}_VIGAS_FUNDOS.dxf
    {obra_id}_VIGAS_FUNDOS.scr
    {obra_id}_GARFOS.dxf
    {obra_id}_GARFOS.scr
    {obra_id}_LAJES.dxf
    {obra_id}_LAJES.scr
    RELATORIO_ENTREGA.pdf
```

**Qualidade gate:** Todos os 5 DXFs de entrega gerados; score geometrico >= 75%; sem sobreposicoes de elementos

---

### squad-fase7-qualidade

**Objetivo:** Revisao final de qualidade — geometria, fidelidade, completude

**Agentes:**
| Agente | Funcao |
|--------|--------|
| geometric-validator | Valida geometria de cada elemento vs ficha |
| fidelity-scorer | Compara com groundtruth se disponivel |
| completeness-checker | Verifica se todos os items de todos os pavimentos estao presentes |
| report-generator | Gera relatorio de qualidade da obra |
| human-final-reviewer | Interface para aprovacao humana antes de entrega |

**Metricas de qualidade:**
```
Score geometrico por elemento: 0-100
Score de completude: n_itens_gerados / n_itens_esperados
Score fidelidade vs groundtruth: 0-100 (quando disponivel)
Taxa de aprovacao humana: % aprovados sem correcao
```

**Outputs:**
```
data/obras/{obra_id}/
  fase7/
    relatorio_qualidade.json
    relatorio_qualidade.pdf
    aprovacao_humana.json
    score_final.json
```

**Qualidade gate:** Score geometrico >= 80%; Completude >= 95%; Aprovacao humana = APROVADO

---

## PARTE 3 — SQUADS DE SUPORTE DA APLICACAO

### squad-cad-engine

**Responsabilidade:** Motor central de parsing DXF e geometria
**Modulos:** `src/core/dxf_loader.py`, `geometry_engine.py`, `spatial_index.py`, `slab_tracer.py`

**Agentes:**
| Agente | Funcao |
|--------|--------|
| dxf-parser | Abstrai ezdxf, retorna entities normalizadas |
| geometry-analyst | Operacoes geometricas (bbox, area, intersecao) |
| spatial-indexer | Indice espacial para queries "elementos proximos" |

---

### squad-ml-training

**Responsabilidade:** Treinamento e melhoria continua da interpretacao semantica
**CRITICO para resolver Fase 3**

**Agentes:**
| Agente | Funcao |
|--------|--------|
| data-curator | Cuida do dataset de treinamento (correcoes humanas) |
| model-trainer | Re-treina modelos com novos dados |
| benchmark-runner | Executa suite de testes de interpretacao |
| prompt-engineer | Melhora prompts de interpretacao da LLM |

**Fluxo de melhoria continua:**
```
Correcao humana → data-curator adiciona ao dataset
dataset >= 50 exemplos por tipo → model-trainer dispara novo treino
benchmark-runner valida novo modelo vs anterior
Se melhora: deploy do novo modelo
```

**Dataset target:**
```
training_data/
  pilares/
    fichas_corretas/    # fichas 100% corretas como ground truth
    corrections/        # par (errado, correto) por correcao humana
  vigas/
    fichas_corretas/
    corrections/
  lajes/
    fichas_corretas/
    corrections/
```

---

### squad-memory-manager

**Responsabilidade:** Gestao de ChromaDB + SQLite + memoria hierarquica

**Agentes:**
| Agente | Funcao |
|--------|--------|
| chroma-manager | CRUD nas colecoes ChromaDB |
| sqlite-manager | Migrations, backups, queries otimizadas |
| memory-indexer | Manutencao dos indices semanticos |

---

### squad-pipeline-orchestrator

**Responsabilidade:** Orquestra o pipeline end-to-end de uma obra completa

**Agentes:**
| Agente | Funcao |
|--------|--------|
| obra-coordinator | Coordena execucao das 7 fases em sequencia |
| phase-monitor | Monitora progresso e detecta falhas |
| state-manager | Persiste estado do pipeline (retoma de onde parou) |
| notifier | Notifica usuario sobre progresso e erros |

**Estado do pipeline (resumavel):**
```json
{
  "obra_id": "Obra_TREINO_21",
  "fase_atual": 3,
  "fases_completas": [1, 2],
  "fase_em_andamento": {
    "numero": 3,
    "pavimento_atual": "3_PAV",
    "items_completos": 45,
    "items_total": 120
  }
}
```

---

### squad-ui-cad

**Responsabilidade:** Interface PySide6 — simplificar interacao para chat AIOS
**Meta:** Tornar a interface um chat simples com progresso visual

**Agentes:**
| Agente | Funcao |
|--------|--------|
| ui-developer | Implementa componentes PySide6 |
| chat-interface | Interface de chat para interacao com squads |
| progress-visualizer | Dashboard de progresso das fases |
| ficha-editor | Editor visual de fichas para revisao humana (Fase 3) |

---

### squad-testing-qa

**Responsabilidade:** Qualidade automatizada de todo o sistema

**Agentes:**
| Agente | Funcao |
|--------|--------|
| unit-tester | Testes unitarios por modulo |
| integration-tester | Testes de integracao entre fases |
| e2e-tester | Testes end-to-end por obra completa |
| regression-guardian | Previne regressoes no score de interpretacao |

**Suite de testes:**
```
tests/
  unit/
    test_dxf_parser.py
    test_geometry_engine.py
    test_transformation_engine.py    # ja existe (6/6 PASS)
    test_fichas_validation.py
  integration/
    test_fase1_to_fase2.py
    test_fase2_to_fase3.py
    test_fase3_to_fase4.py
    test_fase4_to_fase5.py
    test_fase5_to_fase6.py
  e2e/
    test_obra_completa_treino13.py   # obra mais simples
    test_obra_completa_treino21.py   # obra media
    test_score_minimo_75.py          # gate de qualidade
  benchmarks/
    benchmark_interpretacao.py       # score de interpretacao por versao
    benchmark_performance.py         # tempo de processamento
```

**Criterios de qualidade:**
```
Score interpretacao Fase 3: >= 75% (meta: 90%)
Score geometrico Fase 7: >= 80%
Taxa de sucesso E2E: >= 95%
Tempo processamento obra media: < 30 min
Cobertura de testes: >= 60%
```

---

### squad-deploy

**Responsabilidade:** Build, distribuicao e atualizacao do sistema

**Agentes:**
| Agente | Funcao |
|--------|--------|
| builder | PyInstaller/Nuitka para gerar executavel |
| updater | TUFup para distribuicao de updates |
| packager | Empacotamento para distribuicao |

---

## PARTE 4 — MAPA COMPLETO DE SQUADS

```
CAD-ANALYZER ECOSYSTEM
│
├── PIPELINE FASES (sequencial)
│   ├── squad-fase1-ingestao
│   ├── squad-fase2-limpeza
│   ├── squad-fase3-interpretacao   ← CRITICO, resolver primeiro
│   ├── squad-fase4-transformacao   ← JA IMPLEMENTADO, integrar
│   ├── squad-fase5-geracao
│   ├── squad-fase6-unificacao
│   └── squad-fase7-qualidade
│
├── ROBOS (paralelos, chamados pela Fase 5)
│   ├── squad-robo-pilares
│   ├── squad-robo-vigas
│   └── squad-robo-lajes
│
└── INFRAESTRUTURA (transversal)
    ├── squad-cad-engine
    ├── squad-ml-training
    ├── squad-memory-manager
    ├── squad-pipeline-orchestrator
    ├── squad-ui-cad
    ├── squad-testing-qa
    └── squad-deploy
```

**Total: 17 squads**

---

## PARTE 5 — PRIORIDADE DE EXECUCAO

### Fase Imediata (Semana 1-2) — Desbloquear Producao

| Prioridade | Acao | Squad | Impacto |
|-----------|------|-------|---------|
| 1 | Integrar TransformationEngine em motor_fase4.py (Opcao A) | squad-fase4 | +5% score |
| 2 | Executar ATAQUES 10-12 e validar score > 75% | squad-testing-qa | Validacao |
| 3 | Criar interface de revisao de fichas (Fase 3) | squad-ui-cad | Resolver Fase 3 |
| 4 | Criar dataset de treinamento com 10 obras | squad-ml-training | Base Fase 3 |

### Fase 2 (Semana 3-6) — Construir Pipeline

| Prioridade | Acao | Squad |
|-----------|------|-------|
| 5 | Implementar squad-fase1-ingestao completo | squad-fase1 |
| 6 | Implementar squad-fase2-limpeza | squad-fase2 |
| 7 | Melhorar squad-fase3 com revisao assistida | squad-fase3 |
| 8 | Criar squad-pipeline-orchestrator (estado persistente) | squad-pipeline |

### Fase 3 (Semana 7-12) — Robos como Squads AIOS

| Prioridade | Acao | Squad |
|-----------|------|-------|
| 9 | Criar squad-robo-pilares com interface chat | squad-robo-pilares |
| 10 | Criar squad-robo-vigas com interface chat | squad-robo-vigas |
| 11 | Criar squad-robo-lajes com interface chat | squad-robo-lajes |
| 12 | Implementar Fase 5, 6, 7 | squads correspondentes |

### Fase 4 (Semana 13+) — End-to-End

| Prioridade | Acao |
|-----------|------|
| 13 | Teste E2E completo com obra real |
| 14 | Otimizacao de performance |
| 15 | Deploy e distribuicao |

---

## PARTE 6 — ARQUITETURA DE DADOS POR FASE

### Schema SQLite (project_data.vision) — Adicionar

```sql
-- OBRAS
CREATE TABLE obras (
    id TEXT PRIMARY KEY,
    nome TEXT,
    pasta_origem TEXT,
    data_ingestao TIMESTAMP,
    fase_atual INTEGER,
    status TEXT  -- em_processamento|pausado|completo|erro
);

-- FASE 1
CREATE TABLE fase1_arquivos (
    id TEXT PRIMARY KEY,
    obra_id TEXT,
    arquivo TEXT,
    tipo TEXT,  -- dxf_estrutural|dxf_detalhe|pdf_ata|foto|engenharia_reversa
    processado BOOLEAN,
    chroma_collection TEXT,
    FOREIGN KEY (obra_id) REFERENCES obras(id)
);

-- FASE 3 — FICHAS (ja existe parcialmente)
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

CREATE TABLE fase3_corrections (
    id TEXT PRIMARY KEY,
    ficha_id TEXT,
    campo TEXT,
    valor_original TEXT,
    valor_correto TEXT,
    data TIMESTAMP,
    FOREIGN KEY (ficha_id) REFERENCES fase3_fichas(id)
);

-- PIPELINE STATE
CREATE TABLE pipeline_state (
    obra_id TEXT PRIMARY KEY,
    fase_atual INTEGER,
    fase1_completa BOOLEAN DEFAULT FALSE,
    fase2_completa BOOLEAN DEFAULT FALSE,
    fase3_completa BOOLEAN DEFAULT FALSE,
    fase4_completa BOOLEAN DEFAULT FALSE,
    fase5_completa BOOLEAN DEFAULT FALSE,
    fase6_completa BOOLEAN DEFAULT FALSE,
    fase7_completa BOOLEAN DEFAULT FALSE,
    ultima_atualizacao TIMESTAMP
);
```

---

## PARTE 7 — STORIES PRIORITARIAS

### EPIC-1: Integrar TransformationEngine (IMEDIATO)

**Story 1.1:** Criar wrapper em motor_fase4.py com flag A/B
**Story 1.2:** Executar ATAQUES 10-12 e documentar score
**Story 1.3:** Validar score >= 75% e habilitar TransformationEngine em producao

### EPIC-2: Resolver Fase 3 — Interpretacao Semantica

**Story 2.1:** Criar interface de revisao de fichas no PySide6
**Story 2.2:** Implementar score de confianca por campo na interpretacao
**Story 2.3:** Criar pipeline de coleta de correcoes humanas (dataset)
**Story 2.4:** Implementar regras de validacao estrutural intransigentes
**Story 2.5:** Acumular 50 fichas corrigidas por tipo (pilar/viga/laje)
**Story 2.6:** Re-treinar modelo e validar melhora >= 5%

### EPIC-3: Pipeline Orchestrator

**Story 3.1:** Criar schema obras + pipeline_state no SQLite
**Story 3.2:** Implementar fase1-ingestao com suporte a DXF+PDF+foto
**Story 3.3:** Implementar fase2-limpeza com separacao automatica
**Story 3.4:** Implementar state manager (pipeline resumavel)
**Story 3.5:** Criar CLI: `python main.py --obra /caminho/obra --run-pipeline`

### EPIC-4: Robos como Squads AIOS (Chat)

**Story 4.1:** Criar squad-robo-pilares com schema de ficha padronizado
**Story 4.2:** Criar interface chat AIOS para squad-robo-pilares
**Story 4.3:** Criar squad-robo-vigas (laterais + fundos + garfos)
**Story 4.4:** Criar squad-robo-lajes
**Story 4.5:** Unificar interface de chat para os 3 robos

### EPIC-5: Fase 5, 6, 7 Completos

**Story 5.1:** Implementar geracao DXF paralela (Fase 5)
**Story 5.2:** Implementar unificador DXF por classe (Fase 6)
**Story 5.3:** Implementar validador geometrico automatico (Fase 7)
**Story 5.4:** Gerar relatorio de qualidade PDF

### EPIC-6: Testes e QA

**Story 6.1:** Suite de testes unitarios para TransformationEngine e Fase 4
**Story 6.2:** Teste de integracao Fase 3 → 4 → 5
**Story 6.3:** Teste E2E com Obra_TREINO_13 (mais simples)
**Story 6.4:** Teste E2E com Obra_TREINO_21 (media)
**Story 6.5:** Benchmark de score de interpretacao por versao

---

## PARTE 8 — ESTRUTURA DE PASTAS PROPOSTA

```
Agente-cad-PYSIDE/
├── main.py                    # Entry point apenas (~100 linhas, refatorar)
├── src/
│   ├── core/                  # Motores (ja existe)
│   │   ├── dxf_loader.py
│   │   ├── transformation_engine.py
│   │   ├── robot_integration.py
│   │   └── pipeline_orchestrator.py
│   ├── phases/                # NOVO — um modulo por fase
│   │   ├── fase1_ingestao.py
│   │   ├── fase2_limpeza.py
│   │   ├── fase3_interpretacao.py
│   │   ├── fase4_transformacao.py
│   │   ├── fase5_geracao.py
│   │   ├── fase6_unificacao.py
│   │   └── fase7_qualidade.py
│   ├── robos/                 # NOVO — wrappers dos robos
│   │   ├── robo_pilares.py
│   │   ├── robo_vigas.py
│   │   └── robo_lajes.py
│   ├── ai/                    # Componentes ML/AI (ja existe)
│   └── ui/                    # Interface PySide6 (ja existe)
├── squads/                    # NOVO — definicoes AIOS
│   ├── squad-robo-pilares/
│   ├── squad-robo-vigas/
│   ├── squad-robo-lajes/
│   ├── squad-fase1-ingestao/
│   ├── squad-fase2-limpeza/
│   ├── squad-fase3-interpretacao/
│   ├── squad-fase4-transformacao/
│   ├── squad-fase5-geracao/
│   ├── squad-fase6-unificacao/
│   ├── squad-fase7-qualidade/
│   ├── squad-cad-engine/
│   ├── squad-ml-training/
│   ├── squad-pipeline-orchestrator/
│   └── squad-testing-qa/
├── training_data/             # NOVO — dataset de treinamento Fase 3
│   ├── pilares/fichas_corretas/
│   ├── vigas/fichas_corretas/
│   └── lajes/fichas_corretas/
├── data/obras/               # Runtime — dados por obra (gitignored)
├── tests/                    # Testes (ja existe, expandir)
├── migrations/               # Migrations SQLite (ja existe)
├── docs/                     # NOVO — recriar documentacao
└── _ROBOS_ABAS/              # Robos existentes (manter)
```

---

## RESUMO EXECUTIVO

| Dimensao | Status Atual | Meta |
|----------|-------------|------|
| Score Fase 3 (interpretacao) | Ruim (% falsa) | >= 75% real |
| Score Fase 4 (transformacao) | 70.05% | >= 75% |
| Pipeline E2E | Incompleto | 100% automatizado |
| Squads AIOS | 0 | 17 |
| Testes E2E | Parcial | >= 95% success rate |
| Interface | Monolitica (6.5k linhas) | Chat AIOS simples |

**Proximo passo critico:** Integrar TransformationEngine (Fase 4) esta semana.
**Proximo problema critico:** Resolver interpretacao semantica (Fase 3) — centro de tudo.

---

*Masterplan gerado por CEO-PLANEJAMENTO (Athena) | Diana Corporacao Senciente*
*Data: 2026-03-05 | Versao: 1.0*
