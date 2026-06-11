# Algoritmos de Cálculo — Sistema NOVA CAD
**Fonte:** grade_calculator.py, calculo_modo1.py — extraído 2026-06-04
**Uso:** RAG compreensão semântica, extratores Fase-3/4, validações

---

## 1. calcular_grades(medida_total) — Quantidade e Tamanho de Grades

**Arquivo:** `_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src/utils/grade_calculator.py`

Determina o número de grades paralelas (grade_1, grade_2, grade_3) e a distância entre elas.

```
medida_total_ajustada = medida_total + 22
```

| medida_total_ajustada | Num grades | Tamanho grade | distancia |
|-----------------------|------------|---------------|-----------|
| ≤ 106cm               | 1          | adj           | 0         |
| 107–259cm             | 2          | ≤106, mult 5  | 1–15cm    |
| > 259cm               | 3          | ≤106, mult 5  | 1–15cm    |

**Lógica 2 grades:**
- tamanho_ideal = min(106, adj / 2)
- Candidatos: múltiplos de 5 abaixo e acima do ideal
- distancia = adj - (2 × tamanho_grade)
- Restrição: 1 ≤ distancia ≤ 15
- Fallback: distancia=1 se menor; distancia=15 se maior; ajustar tamanho para soma exata

**Lógica 3 grades:**
- Igual para 2 grades mas com 3 instâncias
- distancia = (adj - 3 × tamanho_grade) / 2
- Mesma restrição 1–15cm

**Exemplo P1 (comprimento=66):**
- adj = 66 + 22 = 88cm ≤ 106 → 1 grade, size=88, distancia=0
- grade_1 = 88cm, grade_2 = 0, distancia_1 = 0

---

## 2. calcular_parafusos(comprimento) — Espaçamentos dos Parafusos

**Arquivo:** `grade_calculator.py` (mesma função)

Calcula os espaçamentos horizontais entre parafusos ao longo da grade.

```
comprimento_ajustado = comprimento + 24
quantidade = ceil(comprimento_ajustado / 72)
```

**Distribuição dos espaçamentos:**
- Valor base = floor(adj / qty)
- Resto = adj - (base × qty)
- Distribuição simétrica: alternando extremidades (índice 0, último, 1, penúltimo...)
- Resultado: 8 campos (par_1_2, par_2_3, ... par_8_9), zeros preenchidos

| comprimento | adj | qty | espaçamentos |
|-------------|-----|-----|--------------|
| ≤ 48cm      | ≤72 | 1   | [adj, 0, 0...] |
| 49–120cm    | 73–144 | 2 | [adj/2, adj/2, 0...] |
| 121–192cm   | 145–216 | 3 | 3 espaçamentos |
| 193–264cm   | 217–288 | 4 | 4 espaçamentos |
| 265–336cm   | 289–360 | 5 | 5 espaçamentos |
| 337–408cm   | 361–432 | 6 | 6 espaçamentos |

**ATENÇÃO — Relação com par_1_2 no JSON:**
Os campos par_1_2, par_2_3... representam os espaçamentos ENTRE parafusos consecutivos.
- par_1_2 = distância do 1º ao 2º parafuso
- par_2_3 = distância do 2º ao 3º (0 se só 2 parafusos)
- Soma total = comprimento + 24

**Exemplo P1 (comprimento=66, adj=90, qty=2):**
- par_1_2 = 45, par_2_3 = 45, demais = 0
- Interpretação: 3 parafusos (posições 0, 45, 90) ao longo da grade de 90cm

---

## 3. calculate_face_heights(total_height, face) — Distribuição de Altura h1/h2/h3

**Arquivo:** `grade_calculator.py`

Define h1, h2, h3, h4, h5 para uma face específica do pilar.

```
h1 = 2.0cm (FIXO — cinta inferior, espaçador)
Faces C, D → max_panel = 244cm por slot
Faces A, B, E, F, G, H → max_panel = 122cm por slot
```

**Razão semântica:**
- A chapa NOVA é 244×122cm
- Faces A/B (longas, comprimento): chapa colocada com 122cm na direção da altura
- Faces C/D (curtas, largura): chapa colocada com 244cm na direção da altura

**Algoritmo:**
1. h1 = 2.0 (descontar do total)
2. Preencher h2, h3, h4, h5 com max_panel cada, enquanto restar espaço
3. Última slot = sobra

