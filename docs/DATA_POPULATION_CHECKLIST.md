# Checklist de Populacao de Dados

## Objetivo
Este checklist guia a populacao de dados para treinamento do sistema AgenteCAD.

---

## 1. ESTRUTURAIS BRUTOS

Pasta: `data/raw/estruturais/`

### Minimo Necessario (10 estruturais)
- [ ] projeto_001.dxf
- [ ] projeto_002.dxf
- [ ] projeto_003.dxf
- [ ] projeto_004.dxf
- [ ] projeto_005.dxf
- [ ] projeto_006.dxf
- [ ] projeto_007.dxf
- [ ] projeto_008.dxf
- [ ] projeto_009.dxf
- [ ] projeto_010.dxf

### Ideal (50+ estruturais)
- [ ] 50 DXFs estruturais variados

### Metadata (opcional mas recomendado)
Para cada DXF, criar arquivo `projeto_XXX_metadata.json`:
```json
{
  "nome_projeto": "Edificio X",
  "data": "2026-01-21",
  "total_pilares_esperados": 20,
  "total_vigas_esperadas": 30,
  "total_lajes_esperadas": 15,
  "notas": ""
}
```

---

## 2. DXFs PRODUTOS

### 2.1 Pilares
Pasta: `data/raw/produtos/pilares/`

- [ ] grade_P1_face_A.dxf
- [ ] grade_P1_face_B.dxf
- [ ] grade_P1_face_C.dxf
- [ ] grade_P1_face_D.dxf
- [ ] ... (repetir para cada pilar)

Nomenclatura: `grade_{NOME_PILAR}_face_{FACE}.dxf`

Minimo: 20 grades de pilares diferentes.

### 2.2 Vigas Laterais
Pasta: `data/raw/produtos/vigas_laterais/`

- [ ] lateral_V1_lado_A.dxf
- [ ] lateral_V1_lado_B.dxf
- [ ] ... (repetir para cada viga)

Nomenclatura: `lateral_{NOME_VIGA}_lado_{LADO}.dxf`

Minimo: 20 laterais de vigas diferentes.

### 2.3 Vigas Fundos
Pasta: `data/raw/produtos/vigas_fundos/`

- [ ] fundo_V1.dxf
- [ ] fundo_V2.dxf
- [ ] ... (repetir para cada viga)

Nomenclatura: `fundo_{NOME_VIGA}.dxf`

Minimo: 20 fundos de vigas diferentes.

### 2.4 Lajes
Pasta: `data/raw/produtos/lajes/`

- [ ] painel_L1.dxf
- [ ] painel_L2.dxf
- [ ] ... (repetir para cada laje)

Nomenclatura: `painel_{NOME_LAJE}.dxf`

Minimo: 20 paineis de lajes diferentes.

---

## 3. SCRIPTS SCR

### 3.1 Pilares
Pasta: `data/raw/scripts/pilares/`

Para cada DXF de grade, criar SCR correspondente:
- [ ] grade_P1_face_A.scr
- [ ] grade_P1_face_B.scr
- [ ] ...

### 3.2 Vigas Laterais
Pasta: `data/raw/scripts/vigas_laterais/`

- [ ] lateral_V1_lado_A.scr
- [ ] lateral_V1_lado_B.scr
- [ ] ...

### 3.3 Vigas Fundos
Pasta: `data/raw/scripts/vigas_fundos/`

- [ ] fundo_V1.scr
- [ ] fundo_V2.scr
- [ ] ...

### 3.4 Lajes
Pasta: `data/raw/scripts/lajes/`

- [ ] painel_L1.scr
- [ ] painel_L2.scr
- [ ] ...

---

## 4. JSONs DE CONFIGURACAO

### 4.1 Pilares
Pasta: `data/raw/jsons/pilares/`

```json
{
  "nome": "P-1",
  "formato": "RETANGULAR",
  "dimensoes": {
    "largura": 40,
    "altura": 60
  },
  "faces": {
    "A": {
      "lajes": [
        {"nome": "L1", "nivel": "+3.00", "posicao": "TOPO", "altura_h": 12}
      ],
      "vigas_laterais": {
        "esquerda": {"nome": "V1", "dimensao": "14x60", "abertura": 5},
        "direita": null
      },
      "vigas_frontais": [
        {"nome": "V2", "dimensao": "14x50", "abertura": 0, "diferenca_nivel": 0}
      ]
    },
    "B": {},
    "C": {},
    "D": {}
  }
}
```

