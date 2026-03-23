# C-1: Inventário de Entidades DXF — CAD-ANALYZER
**Conductor (CAD Pipeline Orchestrator) | MASTERPLAN CAD-FICHAS-V2 | 2026-03-19**

---

## Método de Coleta
Dados extraídos de `dxf_reverso_analise.json` (14 arquivos PL, 14 LV, análise LJ)
combinados com inspeção direta do código `agente_estrutural.py`.

---

## 1. ENTIDADES POR TIPO DE ELEMENTO

### 1.1 PL — Pilares (14 arquivos analisados)

| EntityType | Contagem Total | Uso pelo Robô | Atributos-chave ezdxf |
|---|---|---|---|
| **LINE** | 38,633 | ❌ Ignorado na extração de pilares | `e.dxf.start`, `e.dxf.end`, `e.dxf.layer` |
| **DIMENSION** | 22,456 | ❌ Ignorado | `e.dxf.text_midpoint` |
| **LWPOLYLINE** | 16,631 | ✅ **CRÍTICO** — contorno do pilar | `e.get_points('xy')`, `e.is_closed`, `e.dxf.layer` |
| **INSERT** | 10,293 | ⚠️ Apenas PONTALETE/MEIO_PONT para 3D | `e.dxf.name`, `e.dxf.insert` |
| **HATCH** | 9,958 | ❌ Ignorado | — |
| **TEXT** | 7,538 | ✅ **CRÍTICO** — ID do pilar (P1, P17) | `e.dxf.text`, `e.dxf.insert`, `e.dxf.layer` |
| **MTEXT** | 3,291 | ✅ **CRÍTICO** — ID e dimensões | `e.text`, `e.plain_text()`, `e.dxf.insert` |
| **LEADER** | 1,803 | ❌ Ignorado | — |
| **ARC** | 943 | ⚠️ Apenas pilar cambotado | `e.dxf.center`, `e.dxf.radius` |
| **ELLIPSE** | 352 | ❌ Ignorado | — |
| **MLINE** | 286 | ❌ Ignorado | — |
| **SPLINE** | 121 | ❌ Ignorado | — |
| **CIRCLE** | 42 | ❌ Ignorado | — |
| **SOLID** | 22 | ❌ Ignorado | — |
| **ATTDEF** | 12 | ❌ Ignorado | — |
| **OLE2FRAME** | 11 | ❌ Ignorado | — |
| **ARC_DIMENSION** | 4 | ❌ Ignorado | — |

**Entidades que o robô realmente usa em PL: TEXT, MTEXT, LWPOLYLINE (fechada)**

---

### 1.2 LV — Vigas (14 arquivos analisados)

| EntityType | Contagem Total | Uso pelo Robô | Atributos-chave ezdxf |
|---|---|---|---|
| **LINE** | 66,521 | ✅ **CRÍTICO** — geometria da viga (pares LV-FV) | `e.dxf.start`, `e.dxf.end`, `e.dxf.layer` |
| **DIMENSION** | 18,530 | ❌ Ignorado | — |
| **LWPOLYLINE** | 10,310 | ✅ **CRÍTICO** — contorno de seção da viga | `e.get_points('xy')`, `e.dxf.layer` |
| **TEXT** | 9,959 | ✅ **CRÍTICO** — ID da viga (V1, V2, BA1) | `e.dxf.text`, `e.dxf.insert`, `e.dxf.layer` |
| **HATCH** | 8,734 | ❌ Ignorado | — |
| **MTEXT** | 4,073 | ✅ **CRÍTICO** — ID e dimensões (b=20 h=50) | `e.plain_text()`, `e.dxf.insert` |
| **INSERT** | 2,349 | ⚠️ Garfos HT20CT para 3D | `e.dxf.name`, `e.dxf.insert`, `e.dxf.rotation` |
| **ARC** | 279 | ❌ Ignorado | — |
| **CIRCLE** | 231 | ❌ Ignorado | — |
| **LEADER** | 145 | ❌ Ignorado | — |
| **SPLINE** | 72 | ❌ Ignorado | — |
| **ATTDEF** | 14 | ❌ Ignorado | — |
| **POINT** | 12 | ❌ Ignorado | — |
| **ARC_DIMENSION** | 12 | ❌ Ignorado | — |
| **OLE2FRAME** | 12 | ❌ Ignorado | — |
| **MLINE** | 12 | ❌ Ignorado | — |
| **SOLID** | 12 | ❌ Ignorado | — |

