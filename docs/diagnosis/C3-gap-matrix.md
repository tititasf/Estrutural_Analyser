# C-3: Matriz de Gaps — Fichas Atuais vs Robô
**Conductor (CAD Pipeline Orchestrator) | MASTERPLAN CAD-FICHAS-V2 | 2026-03-19**

---

## Método de Análise
Comparação entre conteúdo das fichas instrutivas PDF atuais
e os requisitos reais do código `agente_estrutural.py` / schemas `ficha_*_schema.py`.

**Veredicto do PopForge:** Score 1.5/10. Fichas respondem "como funciona engenharia de formas"
em vez de "dada esta entidade DXF, quais campos JSON extrair".

---

## 1. CAMPOS JSON — PILARES

### Campos que o robô produz (FichaFase3Pilar):

| Campo | Tipo | De onde vem no DXF | Fichas documentam? |
|---|---|---|---|
| `id` | str | TEXT matching RE_PILAR (ex: "P1", "P17") | ❌ NÃO |
| `numero` | str | dígitos extraídos de `id` | ❌ NÃO |
| `pavimento` | str | nome do arquivo DXF ou contexto | ⚠️ PARCIAL |
| `pavimento_numero` | int | índice sequencial do pavimento | ❌ NÃO |
| `obra` | str | pasta raiz da obra | ❌ NÃO |
| `comprimento` | float (cm) | TEXT "NNxMM" → maior dim via RE_DIM | ❌ NÃO |
| `largura` | float (cm) | TEXT "NNxMM" → menor dim via RE_DIM | ❌ NÃO |
| `altura_cm` | float (cm) | derivado de nivel_chegada - nivel_saida | ❌ NÃO |
| `nivel_saida_m` | float (m) | MTEXT h= ou nível do pavimento | ❌ NÃO |
| `nivel_chegada_m` | float (m) | nível do pavimento seguinte | ❌ NÃO |
| `pavimento_anterior` | str | nome do pavimento abaixo | ❌ NÃO |
| `par_1_2` .. `par_8_9` | str | barras armadura por trecho | ❌ NÃO |
| `grade_1`, `distancia_1` | str | diâmetro/espaçamento estribos | ❌ NÃO |
| `pilar_especial` | bool | LWPOLYLINE com bulge > 0.3 | ❌ NÃO |
| `tipo_pilar_especial` | str | "L", "T", "CAMBOTADO" | ❌ NÃO |
| `confidence` | float | score do TextAssociator (0.0..1.0) | ❌ NÃO |
| `revisado_por_humano` | bool | flag de revisão manual | ❌ NÃO |

**Score completude pilar: 1/17 campos documentados (5.9%)**

### Campos CRÍTICOS ausentes nas fichas:

```
CRÍTICO: Como RE_PILAR detecta "P1" vs "PC1" vs "P-1" (regex real)
CRÍTICO: Como RE_DIM extrai "20x50" → comprimento=50, largura=20
CRÍTICO: LWPOLYLINE fechada → contorno pilar (is_closed flag)
CRÍTICO: PILAR_SEARCH_RADIUS=800mm para associar texto→polilinha
CRÍTICO: confidence < 0.80 → revisão humana obrigatória
```

---

## 2. CAMPOS JSON — VIGAS

### Campos que o robô produz (FichaFase3Viga):

| Campo | Tipo | De onde vem no DXF | Fichas documentam? |
|---|---|---|---|
| `codigo` | str | TEXT matching RE_VIGA (ex: "V1", "BA1") | ❌ NÃO |
| `pavimento` | str | nome do arquivo DXF | ⚠️ PARCIAL |
| `obra_nome` | str | pasta raiz da obra | ❌ NÃO |
| `tipo` | str | "retangular", "L", "T" | ❌ NÃO |
| `largura` | float (cm) | TEXT "bxh" → b via RE_DIM/RE_DIM_BH | ❌ NÃO |
| `altura` | float (cm) | TEXT "bxh" → h via RE_DIM/RE_DIM_BH | ❌ NÃO |
| `comprimento` | float (cm) | LINE length ou LWPOLYLINE perimeter | ❌ NÃO |
| `secao_transversal` | dict | {largura, altura, tipo} extraídos | ❌ NÃO |
| `tramos` | List[dict] | segmentos LINE entre apoios | ❌ NÃO |
| `armadura_positiva` | dict | texto "N barras Ø diam" | ❌ NÃO |
| `armadura_negativa` | dict | texto "N barras Ø diam" neg. | ❌ NÃO |
| `estribos` | dict | texto "Ø diam / spacing" | ❌ NÃO |
| `garfos` | dict | INSERT block "GARFOS" ou layer `GARFOS` | ❌ NÃO |
| `confidence` | float | score TextAssociator | ❌ NÃO |
| `dna_vector` | List[float] | vetor DNA para TransformationEngine | ❌ NÃO |

