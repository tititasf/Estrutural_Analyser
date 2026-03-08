# MASTER PLAN - AgenteCAD Sistema Operacional Cognitivo

## Atomic Blueprint Architect - Antigravity

---

# 1. MAPEAMENTO DE CONTEXTO (Global State)

## 1.1 Estado Inicial (Input)

### Sistema Existente
```
AgenteCAD v1.0.1
├── Structural Analyzer (main.py)
│   ├── DXFLoader, SpatialIndex, GeometryEngine
│   ├── TextAssociator, SlabTracer, BeamWalker
│   ├── PillarAnalyzer, ContextEngine
│   └── HierarchicalMemory (basico)
├── Robos Especializados
│   ├── Robo_Lajes (funcional)
│   ├── Robo_Pilares (funcional)
│   ├── Robo_Laterais (funcional)
│   └── Robo_Fundos (funcional)
├── Sistema de Memoria
│   ├── SQLite (persistencia local)
│   ├── ChromaDB (vetores basicos)
│   └── Byterover (configurado, nao integrado)
└── Documentacao
    ├── README.md (basico)
    ├── DEPLOYMENT.md (completo)
    └── Varios MDs espalhados
```

### Gaps Identificados
1. **Falta** Schema JSON padronizado para vetores semanticos
2. **Falta** Sistema de engenharia reversa (DXF produto → dados)
3. **Falta** Pipeline de treinamento bidirecional
4. **Falta** Processamento multimodal real (imagens, DXF avancado)
5. **Falta** Geracao dinamica de DXF via vetores
6. **Falta** Agentes de curadoria automatica
7. **Falta** Documentacao tecnica unificada e profissional
8. **Falta** Botao de export nos robos para estrutural

## 1.2 Estado Final Desejado (Success State)

```
AgenteCAD v2.0.0 - Sistema Cognitivo Completo
├── Fluxo Bidirecional
│   ├── Forward: Estrutural → Analyzer → Robos → SCR → Produto
│   └── Reverse: Produto → Parser → Extrator → Vector DB
├── RAG Multimodal
│   ├── Texto: Embeddings semanticos
│   ├── Imagens: CLIP/Vision embeddings
│   ├── DXF: Embeddings geometricos
│   └── Busca unificada cross-modal
├── Memoria Robusta
│   ├── Curto: RAM cache otimizado
│   ├── Medio: ChromaDB + SQLite integrado
│   └── Longo: Byterover sync automatico
├── Interpretacao Inteligente
│   ├── ML treinado em ambos caminhos
│   ├── Predicao de configuracoes
│   └── Auto-curadoria de dados
└── Documentacao Profissional
    ├── Arquitetura completa
    ├── API Reference
    ├── Guias por modulo
    └── Schema JSON padronizado
```

## 1.3 Arvore de Dependencias

```
[PRE-REQUISITOS]
├── Python 3.12+ instalado
├── PySide6 funcional
├── ChromaDB operacional
├── Byterover autenticado
└── Estrutura de pastas existente

[ORDEM DE EXECUCAO]
Fase 1: Documentacao Base → Fase 2: Schema Vetores →
Fase 3: Sistema Reverso → Fase 4: Treinamento Bidirecional →
Fase 5: RAG Multimodal → Fase 6: Integracao Final
```

---

# 2. BLUEPRINT DE EXECUCAO ATOMICA

---

## FASE 1: DOCUMENTACAO E HARMONIZACAO

### [TASK_001] - Criar Estrutura de Documentacao

**Objetivo:** Estabelecer estrutura de documentacao profissional padronizada.

**Micro-Passos:**
1. Criar diretorio `docs/` na raiz do projeto
2. Criar `docs/README.md` com indice de documentacao
3. Criar `docs/ARCHITECTURE.md` com arquitetura completa
4. Criar `docs/DATA_FLOW.md` com fluxo de dados
5. Atualizar `README.md` principal com links para docs

**Restricoes:**
- Usar Markdown puro (sem HTML complexo)
- Manter nomes em ingles para arquivos
- Incluir diagramas em ASCII art

**Definicao de Pronto (DoP):**
- Pasta `docs/` contem pelo menos 5 arquivos .md
- Indice em `docs/README.md` lista todos os documentos
- `README.md` principal referencia documentacao

**Status:** ✅ CONCLUIDO

---

### [TASK_002] - Harmonizar Documentacao Existente

**Objetivo:** Consolidar documentacao espalhada em estrutura unica.

