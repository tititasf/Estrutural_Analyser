# Interpretação de Lajes e Vigas que Passam para Pilares ABCD

> Documento de referência para o Structural Analyzer (SA).  
> Define como classificar o conteúdo de cada face (A, B, C, D) de um pilar  
> a partir da geometria da planta baixa (top view / DXF).

---

## Convenção de faces

```
PILAR VERTICAL (ph > pw):          PILAR HORIZONTAL (pw >= ph):

       C (topo/cima)                     B (topo — parede longa)
       ↑                           ←──────────────────────────→
  ┌────┴────┐                      ┌──────────────────────────┐
  │         │                      │                          │
A │         │ B            LAJE  A │          P1              │ B  LAJE
  │   P1    │              ←──── │ │     (horizontal)         │ │ ─────→
  │         │                      │                          │
  └────┬────┘                      └──────────────────────────┘
       ↓                           ←──────────────────────────→
       D (base/baixo)                    A (base — parede longa)
```

| Face | Pilar Vertical       | Pilar Horizontal     |
|------|----------------------|----------------------|
| A    | Esquerda (longa)     | Base/baixo (longa)   |
| B    | Direita (longa)      | Topo/cima (longa)    |
| C    | Topo / cima (curta)  | Esquerda (curta)     |
| D    | Base / baixo (curta) | Direita (curta)      |

---

## Lógica de classificação por face

Para cada face, a classificação é determinada pelo **alinhamento geométrico**,
não pelo simples toque de polígonos:

| Resultado   | Condição                                                   |
|-------------|-----------------------------------------------------------|
| **VIGA**    | A face está alinhada com a parede de uma viga              |
| **LAJE**    | A face está deslocada dentro da área de uma laje, sem alinhar com parede de viga |
| **VAZIA**   | A face está deslocada para fora, sem contato com elemento  |
| **VIGA + LAJE** | Face alinhada com parede de viga E com laje adjacente (ver Caso 5 Extra) |

A ficha de interpretação e o motor SA respondem, em cada face, às **três famílias**
(Lajes · Vigas que passam · Vigas que chegam/interior), sempre com **dimensão e nível**
quando existirem na planta. Ver seções no final deste documento:
*Três famílias obrigatórias por face*, *Dualidade esquina C*, *Exemplo canônico P2*.

---

## Casos para faces C e D

### Caso 1 — Face C (CIMA) encostada na parede da viga acima → C = VIGA

```
TOP VIEW:

════════════════════════════════════════
║              Viga VF301              ║
════╧════╧═══════════════════════════════  ← face C = parede inferior da Viga VF301
    │    │
    │ P1 │   ← pilar VERTICAL (C=topo, D=base)
    │    │
    └────┘
```

**C = VIGA** — Face C (topo do pilar) encosta na parede inferior da viga acima.  
Preencher: slots **Vigas que Passam — Esquina CA / CB** (esquerda/direita da face C)
com nome e dimensão. Contorno esq/dir foi removido da UI.

---

### Caso 2 — Face D (BAIXO) encostada na parede da viga abaixo → D = VIGA

```
TOP VIEW:

    ┌────┐
    │    │
    │ P1 │   ← pilar VERTICAL (C=topo, D=base)
    │    │
════╤════╤═══════════════════════════════  ← face D = parede superior da Viga VF302
║              Viga VF302              ║
════════════════════════════════════════
```

**D = VIGA** — Face D (base do pilar) encosta na parede superior da viga abaixo.  
Preencher: campo `Viga que Passa` com nome e dimensão da viga.

---

### Caso 3 — C e D flutuando dentro da laje → C = LAJE, D = LAJE

```
TOP VIEW:

════════════════════════════════════════
║              Viga VF302              ║
════════════════════════════════════════
│           LAJE L302                  │
│              ↑ face C (CIMA/topo)    │
│           ┌────┐                     │
│           │ P1 │                     │
│           └────┘                     │
│              ↓ face D (BAIXO/base)   │
│           LAJE L301                  │
════════════════════════════════════════
║              Viga VF301              ║
════════════════════════════════════════
```

**C = LAJE, D = LAJE** — Pilar deslocado dentro da área de laje, sem alinhar  
com nenhuma parede de viga.  
Preencher: campo `Laje 1` com o nome da laje adjacente a cada face.

---

