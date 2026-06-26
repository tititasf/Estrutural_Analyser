# Semântica dos Campos — Laje NOVA (Sistema Fôrma)
**Fonte:** Validação Sprint 1 Etapa 1.3, Obra_TREINO_1 — confirmada pelo usuário 2026-06-04
**Uso:** RAG, extratores Fase-3/4, motor_fase4.py, Robo Lajes (LJ)

---

## 1. Dimensões

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `comprimento` | float | Maior dimensão da laje (cm) — direção dos painéis de 244cm |
| `largura` | float | Menor dimensão da laje (cm) — direção dos painéis de 122cm |
| `area_cm2` | float | Área total em cm² |

**Regra:** `comprimento` = SEMPRE a maior dimensão. Os painéis de 244cm são posicionados na direção do comprimento.

---

## 2. coordenadas

Polígono do contorno da laje em cm, formato `[[x,y], [x,y], ...]`:
- Valores em centímetros, mesma perspectiva do arquivo estrutural DXF
- Fecha repetindo o primeiro ponto no final
- **Exemplo L1:** `[[0,195],[125,195],[125,0],[0,0],[0,195]]` — retângulo 125×195

---

## 3. linhas_verticais / linhas_horizontais — Grid de Painéis

As linhas definem como preencher a área da laje com chapas NOVA (244×122cm).

### 3.1 Semântica do campo

| Campo | Descrição |
|-------|-----------|
| `linhas_verticais[i].value` | Posição cumulativa do corte, medida a partir do início (cm) |
| `linhas_verticais[i].is_union` | `true` quando o segmento termina com valor ≤ 30cm (emenda, não secciona o painel) |
| `linhas_horizontais[i].value` | Idem na direção perpendicular |

**Exemplo L1 (comprimento=195):**
- `{value:100, is_union:false}` → corte na posição 100cm (painel de 0→100)
- `{value:195, is_union:false}` → borda final em 195cm (painel de 100→195 = 95cm)

### 3.2 Quando existem linhas em cada direção

O objetivo é preencher TODA a superfície com painéis 244×122cm, usando-os da melhor maneira e recortando quando necessário:

| Condição | linhas_verticais | linhas_horizontais |
|----------|-----------------|-------------------|
| comprimento > 244cm | tem cortes | — |
| comprimento ≤ 244cm | pode ser vazio (painel cobre tudo) | — |
| largura > 122cm | — | tem cortes |
| largura ≤ 122cm | — | pode ser vazio |
| Laje irregular ou com obstáculos | cortes conforme contorno | idem |

### 3.3 is_union — Segmento de Emenda

`is_union = true` quando o segmento resultante tem tamanho ≤ 30cm:
- Esse segmento não secciona o painel (o painel passa contínuo)
- Representa uma linha de emenda/união entre chapas adjacentes
- Visualmente: linha desenhada mas sem separar os painéis

### 3.4 Algoritmo atual vs algoritmo correto

**Bug LJ-B1 — motor_fase4.py usa STEP=100cm fixo:**
```python
# ERRADO (atual)
STEP = 100.0
pos += STEP
is_union = (value <= 30)
```

**Algoritmo correto (calculo_modo1.py do Robo Lajes):**
- Primeiro ciclo: 122cm + 60cm + união (20-30cm)
- Ciclos seguintes: 122cm + união
- Meta: zero sobra, uniões entre 20-30cm

---

## 4. modo_selecionado

Define o sentido/orientação dos painéis de acordo com a dimensão da área:
- `modo_selecionado = 0` → automático (Modo 1: painéis alinhados com comprimento)
- Outros valores: modos alternativos de posicionamento (ler `calculo_modo1.py` para lógica completa)

---

## 5. obstaculos — Ilhas Internas

Elementos INTERNOS à área da laje que criam "buracos" no preenchimento:
- Pilares centrais
- Colunas internas
- Aberturas (escadas, vazios estruturais)
- Recortes de projeto

Cada obstáculo define uma região a subtrair da área total de painéis.

---

## 6. unioes_nos_bordes

`false` = padrão normal (sem tratamento especial nas bordas)
`true` = há painéis de borda de 20cm nas extremidades do marco — caso especial de projeto, raramente usado.

---

## 7. pontaletes

Apoios verticais da laje (escoras/pontaletes). Campo ainda **não definido** no sistema — ignorar por enquanto.

---

## 8. Tabela Completa de Campos — Laje (LJ)

| Campo | Tipo | Descrição | Status |
|-------|------|-----------|--------|
| `numero` | int | Número da laje | Extraído |
| `nome` | str | Nome (ex: "L1") | Extraído |
| `comprimento` | float | Maior dimensão (cm) | Extraído |
| `largura` | float | Menor dimensão (cm) | Extraído |
| `pavimento` | str | Pavimento | Extraído |
| `coordenadas` | list | Polígono do contorno [[x,y]...] | Extraído |
| `area_cm2` | float | Área total (cm²) | Extraído |
| `linhas_verticais` | list | Posições cumulativas de corte vertical | Extraído (BUG step) |
| `linhas_horizontais` | list | Posições cumulativas de corte horizontal | Extraído |
| `obstaculos` | list | Ilhas internas (pilares, aberturas) | Sempre [] |
| `modo_selecionado` | int | Modo de distribuição dos painéis | Extraído |
| `unioes_nos_bordes` | bool | Painéis de borda 20cm nas extremidades | Extraído |
| `pontaletes` | dict | Apoios verticais (não definido) | Ignorar |

---

## 9. Bugs Conhecidos (Laje)

| # | Campo | Problema | Status |
|---|-------|----------|--------|
| LJ-B1 | `linhas_verticais` | `motor_fase4.py` usa STEP=100cm fixo; algoritmo correto em `calculo_modo1.py` (122+60+união) | ABERTO |
| LJ-B2 | `obstaculos` | Sempre lista vazia — extrator não detecta ilhas internas (pilares centrais, aberturas) | ABERTO |
