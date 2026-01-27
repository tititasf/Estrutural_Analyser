# Documentacao Tecnica AgenteCAD / Estrutural Analyzer

## Indice de Documentacao Profissional

Este diretorio contem toda a documentacao tecnica do sistema AgenteCAD.

### Documentos Principais

| Documento | Descricao | Status |
|-----------|-----------|--------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Arquitetura geral do sistema | Criado |
| [DATA_FLOW.md](./DATA_FLOW.md) | Fluxo de dados completo | Criado |
| [VECTOR_SCHEMA.md](./VECTOR_SCHEMA.md) | Schema JSON dos vetores semanticos | Criado |
| [API_REFERENCE.md](./API_REFERENCE.md) | Referencia de APIs internas | Criado |
| [ROBOS_GUIDE.md](./ROBOS_GUIDE.md) | Guia dos Robos especializados | Criado |
| [ML_PIPELINE.md](./ML_PIPELINE.md) | Pipeline de Machine Learning | Criado |
| [REVERSE_ENGINEERING.md](./REVERSE_ENGINEERING.md) | Sistema de Engenharia Reversa | Criado |
| [DEVELOPER_ONBOARDING.md](./DEVELOPER_ONBOARDING.md) | Guia de Onboarding | Criado |

### Estrutura do Projeto

```
AgenteCAD/
├── main.py                     # Ponto de entrada principal
├── src/
│   ├── core/                   # Motores de processamento
│   │   ├── dxf_loader.py       # Carregamento de DXF
│   │   ├── spatial_index.py    # Indice espacial
│   │   ├── geometry_engine.py  # Motor geometrico
│   │   ├── text_associator.py  # Associador de textos
│   │   ├── slab_tracer.py      # Tracador de lajes
│   │   ├── beam_walker.py      # Analisador de vigas
│   │   ├── pillar_analyzer.py  # Analisador de pilares
│   │   ├── context_engine.py   # Motor de contexto
│   │   ├── memory.py           # Sistema de memoria hierarquica
│   │   ├── memory_system.py    # Sistema multinivel
│   │   ├── agent_identity.py   # Identidade agentica
│   │   └── database.py         # Gerenciador de banco
│   ├── ai/
│   │   ├── multimodal_processor.py  # Processador multimodal
│   │   ├── memory_store.py     # Armazenamento de memoria
│   │   └── vision_client.py    # Cliente de visao
│   └── ui/                     # Interface grafica
├── _ROBOS_ABAS/               # Robos especializados
│   ├── Robo_Lajes/            # Processamento de lajes
│   ├── Robo_Pilares/          # Processamento de pilares
│   ├── Robo_Laterais_de_Vigas/ # Laterais de vigas
│   └── Robo_Fundos_de_Vigas/  # Fundos de vigas
└── docs/                      # Documentacao tecnica
```

### Versao Atual

- **Versao**: 1.0.1
- **Python**: 3.12+
- **Framework UI**: PySide6
- **Backend**: Supabase
- **Vector DB**: ChromaDB
