# Semântica dos Campos — Viga NOVA (Sistema Fôrma)
**Fonte:** Validação Sprint 1 Etapa 1.2, Obra_TREINO_1 — confirmada pelo usuário 2026-06-04
**Uso:** RAG, extratores Fase-3/4, motor_fase4.py, Robo LV, Robo FV

---

## 1. Dimensões da Seção Transversal

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `total_width` | float | Espessura da viga (b) em cm — largura do fundo |
| `total_height` | str/float | Altura da viga (h) em cm |

- `total_width` = dimensão perpendicular ao eixo da viga (a "espessura" do fundo)
- Para **Robo LV** (lateral): não influencia diretamente o tamanho dos painéis
- Para **Robo FV** (fundo): é a largura do retângulo do fundo

---

## 2. Painéis (panels[])

Cada entrada em `panels` representa um segmento horizontal da face lateral.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `panels[i].width` | float | Comprimento horizontal do segmento de painel (cm) |
| `panels[i].height1` | float | Altura do painel INFERIOR (cm) |
| `panels[i].height2` | float | Altura do painel SUPERIOR (cm) |
| `panels[i].grade_h1` | str | Comprimento do sarrafo horizontal 1 (SARR_3.5x7) na união |
| `panels[i].grade_h2` | str | Comprimento do sarrafo horizontal 2 (SARR_3.5x7) |

### 2.1 Distribuição de width (comprimento dos segmentos)

Regra de distribuição por `total_height`:

| Altura da viga | Max painel width |
|----------------|-----------------|
| h < 122cm      | 244cm (chapa completa rotacionada) |
| h ≥ 122cm      | 122cm (chapa padrão vertical) |

**Exemplo V10 (h=50cm < 122):** comprimento=1009cm → ceil(1009/244) = 5 painéis, cada um ≤244cm  
**BUG LV-B2:** `motor_fase4.py` usa `MAX_PANEL_WIDTH = 120.0cm` fixo para todos os casos (ignorando a regra de h).

### 2.2 height1 / height2 — Dois Níveis de Painéis

Uma viga pode ter:
- **Somente height1**: 1 nível de painéis, do fundo ao topo
- **height1 + height2**: 2 níveis sobrepostos com possível laje entre eles
  - `height1` = altura do painel INFERIOR (do fundo até a laje ou até o nível intermediário)
  - `height2` = altura do painel SUPERIOR (da laje até o topo)
  - height1 + height2 + espessura_laje = total_height

### 2.3 grade_h1 / grade_h2 — Sarrafos Horizontais SARR_3.5x7

Os sarrafos horizontais são barras de 3.5cm de espessura que percorrem o comprimento do painel:
- Posicionadas nas **uniões entre painéis** ou a **7cm das extremidades**
- Comprimento padrão = **largura do painel** (`panel.width`)
- Em casos de reaproveitamento: podem ser maiores que o painel

**Posições verticais dos sarrafos horizontais (por altura):**

| Altura do painel | Sarrafos verticais | Posições |
|-----------------|-------------------|----------|
| h < 30cm        | 2 sarrafos        | 7cm do fundo ("baixo"), 7cm do topo ("cima") |
| 30 ≤ h < 80cm   | 4 sarrafos        | 7 "baixo", 7 "cima", 3.5 "centro_cima", 3.5 "centro_baixo" |
| h ≥ 80cm        | mais sarrafos     | ver gerador_script_viga.py |

**V10 (h=50cm):** 4 sarrafos horizontais por painel
**BUG LV-B1:** `grade_h1` e `grade_h2` sempre "0" — extrator não implementado

---

## 3. Convenção de Lados (side A / B)

| Orientação da viga | Side A | Side B |
|-------------------|--------|--------|
| Viga HORIZONTAL   | Face INFERIOR (linha de baixo no plano) | Face SUPERIOR (linha de cima) |
| Viga VERTICAL     | Face ESQUERDA | Face DIREITA |

Sempre geram dois arquivos JSON: `{viga}_A.json` e `{viga}_B.json`

---

## 4. holes — Aberturas na Face Lateral

