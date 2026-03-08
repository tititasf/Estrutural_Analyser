# 📋 Contextualização: Lista de Vigas, Campo SEGMENTOS e Abas A/B de FUNDOS

## 🎯 Visão Geral

Este documento contextualiza três componentes críticos do sistema AgenteCAD:
1. **Lista de Vigas do Estrutural Analyzer** (`main.py`)
2. **Campo SEGMENTOS** (completamente)
3. **Abas A e B de FUNDOS** (Robo Fundos de Vigas)

---

## 1. 📊 LISTA DE VIGAS DO ESTRUTURAL ANALYZER

### 1.1 Localização e Estrutura

**Arquivo Principal:** `main.py`  
**Método de Setup:** `_setup_structural_analyzer_area()` (linha ~956)  
**Widget:** `self.list_beams` (QTreeWidget)

### 1.2 Estrutura da Lista

```python
# main.py linha ~1147-1152
self.list_beams = QTreeWidget()
self.list_beams.setHeaderLabels(["Item", "Nome", "Status", "%"])
self.list_beams.setColumnWidth(0, 50)   # Item
self.list_beams.setColumnWidth(1, 120)  # Nome
self.list_beams.setColumnWidth(2, 50)   # Status
self.list_beams.setColumnWidth(3, 50)   # %
```

### 1.3 Colunas da Lista

| Coluna | Descrição | Tipo | Largura |
|--------|-----------|------|---------|
| **Item** | Número sequencial da viga | Integer | 50px |
| **Nome** | Identificação da viga (ex: V1, V-1) | String | 120px |
| **Status** | Estado de processamento | String | 50px |
| **%** | Percentual de completude | Float | 50px |

### 1.4 Integração com Abas

A lista de vigas está dentro de um sistema de abas hierárquico:

```
Structural Analyzer (Módulo Principal)
└── main_tabs (QTabWidget)
    └── tab_analysis (Aba "Análise Atual")
        └── tabs_analysis_internal (QTabWidget)
            ├── "Pilares" → list_pillars
            ├── "Vigas" → list_beams ⭐ (Nossa lista)
            ├── "Lajes" → list_slabs
            └── "⚠️ Pendências" → list_issues
```

### 1.5 Eventos e Conectores

```python
# main.py linha ~1168-1169
self.list_beams.itemClicked.connect(self.on_list_beam_clicked)
self.list_beams.currentItemChanged.connect(
    lambda curr, prev: self.on_list_beam_clicked(curr, 0) if curr else None
)
```

**Ações ao clicar:**
- Seleciona a viga no canvas
- Atualiza o DetailCard com informações da viga
- Carrega dados de segmentos (Lado A, Lado B, Fundo)

### 1.6 Processamento de Vigas

**Método Principal:** `_process_beam_intelligent()` (linha ~3825)

**Fluxo de Processamento:**
1. **Identificação Geométrica:**
   - Linhas classificadas como `seg_side_a` e `seg_side_b`
   - Textos de dimensão associados
   - Suportes (pilares, vigas, paredes)

2. **Cálculo de Segmentos:**
   ```python
   # main.py linha ~3874-3892
   def process_segments(side_key, tag):
       lines = classified.get(side_key, [])
       total_len = 0
       for line in lines:
           p1, p2 = line[0], line[-1]
           length = ((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)**0.5
           total_len += length
           b['links']['viga_segs'][side_key].append({
               'type': 'poly', 'points': line, 'len': length, 'tag': tag
           })
       return total_len
   
   len_a = process_segments('seg_side_a', 'Lado A')
   len_b = process_segments('seg_side_b', 'Lado B')
   b['fields']['comprimento_total_a'] = round(len_a, 1)
   b['fields']['comprimento_total_b'] = round(len_b, 1)
   b['seg_a'] = len(classified.get('seg_side_a', []))
   b['seg_b'] = len(classified.get('seg_side_b', []))
   ```

3. **Campos Gerados:**
   - `comprimento_total_a`: Comprimento total do Lado A
   - `comprimento_total_b`: Comprimento total do Lado B
   - `seg_a`: Quantidade de segmentos do Lado A
   - `seg_b`: Quantidade de segmentos do Lado B

### 1.7 Sincronização com Robôs