### Caso 4 — Pilar VERTICAL completamente dentro da viga → C = VIGA, D = VIGA (internos)

```
TOP VIEW:

════════════════════════════════════════
║        ┌────┐                        ║
║        │ P1 │   Viga VF301           ║
║        └────┘   (pilar mais estreito)║
════════════════════════════════════════
```

**Todos os lados = VIGA** — Pilar completamente no interior da viga.  
C e D (e A e B) são faces internas dentro do corpo da viga.

---

### Caso 5 — Pilar HORIZONTAL mesma altura da viga contínua → C = VIGA, D = VIGA

```
TOP VIEW:

    LAJE          LAJE           LAJE
════════════════════════════════════════════  ← B (parede superior, LAJE acima)
║    Viga (esq)  │        │  Viga (dir)    ║
║                C   P1   D                ║
════════════════════════════════════════════  ← A (parede inferior, LAJE abaixo)
    LAJE          LAJE           LAJE

                  C        D
                (VIGA)   (VIGA)
```

**C = VIGA** — Viga entra pelo lado esquerdo do pilar.  
**D = VIGA** — Viga sai pelo lado direito do pilar.  
**A e B** → ver seção de casos A/B abaixo.

---

## Casos para faces A e B

A e B são as **faces longas** do pilar vertical (esquerda e direita).  
No pilar horizontal, A e B são as **paredes longitudinais** (base e topo).

### Resumo por caso

| Caso | A          | B          | Observação                          |
|------|------------|------------|--------------------------------------|
| 1    | Laje/Vazio | Laje/Vazio | Pilar vertical toca viga apenas em C |
| 2    | Laje/Vazio | Laje/Vazio | Pilar vertical toca viga apenas em D |
| 3    | Laje/Vazio | Laje/Vazio | Pilar flutuando na laje              |
| 4    | **VIGA**   | **VIGA**   | Pilar completamente dentro da viga   |
| 5    | Laje/Vazio + Viga que Passa | Laje/Vazio + Viga que Passa | Ver Caso 5 Extra abaixo |

---

### Caso 5 Extra — A e B alinhados com parede da viga → preencher AMBOS os campos

No Caso 5 (pilar horizontal dentro de viga contínua), as faces A e B estão
**alinhadas com as paredes longitudinais da viga**. Isso significa que há
simultaneamente:

1. **Contato com a laje** — a laje está além da parede da viga, adjacente a A ou B.
2. **Alinhamento com a viga** — a parede da viga coincide com a face A ou B.

```
TOP VIEW — detalhe do lado A (parede inferior):

════════════════════════════════════════════  ← A = parede inferior da viga
║    Viga (esq)  │        │  Viga (dir)    ║
════════════════════════════════════════════
           ↓ laje abaixo (além da parede)
    LAJE L101          LAJE L102
```

**Regra:** Preencher **dois campos** para a face A e dois para a face B:

| Campo              | Conteúdo                                      |
|--------------------|-----------------------------------------------|
| `Laje 1`           | Nome da laje adjacente (ex: L101)             |
| `Viga que Passa`   | Nome + dimensão da viga alinhada (ex: VF301)  |

Ambos os vínculos devem ser registrados na pré-ficha e vinculados ao pilar.  
A laje fornece o nível e a altura; a viga fornece a dimensão e o alinhamento.

---

## Regra geral de detecção

```
Para cada face F do pilar:

1. Há parede de viga alinhada com F?
   ├── SIM → F = VIGA
   │         (se também há laje além → preencher Laje 1 + Viga que Passa)
   └── NÃO → F está dentro de área de laje?
              ├── SIM → F = LAJE  (preencher Laje 1)
              └── NÃO → F = VAZIO (deixar em branco ou N/A)
```

---

## Campos da pré-ficha por face

Cada face A, B, C, D tem os seguintes campos na ficha:

| Campo          | Descrição                                      |
|----------------|------------------------------------------------|
| `Laje 1 Nome`  | Nome da primeira laje adjacente               |
| `Laje 1 H`     | Altura da laje 1                              |
| `Laje 1 Nível` | Nível (cota) da laje 1                        |
| `Laje 2 Nome`  | Nome da segunda laje (quando houver duas)     |
| `Laje 2 H`     | Altura da laje 2                              |
| `Laje 2 Nível` | Nível (cota) da laje 2                        |
| `Viga Nome`    | Nome da viga que passa/corre nessa face       |
| `Viga Dim`     | Dimensão da viga (ex: 19×60)                  |
| `Viga Nível`   | Nível da viga                                 |

