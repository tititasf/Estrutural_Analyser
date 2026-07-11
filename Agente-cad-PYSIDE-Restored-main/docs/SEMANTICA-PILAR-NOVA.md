# Semântica dos Campos — Pilar NOVA (Sistema Fôrma)
**Fonte:** Validação Sprint 1, Obra_TREINO_1 — confirmada pelo usuário 2026-06-04
**Uso:** RAG, extratores Fase-3/4, motor_fase4.py, robos SCR

---

## 1. Nomenclatura das Faces (CONVENÇÃO CORRETA)

```
Vista em planta do pilar:

        Face B (longo, comprimento)
       ┌────────────────────────────┐
Face D │                            │ Face C
(curto,│          PILAR             │ (curto,
largura│          P1                │ largura
  19cm)│       66 × 19 cm           │   19cm)
       └────────────────────────────┘
        Face A (longo, comprimento)
```

| Face | Tipo | Campo `larg1_X` | Valor para P1 |
|------|------|-----------------|---------------|
| A    | LONGO (comprimento) | comprimento | 66cm |
| B    | LONGO (comprimento) | comprimento | 66cm |
| C    | CURTO (largura)     | largura     | 19cm |
| D    | CURTO (largura)     | largura     | 19cm |
| E-H  | Faces especiais (pilar L/T/U) | 0 se pilar retangular | 0 |

> ⚠️ **BUG CONHECIDO NO SISTEMA (Fase-3/4):** motor_fase4.py atribui A/C=longo e B/D=curto (ERRADO).
> `larg1_B` está com 19cm (curto) mas deveria ser 66cm (longo).
> `larg1_C` está com 66cm (longo) mas deveria ser 19cm (curto).

---

## 2. Distribuição de Altura — Painéis da Chapa

```
VISTA LATERAL (face A, exemplo P1 h=280cm, sem laje):

  280cm ┤ topo
        │ h3 = 34cm  (sobra do corte, último painel)
  246cm ┤
        │
        │ h2 = 244cm (chapa inteira padrão NOVA 244×122)
        │
    2cm ┤
        │ h1 = 2cm   (cinta inferior, FIXO)
    0cm ┤ base
```

**Regras de distribuição (lógica NOVA):**
- `h1 = 2cm` — sempre fixo, cinta inferior (espaçador)
- `h2, h2_2, ...` — preencher com chapas inteiras (244cm) ou meias (122cm), maximizando uso
  - Prioridade: 244cm → 122cm → pedaços
  - Para altura de 280cm (sem laje): h1=2 + h2=244 = 246, sobra=34 → h3=34cm
  - Para altura de 280cm com laje de 12cm: h_útil=280-12=268, h1=2, h2=244, sobra=22 → h3=22cm
- `h3` — NÃO É FIXO. É o que sobra após distribuição.
- `h4` — extensão acima do pé-direito, para dentro da espessura da laje (0 se laje não sobe além do pilar)
- `h5` — reservado

**Chapas disponíveis (sistema NOVA):** 244 × 122cm (inteira) | 122 × 122cm (meia)

---

## 2.1 Cotas verticais ABCD — degraus (níveis 1 / 2 / 3)

As cotas verticais de cada face **não ficam todas na mesma coluna**: há degraus
horizontais (offset a partir do bordo direito da face) para não sobrepor texto.

Medido no DXF manual P1_PARA (offsets ≈ distância da linha de cota ao bordo):

| Nível | Offset (cm) | O que entra | Cor / estilo |
|-------|-------------|-------------|--------------|
| **1** | **17** | Cinta **h1 = 2 cm**; cotas de **recorte/abertura** no painel (ex. 66 do fundo da abertura até a próxima junta) | COTA ciano |
| **2** | **40** | Medidas dos **painéis** da malha (módulos 122, sobra 58, trechos 37/14/7 de rebaixo-vazio no miolo dual, faixa laje C/D) | COTA ciano |
| **3** | **63** | **Painéis unidos** pelo mesmo sarrafo: cota **total** da soma (ex. 100+22 → total **122**), além das partes no nível 2 | COTA ciano |

```
        bordo face ──►
              │  N1 (17)      N2 (40)       N3 (63)
              │  ├─ 2 (h1)    ├─ 122        ├─ 122 total (unido)
              │  ├─ 66 (rec)  ├─ 100        │   (só se paineis_unidos_*)
              │               ├─ 22
              │               ├─ 58
```

### Painéis unidos (mesmo sarrafo) — campo opcional

O robô **não gera sozinho** união 100+22: a malha default é módulo inteiro 122.
O dono pode editar o JSON e o N3 (modo NOVA) deve respeitar:

