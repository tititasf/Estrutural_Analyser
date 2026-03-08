# Schema JSON dos Vetores Semanticos

## 1. Visao Geral

Este documento define o schema padronizado para representacao de vetores semanticos no AgenteCAD. Cada elemento estrutural e representado como um vetor JSON completo contendo geometria, metadados, relacoes e embeddings.

---

## 2. Schema Hierarquico

### 2.1 Estrutura de Niveis

```
Estrutural Completo
├── Estrutural Limpo/Separado
│   ├── Lajes[]
│   │   ├── Informacoes basicas
│   │   ├── Geometria (marco)
│   │   ├── Paineis calculados
│   │   └── Vinculos (vigas adjacentes)
│   ├── Vigas[]
│   │   ├── Informacoes basicas
│   │   ├── Segmentos A/B
│   │   ├── Conflitos (pilares, vigas)
│   │   └── Cortes de detalhe
│   └── Pilares[]
│       ├── Informacoes basicas
│       ├── Faces (A-H)
│       ├── Grades e sarrafos
│       └── Aberturas
```

---

## 3. Schema do Vetor Estrutural Completo

```json
{
  "schema_version": "1.0.0",
  "tipo": "ESTRUTURAL_COMPLETO",
  "metadados": {
    "id": "uuid-v4",
    "nome_projeto": "string",
    "data_criacao": "ISO-8601",
    "data_atualizacao": "ISO-8601",
    "origem_dxf": {
      "caminho": "string",
      "hash_md5": "string",
      "data_importacao": "ISO-8601"
    },
    "versao_agentecad": "string",
    "status": "RASCUNHO|VALIDADO|PRODUZIDO"
  },
  "estatisticas": {
    "total_pilares": "integer",
    "total_vigas": "integer",
    "total_lajes": "integer",
    "area_total_m2": "float",
    "perimetro_total_m": "float"
  },
  "elementos": {
    "pilares": [],
    "vigas": [],
    "lajes": []
  },
  "relacoes": {
    "pilar_viga": [],
    "pilar_laje": [],
    "viga_laje": []
  },
  "embedding_global": {
    "vetor": [],
    "modelo": "string",
    "dimensoes": "integer"
  }
}
```

---

## 4. Schema do Pilar

```json
{
  "schema_version": "1.0.0",
  "tipo": "PILAR",
  "identificacao": {
    "id": "uuid-v4",
    "nome": "P-1",
    "numero_item": 1,
    "formato": "RETANGULAR|CIRCULAR|L|T|U"
  },
  "dimensoes": {
    "largura_cm": "float",
    "altura_cm": "float",
    "dimensao_texto": "40x60"
  },
  "geometria": {
    "centroide": {"x": "float", "y": "float"},
    "bounding_box": {
      "min": {"x": "float", "y": "float"},
      "max": {"x": "float", "y": "float"}
    },
    "vertices": [{"x": "float", "y": "float"}],
    "area_cm2": "float",
    "perimetro_cm": "float"
  },
  "faces": {
    "A": {
      "lajes": [
        {
          "nome": "L1",
          "nivel": "+0.00",
          "posicao": "TOPO|FUNDO|CENTRO",
          "altura_h": 12
        }
      ],
      "vigas_laterais": {
        "esquerda": {
          "nome": "V1",
          "dimensao": "12x50",
          "abertura_cm": 5.0
        },
        "direita": null
      },
      "vigas_frontais": [
        {
          "nome": "V2",
          "dimensao": "14x60",
          "abertura_cm": 0,
          "diferenca_nivel": 0
        }
      ]
    },
    "B": {},
    "C": {},
    "D": {},
    "E": null,
    "F": null,
    "G": null,
    "H": null
  },
  "producao": {
    "grades": [
      {
        "face": "A",
        "quantidade_sarrafos": 4,
        "alturas_sarrafos_cm": [30, 60, 90, 120],
        "largura_grade_cm": 40,
        "altura_grade_cm": 150
      }
    ],
    "aberturas": [
      {
        "face": "A",
        "posicao_x_cm": 10,
        "posicao_y_cm": 20,
        "largura_cm": 15,
        "altura_cm": 25,
        "tipo": "VIGA_CHEGADA|PASSAGEM"
      }
    ],
    "parafusos": {
      "quantidade_total": 8,
      "posicoes": []
    }
  },
  "vinculos_canvas": {
    "texto_nome": {
      "entidade_id": "string",
      "coordenadas": {"x": "float", "y": "float"},
      "cor_destaque": "#FF0000"
    },
    "retangulo_formato": {
      "entidade_ids": [],
      "coordenadas": []
    },
    "texto_dimensao": {
      "entidade_id": "string",
      "valor_original": "40x60"
    }
  },
  "treinamento": {
    "status": "NAO_VALIDADO|VALIDADO|INVALIDADO",
    "validado_por": "string",
    "data_validacao": "ISO-8601",
    "comentario_invalidacao": "string",
    "dna_vetor": [],
    "similaridade_score": "float"
  },
  "embedding": {
    "vetor": [],
    "modelo": "sentence-transformers/all-MiniLM-L6-v2",
    "dimensoes": 384
  }
}
```

