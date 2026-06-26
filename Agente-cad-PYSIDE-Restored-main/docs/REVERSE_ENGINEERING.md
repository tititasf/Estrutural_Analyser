# Sistema de Engenharia Reversa - AgenteCAD

## 1. Visao Geral

O sistema de Engenharia Reversa permite alimentar o banco de vetores a partir de DXFs produtos ja finalizados, criando um ciclo de aprendizado bidirecional que acelera o treinamento do modelo de interpretacao.

### 1.1 Fluxo Bidirecional

```
┌─────────────────────────────────────────────────────────────────┐
│                 FLUXO NORMAL (Forward)                          │
│                                                                 │
│  DXF Bruto → Analyzer → Robos → SCR → DXF Produto              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↑↓
                     Treinamento Cruzado
                              ↑↓
┌─────────────────────────────────────────────────────────────────┐
│               FLUXO REVERSO (Backward)                          │
│                                                                 │
│  DXF Produto → Parser → Extrator → Dados Robo → Vector DB      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Beneficios

1. **Alimentacao em massa**: Aproveitar DXFs ja produzidos manualmente
2. **Validacao automatica**: Produtos finais sao "ground truth"
3. **Aceleracao de treinamento**: Mais dados = melhor predicao
4. **Consistencia**: Padroniza interpretacao baseada em exemplos reais

---

## 2. Arquitetura do Sistema Reverso

### 2.1 Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                   REVERSE PARSER                                │
│  • Identifica tipo de produto (grade, fundo, lateral, painel)  │
│  • Extrai geometria e dimensoes                                │
│  • Reconhece padroes de layout                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PATTERN MATCHER                               │
│  • Correlaciona produto com estrutural original                │
│  • Identifica elemento fonte (pilar, viga, laje)               │
│  • Valida correspondencia geometrica                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DATA EXTRACTOR                                │
│  • Extrai campos dos robos a partir do produto                 │
│  • Calcula valores derivados (sarrafos, aberturas)             │
│  • Gera JSON no schema padrao                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   VECTOR INJECTOR                               │
│  • Gera embeddings do elemento                                 │
│  • Insere no ChromaDB com metadados                            │
│  • Atualiza indice de similaridade                             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Classes Principais

```python
# src/core/reverse_engineering/reverse_parser.py

class ReverseParser:
    """Parser de DXF produto para extracao de dados."""
    
    PRODUCT_PATTERNS = {
        'GRADE_PILAR': {
            'layers': ['GRADE', 'SARRAFO', 'PARAFUSO'],
            'patterns': ['retangulo_principal', 'linhas_horizontais']
        },
        'FUNDO_VIGA': {
            'layers': ['FUNDO', 'SARRAFO'],
            'patterns': ['retangulo_largo', 'linhas_transversais']
        },
        'LATERAL_VIGA': {
            'layers': ['LATERAL', 'RECORTE'],
            'patterns': ['retangulo_alto', 'recortes_pilar']
        },
        'PAINEL_LAJE': {
            'layers': ['PAINEL', 'MARCO'],
            'patterns': ['poligono_fechado', 'cotas_internas']
        }
    }
    
    def parse_product_dxf(self, dxf_path: str) -> Dict:
        """
        Analisa DXF produto e extrai informacoes estruturadas.
        
        Returns:
            {
                'tipo_produto': 'GRADE_PILAR',
                'geometria': {...},
                'dimensoes': {...},
                'componentes': [...]
            }
        """
        pass
    
    def identify_product_type(self, entities: List) -> str:
        """Identifica tipo de produto baseado em padroes."""
        pass
```

```python
# src/core/reverse_engineering/pattern_matcher.py

class PatternMatcher:
    """Correlaciona produto com estrutural original."""
    
    def match_to_structural(
        self, 
        product_data: Dict, 
        structural_dxf_path: str
    ) -> Optional[Dict]:
        """
        Encontra elemento no estrutural que corresponde ao produto.
        
        Returns:
            {
                'elemento_tipo': 'PILAR',
                'elemento_nome': 'P-1',
                'face': 'A',
                'confidence': 0.95,
                'match_details': {...}
            }
        """
        pass
    
    def calculate_match_score(
        self, 
        product_geom: Dict, 
        structural_geom: Dict
    ) -> float:
        """Calcula score de correspondencia geometrica."""
        pass
```

```python
# src/core/reverse_engineering/data_extractor.py

class ReverseDataExtractor:
    """Extrai dados de robo a partir de produto."""
    
    def extract_pilar_data(self, product_data: Dict, match: Dict) -> Dict:
        """
        Extrai dados completos de pilar do produto.
        
        Returns:
            Schema completo de pilar (ver VECTOR_SCHEMA.md)
        """
        pass
    
    def extract_viga_data(self, product_data: Dict, match: Dict) -> Dict:
        """Extrai dados de viga (fundo ou lateral)."""
        pass
    
    def extract_laje_data(self, product_data: Dict, match: Dict) -> Dict:
        """Extrai dados de laje."""
        pass
