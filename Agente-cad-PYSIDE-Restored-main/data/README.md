# Estrutura de Dados - AgenteCAD

## Visao Geral

Esta pasta contem todos os dados para treinamento e operacao do sistema cognitivo.

## Estrutura

```
data/
├── raw/                    # VOCE POPULA - Dados brutos
│   ├── estruturais/        # DXFs estruturais originais
│   ├── produtos/           # DXFs produtos finais
│   │   ├── pilares/        # Grades de pilares
│   │   ├── vigas_laterais/ # Laterais de vigas
│   │   ├── vigas_fundos/   # Fundos de vigas
│   │   └── lajes/          # Paineis de lajes
│   ├── scripts/            # Arquivos SCR
│   │   ├── pilares/
│   │   ├── vigas_laterais/
│   │   ├── vigas_fundos/
│   │   └── lajes/
│   └── jsons/              # JSONs de configuracao dos robos
│       ├── pilares/
│       ├── vigas/
│       └── lajes/
│
├── processed/              # SISTEMA GERA - Dados processados
│   ├── embeddings/         # Vetores embeddings
│   ├── features/           # Features extraidas
│   └── trajectories/       # Trajetorias de raciocinio
│
├── training/               # SISTEMA GERA - Dados de treino
│   ├── forward/            # Estrutural → Produto
│   ├── reverse/            # Produto → Estrutural
│   └── synthetic/          # Dados sinteticos
│
├── vectors/                # SISTEMA GERA - Bancos vetoriais
│   ├── chromadb/           # ChromaDB collections
│   ├── faiss/              # FAISS indices
│   └── causal/             # Causal trajectories
│
└── models/                 # SISTEMA GERA - Modelos treinados
    ├── llama/              # Modelos LLaMA fine-tuned
    ├── embeddings/         # Modelos de embedding
    └── classifiers/        # Classificadores
```

## Como Popular os Dados

### 1. Estruturais Brutos (`raw/estruturais/`)

Coloque seus DXFs estruturais originais aqui. Formato esperado:
- Arquivo: `projeto_XXX.dxf` ou `estrutural_XXX.dxf`
- Opcional: `projeto_XXX_metadata.json` com informacoes extras

### 2. DXFs Produtos (`raw/produtos/`)

Organize por tipo de elemento:
- `pilares/grade_PXXX_face_X.dxf`
- `vigas_laterais/lateral_VXXX_lado_X.dxf`
- `vigas_fundos/fundo_VXXX.dxf`
- `lajes/painel_LXXX.dxf`

### 3. Scripts SCR (`raw/scripts/`)

Arquivos SCR correspondentes aos DXFs:
- Mesmo nome do DXF mas com extensao `.scr`

### 4. JSONs dos Robos (`raw/jsons/`)

Configuracoes exportadas dos robos:
- `pilares/config_PXXX.json`
- `vigas/config_VXXX.json`
- `lajes/config_LXXX.json`

## Formato dos JSONs

### Pilar
```json
{
  "nome": "P-1",
  "formato": "RETANGULAR",
  "dimensoes": {"largura": 40, "altura": 60},
  "faces": {
    "A": {
      "lajes": [...],
      "vigas_laterais": {...},
      "vigas_frontais": [...]
    }
  }
}
```

### Viga
```json
{
  "nome": "V1",
  "dimensao": "14x60",
  "lados": {
    "A": {"segmentos": [...]},
    "B": {"segmentos": [...]}
  }
}
```

### Laje
```json
{
  "nome": "L1",
  "coordenadas": [[x,y], ...],
  "altura_h": 12,
  "nivel": "+3.00",
  "linhas_verticais": [...],
  "linhas_horizontais": [...]
}
```

## Convencao de Nomes

- Projetos: `projeto_001`, `projeto_002`, ...
- Pilares: `P-1`, `P-2`, ... ou `P1`, `P2`, ...
- Vigas: `V1`, `V2`, ... ou `V-1`, `V-2`, ...
- Lajes: `L1`, `L2`, ... ou `LAJE1`, `LAJE2`, ...
- Faces: `A`, `B`, `C`, `D`, `E`, `F`, `G`, `H`
- Lados: `A` (esquerda/baixo), `B` (direita/cima)