```json
"paineis_intervals_A": [122.0, 122.0, 58.0],
"paineis_unidos_A": [
  {
    "interval_index": 0,
    "parts": [100.0, 22.0]
  }
]
```

| Campo | Significado |
|-------|-------------|
| `interval_index` | Índice em `paineis_intervals_{face}` que é subdividido (0 = primeiro módulo acima de h1) |
| `parts` | Alturas parciais (cm); **soma deve ≈** o valor do interval (tol 0.6 cm) |

**Efeitos no desenho:**
1. **Linha de painel extra** em cada junção interna das `parts` (ex. a 100 cm do início do módulo) — camada `Painéis`, mesma regra de H full/parcial que o resto da malha.
2. **Cotas nível 2:** cada `part` (100 e 22), **não** o 122 “inteiro” isolado nesse trecho.
3. **Cota nível 3:** uma cota do **total** (122) abrangendo o intervalo unido inteiro.
4. **Sarrafo NÃO seccionado** na junção das parts (contínuo) — é o que justifica a cota N3.

Sem `paineis_unidos_*`, o comportamento é só N1+N2 (como hoje, com degraus).

### Seccionamento de sarrafos nos cruzamentos com painéis

Referência: `PL_ABCD_preview_P1-exemplosarrafos.dxf`.

- Sarrafos verticais (pressão HIDDEN A/B, SARR de abertura/marco, SARR C/D) são
  **cortados em cada junta de módulo lógico** (Ys de `paineis_intervals_*`).
- Ex.: malha [122, 122, 58] → pressão em trechos 122 + 122 + 58, não um fuste contínuo de 302.
- **Exceção:** em `paineis_unidos_*`, o fuste **atravessa** a linha extra das parts
  (mesmo sarrafo) → aí sim existe cota **nível 3** do total.
- Cota horizontal de offset **7 cm** do sarrafo: só faces **A e B** (não C/D).

Constantes no gerador:
`DIM_LVL1_OFF`, `DIM_LVL2_OFF`, `DIM_LVL3_OFF`.

### Modo visual INI vs NOVA (perfil final)

A **geometria** (malha, aberturas, rebaixo, seccionamento, cotas N1/N2/N3, hatch)
é **idêntica** para PARA e PASSA e para qualquer item. Só o perfil de traço muda:

| | **NOVA** | **INI** (templates SCR) |
|--|----------|-------------------------|
| Sarrafo sólido (abertura, marco, H sob vazio laje/viga, fustes C/D) | LINE / LWPOLY | **MLINE** estilo SAR3 |
| Sarrafo de pressão (HIDDEN) e outros DASHED | LINE HIDDEN | **LINE** (não vira MLINE) |
| Layers / cores | paleta atual | remapeamento legado + BYLAYER |

Aplicado em `scripts/visual_modes.apply_visual_mode(..., robot_class="PL")` no fim da geração.

---

## 3. Grade — Comprimento e Parafusos

### grade_1 (campo JSON, medido no DXF)
```
grade_1 = comprimento_faces_AB + 22cm  (11cm de extensão de cada lado)

Exemplo P1: grade_1 = 66 + 22 = 88cm
```

A grade é a **barra horizontal metálica** que passa pelos furos da chapa e se prolonga além do pilar para fixação. Aplica-se às **faces A e B** (lados longos).

### Quantidade de parafusos (faces A e B)
Determinada pelo `grade_calculator.py` com base em `comprimento_ajustado = comprimento + 24`:

| Comprimento face | Qtd parafusos | par fields usados |
|-----------------|---------------|-------------------|
| ≤ 120cm         | 2             | par_1_2           |
| 121–195cm       | 3             | par_1_2, par_2_3  |
| 196–260cm       | 4             | par_1_2..par_3_4  |
| 261–330cm       | 5             | par_1_2..par_4_5  |
| 331–400cm       | 6             | par_1_2..par_5_6  |
| 401+            | 7+            | ...               |

Para P1 (comprimento=66cm, ajustado=90): **2 parafusos**, par_1_2=45, par_2_3=45
→ Soma: 45+45=90 = comprimento_ajustado ✓

### par_1_2, par_2_3, ... (espaçamento HORIZONTAL entre parafusos)
São os espaçamentos (em cm) entre parafusos consecutivos **ao longo da grade** (direção horizontal, paralela às faces A/B).
- Os valores somam `comprimento_ajustado = comprimento + 24`
- Distribuídos simetricamente (extremos maiores ou iguais ao centro)

### distancia_1, distancia_2 (interpretação)
- `distancia_1` = distância entre a grade 1 e a grade 2 (grades paralelas na mesma face)
- `distancia_2` = distância entre grade 2 e grade 3
- Quando grade_2=0: distancia_2=0

