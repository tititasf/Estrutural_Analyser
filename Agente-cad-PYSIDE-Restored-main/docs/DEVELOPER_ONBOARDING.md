# Guia de Onboarding para Desenvolvedores

## Bem-vindo ao AgenteCAD!

Este guia te ajudara a entender rapidamente a arquitetura e comecar a contribuir.

---

## 1. Visao Geral Rapida

**O que e o AgenteCAD?**
- Sistema de analise estrutural inteligente
- Le DXFs de projetos estruturais (pilares, vigas, lajes)
- Gera automaticamente scripts de producao (SCR)
- Aprende com correcoes do usuario via ML

**Stack Tecnologica:**
```
Frontend: PySide6 (Qt for Python)
Backend: Python 3.12+
Database: SQLite + ChromaDB (vetores)
Cloud: Supabase + Byterover
ML: scikit-learn + sentence-transformers
CAD: ezdxf + Shapely
```

---

## 2. Setup do Ambiente

### 2.1 Pre-requisitos

```bash
# Python 3.12+
python --version  # Deve ser >= 3.12

# Git
git --version
```

### 2.2 Clonar e Instalar

```bash
# Clonar repositorio
git clone <repo-url>
cd Agente-cad-PYSIDE

# Criar ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt
```

### 2.3 Verificar Instalacao

```bash
# Rodar aplicacao principal
python main.py

# Rodar testes
python -m pytest tests/
```

---

## 3. Estrutura do Projeto

```
AgenteCAD/
├── main.py                 # Ponto de entrada - MainWindow
├── src/
│   ├── core/               # Motores de processamento
│   │   ├── dxf_loader.py   # Carrega arquivos DXF
│   │   ├── spatial_index.py# Indice R-Tree
│   │   ├── geometry_engine.py # Analise geometrica
│   │   ├── text_associator.py # Vincula textos
│   │   ├── slab_tracer.py  # Tracador de lajes
│   │   ├── beam_walker.py  # Analisador de vigas
│   │   ├── pillar_analyzer.py # Analisador de pilares
│   │   ├── memory.py       # Sistema de memoria
│   │   └── database.py     # SQLite manager
│   ├── ai/                 # Componentes de IA
│   │   ├── multimodal_processor.py
│   │   └── memory_store.py
│   └── ui/                 # Interface grafica
│       ├── canvas.py       # Canvas de desenho
│       ├── widgets/        # Widgets customizados
│       └── modules/        # Modulos da UI
├── _ROBOS_ABAS/            # Robos especializados
│   ├── Robo_Lajes/
│   ├── Robo_Pilares/
│   ├── Robo_Laterais_de_Vigas/
│   └── Robo_Fundos_de_Vigas/
├── docs/                   # Documentacao tecnica
└── tests/                  # Testes automatizados
```

---

## 4. Fluxo de Dados Basico

```
1. ENTRADA: Usuario carrega DXF estrutural
   ↓
2. PARSING: DXFLoader extrai entidades
   ↓
3. INDEXACAO: SpatialIndex cria R-Tree
   ↓
4. ANALISE: Engines identificam pilares/vigas/lajes
   ↓
5. ASSOCIACAO: TextAssociator vincula textos
   ↓
6. ROBOS: Usuario seleciona elemento → Robo processa
   ↓
7. SAIDA: Script SCR gerado para AutoCAD
```

---

## 5. Primeiras Contribuicoes

### 5.1 Corrigir Bug Simples

1. Encontre um issue marcado como `good first issue`
2. Crie branch: `git checkout -b fix/nome-do-bug`
3. Faca a correcao
4. Rode testes: `python -m pytest tests/`
5. Commit e push

### 5.2 Adicionar Feature

1. Leia a documentacao relevante em `docs/`
2. Discuta no issue antes de implementar
3. Siga o padrao de codigo existente
4. Adicione testes para a feature
5. Atualize documentacao se necessario

---

## 6. Padroes de Codigo

### 6.1 Estilo

```python
# Use type hints
def process_element(element: Dict[str, Any]) -> Optional[str]:
    pass

# Use docstrings
def calculate_area(vertices: List[Tuple[float, float]]) -> float:
    """
    Calcula area de poligono a partir de vertices.
    
    Args:
        vertices: Lista de tuplas (x, y)
        
    Returns:
        Area em unidades quadradas
    """
    pass

# Nomes em ingles para codigo
class PillarAnalyzer:  # NAO: AnalisadorPilares
    pass

# Constantes em UPPER_CASE
MAX_VERTICES = 1000
DEFAULT_TOLERANCE = 0.01
```

### 6.2 Commits

```bash
# Formato: tipo(escopo): descricao
feat(pillar): add face detection algorithm
fix(dxf-loader): handle empty layers
docs(readme): update installation steps
refactor(memory): optimize cache lookup
test(beam): add walker unit tests
```

---

## 7. Debug e Troubleshooting

### 7.1 Logs

```python
import logging
logger = logging.getLogger(__name__)

# Niveis de log
logger.debug("Detalhes tecnicos")
logger.info("Operacoes normais")
logger.warning("Algo inesperado")
logger.error("Erro recuperavel")
logger.critical("Erro fatal")
```

### 7.2 Problemas Comuns

**DXF nao carrega:**
```python
# Verificar formato
import ezdxf
doc = ezdxf.readfile("arquivo.dxf")
print(doc.dxfversion)  # Deve ser AC1027 ou superior
```

**Memoria alta:**
```python
# Limpar cache
spatial_index.clear()
memory.cleanup_expired()
```

**UI nao responde:**
```python
# Usar worker threads para operacoes longas
from PySide6.QtCore import QThread
```

---

## 8. Contatos e Recursos

### Documentacao Tecnica
- `docs/ARCHITECTURE.md` - Arquitetura geral
- `docs/VECTOR_SCHEMA.md` - Schema de dados
- `docs/MASTER_PLAN.md` - Roadmap completo
- `docs/GIT_DVC_GUIDE.md` - Workflow Git + DVC (branches, commits, dados)

### Memoria do Projeto
- Byterover: Consulte conhecimento acumulado
- ChromaDB local: Vetores de treinamento

---

## 9. Proximos Passos

1. **Ler:** `docs/ARCHITECTURE.md` para entender o sistema
2. **Explorar:** Rode a aplicacao e teste funcionalidades
3. **Contribuir:** Escolha um issue e comece!

Bem-vindo ao time! 🚀