**Regra de preenchimento:**
- Face com VIGA apenas → preencher só campos de Viga.
- Face com LAJE apenas → preencher só campos de Laje 1 (e Laje 2 se houver).
- Face VAZIO → deixar todos em N/A.
- Face Caso 5 Extra (alinhada com viga E toca laje) → preencher **ambos**:  
  campos de Laje 1 **e** campos de Viga que Passa.

---

## Guia de Validação de QA — Cotas de Nível em Fôrmas (Pilares vs Vigas/Lajes)

### 1. Distinção por Tipo de Elemento
* **Vigas e Lajes (Elementos Horizontais do Pavimento)**:
  - **SÓ POSSUEM NÍVEL DE CHEGADA** ($N_{\text{chegada}}$).
  - Não possuem "Nível de Saída" (são elementos planos no topo do andar).
  - O $N_{\text{chegada}}$ padrão de vigas e lajes é o **Nível de Chegada do Pavimento Atual** (ex: `852.19cm` / `+85,219m` no 13º PAV).
  - Lajes rebaixadas aplicam o delta de rebaixo (ex: `L301` com $-7\text{cm}$ $\rightarrow$ $852.19 - 0.07 = \mathbf{852.12cm}$ / `+85,212m`).

* **Pilares (Elementos Tridimensionais Verticais Contínuos)**:
  - **POSSUEM NÍVEL DE SAÍDA E NÍVEL DE CHEGADA**.
  - **Nível de Saída ($N_{\text{saída}}$)**: Cota de partida na base do pilar (piso do pavimento inferior = $N_{\text{chegada}}$ do $N-1$º PAV, ex: 12º PAV = `848.98cm` / `+84,898m`).
  - **Nível de Chegada ($N_{\text{chegada}}$)**: Cota de encerramento no topo do pilar (teto no pavimento atual = $N_{\text{chegada}}$ do $N$º PAV, ex: 13º PAV = `852.19cm` / `+85,219m`).
  - **Pé-Direito (Altura do Pilar)**: $N_{\text{chegada}} - N_{\text{saída}} = 852.19 - 848.98 = \mathbf{321.0cm}$ ($3,21\text{m}$).

### 2. Checklist do QA para Auditoria Visual (HTML & Pré-Ficha N1)
- [ ] **Identidade do Pilar**:
  - `Nível de saída` $\rightarrow$ Nível de chegada do pavimento inferior (ex: `849.0cm` / `848.98cm`).
  - `Nível de chegada` $\rightarrow$ Nível de chegada do pavimento atual (ex: `852.2cm` / `852.19cm`).
  - `Pé-direito (altura)` $\rightarrow$ Diferença exata $N_{\text{chegada}} - N_{\text{saída}}$ (ex: `321cm`).
- [ ] **Face Cards (A, B, C, D)**:
  - Vigas exibem **somente Nível de Chegada** (ex: `Viga: V309A · dim: 19/120 · N: 852.19cm`).
  - Lajes exibem seu nível calculado com rebaixo (ex: `Laje: L301 · esp: 12cm · N: 852.12cm`).
- [ ] **Acentuação & Formatting**:
  - Verificar que rótulos não contêm Mojibake/caracteres corrompidos (ex: exibir `vínculo topológico SA` limpo).

---

## Três famílias obrigatórias por face (contrato da ficha)

> Complementa (não substitui) a classificação VIGA / LAJE / VAZIA / VIGA+LAJE
> e os Casos 1–5 acima. A ficha de interpretação e o SA devem responder
> **sempre** estas três linhas em **cada** face A, B, C, D.

| # | Família | Pergunta geométrica | Slot típico SA / ficha |
|---|---------|---------------------|------------------------|
| 1 | **Lajes** | Há laje adjacente / área de laje na face? | `l1_*`, `l2_*`, `fontes_n1.lajes` |
| 2 | **Vigas que passam** | Há parede de viga alinhada **ou** eixo contínuo que corre na face (inclui múltiplos segmentos)? | `v_passa_esq/dir`, `fontes_n1.passa` |
| 3 | **Vigas que chegam / interior** | Há viga que **chega** perpendicular (morre no pilar) **ou** face é **limite interno** (Caso 4)? | `v_ch*`, `para[]`, `interior`, `fontes_n1.chega` / `interior` |

