# SPEC-PILARES — Extração de Pilares do DXF
## Especificação Operacional para CAD-ANALYZER
**Fonte da verdade: agente_estrutural.py + ficha_pilares_schema.py | 2026-03-19**

---

## SEÇÃO 1 — IDENTIFICAÇÃO DO PILAR NO DXF

### 1.1 Detecção por Texto (TEXT / MTEXT)

O robô detecta um pilar quando encontra um texto que bate com `RE_PILAR`:

```python
import re

RE_PILAR = re.compile(
    r'^(PC?\.?-?\d+([A-Z]|\.\d+|-\d+)?|P-\d+[A-Z]?)$',
    re.IGNORECASE
)

# Exemplos que CASAM:
# P1, P17, P101, PC1, P-1, P1A, P.1, P-1A

# Exemplos que NÃO casam (não são pilares):
# PL1 (planta), PD1 (detalhe), P (sem número), PONTALETE
```

### 1.2 Extração do Texto do DXF

```python
import ezdxf

doc = ezdxf.readfile("arquivo.dxf")
msp = doc.modelspace()

pilares_txt = []

for e in msp:
    etype = e.dxftype()

    if etype == 'TEXT':
        text = getattr(e.dxf, 'text', '').strip()
        x = float(e.dxf.insert.x)
        y = float(e.dxf.insert.y)
        layer = e.dxf.layer

    elif etype == 'MTEXT':
        text = None
        for method in ('plain_text', 'plain_mtext'):
            fn = getattr(e, method, None)
            if callable(fn):
                result = fn()
                if result:
                    text = str(result).strip()
                    break
        if text is None:
            raw = getattr(e.dxf, 'text', '') or ''
            text = re.sub(r'\\[A-Za-z][^;]*;', '', raw)
            text = re.sub(r'\\[\\{}|]', '', text).strip()
        x = float(e.dxf.insert.x)
        y = float(e.dxf.insert.y)
        layer = e.dxf.layer

    else:
        continue

    if text and RE_PILAR.match(text):
        pilares_txt.append({'text': text, 'x': x, 'y': y, 'layer': layer})
```

**Layer esperado para IDs de pilares:** `NOMENCLATURA` (14/14 arquivos) ou `TEXTO_GERAL`

### 1.3 Associação Texto → Polilinha (3-Radius Logic)

Após detectar o texto "P17", o robô busca a LWPOLYLINE fechada mais próxima:

```python
from shapely.geometry import Polygon, Point
import math

PILAR_SEARCH_RADIUS = 800.0  # mm

def associar_pilar(pilar_txt, polylines):
    """Retorna (polilinha, confidence) para um texto de pilar."""
    px, py = pilar_txt['x'], pilar_txt['y']
    melhor = None
    melhor_score = 0.0

    for poly in polylines:
        if not poly['closed'] or len(poly['points']) < 3:
            continue  # apenas polilinhas FECHADAS

        polygon = Polygon(poly['points'])
        ponto = Point(px, py)
        dist = polygon.distance(ponto)

        # --- LÓGICA DE 3 RAIOS ---
        if polygon.contains(ponto):
            score = 1.0                              # Raio 1: texto DENTRO
        elif dist <= 5.0:
            score = 0.8                              # Raio 2: tocando/adjacente
        elif dist <= PILAR_SEARCH_RADIUS:
            decay = 1.0 - (dist / PILAR_SEARCH_RADIUS)
            score = 0.5 * decay                      # Raio 3: decaimento linear
        else:
            continue

        if score > melhor_score:
            melhor_score = score
            melhor = poly

    return melhor, melhor_score
```

**Regra de auto-assign:** `confidence >= 0.80` → aceitar automaticamente.
**Abaixo de 0.80:** enviar para fila de revisão humana (`precisa_revisao=True`).

---

## SEÇÃO 2 — EXTRAÇÃO DOS CAMPOS JSON

### 2.1 Todos os campos de `FichaFase3Pilar`