---

## 5. Schema da Viga

```json
{
  "schema_version": "1.0.0",
  "tipo": "VIGA",
  "identificacao": {
    "id": "uuid-v4",
    "nome": "V1",
    "numero_item": 1
  },
  "dimensoes": {
    "base_cm": "float",
    "altura_cm": "float",
    "comprimento_total_cm": "float",
    "dimensao_texto": "14x60"
  },
  "lados": {
    "A": {
      "local_inicial": {
        "tipo": "PILAR|VIGA|PAREDE",
        "nome": "P-1"
      },
      "local_final": {
        "tipo": "PILAR|VIGA|PAREDE",
        "nome": "P-2"
      },
      "dimensao_corte": "14x60",
      "nivel": "+3.00",
      "lajes_associadas": [
        {
          "nome": "L1",
          "dimensao": "h=12"
        }
      ],
      "segmentos": [
        {
          "numero": 1,
          "tipo_inicio": "PILAR",
          "nome_inicio": "P-1",
          "distancia_inicio_cm": 0,
          "tipo_conflito": "PILAR|VIGA|FIM",
          "nome_conflito": "P-3",
          "tamanho_conflito_cm": 40,
          "distancia_pos_conflito_cm": 120
        }
      ],
      "quantidade_segmentos": 3
    },
    "B": {}
  },
  "corte_detalhe": {
    "imagem_referencia": "base64|path",
    "descricao": "string",
    "cotas": []
  },
  "producao": {
    "fundos": [
      {
        "lado": "A",
        "largura_cm": 14,
        "comprimento_cm": 300,
        "sarrafos": [
          {"posicao_cm": 50, "tipo": "HORIZONTAL"}
        ]
      }
    ],
    "laterais": [
      {
        "lado": "A",
        "altura_cm": 60,
        "comprimento_cm": 300,
        "recortes": []
      }
    ]
  },
  "vinculos_canvas": {
    "linhas_segmentos": [],
    "textos_dimensao": [],
    "textos_nome": []
  },
  "treinamento": {
    "status": "NAO_VALIDADO|VALIDADO|INVALIDADO",
    "dna_vetor": [],
    "similaridade_score": "float"
  },
  "embedding": {
    "vetor": [],
    "modelo": "string",
    "dimensoes": "integer"
  }
}
```

---

## 6. Schema da Laje

```json
{
  "schema_version": "1.0.0",
  "tipo": "LAJE",
  "identificacao": {
    "id": "uuid-v4",
    "nome": "L1",
    "numero_item": 1
  },
  "dimensoes": {
    "altura_h_cm": 12,
    "nivel": "+3.00",
    "area_m2": "float",
    "perimetro_m": "float"
  },
  "geometria": {
    "tipo": "RETANGULAR|L_SHAPE|COMPLEXA",
    "marco": {
      "vertices": [{"x": "float", "y": "float"}],
      "coordenadas_absolutas": true
    },
    "ilhas": [
      {
        "vertices": [],
        "area_m2": "float",
        "descricao": "Furo para escada"
      }
    ],
    "bounding_box": {
      "min": {"x": "float", "y": "float"},
      "max": {"x": "float", "y": "float"}
    }
  },
  "vigas_adjacentes": [
    {
      "nome": "V1",
      "lado": "NORTE|SUL|LESTE|OESTE",
      "comprimento_adjacencia_cm": "float"
    }
  ],
  "pilares_adjacentes": [
    {
      "nome": "P-1",
      "canto": "NE|NO|SE|SO",
      "face_contato": "A|B|C|D"
    }
  ],
  "producao": {
    "modo_calculo": 1,
    "linhas_verticais": {
      "distancias_cm": [122, 60, 122],
      "total": 3
    },
    "linhas_horizontais": {
      "distancias_cm": [100, 100],
      "total": 2
    },
    "paineis": [
      {
        "id": 1,
        "vertices": [],
        "largura_cm": 122,
        "comprimento_cm": 100,
        "area_cm2": 12200,
        "tipo": "SEM_DEFORMIDADE|COM_DEFORMIDADE",
        "quantidade": 4
      }
    ],
    "resumo_paineis": {
      "total_paineis": 12,
      "grupos": [
        {
          "medida": "122x100",
          "quantidade": 4,
          "area_unitaria_cm2": 12200
        }
      ]
    }
  },
  "vinculos_canvas": {
    "texto_nome": {},
    "texto_altura": {},
    "texto_nivel": {},
    "linhas_marco": []
  },
  "treinamento": {
    "status": "NAO_VALIDADO|VALIDADO|INVALIDADO",
    "features_geometricas": {
      "area": "float",
      "perimetro": "float",
      "aspect_ratio": "float",
      "solidez": "float",
      "num_vertices": "integer",
      "num_ilhas": "integer",
      "hu_moments": []
    },
    "dna_vetor": [],
    "similaridade_score": "float"
  },
  "embedding": {
    "vetor": [],
    "modelo": "string",
    "dimensoes": "integer"
  }
}
```

