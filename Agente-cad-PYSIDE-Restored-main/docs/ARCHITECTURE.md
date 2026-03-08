# Arquitetura do Sistema AgenteCAD / Estrutural Analyzer

## 1. Visao Geral

O AgenteCAD e um sistema de analise estrutural inteligente que processa arquivos DXF (desenhos CAD estruturais) e gera automaticamente scripts de producao para elementos estruturais como lajes, vigas e pilares.

### 1.1 Proposito do Sistema

```
ENTRADA: DXF Estrutural Bruto (projeto de engenharia)
         ↓
PROCESSAMENTO: Interpretacao semantica via ML + Regras
         ↓
SAIDA: Scripts SCR + DXF Produtos (paineis, sarrafos, grades)
```

### 1.2 Principios Arquiteturais

1. **Modularidade**: Cada robo e independente mas compartilha dados via hub central
2. **Aprendizado Continuo**: Sistema de ML que melhora com correcoes do usuario
3. **Memoria Hierarquica**: 3 niveis (curto/medio/longo prazo) para retencao de conhecimento
4. **Multimodalidade**: Preparado para processar texto, imagens e geometria

---

## 2. Componentes Principais

### 2.1 Structural Analyzer (Hub Central)

**Arquivo**: `main.py`
**Classe Principal**: `MainWindow`

```python
class MainWindow(QMainWindow):
    def __init__(self):
        # Estado Central
        self.db = DatabaseManager()          # SQLite persistencia
        self.memory = HierarchicalMemory()   # Sistema de aprendizado
        self.spatial_index = SpatialIndex()  # Indice R-Tree
        
        # Engines de Processamento
        self.context_engine = ContextEngine()
        self.pillar_analyzer = PillarAnalyzer()
        self.slab_tracer = SlabTracer()
        
        # Dados Processados
        self.pillars_found = []   # Pilares identificados
        self.slabs_found = []     # Lajes identificadas
        self.beams_found = []     # Vigas identificadas
```

### 2.2 Robos Especializados

| Robo | Funcao | Entrada | Saida |
|------|--------|---------|-------|
| **Robo_Lajes** | Processar formas de lajes | Coordenadas, dimensoes | SCR de paineis |
| **Robo_Pilares** | Processar pilares | Geometria, faces, grades | SCR de pilares |
| **Robo_Laterais** | Processar laterais de vigas | Segmentos, conflitos | SCR de laterais |
| **Robo_Fundos** | Processar fundos de vigas | Dimensoes, sarrafos | SCR de fundos |

### 2.3 Pipeline de Dados

```
┌─────────────────────────────────────────────────────────────────┐
│                    DXF ESTRUTURAL BRUTO                         │
│                (AutoCAD/BricsCAD export)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DXF LOADER                                 │
│  • Parsing de entidades (LINE, POLYLINE, TEXT, MTEXT, INSERT)  │
│  • Extracoes de layers, blocos, atributos                       │
│  • Normalizacao de coordenadas                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SPATIAL INDEX                                │
│  • R-Tree para busca espacial eficiente                        │
│  • Bounding boxes de todas entidades                           │
│  • Queries por regiao ou proximidade                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   GEOMETRY ENGINE                               │
│  • Classificacao de formas (RECT, L, T, U, CIRCLE)             │
│  • Calculo de areas, perimetros, centroides                    │
│  • Deteccao de relacoes espaciais                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TEXT ASSOCIATOR                               │
│  • Vinculacao de textos a geometrias                           │
│  • Extracao de dimensoes (12x40, V1, P-1, L1)                  │
│  • Interpretacao de niveis e cotas                              │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│  PILLAR ANALYZER  │ │   SLAB TRACER     │ │   BEAM WALKER     │
│  • Faces A-H      │ │   • Marcos        │ │   • Segmentos     │
│  • Grades         │ │   • Paineis       │ │   • Conflitos     │
│  • Aberturas      │ │   • Sarrafos      │ │   • Dimensoes     │
└───────────────────┘ └───────────────────┘ └───────────────────┘
              │               │               │
              └───────────────┼───────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CONTEXT ENGINE                                │
│  • Memoria hierarquica de decisoes                             │
│  • Aprendizado de padroes do usuario                           │
│  • Predicao de vinculos e atributos                            │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│   ROBO PILARES    │ │   ROBO LAJES      │ │   ROBO VIGAS      │
│  (PilarService)   │ │  (LajeMainWindow) │ │  (VigaMainWindow) │
└───────────────────┘ └───────────────────┘ └───────────────────┘
              │               │               │
              └───────────────┼───────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SCRIPT GENERATOR                              │
│  • Geracao de arquivos .SCR (AutoCAD Script)                   │
│  • Comandos: LINE, PLINE, TEXT, HATCH, LAYER                   │
│  • Otimizacao de sequencia de desenho                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DXF PRODUTO FINAL                            │
│  • Paineis de laje com medidas                                 │
│  • Grades de pilar com sarrafos                                │
│  • Fundos e laterais de viga                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Sistema de Memoria

### 3.1 Arquitetura de 3 Niveis

```
┌─────────────────────────────────────────────────────────────────┐
│                   LONGO PRAZO (Byterover)                       │
│  • Conhecimento global (cross-projeto)                         │
│  • Padroes universais de interpretacao                         │
│  • Insights arquiteturais permanentes                          │
│  • TTL: Permanente                                             │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Sincronizacao Seletiva
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  MEDIO PRAZO (SQLite + ChromaDB)                │
│  • Contexto do projeto atual                                   │
│  • Historico de treinamentos do usuario                        │
│  • Vetores de similaridade por elemento                        │
│  • TTL: 1 semana                                               │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Cache Inteligente
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CURTO PRAZO (RAM)                             │
│  • Sessao ativa do usuario                                     │
│  • Cache de calculos geometricos                               │
│  • Estado temporario de edicao                                 │
│  • TTL: 1 hora                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Classe HierarchicalMemory

