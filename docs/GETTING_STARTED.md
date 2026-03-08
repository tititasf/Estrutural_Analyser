# Getting Started - CAD-ANALYZER v3.0

## Guia de Primeiros Passos

Este guia cobre tudo que você precisa para começar a usar o CAD-ANALYZER, desde a instalação até o primeiro pipeline completo.

---

## 📋 Pré-requisitos

### Sistema Operacional
- ✅ Windows 10/11 (64-bit)
- ✅ Linux Ubuntu 20.04+ (suporte parcial)
- ⚠️ macOS (não testado)

### Hardware Mínimo
| Componente | Mínimo | Recomendado |
|------------|--------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16+ GB |
| Storage | 10 GB livres | 50+ GB SSD |
| GPU | Integrada | Dedicada (para OCR) |

### Software Requerido

#### 1. Python 3.8+
```bash
# Verificar versão
python --version

# Baixar em: https://www.python.org/downloads/
# Marque: "Add Python to PATH" durante instalação
```

#### 2. Tesseract OCR (Windows)
```bash
# 1. Baixe instalador em:
# https://github.com/UB-Mannheim/tesseract/wiki

# 2. Instale em: C:\Program Files\Tesseract-OCR

# 3. Durante instalação, marque:
#    - Portuguese (Brazil) language data
#    - English language data

# 4. Verifique instalação
tesseract --version
```

#### 3. Git (opcional)
```bash
# Baixe em: https://git-scm.com/download/win
git --version
```

---

## 🚀 Instalação Passo-a-Passo

### Passo 1: Clonar/Download do Projeto

```bash
# Opção A: Git clone
cd D:\
git clone https://github.com/seu-org/cad-analyzer.git Agente-cad-PYSIDE
cd Agente-cad-PYSIDE

# Opção B: Download ZIP
# Baixe e extraia em D:\Agente-cad-PYSIDE
```

### Passo 2: Criar Ambiente Virtual

```bash
# Navegue até o diretório
cd D:\Agente-cad-PYSIDE

# Crie ambiente virtual
python -m venv venv

# Ative o ambiente
# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate

# Verifique ativação (deve mostrar "venv" no prompt)
```

### Passo 3: Instalar Dependências

```bash
# Instale todas as dependências
pip install -r requirements-phases.txt

# Verifique instalações
pip list

# Dependências instaladas:
# - ezdxf>=1.1.0          (leitura DXF)
# - pdfminer.six>=20221105 (extração PDF)
# - opencv-python>=4.8.0  (processamento imagens)
# - pytesseract>=0.3.10   (OCR)
# - numpy>=1.24.0         (suporte OpenCV)
# - rtree>=1.0.0          (índice espacial)
# - pytest>=7.4.0         (testes)
```

### Passo 4: Configurar Tesseract no Código

Edite o arquivo `src/phases/fase1_ingestao.py` se necessário:

```python
# Adicione no início do arquivo, após imports:
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

### Passo 5: Verificar Instalação

```bash
# Execute testes básicos
pytest tests/test_transformation_engine.py -v

# Verifique módulos principais
python -c "from src.phases.fase1_ingestao import Fase1Ingestao; print('OK')"
```

---

## 🎯 Primeiro Pipeline Completo

### Cenário: Processar Obra de Exemplo

Vamos processar uma pasta de obra com DXFs estruturais.

#### Preparação dos Dados

```bash
# 1. Crie pasta de exemplo
mkdir D:\obras\exemplo_001

# 2. Copie DXFs para pasta
# Copie arquivos .dxf para D:\obras\exemplo_001\

# Estrutura esperada:
# D:\obras\exemplo_001\
#   ├── pavimento_terreo.dxf
#   ├── pavimento_1.dxf
#   ├── memorial.pdf
#   └── foto_obra.jpg
```

#### Executando o Pipeline

**Opção 1: Script Python**

```python
# Crie arquivo: run_pipeline.py
from src.phases.fase1_ingestao import Fase1Ingestao
from src.orchestrator.pipeline_orchestrator import PipelineOrchestrator