---

## 7. Schema de Relacoes

```json
{
  "pilar_viga": [
    {
      "pilar_id": "uuid",
      "pilar_nome": "P-1",
      "pilar_face": "A",
      "viga_id": "uuid",
      "viga_nome": "V1",
      "tipo_conexao": "CHEGADA|PASSAGEM|CONTINUACAO",
      "abertura_cm": 5.0,
      "diferenca_nivel_cm": 0
    }
  ],
  "pilar_laje": [
    {
      "pilar_id": "uuid",
      "pilar_nome": "P-1",
      "pilar_face": "A",
      "laje_id": "uuid",
      "laje_nome": "L1",
      "posicao": "TOPO|FUNDO|CENTRO",
      "distancia_centro_cm": 0
    }
  ],
  "viga_laje": [
    {
      "viga_id": "uuid",
      "viga_nome": "V1",
      "viga_lado": "A",
      "laje_id": "uuid",
      "laje_nome": "L1",
      "comprimento_adjacencia_cm": 300
    }
  ]
}
```

---

## 8. Schema de Imagens e Multimodalidade

```json
{
  "imagens": {
    "dxf_original": {
      "tipo": "SCREENSHOT|RENDER",
      "formato": "PNG|JPG",
      "dados": "base64_encoded",
      "dimensoes": {"largura": 1920, "altura": 1080},
      "embedding_visual": {
        "vetor": [],
        "modelo": "CLIP",
        "dimensoes": 512
      }
    },
    "cortes_detalhe": [
      {
        "elemento_id": "uuid",
        "elemento_tipo": "VIGA",
        "lado": "A",
        "dados": "base64_encoded",
        "descricao": "Corte transversal V1 lado A",
        "embedding_visual": {}
      }
    ],
    "capturas_canvas": [
      {
        "timestamp": "ISO-8601",
        "viewport": {},
        "dados": "base64_encoded"
      }
    ]
  }
}
```

---

## 9. Validacoes de Schema

### 9.1 Regras de Validacao

```python
VALIDATION_RULES = {
    "pilar": {
        "required_fields": ["identificacao.nome", "dimensoes", "geometria"],
        "formato_valido": ["RETANGULAR", "CIRCULAR", "L", "T", "U"],
        "faces_por_formato": {
            "RETANGULAR": ["A", "B", "C", "D"],
            "CIRCULAR": [],
            "L": ["A", "B", "C", "D", "E", "F"],
            "T": ["A", "B", "C", "D", "E", "F", "G", "H"],
            "U": ["A", "B", "C", "D", "E", "F", "G", "H"]
        }
    },
    "viga": {
        "required_fields": ["identificacao.nome", "dimensoes", "lados"],
        "lados_validos": ["A", "B"]
    },
    "laje": {
        "required_fields": ["identificacao.nome", "dimensoes", "geometria"],
        "altura_h_range": [8, 30]
    }
}
```

### 9.2 Exemplo de Uso

```python
from pydantic import BaseModel, validator
from typing import List, Optional
from uuid import UUID

class PilarSchema(BaseModel):
    id: UUID
    nome: str
    formato: Literal["RETANGULAR", "CIRCULAR", "L", "T", "U"]
    dimensoes: DimensoesSchema
    faces: Dict[str, FaceSchema]
    
    @validator('faces')
    def validate_faces_by_format(cls, v, values):
        formato = values.get('formato')
        expected_faces = VALIDATION_RULES['pilar']['faces_por_formato'][formato]
        # Validar que faces correspondem ao formato
        return v
```

---

## 10. Versionamento de Schema

| Versao | Data | Mudancas |
|--------|------|----------|
| 1.0.0 | 2026-01-21 | Schema inicial |
| 1.1.0 | Planejado | Adicao de embeddings multimodais |
| 2.0.0 | Planejado | Schema para engenharia reversa |