### Preenchimento mínimo por vínculo

Todo item de laje ou viga nas três famílias **deve** carregar, quando existir na planta:

| Atributo | Laje | Viga passa | Viga chega / interior |
|----------|------|------------|------------------------|
| **Identidade** | nome (ex. L301) | nome | nome |
| **Dimensão / espessura** | espessura `h` (ex. 12 cm) | seção B/H | seção B/H |
| **Nível** | $N_{\text{chegada}}$ (c/ rebaixo se houver) | $N_{\text{chegada}}$ | $N_{\text{chegada}}$ |
| **Papel / canto** | face A/B/C/D | `passa` + CA/CB se face C | `chega` (AC/BC…) ou `interior` |
| **d.esq / d.dir** | sim — cobertura ao longo da face | **não** (sempre —) | sim — posicionamento no comprimento da face |
| **Evidência** | alinhamento / área | wall-align / eixo contínuo | perpendicular / Caso 4 |

**d.esq / d.dir:** distâncias (cm) dos **cantos esquerdo e direito** da face
(convenção `FACE_CORNERS`: A→AC/AD, B→BD/BC, C→CA/CB, D→DA/DB) até o trecho
ocupado pelo elemento. Cobertura total da face → `0 / 0`. Elemento no canto
esq. com largura `w` em face de comprimento `L` → `0 / (L−w)`.

Vazio legítimo = anotar **nenhuma** / N/A na família — **não** omitir a linha.

### Múltiplos segmentos de “passa” na mesma face

Uma face pode ter **mais de uma** viga que passa (ou a **mesma** viga com **segmentos** de profundidade / nível diferentes):

- Anotar **todas** as passantes (ou todos os segmentos relevantes).
- Cada segmento leva **dimensão (profundidade)** e **nível** próprios.
- Exemplo típico na face **C**: dois trechos E–W (esq/dir) com cotas distintas (ex. 14/55 e 19/66) — **ambos** entram em “vigas que passam” na C.

### Dualidade esquina C ↔ faces longas (AC / BC)

Regra de consistência (pilar vertical):

```
Viga que CHEGA na face A no canto AC  ⟷  é a mesma que PASSA na face C (lado esq / CA)
Viga que CHEGA na face B no canto BC  ⟷  é a mesma que PASSA na face C (lado dir / CB)
```

- Em **A** (canto AC) e **B** (canto BC): família **chega**.
- Em **C**: as **mesmas** identidades aparecem como **passa** (uma ou duas linhas/segmentos).
- Não inventar VF/V “ancorado por texto” sem geometria; a dualidade exige o **mesmo nome/dim** nos dois papéis.

### Viga “de baixo” nas longas + interior em D

Padrão frequente (pilares da fileira sobre corredor N–S):

```
        C  (passantes do topo — ver dualidade AC/BC)
   A ──────── P ──────── B
        D  (INTERIOR da viga que vem de baixo)
              ↕
         viga N–S “de baixo”
```

| Face | Papel da viga “de baixo” |
|------|---------------------------|
| **A** e **B** | **Viga que passa** (corre / wall no corredor das longas) |
| **D** | **Interior** (Caso 4 — face é limite interno; pilar no corpo/eixo da viga) |
| **C** | Em geral **não** é essa viga (C fica com as passantes do topo) |

A **mesma** identidade de viga pode, portanto, aparecer como:

- `passa` em A e B, e  
- `interior` em D  

Isso **não** é contradição: muda o **papel topológico** por face.

### Face mista (laje + viga na mesma face longa)

Nas longas (A/B) é comum coexistirem:

1. **Laje** no corpo da face (ex. ~52 cm de altura em planta), e  
2. **Viga que passa** (a de baixo), e  
3. **Viga que chega** no canto do topo (AC ou BC),

sem colapsar tudo em um único campo. A ficha lista as **três famílias** preenchidas.

### Proibições (anti-alucinação)