**Micro-Passos:**
1. Listar todos arquivos .md no projeto (112 arquivos identificados)
2. Categorizar por tema (arquitetura, seguranca, robos, testes)
3. Mover documentos importantes para `docs/`
4. Criar referencias cruzadas
5. Remover ou arquivar documentos obsoletos

**Restricoes:**
- NAO deletar documentacao de robos especificos
- Manter historico em `.git`
- Preservar MDs em subpastas de robos

**Definicao de Pronto (DoP):**
- Documentacao principal centralizada em `docs/`
- Sem duplicacao de informacao
- Referencias cruzadas funcionais

**Status:** PENDENTE

---

## FASE 2: SCHEMA DE VETORES SEMANTICOS

### [TASK_003] - Definir Schema JSON v1.0

**Objetivo:** Criar schema padronizado para representacao de vetores semanticos.

**Micro-Passos:**
1. Criar `docs/VECTOR_SCHEMA.md` com especificacao completa
2. Definir schema para Pilar (todas faces, grades, aberturas)
3. Definir schema para Viga (lados A/B, segmentos, conflitos)
4. Definir schema para Laje (marco, paineis, linhas)
5. Definir schema de relacoes (pilar-viga, viga-laje, etc)
6. Criar classe Pydantic para validacao

**Restricoes:**
- Compativel com JSON Schema Draft 7
- Suportar nulls para campos opcionais
- Incluir campo de versionamento

**Definicao de Pronto (DoP):**
- Schema documentado em `docs/VECTOR_SCHEMA.md`
- Arquivo `src/core/schemas/vector_schemas.py` com Pydantic models
- Testes de validacao passando

**Status:** ✅ CONCLUIDO (documentacao)

---

### [TASK_004] - Implementar Modelos Pydantic

**Objetivo:** Criar modelos Python para validacao de vetores.

**Micro-Passos:**
1. Criar diretorio `src/core/schemas/`
2. Implementar `pilar_schema.py`
3. Implementar `viga_schema.py`
4. Implementar `laje_schema.py`
5. Implementar `relacoes_schema.py`
6. Criar arquivo `__init__.py` com exports

**Restricoes:**
- Usar Pydantic v2
- Incluir validators customizados
- Documentar com docstrings

**Definicao de Pronto (DoP):**
- Todos os schemas importaveis
- Validacao funcional em testes unitarios
- Serializacao JSON/dict bidirecional

**Status:** PENDENTE

---

## FASE 3: SISTEMA DE ENGENHARIA REVERSA

### [TASK_005] - Implementar ReverseParser

**Objetivo:** Criar parser que identifica tipo de produto DXF e extrai dados.

**Micro-Passos:**
1. Criar `src/core/reverse_engineering/__init__.py`
2. Implementar `reverse_parser.py` com classe ReverseParser
3. Definir patterns para cada tipo de produto
4. Implementar metodo `parse_product_dxf()`
5. Implementar metodo `identify_product_type()`
6. Criar testes unitarios

**Restricoes:**
- Usar ezdxf para parsing
- Suportar DXF 2010-2018 format
- Timeout de 30s por arquivo

**Definicao de Pronto (DoP):**
- Classe ReverseParser funcional
- Identifica corretamente 4 tipos de produto
- Cobertura de testes > 80%

**Status:** PENDENTE

---

### [TASK_006] - Implementar PatternMatcher

**Objetivo:** Correlacionar produto DXF com elemento no estrutural original.

**Micro-Passos:**
1. Implementar `pattern_matcher.py`
2. Criar algoritmo de match geometrico
3. Implementar calculo de confidence score
4. Suportar match por nome (fallback)
5. Implementar cache de matches
6. Criar testes com dados reais

**Restricoes:**
- Confidence minimo de 0.7 para auto-match
- Suportar rotacao de geometria
- Tolerancia de 1cm em dimensoes

**Definicao de Pronto (DoP):**
- Match funcional em 90% dos casos
- Confidence score calibrado
- False positives < 5%

**Status:** PENDENTE

---

### [TASK_007] - Implementar DataExtractor

**Objetivo:** Extrair dados de robo a partir de produto matched.

**Micro-Passos:**
1. Implementar `data_extractor.py`
2. Criar extrator para cada tipo de elemento
3. Implementar calculo de campos derivados
4. Gerar JSON no schema padrao
5. Validar output com Pydantic
6. Criar testes de integracao

**Restricoes:**
- Output deve passar validacao de schema
- Campos nao extraiveis = null
- Log de warnings para dados incompletos

**Definicao de Pronto (DoP):**
- Extracao funcional para Pilar, Viga, Laje
- JSON valido contra schema
- Integracao com vector DB

**Status:** PENDENTE

