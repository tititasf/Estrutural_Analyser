# CLI Reference - CAD-ANALYZER v3.0

## Referência Completa de Linha de Comando

Este documento cobre todos os comandos, opções e casos de uso do CAD-ANALYZER.

---

## 📋 Índice

1. [Comandos Principais](#comandos-principais)
2. [Fase 1 - Ingestão](#fase-1---ingestao)
3. [Fase 2 - Triagem](#fase-2---triagem)
4. [Fase 3 - Interpretação](#fase-3---interpretacao)
5. [Fase 4 - Transformação](#fase-4---transformacao)
6. [Pipeline Orchestrator](#pipeline-orchestrator)
7. [Testes](#testes)
8. [Utilitários](#utilitarios)
9. [Casos de Uso](#casos-de-uso)

---

## Comandos Principais

### Executar Pipeline Completo

```bash
python -m src.orchestrator.pipeline_orchestrator [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--obra <path>` | Diretório da obra | Obrigatório |
| `--obra-id <id>` | Identificador da obra | Nome do diretório |
| `--db <path>` | Caminho do SQLite | `project_data.vision` |
| `--run-pipeline` | Executar todas as fases | `False` |
| `--fase <n>` | Executar apenas fase N | Todas |
| `--resume` | Retomar de onde parou | `False` |
| `--verbose` | Logs detalhados | `False` |

**Exemplos:**

```bash
# Pipeline completo
python -m src.orchestrator.pipeline_orchestrator --obra D:/obras/obra21 --run-pipeline

# Apenas Fase 1
python -m src.orchestrator.pipeline_orchestrator --obra D:/obras/obra21 --fase 1

# Retomar pipeline interrompido
python -m src.orchestrator.pipeline_orchestrator --obra D:/obras/obra21 --resume
```

---

## Fase 1 - Ingestão

### Comando

```bash
python -m src.phases.fase1_ingestao [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--obra <path>` | Diretório da obra | Obrigatório |
| `--obra-id <id>` | Identificador da obra | Auto |
| `--db <path>` | SQLite database | `project_data.vision` |
| `--workers <n>` | Número de workers | CPU cores (max 8) |
| `--no-cache` | Desabilitar cache | `False` |
| `--batch-size <n>` | Tamanho do batch | 50 |
| `--verbose` | Logs detalhados | `False` |

**Exemplos:**

```bash
# Ingestão padrão
python -m src.phases.fase1_ingestao --obra D:/obras/obra21 --obra-id OBRA21

# Com cache desabilitado
python -m src.phases.fase1_ingestao --obra D:/obras/obra21 --no-cache

# Performance máxima (8 workers)
python -m src.phases.fase1_ingestao --obra D:/obras/obra21 --workers 8
```

### Script Python

```python
from src.phases.fase1_ingestao import Fase1Ingestao

ingestao = Fase1Ingestao(
    obra_dir="D:/obras/obra21",
    db_path="project_data.vision",
    usar_cache=True,
    num_workers=4
)

resultado = ingestao.executar(obra_id="OBRA21")
print(f"Arquivos: {resultado.arquivos_processados}")
print(f"Entidades: {resultado.entidades_extraidas}")
print(f"Tempo: {resultado.tempo_total_seg:.2f}s")

ingestao.close()
```

### Output

```
2026-03-06 10:30:15 - INFO - [OBRA21] Iniciando Fase 1 - Ingestao (OTIMIZADA - 4 workers)
2026-03-06 10:30:16 - INFO - Encontrados: 15 DXFs, 5 PDFs, 10 imagens
2026-03-06 10:30:25 - INFO - Processamento paralelo DXF: 15 arquivos em 12.34s
2026-03-06 10:30:30 - INFO - [OBRA21] Fase 1 completada: 30 arquivos, 5420 entidades em 15.67s
```

---

## Fase 2 - Triagem

### Comando

```bash
python -m src.phases.fase2_triagem [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--obra-id <id>` | Identificador da obra | Obrigatório |
| `--db <path>` | SQLite database | `project_data.vision` |
| `--separate-pavimentos` | Separar pavimentos | `True` |
| `--clean-layers` | Filtrar layers | `True` |
| `--verbose` | Logs detalhados | `False` |

**Exemplos:**

```bash
# Triagem completa
python -m src.phases.fase2_triagem --obra-id OBRA21

# Apenas separação de pavimentos
python -m src.phases.fase2_triagem --obra-id OBRA21 --separate-pavimentos
```

### Script Python

```python
from src.phases.fase2_triagem import Fase2Triagem

triagem = Fase2Triagem(
    obra_id="OBRA21",
    db_path="project_data.vision"
)

resultado = triagem.executar()
print(f"Pavimentos: {resultado.pavimentos_encontrados}")
print(f"Detalhes: {resultado.detalhes_separados}")

triagem.close()
```

---

## Fase 3 - Interpretação

### Comando

```bash
python -m src.phases.fase3_interpretacao [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--obra-id <id>` | Identificador da obra | Obrigatório |
| `--db <path>` | SQLite database | `project_data.vision` |
| `--confidence <0-1>` | Threshold de confiança | 0.7 |
| `--review-mode` | Modo revisão humana | `False` |
| `--auto-approve` | Aprovar automaticamente | `False` |
| `--verbose` | Logs detalhados | `False` |

**Exemplos:**

```bash
# Interpretação automática
python -m src.phases.fase3_interpretacao --obra-id OBRA21 --auto-approve

# Modo revisão (campos < 0.7 confiança)
python -m src.phases.fase3_interpretacao --obra-id OBRA21 --confidence 0.7 --review-mode
```

### Script Python

```python
from src.phases.fase3_interpretacao import Fase3Interpretacao
from src.phases.fase3_revisor import Fase3Revisor

# Interpretação
interpretacao = Fase3Interpretacao(
    obra_id="OBRA21",
    db_path="project_data.vision",
    confidence_threshold=0.7
)

fichas = interpretacao.executar()
print(f"Pilares: {len(fichas.pilares)}")
print(f"Vigas: {len(fichas.vigas)}")
print(f"Lajes: {len(fichas.lajes)}")

# Revisão humana (se necessário)
revisor = Fase3Revisor(db_path="project_data.vision")
revisor.revisar_fichas(obra_id="OBRA21", confidence_threshold=0.7)

interpretacao.close()
```

---

## Fase 4 - Transformação

### Comando

```bash
python -m src.pipeline.transformation_engine [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--db <path>` | SQLite database | `project_data.vision` |
| `--derive` | Derivar regras | `False` |
| `--persist` | Persistir regras | `False` |
| `--load` | Carregar regras | `False` |
| `--test` | Testar regras | `False` |
| `--min-events <n>` | Mínimo de eventos | 10 |
| `--verbose` | Logs detalhados | `False` |

**Exemplos:**

```bash
# Derivar e persistir regras
python -m src.pipeline.transformation_engine --db project_data.vision --derive --persist

# Carregar regras existentes
python -m src.pipeline.transformation_engine --db project_data.vision --load

# Testar aplicação de regras
python -m src.pipeline.transformation_engine --db project_data.vision --load --test
```

### Script Python

```python
from src.pipeline.transformation_engine import TransformationEngine

engine = TransformationEngine(db_path="project_data.vision")

# 1. Carregar eventos de treinamento
event_count = engine.load_training_events()
print(f"Eventos carregados: {event_count}")

# 2. Derivar regras
rules = engine.derive_rules()
print(f"Regras derivadas: {len(rules)}")

# 3. Estatísticas
stats = engine.get_rule_stats()
print(f"Coverage médio: {stats['avg_coverage_pct']:.2f}%")
print(f"Accuracy médio: {stats['avg_accuracy_pct']:.2f}%")

# 4. Persistir regras
persisted = engine.persist_rules(min_coverage=50.0)
print(f"Regras persistidas: {persisted}")

# 5. Aplicar regra
predicted = engine.apply_rule("Pilar_name", dna_vector)
print(f"Predição: {predicted}")

engine.close()
```

### Output

```
======================================================================
TRANSFORMATION ENGINE - CAD-ANALYZER
======================================================================

[1] Carregando training_events...
    -> 542 eventos carregados

[2] Derivando regras...
    -> 15 regras derivadas

[3] Estatísticas das regras:
    -> Total regras: 15
    -> Coverage médio: 68.45%
    -> Accuracy médio: 72.30%
    -> Regras por entidade: {'Pilar': 5, 'Viga': 5, 'Laje': 5}

[4] Top 10 regras por coverage:
     1. Pilar_name                         coverage=85.20%  accuracy=78.50%
     2. Viga_lateral_outline               coverage=78.30%  accuracy=75.20%
     3. Laje_name                          coverage=72.10%  accuracy=70.80%
     ...

[5] Persistindo regras...
    -> 12 regras persistidas

======================================================================
EXECUÇÃO CONCLUÍDA
======================================================================
```

---

## Pipeline Orchestrator

### Comando

```bash
python -m src.orchestrator.pipeline_orchestrator [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--obra <path>` | Diretório da obra | Obrigatório |
| `--obra-id <id>` | Identificador da obra | Auto |
| `--db <path>` | SQLite database | `project_data.vision` |
| `--run-pipeline` | Executar todas as fases | `False` |
| `--fase <1-7>` | Executar apenas fase N | Todas |
| `--resume` | Retomar de onde parou | `False` |
| `--dry-run` | Simular execução | `False` |
| `--verbose` | Logs detalhados | `False` |

**Exemplos:**

```bash
# Pipeline completo
python -m src.orchestrator.pipeline_orchestrator --obra D:/obras/obra21 --run-pipeline

# Apenas Fase 3
python -m src.orchestrator.pipeline_orchestrator --obra D:/obras/obra21 --fase 3

# Retomar pipeline
python -m src.orchestrator.pipeline_orchestrator --obra D:/obras/obra21 --resume
```

### Script Python

```python
from src.orchestrator.pipeline_orchestrator import PipelineOrchestrator

orchestrator = PipelineOrchestrator(
    obra_dir="D:/obras/obra21",
    obra_id="OBRA21",
    db_path="project_data.vision"
)

# Executar todas as fases
orchestrator.executar_todas_fases()

# Ou executar fase específica
orchestrator.executar_fase(3)

# Verificar estado
estado = orchestrator.get_estado()
print(f"Fase atual: {estado['fase_atual']}")
print(f"Fases completas: {estado['fases_completas']}")

orchestrator.close()
```

---

## Testes

### Suite Completa

```bash
# Todos os testes
pytest tests/ -v --cov=src

# Com coverage report
pytest tests/ -v --cov=src --cov-report=html

# Abrir coverage report
start htmlcov/index.html  # Windows
```

### Testes por Módulo

```bash
# Fase 1 e 2
pytest tests/test_fases_1_2.py -v

# Fase 3 - Interpretação
pytest tests/test_fase3_interpretacao.py -v

# Fase 4 - Transformação
pytest tests/test_transformation_engine.py -v

# Pipeline E2E
pytest tests/test_pipeline_e2e.py -v

# Orchestrator
pytest tests/test_pipeline_orchestrator.py -v
```

### Opções pytest

| Opção | Descrição |
|-------|-----------|
| `-v` | Verbose output |
| `--cov=src` | Coverage report |
| `--cov-report=html` | HTML coverage |
| `-k <pattern>` | Filtrar por nome |
| `-x` | Parar no primeiro erro |
| `--tb=short` | Traceback curto |

**Exemplos:**

```bash
# Apenas testes de transformação
pytest tests/ -k transformation -v

# Parar no primeiro erro
pytest tests/test_pipeline_e2e.py -x -v

# Coverage apenas do módulo phases
pytest tests/ --cov=src/phases -v
```

---

## Utilitários

### Verificar Status do Cache

```bash
python -c "from src.core.cache import DXFCache; c = DXFCache('project_data.vision'); print(c.get_stats())"
```

### Limpar Cache

```bash
python -c "from src.core.cache import DXFCache; c = DXFCache('project_data.vision'); c.clear(); c.close()"
```

### Listar Obras Processadas

```bash
python -c "import sqlite3; c = sqlite3.connect('project_data.vision'); print([r[0] for r in c.execute('SELECT id FROM obras')])"
```

### Exportar Resultados

```python
import json
import sqlite3

conn = sqlite3.connect('project_data.vision')
cursor = conn.cursor()

# Exportar fichas
cursor.execute("SELECT * FROM fase3_fichas WHERE obra_id = ?", ("OBRA21",))
fichas = cursor.fetchall()

with open('fichas_export.json', 'w') as f:
    json.dump(fichas, f, indent=2)

conn.close()
```

---

## Casos de Uso

### Caso 1: Processar Obra Nova

```bash
# 1. Ingestão
python -m src.phases.fase1_ingestao --obra D:/obras/obra_nova --obra-id OBRA_NOVA

# 2. Triagem
python -m src.phases.fase2_triagem --obra-id OBRA_NOVA

# 3. Interpretação (com revisão)
python -m src.phases.fase3_interpretacao --obra-id OBRA_NOVA --review-mode

# 4. Transformação
python -m src.pipeline.transformation_engine --db project_data.vision --derive --persist

# 5. Pipeline completo (Fases 5-7)
python -m src.orchestrator.pipeline_orchestrator --obra D:/obras/obra_nova --fase 5 --run-pipeline
```

### Caso 2: Re-processar com Cache

```bash
# Re-processar usando cache existente
python -m src.phases.fase1_ingestao --obra D:/obras/obra_nova --obra-id OBRA_NOVA --no-cache
```

### Caso 3: Pipeline em Lote

```bash
# Processar múltiplas obras
for obra in D:/obras/*; do
    python -m src.orchestrator.pipeline_orchestrator --obra $obra --run-pipeline
done
```

### Caso 4: Apenas Validação

```bash
# Validar DXFs gerados
python -m src.phases.fase7_qualidade --obra-id OBRA21 --validate-only
```

### Caso 5: Treinar Modelo

```bash
# 1. Coletar correções humanas
# (via interface de revisão)

# 2. Derivar novas regras
python -m src.pipeline.transformation_engine --db project_data.vision --derive --persist --min-events 50

# 3. Testar novas regras
python -m src.pipeline.transformation_engine --db project_data.vision --load --test
```

---

## Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `CAD_ANALYZER_DB` | Caminho do SQLite | `project_data.vision` |
| `CAD_ANALYZER_WORKERS` | Número de workers | CPU cores |
| `CAD_ANALYZER_CACHE` | Habilitar cache | `true` |
| `CAD_ANALYZER_VERBOSE` | Logs detalhados | `false` |
| `TESSERACT_PATH` | Caminho do Tesseract | Auto |

**Exemplo:**

```bash
# Windows
set CAD_ANALYZER_DB=D:/dados/project_data.vision
set CAD_ANALYZER_WORKERS=4
set TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe

# Linux
export CAD_ANALYZER_DB=/home/user/dados/project_data.vision
export CAD_ANALYZER_WORKERS=4
```

---

## Scripts de Exemplo

### run_pipeline.py

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para executar pipeline completo de uma obra."""

import argparse
import logging
from src.phases.fase1_ingestao import Fase1Ingestao
from src.orchestrator.pipeline_orchestrator import PipelineOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Pipeline CAD-ANALYZER')
    parser.add_argument('--obra', required=True, help='Diretório da obra')
    parser.add_argument('--obra-id', help='ID da obra (opcional)')
    parser.add_argument('--db', default='project_data.vision', help='SQLite DB')
    parser.add_argument('--workers', type=int, default=4, help='Workers')
    args = parser.parse_args()

    obra_id = args.obra_id or args.obra.split('/')[-1]

    logger.info(f"Iniciando pipeline para {obra_id}")

    # Fase 1
    ingestao = Fase1Ingestao(
        obra_dir=args.obra,
        db_path=args.db,
        num_workers=args.workers
    )
    resultado = ingestao.executar(obra_id=obra_id)
    logger.info(f"Fase 1: {resultado.arquivos_processados} arquivos")
    ingestao.close()

    # Pipeline completo
    orchestrator = PipelineOrchestrator(
        obra_dir=args.obra,
        obra_id=obra_id,
        db_path=args.db
    )
    orchestrator.executar_todas_fases()
    orchestrator.close()

    logger.info(f"Pipeline completo para {obra_id}")

if __name__ == '__main__':
    main()
```

**Uso:**

```bash
python run_pipeline.py --obra D:/obras/obra21 --workers 4
```

---

## 📞 Suporte

- **Documentação**: `/docs`
- **Issues**: GitHub Issues
- **Email**: suporte@corporacaosenciente.com

---

**Última atualização**: Março 2026 | **Versão**: 3.0.0
