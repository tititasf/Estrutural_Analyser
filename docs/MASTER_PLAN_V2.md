# MASTER PLAN V2 - Sistema Operacional Cognitivo AgenteCAD

## Atomic Blueprint Architect - Antigravity

---

# VISAO GERAL DAS 5 ETAPAS

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ETAPA 1: DESENVOLVIMENTO DO SISTEMA E PREPARACAO PARA DADOS               │
│  Status: EM DESENVOLVIMENTO                                                 │
│  - Infraestrutura completa                                                 │
│  - Swarm Agents configurados                                               │
│  - Bancos vetoriais preparados                                             │
│  - Estrutura de pastas de dados                                            │
│  - CausalVectorEngine implementado                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ETAPA 2: TRATAMENTO DE DADOS E ALIMENTACAO DE VETORES                     │
│  Status: PENDENTE                                                          │
│  - Popular estruturais brutos                                              │
│  - Popular DXFs produtos                                                   │
│  - Popular JSONs dos robos                                                 │
│  - Popular SCRs de todas possibilidades                                    │
│  - Treinamento bidirecional                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ETAPA 3: VALIDACAO E UTILIZACAO BIDIRECIONAL                              │
│  Status: PENDENTE                                                          │
│  - Teste Forward: Estrutural → Produto                                     │
│  - Teste Reverse: Produto → Estrutural                                     │
│  - Validacao end-to-end                                                    │
│  - Metricas de acuracia                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ETAPA 4: TESTES SINTETICOS E AUTOEVOLUCAO                                 │
│  Status: PENDENTE                                                          │
│  - Geracao de dados sinteticos                                             │
│  - Treino de agentes especializados                                        │
│  - Metricas e dashboards                                                   │
│  - Loop de autoevolucao ate 95% acuracia                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ETAPA 5: VALIDACAO FINAL E USO EM PRODUCAO                                │
│  Status: PENDENTE                                                          │
│  - Validacao com dados reais                                               │
│  - Deploy para usuarios                                                    │
│  - Monitoramento continuo                                                  │
│  - Documentacao final                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# ARQUITETURA DO SISTEMA COGNITIVO

## 1. Swarm Agents

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SWARM ORCHESTRATOR                                  │
│                    (Coordenador Central - Claude/GPT)                       │
└─────────────────────────────────────────────────────────────────────────────┘
        │                    │                    │                    │
        ▼                    ▼                    ▼                    ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ PERCEPTION    │    │ INTERPRETER   │    │ VALIDATOR     │    │ GENERATOR     │
│ AGENT         │    │ AGENT         │    │ AGENT         │    │ AGENT         │
│ (LLaMA 4B)    │    │ (LLaMA 4B)    │    │ (LLaMA 4B)    │    │ (LLaMA 4B)    │
├───────────────┤    ├───────────────┤    ├───────────────┤    ├───────────────┤
│ - Le DXF      │    │ - Interpreta  │    │ - Valida      │    │ - Gera SCR    │
│ - Extrai      │    │ - Classifica  │    │ - Compara     │    │ - Gera DXF    │
│   geometria   │    │ - Associa     │    │ - Pontua      │    │ - Gera JSON   │
│ - Identifica  │    │   textos      │    │ - Aprova/     │    │ - Popula      │
│   elementos   │    │ - Contextua-  │    │   Rejeita     │    │   vetores     │
│               │    │   liza        │    │               │    │               │
└───────────────┘    └───────────────┘    └───────────────┘    └───────────────┘
        │                    │                    │                    │
        └────────────────────┴────────────────────┴────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │   CAUSAL VECTOR ENGINE    │
                    │   (Blockchain de          │
                    │    Pensamentos)           │
                    └───────────────────────────┘
