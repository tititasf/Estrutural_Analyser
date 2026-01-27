# AgenteCAD / Estrutural Analyzer

Sistema de analise estrutural inteligente com interpretacao semantica de DXFs e geracao automatizada de scripts de producao.

## Visao Geral

O AgenteCAD le arquivos DXF estruturais (projetos de engenharia), interpreta automaticamente os elementos (pilares, vigas, lajes) usando Machine Learning, e gera scripts de producao para AutoCAD.

```
DXF Estrutural → Interpretacao ML → Robos Especializados → Scripts SCR → DXF Produto
```

## Funcionalidades Principais

- **Interpretacao Inteligente**: ML treinado para reconhecer elementos estruturais
- **Robos Especializados**: Processadores para Lajes, Pilares, Vigas (Laterais/Fundos)
- **Memoria Hierarquica**: Sistema de aprendizado em 3 niveis
- **Engenharia Reversa**: Alimenta treinamento a partir de produtos finalizados

## Como Iniciar

### Usuario Final

1. Baixe `Estrutural_Analyzer_download_updater.exe` da pasta `dist/`
2. Execute o instalador - ele baixara a versao mais recente
3. O atalho sera criado na area de trabalho

### Desenvolvedor

```bash
# Clonar e instalar
git clone <repo-url>
cd Agente-cad-PYSIDE
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Executar
python main.py
```

## Stack Tecnologica

| Categoria | Tecnologia |
|-----------|------------|
| Linguagem | Python 3.12+ |
| UI Framework | PySide6 |
| Vector DB | ChromaDB |
| Database | SQLite |
| Cloud | Supabase |
| DXF Parser | ezdxf |
| ML | scikit-learn |

## Documentacao Tecnica

| Documento | Descricao |
|-----------|-----------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arquitetura geral do sistema |
| [docs/VECTOR_SCHEMA.md](docs/VECTOR_SCHEMA.md) | Schema JSON dos vetores semanticos |
| [docs/REVERSE_ENGINEERING.md](docs/REVERSE_ENGINEERING.md) | Sistema de engenharia reversa |
| [docs/ROBOS_GUIDE.md](docs/ROBOS_GUIDE.md) | Guia dos robos especializados |
| [docs/DEVELOPER_ONBOARDING.md](docs/DEVELOPER_ONBOARDING.md) | Guia de onboarding |
| [docs/MASTER_PLAN.md](docs/MASTER_PLAN.md) | Roadmap completo do projeto |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Manual de deploy e distribuicao |
| [MEMORY_SYSTEM_README.md](MEMORY_SYSTEM_README.md) | Sistema de memoria multinivel |

## Estrutura do Projeto

```
AgenteCAD/
├── main.py                 # Ponto de entrada
├── src/
│   ├── core/               # Motores de processamento
│   ├── ai/                 # Componentes de IA
│   └── ui/                 # Interface grafica
├── _ROBOS_ABAS/           # Robos especializados
│   ├── Robo_Lajes/
│   ├── Robo_Pilares/
│   ├── Robo_Laterais_de_Vigas/
│   └── Robo_Fundos_de_Vigas/
├── docs/                   # Documentacao tecnica
└── tests/                  # Testes automatizados
```

## Distribuicao e Update

Sistema de atualizacao baseado no TUFup (The Update Framework), customizado para downloads em partes no Supabase Storage.

## Licenca

Proprietario - Todos os direitos reservados.