```python
class HierarchicalMemory:
    def save_training_event(self, project_context, item_context, field_context, label):
        """
        Salva evento de treinamento do usuario.
        
        Args:
            project_context: {id, name, dxf_path}
            item_context: {type: 'PILAR'|'VIGA'|'LAJE', dna_vector: [...]}
            field_context: {field_name, link_type, value}
            label: Valor correto definido pelo usuario
        """
        
    def retrieve_relevant_context(self, role, item_type, dna_vector):
        """
        Recupera contexto relevante para predicao.
        
        Returns:
            {avg_rel_pos, samples, similarity, predicted_status}
        """
```

---

## 4. Integracao com Robos

### 4.1 Interface de Comunicacao

Cada robo recebe dados do hub central atraves de um contrato padronizado:

```python
# Dados enviados para cada Robo
robo_data = {
    "projeto": {
        "id": "uuid",
        "nome": "Edificio X",
        "dxf_path": "/path/to/estrutural.dxf"
    },
    "elemento": {
        "tipo": "PILAR",  # ou VIGA, LAJE
        "nome": "P-1",
        "geometria": {...},
        "dimensoes": {...},
        "vinculos": {...}
    },
    "contexto": {
        "vigas_adjacentes": [...],
        "lajes_adjacentes": [...],
        "pilares_adjacentes": [...]
    }
}
```

### 4.2 Proxy de Licenciamento

```python
class LicensingProxy:
    """Interface unificada de creditos para todos os robos."""
    
    def consume_credits(self, amount):
        """Debita creditos do usuario."""
        
    def consultar_saldo(self):
        """Retorna saldo atual."""
```

---

## 5. Tecnologias Utilizadas

| Categoria | Tecnologia | Versao |
|-----------|------------|--------|
| **Linguagem** | Python | 3.12+ |
| **UI Framework** | PySide6 | 6.6+ |
| **Vector DB** | ChromaDB | 0.4+ |
| **Database** | SQLite | 3.x |
| **Cloud Backend** | Supabase | - |
| **DXF Parser** | ezdxf | 1.1+ |
| **Geometry** | Shapely | 2.0+ |
| **ML** | scikit-learn | 1.2+ |
| **Spatial Index** | rtree | 1.0+ |

---

## 6. Proximos Passos Arquiteturais

1. **Implementar RAG Multimodal**: Busca vetorial em texto, imagem e DXF
2. **Engenharia Reversa**: DXF Produto → Dados de Treinamento
3. **Pipeline Bidirecional**: Treinamento por ambos os caminhos
4. **Agentes de Curadoria**: Validacao automatica de interpretacoes
5. **Geracao Dinamica de DXF**: Construcao baseada em vetores semanticos