**Entidades que o robô realmente usa em LV: TEXT, MTEXT, LWPOLYLINE (aberta), LINE**

---

### 1.3 LJ — Lajes (análise amostral)

| EntityType | Contagem Total | Uso pelo Robô | Atributos-chave ezdxf |
|---|---|---|---|
| **LINE** | 7,500 | ✅ **CRÍTICO** — contorno e divisões | `e.dxf.start`, `e.dxf.end`, `e.dxf.layer` |
| **DIMENSION** | 2,781 | ❌ Ignorado | — |
| **LWPOLYLINE** | 2,301 | ✅ **CRÍTICO** — contorno da laje | `e.get_points('xy')`, `e.is_closed` |
| **TEXT** | 2,185 | ✅ **CRÍTICO** — ID laje (L1, L2, h=10) | `e.dxf.text`, `e.dxf.insert` |
| **MTEXT** | 1,320 | ✅ **CRÍTICO** — espessura (h=12, h=14) | `e.plain_text()`, `e.dxf.insert` |
| **HATCH** | 832 | ❌ Ignorado | — |
| **INSERT** | 285 | ❌ Ignorado na extração de lajes | — |
| **CIRCLE** | 127 | ❌ Ignorado | — |
| **SOLID** | 122 | ❌ Ignorado | — |
| **ARC** | 51 | ❌ Ignorado | — |
| **MULTILEADER** | 14 | ❌ Ignorado | — |

**Entidades que o robô realmente usa em LJ: TEXT, MTEXT, LWPOLYLINE, LINE**

---

## 2. ACESSO ezdxf — CÓDIGO PYTHON POR ENTIDADE

### TEXT
```python
doc = ezdxf.readfile("arquivo.dxf")
msp = doc.modelspace()

for e in msp.query("TEXT"):
    text_content = e.dxf.text.strip()          # conteúdo do texto
    insert_x = e.dxf.insert.x                  # posição X
    insert_y = e.dxf.insert.y                  # posição Y
    layer = e.dxf.layer                        # nome do layer
    height = e.dxf.height                      # altura da fonte (mm)
    rotation = getattr(e.dxf, 'rotation', 0)   # rotação em graus
```

### MTEXT
```python
for e in msp.query("MTEXT"):
    # Compatibilidade entre versões do ezdxf:
    text_content = None
    for method in ('plain_text', 'plain_mtext'):
        fn = getattr(e, method, None)
        if callable(fn):
            text_content = fn()
            break
    if text_content is None:
        text_content = e.dxf.text  # fallback raw (pode ter formatação)

    insert_x = e.dxf.insert.x
    insert_y = e.dxf.insert.y
    layer = e.dxf.layer
```

### LWPOLYLINE (pilar — fechada)
```python
for e in msp.query("LWPOLYLINE"):
    pts = [(float(p[0]), float(p[1])) for p in e.get_points('xy')]
    is_closed = (e.dxf.flags & 1 == 1) or e.is_closed
    layer = e.dxf.layer

    # Detectar pilar cambotado (curvado):
    bulges = [float(p[4]) if len(p) > 4 else 0.0
              for p in e.get_points('xyzsb')]
    has_arcs = any(abs(b) > 0.01 for b in bulges)

    if is_closed and len(pts) >= 3:
        # → CONTORNO DE PILAR ou LAJE
        area = calcular_area_shoelace(pts)
```

### LINE (viga)
```python
for e in msp.query("LINE"):
    start_x = e.dxf.start.x
    start_y = e.dxf.start.y
    end_x = e.dxf.end.x
    end_y = e.dxf.end.y
    layer = e.dxf.layer
    length = math.hypot(end_x - start_x, end_y - start_y)
```

### INSERT (blocos — pontalete, garfo)
```python
for e in msp.query("INSERT"):
    block_name = e.dxf.name        # "PONTALETE", "GARFOS", "HT20CT"
    x = e.dxf.insert.x
    y = e.dxf.insert.y
    rotation = getattr(e.dxf, 'rotation', 0.0)
    scale_x = getattr(e.dxf, 'xscale', 1.0)
    scale_y = getattr(e.dxf, 'yscale', 1.0)
```