---

### [TASK_008] - Criar Botao Export nos Robos

**Objetivo:** Adicionar botao "Exportar para Estrutural" em cada robo.

**Micro-Passos:**
1. Adicionar QPushButton em RoboPilares
2. Adicionar QPushButton em RoboVigas
3. Adicionar QPushButton em RoboLajes
4. Implementar metodo `export_to_structural()` em cada
5. Integrar com memoria system
6. Feedback visual ao usuario

**Restricoes:**
- Botao desabilitado se dados incompletos
- Confirmar antes de exportar
- Log de exportacoes

**Definicao de Pronto (DoP):**
- Botao funcional em todos os robos
- Dados exportados para ChromaDB
- Feedback visual implementado

**Status:** PENDENTE

---

## FASE 4: TREINAMENTO BIDIRECIONAL

### [TASK_009] - Implementar BidirectionalTrainer

**Objetivo:** Criar classe que treina modelo usando ambos os caminhos.

**Micro-Passos:**
1. Criar `src/ai/bidirectional_trainer.py`
2. Implementar `train_from_forward()`
3. Implementar `train_from_reverse()`
4. Implementar `predict_configuration()`
5. Integrar com KNN do scikit-learn
6. Criar sistema de pesos por fonte

**Restricoes:**
- Normalizar features antes do KNN
- Limite de 10000 samples em memoria
- Persistir modelo treinado

**Definicao de Pronto (DoP):**
- Treinamento funcional em ambos caminhos
- Predicao com accuracy > 70%
- Modelo persistivel

**Status:** PENDENTE

---

### [TASK_010] - Criar BatchUploadDialog

**Objetivo:** Interface para upload em massa de estruturais e produtos.

**Micro-Passos:**
1. Criar `src/ui/dialogs/batch_upload_dialog.py`
2. Implementar QListWidget para arquivos
3. Implementar opcoes de processamento
4. Criar worker thread para batch
5. Implementar progress feedback
6. Integrar com pipeline reverso

**Restricoes:**
- Maximo 100 arquivos por batch
- Mostrar progresso individual
- Permitir cancelamento

**Definicao de Pronto (DoP):**
- Dialog funcional e responsivo
- Batch processing operacional
- Resultados salvos corretamente

**Status:** PENDENTE

---

## FASE 5: RAG MULTIMODAL

### [TASK_011] - Implementar Embeddings Reais

**Objetivo:** Substituir embeddings mock por modelos reais.

**Micro-Passos:**
1. Instalar sentence-transformers
2. Implementar TextEmbedder com all-MiniLM-L6-v2
3. Implementar GeometryEmbedder customizado
4. (Opcional) Integrar CLIP para imagens
5. Criar cache de embeddings
6. Atualizar MultimodalProcessor

**Restricoes:**
- Usar modelos leves (< 500MB)
- Cache em disco para performance
- Fallback para mock se falha

**Definicao de Pronto (DoP):**
- Embeddings de texto funcionais
- Embeddings de geometria funcionais
- Busca por similaridade operacional

**Status:** PENDENTE

---

### [TASK_012] - Implementar Busca Vetorial Avancada

**Objetivo:** Criar sistema de busca que combina multiplas modalidades.

**Micro-Passos:**
1. Implementar `src/ai/vector_search.py`
2. Criar indices separados por modalidade
3. Implementar fusao de resultados
4. Adicionar filtros por metadados
5. Implementar ranking personalizado
6. Criar API unificada de busca

**Restricoes:**
- Usar ChromaDB como backend
- Latencia < 500ms por query
- Top-k configuravel

**Definicao de Pronto (DoP):**
- Busca multimodal funcional
- Resultados relevantes
- Performance dentro do SLA

**Status:** PENDENTE

---

## FASE 6: INTEGRACAO FINAL

### [TASK_013] - Sincronizacao Byterover Automatica

**Objetivo:** Implementar sync automatico de insights para Byterover.

**Micro-Passos:**
1. Integrar Byterover MCP tools no codigo
2. Implementar triggers de sync
3. Criar formatador de insights
4. Implementar queue offline
5. Criar retry logic
6. Adicionar logging detalhado

**Restricoes:**
- Sync apenas insights importantes
- Rate limit de 10 requests/min
- Fallback para queue local

**Definicao de Pronto (DoP):**
- Sync automatico funcional
- Insights chegando no Byterover
- Resiliente a falhas de rede

**Status:** PENDENTE

---

### [TASK_014] - Criar TrainingDashboard

**Objetivo:** Dashboard visual para monitorar treinamento do modelo.