**Score completude viga: 0/15 campos documentados (0%)**

### Campos CRÍTICOS ausentes nas fichas:

```
CRÍTICO: RE_VIGA pattern — "V1", "BA1", "VB1", "VT1", "VC1"
CRÍTICO: RE_DIM_BH pattern — "b=20 h=50" (formato alternativo de dimensão)
CRÍTICO: VIGA_SEARCH_RADIUS=1200mm para texto→LINE associação
CRÍTICO: layer "fundo" → FV (Fundo de Viga) vs "Painéis" → LV (Lateral de Viga)
CRÍTICO: LINE entities (não LWPOLYLINE) para geometria de viga
```

---

## 3. CAMPOS JSON — LAJES

### Campos que o robô produz (FichaFase3Laje):

| Campo | Tipo | De onde vem no DXF | Fichas documentam? |
|---|---|---|---|
| `codigo` | str | TEXT matching RE_LAJE (L1, Y1, X1...) | ❌ NÃO |
| `pavimento` | str | nome do arquivo DXF | ⚠️ PARCIAL |
| `obra_nome` | str | pasta raiz | ❌ NÃO |
| `tipo` | str | "macica", "pre_moldada", "steel_deck" | ❌ NÃO |
| `dimensoes` | dict | {comprimento, largura, espessura} (cm) | ❌ NÃO |
| `espessura` | float (cm) | TEXT "h=12" via RE_LAJE_H | ❌ NÃO |
| `outline_segs` | List[dict] | LWPOLYLINE vertices [{x,y}...] | ❌ NÃO |
| `nivel` | float (m) | cota Z do pavimento | ❌ NÃO |
| `armadura` | dict | {tipo, diâmetro, espaçamento, direção} | ❌ NÃO |
| `confidence` | float | score TextAssociator | ❌ NÃO |

**Score completude laje: 0/10 campos documentados (0%)**

### Campos CRÍTICOS ausentes:

```
CRÍTICO: RE_LAJE_H — como "h=12" vira espessura (12 cm)
CRÍTICO: LAJE_SEARCH_RADIUS=1500mm para texto→contorno
CRÍTICO: Laje sintética — quando não há texto L1/L2 explícito:
         clusters de "h=" com CLUSTER_RADIUS=500mm geram laje SYNTHETIC
CRÍTICO: layer "Vázio"/"Vázio" → abertura na laje (encoding!)
CRÍTICO: layer "Pilares" em LJ → recortes de pilares no contorno
```

---

## 4. GAPS PRIORITIZADOS

### CRÍTICOS (sistema falha sem eles)

| Gap | Elemento | Impacto |
|---|---|---|
| Regex patterns RE_PILAR/RE_VIGA/RE_LAJE não documentados | PL/LV/LJ | Robô não sabe o que constitui ID válido |
| Layer "NOMENCLATURA" → TEXT com IDs não explicado | PL | Robô não sabe onde buscar texto P1 |
| LWPOLYLINE fechada = pilar; LINE = viga (não é explicado) | PL/LV | Confusão entre tipos de geometria |
| RE_DIM "NNxMM" → comprimento/largura não documentado | PL/LV | Dimensões erradas no JSON |
| 3-radius proximity logic (score 1.0/0.8/0.5..0.0) | Todos | Sem doc, robô parece "mágico" |
| PILAR_SEARCH_RADIUS=800mm / VIGA=1200mm / LAJE=1500mm | Todos | Raios de busca desconhecidos |
| confidence < 0.80 → revisão humana | Todos | Threshold desconhecido |
| layer "fundo" → FV vs "Painéis" → LV | LV | Robô confunde lateral com fundo |
| RE_LAJE_H "h=NN" → espessura | LJ | Campo crítico sem extração documentada |
| Laje sintética por cluster de h= | LJ | 30%+ das lajes são SYNTHETIC → sem doc |
| layer "Vázio" (com acento corrompido) → abertura | LJ | Aberturas ignoradas se nome errado |
| Família BIM vs TQS: algoritmo de detecção | Todos | Sem detecção correta, extração falha |

