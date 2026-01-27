# Fluxo de Dados Completo - AgenteCAD

## 1. Pipeline Principal

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FLUXO FORWARD (Normal)                               │
│                                                                             │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐  │
│  │   DXF   │───▶│  PARSE  │───▶│ ANALYZE │───▶│  ROBOS  │───▶│   SCR   │  │
│  │  BRUTO  │    │   &     │    │    &    │    │    &    │    │    &    │  │
│  │         │    │  INDEX  │    │ CONTEXT │    │ PROCESS │    │ PRODUTO │  │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↑↓
                         Treinamento Bidirecional
                                    ↑↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FLUXO REVERSE (Engenharia Reversa)                   │
│                                                                             │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐  │
│  │   DXF   │───▶│  PARSE  │───▶│  MATCH  │───▶│ EXTRACT │───▶│ VECTOR  │  │
│  │ PRODUTO │    │ PRODUCT │    │    TO   │    │  ROBOT  │    │   DB    │  │
│  │         │    │  TYPE   │    │ STRUCT  │    │  DATA   │    │         │  │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Fluxo Forward Detalhado

### 2.1 Etapa 1: Carregamento DXF

```python
# Entrada: Arquivo DXF estrutural do AutoCAD/BricsCAD
# Saida: Lista de entidades parseadas

dxf_loader = DXFLoader()
entities = dxf_loader.load("estrutural.dxf")

# Entidades extraidas:
# - LINE: Linhas simples
# - POLYLINE/LWPOLYLINE: Polilinhas
# - TEXT/MTEXT: Textos
# - INSERT: Blocos
# - CIRCLE/ARC: Circulos e arcos
# - HATCH: Hachurados
```

### 2.2 Etapa 2: Indexacao Espacial

```python
# Entrada: Lista de entidades
# Saida: Indice R-Tree para busca eficiente

spatial_index = SpatialIndex()
spatial_index.build(entities)

# Operacoes disponiveis:
# - query_point(x, y, radius)
# - query_region(bbox)
# - nearest_neighbors(point, k)
```

### 2.3 Etapa 3: Analise de Elementos

```python
# Pilares
pillar_analyzer = PillarAnalyzer(spatial_index)
pillars = pillar_analyzer.find_all()
# Retorna: Lista de pilares com formato, dimensoes, posicao

# Vigas
beam_walker = BeamWalker(spatial_index)
beams = beam_walker.find_all()
# Retorna: Lista de vigas com segmentos, conflitos, dimensoes

# Lajes
slab_tracer = SlabTracer(spatial_index)
slabs = slab_tracer.find_all()
# Retorna: Lista de lajes com marco, area, nivel
```

### 2.4 Etapa 4: Associacao de Textos

```python
# Entrada: Elementos encontrados + textos do DXF
# Saida: Elementos enriquecidos com informacoes textuais

text_associator = TextAssociator(spatial_index)

for pilar in pillars:
    text_associator.associate(pilar)
    # Vincula: nome, dimensoes, nivel

for viga in beams:
    text_associator.associate(viga)
    # Vincula: nome, dimensoes, corte

for laje in slabs:
    text_associator.associate(laje)
    # Vincula: nome, altura h, nivel
```

### 2.5 Etapa 5: Contextualizacao

```python
# Entrada: Elementos analisados
# Saida: Contexto com relacoes entre elementos

context_engine = ContextEngine()
context = context_engine.build_context(pillars, beams, slabs)

# Contexto inclui:
# - pilar_viga: Qual viga chega em qual face do pilar
# - pilar_laje: Qual laje toca qual face do pilar
# - viga_laje: Qual laje e adjacente a qual lado da viga
```

### 2.6 Etapa 6: Processamento por Robo