```python
# Schema completo (src/pipeline/ficha_pilares_schema.py)
{
    "id": "P17",           # texto original do DXF
    "numero": "17",        # apenas dígitos do id
    "pavimento": "TERREO", # nome do arquivo DXF (sem extensão)
    "pavimento_numero": 0, # 0=térreo, 1=1°pav, 2=2°pav...
    "obra": "ALIMONTI-PARAISO",  # pasta raiz da obra

    # Seção transversal (cm) — extraídas de RE_DIM
    "comprimento": 40.0,   # MAIOR dimensão
    "largura": 20.0,       # MENOR dimensão

    # Altura e nível
    "altura_cm": 280.0,    # nivel_chegada - nivel_saida (cm)
    "nivel_saida_m": 0.0,  # cota do piso do pavimento (m)
    "nivel_chegada_m": 2.80, # cota do teto (m)
    "pavimento_anterior": "", # nome do pavimento abaixo

    # Armadura longitudinal (barras por trecho entre pisos)
    "par_1_2": "8",  # 8 barras no trecho piso1→piso2
    "par_2_3": "0",
    "par_3_4": "0",
    "par_4_5": "0",
    "par_5_6": "0",
    "par_6_7": "0",
    "par_7_8": "0",
    "par_8_9": "0",

    # Armadura transversal (estribos)
    "grade_1": "8",     # diâmetro da barra em mm
    "distancia_1": "10", # espaçamento em cm
    "grade_2": "",
    "distancia_2": "",
    "grade_3": "",

    # Pilar especial
    "pilar_especial": False,  # True = L, T, ou CAMBOTADO
    "tipo_pilar_especial": "L",

    # Metadados (internos — não vão para o robô final)
    "confidence": 0.92,
    "revisado_por_humano": False
}
```

### 2.2 Como Extrair `comprimento` e `largura`

Busca texto de dimensão dentro de `DIM_SEARCH_RADIUS = 600mm` do centro do pilar:

```python
RE_DIM = re.compile(r'(\d{1,3})\s*[xX*\/]\s*(\d{1,3})')
RE_DIM_BH = re.compile(r'b\s*=\s*(\d{1,3}).*?h\s*=\s*(\d{1,3})', re.IGNORECASE | re.DOTALL)

DIM_SEARCH_RADIUS = 600.0  # mm

def extrair_dimensoes(pilar_center, texts):
    """
    Retorna (comprimento, largura) do pilar em cm.
    comprimento = lado maior, largura = lado menor.
    """
    cx, cy = pilar_center

    for t in texts:
        if abs(t['x'] - cx) > DIM_SEARCH_RADIUS:
            continue
        if abs(t['y'] - cy) > DIM_SEARCH_RADIUS:
            continue

        # Formato "20x50" ou "20X50" ou "20*50"
        m = RE_DIM.search(t['text'])
        if m:
            d1, d2 = float(m.group(1)), float(m.group(2))
            return max(d1, d2), min(d1, d2)

        # Formato "b=20 h=50"
        m = RE_DIM_BH.search(t['text'])
        if m:
            d1, d2 = float(m.group(1)), float(m.group(2))
            return max(d1, d2), min(d1, d2)

    return 0.0, 0.0  # não encontrado → revisão humana
```

### 2.3 Como Extrair `nivel_saida_m` e `nivel_chegada_m`

```python
RE_NIVEL = re.compile(r'[Nn][ií]vel\s*[=:]?\s*([+-]?\d+[.,]\d+)', re.IGNORECASE)
# Exemplo: "Nível +2,80" → 2.80
# Exemplo: "h = 2.80" em layer NIVEL

def extrair_nivel(texts, layer_target='NIVEL'):
    for t in texts:
        if t['layer'].upper() == layer_target.upper():
            m = RE_NIVEL.search(t['text'])
            if m:
                val = m.group(1).replace(',', '.')
                return float(val)
    return None
```

### 2.4 Como Calcular `numero` a Partir de `id`

```python
def extrair_numero(pilar_id: str) -> str:
    """'P17' → '17', 'PC3' → '3', 'P-1A' → '1'"""
    return ''.join(filter(str.isdigit, pilar_id)) or '0'
```

### 2.5 Pilar Especial — Cambotado

```python
def detectar_cambotado(polyline_entity) -> tuple[bool, str]:
    """
    Retorna (pilar_especial, tipo_pilar_especial).
    Bulge = fator de curvatura de segmento LWPOLYLINE.
    """
    bulges = []
    try:
        bulges = [float(p[4]) if len(p) > 4 else 0.0
                  for p in polyline_entity.get_points('xyzsb')]
    except Exception:
        return False, 'L'

    max_bulge = max((abs(b) for b in bulges), default=0.0)

    if max_bulge > 0.3:
        return True, 'CAMBOTADO'
    elif max_bulge > 0.01:
        return True, 'L'   # possível pilar em L ou T com aresta suave
    return False, 'L'
```

---

## SEÇÃO 3 — VALIDAÇÃO DOS CAMPOS

