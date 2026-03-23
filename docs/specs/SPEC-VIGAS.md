# SPEC-VIGAS — Extração de Vigas do DXF
## Especificação Operacional para CAD-ANALYZER
**Fonte da verdade: agente_estrutural.py + ficha_vigas_schema.py | 2026-03-19**

---

## SEÇÃO 1 — IDENTIFICAÇÃO DA VIGA NO DXF

### 1.1 Detecção por Texto (TEXT / MTEXT)

```python
import re

RE_VIGA = re.compile(
    r'^(V|BA|VB|VT|VC)\.?-?\d+([A-Z]|\.\d+|/\d+)?$',
    re.IGNORECASE
)

# Exemplos que CASAM:
# V1, V2, V101, BA1 (balanço), VB1, VT1, VC1
# V1A, V1.2, V1/2, V-1

# Exemplos que NÃO casam:
# VIGA (sem número), V (sem número), LV1 (layer name)
```

**Prefixos e seus significados:**
| Prefixo | Tipo | Observação |
|---|---|---|
| `V` | Viga padrão | Mais comum |
| `BA` | Balanço | `_is_balanco()` retorna True |
| `VB` | Viga de bordo | Tratada como balanço |
| `VT` | Viga tronco | Seção variável |
| `VC` | Viga curva | Seção especial |

### 1.2 Extração do Texto

```python
vigas_txt = []
for e in msp:
    etype = e.dxftype()
    text, x, y, layer = None, 0.0, 0.0, '0'

    if etype == 'TEXT':
        text = getattr(e.dxf, 'text', '').strip()
        x, y = float(e.dxf.insert.x), float(e.dxf.insert.y)
        layer = e.dxf.layer

    elif etype == 'MTEXT':
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

    if text and RE_VIGA.match(text):
        vigas_txt.append({'text': text, 'x': x, 'y': y, 'layer': layer})
```

**Layer esperado para IDs de vigas:** `NOMENCLATURA`, `texto`, `TEXTO_GERAL`

### 1.3 Geometria da Viga — LINE entities (não LWPOLYLINE)

**Diferença crítica viga vs pilar:**
- **Pilar** → LWPOLYLINE **fechada** (polígono = seção transversal)
- **Viga** → conjuntos de LINE entities representando LV (lateral) e FV (fundo)

```python
VIGA_SEARCH_RADIUS = 1200.0  # mm — maior que pilar (800mm)

lines = []
for e in msp.query("LINE"):
    lines.append({
        'start': (float(e.dxf.start.x), float(e.dxf.start.y)),
        'end':   (float(e.dxf.end.x),   float(e.dxf.end.y)),
        'layer': e.dxf.layer,
        'length': math.hypot(
            e.dxf.end.x - e.dxf.start.x,
            e.dxf.end.y - e.dxf.start.y
        )
    })
```

### 1.4 Layers Críticos de Viga

| Layer | Canonical | Elemento |
|---|---|---|
| `Painéis` / `PAINEIS` | `PANEL_GEOMETRY` | **LV — Lateral de Viga** |
| `fundo` / `FUNDOS` | `BEAM_BOTTOM` | **FV — Fundo de Viga** |
| `Escoras` / `Escora de Viga` | `SHORING` | Escoras de apoio |
| `GARFOS` | `FORK_METAL` | Garfos metálicos HT20CT |
| `presilha` / `Presilha` | `CLAMP_METAL` | Presilhas |
| `barrote` | `BATTEN_BEAM` | Barrotes |
| `SCO-___-LAJ` | `SLAB_INTERFACE` | Interface laje-viga |
| `Forcador` | `SPACER` | Espaçadores |
| `BARRA DE ANCORAGEM` | `ANCHOR_BAR` | Barras de ancoragem (**alias de "BARRA ANCORAGEM" em PL!**) |

---

## SEÇÃO 2 — EXTRAÇÃO DOS CAMPOS JSON

### 2.1 Schema completo `FichaFase3Viga`