```python
# Robo Pilares
for pilar in pillars:
    robo_pilares = RoboPilares(pilar, context)
    scr_content = robo_pilares.generate()
    # Gera: SCR com grades, sarrafos, aberturas, parafusos

# Robo Vigas (Laterais)
for viga in beams:
    robo_laterais = RoboLaterais(viga, context)
    scr_content = robo_laterais.generate()
    # Gera: SCR com lateral, recortes

# Robo Vigas (Fundos)
for viga in beams:
    robo_fundos = RoboFundos(viga, context)
    scr_content = robo_fundos.generate()
    # Gera: SCR com fundo, sarrafos

# Robo Lajes
for laje in slabs:
    robo_lajes = RoboLajes(laje, context)
    scr_content = robo_lajes.generate()
    # Gera: SCR com paineis, cotas
```

### 2.7 Etapa 7: Geracao de Produto

```python
# Entrada: Scripts SCR
# Saida: DXF produto ou execucao em AutoCAD

# Opcao 1: Salvar SCR para execucao manual
with open("output.scr", "w") as f:
    f.write(scr_content)

# Opcao 2: Execucao via pyautocad (se disponivel)
from pyautocad import Autocad
acad = Autocad()
acad.doc.SendCommand(scr_content)
```

---

## 3. Fluxo Reverse Detalhado

### 3.1 Etapa 1: Parse de Produto

```python
# Entrada: DXF produto (grade, fundo, lateral, painel)
# Saida: Tipo identificado + dados extraidos

reverse_parser = ReverseParser()
product_type, product_data = reverse_parser.parse("grade_p1.dxf")

# Tipos identificaveis:
# - GRADE_PILAR
# - FUNDO_VIGA
# - LATERAL_VIGA
# - PAINEL_LAJE
```

### 3.2 Etapa 2: Match com Estrutural

```python
# Entrada: Dados do produto + DXF estrutural original
# Saida: Match com elemento correspondente

pattern_matcher = PatternMatcher()
match = pattern_matcher.match(
    product_data=product_data,
    structural_dxf="estrutural.dxf"
)

# Match retorna:
# {
#     "elemento_tipo": "PILAR",
#     "elemento_nome": "P-1",
#     "face": "A",
#     "confidence": 0.92
# }
```

### 3.3 Etapa 3: Extracao de Dados de Robo

```python
# Entrada: Produto matched
# Saida: Dados no formato do schema JSON

data_extractor = ReverseDataExtractor()
robot_data = data_extractor.extract(
    product_data=product_data,
    match=match,
    product_type=product_type
)

# robot_data contem todos os campos do schema:
# - identificacao
# - dimensoes
# - faces/lados (dependendo do tipo)
# - producao (grades, sarrafos, etc)
```

### 3.4 Etapa 4: Injecao no Vector DB

```python
# Entrada: Dados extraidos
# Saida: Vetor armazenado no ChromaDB

# Gerar embedding
embedding = multimodal_processor.generate_embedding(robot_data)

# Armazenar
memory_system.store(
    content=robot_data,
    modality=ModalityType.STRUCTURAL_PATTERN,
    tier=MemoryTier.MEDIUM_TERM,
    metadata={
        "source": "REVERSE_ENGINEERING",
        "product_type": product_type,
        "match_confidence": match["confidence"],
        "structural_dxf": "estrutural.dxf"
    },
    vector_embedding=embedding
)
```

---

## 4. Fluxo de Treinamento

### 4.1 Treinamento Forward

```
Usuario carrega DXF
        ↓
Sistema interpreta (com possiveis erros)
        ↓
Usuario corrige interpretacao
        ↓
Usuario clica "Validar como Treino"
        ↓
Sistema salva no Vector DB como exemplo validado
        ↓
Proximo DXF similar tera melhor predicao
```

### 4.2 Treinamento Reverse

```
Usuario tem DXF produto pronto (feito manualmente)
        ↓
Usuario carrega produto no sistema
        ↓
Sistema faz engenharia reversa automatica
        ↓
Usuario valida se match esta correto
        ↓
Sistema salva no Vector DB como exemplo validado
        ↓
Proximo elemento similar tera melhor predicao
```

### 4.3 Predicao com Dados Combinados