---

## 3. PADRÕES REGEX DE IDENTIFICAÇÃO

```python
# Pilar: P1, P17, PC1, P-1, P1A, P.1
RE_PILAR = re.compile(
    r'^(PC?\.?-?\d+([A-Z]|\.\d+|-\d+)?|P-\d+[A-Z]?)$',
    re.IGNORECASE
)

# Viga: V1, V2, BA1, VB1, VT1, VC1, V1.2, V1/2
RE_VIGA = re.compile(
    r'^(V|BA|VB|VT|VC)\.?-?\d+([A-Z]|\.\d+|/\d+)?$',
    re.IGNORECASE
)

# Laje: L1, L1A, Y1, X1, LAJ-1, LAJE 1
RE_LAJE = re.compile(
    r'^(L\d+[A-Za-z]?|Y\d+[A-Za-z]?|X\d+[A-Za-z]?|LAJ[-_]?\d+|LAJE[-_\s]*\d+)$',
    re.IGNORECASE
)

# Dimensões: 20x50, 20X50, 20*50
RE_DIM = re.compile(r'(\d{1,3})\s*[xX*\/]\s*(\d{1,3})')

# Espessura de laje: h=12, h = 14
RE_LAJE_H = re.compile(r'h\s*[=:]\s*([\d,.]+)', re.IGNORECASE)
# Dimensão b=h: b=20 h=50
RE_DIM_BH = re.compile(r'b\s*=\s*(\d{1,3}).*?h\s*=\s*(\d{1,3})', re.IGNORECASE | re.DOTALL)
```

---

## 4. RAIOS DE BUSCA ESPACIAL (UNIDADES DXF = MM)

| Elemento | Raio de Busca | Constante |
|---|---|---|
| Pilar (texto → polilinha) | 800 mm | `PILAR_SEARCH_RADIUS` |
| Viga (texto → linha) | 1200 mm | `VIGA_SEARCH_RADIUS` |
| Laje (texto → contorno) | 1500 mm | `LAJE_SEARCH_RADIUS` |
| Dimensão (dim → elemento) | 600 mm | `DIM_SEARCH_RADIUS` |
| Cluster laje sintética | 500 mm | `CLUSTER_RADIUS` |

### Lógica de 3 Raios (TextAssociator)
```python
# Score 1.0: texto DENTRO do polígono
if polygon.contains(Point(tx, ty)):
    score = 1.0

# Score 0.8: distância <= 5 unidades DXF
elif dist <= 5.0:
    score = 0.8

# Score 0.5..0.0: decaimento linear até context_radius
elif dist <= context_radius:
    decay = 1.0 - (dist / context_radius)
    score = 0.5 * decay
```

**Confidence mínima para auto-assign: 0.80. Abaixo → fila de revisão humana.**

---

## 5. ENTIDADES IGNORADAS (não relevantes para extração)

| EntityType | Por quê ignorado |
|---|---|
| DIMENSION | Cotas visuais — medidas vêm de RE_DIM nos TEXT/MTEXT |
| HATCH | Preenchimento visual (CONCRETO, madeira) — sem dados semânticos |
| LEADER | Setas de cota visual — sem dados semânticos |
| ARC, ELLIPSE, SPLINE | Geometria decorativa — exceto ARC em pilar cambotado |
| INSERT (maioria) | Blocos decorativos — exceto PONTALETE/GARFOS para geração 3D |
| OLE2FRAME, ATTDEF | Objetos OLE e definições de atributo — irrelevantes |

---

## 6. PILAR ESPECIAL — DETECÇÃO DE CAMBOTADO

```python
# Cambotado = pilar com face curva
if has_arcs and max_bulge > 0.3:
    pilar_especial = True
    tipo_pilar_especial = "CAMBOTADO"
elif 0.1 < max_bulge <= 0.3:
    # Possível cambotado — enviar para revisão humana
    needs_review = True
```

**Bulge = fator de curvatura da polilinha. Abs(bulge) > 0.01 = segmento curvo.**

---

*C-1 COMPLETO — Gate: 17 tipos entidade PL / 17 tipos LV / 11 tipos LJ documentados. ✅*