# 1. Ingestão (Fase 1)
print("=" * 60)
print("FASE 1 - INGESTÃO")
print("=" * 60)

ingestao = Fase1Ingestao(
    obra_dir="D:/obras/exemplo_001",
    db_path="project_data.vision",
    usar_cache=True,
    num_workers=4
)

resultado = ingestao.executar(obra_id="EXEMPLO_001")
print(f"Arquivos processados: {resultado.arquivos_processados}")
print(f"DXFs: {resultado.dxf_ingestados}")
print(f"PDFs: {resultado.pdf_ingestados}")
print(f"Fotos: {resultado.fotos_ingestadas}")
print(f"Entidades: {resultado.entidades_extraidas}")
print(f"Tempo: {resultado.tempo_total_seg:.2f}s")
ingestao.close()

# 2. Pipeline completo (Fases 1-7)
print("\n" + "=" * 60)
print("PIPELINE COMPLETO")
print("=" * 60)

orchestrator = PipelineOrchestrator(
    obra_dir="D:/obras/exemplo_001",
    obra_id="EXEMPLO_001",
    db_path="project_data.vision"
)

orchestrator.executar_todas_fases()
```

**Opção 2: Linha de Comando**

```bash
# Executar apenas Fase 1
python -m src.phases.fase1_ingestao --obra D:/obras/exemplo_001 --obra-id EXEMPLO_001

# Executar pipeline completo
python -m src.orchestrator.pipeline_orchestrator --obra D:/obras/exemplo_001 --obra-id EXEMPLO_001 --run-pipeline

# Derivar regras de transformação
python -m src.pipeline.transformation_engine --db project_data.vision --derive --persist
```

#### Verificando Resultados

```bash
# Resultados são salvos em:
# data/obras/EXEMPLO_001/

# Estrutura de output:
data/obras/EXEMPLO_001/
├── fase1/
│   ├── catalogo.json         # Inventário de arquivos
│   ├── dxf_entities.json     # Entidades extraídas
│   └── vetores_fase1.json    # Vetores ChromaDB
├── fase2/
│   └── pavimentos/           # Pavimentos separados
├── fase3/
│   └── fichas/               # Fichas estruturais
├── fase4/
│   └── transformadas/        # Fichas transformadas
├── fase5/
│   └── dxfs/                 # DXFs individuais
├── fase6/
│   └── unificados/           # DXFs unificados
├── fase7/
│   └── relatorio.pdf         # Relatório de qualidade
└── ENTREGA/
    ├── EXEMPLO_001_PILARES.dxf
    ├── EXEMPLO_001_VIGAS_LATERAIS.dxf
    ├── EXEMPLO_001_VIGAS_FUNDOS.dxf
    ├── EXEMPLO_001_GARFOS.dxf
    └── EXEMPLO_001_LAJES.dxf
```

---

## 🔍 Troubleshooting Comum

### Problema: "ezdxf não instalado"

**Sintoma:**
```
ERROR - ezdxf nao instalado
```

**Solução:**
```bash
pip install ezdxf
# Ou reinstale tudo:
pip install -r requirements-phases.txt --force-reinstall
```

---

### Problema: "Tesseract não encontrado"

**Sintoma:**
```
TesseractNotFoundError: tesseract is not installed
```

**Solução:**
```python
# Adicione no início do seu script:
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Ou adicione ao PATH do Windows:
# 1. Painel de Controle → Sistema → Variáveis de Ambiente
# 2. Edite PATH
# 3. Adicione: C:\Program Files\Tesseract-OCR
```

---

### Problema: "SQLite locked"

**Sintoma:**
```
sqlite3.OperationalError: database is locked
```

**Solução:**
```bash
# Feche todos os processos usando o banco
# Delete arquivos de lock
del project_data.vision-shm
del project_data.vision-wal