| Campo | Descrição |
|-------|-----------|
| `holes[i].active` | Se a abertura está presente |
| `holes[i].width` | Largura da abertura (cm) |
| `holes[i].height` | Altura da abertura (cm) |
| `holes[i].position` | Distância do início da face até o centro da abertura (cm) |

**Quando ativa:** passagem de viga transversal, pilar que corta a face lateral, ou outro elemento estrutural que intersecta a face.

**BUG LV-B4:** `holes` sempre inactivo — extrator não detecta aberturas

---

## 5. pillar_left / pillar_right — Pilar na Extremidade

Representa a situação onde a viga PASSA SOBRE um pilar (pilar no meio do vão ou nas extremidades da viga).

| Campo | Descrição |
|-------|-----------|
| `pillar_left.active` | Se há pilar na extremidade esquerda |
| `pillar_left.width` | Distância do início da viga até a parede do pilar (cm) |
| `pillar_left.length` | Espessura do pilar no sentido do eixo da viga (cm) |
| `pillar_right.*` | Idem para extremidade direita |

**Exemplo:** Se a viga começa 5cm antes de um pilar de 20cm:
- `pillar_left.active = true`
- `pillar_left.width = 5`
- `pillar_left.length = 20`

**BUG LV-B3:** `pillar_left/right` sempre inactivo — extrator não detecta interseção pilar×viga

---

## 6. sarrafo_left_id / sarrafo_right_id

Identificadores dos sarrafos verticais de 7cm de espessura nas extremidades do painel lateral.

- `sarrafo_left_id = 0` → nenhum sarrafo especial à esquerda (0 = padrão geral)
- Geralmente gerado para TODOS os painéis (sarrafos nas extremidades são regra)
- Casos especiais sem sarrafo: a aprender via mais obras (regra ainda não formalizada)

---

## 7. Tabela Completa de Campos — Viga (LV/FV)

| Campo | Tipo | Descrição | Status |
|-------|------|-----------|--------|
| `number` | str | Número da viga (ex: "10") | Extraído |
| `name` | str | Nome + side (ex: "V10_A") | Extraído |
| `floor` | str | Pavimento (ex: "12 PAV") | Extraído |
| `side` | str | "A" ou "B" (ver conv. acima) | Extraído |
| `total_width` | float | Espessura b (cm) | Extraído |
| `total_height` | str | Altura h (cm) | Extraído |
| `panels[].width` | float | Comprimento do segmento (cm) | Extraído |
| `panels[].height1` | float | Altura painel inferior (cm) | Extraído |
| `panels[].height2` | float | Altura painel superior (cm) | Extraído |
| `panels[].grade_h1` | str | Comprimento SARR_3.5x7 nível 1 | **BUG: sempre "0"** |
| `panels[].grade_h2` | str | Comprimento SARR_3.5x7 nível 2 | **BUG: sempre "0"** |
| `holes[].active` | bool | Abertura presente | **BUG: sempre false** |
| `holes[].width` | float | Largura abertura (cm) | Não extraído |
| `holes[].height` | float | Altura abertura (cm) | Não extraído |
| `holes[].position` | float | Posição da abertura (cm) | Não extraído |
| `pillar_left.active` | bool | Pilar na extremidade esquerda | **BUG: sempre false** |
| `pillar_left.width` | float | Distância até o pilar (cm) | Não extraído |
| `pillar_left.length` | float | Espessura do pilar (cm) | Não extraído |
| `pillar_right.*` | — | Idem extremidade direita | Não extraído |
| `sarrafo_left_id` | int | ID sarrafo extremidade esquerda | 0 = padrão |
| `sarrafo_right_id` | int | ID sarrafo extremidade direita | 0 = padrão |

---

## 8. Bugs Conhecidos (Viga)

| # | Campo | Problema | Status |
|---|-------|----------|--------|
| LV-B1 | `grade_h1`, `grade_h2` | Extrator não implementado, sempre "0" | ABERTO |
| LV-B2 | `panels[].width` | `MAX_PANEL_WIDTH=120cm` fixo; deveria ser 244cm se h<122, 122cm se h≥122 | ABERTO |
| LV-B3 | `pillar_left/right` | Interseção pilar×viga não detectada | ABERTO |
| LV-B4 | `holes` | Aberturas não detectadas | ABERTO |