**Exemplo P1 (altura=280cm, face A/B, max_panel=122):**
- h1 = 2.0
- restante = 278
- h2 = 122 → restante = 156
- h3 = 122 → restante = 34
- h4 = 34 → restante = 0
- Resultado: h1=2, h2=122, h3=122, h4=34

**IMPORTANTE — Duas implementações diferentes:**
- `motor_fase4.py` (pipeline Fase-4): usa 244cm para TODAS as faces (A, B, C, D) ✓ CORRETO
- `grade_calculator.py: calculate_face_heights()` (Robo PySide): usa 122cm para A/B — lógica diferente, provavelmente para outra finalidade dentro do robo
- Sprint 1 (usuário validou): h2=244cm para P1 faces A/B — confirma motor_fase4.py correto

---

## 4. calculate_details_legacy(valor_grade) — Subdivisão da Grade em Detalhes

**Arquivo:** `grade_calculator.py`

Divide o valor da grade em segmentos (detalhe_grade1_1...5) com máx 33cm cada.

```
quantidade = min(ceil(valor_grade / 33.0), 5)
```

**Para grades inteiras:** base = valor_int // qty, distribuir resto nos primeiros
**Para grades fracionárias:** base = int(val/qty), resto adicionado ao centro
**Validação final:** soma dos detalhes deve ser exata (ajuste no último detalhe >0)

**Exemplo grade_1=88cm:**
- qty = ceil(88/33) = 3
- base = 88 // 3 = 29, resto = 88 % 3 = 1
- detalhe_grade1_1 = 30, detalhe_grade1_2 = 29, detalhe_grade1_3 = 29

---

## 5. mirror_group1_to_group2(pilar) — Espelhamento de Grades

Espelha grades do Grupo 1 para Grupo 2 com inversão de ordem.
- 1 grade ativa: copia direta
- 2 grades ativas: inverte ordem (g1↔g2)
- 3 grades ativas: g1_inv=g3, g2=g2, g3_inv=g1
- Distâncias e detalhes também invertidos

---

## 6. Laje: calcular_modo1_verticais(largura_total) — Linhas Verticais

**Arquivo:** `_ROBOS_ABAS/Robo_Lajes/laje_src/services/calculo_modo1.py`

Algoritmo de distribuição das linhas verticais na grade da laje (Modo 1).

**Constantes:**
- LINHA_122 = 122.0cm (painel principal)
- LINHA_60 = 60.0cm (painel intermediário)
- LINHA_20 = 20.0cm (união mínima)
- CICLO_182 = 182.0cm (122 + 60, ciclo completo)

**Algoritmo:**
1. Primeiro ciclo: 122 + 60 + união (CICLO_182)
2. Ciclos seguintes: 122 + união (até N=10 ciclos testados)
3. Selecionar configuração com menor sobra (meta: sobra=0)
4. União = espaço restante / num_uniões, deve estar 20–30cm

**Critérios de qualidade:**
- União entre 20-30cm (preferir 20cm)
- Zero sobra (espaço distribuído nas uniões)
- A cada 182cm acumulados, deve haver uma linha ≤30cm (união)

---

## 7. gerar_script_scr.py (Laje) — Geração de Painéis

**Arquivo:** `_ROBOS_ABAS/Robo_Lajes/laje_src/services/gerar_script_scr.py`

**linhas_horizontais_reversed:** A função inverte a lista de linhas horizontais antes do cálculo.
```python
linhas_horizontais_reversed = list(reversed(linhas_horizontais))  # linha 520
```

**calcular_paineis_com_labels():** Grid com labels tipo A1, A2, B1...
- Coluna = letra (A, B, C...)
- Linha = número (1, 2, 3...)
- Hatch union: comando HLAZ

---

## 8. calcular_grades() para Pilar L/T/U — Grades Especiais

**Arquivo:** `grade_calculator.py: calculate_special_pillar_grades(pilar)`

Para pilares em L/T/U com comp_1, comp_2, larg_1, larg_2:
```
grade_a_1 = comp_1 + 22
grade_b_1 = comp_1 - 13.2 + (larg_2 - 20)
grade_e_1 = comp_2 + 11 + (larg_1 - 20)
grade_f_1 = comp_1 - 27.4  (modo NOVA)
grade_f_1 = comp_2 - 27.4  (modo INI)
```
