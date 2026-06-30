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
Preencher: campo `Viga que Passa` com nome e dimensão da viga.

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