- Hardcode por item/obra (“se B tem laje, injeta V301/VF301”) — **proibido**.
- Fallback de laje em face que a planta mostra como **parede de viga** (ex. forçar L301 em C no Caso 1) — **proibido**.
- Promover viga de **interior em D** como única passante em A/B **sem** wall-align / eixo nas longas — **proibido** (a dualidade “passa A/B + interior D” exige a viga **de baixo** correta, não contaminação de texto).
- Omitir dimensão ou nível quando a cota existe no N1/DXF — **proibido** na ficha consolidada.

---

## Exemplo canônico consolidado — Pilar P2 (13º PAV, Obra_TREINO_1)

> Leitura de referência (N1 próximo + contexto + doc ABCD + DB/SA).  
> Usar para calibrar motor, ficha HTML e QA — não como hardcode de código.

**Identidade:** P2 · retangular vertical **19 × 66**  
**Bbox (planta):** X ≈ 1603.4–1622.4 · Y ≈ 3141.0–3207.0  
**Faces:** A oeste (longa) · B leste (longa) · C norte (curta) · D sul (curta)  
**Níveis de pavimento (referência):** chegada abs. **852.19 cm** · saída abs. **848.98 cm** · pé-direito **321 cm**  
(fonte: `niveis_extractor` / elevação típica da obra)

### Fontes de nome / dim / nível (P2)

| Elemento | Nome | Dim / esp. | Nível | Fonte |
|----------|------|------------|-------|--------|
| Laje oeste | **L301** | h=**12** cm | **852.12** cm | SA `laje_nivel` / fields |
| Laje leste | **L302** | h=**12** cm | **852.12** cm | SA `laje_nivel` / fields |
| Viga de baixo (N–S) | **V312** | **19/120** | **852.19** cm | SA segs `viga_*_nivel_viga` + cota N1 |
| Viga de topo (E–W), **mesmo nome, 2 segmentos** | **VF301** | seg. esq. **14/55** · seg. nó/dir. **19/66** | **852.19** cm (lado B / chegada pav.) | Nome **VF301** no DXF (rótulo na faixa Y≈3210 a oeste); cotas **14/55** e **19/66** no N1 junto ao P2; SA `dim`/`viga_fundo` 19/66, `viga_b_seg_*_nivel_viga` 852.19 |

Notas de proveniência (não apagar):

- No N1 do P2 as cotas de topo **14/55** (esq.) e **19/66** (sobre o P2) estão na **mesma faixa** da viga E–W do topo; a regra de **mesma viga com segmentos de profundidade diferentes** aplica-se: ambos os segmentos = **VF301**.
- O rótulo textual **VF301** no DXF aparece na faixa norte (~Y 3210) mais a oeste (perto da fileira de P1); a **identidade de seção 19/66** e a continuidade da faixa verde amarram o nó do P2 a essa viga. Não usar VF301 como chega na face **B** do corpo (erro de hardcode antigo).
- Nível de laje **852.12** (rebaixo −0.07 em relação a 852.19) confere com SA; vigas de pavimento usam **852.19** salvo segmento explícito em contrário.

### Esquema

```
     VF301 passa C seg.1 (14/55)   VF301 passa C seg.2 (19/66)
              ~~~~~~~~~~~~~~ C ~~~~~~~~~~~~~~
           ↗ chega AC=VF301 14/55    chega BC=VF301 19/66 ↖
   L301  A ──────────── P2 ──────────── B  L302
         │   passa V312 19/120          │
         ~~~~~~~~~~~~~~ D ~~~~~~~~~~~~~~
              INTERIOR V312 19/120
```

### Face A — esquerda / oeste (longa)

| Família | Nome | Dim / esp. | Nível | Papel |
|---------|------|------------|-------|--------|
| **Lajes** | **L301** | esp. **12** cm | **852.12** cm | laje adjacente oeste |
| **Vigas que passam** | **V312** | **19/120** | **852.19** cm | viga de baixo (corredor N–S) |
| **Vigas que chegam / interior** | **VF301** | **14/55** | **852.19** cm | **chega no canto AC** (= passa C seg. 1) |

### Face B — direita / leste (longa)

| Família | Nome | Dim / esp. | Nível | Papel |
|---------|------|------------|-------|--------|
| **Lajes** | **L302** | esp. **12** cm | **852.12** cm | laje adjacente leste |
| **Vigas que passam** | **V312** | **19/120** | **852.19** cm | mesma viga de baixo |
| **Vigas que chegam / interior** | **VF301** | **19/66** | **852.19** cm | **chega no canto BC** (= passa C seg. 2) |