```

---

## 3. Fluxo de Engenharia Reversa

### 3.1 Passo a Passo

```python
# Exemplo de uso do sistema de engenharia reversa

from reverse_engineering import ReverseEngineeringPipeline

# 1. Inicializar pipeline
pipeline = ReverseEngineeringPipeline(
    vector_db=chroma_client,
    structural_analyzer=analyzer
)

# 2. Carregar DXF produto
product_path = "grade_pilar_p1_face_a.dxf"
structural_path = "estrutural_original.dxf"

# 3. Executar engenharia reversa
result = pipeline.reverse_engineer(
    product_dxf=product_path,
    structural_dxf=structural_path,
    auto_validate=False  # Requer validacao manual
)

# 4. Resultado
print(result)
# {
#     'success': True,
#     'tipo_produto': 'GRADE_PILAR',
#     'elemento_match': {
#         'tipo': 'PILAR',
#         'nome': 'P-1',
#         'face': 'A',
#         'confidence': 0.92
#     },
#     'dados_extraidos': {...},  # Schema completo
#     'status': 'PENDING_VALIDATION'
# }

# 5. Validar e injetar no vector DB
if user_validates(result):
    pipeline.inject_to_vector_db(result, status='VALIDATED')
```

### 3.2 Fluxo Visual

```
┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│   DXF Produto  │────▶│  Parse & ID    │────▶│  Match to      │
│  (grade.dxf)   │     │  Product Type  │     │  Structural    │
└────────────────┘     └────────────────┘     └────────────────┘
                                                      │
                                                      ▼
┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│  Inject to     │◀────│  User          │◀────│  Extract       │
│  Vector DB     │     │  Validation    │     │  Robot Data    │
└────────────────┘     └────────────────┘     └────────────────┘
```

---

## 4. Botao "Exportar para Estrutural" nos Robos

### 4.1 Funcionalidade

Cada robo tera um botao que permite exportar os dados atuais para alimentar o vetor de treinamento, vinculando automaticamente ao estrutural correspondente.

### 4.2 Implementacao

```python
# Em cada Robo (ex: RoboPilares)

class RoboPilares(QWidget):
    def __init__(self):
        # ... inicializacao existente ...
        
        # Botao de exportacao
        self.btn_export_structural = QPushButton("Exportar para Estrutural")
        self.btn_export_structural.clicked.connect(self.export_to_structural)
        
    def export_to_structural(self):
        """
        Exporta dados atuais do pilar para o banco de vetores,
        vinculando ao estrutural original.
        """
        # 1. Coletar dados atuais
        pilar_data = self.collect_current_pilar_data()
        
        # 2. Gerar vetor JSON completo
        json_vector = self.generate_vector_json(pilar_data)
        
        # 3. Criar embedding
        embedding = self.multimodal_processor.generate_embedding(json_vector)
        
        # 4. Injetar no banco
        self.memory_system.store(
            content=json_vector,
            modality=ModalityType.STRUCTURAL_PATTERN,
            tier=MemoryTier.MEDIUM_TERM,
            metadata={
                'source': 'ROBO_EXPORT',
                'tipo_elemento': 'PILAR',
                'structural_dxf': self.current_structural_path,
                'validation_status': 'MANUAL_EXPORT'
            }
        )
        
        # 5. Feedback ao usuario
        QMessageBox.information(
            self, 
            "Exportacao",
            f"Pilar {pilar_data['nome']} exportado para treinamento!"
        )