> Nota: o campo `medida_fundo_primeiro_ab=30` em config_abcd.json é o espaçamento VERTICAL
> entre a base do pilar e o primeiro parafuso (na direção da altura, não da grade).

---

## 4. Posicionamento da Laje (posicao_laje_X)

A laje sempre passa em alguma face do pilar. Quando passa:
- `laje_X` = espessura da laje em cm (ex: 12cm)
- `posicao_laje_X` = número do painel acima do qual a laje está posicionada:

```
Painéis numerados de baixo para cima:

  painel 1 = h1 (2cm)
  painel 2 = h2 (244cm, o principal)
  painel 3 = h3 (sobra)
  ...

posicao_laje = 0          → fundo (laje no piso base)
posicao_laje = 1          → acima do painel 1 (acima da cinta inferior)
posicao_laje = 2          → acima do painel 2 (acima do corpo principal)
posicao_laje = 5 (topo)   → acima de todos os painéis (laje no topo)
```

Se nenhuma face tem laje: `laje_X=0, posicao_laje_X=0` para todas as faces.

---

## 5. Campos do JSON Pilar — Tabela Completa

| Campo | Tipo | Descrição | Regra / Fórmula |
|-------|------|-----------|-----------------|
| `comprimento` | float | Dimensão maior (faces A, B) em cm | Medido no DXF, layer BH |
| `largura` | float | Dimensão menor (faces C, D) em cm | Medido no DXF, layer BH |
| `altura` | float | Pé-direito do pavimento (cm) | Cota de nível no DXF |
| `nivel_chegada` | float | Cota base do pilar (cm) | 0.0 para pavimento base |
| `nivel_saida` | float | Cota topo (cm) | nivel_chegada + altura |
| `h1_X` | float | Cinta inferior face X (cm) | Fixo = 2.0 |
| `h2_X` | float | Corpo principal face X (cm) | Chapa 244 ou 122 |
| `h3_X` | float | Sobra/último painel face X (cm) | altura - laje - h1 - Σh2 |
| `h4_X` | float | Extensão dentro da laje (cm) | 0 se laje não sobe acima |
| `h5_X` | float | Reservado | 0 |
| `larg1_X` | float | Largura da chapa face X (cm) | A/B=comprimento, C/D=largura |
| `larg2_X` | float | Segunda largura (pilar especial) | 0 para retangular |
| `larg3_X` | float | Terceira largura (pilar especial) | 0 para retangular |
| `laje_X` | float | Espessura da laje na face X (cm) | 0 se face não tem laje |
| `posicao_laje_X` | int | Nº do painel acima do qual a laje está | 0=fundo, N=acima painel N, 5=topo |
| `grade_1` | float | Comprimento da grade principal (cm) | comprimento_AB + 22 |
| `grade_2` | float | Comprimento da 2ª grade (cm) | 0 para pilares pequenos |
| `distancia_1` | float | Distância entre grade 1 e grade 2 | Config robo |
| `distancia_2` | float | Distância entre grade 2 e grade 3 | Config robo |
| `par_1_2` | float | Espaç. horizontal parafuso 1→2 (cm) | Calc: (comprimento+24)/qtd_par |
| `par_2_3` | float | Espaç. horizontal parafuso 2→3 (cm) | 0 se qtd_par < 3 |
| `par_N_M` | float | Espaç. parafuso N→N+1 | 0 se não usado |
| `modo_distribuicao` | str | Padrão construtivo | "NOVA" (padrão desta obra) |
| `paineis_intervals_X` | list[float] | Deltas de malha H acima de h1 (cm) | NOVA: 122+sobra; C/D passante: painel contínuo |
| `paineis_unidos_X` | list[dict] | Subdivisão manual de módulo (parts + total N3) | Opcional; ver §2.1 — robô não gera sozinho |

---

## 6. Inconsistências Conhecidas (Bugs a Corrigir)

| # | Campo | Problema | Status |
|---|-------|----------|--------|
| B1 | `larg1_B`, `larg1_C` | Nomenclatura A/C=longo invertida; B deveria ter comprimento | ABERTO |
| B2 | `laje_X`, `posicao_laje_X` | Sistema não detecta lajes no extrator DXF | ABERTO |
| B3 | `grade_h1`, `grade_h2` nas vigas | Sempre "0", extrator não implementado | DOCUMENTADO |
| B4 | `h2_E..H` pilar | Faces E-H copiavam h2=244 do retangular | CORRIGIDO (motor_fase4 2026-06-04) |
| B5 | `coordenadas[-1]` laje | Polígono com 3 vértices fechava em [0,0] em vez de [0,L] | CORRIGIDO (motor_fase4 2026-06-04) |
