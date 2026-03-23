# DECISION-MATRIX — Fallbacks e Confidence Scoring
## CAD-ANALYZER | 2026-03-19

---

## 1. CONFIDENCE THRESHOLDS

| Score | Classe | Ação |
|---|---|---|
| `>= 0.80` | **ALTO** | Auto-assign — aceitar sem revisão |
| `0.50 – 0.79` | **MÉDIO** | Aceitar com log de aviso |
| `0.30 – 0.49` | **BAIXO** | Fila de revisão humana |
| `< 0.30` | **MUITO BAIXO** | Rejeitar — não registrar no DB |

```python
CONF_AUTO    = 0.80   # auto-assign
CONF_WARN    = 0.50   # aceitar com aviso
CONF_REVIEW  = 0.30   # revisão humana obrigatória
CONF_REJECT  = 0.30   # abaixo disso → rejeitar
```

---

## 2. FÓRMULA DE CONFIDENCE

```python
def calcular_confidence(raio_score: float, tem_dimensao: bool,
                        tem_texto_id: bool, tem_contorno: bool) -> float:
    """Confidence base do TextAssociator + penalidades."""
    conf = raio_score  # 1.0 / 0.8 / 0.0..0.5 (lógica 3 raios)

    if not tem_dimensao:
        conf -= 0.30   # sem dimensão → penalidade
    if not tem_texto_id:
        conf -= 0.40   # sem ID → penalidade severa
    if not tem_contorno:
        conf -= 0.20   # sem contorno (só para pilar/laje)

    return max(0.0, min(conf, 1.0))
```

---

## 3. MATRIZ DE DECISÃO — CASOS AMBÍGUOS

| Situação | Condição | Ação | Confidence | Log |
|---|---|---|---|---|
| Texto dentro da polilinha | `polygon.contains(Point)` | Auto-assign | 1.0 | — |
| Texto tocando (dist ≤ 5mm) | `dist <= 5.0` | Auto-assign | 0.8 | — |
| Texto próximo (dist ≤ raio) | `dist <= search_radius` | Score decaimento | 0.0–0.5 | avisar se < 0.50 |
| Texto fora do raio | `dist > search_radius` | Ignorar | 0.0 | — |
| 2 textos competindo | ambos dentro do raio | Vence score maior | vencedor | log ambos |
| Empate exato de score | scores iguais | Revisão humana | score | log "EMPATE" |
| ID detectado, sem dimensão | RE_PILAR/RE_VIGA match, sem NNxMM | Registrar sem dim | conf -= 0.30 | "dim não encontrada" |
| Dimensão sem ID próximo | NNxMM, sem P/V/L texto | Desconsiderar dim | 0.0 | — |
| Laje sem ID explícito | sem L1/L2 mas h= detectado | SYNTHETIC | 0.50 | "laje sintética" |
| Layer desconhecido | não está em CONFIG-LAYERS | Processar mesmo assim | conf -= 0.10 | "layer UNKNOWN" |
| Encoding corrompido (Painéis) | "Pain?is" no DXF | normalize_layer() | sem penalidade | — |
| Família não detectada | nenhuma regra bate | default BIM | sem penalidade | "família: BIM (default)" |

---

## 4. FALLBACK CHAIN — POR ELEMENTO

### Pilares
```
1. Texto RE_PILAR em layer NOMENCLATURA → LWPOLYLINE fechada em Painéis
   → se encontrado: confidence = raio_score
2. Texto RE_PILAR em layer TEXTO_GERAL → mesmo fallback
   → se encontrado: confidence -= 0.05
3. Texto RE_PILAR em qualquer layer → LWPOLYLINE fechada em qualquer layer
   → se encontrado: confidence -= 0.15
4. Texto RE_PILAR sem LWPOLYLINE próxima
   → registrar sem contorno: confidence -= 0.40
5. Nenhum texto RE_PILAR encontrado
   → não registrar (LWPOLYLINE sozinha não é pilar sem ID)
```

### Vigas
```
1. Texto RE_VIGA → LINE em layer Painéis ou fundo dentro de VIGA_SEARCH_RADIUS=1200mm
   → confidence = raio_score
2. Texto RE_VIGA → LINE em qualquer layer (não Painéis/fundo)
   → confidence -= 0.15
3. Texto RE_VIGA + RE_DIM → largura/altura extraídas
   → +0 (esperado)
4. Texto RE_VIGA + RE_DIM_BH (b=20 h=50)
   → +0 (aceito igualmente)
5. Texto RE_VIGA sem dimensão próxima
   → largura=0, altura=0, confidence -= 0.30
6. BA*/VB* → balanço com 1 apoio → apoio_fim='' é esperado, não é erro
```

### Lajes
```
1. Texto RE_LAJE → LWPOLYLINE fechada grande (área > 50000mm²) dentro de 1500mm
   → confidence = raio_score
2. Texto RE_LAJE sem LWPOLYLINE
   → outline_segs=[], confidence -= 0.20
3. Sem texto RE_LAJE, mas clusters h= (CLUSTER_RADIUS=500mm)
   → laje SYNTHETIC, confidence = 0.50
4. Texto RE_LAJE_H isolado (sem cluster vizinho)
   → associar à laje mais próxima com score decaimento
5. Nenhum texto e nenhum h=
   → não registrar (área coberta por outras lajes)
```

---

## 5. CASOS ESPECIAIS — REGRAS FIXAS

| Caso | Regra |
|---|---|
| `BA*` ou `VB*` (balanço) | `tramos[0].apoio_fim = ''` — 1 apoio é correto |
| `pilar_especial` com `bulge > 0.3` | `tipo_pilar_especial = "CAMBOTADO"` |
| `comprimento < largura` em pilar | Trocar valores (comprimento = maior) |
| `largura < altura` em viga | OK — b < h por convenção |
| Laje `espessura < 7 cm` | Inválida — `confidence = 0` |
| Pilar `comprimento <= 0` | Inválido — revisão humana |
| Coordenadas UTM (x ou y > 50000) | Ignorar — georeferenciamento, não DXF de fôrmas |
| Encoding: layer com acento | Sempre `normalize_layer()` antes de comparar |

---

## 6. CAMPOS DE LOG OBRIGATÓRIOS

Para toda entidade com `confidence < 0.80`:

```python
log_entry = {
    "elemento_id": "P17",
    "tipo": "pilar",
    "confidence": 0.65,
    "motivo": "dim não encontrada (DIM_SEARCH_RADIUS=600mm)",
    "acao": "revisão humana",
    "raio_usado": 800,
    "dist_texto_poligono": 145.3,
    "layer_texto": "NOMENCLATURA",
    "layer_poligono": "Painéis"
}
```

---

## 7. REGRAS DE INTEGRIDADE CRUZADA

| Verificação | Condição de Alerta |
|---|---|
| Pilar sem viga em qualquer lado | `len(links) == 0` → "pilar isolado?" |
| Viga sem apoio_ini | `apoio_ini == ''` e não é balanço |
| Laje sem vigas vizinhas | `vigas_around == []` → suspeito |
| Viga com comprimento estimado > 1500 cm | `comprimento > 1500` → revisar |
| Pilar com área de seção > 2500 cm² | `comprimento * largura > 2500` → revisar |
| Laje com espessura 0 e não SYNTHETIC | `espessura == 0 and codigo != 'synth_*'` → erro |

---

*DECISION-MATRIX v1.0 | 7 seções | Fonte: agente_estrutural.py + validate_proximity_search.py*