**Botões de Sincronização** (linha ~1104-1113):
- **"🤖 Sincronizar Laterais de Vigas"**: Envia para `Robo_Laterais_de_Vigas`
- **"🤖 Sincronizar Fundo de Vigas"**: Envia para `Robo_Fundos_de_Vigas`

---

## 2. 🔗 CAMPO SEGMENTOS (Completamente)

### 2.1 Definição Conceitual

**Segmento** = Trecho de viga entre dois conflitos (pilares, vigas cruzadas, ou fim da viga).

### 2.2 Estrutura de Dados

**No Estrutural Analyzer (`main.py`):**
```python
b['links']['viga_segs'] = {
    'seg_side_a': [
        {
            'type': 'poly',
            'points': [(x1, y1), (x2, y2), ...],
            'len': 150.5,
            'tag': 'Lado A',
            'dim_text': '14x60'  # Opcional: dimensão específica do segmento
        },
        ...
    ],
    'seg_side_b': [...],
    'seg_bottom': [...]  # Segmentos do fundo
}
```

**No Robo Laterais (`robo_laterais_viga_pyside.py`):**
```python
@dataclass
class VigaState:
    segment_class: str = "Lista Geral"  # Classe de agrupamento
    side: str = "A"  # Lado da viga (A ou B)
    continuation: str = "Proxima Parte"  # Tipo de continuação
```

### 2.3 Classificação de Segmentos

**Tipos de Segmentos:**

1. **Segmentos Laterais (Lado A/B):**
   - `seg_side_a`: Linhas do lado A da viga
   - `seg_side_b`: Linhas do lado B da viga
   - Processados em `_process_beam_intelligent()` (linha ~3874)

2. **Segmentos de Fundo:**
   - `seg_bottom`: Linhas do fundo da viga
   - Usados para cálculo de área de fundo

3. **Segmentos de Continuação:**
   - `seg_cont`: Segmento de viga que continua após um pilar
   - Usado no contexto de pilares

### 2.4 Campo `segment_class` (Robo Laterais)

**Localização:** `_ROBOS_ABAS/Robo_Laterais_de_Vigas/robo_laterais_viga_pyside.py` (linha ~97)

**Propósito:** Agrupar vigas relacionadas (ex: V1, V1a, V1b, V1c)

**Valores Comuns:**
- `"Lista Geral"`: Padrão para vigas não agrupadas
- `"V1"`, `"V2"`, etc.: Agrupamento por viga base
- `"V1A"`, `"V1B"`: Agrupamento com sufixo de lado

**Uso na Lista:**
```python
# robo_laterais_viga_pyside.py linha ~8031-8077
def update_vigas_list(self):
    """Update tree1 with vigas grouped by Segment Class"""
    self.viga_grouping = {}
    
    for pav_name in target_pavs:
        for viga_name, vstate in pavimentos[pav_name].get('vigas', {}).items():
            cls = getattr(vstate, 'segment_class', 'Lista Geral')
            if cls not in self.viga_grouping:
                self.viga_grouping[cls] = []
            self.viga_grouping[cls].append((viga_name, vstate, pav_name))
```

**Hierarquia na Árvore:**
```
Lista Geral
├── V1.A
├── V1.B
└── V2.A
V1
├── V1a.A
├── V1b.A
└── V1c.A
```

### 2.5 Processamento de Segmentos no LinkManager

**Arquivo:** `src/ui/widgets/link_manager.py` (linha ~73-76)

**Definição de Links:**
```python
'_viga_segs': [
    {'id': 'seg_side_a', 'name': 'Segmentos Lado A', 'type': 'poly', 
     'prompt': 'Desenhe os segmentos do Lado A. [Enter] para finalizar.', 
     'help': 'Linhas do lado A da viga.'},
    {'id': 'seg_side_b', 'name': 'Segmentos Lado B', 'type': 'poly', 
     'prompt': 'Desenhe os segmentos do Lado B. [Enter] para finalizar.', 
     'help': 'Linhas do lado B da viga.'},
    {'id': 'seg_bottom', 'name': 'Segmentos Fundos', 'type': 'poly', 
     'prompt': 'Desenhe os segmentos do Fundo. [Enter] para finalizar.', 
     'help': 'Linhas do fundo da viga.'}
]
```

### 2.6 Visualização no DetailCard