- [ ] config_P1.json
- [ ] config_P2.json
- [ ] ... (minimo 20)

### 4.2 Vigas
Pasta: `data/raw/jsons/vigas/`

```json
{
  "nome": "V1",
  "dimensao": "14x60",
  "lados": {
    "A": {
      "local_inicial": {"tipo": "PILAR", "nome": "P-1"},
      "local_final": {"tipo": "PILAR", "nome": "P-2"},
      "nivel": "+3.00",
      "lajes_associadas": [{"nome": "L1", "altura_h": 12}],
      "segmentos": [
        {
          "numero": 1,
          "tipo_inicio": "PILAR",
          "nome_inicio": "P-1",
          "distancia_inicio_cm": 0,
          "tipo_conflito": "PILAR",
          "nome_conflito": "P-3",
          "tamanho_conflito_cm": 40,
          "distancia_pos_conflito_cm": 120
        }
      ]
    },
    "B": {}
  }
}
```

- [ ] config_V1.json
- [ ] config_V2.json
- [ ] ... (minimo 20)

### 4.3 Lajes
Pasta: `data/raw/jsons/lajes/`

```json
{
  "nome": "L1",
  "altura_h": 12,
  "nivel": "+3.00",
  "coordenadas": [[0,0], [500,0], [500,400], [0,400]],
  "linhas_verticais": [122, 60, 122, 60, 122],
  "linhas_horizontais": [100, 100, 100],
  "modo_calculo": 1
}
```

- [ ] config_L1.json
- [ ] config_L2.json
- [ ] ... (minimo 20)

---

## 5. EXEMPLO COMPLETO

### Um projeto completo do inicio ao fim:

1. **Estrutural Original**
   - [ ] `data/raw/estruturais/exemplo_completo.dxf`

2. **Interpretacao 100%**
   - [ ] Todos os pilares identificados e mapeados
   - [ ] Todas as vigas identificadas e mapeadas
   - [ ] Todas as lajes identificadas e mapeadas

3. **JSONs dos Robos**
   - [ ] Todos os pilares com JSON completo
   - [ ] Todas as vigas com JSON completo
   - [ ] Todas as lajes com JSON completo

4. **Scripts SCR**
   - [ ] SCR de cada grade de pilar
   - [ ] SCR de cada lateral de viga
   - [ ] SCR de cada fundo de viga
   - [ ] SCR de cada painel de laje

5. **DXFs Produtos**
   - [ ] DXF de cada grade (executar SCR)
   - [ ] DXF de cada lateral (executar SCR)
   - [ ] DXF de cada fundo (executar SCR)
   - [ ] DXF de cada painel (executar SCR)

---

## 6. VARIACOES PARA COBERTURA

### Pilares - Variar:
- [ ] Diferentes formatos (RETANGULAR, L, T, U)
- [ ] Diferentes dimensoes
- [ ] Diferentes quantidades de vigas chegando
- [ ] Diferentes quantidades de lajes
- [ ] Com e sem aberturas

### Vigas - Variar:
- [ ] Diferentes comprimentos
- [ ] Diferentes quantidades de segmentos
- [ ] Diferentes tipos de conflitos
- [ ] Com e sem recortes

### Lajes - Variar:
- [ ] Retangulares simples
- [ ] Formas em L
- [ ] Com recortes/ilhas
- [ ] Diferentes tamanhos

---

## 7. VALIDACAO

Apos popular, verificar:

- [ ] Todos os arquivos estao nas pastas corretas
- [ ] Nomenclatura consistente
- [ ] JSONs validos (sem erros de sintaxe)
- [ ] SCRs executaveis no AutoCAD
- [ ] DXFs produtos correspondem aos SCRs
- [ ] Relacao 1:1 entre estrutural, JSON, SCR e DXF produto

---

## STATUS GERAL

| Categoria | Minimo | Ideal | Atual |
|-----------|--------|-------|-------|
| Estruturais | 10 | 50+ | 0 |
| Grades pilares | 20 | 100+ | 0 |
| Laterais vigas | 20 | 100+ | 0 |
| Fundos vigas | 20 | 100+ | 0 |
| Paineis lajes | 20 | 100+ | 0 |
| JSONs pilares | 20 | 100+ | 0 |
| JSONs vigas | 20 | 100+ | 0 |
| JSONs lajes | 20 | 100+ | 0 |
| Exemplo completo | 1 | 5+ | 0 |
