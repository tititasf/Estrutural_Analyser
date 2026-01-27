# Estrutura Completa de `dados_pilar` Esperada pelo Gerador Legacy

## TASK-007: Documentação da Estrutura de Dados

Este documento descreve a estrutura completa do dicionário `dados_pilar` esperado pelo gerador legacy de scripts CIMA, ABCD e GRADES.

## Campos Obrigatórios

### Campos Básicos
- `nome` (str): Nome do pilar (ex: "P1")
- `pavimento` (str): Nome do pavimento (ex: "P1")
- `comprimento` (float): Comprimento do pilar em cm
- `largura` (float): Largura do pilar em cm
- `altura` (float): Altura do pilar em cm
- `numero` (str): Número do pilar (ex: "1")

### Dicionários Obrigatórios

#### `grades_grupo1` (dict)
```python
{
    'grade_1': float,
    'distancia_1': float,
    'grade_2': float,
    'distancia_2': float,
    'grade_3': float,
}
```

#### `detalhes_grades` (dict)
```python
{
    'detalhe_grade1_1': float,
    'detalhe_grade1_2': float,
    'detalhe_grade1_3': float,
    'detalhe_grade1_4': float,
    'detalhe_grade1_5': float,
    'detalhe_grade2_1': float,
    # ... até detalhe_grade3_5
}
```

## Campos Opcionais

### Parafusos
- `parafuso_p1_p2` (int): Distância entre parafusos P1-P2
- `parafuso_p2_p3` (int): Distância entre parafusos P2-P3
- `parafuso_p3_p4` (int): Distância entre parafusos P3-P4
- `parafuso_p4_p5` (int): Distância entre parafusos P4-P5
- `parafuso_p5_p6` (int): Distância entre parafusos P5-P6
- `parafuso_p6_p7` (int): Distância entre parafusos P6-P7
- `parafuso_p7_p8` (int): Distância entre parafusos P7-P8
- `parafuso_p8_p9` (int): Distância entre parafusos P8-P9

### Pilar Especial

#### Estrutura `pilar_especial` (dict)
**IMPORTANTE**: O código legacy espera `pilar_especial` como dicionário com `ativar_pilar_especial` dentro.

```python
{
    'ativar_pilar_especial': bool,  # Campo crítico dentro do dicionário
    'tipo_pilar_especial': str,     # Ex: "L"
    'comp_1': float,
    'comp_2': float,
    'comp_3': float,
    'larg_1': float,
    'larg_2': float,
    'larg_3': float,
    'distancia_pilar_especial': float,
    'parafusos_especiais': {        # Opcional dentro de pilar_especial
        'parafusos_a': [float, ...],  # Lista de 9 valores
        'parafusos_e': [float, ...],  # Lista de 9 valores
    }
}
```

**Compatibilidade**: O código legacy também verifica campos no nível raiz:
- `pilar_especial_ativo` (bool) - nome alternativo
- `ativar_pilar_especial` (bool) - no nível raiz
- `tipo_pilar_especial` (str) - no nível raiz
- `comp_1`, `comp_2`, `comp_3` (float) - no nível raiz
- `larg_1`, `larg_2`, `larg_3` (float) - no nível raiz
- `distancia_pilar_especial` (float) - no nível raiz

### Parafusos Especiais

#### Estrutura `parafusos_especiais` (dict)
**IMPORTANTE**: Pode estar no nível raiz OU dentro de `pilar_especial`.

```python
{
    'parafusos_a': [float, float, float, float, float, float, float, float, float],  # 9 valores
    'parafusos_e': [float, float, float, float, float, float, float, float, float],  # 9 valores
}
```

**Prioridade**: Se presente em ambos, `pilar_especial['parafusos_especiais']` tem prioridade.

### Grades Grupo 2

#### `grades_grupo2` (dict)
```python
{
    'grade_1_grupo2': float,
    'distancia_1_grupo2': float,
    'grade_2_grupo2': float,
    'distancia_2_grupo2': float,
    'grade_3_grupo2': float,
}
```

#### `detalhes_grades_grupo2` (dict)
```python
{
    'detalhe_grade1_1_grupo2': float,
    'detalhe_grade1_2_grupo2': float,
    # ... até detalhe_grade3_5_grupo2
}
```

### Detalhes de Grades Especiais

#### `detalhes_grades_especiais` (dict)
Contém detalhes para faces especiais (A, B, E, F, G, H):
```python
{
    'detalhe_a_1_1': float,
    'detalhe_a_1_2': float,
    # ... até detalhe_h_3_5
}
```

## Faces (A, B, C, D, E, F, G, H)

Para cada face, os seguintes campos podem estar presentes:

### Campos Básicos por Face
- `laje_{face}` (float): Valor da laje
- `posicao_laje_{face}` (float): Posição da laje
- `larg1_{face}`, `larg2_{face}`, `larg3_{face}` (float): Larguras
- `h1_{face}`, `h2_{face}`, `h3_{face}`, `h4_{face}`, `h5_{face}` (float): Alturas

### Hachuras por Face
- `hachura_l1_h2_{face}` até `hachura_l3_h5_{face}` (int): Valores de hachura