# Ou use timeout maior no código:
conn = sqlite3.connect(db_path, timeout=60.0)
```

---

### Problema: "MemoryError" em DXFs grandes

**Sintoma:**
```
MemoryError: Unable to allocate X GB
```

**Solução:**
```python
# Reduza número de workers
ingestao = Fase1Ingestao(
    obra_dir=obra_dir,
    num_workers=2  # Em vez de 8
)

# Ou processe em batches
for dxf_file in dxf_files[::10]:  # De 10 em 10
    processar_dxf_individual(dxf_file)
```

---

### Problema: "Interpretação incorreta na Fase 3"

**Sintoma:**
```
Fichas geradas com campos errados
```

**Solução:**

1. **Ative revisão humana:**
```python
from src.phases.fase3_revisor import Fase3Revisor

revisor = Fase3Revisor(db_path="project_data.vision")
revisor.revisar_fichas(obra_id="EXEMPLO_001", confidence_threshold=0.7)
```

2. **Adicione mais dados de treinamento:**
```bash
# Cada correção humana alimenta o dataset
# Acumule mínimo 50 fichas corrigidas por tipo
```

3. **Derive novas regras:**
```bash
python -m src.pipeline.transformation_engine --derive --persist --min-events 50
```

---

### Problema: "DXF não abre no AutoCAD"

**Sintoma:**
```
Error reading DXF file
```

**Solução:**
```python
# Valide DXF gerado
from src.phases.fase7_qualidade import GeometricValidator

validator = GeometricValidator()
validator.validar_dxf("data/obras/EXEMPLO_001/ENTREGA/PILARES.dxf")
```

---

## 📊 Entendendo Outputs

### Log de Execução

```
2026-03-06 10:30:15 - INFO - [EXEMPLO_001] Iniciando Fase 1 - Ingestao (OTIMIZADA - 4 workers)
2026-03-06 10:30:16 - INFO - Encontrados: 5 DXFs, 2 PDFs, 3 imagens
2026-03-06 10:30:20 - INFO - Processamento paralelo DXF: 5 arquivos em 4.52s (1.1 arquivos/s)
2026-03-06 10:30:25 - INFO - [EXEMPLO_001] Fase 1 completada: 10 arquivos, 1250 entidades em 10.23s
2026-03-06 10:30:25 - INFO - [EXEMPLO_001] Cache: 0 hits, 5 misses
```

**Campos:**
- `workers`: Número de processos paralelos
- `arquivos`: Total processado
- `entidades`: Elementos extraídos (linhas, textos, etc.)
- `cache hits`: Arquivos reutilizados do cache
- `tempo`: Duração em segundos

### Resultado JSON

```json
{
  "obra_id": "EXEMPLO_001",
  "arquivos_processados": 10,
  "dxf_ingestados": 5,
  "pdf_ingestados": 2,
  "fotos_ingestadas": 3,
  "entidades_extraidas": 1250,
  "cache_hits": 0,
  "cache_misses": 5,
  "erros": [],
  "tempo_total_seg": 10.23
}
```

---

## 🎓 Próximos Passos

1. **Execute com seus dados:**
   - Substitua `D:/obras/exemplo_001` pela sua pasta de obra

2. **Explore a documentação:**
   - [CLI Reference](CLI_REFERENCE.md) - Todos os comandos
   - [Performance Benchmark](PERFORMANCE_BENCHMARK.md) - Otimizações

3. **Configure produção:**
   - Ajuste `num_workers` para seu hardware
   - Configure cache persistente
   - Setup de backups do SQLite

4. **Contribua:**
   - Reporte bugs
   - Sugira melhorias
   - Adicione testes

---

## 📞 Suporte

- **Issues**: GitHub Issues
- **Email**: suporte@corporacaosenciente.com
- **Docs**: `/docs`

---

**Última atualização**: Março 2026 | **Versão**: 3.0.0