```python
# Ao processar novo elemento:
trainer = BidirectionalTrainer()

# 1. Extrair features do elemento
features = trainer.extract_features(novo_elemento)

# 2. Buscar vizinhos (combina forward + reverse)
neighbors = trainer.find_neighbors(
    features,
    sources=["FORWARD", "REVERSE"],
    k=5
)

# 3. Ponderar por confianca e similaridade
predicted_config = trainer.weighted_predict(neighbors)

# 4. Aplicar configuracao sugerida
robo.apply_configuration(predicted_config)
```

---

## 5. Fluxo de Memoria

### 5.1 Hierarquia de Armazenamento

```
┌─────────────────────────────────────────────────────────────────┐
│                    CURTO PRAZO (RAM)                            │
│  TTL: 1 hora                                                    │
│  Conteudo:                                                      │
│  - Sessao ativa do usuario                                     │
│  - Cache de calculos geometricos                               │
│  - Estado de edicao temporario                                 │
│  - Historico de undo/redo                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                    Promocao se importante
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   MEDIO PRAZO (SQLite + ChromaDB)               │
│  TTL: 1 semana                                                  │
│  Conteudo:                                                      │
│  - Contexto do projeto atual                                   │
│  - Treinamentos validados do usuario                           │
│  - Vetores de similaridade locais                              │
│  - Historico de operacoes                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                    Sync se insight importante
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LONGO PRAZO (Byterover)                       │
│  TTL: Permanente                                                │
│  Conteudo:                                                      │
│  - Conhecimento global cross-projeto                           │
│  - Padroes arquiteturais universais                            │
│  - Insights de debugging                                       │
│  - Decisoes de design criticas                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Criterios de Promocao

```python
def should_promote_to_medium(item):
    """Promover de curto para medio prazo."""
    return (
        item.access_count > 3 or
        item.validation_status == "VALIDATED" or
        item.importance_score > 0.7
    )

def should_sync_to_long(item):
    """Sincronizar com Byterover."""
    return (
        item.is_architectural_decision or
        item.is_error_resolution or
        item.is_pattern_discovery or
        item.importance_score > 0.9
    )
```

---

## 6. Formato de Dados Inter-Modulo

### 6.1 Analyzer → Robo

```json
{
  "projeto": {
    "id": "uuid",
    "nome": "Edificio X",
    "dxf_path": "/path/estrutural.dxf"
  },
  "elemento": {
    "tipo": "PILAR",
    "nome": "P-1",
    "formato": "RETANGULAR",
    "geometria": {
      "centroide": [100.0, 200.0],
      "vertices": [[...], [...]]
    },
    "dimensoes": {
      "largura": 40,
      "altura": 60
    }
  },
  "contexto": {
    "vigas_adjacentes": [
      {"nome": "V1", "face": "A", "tipo": "CHEGADA"}
    ],
    "lajes_adjacentes": [
      {"nome": "L1", "face": "A", "nivel": "+3.00"}
    ]
  }
}
```

### 6.2 Robo → Script Generator

```json
{
  "tipo_script": "GRADE_PILAR",
  "elemento_nome": "P-1",
  "comandos": [
    {"tipo": "LAYER", "nome": "GRADE"},
    {"tipo": "RECTANGLE", "p1": [0,0], "p2": [40,150]},
    {"tipo": "LINE", "p1": [0,30], "p2": [40,30]},
    {"tipo": "TEXT", "pos": [20,5], "texto": "P-1"}
  ],
  "metadados": {
    "area_m2": 0.024,
    "sarrafos": 4,
    "parafusos": 8
  }
}
```

---

## 7. Metricas de Fluxo

| Metrica | Descricao | Meta |
|---------|-----------|------|
| Parse Time | Tempo para carregar DXF | < 5s |
| Analysis Time | Tempo para identificar elementos | < 10s |
| Prediction Time | Tempo para sugerir configuracao | < 1s |
| SCR Generation | Tempo para gerar script | < 2s |
| Match Accuracy | Acuracia do pattern matching | > 90% |
| Prediction Accuracy | Acuracia da predicao ML | > 75% |