```

## 2. CausalVectorEngine

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        VECTOR TRAJECTORY                                    │
│                                                                             │
│  [Percepcao] ──hash──▶ [Interpretacao] ──hash──▶ [Validacao] ──hash──▶ ... │
│      │                       │                        │                     │
│      ▼                       ▼                        ▼                     │
│  {vetor,                 {vetor,                  {vetor,                   │
│   metadata,              metadata,                metadata,                 │
│   timestamp,             timestamp,               timestamp,                │
│   prev_hash}             prev_hash}               prev_hash}                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 3. RAG Dialetico

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CHAIN OF DENSITY                                     │
│                                                                             │
│  ┌─────────┐        ┌─────────────┐        ┌─────────┐                     │
│  │  TESE   │───────▶│  ANTITESE   │───────▶│ SINTESE │                     │
│  │         │        │             │        │         │                     │
│  │ Query   │        │ Analisa     │        │ Combina │                     │
│  │ inicial │        │ lacunas     │        │ contextos│                    │
│  │ + Busca │        │ + Busca     │        │ + Resposta│                   │
│  │         │        │ corretiva   │        │ densa    │                    │
│  └─────────┘        └─────────────┘        └─────────┘                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# ESTRUTURA DE PASTAS DE DADOS

```
data/
├── raw/                              # DADOS BRUTOS (voce popula)
│   ├── estruturais/                  # DXFs estruturais brutos
│   │   ├── projeto_001/
│   │   │   ├── estrutural.dxf
│   │   │   └── metadata.json
│   │   └── ...
│   ├── produtos/                     # DXFs produtos finais
│   │   ├── pilares/
│   │   │   ├── grade_p1_face_a.dxf
│   │   │   └── ...
│   │   ├── vigas_laterais/
│   │   ├── vigas_fundos/
│   │   └── lajes/
│   ├── scripts/                      # SCRs gerados
│   │   ├── pilares/
│   │   ├── vigas_laterais/
│   │   ├── vigas_fundos/
│   │   └── lajes/
│   └── jsons/                        # JSONs dos robos
│       ├── pilares/
│       ├── vigas/
│       └── lajes/
│
├── processed/                        # DADOS PROCESSADOS (sistema gera)
│   ├── embeddings/
│   ├── features/
│   └── trajectories/
│
├── training/                         # DADOS DE TREINAMENTO
│   ├── forward/                      # Estrutural → Produto
│   ├── reverse/                      # Produto → Estrutural
│   └── synthetic/                    # Dados sinteticos
│
├── vectors/                          # BANCOS VETORIAIS
│   ├── chromadb/
│   ├── faiss/
│   └── causal/
│
└── models/                           # MODELOS TREINADOS
    ├── llama/
    ├── embeddings/
    └── classifiers/