```python
{
    "codigo": "V101",          # texto original do DXF
    "pavimento": "1_PAVIMENTO", # nome do arquivo DXF
    "obra_nome": "ALIMONTI-PARAISO",

    # Tipo e geometria
    "tipo": "retangular",      # "retangular" | "L" | "T"
    "largura": 20.0,           # b (cm) — dimensão horizontal
    "altura": 50.0,            # h (cm) — dimensão vertical
    "comprimento": 480.0,      # span entre apoios (cm)

    # Seção transversal
    "secao_transversal": {
        "tipo": "RET",
        "largura": 20.0,
        "altura": 50.0,
        "area_cm2": 1000.0
    },

    # Tramos (vãos entre apoios)
    "tramos": [
        {
            "apoio_ini": "P5",
            "apoio_fim": "P8",
            "comprimento": 480.0,
            "laje_esq": "L3",
            "laje_dir": "L4"
        }
    ],

    # Armadura (inferida de texto próximo — pode ser vazio)
    "armadura_positiva": {"barras": 3, "diametro": 16, "posicao": "inferior"},
    "armadura_negativa": {"barras": 2, "diametro": 16, "posicao": "superior"},

    # Estribos
    "estribos": {"diametro": 8, "espacamento": 15},

    # Componentes metálicos
    "garfos": {"tipo": "HT20CT", "quantidade": 4, "posicao": "lateral"},

    # Metadados
    "confidence": 0.87,
    "dna_vector": [],
    "revisado": False
}
```

### 2.2 Como Extrair `largura` e `altura` — Dois Formatos

```python
RE_DIM = re.compile(r'(\d{1,3})\s*[xX*\/]\s*(\d{1,3})')
RE_DIM_BH = re.compile(
    r'b\s*=\s*(\d{1,3}).*?h\s*=\s*(\d{1,3})',
    re.IGNORECASE | re.DOTALL
)

def extrair_dim_viga(text: str) -> tuple[float, float]:
    """
    Retorna (largura, altura) em cm.
    Para vigas: largura=b (horizontal), altura=h (vertical).
    """
    # Formato "20x50" → largura=20, altura=50 (b < h por convenção)
    m = RE_DIM.search(text)
    if m:
        d1, d2 = float(m.group(1)), float(m.group(2))
        return min(d1, d2), max(d1, d2)  # b=menor, h=maior

    # Formato "b=20 h=50"
    m = RE_DIM_BH.search(text)
    if m:
        return float(m.group(1)), float(m.group(2))  # b, h explícitos

    return 0.0, 0.0
```

**⚠️ DIFERENÇA PILAR vs VIGA:**
- Pilar: `comprimento = max(d1,d2)` (lado maior)
- Viga: `largura = min(d1,d2)`, `altura = max(d1,d2)` (b < h por norma)

### 2.3 Como Calcular `comprimento` (Span da Viga)

```python
def calcular_comprimento(viga_pos, pilares_proximos, viga_search_radius):
    """
    Encontra os 2 pilares de apoio mais próximos.
    Distância entre eles = comprimento estimado da viga.
    """
    sorted_p = sorted(pilares_proximos, key=lambda x: x[1])  # por distância

    if len(sorted_p) >= 2:
        p1, p2 = sorted_p[0][0], sorted_p[1][0]
        comprimento = math.hypot(p1.x - p2.x, p1.y - p2.y)
        return round(comprimento / 10, 1)  # converter mm → cm
    return 0.0
```

### 2.4 Associação Apoios (Pilares Vizinhos)

```python
VIGA_SEARCH_RADIUS = 1200.0  # mm

def encontrar_apoios(viga_pos, pilares_txt):
    """Retorna (apoio_ini, apoio_fim, conf_ini, conf_fim)."""
    candidatos = []
    vx, vy = viga_pos

    for p in pilares_txt:
        dist = math.hypot(p['x'] - vx, p['y'] - vy)
        if dist <= VIGA_SEARCH_RADIUS:
            conf = max(0.0, 1.0 - dist / VIGA_SEARCH_RADIUS)
            candidatos.append((p['text'], dist, conf))

    candidatos.sort(key=lambda x: x[1])

    apoio_ini = candidatos[0][0] if len(candidatos) >= 1 else ''
    apoio_fim = candidatos[1][0] if len(candidatos) >= 2 else ''
    conf_ini = candidatos[0][2] if len(candidatos) >= 1 else 0.0
    conf_fim = candidatos[1][2] if len(candidatos) >= 2 else 0.0

    return apoio_ini, apoio_fim, conf_ini, conf_fim
```

### 2.5 Detecção de Balanço

```python
def is_balanco(codigo: str) -> bool:
    """BA* e VB* são sempre balanços (viga com apenas 1 apoio)."""
    return bool(re.match(r'^(BA|VB)\d+', codigo, re.IGNORECASE))
```

