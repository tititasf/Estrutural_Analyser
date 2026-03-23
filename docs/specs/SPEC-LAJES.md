# SPEC-LAJES — Extração de Lajes do DXF
## Especificação Operacional para CAD-ANALYZER
**Fonte da verdade: agente_estrutural.py + ficha_lajes_schema.py | 2026-03-19**

---

## SEÇÃO 1 — IDENTIFICAÇÃO DA LAJE NO DXF

### 1.1 Detecção por Texto — Dois Caminhos

**Caminho A: Texto de ID explícito (L1, L2, Y1...)**

```python
import re

RE_LAJE = re.compile(
    r'^(L\d+[A-Za-z]?|Y\d+[A-Za-z]?|X\d+[A-Za-z]?|LAJ[-_]?\d+|LAJE[-_\s]*\d+)$',
    re.IGNORECASE
)

# Exemplos que CASAM: L1, L12, L1A, Y1, X2, LAJ-1, LAJE 1, LAJE_2
# Exemplos que NÃO casam: L (sem número), LAJE (sem número)
```

**Caminho B: Espessura h= (laje sem ID explícito)**

```python
RE_LAJE_H = re.compile(r'h\s*[=:]\s*([\d,.]+)', re.IGNORECASE)
# Exemplos: "h=12", "h = 14", "h:10", "h=12cm"
# → espessura em cm
```

**LAJE SINTÉTICA:** Quando não há texto L1/L2 mas há clusters de `h=`:
```python
CLUSTER_RADIUS = 500.0  # mm — raio para agrupar h= próximos

# Se múltiplos "h=12" dentro de 500mm → geram 1 laje SYNTHETIC
# LajeDXF.name = "SYNTHETIC", LajeDXF.id = "synth_0", "synth_1"...
```

### 1.2 Extração dos Textos

```python
LAJE_SEARCH_RADIUS = 1500.0  # mm — maior raio (lajes são grandes)

lajes_txt = []
laje_dims = []  # textos "h=NN"

for e in msp:
    etype = e.dxftype()
    if etype not in ('TEXT', 'MTEXT'):
        continue

    if etype == 'TEXT':
        text = getattr(e.dxf, 'text', '').strip()
        x, y = float(e.dxf.insert.x), float(e.dxf.insert.y)
        layer = e.dxf.layer
    else:
        text = ''
        for method in ('plain_text', 'plain_mtext'):
            fn = getattr(e, method, None)
            if callable(fn):
                result = fn()
                if result:
                    text = str(result).strip()
                    break
        if not text:
            raw = getattr(e.dxf, 'text', '') or ''
            text = re.sub(r'\\[A-Za-z][^;]*;', '', raw).strip()
        x, y = float(e.dxf.insert.x), float(e.dxf.insert.y)
        layer = e.dxf.layer

    # Checar h= (espessura)
    m_h = RE_LAJE_H.search(text)
    if m_h:
        val = float(m_h.group(1).replace(',', '.'))
        laje_dims.append({'text': text, 'x': x, 'y': y, 'layer': layer, 'h_val': val})

    # Checar ID de laje
    if text.upper().startswith(('L', 'Y', 'X', 'LAJ')):
        text_clean = re.sub(r'h\s*[=:]\s*[\d,.]+', '', text).strip()
        if RE_LAJE.match(text_clean):
            lajes_txt.append({'text': text_clean, 'x': x, 'y': y, 'layer': layer})
```

### 1.3 Layers Críticos de Laje

| Layer | Canonical | Função |
|---|---|---|
| `EST-LAJE-TEXT` | `SLAB_TEXT` | **IDs de lajes** (L1, L2…) → principal |
| `NOMENCLATURA` | `ELEMENT_LABEL` | IDs de lajes (alternativo) |
| `Pilares` | `PILLAR_CUTOUT` | **Recortes de pilares no contorno da laje** |
| `VIGAS` | `BEAM_INTERFACE` | Interface de vigas na laje |
| `REAPROVEITAMENTO` | `REUSE_STATUS` | Estado de reaproveitamento (BOM/REGULAR/RUIM) |
| `SARRAFO DE PRESSAO` | `PRESSURE_BATTEN` | Sarrafo de pressão |
| `Vázio` / `V?zio` | `VOID_OPENING` | **Vazios e aberturas** ⚠️ encoding! |
| `EST-PILAR-CUT` | `PILLAR_CUT` | Contorno de corte de pilar |
| `Painéis` / `Pain?is` | `PANEL_GEOMETRY` | Painéis de fundo de laje |

### 1.4 Contorno da Laje — LWPOLYLINE

```python
for e in msp.query("LWPOLYLINE"):
    pts = [(float(p[0]), float(p[1])) for p in e.get_points('xy')]
    is_closed = (getattr(e.dxf, 'flags', 0) & 1 == 1) or e.is_closed

    if is_closed and len(pts) >= 3:
        # Pode ser pilar, laje ou outline de viga
        # Discriminar pelo tamanho:
        from shapely.geometry import Polygon
        area = Polygon(pts).area

        if area > 50000:   # > 50.000 mm² → provável LAJE
            pass           # candidato a contorno de laje
        elif area < 5000:  # < 5.000 mm² → provável PILAR
            pass
        # Associar via texto mais próximo (RE_LAJE ou RE_PILAR)
```