**Arquivo:** `src/ui/widgets/detail_card.py` (linha ~1259-1303)

**Estrutura de Abas:**
```python
def _setup_viga_complex_view(self, layout):
    """Implementa detalhamento rigoroso de Lado A, Lado B e Fundo"""
    tabs = QTabWidget()
    sides_config = [
        ('A', 'Lado A', False), 
        ('B', 'Lado B', False), 
        ('Fundo', 'Fundo', True)
    ]
    
    for side, label, is_bottom in sides_config:
        # Container de Segmentos Rica
        for i in sorted(list(existing_indices)):
            self._add_rich_segment_pack(segs_layout, prefix, i)
```

**Campos por Segmento:**
- Nome do conflito inicial
- Tipo do conflito inicial
- Distância até o conflito
- Nome do conflito final
- Tipo do conflito final
- Tamanho do conflito
- Distância após conflito

---

## 3. 🏗️ ABAS A E B DE FUNDOS

### 3.1 Localização

**Arquivo Principal:** `_ROBOS_ABAS/Robo_Fundos_de_Vigas/compactador-producao/fundo_pyside.py`  
**Classe:** `FundoMainWindow` (linha ~417)  
**Método de Setup:** `setup_ui()` (linha ~1800)

### 3.2 Estrutura da Interface

**Layout Principal:**
```
FundoMainWindow
├── LEFT: Lista de Vigas (tree_fundos)
├── CENTER: Visualização (canvas)
└── RIGHT: Comandos + Detalhes (tabs_details)
```

### 3.3 Abas de Detalhes

**Widget:** `self.tabs_details` (QTabWidget, linha ~1980)

**Abas Disponíveis:**
1. **"Geral"** (tab_geral): Informações básicas
2. **"Painéis"** (tab_paineis): Configuração de painéis
3. **"Recuos"** (tab_recuos): Chanfros e aberturas
4. **"Painel L"** (tab_l): Configurações especiais para formato L

### 3.4 Diferença: Abas A/B vs Abas de Detalhes

⚠️ **IMPORTANTE:** As "Abas A e B" referem-se ao **LADO DA VIGA**, não às abas do QTabWidget.

**No Robo Fundos:**
- Cada viga pode ter **Fundo do Lado A** e **Fundo do Lado B**
- Isso é controlado pelo campo `side` no `VigaState` (Robo Laterais)
- O Robo Fundos processa ambos os lados quando sincronizado

### 3.5 Processamento de Lados A e B

**Sincronização do Estrutural Analyzer:**
```python
# main.py linha ~1110-1113
btn_fundo = QPushButton("🤖 Sincronizar Fundo de Vigas")
btn_fundo.clicked.connect(self.sync_beams_to_fundo_action)
```

**Dados Enviados:**
```python
# Cada viga tem:
{
    "nome": "V1.A",  # Sufixo .A ou .B indica o lado
    "largura": 14,
    "comprimento": 300,
    "segmentos": [...],
    "side": "A"  # ou "B"
}
```

### 3.6 Agrupamento por Segmentos Sequenciais

**Método:** `_agrupar_segmentos_sequenciais()` (linha ~984)

**Propósito:** Agrupar fundos de vigas com sufixos sequenciais (V1a, V1b, V1c)

```python
def _agrupar_segmentos_sequenciais(self, fundos_dict):
    # Agrupa por base (ex: "V1") e ordena sequencialmente
    grupos = {}
    for nome, dados in fundos_dict.items():
        base = re.match(r'^(.+?)([a-z])?$', nome).group(1)
        if base not in grupos:
            grupos[base] = []
        grupos[base].append((nome, dados))
    
    # Ordenar segmentos dentro de cada grupo
    for base in grupos:
        grupos[base].sort(key=lambda x: x[0])
```

### 3.7 Geração de Scripts por Lado

**Método:** `_gerar_script_segmento()` (linha ~914)

**Comportamento:**
- Gera scripts separados para cada lado (A e B)
- Agrupa segmentos sequenciais do mesmo lado
- Cria arquivos `.scr` para execução no AutoCAD

### 3.8 Campos Específicos por Lado