### 2.6 Garfos HT20CT — INSERT blocks

```python
garfos = []
for e in msp.query("INSERT"):
    block_name = e.dxf.name.upper()
    layer = e.dxf.layer.upper()

    if 'GARFO' in block_name or 'HT20' in block_name or layer == 'GARFOS':
        garfos.append({
            'x': float(e.dxf.insert.x),
            'y': float(e.dxf.insert.y),
            'rotation': getattr(e.dxf, 'rotation', 0.0),
            'tipo': 'HT20CT' if 'HT20' in block_name else 'GARFO'
        })

# Associar garfos à viga mais próxima por proximidade espacial
```

---

## SEÇÃO 3 — VALIDAÇÃO

| Campo | Range Válido | Ação se Inválido |
|---|---|---|
| `largura` | 12 – 100 cm | `confidence -= 0.3` |
| `altura` | 25 – 200 cm | `confidence -= 0.3` |
| `comprimento` | > 0 cm | avisar; confidence -= 0.1 |
| `tipo` | "retangular","L","T" | default "retangular" |
| `tramos` | >= 1 tramo | `confidence -= 0.2` |
| `largura < altura` | obrigatório (b < h) | trocar valores |

---

## SEÇÃO 4 — EXEMPLOS REAIS (DXF → JSON)

### Exemplo 1 — ALIMONTI Viga Simples

**DXF input:**
```
TEXT layer=NOMENCLATURA  text="V101"  insert=(2086, 16806)
TEXT layer=cotas         text="20x50"  insert=(2100, 16750)
LINE layer=Painéis  start=(1800,16750) end=(3200,16750)  # LV
LINE layer=fundo    start=(1800,16680) end=(3200,16680)  # FV
```

**JSON output:**
```json
{
  "codigo": "V101",
  "tipo": "retangular",
  "largura": 20.0,
  "altura": 50.0,
  "comprimento": 140.0,
  "confidence": 0.92
}
```

### Exemplo 2 — Viga Balanço

**DXF input:**
```
TEXT layer=NOMENCLATURA  text="BA3"  insert=(4458, 16712)
TEXT layer=cotas         text="15x40"  insert=(4470, 16680)
```

**JSON output:**
```json
{
  "codigo": "BA3",
  "tipo": "retangular",
  "largura": 15.0,
  "altura": 40.0,
  "tramos": [{"apoio_ini": "P5", "apoio_fim": ""}],
  "confidence": 0.75
}
```
*(balanço tem apenas 1 apoio — `apoio_fim` vazio é esperado)*

### Exemplo 3 — Viga com Dimensão b=h

**DXF input:**
```
MTEXT layer=NOMENCLATURA  text="V205\nb=25 h=60"  insert=(8000, 5000)
```

**JSON output:**
```json
{
  "codigo": "V205",
  "largura": 25.0,
  "altura": 60.0,
  "confidence": 0.88
}
```

---

## SEÇÃO 5 — CASOS ESPECIAIS

### Viga sem dimensão próxima
```
Situação: V1 detectado, sem texto "NNxMM" em 600mm
Ação: largura=0, altura=0, confidence -= 0.4
Log: "V1: dimensão não encontrada"
Nota: a viga é registrada mesmo sem dimensão (para revisão humana)
```

### Viga com LV mas sem FV
```
Situação: apenas layer "Painéis" encontrado, sem layer "fundo"
Significado: ficha de LV (lateral) sem o fundo correspondente
Ação: registrar como LV somente, marcar "fundo_ausente": true
```

### Aliases de layer que mudam entre obras
```python
# "fundo" vs "FUNDOS" vs "Fundo da Viga" — todos são FV:
BEAM_BOTTOM_ALIASES = {'fundo', 'fundos', 'fundo da viga', 'fundo viga', 'fv'}

def is_beam_bottom(layer: str) -> bool:
    return layer.lower().strip() in BEAM_BOTTOM_ALIASES
```

### Viga com encoding corrompido em layer
```python
# Layer "Painéis" pode chegar como "Pain?is"
# Solução: normalizar antes de comparar
import unicodedata
def norm(s):
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().upper()
```

---

*SPEC-VIGAS v1.0 | 5 seções | Fonte: agente_estrutural.py + ficha_vigas_schema.py*
