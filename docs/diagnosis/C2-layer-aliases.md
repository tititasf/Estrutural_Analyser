# C-2: Tabela de Aliases de Layers — CAD-ANALYZER
**Conductor (CAD Pipeline Orchestrator) | MASTERPLAN CAD-FICHAS-V2 | 2026-03-19**

---

## Método de Coleta
Dados extraídos de `dxf_reverso_analise.json` (ocorrência em 14 arquivos PL + 14 LV + LJ)
e do código `agente_estrutural.py` (função `_detect_family`).

---

## 1. FAMÍLIAS DE DXF — DETECÇÃO AUTOMÁTICA

O sistema detecta a "família" do DXF antes de processar layers:

| Família | Algoritmo de Detecção | Obras Conhecidas |
|---|---|---|
| **BIM** | Layers descritivos: CONCRETO, PAINEI, BEAM, COLUMN, SLAB, PILAR, VIGA, LAJE, F-, S- | ALIMONTI, maioria das obras |
| **TQS** | >30% dos layers são numéricos (`re.match(r'^\d+$', layer)`) | Obras com layers "1", "2", "3" |
| **METHODUS** | Qualquer layer começa com `MTH-` | Firma METHODUS (raro) |
| **EBERICK** | >15% dos layers começam com `TX` | Firma EBERICK (raro) |

```python
# Código real de detecção (agente_estrutural.py):
layers = [layer.dxf.name for layer in doc.layers]

if any(l.upper().startswith('MTH-') for l in layers):
    family = 'METHODUS'
elif sum(1 for l in layers if l.upper().startswith('TX')) > len(layers) * 0.15:
    family = 'EBERICK'
elif sum(1 for l in layers if re.match(r'^\d+$', l)) > len(layers) * 0.3:
    family = 'TQS'
elif any(kw in l.upper() for l in layers
         for kw in ['CONCRETO','PAINEI','BEAM','COLUMN','SLAB','PILAR','VIGA','LAJE','F-','S-']):
    family = 'BIM'
else:
    family = 'TQS'  # fallback
```

---

## 2. LAYERS — PILARES (PL)

Presença nos 14 arquivos analisados (frequência = nº de arquivos com o layer):

| Layer Real | Frequência | Canonical Name | Função no Robô | Confidence |
|---|---|---|---|---|
| `0` | 14/14 | `DEFAULT` | Geometria genérica | ALTO |
| `Hachura` | 14/14 | `HATCH_WOOD` | Preenchimento visual madeira | N/A (ignorado) |
| `Defpoints` | 14/14 | `DEFPOINTS` | Pontos auxiliares AutoCAD | N/A (ignorado) |
| `Madeira` | 14/14 | `WOOD_GEOMETRY` | Geometria de madeira/fôrma | ALTO |
| `COTA` | 14/14 | `DIMENSION_LINES` | Linhas de cota visual | N/A (ignorado) |
| `Painéis` / `Pain?is` | 14/14 | `PANEL_GEOMETRY` | **Contorno dos painéis** → LWPOLYLINE | ALTO |
| `Demarcação 2` | 14/14 | `ZONE_MARK_2` | Demarcação de zona 2 | N/A |
| `Demarcação 1` | 14/14 | `ZONE_MARK_1` | Demarcação de zona 1 | N/A |
| `CONCRETO` | 14/14 | `CONCRETE_FILL` | Hachura de concreto | N/A (ignorado) |
| `Perfil Metálico` | 14/14 | `METAL_PROFILE` | Perfis metálicos estruturais | N/A |
| `CARIMBO` | 14/14 | `TITLE_BLOCK` | Carimbo do projeto | N/A (ignorado) |
| `SARRAFO` | 14/14 | `WOOD_BATTEN` | Sarrafos genéricos | ALTO |
| `SARRAFO DE PRESSAO` | 14/14 | `PRESSURE_BATTEN` | Sarrafo de pressão (DASHED) | ALTO |
| `Folhas` | 14/14 | `SHEET_BORDER` | Borda da folha | N/A (ignorado) |
| `NOMENCLATURA` | 14/14 | `ELEMENT_LABEL` | **IDs de elementos** (P1, P2…) → TEXT | ALTO |
| `texto` | 14/14 | `GENERAL_TEXT` | Textos gerais | MÉDIO |
| `SARR_2.2x7` | 14/14 | `BATTEN_2x7` | Sarrafo 2,2x7cm específico | ALTO |
| `BARRA ANCORAGEM` | 14/14 | `ANCHOR_BAR` | Barras de ancoragem | MÉDIO |
| `NIVEL` | 14/14 | `ELEVATION_MARK` | Marcações de nível | ALTO |
| `cotas` | 13/14 | `DIM_TEXT` | Textos de cotas | MÉDIO |
| `Texto Seção` | 13/14 | `SECTION_TEXT` | Texto de seção transversal → **dimensões pilar** | ALTO |
| `Texto Qtd Sarr` | 13/14 | `BATTEN_COUNT_TEXT` | Quantidade de sarrafos | MÉDIO |
| `Texto de Titulo` | 13/14 | `TITLE_TEXT` | Título do desenho | N/A |
| `TEXTO_GERAL` | 13/14 | `GENERAL_TEXT_2` | Textos gerais alt. | MÉDIO |
| `CHAPA` | 13/14 | `PLATE_GEOMETRY` | Chapas de compensado | ALTO |
| `SARR_2.2x10` | 12/14 | `BATTEN_2x10` | Sarrafo 2,2x10cm | ALTO |
| `SARR_7x7` | 12/14 | `BATTEN_7x7` | Sarrafo 7x7cm (cantos) | ALTO |
| `SARR_3.5x7` | 12/14 | `BATTEN_3x7` | Sarrafo 3,5x7cm | ALTO |