**Micro-Passos:**
1. Criar `src/ui/modules/training_dashboard.py`
2. Implementar graficos de metricas
3. Mostrar contagem de samples
4. Mostrar accuracy por tipo
5. Listar samples pendentes de validacao
6. Integrar no MainWindow

**Restricoes:**
- Usar PyQtGraph ou matplotlib
- Atualizar em tempo real
- Nao impactar performance

**Definicao de Pronto (DoP):**
- Dashboard funcional
- Metricas visiveis
- Atualizacao em tempo real

**Status:** PENDENTE

---

### [TASK_015] - Final System Integration Test

**Objetivo:** Validar funcionamento end-to-end de todo o sistema.

**Micro-Passos:**
1. Criar suite de testes E2E
2. Testar fluxo forward completo
3. Testar fluxo reverse completo
4. Testar treinamento bidirecional
5. Testar predicao em novos elementos
6. Documentar resultados

**Restricoes:**
- Usar dados reais de producao
- Cobrir todos os tipos de elemento
- Documentar falhas encontradas

**Definicao de Pronto (DoP):**
- Todos os fluxos passando
- Accuracy geral > 75%
- Documentacao de testes completa

**Status:** PENDENTE

---

# 3. PROTOCOLO DE VALIDACAO (Feedback Loops)

## 3.1 Unit Validation

| Task | Comando de Validacao |
|------|---------------------|
| TASK_001 | `ls docs/*.md \| wc -l` >= 5 |
| TASK_004 | `python -c "from src.core.schemas import *"` |
| TASK_005 | `python -m pytest tests/test_reverse_parser.py` |
| TASK_006 | `python -m pytest tests/test_pattern_matcher.py` |
| TASK_009 | `python -m pytest tests/test_bidirectional.py` |
| TASK_011 | `python -c "from src.ai.multimodal_processor import *"` |

## 3.2 Integration Check

```python
# Teste de integracao completo
def test_full_pipeline():
    # 1. Carregar estrutural
    analyzer = StructuralAnalyzer()
    analyzer.load_dxf("test_structural.dxf")
    
    # 2. Processar elementos
    pilares = analyzer.find_pillars()
    vigas = analyzer.find_beams()
    lajes = analyzer.find_slabs()
    
    # 3. Gerar produto via robo
    robo = RoboPilares(pilares[0])
    robo.generate_scr()
    
    # 4. Engenharia reversa
    reverse = ReverseEngineeringPipeline()
    result = reverse.reverse_engineer(
        product_dxf="produto.dxf",
        structural_dxf="test_structural.dxf"
    )
    
    # 5. Validar match
    assert result['success'] == True
    assert result['elemento_match']['confidence'] > 0.8
    
    # 6. Treinar modelo
    trainer = BidirectionalTrainer()
    trainer.train_from_reverse(result)
    
    # 7. Predizer novo elemento
    prediction = trainer.predict_configuration(pilares[1])
    assert prediction is not None
```

## 3.3 Fail-Safe

| Falha | Rollback/Correcao |
|-------|-------------------|
| Import error | Verificar requirements.txt e reinstalar |
| Schema validation | Revisar schema e regenerar models |
| Match failure | Aumentar tolerancia ou revisar patterns |
| Sync failure | Ativar queue offline |
| Performance | Reduzir batch size ou ativar cache |

---

# 4. CRONOGRAMA SUGERIDO

| Fase | Tasks | Estimativa |
|------|-------|------------|
| Fase 1 | TASK_001, TASK_002 | 1 sessao |
| Fase 2 | TASK_003, TASK_004 | 1 sessao |
| Fase 3 | TASK_005-008 | 2-3 sessoes |
| Fase 4 | TASK_009, TASK_010 | 2 sessoes |
| Fase 5 | TASK_011, TASK_012 | 2-3 sessoes |
| Fase 6 | TASK_013-015 | 2 sessoes |

**Total Estimado:** 10-14 sessoes de desenvolvimento

---

# 5. GARANTIA DE 100% FUNCIONALIDADE

O plano e considerado completo quando:

1. ✅ Documentacao profissional completa em `docs/`
2. ✅ Schema JSON v1.0 definido e implementado
3. ✅ Sistema de engenharia reversa funcional
4. ✅ Treinamento bidirecional operacional
5. ✅ RAG multimodal com embeddings reais
6. ✅ Sincronizacao Byterover automatica
7. ✅ Dashboard de treinamento visivel
8. ✅ Teste E2E passando com accuracy > 75%

**Final System Integration Test:** Executar fluxo completo de ponta a ponta validando todos os componentes integrados.