---

## SEÇÃO 2 — EXTRAÇÃO DOS CAMPOS JSON

### 2.1 Schema completo `FichaFase3Laje`

```python
{
    "codigo": "L5",               # texto original do DXF (ou "synth_0")
    "pavimento": "1_PAVIMENTO",   # nome do arquivo DXF
    "obra_nome": "ALIMONTI-PARAISO",

    "tipo": "macica",             # "macica" | "pre_moldada" | "steel_deck"
    "espessura": 12.0,            # cm — extraído de "h=12"

    "dimensoes": {
        "comprimento": 620.0,     # cm — bbox do contorno
        "largura": 430.0,         # cm — bbox do contorno
        "espessura": 12.0         # cm
    },

    # Contorno como lista de vértices [{x,y}] em mm (coordenadas DXF)
    "outline_segs": [
        {"x": 15000.0, "y": 10000.0},
        {"x": 21200.0, "y": 10000.0},
        {"x": 21200.0, "y": 14300.0},
        {"x": 15000.0, "y": 14300.0}
    ],

    "nivel": 2.80,                # cota m — do layer NIVEL ou pavimento

    "armadura": {
        "tipo": "bidirecional",
        "diametro": 10,           # mm
        "espacamento": 20,        # cm
        "direcao": "XY"
    },

    # Elementos vizinhos (inferidos por proximidade)
    "vigas_around": ["V101", "V102", "V103", "V104"],
    "pilares_around": ["P5", "P6", "P7", "P8"],

    "confidence": 0.70,
    "revisado": False
}
```

### 2.2 Como Extrair `espessura` de h=

```python
def extrair_espessura(texts, laje_pos, raio=LAJE_SEARCH_RADIUS):
    """Retorna espessura em cm a partir de texto "h=NN" mais próximo."""
    lx, ly = laje_pos
    candidatos = []

    for t in texts:
        m = RE_LAJE_H.search(t['text'])
        if m:
            dist = math.hypot(t['x'] - lx, t['y'] - ly)
            if dist <= raio:
                val = float(m.group(1).replace(',', '.'))
                candidatos.append((val, dist))

    if candidatos:
        candidatos.sort(key=lambda x: x[1])  # mais próximo primeiro
        return candidatos[0][0]
    return 0.0
```

**Valores válidos de espessura:** 7 – 40 cm (abaixo de 7 cm: inválido por norma)

### 2.3 Área por Fórmula Shoelace

```python
def calcular_area_shoelace(pts: list) -> float:
    """Área em mm². Divide por 1e6 para m²."""
    n = len(pts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return abs(area) / 2.0

# Uso:
area_mm2 = calcular_area_shoelace(outline_pts)
area_m2 = area_mm2 / 1_000_000
```

### 2.4 Laje Sintética (sem ID explícito)

```python
def gerar_lajes_sinteticas(laje_dims: list) -> list:
    """
    Agrupa textos "h=NN" por proximidade → laje SYNTHETIC por cluster.
    Usado quando não há texto L1, L2... explícito.
    """
    if not laje_dims:
        return []

    used = set()
    clusters = []

    for i, d in enumerate(laje_dims):
        if i in used:
            continue
        cluster = [d]
        used.add(i)
        for j, d2 in enumerate(laje_dims):
            if j in used:
                continue
            dist = math.hypot(d['x'] - d2['x'], d['y'] - d2['y'])
            if dist < CLUSTER_RADIUS:
                cluster.append(d2)
                used.add(j)
        clusters.append(cluster)

    sinteticas = []
    for idx, cluster in enumerate(clusters):
        cx = sum(d['x'] for d in cluster) / len(cluster)
        cy = sum(d['y'] for d in cluster) / len(cluster)
        h_val = cluster[0]['h_val']  # espessura do primeiro elemento do cluster
        sinteticas.append({
            'id': f'synth_{idx}',
            'name': 'SYNTHETIC',
            'x': cx, 'y': cy,
            'espessura': h_val,
            'confidence': 0.50  # lajes sintéticas têm confidence reduzida
        })
    return sinteticas
```

### 2.5 Recortes de Pilares na Laje

```python
def detectar_recortes_pilares(laje_contorno, polylines):
    """
    Identifica LWPOLYLINE fechadas em layer "Pilares" ou "EST-PILAR-CUT"
    que intersectam o contorno da laje.
    """
    from shapely.geometry import Polygon

    laje_poly = Polygon(laje_contorno)
    recortes = []

    for poly in polylines:
        if not poly['closed']:
            continue

        layer_norm = norm(poly['layer'])
        if layer_norm not in ('PILARES', 'EST-PILAR-CUT', 'PILLAR-CUT'):
            continue

        recorte_poly = Polygon(poly['points'])
        if laje_poly.intersects(recorte_poly):
            recortes.append({
                'pontos': poly['points'],
                'area': recorte_poly.area
            })

    return recortes
```