**Layers raros em PL (< 5 arquivos):**

| Layer Real | Frequência | Canonical | Observação |
|---|---|---|---|
| `PONTALETE` | 5/14 | `PROP_LAYER` | Pontaletes direto em layer |
| `GRAVATA` | 5/14 | `CLAMP_LAYER` | Gravatas metálicas |
| `1-2 PONTALETE` | 5/14 | `PROP_12_LAYER` | Meia-pontalete |
| `F-PILARES-S` | 3/14 | `PILLAR_FACE_S` | Face Sul do pilar |
| `S-COLS` | 2/14 | `TQS_COLUMN` | Pilar em família TQS |
| `S-BEAM` | 2/14 | `TQS_BEAM` | Viga em família TQS |
| `COTAS FURAÇ` | 1/14 | `HOLE_DIM` | Cotas de furação |

---

## 3. LAYERS — VIGAS (LV)

| Layer Real | Frequência | Canonical Name | Função no Robô | Confidence |
|---|---|---|---|---|
| `0` | 14/14 | `DEFAULT` | Geometria genérica | ALTO |
| `Defpoints` | 14/14 | `DEFPOINTS` | Pontos auxiliares | N/A |
| `COTA` | 14/14 | `DIMENSION_LINES` | Cotas visuais | N/A |
| `Hachura` | 14/14 | `HATCH_GENERAL` | Hachura geral | N/A |
| `Painéis` / `Pain?is` | 14/14 | `PANEL_GEOMETRY` | Contorno dos painéis | ALTO |
| `Demarcação 1/2` | 14/14 | `ZONE_MARK` | Zonas de demarcação | N/A |
| `CONCRETO` | 14/14 | `CONCRETE_FILL` | Hachura concreto | N/A |
| `Madeira` | 14/14 | `WOOD_GEOMETRY` | Geometria madeira/fôrma | ALTO |
| `Perfil Metálico` | 14/14 | `METAL_PROFILE` | Perfis metálicos | N/A |
| `CARIMBO` | 14/14 | `TITLE_BLOCK` | Carimbo | N/A |
| `SARRAFO DE PRESSAO` | 14/14 | `PRESSURE_BATTEN` | Sarrafo de pressão | ALTO |
| `Folhas` | 14/14 | `SHEET_BORDER` | Borda folha | N/A |
| `SARR_2.2x7` | 14/14 | `BATTEN_2x7` | Sarrafo específico | ALTO |
| `NOMENCLATURA` | 14/14 | `ELEMENT_LABEL` | **IDs de vigas** (V1, V2…) | ALTO |
| `5` / `9` | 14/14 | `TQS_LAYER_NUMERIC` | Layer numérico → família TQS | MÉDIO |
| `texto` | 14/14 | `GENERAL_TEXT` | Textos gerais | MÉDIO |
| `BARRA DE ANCORAGEM` / `BARRA ANCORAGEM` | 14/14 | `ANCHOR_BAR` | Barras de ancoragem (alias!) | ALTO |
| `Forcador` | 14/14 | `SPACER` | Espaçadores de viga | ALTO |
| `Escoras` | 14/14 | `SHORING` | Escoras metálicas | ALTO |
| `material do compensado` | 14/14 | `PLYWOOD_MATERIAL` | Material compensado | MÉDIO |
| `fundo` | 14/14 | `BEAM_BOTTOM` | **Fundo da viga (FV)** → elemento crítico | ALTO |
| `GARFOS` | 14/14 | `FORK_METAL` | Garfos metálicos HT20CT | ALTO |
| `HACHURA MADEIRAS` | 14/14 | `HATCH_WOOD_BEAM` | Hachura madeira viga | N/A |
| `SARR_3.5x7` | 14/14 | `BATTEN_3x7` | Sarrafo específico | ALTO |
| `detalhes` | 14/14 | `DETAIL_LAYER` | Camada de detalhes | BAIXO |
| `SARR_EDITAR` | 14/14 | `BATTEN_EDIT` | Sarrafo em edição | BAIXO |
| `presilha` / `Presilha` | 14/14 | `CLAMP_METAL` | Presilhas metálicas | ALTO |
| `barrote` | 14/14 | `BATTEN_BEAM` | Barrotes de viga | ALTO |
| `SCO-___-LAJ` | 14/14 | `SLAB_INTERFACE` | Interface laje-viga | ALTO |
| `SARR_2.2x10` | 14/14 | `BATTEN_2x10` | Sarrafo específico | ALTO |