| Campo | Range Válido | Ação se Inválido |
|---|---|---|
| `comprimento` | 10 – 200 cm | `confidence -= 0.3`, fila revisão |
| `largura` | 10 – 150 cm | `confidence -= 0.3`, fila revisão |
| `altura_cm` | 100 – 600 cm | `confidence -= 0.2`, fila revisão |
| `nivel_saida_m` | -5.0 – 50.0 m | aceitar, avisar |
| `comprimento >= largura` | obrigatório | trocar valores |
| `confidence` | 0.0 – 1.0 | clamp a 0.0 ou 1.0 |

```python
def validar_pilar(ficha: dict) -> list[str]:
    erros = []
    if ficha['comprimento'] <= 0:
        erros.append(f"comprimento inválido: {ficha['comprimento']}")
    if ficha['largura'] <= 0:
        erros.append(f"largura inválida: {ficha['largura']}")
    if ficha['altura_cm'] <= 0:
        erros.append(f"altura inválida: {ficha['altura_cm']}")
    if ficha['comprimento'] < ficha['largura']:
        # Convenção: comprimento é sempre o MAIOR lado
        ficha['comprimento'], ficha['largura'] = ficha['largura'], ficha['comprimento']
    return erros
```

---

## SEÇÃO 4 — EXEMPLOS REAIS (DXF → JSON)

### Exemplo 1 — ALIMONTI (família BIM)

**DXF input:**
```
TEXT layer=NOMENCLATURA  text="P17"  insert=(17799, 3038)
TEXT layer=cotas         text="20x50"  insert=(17830, 3000)
LWPOLYLINE layer=Painéis  closed=True
  vertices=[(17770,3010),(17820,3010),(17820,3066),(17770,3066)]
```

**JSON output:**
```json
{
  "id": "P17",
  "numero": "17",
  "comprimento": 50.0,
  "largura": 20.0,
  "confidence": 1.0
}
```
*(texto "P17" está DENTRO da polilinha → Raio 1 → score=1.0)*

---

### Exemplo 2 — Pilar com texto adjacente

**DXF input:**
```
TEXT layer=NOMENCLATURA  text="P5"  insert=(16200, 2500)
TEXT layer=Texto Seção   text="25x40"  insert=(16250, 2450)
LWPOLYLINE layer=Painéis  closed=True
  vertices=[(16350,2400),(16400,2400),(16400,2440),(16350,2440)]
  # texto P5 está a 170mm do centro da polilinha
```

**Cálculo:**
```python
dist = 170  # mm
score = 0.5 * (1.0 - 170/800) = 0.5 * 0.7875 = 0.394
# → confidence = 0.394 < 0.80 → revisão humana obrigatória
```

---

### Exemplo 3 — Pilar cambotado

**DXF input:**
```
TEXT layer=NOMENCLATURA  text="PC1"  insert=(5000, 5000)
LWPOLYLINE layer=Painéis  closed=True
  vertices=[(4950,4950),(5050,4950),(5050,5050),(4950,5050)]
  bulges=[0.0, 0.45, 0.0, 0.0]   # segmento 2 é curvo
```

**JSON output:**
```json
{
  "id": "PC1",
  "pilar_especial": true,
  "tipo_pilar_especial": "CAMBOTADO",
  "confidence": 0.95
}
```

---

## SEÇÃO 5 — CASOS ESPECIAIS

### Pilar sem texto de dimensão próximo
```
Situação: P1 detectado, mas nenhum texto "NNxMM" em raio de 600mm
Ação: comprimento=0, largura=0, confidence -= 0.4
Log: "P1: dimensão não encontrada (DIM_SEARCH_RADIUS=600mm)"
```

### Dois textos competindo pelo mesmo polígono
```
Situação: "P1" e "P2" ambos dentro de 800mm do mesmo polígono
Ação: vence o que tem score maior (Raio 1 > Raio 2 > Raio 3)
Empate: fila de revisão humana
```

### Pilar em layer desconhecido
```
Situação: LWPOLYLINE fechada em layer "00-FELIPE" (não é Painéis)
Ação: processar normalmente — layer da polilinha não bloqueia extração
Nota: a polilinha é válida independente do layer; o que importa é is_closed=True
```

### Encoding de layer (problema real)
```python
# "Painéis" pode chegar como "Pain?is" ou "Pain\xc3\xa9is"
# Usar normalização:
import unicodedata
def norm(s):
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().upper()

# norm("Painéis") == norm("Pain?is") == "PAINEIS"
```

---

*SPEC-PILARES v1.0 | 5 seções | Fonte: agente_estrutural.py + ficha_pilares_schema.py*