### 2.6 Aberturas (Vazios)

```python
# Layer "Vázio" sofre corrupção de encoding em CP1252
# Usar comparação normalizada:
VOID_ALIASES = {'vazio', 'vazios', 'abertura', 'aberturas', 'buraco', 'void', 'opening'}

def is_void_layer(layer: str) -> bool:
    normalized = unicodedata.normalize('NFKD', layer).encode('ascii', 'ignore').decode().lower()
    return normalized in VOID_ALIASES or 'vaz' in normalized

# LWPOLYLINE fechada em layer Vázio → abertura na laje
```

### 2.7 Confidence da Laje

```python
def calcular_confidence_laje(laje: dict) -> float:
    conf = 0.30  # base
    if laje.get('espessura', 0) > 0:
        conf += 0.30
    if laje.get('outline_segs') and len(laje['outline_segs']) >= 3:
        conf += 0.20
    if laje.get('vigas_around'):
        conf += 0.20
    return min(conf, 1.0)

# Laje SYNTHETIC começa em 0.50 (espessura conhecida, mas contorno incerto)
```

---

## SEÇÃO 3 — VALIDAÇÃO

| Campo | Range Válido | Ação se Inválido |
|---|---|---|
| `espessura` | 7 – 40 cm | `confidence -= 0.3` |
| `outline_segs` | >= 3 vértices | `confidence -= 0.2`, marcar SYNTHETIC |
| `dimensoes.comprimento` | > 0 | avisar |
| `dimensoes.largura` | > 0 | avisar |
| `tipo` | "macica","pre_moldada","steel_deck" | default "macica" |

---

## SEÇÃO 4 — EXEMPLOS REAIS

### Exemplo 1 — Laje com ID explícito

**DXF input:**
```
TEXT layer=EST-LAJE-TEXT  text="L5"  insert=(18000, 12000)
TEXT layer=COTA           text="h=12"  insert=(18100, 11900)
LWPOLYLINE layer=Painéis  closed=True
  vertices=[(15000,10000),(21200,10000),(21200,14300),(15000,14300)]
```

**JSON output:**
```json
{
  "codigo": "L5",
  "tipo": "macica",
  "espessura": 12.0,
  "outline_segs": [
    {"x": 15000.0, "y": 10000.0},
    {"x": 21200.0, "y": 10000.0},
    {"x": 21200.0, "y": 14300.0},
    {"x": 15000.0, "y": 14300.0}
  ],
  "dimensoes": {"comprimento": 620.0, "largura": 430.0, "espessura": 12.0},
  "confidence": 1.0
}
```

### Exemplo 2 — Laje Sintética (cluster h=)

**DXF input:**
```
TEXT layer=COTA  text="h=10"  insert=(3000, 8000)
TEXT layer=COTA  text="h=10"  insert=(3200, 8100)
TEXT layer=COTA  text="h=10"  insert=(3100, 7900)
# Três textos h=10 dentro de 300mm entre si → 1 cluster
```

**JSON output:**
```json
{
  "codigo": "synth_0",
  "tipo": "macica",
  "espessura": 10.0,
  "outline_segs": [],
  "confidence": 0.50
}
```

### Exemplo 3 — Laje com Abertura

**DXF input:**
```
TEXT layer=EST-LAJE-TEXT  text="L3"  insert=(6000, 6000)
LWPOLYLINE layer=Vázio  closed=True
  vertices=[(5800,5900),(5900,5900),(5900,6100),(5800,6100)]
```

**JSON output:**
```json
{
  "codigo": "L3",
  "aberturas": [
    {"pontos": [[5800,5900],[5900,5900],[5900,6100],[5800,6100]],
     "area": 20000.0}
  ],
  "confidence": 0.80
}
```

---

## SEÇÃO 5 — CASOS ESPECIAIS

### Laje pre-moldada
```
Identificação: texto "h=12" + INSERT blocks de vigotas
Layer típico: "barrote" ou "EST-SIMB"
Tipo: "pre_moldada"
```

### Laje de grande área sem contorno claro
```
Situação: L1 encontrado, mas LWPOLYLINE de Painéis cobre toda a folha
Ação: usar bbox das vigas_around para estimar contorno
confidence = 0.40 (estimado)
```

### Laje com h= em 2 formatos conflitantes
```python
# "h=12" e "h = 14" dentro do mesmo raio de busca
# → usar o valor do texto mais próximo ao centróide da laje
```

### Encoding de layer "Vázio"
```
Layer real no DXF: "Vázio" (CP1252: 0x56 0xE1 0x7A 0x69 0x6F)
Lido como UTF-8: "V?zio" ou "V\xc3\xa1zio"
Solução: normalize_layer("Vázio") == normalize_layer("V?zio") == "VAZIO"
```

---

*SPEC-LAJES v1.0 | 5 seções | Fonte: agente_estrutural.py + ficha_lajes_schema.py*