**No Robo Fundos, cada fundo tem:**
- **Largura**: Largura da viga (cm)
- **Comprimento**: Comprimento total do fundo (cm)
- **Painéis**: 6 painéis configuráveis (P1-P6)
- **Sarrafos**: Sarrafos verticais (esquerda/direita)
- **Recuos**: 4 recuos (T/E, F/E, T/D, F/D)
- **Aberturas**: 4 aberturas com 3 dimensões cada

**Diferença entre Lado A e B:**
- Mesma estrutura de dados
- Processamento independente
- Scripts gerados separadamente
- Agrupamento por `segment_class` considera ambos os lados

---

## 4. 🔄 FLUXO COMPLETO: Estrutural Analyzer → Robo Fundos

### 4.1 Fluxo de Dados

```
1. Estrutural Analyzer (main.py)
   ├── Processa DXF
   ├── Identifica Vigas
   ├── Calcula Segmentos (Lado A, Lado B)
   └── Armazena em beams_found[]

2. Usuário clica "🤖 Sincronizar Fundo de Vigas"
   └── sync_beams_to_fundo_action()

3. Dados Transformados
   ├── Para cada viga em beams_found:
   │   ├── Extrai segmentos do Lado A
   │   ├── Extrai segmentos do Lado B
   │   ├── Calcula comprimento total
   │   └── Cria entrada no Robo Fundos
   └── Envia para FundoMainWindow

4. Robo Fundos (fundo_pyside.py)
   ├── Recebe dados
   ├── Agrupa por segment_class
   ├── Exibe na tree_fundos
   └── Permite edição e geração de scripts
```

### 4.2 Estrutura de Dados de Sincronização

```python
# Dados enviados do Estrutural Analyzer para Robo Fundos
fundo_data = {
    "nome": "V1.A",  # Nome + sufixo do lado
    "numero": "1",
    "pavimento": "P-1",
    "largura": 14.0,
    "altura": 60.0,
    "comprimento": 300.0,  # Soma dos segmentos
    "segment_class": "V1",
    "side": "A",
    "segmentos": [
        {"inicio": "P-1", "fim": "P-2", "comprimento": 150.0},
        {"inicio": "P-2", "fim": "P-3", "comprimento": 150.0}
    ],
    "texto_esq": "P-1",
    "texto_dir": "P-3"
}
```

---

## 5. 📝 RESUMO EXECUTIVO

### 5.1 Lista de Vigas (Estrutural Analyzer)
- **Widget:** `QTreeWidget` com 4 colunas (Item, Nome, Status, %)
- **Localização:** Aba "Vigas" dentro de "Análise Atual"
- **Função:** Lista todas as vigas detectadas no DXF
- **Ações:** Seleção, sincronização com robôs, criação de comandos LISP

### 5.2 Campo SEGMENTOS
- **Definição:** Trechos de viga entre conflitos
- **Tipos:** `seg_side_a`, `seg_side_b`, `seg_bottom`
- **Campo `segment_class`:** Agrupa vigas relacionadas (V1, V1a, V1b)
- **Processamento:** Cálculo automático de comprimentos e quantidades

### 5.3 Abas A e B de FUNDOS
- **Conceito:** Lados da viga (A e B), não abas do QTabWidget
- **Processamento:** Independente para cada lado
- **Agrupamento:** Por `segment_class` considerando ambos os lados
- **Geração:** Scripts separados para cada lado e segmento sequencial

---

## 6. 🔍 REFERÊNCIAS DE CÓDIGO

### Arquivos Principais:
- `main.py`: Estrutural Analyzer, lista de vigas, processamento
- `_ROBOS_ABAS/Robo_Laterais_de_Vigas/robo_laterais_viga_pyside.py`: Campo `segment_class`
- `_ROBOS_ABAS/Robo_Fundos_de_Vigas/compactador-producao/fundo_pyside.py`: Interface de fundos
- `src/ui/widgets/link_manager.py`: Definição de links de segmentos
- `src/ui/widgets/detail_card.py`: Visualização de segmentos no DetailCard

### Métodos Chave:
- `_setup_structural_analyzer_area()`: Setup da lista de vigas
- `_process_beam_intelligent()`: Processamento de segmentos
- `update_vigas_list()`: Atualização da lista no Robo Laterais
- `_agrupar_segmentos_sequenciais()`: Agrupamento no Robo Fundos

---

**Última Atualização:** 2025-01-22  
**Autor:** Sistema AgenteCAD - Contextualização Automática
