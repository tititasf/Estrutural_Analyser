# CAD-ANALYZER v3.0

## Sistema de Análise e Processamento de Projetos Estruturais

[![Version](https://img.shields.io/badge/version-3.0.0-blue)](https://github.com)
[![Python](https://img.shields.io/badge/python-3.8+-green)](https://python.org)
[![License](https://img.shields.io/badge/license-proprietary-red)](https://github.com)

---

## 📋 Visão Geral

**CAD-ANALYZER** é um sistema automatizado de processamento de projetos estruturais que transforma pastas de obras brutas (DXFs, PDFs, fotos) em DXFs de entrega prontos para engenharia.

### Pipeline End-to-End

```
OBRA (pasta DXFs/PDFs/fotos)
        │
        ▼
[FASE 1] Ingestão e Vetorização ────────┐
        │                                │
        ▼                                │
[FASE 2] Limpeza e Separação             │
        │                                │
        ▼                                │
[FASE 3] Interpretação Semântica ◄───────┤ Machine Learning
        │                                │
        ▼                                │
[FASE 4] Transformação (Robo Integration)│
        │                                │
        ▼                                │
[FASE 5] Geração DXF por Item            │
        │                                │
        ▼                                │
[FASE 6] Unificação DXF em Produtos      │
        │                                │
        ▼                                │
[FASE 7] Revisão de Qualidade ───────────┘
        │
        ▼
DXFs FINAIS: Pilares | Vigas Laterais | Vigas Fundos | Garfos | Lajes
```

### Principais Recursos

- ✅ **Processamento Paralelo**: Múltiplos DXFs processados simultaneamente
- ✅ **Cache Inteligente**: Evita reprocessamento de arquivos já analisados
- ✅ **7 Fases Automatizadas**: Pipeline completo de ingestão à entrega
- ✅ **Machine Learning**: Interpretação semântica que melhora com uso
- ✅ **Robôs Especializados**: Pilares, Vigas e Lajes como serviços independentes
- ✅ **Qualidade Garantida**: Validação geométrica e revisão humana assistida

---

## 🚀 Quick Start

### Instalação Rápida

```bash
# Clone o repositório
git clone https://github.com/seu-org/cad-analyzer.git
cd cad-analyzer

# Crie ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Instale dependências
pip install -r requirements-phases.txt

# Instale Tesseract OCR (Windows)
# Baixe em: https://github.com/UB-Mannheim/tesseract/wiki
```

### Primeiro Pipeline (5 minutos)

```python
from src.phases.fase1_ingestao import Fase1Ingestao

# 1. Ingestão de obra bruta
ingestao = Fase1Ingestao(
    obra_dir="D:/obras/exemplo",
    db_path="project_data.vision",
    usar_cache=True,
    num_workers=4
)

resultado = ingestao.executar(obra_id="OBRA_001")
print(f"Processados: {resultado.arquivos_processados} arquivos")
print(f"Entidades: {resultado.entidades_extraidas}")
ingestao.close()
```

### Exemplo Completo

```python
from src.pipeline.transformation_engine import TransformationEngine

# 2. Transformação para formato dos robôs
engine = TransformationEngine(db_path="project_data.vision")
engine.load_training_events()
engine.derive_rules()
engine.persist_rules()

# Aplicar regra de transformação
ficha_transformada = engine.apply_rule("Pilar_name", dna_vector)
```

---

## 📁 Estrutura de Pastas

```
Agente-cad-PYSIDE/
├── src/
│   ├── phases/                 # Pipeline de 7 fases
│   │   ├── fase1_ingestao.py   # Ingestão DXF/PDF/foto
│   │   ├── fase2_triagem.py    # Limpeza e separação
│   │   ├── fase3_interpretacao.py  # Interpretação semântica
│   │   └── fase3_revisor.py    # Revisão humana assistida
│   │
│   ├── pipeline/               # Engines de transformação
│   │   ├── transformation_engine.py  # ML para regras
│   │   ├── ficha_pilares_schema.py   # Schemas de ficha
│   │   ├── ficha_vigas_schema.py
│   │   └── ficha_lajes_schema.py
│   │
│   ├── orchestrator/           # Orquestração do pipeline
│   │   └── pipeline_orchestrator.py
│   │
│   └── adapters/               # Adaptadores Fase 3→4
│   │   ├── fase3_to_fase4_pilares.py
│   │   ├── fase3_to_fase4_vigas.py
│   │   └── fase3_to_fase4_lajes.py
│
├── _ROBOS_ABAS/                # Robôs geradores DXF
│   ├── Robo_Pilares/           # Gera DXF de pilares
│   ├── Robo_Laterais_de_Vigas/ # Vigas laterais
│   ├── Robo_Fundos_de_Vigas/   # Vigas fundo
│   └── Robo_Lajes/             # Lajes
│
├── tests/                      # Suite de testes
│   ├── test_fase1_2.py         # Testes Fases 1-2
│   ├── test_fase3_interpretacao.py
│   ├── test_fase4_adapter.py
│   ├── test_transformation_engine.py
│   └── test_pipeline_e2e.py    # Teste end-to-end
│
├── docs/                       # Documentação
│   ├── GETTING_STARTED.md
│   ├── CLI_REFERENCE.md
│   └── PERFORMANCE_BENCHMARK.md
│
├── data/obras/                 # Runtime (gitignored)
│   └── {obra_id}/
│       ├── fase1/
│       ├── fase2/
│       ├── fase3/
│       ├── fase4/
│       ├── fase5/
│       ├── fase6/
│       └── ENTREGA/
│
├── requirements-phases.txt     # Dependências Python
├── project_data.vision         # SQLite database
└── README.md                   # Este arquivo
```

---

## 📚 Documentação Completa

| Documento | Descrição |
|-----------|-----------|
| [Getting Started](docs/GETTING_STARTED.md) | Setup passo-a-passo, primeiro pipeline |
| [CLI Reference](docs/CLI_REFERENCE.md) | Todos os comandos e opções |
| [Release Notes v3.0](RELEASE_NOTES_v3.0.md) | Changelog, breaking changes |
| [Performance Benchmark](docs/PERFORMANCE_BENCHMARK.md) | Métricas de performance |

---

## 🔧 Comandos Principais

### Pipeline Completo

```bash
# Executar pipeline completo de uma obra
python -m src.orchestrator.pipeline_orchestrator --obra D:/obras/exemplo --run-pipeline

# Executar fase específica
python -m src.phases.fase1_ingestao --obra D:/obras/exemplo --obra-id OBRA_001

# Derivar regras de transformação
python -m src.pipeline.transformation_engine --derive --persist
```

### Testes

```bash
# Suite completa de testes
pytest tests/ -v --cov=src

# Teste end-to-end
pytest tests/test_pipeline_e2e.py -v

# Teste de transformação
pytest tests/test_transformation_engine.py -v
```

---

## 🏗️ Arquitetura

### Componentes Principais

| Componente | Responsabilidade |
|------------|-----------------|
| **Fase1Ingestao** | Processa DXFs/PDFs/fotos em paralelo |
| **TransformationEngine** | Deriva regras de transformação via ML |
| **PipelineOrchestrator** | Coordena execução das 7 fases |
| **Robo_Pilares** | Gera DXF de pilares a partir de ficha |
| **Robo_Laterais/Vigas** | Gera DXF de vigas |
| **Robo_Lajes** | Gera DXF de lajes |

### Banco de Dados (SQLite)

```sql
-- Tabelas principais
CREATE TABLE obras (...);              -- Obras processadas
CREATE TABLE dxf_entidades (...);      -- Entidades extraídas
CREATE TABLE fase3_fichas (...);       -- Fichas estruturais
CREATE TABLE transformation_rules (...); -- Regras de transformação
CREATE TABLE training_events (...);    -- Eventos de treinamento ML
```

---

## 📊 Métricas de Qualidade

| Métrica | Valor Atual | Meta |
|---------|-------------|------|
| Score Interpretação (Fase 3) | 70-75% | ≥90% |
| Score Transformação (Fase 4) | 70.05% | ≥75% |
| Taxa Sucesso E2E | 95% | ≥98% |
| Tempo Processamento (obra média) | <30 min | <20 min |
| Cobertura de Testes | 60% | ≥80% |

---

## 🤝 Contribuindo

1. Fork o repositório
2. Crie branch para feature (`git checkout -b feature/nova-feature`)
3. Commit mudanças (`git commit -m 'Adiciona nova feature'`)
4. Push para branch (`git push origin feature/nova-feature`)
5. Abra Pull Request

---

## 📝 Licença

Proprietário - Todos os direitos reservados.

---

## 👥 Contributors

- Diana Corporação Senciente
- CEO-PLANEJAMENTO (Athena)
- CAD-ANALYZER Squad

---

## 📞 Suporte

- **Documentação**: `/docs`
- **Issues**: GitHub Issues
- **Email**: suporte@corporacaosenciente.com

---

**Última atualização**: Março 2026 | **Versão**: 3.0.0