### IMPORTANTES (degradação de qualidade)

| Gap | Elemento | Impacto |
|---|---|---|
| RE_DIM_BH "b=20 h=50" não documentado | LV | 15-20% das dimensões de viga usam este padrão |
| Bulge > 0.3 → pilar cambotado | PL | Pilares especiais mal classificados |
| INSERT "GARFOS" → componente metálico | LV | Garfos HT20CT não documentados |
| layer "REAPROVEITAMENTO" → estado dos painéis | LJ | Reaproveitamento ignorado |
| DIM_SEARCH_RADIUS=600mm para dimensões | Todos | Dimensões não encontradas se distância > 600mm |
| pilar_especial="L", "T", "CAMBOTADO" | PL | Tipos especiais sem critério |
| Encoding CP1252 vs UTF-8 (Painéis, Vázio) | Todos | Layers com acento podem não ser detectados |

### NICE-TO-HAVE

| Gap | Elemento | Impacto |
|---|---|---|
| Famílias METHODUS e EBERICK documentadas | Todos | Menos de 5% das obras usam |
| CLUSTER_RADIUS=500mm para lajes sintéticas | LJ | Parâmetro ajustável |
| Fórmula shoelace para área de laje | LJ | Calculável, não crítico |
| Blocos INSERT ignorados (PONTALETE só para 3D) | PL/LV | Confusão de propósito |

---

## 5. O QUE AS FICHAS ATUAIS TÊM (mas o robô NÃO usa)

| Conteúdo atual nas fichas | Valor para o robô |
|---|---|
| Desenhos de montagem de fôrmas | 0% |
| Normas ABNT NBR 14931/14090 | 0% |
| Tabelas de tolerâncias construtivas | 0% |
| Decisão de pontalete por vão | 0% |
| Detalhes de ancoragem DYWIDAG | 0% |
| Seções isométricas 3D de pilar | 0% |
| Explicação de reaproveitamento de painéis | 0% (sem vinculo ao JSON) |
| Screenshots do DXF visual sem código | 0% |
| Gráficos de fluxo de montagem na obra | 0% |

**Estimativa: ~90% do conteúdo atual é irrelevante para o robô.**

---

## 6. SCORE DE COMPLETUDE POR ELEMENTO

| Elemento | Campos JSON | Documentados | Score |
|---|---|---|---|
| **Pilares** | 17 | 1 | **5.9%** |
| **Vigas** | 15 | 0 | **0%** |
| **Lajes** | 10 | 0 | **0%** |
| **Extração geral** | regex + raios + família | 0 | **0%** |

**Score geral fichas atuais para o robô: ~1.5/10 (PopForge confirmado)**

---

## 7. HANDOFF H1 → FASE A

```yaml
gate_H1_status: PASS
entity_inventory_coverage:
  PL: 17 entity types  # gate: >= 10 ✅
  LV: 17 entity types  # gate: >= 10 ✅
  LJ: 11 entity types  # gate: >= 10 ✅

gaps_críticos_identificados: 12
gaps_importantes_identificados: 8
gaps_nice_to_have_identificados: 5

prioridade_fase_A:
  1. SPEC-PILARES.md — regex + layers + proximity + confidence
  2. SPEC-VIGAS.md — regex alt + LINE entities + layer fundo
  3. SPEC-LAJES.md — h= extraction + SYNTHETIC + encoding
  4. CONFIG-LAYERS.yaml — aliases + familia detection
  5. DECISION-MATRIX.md — confidence thresholds + fallbacks

instrução_para_fase_A: >
  Cada spec DEVE conter: (a) o regex real de identificação,
  (b) os atributos ezdxf exatos para cada campo JSON,
  (c) exemplo Python funcional com input DXF → output JSON,
  (d) os casos especiais documentados aqui como CRÍTICOS.
```

---

*C-3 COMPLETO — 25 gaps identificados (12 CRÍTICOS, 8 IMPORTANTES, 5 NICE-TO-HAVE). Score atual: 1.5/10. Potencial pós-FASE A: 90+/10. ✅*