### Face C — topo / norte (curta)

| Família | Nome | Dim / esp. | Nível | Papel |
|---------|------|------------|-------|--------|
| **Lajes** | **nenhuma** | — | — | L301/L302 param abaixo da faixa de topo (cota **52** ≈ 66−14 no N1) |
| **Vigas que passam** | **VF301** (seg. 1) | **14/55** | **852.19** cm | **passa CA** (direção/posição esq. da face C) — **mesma** que chega A@AC |
| **Vigas que passam** | **VF301** (seg. 2) | **19/66** | **852.19** cm | **passa CB** (direção/posição dir. da face C) — **mesma** que chega B@BC |
| **Vigas que chegam / interior** | **nenhuma** *como papel extra* | — | — | o papel “chega” fica em A@AC e B@BC |

### Face D — base / sul (curta)

| Família | Nome | Dim / esp. | Nível | Papel |
|---------|------|------------|-------|--------|
| **Lajes** | **nenhuma** | — | — | — |
| **Vigas que passam** | **nenhuma** | — | — | na D o papel não é “passa” |
| **Vigas que chegam / interior** | **V312** | **19/120** | **852.19** cm | **interior** Caso 4 (mesma que passa em A e B) |

### Matriz de consistência P2 (obrigatória na ficha)

| Identidade | Dim | Nível | A | B | C | D |
|------------|-----|-------|---|---|---|---|
| **L301** | 12 cm | **852.12** | laje | — | — | — |
| **L302** | 12 cm | **852.12** | — | laje | — | — |
| **V312** | **19/120** | **852.19** | **passa** | **passa** | — | **interior** |
| **VF301** seg.1 | **14/55** | **852.19** | **chega AC** | — | **passa CA** | — |
| **VF301** seg.2 | **19/66** | **852.19** | — | **chega BC** | **passa CB** | — |

### Completude da ficha P2 (checklist)

- [ ] A: L301 · 12 · N **852.12**
- [ ] A: passa **V312** · **19/120** · N **852.19**
- [ ] A: chega AC **VF301** · **14/55** · N **852.19**
- [ ] B: L302 · 12 · N **852.12**
- [ ] B: passa **V312** · **19/120** · N **852.19**
- [ ] B: chega BC **VF301** · **19/66** · N **852.19**
- [ ] C: passa **VF301** seg.1 **14/55** · N **852.19**
- [ ] C: passa **VF301** seg.2 **19/66** · N **852.19**
- [ ] C: sem laje inventada
- [ ] D: interior **V312** · **19/120** · N **852.19** apenas
- [ ] Dualidade AC/BC ↔ C com mesmo nome **VF301** e dims por segmento
- [ ] Nenhuma injeção hardcoded (VF301 no corpo de B como passa global, L301 em C, etc.)

---

## Campos da pré-ficha por face (extensão multi-família)

> Mantém a tabela clássica de Laje 1/2 + Viga Nome/Dim/Nível.  
> A extensão abaixo é o contrato **completo** da ficha de interpretação atual.

| Família | Campos (por face) | Obrigatório quando |
|---------|-------------------|--------------------|
| Laje | `l1_n`, `l1_h`, `l1_v` (+ `l2_*`) | Há laje na face |
| Passa | `v_passa_esq_n/d/v`, `v_passa_dir_n/d/v` e/ou lista de segmentos `{nome, dim, nivel, canto, profundidade}` | Há 1+ passantes / segmentos |
| Chega | `v_ch1_n/d/v` … `v_ch3_*` + canto (AC/BC/…) | Há chegada perpendicular |
| Interior | slot / linha `interior` `{nome, dim, nivel}` | Caso 4 / limite interno |

**Regra de preenchimento (estendida, não remove a clássica):**

- Face só laje → lajes preenchidas; passa/chega/interior = nenhuma.  
- Face só viga passa → passa (+ dim + N); lajes = nenhuma.  
- Face Caso 5 Extra / mista → **laje e passa** (e chega se houver canto).  
- Face Caso 4 em D → **interior** com dim + N; em A/B a **mesma** viga pode ser **passa**.  
- Face C com dois segmentos de topo → **duas** entradas passa, cada uma com profundidade e nível.  
- Dualidade AC/BC ↔ C: ids e dims **coerentes** entre chega (A/B) e passa (C).