### Aberturas (Faces A e B)
- `distancia_esq_1_{face}`, `largura_esq_1_{face}`, `profundidade_esq_1_{face}`, `posicao_esq_1_{face}` (float)
- `distancia_esq_2_{face}`, `largura_esq_2_{face}`, `profundidade_esq_2_{face}`, `posicao_esq_2_{face}` (float)
- `distancia_dir_1_{face}`, `largura_dir_1_{face}`, `profundidade_dir_1_{face}`, `posicao_dir_1_{face}` (float)
- `distancia_dir_2_{face}`, `largura_dir_2_{face}`, `profundidade_dir_2_{face}`, `posicao_dir_2_{face}` (float)

### Grades Especiais (Faces A, B, E, F, G, H)
- `grade_{face}_1`, `grade_{face}_2`, `grade_{face}_3` (float)
- `dist_{face}_1`, `dist_{face}_2` (float)
- `detalhe_{face}_{grade}_{detalhe}` (float): Grade 1-3, Detalhe 1-5
- `altura_detalhe_{face}_{grade}_{altura}` (float): Grade 1-3, Altura 0-5

## Exemplo Completo

```python
dados_pilar = {
    # Campos básicos obrigatórios
    'nome': 'P1',
    'pavimento': 'P1',
    'comprimento': 44.0,
    'largura': 44.0,
    'altura': 300.0,
    'numero': '1',
    
    # Grades Grupo 1 (obrigatório)
    'grades_grupo1': {
        'grade_1': 0.0,
        'distancia_1': 0.0,
        'grade_2': 0.0,
        'distancia_2': 0.0,
        'grade_3': 0.0,
    },
    
    # Detalhes Grades (obrigatório)
    'detalhes_grades': {
        'detalhe_grade1_1': 0.0,
        'detalhe_grade1_2': 0.0,
        # ... todos os detalhes
    },
    
    # Pilar Especial (opcional, mas estrutura completa se presente)
    'pilar_especial': {
        'ativar_pilar_especial': False,
        'tipo_pilar_especial': 'L',
        'comp_1': 0.0,
        'comp_2': 0.0,
        'comp_3': 0.0,
        'larg_1': 0.0,
        'larg_2': 0.0,
        'larg_3': 0.0,
        'distancia_pilar_especial': 0.0,
    },
    
    # Parafusos Especiais (opcional)
    'parafusos_especiais': {
        'parafusos_a': [0.0] * 9,
        'parafusos_e': [0.0] * 9,
    },
    
    # Campos no nível raiz para compatibilidade
    'pilar_especial_ativo': False,
    'ativar_pilar_especial': False,
    'tipo_pilar_especial': 'L',
    'comp_1': 0.0,
    'comp_2': 0.0,
    'comp_3': 0.0,
    'larg_1': 0.0,
    'larg_2': 0.0,
    'larg_3': 0.0,
    'distancia_pilar_especial': 0.0,
    
    # Parafusos normais
    'parafuso_p1_p2': 0,
    'parafuso_p2_p3': 0,
    # ... até parafuso_p8_p9
    
    # Grades Grupo 2 (opcional)
    'grades_grupo2': {
        'grade_1_grupo2': 0.0,
        'distancia_1_grupo2': 0.0,
        'grade_2_grupo2': 0.0,
        'distancia_2_grupo2': 0.0,
        'grade_3_grupo2': 0.0,
    },
    
    'detalhes_grades_grupo2': {
        'detalhe_grade1_1_grupo2': 0.0,
        # ... todos os detalhes grupo 2
    },
    
    'detalhes_grades_especiais': {
        'detalhe_a_1_1': 0.0,
        # ... todos os detalhes especiais
    },
    
    # Campos de faces (opcionais, muitos campos)
    'laje_A': 0.0,
    'posicao_laje_A': 0.0,
    # ... todos os campos de faces
}
```

## Referências de Código Legacy

- **Estrutura pilar_especial**: `_ROBOS_ABAS/pilares-legacy/src/interfaces/CIMA_FUNCIONAL_EXCEL.py` - Linhas 797-818
- **Parafusos especiais**: `_ROBOS_ABAS/pilares-legacy/src/interfaces/CIMA_FUNCIONAL_EXCEL.py` - Linhas 620-630
- **Validação de dados**: Ver função `_validate_legacy_data()` em `automation_service.py`

## Notas Importantes

1. **Estrutura Aninhada**: O código legacy verifica campos tanto no nível raiz quanto dentro de dicionários aninhados (ex: `pilar_especial['ativar_pilar_especial']`)

2. **Prioridade**: Quando um campo existe em múltiplos locais, a prioridade é:
   - Dicionário aninhado (ex: `pilar_especial['parafusos_especiais']`)
   - Nível raiz (ex: `parafusos_especiais`)

3. **Compatibilidade**: O mapeamento atual mantém campos tanto no nível raiz quanto em dicionários aninhados para máxima compatibilidade

4. **Configurações**: Campos de configuração (como `grades_com_sarrafo`) são gerenciados internamente pelo gerador via `config_manager`, não precisam ser passados nos dados