```

---

## 5. Upload de Estruturais e Produtos em Batch

### 5.1 Interface de Upload em Massa

```python
class BatchUploadDialog(QDialog):
    """Dialog para upload em massa de estruturais e produtos."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Upload em Massa para Treinamento")
        
        # Layout
        layout = QVBoxLayout(self)
        
        # Secao: Estruturais brutos
        layout.addWidget(QLabel("DXFs Estruturais Brutos:"))
        self.list_structural = QListWidget()
        self.btn_add_structural = QPushButton("Adicionar Estruturais...")
        
        # Secao: Produtos finalizados
        layout.addWidget(QLabel("DXFs Produtos (grades, fundos, etc):"))
        self.list_products = QListWidget()
        self.btn_add_products = QPushButton("Adicionar Produtos...")
        
        # Opcoes
        self.chk_auto_match = QCheckBox("Tentar match automatico")
        self.chk_validate_manual = QCheckBox("Requerer validacao manual")
        
        # Botao processar
        self.btn_process = QPushButton("Processar Batch")
        self.btn_process.clicked.connect(self.process_batch)
        
    def process_batch(self):
        """Processa todos os arquivos em batch."""
        pipeline = ReverseEngineeringPipeline()
        
        results = []
        for structural in self.structural_files:
            for product in self.product_files:
                result = pipeline.reverse_engineer(
                    product_dxf=product,
                    structural_dxf=structural,
                    auto_validate=not self.chk_validate_manual.isChecked()
                )
                results.append(result)
        
        self.show_results_summary(results)
```

---

## 6. Treinamento Bidirecional

### 6.1 Arquitetura de Treinamento

```
┌─────────────────────────────────────────────────────────────────┐
│                    DADOS DE TREINAMENTO                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────┐          ┌───────────────────┐          │
│  │   Caminho Normal  │          │  Caminho Reverso  │          │
│  │   (Forward Path)  │          │  (Backward Path)  │          │
│  ├───────────────────┤          ├───────────────────┤          │
│  │ • Estrutural novo │          │ • DXF produto     │          │
│  │ • Interpretacao   │          │ • Engenharia rev  │          │
│  │ • Correcao manual │          │ • Match auto      │          │
│  │ • Validacao       │          │ • Validacao       │          │
│  └─────────┬─────────┘          └─────────┬─────────┘          │
│            │                              │                     │
│            └──────────────┬───────────────┘                     │
│                           ▼                                     │
│              ┌───────────────────────┐                          │
│              │   VECTOR DATABASE     │                          │
│              │   (ChromaDB)          │                          │
│              │                       │                          │
│              │ • DNA geometrico      │                          │
│              │ • Embeddings          │                          │
│              │ • Metadados           │                          │
│              │ • Validacao status    │                          │
│              └───────────────────────┘                          │
│                           │                                     │
│                           ▼                                     │
│              ┌───────────────────────┐                          │
│              │   MODELO ML           │                          │
│              │   (KNN + Embeddings)  │                          │
│              └───────────────────────┘                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Algoritmo de Treinamento Cruzado

```python
class BidirectionalTrainer:
    """Treinador bidirecional que usa ambos os caminhos."""
    
    def train_from_forward(self, structural_session: Dict):
        """
        Treina a partir do caminho normal:
        Estrutural → Interpretacao → Correcao → Validacao
        """
        # Extrair features do elemento
        features = self.extract_geometric_features(structural_session['elemento'])
        
        # Capturar configuracao validada
        config = structural_session['configuracao_final']
        
        # Salvar no vector DB
        self.save_training_sample(
            features=features,
            config=config,
            source='FORWARD',
            confidence=1.0  # Validacao manual = alta confianca
        )
    
    def train_from_reverse(self, reverse_result: Dict):
        """
        Treina a partir do caminho reverso:
        DXF Produto → Match → Extracao → Validacao
        """
        # Extrair features do match
        features = self.extract_geometric_features(reverse_result['elemento_match'])
        
        # Configuracao extraida do produto
        config = reverse_result['dados_extraidos']
        
        # Confianca baseada no match score
        confidence = reverse_result['elemento_match']['confidence']
        
        # Salvar no vector DB
        self.save_training_sample(
            features=features,
            config=config,
            source='REVERSE',
            confidence=confidence
        )
    
    def predict_configuration(self, new_element: Dict) -> Dict:
        """
        Prediz configuracao para novo elemento usando
        conhecimento de ambos os caminhos.
        """
        # Extrair features
        features = self.extract_geometric_features(new_element)
        
        # Buscar vizinhos mais proximos (combina ambas fontes)
        neighbors = self.find_nearest_neighbors(
            features,
            sources=['FORWARD', 'REVERSE'],
            k=5
        )
        
        # Ponderar por confianca e similaridade
        predicted_config = self.weighted_interpolation(neighbors)
        
        return predicted_config
```

---

## 7. Metricas e Monitoramento

### 7.1 Dashboard de Treinamento

```python
class TrainingDashboard:
    """Dashboard de metricas de treinamento."""
    
    def get_statistics(self) -> Dict:
        return {
            'total_samples': {
                'forward': self.count_samples('FORWARD'),
                'reverse': self.count_samples('REVERSE'),
                'total': self.count_samples()
            },
            'by_element_type': {
                'PILAR': self.count_by_type('PILAR'),
                'VIGA': self.count_by_type('VIGA'),
                'LAJE': self.count_by_type('LAJE')
            },
            'validation_status': {
                'validated': self.count_by_status('VALIDATED'),
                'pending': self.count_by_status('PENDING'),
                'invalidated': self.count_by_status('INVALIDATED')
            },
            'prediction_accuracy': {
                'overall': self.calculate_accuracy(),
                'by_type': {
                    'PILAR': self.calculate_accuracy('PILAR'),
                    'VIGA': self.calculate_accuracy('VIGA'),
                    'LAJE': self.calculate_accuracy('LAJE')
                }
            }
        }
```

---

## 8. Proximos Passos de Implementacao

| Prioridade | Tarefa | Complexidade |
|------------|--------|--------------|
| 1 | Implementar ReverseParser | Media |
| 2 | Implementar PatternMatcher | Alta |
| 3 | Implementar DataExtractor | Media |
| 4 | Criar botao export nos robos | Baixa |
| 5 | Criar BatchUploadDialog | Media |
| 6 | Implementar BidirectionalTrainer | Alta |
| 7 | Criar TrainingDashboard | Media |