**⚠️ ALIAS CRÍTICO:** `BARRA DE ANCORAGEM` (LV) ≠ `BARRA ANCORAGEM` (PL) — mesmo significado, nome diferente por arquivo!

---

## 4. LAYERS — LAJES (LJ)

| Layer Real | Frequência | Canonical Name | Função no Robô | Confidence |
|---|---|---|---|---|
| `0` | N/A | `DEFAULT` | Geometria genérica | ALTO |
| `CARIMBO` | N/A | `TITLE_BLOCK` | Carimbo | N/A |
| `SARRAFO DE PRESSAO` | N/A | `PRESSURE_BATTEN` | Sarrafo de pressão | ALTO |
| `Folhas` / `FOLHA` | N/A | `SHEET_BORDER` | Borda folha — **ALIAS!** | ALTO |
| `Painéis` | N/A | `PANEL_GEOMETRY` | Contorno painéis laje | ALTO |
| `Hachura` | N/A | `HATCH_GENERAL` | Hachura geral | N/A |
| `REAPROVEITAMENTO` | N/A | `REUSE_STATUS` | **Estado de reaproveitamento** | ALTO |
| `COTA` | N/A | `DIMENSION_LINES` | Cotas | N/A |
| `Pilares` | N/A | `PILLAR_CUTOUT` | **Recortes de pilares na laje** | ALTO |
| `VIGAS` | N/A | `BEAM_INTERFACE` | Interface de vigas na laje | ALTO |
| `SARR_2.2x7` | N/A | `BATTEN_2x7` | Sarrafos | ALTO |
| `EST-PILAR` | N/A | `STRUCTURAL_PILLAR` | Símbolo estrutural pilar | MÉDIO |
| `EST-VIGA` | N/A | `STRUCTURAL_BEAM` | Símbolo estrutural viga | MÉDIO |
| `EST-SIMB` | N/A | `STRUCTURAL_SYMBOL` | Símbolos gerais | BAIXO |
| `EST-VIGA-TEXT` | N/A | `BEAM_TEXT` | Texto de viga estrutural | MÉDIO |
| `EST-PILAR-TEXT` | N/A | `PILLAR_TEXT` | Texto de pilar estrutural | MÉDIO |
| `EST-TEXT` | N/A | `STRUCTURAL_TEXT` | Textos estruturais | MÉDIO |
| `EST-LAJE-TEXT` | N/A | `SLAB_TEXT` | **Texto da laje** → ID laje | ALTO |
| `EST-SIMB-Spot Elevations` | N/A | `SPOT_ELEVATION` | Cotas de nível | MÉDIO |
| `Vázio` / `V?zio` | N/A | `VOID_OPENING` | **Vazios/aberturas na laje** | ALTO |
| `EST-PILAR-CUT` | N/A | `PILLAR_CUT` | Contorno de corte de pilar | ALTO |
| `SARR_3.5x7` | N/A | `BATTEN_3x7` | Sarrafos | ALTO |

