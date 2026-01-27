# Guia dos Robos Especializados

## Visao Geral

Os robos sao modulos especializados que processam elementos estruturais especificos e geram scripts de producao.

---

## 1. Robo Lajes

**Localizacao:** `_ROBOS_ABAS/Robo_Lajes/`
**Classe Principal:** `LajeMainWindow`
**Funcao:** Processar formas de lajes e gerar paineis

### 1.1 Funcionalidades

- Selecao de laje via AutoCAD (Hatch, Polyline, Objetos)
- Configuracao de linhas verticais e horizontais
- Calculo automatico de paineis
- Classificacao: com/sem deformidade
- Agrupamento por medidas iguais

### 1.2 Entrada de Dados

```json
{
  "coordenadas": [[x1,y1], [x2,y2], ...],
  "linhas_verticais": [122, 60, 122],
  "linhas_horizontais": [100, 100],
  "modo_calculo": 1
}
```

### 1.3 Saida

```
SCR de paineis com:
- Marco da laje
- Linhas de divisao
- Cotas
- Tabela de resumo
```

### 1.4 Machine Learning

O Robo Lajes usa KNN para sugerir configuracoes de linhas baseado em geometrias similares:
- Features: area, perimetro, aspect_ratio, solidez, hu_moments
- Arquivo: `data/learning_map.db`

---

## 2. Robo Pilares

**Localizacao:** `_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/`
**Classe Principal:** `create_pilares_widget()`
**Funcao:** Processar pilares e gerar grades

### 2.1 Funcionalidades

- Suporte a formatos: RETANGULAR, CIRCULAR, L, T, U
- Configuracao de faces (A-H dependendo do formato)
- Calculo de grades e sarrafos
- Configuracao de aberturas
- Calculo de parafusos

### 2.2 Entrada de Dados

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

### 2.3 Saida

```
SCR de grades com:
- Retangulo principal
- Sarrafos internos
- Aberturas
- Cotas
- Parafusos
```

### 2.4 Regras de Faces por Formato

| Formato | Faces Disponiveis |
|---------|-------------------|
| RETANGULAR | A, B, C, D |
| CIRCULAR | (sem faces, topo/fundo) |
| L | A, B, C, D, E, F |
| T | A, B, C, D, E, F, G, H |
| U | A, B, C, D, E, F, G, H |

---

## 3. Robo Laterais de Vigas

**Localizacao:** `_ROBOS_ABAS/Robo_Laterais_de_Vigas/`
**Classe Principal:** `VigaMainWindow`
**Funcao:** Processar laterais de vigas

### 3.1 Funcionalidades

- Processamento de lados A e B
- Identificacao de segmentos
- Marcacao de conflitos (pilares, vigas)
- Calculo de recortes
- Geracao de laterais

### 3.2 Entrada de Dados

```json
{
  "nome": "V1",
  "dimensao": "14x60",
  "lados": {
    "A": {
      "local_inicial": "P-1",
      "local_final": "P-2",
      "segmentos": [...]
    },
    "B": {...}
  }
}
```

### 3.3 Saida

```
SCR de laterais com:
- Retangulo lateral
- Recortes para pilares
- Cotas
- Nivel
```

---

## 4. Robo Fundos de Vigas

**Localizacao:** `_ROBOS_ABAS/Robo_Fundos_de_Vigas/compactador-producao/`
**Classe Principal:** `FundoMainWindow`
**Funcao:** Processar fundos de vigas

### 4.1 Funcionalidades

- Calculo de comprimento total
- Configuracao de sarrafos transversais
- Agrupamento por dimensoes
- Otimizacao de producao

### 4.2 Entrada de Dados

```json
{
  "nome": "V1",
  "largura": 14,
  "comprimento": 300,
  "sarrafos": [
    {"posicao": 50, "tipo": "HORIZONTAL"}
  ]
}
```

### 4.3 Saida

```
SCR de fundos com:
- Retangulo do fundo
- Sarrafos
- Cotas
- Identificacao
```

---

## 5. Integracao com Structural Analyzer

### 5.1 Fluxo de Dados

```
Structural Analyzer (main.py)
        │
        ├─► find_pillars() ─► Robo Pilares
        │
        ├─► find_beams() ─► Robo Laterais + Robo Fundos
        │
        └─► find_slabs() ─► Robo Lajes
```

### 5.2 Interface de Comunicacao

```python
# Dados enviados do Analyzer para o Robo
robo_data = {
    "projeto": {...},
    "elemento": {...},
    "contexto": {...}
}

# Robo processa e retorna
result = {
    "scr_content": "...",
    "warnings": [...],
    "stats": {...}
}
```

### 5.3 LicensingProxy

Interface unificada para controle de creditos:

```python
class LicensingProxy:
    def consume_credits(self, amount):
        """Debita creditos do usuario."""
        
    def consultar_saldo(self):
        """Retorna saldo atual."""
```

---

## 6. Sincronizacao de Dados

### 6.1 Natural Sorting

Vigas sao ordenadas naturalmente (V2 antes de V10):

```python
from natsort import natsorted
vigas_sorted = natsorted(vigas, key=lambda x: x['nome'])
```

### 6.2 Agrupamento

```python
# Agrupar elementos por dimensao
from itertools import groupby
grouped = groupby(sorted(elementos, key=get_dim), get_dim)
```

---

## 7. Botao "Exportar para Estrutural"

Cada robo tera um botao para exportar dados para o banco de vetores:

```python
def export_to_structural(self):
    # 1. Coletar dados atuais
    data = self.collect_current_data()
    
    # 2. Validar contra schema
    validated = validate_schema(data)
    
    # 3. Gerar embedding
    embedding = processor.generate_embedding(data)
    
    # 4. Salvar no vector DB
    memory_system.store(
        content=validated,
        modality=ModalityType.STRUCTURAL_PATTERN,
        metadata={'source': 'ROBO_EXPORT'}
    )
```

---

## 8. Proximas Melhorias Planejadas

1. **Predicao de configuracao**: Usar ML para sugerir valores
2. **Validacao automatica**: Verificar consistencia de dados
3. **Export batch**: Exportar multiplos elementos de uma vez
4. **Preview de SCR**: Visualizar antes de gerar