```

---

# ETAPA 1 - BLUEPRINT DETALHADO

## Fase 1.1: Infraestrutura Base

### [TASK_1.1.1] - Criar Estrutura de Pastas de Dados

**Objetivo:** Criar toda arvore de diretorios para receber dados.

**Micro-Passos:**
1. Criar diretorio `data/` na raiz
2. Criar subdiretorios `raw/`, `processed/`, `training/`, `vectors/`, `models/`
3. Criar estrutura dentro de `raw/` para cada tipo de dado
4. Criar arquivos `.gitkeep` para preservar estrutura vazia
5. Criar `data/README.md` com instrucoes de populacao

**Definicao de Pronto:** Estrutura completa criada e documentada.

---

### [TASK_1.1.2] - Instalar Dependencias Core

**Objetivo:** Instalar todas bibliotecas necessarias.

**Micro-Passos:**
1. Atualizar `requirements.txt` com novas dependencias
2. Instalar ChromaDB, FAISS, sentence-transformers
3. Instalar Ollama para LLaMA local
4. Instalar MLflow e ZenML
5. Instalar Pydantic v2, numpy, scipy

**Definicao de Pronto:** Todas dependencias instaladas sem erros.

---

## Fase 1.2: CausalVectorEngine

### [TASK_1.2.1] - Implementar VectorTrajectory

**Objetivo:** Criar estrutura de blockchain de pensamentos.

**Micro-Passos:**
1. Criar `src/cognitive/vector_trajectory.py`
2. Implementar `TrajectoryNode` com hash encadeado
3. Implementar `VectorTrajectory` como cadeia de nodes
4. Criar metodos de append, validate, serialize
5. Criar testes unitarios

**Definicao de Pronto:** Trajetoria funcional com hashes validos.

---

### [TASK_1.2.2] - Implementar CausalVectorEngine

**Objetivo:** Criar motor de raciocinio com RAG dialetico.

**Micro-Passos:**
1. Criar `src/cognitive/causal_engine.py`
2. Implementar metodo `thesis()` - busca inicial
3. Implementar metodo `antithesis()` - busca corretiva
4. Implementar metodo `synthesis()` - combinacao
5. Implementar interface de debug

**Definicao de Pronto:** Engine funcional com debug trail.

---

## Fase 1.3: Swarm Agents

### [TASK_1.3.1] - Configurar Ollama com LLaMA

**Objetivo:** Instalar e configurar modelo local.

**Micro-Passos:**
1. Instalar Ollama CLI
2. Baixar modelo llama3.2:3b ou phi3:3.8b
3. Testar inferencia basica
4. Criar wrapper Python para Ollama
5. Validar performance

**Definicao de Pronto:** Modelo respondendo queries localmente.

---

### [TASK_1.3.2] - Implementar Agent Base

**Objetivo:** Criar classe base para todos os agentes.

**Micro-Passos:**
1. Criar `src/agents/base_agent.py`
2. Implementar interface comum (think, act, observe)
3. Implementar conexao com Ollama
4. Implementar logging de acoes
5. Criar sistema de tools

**Definicao de Pronto:** Agent base funcional.

---

### [TASK_1.3.3] - Implementar Agentes Especializados

**Objetivo:** Criar os 4 agentes do swarm.

**Micro-Passos:**
1. Criar `PerceptionAgent` - le DXF e extrai dados
2. Criar `InterpreterAgent` - classifica e associa
3. Criar `ValidatorAgent` - valida e pontua
4. Criar `GeneratorAgent` - gera outputs

**Definicao de Pronto:** 4 agentes funcionando isoladamente.

---

### [TASK_1.3.4] - Implementar Swarm Orchestrator

**Objetivo:** Coordenar comunicacao entre agentes.

**Micro-Passos:**
1. Criar `src/agents/swarm_orchestrator.py`
2. Implementar protocolo de mensagens
3. Implementar roteamento de tasks
4. Implementar agregacao de resultados
5. Testar conversacao entre agentes

**Definicao de Pronto:** Swarm executando task completa.

---

## Fase 1.4: Bancos Vetoriais

### [TASK_1.4.1] - Configurar ChromaDB

**Objetivo:** Preparar banco vetorial principal.

**Micro-Passos:**
1. Criar colecoes para cada tipo de elemento
2. Configurar embeddings
3. Criar indices
4. Implementar wrapper de acesso

**Definicao de Pronto:** ChromaDB operacional (vazio).

---

### [TASK_1.4.2] - Configurar FAISS

**Objetivo:** Preparar banco para busca rapida.

**Micro-Passos:**
1. Criar indices FAISS
2. Configurar dimensionalidade
3. Implementar wrapper
4. Testar performance

**Definicao de Pronto:** FAISS operacional (vazio).

---

## Fase 1.5: Pipeline MLOps

### [TASK_1.5.1] - Configurar MLflow

**Objetivo:** Setup de tracking de experimentos.

**Micro-Passos:**
1. Instalar MLflow
2. Configurar tracking server local
3. Criar experimentos base
4. Implementar logging de metricas

**Definicao de Pronto:** MLflow UI acessivel.

---

### [TASK_1.5.2] - Configurar ZenML

**Objetivo:** Setup de pipeline de ML.

**Micro-Passos:**
1. Instalar ZenML
2. Criar stack local
3. Definir pipelines base
4. Testar execucao

**Definicao de Pronto:** ZenML dashboard acessivel.

---

## Fase 1.6: Documentacao e Entrevistas

### [TASK_1.6.1] - Criar MDs de Entrevistas

**Objetivo:** Documentar requisitos detalhados de cada parte.

**Micro-Passos:**
1. Criar `docs/interviews/PILARES.md`
2. Criar `docs/interviews/VIGAS.md`
3. Criar `docs/interviews/LAJES.md`
4. Criar `docs/interviews/SWARM.md`
5. Criar `docs/interviews/VETORES.md`

**Definicao de Pronto:** MDs com perguntas e respostas.

---

### [TASK_1.6.2] - Criar Checklist de Populacao

**Objetivo:** Lista de dados para usuario popular.

**Micro-Passos:**
1. Criar `docs/DATA_POPULATION_CHECKLIST.md`
2. Listar cada tipo de dado necessario
3. Criar formato esperado de cada arquivo
4. Criar exemplos de cada categoria

**Definicao de Pronto:** Checklist completo e claro.

---

# CHECKLIST DE POPULACAO DE DADOS

## Dados que VOCE vai fornecer:

### 1. Estruturais Brutos
- [ ] Pasta com DXFs estruturais originais
- [ ] Minimo: 10 estruturais variados
- [ ] Ideal: 50+ estruturais

### 2. DXFs Produtos
- [ ] Pilares: Grades de cada face
- [ ] Vigas Laterais: Laterais de cada lado
- [ ] Vigas Fundos: Fundos completos
- [ ] Lajes: Paineis de cada laje

### 3. Scripts SCR
- [ ] SCRs de pilares (todas variacoes)
- [ ] SCRs de vigas laterais
- [ ] SCRs de vigas fundos
- [ ] SCRs de lajes

### 4. JSONs dos Robos
- [ ] JSON de configuracao de pilares
- [ ] JSON de configuracao de vigas
- [ ] JSON de configuracao de lajes

### 5. Exemplo Completo
- [ ] 1 estrutural completo
- [ ] Interpretacao 100% desse estrutural
- [ ] Todos robos alimentados
- [ ] Todos SCRs gerados
- [ ] Todos DXFs produtos

---

# TECNOLOGIAS A INSTALAR

| Tecnologia | Versao | Proposito |
|------------|--------|-----------|
| ChromaDB | 0.4+ | Vector DB principal |
| FAISS | 1.7+ | Busca rapida |
| Ollama | latest | LLM local |
| LLaMA 3.2 | 3B | Agentes swarm |
| MLflow | 2.0+ | Tracking ML |
| ZenML | 0.50+ | Pipeline ML |
| sentence-transformers | 2.2+ | Embeddings |
| Pydantic | 2.0+ | Validacao schemas |
| ezdxf | 1.1+ | Parse DXF |
| Shapely | 2.0+ | Geometria |

---

# PROXIMOS PASSOS IMEDIATOS

1. Criar estrutura de pastas `data/`
2. Atualizar requirements.txt
3. Implementar CausalVectorEngine
4. Configurar Ollama + LLaMA
5. Implementar Swarm Agents
6. Criar MDs de entrevistas
7. Criar checklist de populacao