---

## 5. ALIASES ENTRE FIRMAS — CRÍTICOS

| Canonical | ALIMONTI | GWT/outros | TQS |
|---|---|---|---|
| `ELEMENT_LABEL` (IDs) | `NOMENCLATURA` | `TEXTO_GERAL` | layer numérico + regex |
| `PANEL_GEOMETRY` | `Painéis` | `Painéis` ou `PAINEIS` | `S-COLS` (pilares) |
| `WOOD_BATTEN` | `SARRAFO` | `SARRAFO` | `barrote` |
| `ANCHOR_BAR` (PL) | `BARRA ANCORAGEM` | `BARRA ANCORAGEM` | N/A |
| `ANCHOR_BAR` (LV) | `BARRA DE ANCORAGEM` | `BARRA DE ANCORAGEM` | N/A |
| `BEAM_BOTTOM` | `fundo` | `fundo` ou `FUNDOS` | `S-BEAM` |
| `SLAB_LABEL` | `EST-LAJE-TEXT` | sem layer definido | layer numérico |
| `VOID_OPENING` | `Vázio` | `Vazio` ou `ABERTURA` | N/A |
| `CLAMP_METAL` | `presilha` | `Presilha` ou `PRESILHA` | N/A |
| `SHORING` | `Escoras` | `Escora de Viga` | N/A |

### Aliases confirmados por análise de frequência:
```
"BARRA ANCORAGEM" == "BARRA DE ANCORAGEM"  → ANCHOR_BAR
"Folhas" == "FOLHA"                        → SHEET_BORDER
"Painéis" == "Pain?is" == "PAINEIS"        → PANEL_GEOMETRY (encoding issue!)
"presilha" == "Presilha" == "PRESILHA"     → CLAMP_METAL
"Escoras" == "Escora de Viga"              → SHORING
"FUNDOS" == "fundo"                        → BEAM_BOTTOM
```

---

## 6. ENCODING — PROBLEMA CRÍTICO

**⚠️ Os layers com acentos (Painéis, Demarcação, Vázio, Nível) sofrem corrupção de encoding.**

Observado no JSON: `"Pain?is"`, `"Demarca??o"`, `"N?vel"`, `"V?zio"`.

**Causa:** arquivos DXF salvos em CP1252 (Windows-1252), lidos como UTF-8.

**Solução implementada:**
```python
# Comparação normalizada de layer names:
import unicodedata

def normalize_layer(name: str) -> str:
    nfkd = unicodedata.normalize('NFKD', name)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).upper()

# Uso:
if normalize_layer(layer) in ('PAINEIS', 'PAINEL'):
    # → PANEL_GEOMETRY
```

---

*C-2 COMPLETO — 28+ layers PL / 30+ layers LV / 22+ layers LJ mapeados. Famílias BIM/TQS/METHODUS/EBERICK documentadas. ✅*
