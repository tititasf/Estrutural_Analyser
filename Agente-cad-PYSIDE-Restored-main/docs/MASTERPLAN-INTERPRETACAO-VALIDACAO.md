# MASTERPLAN — Validação Campo a Campo da Interpretação DXF
**Data:** 2026-05-18 | **Status:** ATIVO

---

## Visão Geral

O pipeline extrai dados de DXFs STOG em 4 classes de itens:

| Classe | Arquivos | Obra_TREINO_1 | Fonte DXF |
|--------|----------|---------------|-----------|
| **PILAR (PL)** | JSON_Pilares/P{n}.json | 35 pilares | PL (planta baixa + seções) |
| **VIGA LATERAL (LV)** | JSON_Vigas_Laterais/V{n}_A/B.json | 62 faces | LV (vista lateral) |
| **VIGA FUNDO (FV)** | JSON_Vigas_Fundo/V{n}_fundo.json | 31 vigas | FV (vista frontal) |
| **LAJE (LJ)** | JSON_Lajes/L{n}.json | 23 lajes | LJ (planta) |

**Ordem de validação:** campo por campo → item por item → pavimento por pavimento → obra por obra.
**Protocolo:** Para cada campo, pergunto o valor real → comparo com o interpretado → registramos desvios.

---

## FASE 0 — Panorama de Problemas Conhecidos

Antes do questionário campo a campo, observações diretas dos dados Obra_TREINO_1:

| Problema | Classe | Detalhe |
|----------|--------|---------|
| Faces E/F/G/H larg1=0 mas h2>0 | PILAR | Faces sem chapa não deveriam ter h2 distribuído |
| grade_h1/grade_h2 = "0" em todos panels | LV/FV | Nenhuma viga tem grade detectada |
| linhas_horizontais = [] em todas lajes | LJ | Nunca preenchido |
| holes ativos = false em todas vigas | LV/FV | Nenhuma abertura detectada |
| pillar_left/right active = false todos | LV/FV | Pilares de extremidade nunca detectados |
| Vigas GT confidence 0.25 | LV/FV | Ground truth péssimo para vigas |
| grade_2 = null/0 na maioria pilares | PL | Só grade_1 extraída |

---

## CLASSE 1 — PILAR (PL)

### Estrutura atual (Fase-4)
```json
{
  "numero": "1",          // ID numérico
  "nome": "P1",           // Label
  "comprimento": 88.0,    // = h do BH (dimensão maior, cm)
  "largura": 19.0,        // = b do BH (dimensão menor, cm)
  "altura": 280.0,        // altura total do pavimento (cm)
  "pavimento": "TÉRREO",  // nome do pavimento
  "nivel_chegada": 0.0,   // nível base (cm)
  "nivel_saida": 280.0,   // nível topo (cm)
  "modo_distribuicao": "NOVA",
  // Faces A–H (8 faces), cada uma com:
  "h1_A": 2.0,    // espessura base (cinta inferior)
  "h2_A": 244.0,  // corpo central
  "h3_A": 34.0,   // espessura topo (cinta superior)
  "h4_A": 0.0,    // extensão extra (laje)
  "h5_A": 0.0,    // reservado
  "larg1_A": 88.0, // largura da face A (= comprimento do pilar se face lateral)
  "larg2_A": 0.0, // largura secundária
  "larg3_A": 0.0, // largura terciária
  "laje_A": 0.0,      // altura da laje na face A
  "posicao_laje_A": 0.0, // posição da laje
  // ... mesmo padrão para B, C, D, E, F, G, H
  "grade_1": 88.0,    // dimensão da grade (chapa horizontal maior)
  "grade_2": 0.0,     // segunda grade (se houver)
  "grade_3": 0.0,
  "distancia_1": 14.0, // distância da grade ao bordo
  "distancia_2": 0.0,
  "par_1_2": 56.0,  // espaçamento entre linhas de fixação
  "par_2_3": 56.0,
  // ... par_3_4 até par_8_9
}
```

### Questionário — PILAR

#### Grupo 1: Dimensões Básicas
| # | Campo | Pergunta | Como validar |
|---|-------|----------|-------------|
| P-01 | `comprimento` | Qual a dimensão MAIOR do pilar em cm? (ex: 88cm) | Medir na seção do DXF, comparar com `h` do BH |
| P-02 | `largura` | Qual a dimensão MENOR do pilar em cm? (ex: 19cm) | Medir na seção, comparar com `b` do BH |
| P-03 | `altura` | Qual a altura total do pavimento em cm? (pé-direito) | Ler cota de nível no DXF |
| P-04 | `nivel_chegada` | O pilar começa em que cota? (0.0 = térreo, 280 = 1º pav, etc.) | Cota no DXF |
| P-05 | `nivel_saida` | O pilar termina em que cota? | Cota no DXF |

#### Grupo 2: Faces (A–H)
| # | Campo | Pergunta | Como validar |
|---|-------|----------|-------------|
| P-06 | `h1_X` | Qual a espessura da cinta inferior da face X? (típico: 2cm) | Ver seção vertical |
| P-07 | `h2_X` | Qual a altura do corpo central da face X? (típico: 240-250cm) | h_total - h1 - h3 |
| P-08 | `h3_X` | Qual a espessura da cinta superior? (típico: 30-40cm) | Ver seção |
| P-09 | `h4_X` | Há extensão para dentro da laje? Qual cm? | 0 se não houver |
| P-10 | `larg1_X` | Qual a largura da chapa da face X? (= comprimento ou largura do pilar) | Medir chapa no DXF |
| P-11 | `larg1_E..H` | Faces E/F/G/H: pilar tem mais de 4 faces? Se não, larg1 deve ser 0 | Contar faces reais |
| P-12 | `laje_X` | A face X tem laje passando? Qual a altura da laje (cm)? | Verificar no DXF |
| P-13 | `posicao_laje_X` | Em que posição vertical a laje ocorre nesta face? | Medir no DXF |

#### Grupo 3: Assembly / Grades
| # | Campo | Pergunta | Como validar |
|---|-------|----------|-------------|
| P-14 | `grade_1` | Qual a dimensão da grade principal? (= comprimento do pilar tipicamente) | Medir linha de grade no DXF |
| P-15 | `grade_2` | Há segunda grade? Qual dimensão? | Pilar com 2 séries de furos |
| P-16 | `distancia_1` | Distância da primeira linha de fixação ao bordo (cm)? | Cota no DXF |
| P-17 | `par_1_2` | Espaçamento entre 1ª e 2ª linha de furos (cm)? | Cota no DXF |
| P-18 | `par_2_3` | Espaçamento entre 2ª e 3ª linha? | 0 se só 2 linhas |
| P-19 | `modo_distribuicao` | NOVA ou outra? Qual o padrão desta obra? | Campo de configuração |

---

## CLASSE 2 — VIGA LATERAL (LV)

### Estrutura atual
```json
{
  "number": "101",
  "name": "V101_A",
  "floor": "TÉRREO",
  "side": "A",           // face: A ou B
  "total_width": 19.0,   // espessura da viga (= largura do pilar adjacente, cm)
  "total_height": "120.0", // altura total da viga (cm)
  "panels": [            // painéis que compõem a viga
    {
      "width": 120.0,    // largura do painel (cm)
      "height1": 120.0,  // altura lado esquerdo
      "height2": 120.0,  // altura lado direito
      "grade_h1": "0",   // tem grade horizontal no topo?
      "grade_h2": "0"    // tem grade horizontal no fundo?
    }
  ],
  "holes": [             // aberturas/furos na viga
    {"active": false, "width": 0.0, "height": 0.0, "position": 0.0}
  ],
  "pillar_left": {"active": false, "width": 0.0, "length": 0.0},
  "pillar_right": {"active": false, "width": 0.0, "length": 0.0},
  "sarrafo_left_id": 0,
  "sarrafo_right_id": 0
}
```

### Questionário — VIGA LATERAL

#### Grupo 1: Identificação
| # | Campo | Pergunta | Como validar |
|---|-------|----------|-------------|
| V-01 | `number` | O número 101 corresponde à viga V101 no DXF? | Verificar ID no layer |
| V-02 | `side` | A face "A" é a face leste/norte/esquerda? Qual convenção? | Verificar no DXF qual é A e qual é B |
| V-03 | `floor` | O pavimento TÉRREO está correto para esta viga? | Confirmar nível |

#### Grupo 2: Dimensões
| # | Campo | Pergunta | Como validar |
|---|-------|----------|-------------|
| V-04 | `total_width` | A espessura 19.0cm está correta? (= largura do pilar?) | Medir no DXF LV |
| V-05 | `total_height` | A altura 120cm está correta para esta viga? | Medir cota vertical no DXF |

#### Grupo 3: Painéis
| # | Campo | Pergunta | Como validar |
|---|-------|----------|-------------|
| V-06 | `panels` count | V101_A tem 5 painéis. Correto? (soma larguras ≈ comprimento total?) | Somar `width` dos panels = comprimento total |
| V-07 | `panel.width` | O painel de 120cm + 120cm + 120cm + 120cm + 38cm totaliza 518cm. Qual o comprimento real de V101? | Medir no DXF |
| V-08 | `panel.height1/2` | Os dois lados têm altura 120cm (sem variação). A viga tem inclinação ou escada? | Verificar se height1 ≠ height2 em algum caso |
| V-09 | `grade_h1/h2` | Todos os `grade_h1` = "0". Nenhuma viga tem grade detectada. Correto? | Verificar visualmente no DXF se há linhas de grade horizontais |

#### Grupo 4: Aberturas e Pilares
| # | Campo | Pergunta | Como validar |
|---|-------|----------|-------------|
| V-10 | `holes.active` | Todas as aberturas estão `false`. Há vigas com furos/aberturas nesta obra? | Inspecionar DXF visualmente |
| V-11 | `pillar_left.active` | A viga V101 não tem pilar na extremidade esquerda? | Ver se viga começa em pilar ou em parede |
| V-12 | `sarrafo_left_id` | Sarrafo_left_id = 0. Qual é o ID do sarrafo real desta viga? | Ver layer SARRAFO no DXF |

---

## CLASSE 3 — VIGA FUNDO (FV)

### Questionário — VIGA FUNDO

A FV usa estrutura idêntica à LV mas representa a vista frontal (fundo da forma).

| # | Campo | Pergunta | Como validar |
|---|-------|----------|-------------|
| F-01 | `total_height` | A altura 120cm da FV é a mesma da LV? Deve ser igual | Comparar LV e FV da mesma viga |
| F-02 | `panels` | Os panels da FV têm mesma largura que os da LV? | Comparar V101_A.json vs V101_fundo.json |
| F-03 | **Anomalia** | V101_fundo.json tem `name: "V101_A"` (igual ao LV). Deveria ser `"V101_fundo"`? | Verificar se é bug de nomenclatura |
| F-04 | `grade_h1/h2` | Mesma questão: todas "0". FV tem grades horizontais diferentes? | Inspecionar layer FV no DXF |

---

## CLASSE 4 — LAJE (LJ)

### Estrutura atual
```json
{
  "numero": 101,
  "nome": "L101",
  "comprimento": 1420.2,   // cm
  "largura": 302.0,        // cm
  "pavimento": "TÉRREO",
  "coordenadas": [[0,0],[1420.2,0],[1420.2,302.0],[0,0]], // polígono
  "area_cm2": 428900.4,
  "linhas_verticais": [    // divisórias verticais (painéis)
    {"value": 100.0, "is_union": false}, ...
  ],
  "linhas_horizontais": [], // SEMPRE VAZIO — problema?
  "obstaculos": [],         // aberturas/furos na laje
  "modo_selecionado": 0,
  "unioes_nos_bordes": false,
  "observacoes": "",
  "pontaletes": {
    "pontalete": 60, "meio_pontalete": 0, "total": 60,
    "tipo": "PONTALETE", "linhas": 4, "colunas": 15
  }
}
```

### Questionário — LAJE

#### Grupo 1: Dimensões
| # | Campo | Pergunta | Como validar |
|---|-------|----------|-------------|
| L-01 | `comprimento` | L101 tem 1420.2cm de comprimento. Correto? | Medir no DXF LJ |
| L-02 | `largura` | 302.0cm de largura. Correto? | Medir no DXF LJ |
| L-03 | `area_cm2` | 428900 cm² ≈ 42.89 m². Bate com comprimento × largura? | 1420.2 × 302.0 = 428.900 ✓ |
| L-04 | `coordenadas` | As 4 coordenadas formam polígono fechado? O 4º ponto = [0,0] (deveria ser [0,302])? | Bug potencial no fechamento |

#### Grupo 2: Painéis
| # | Campo | Pergunta | Como validar |
|---|-------|----------|-------------|
| L-05 | `linhas_verticais` | L101 tem 15 linhas verticais (100, 200, ..., 1420.2). Corresponde a 15 painéis de 100cm + 1 de 20.2cm? | Contar divisórias no DXF |
| L-06 | `linhas_horizontais` | SEMPRE VAZIO em todas as lajes. Nenhuma laje tem divisão horizontal? | Verificar no DXF se há linhas horizontais |
| L-07 | `is_union` | Nenhuma linha tem `is_union: true`. O que são uniões? Painéis que se unem a outra laje? | Verificar regra de negócio |

#### Grupo 3: Obstáculos e Pontaletes
| # | Campo | Pergunta | Como validar |
|---|-------|----------|-------------|
| L-08 | `obstaculos` | Sem obstáculos em L101. Há lajes com furos de pilar ou shaft nesta obra? | Inspecionar DXF |
| L-09 | `pontaletes.total` | 60 pontaletes para 1420×302cm. Faz sentido (grid 100cm, 4 linhas × 15 cols)? | Verificar fórmula |
| L-10 | `modo_selecionado` | Sempre 0. O que são os modos 1, 2, 3? Quando usar cada um? | Verificar regra de negócio |

---

## PROTOCOLO DE VALIDAÇÃO — Passo a Passo

### Sprint 1 — Obra_TREINO_1 — CONCLUÍDO 2026-06-04
**Status:** ✅ P1 validado | V10/L1 pendentes (itens disponíveis na obra)
**Semântica completa:** `docs/SEMANTICA-PILAR-NOVA.md`

#### Resultados P1 — Validação Campo a Campo

| Campo | Valor Sistema | Valor Real | Status | Nota |
|-------|--------------|------------|--------|------|
| comprimento | 66cm | 66cm | ✅ | Faces A e B (longas) |
| largura | 19cm | 19cm | ✅ | Faces C e D (curtas) |
| altura | 280cm | 280cm | ✅ | Pé-direito |
| nivel_chegada | 0.0 | 0.0 | ✅ | Base térreo |
| nivel_saida | 280.0 | 280.0 | ✅ | = chegada + altura |
| h1_A..D | 2.0cm | 2cm | ✅ | Fixo, cinta inferior |
| h2_A..D | 244.0cm | 244cm | ✅ | Chapa inteira 244×122 |
| h3_A..D | 34.0cm | 34cm | ✅ | Sobra: 280-2-244=34 |
| h4_A..D | 0.0 | 0 | ✅ | Sem extensão laje |
| larg1_A | 66cm | 66cm | ✅ | Face longa A |
| larg1_B | 19cm | **66cm** | ❌ BUG | B é face LONGA (=comprimento) |
| larg1_C | 66cm | **19cm** | ❌ BUG | C é face CURTA (=largura) |
| larg1_D | 19cm | 19cm | ✅ | Face curta D |
| larg1_E..H | 0 | 0 | ✅ | Pilar retangular simples |
| laje_A..D | 0 | ? | ⚠️ | Extrator não detecta lajes |
| posicao_laje_X | 0 | ? | ⚠️ | Depende de laje_X |
| grade_1 | 88cm | 88cm | ✅ | comprimento+22 = 66+22 |
| grade_2 | 0 | ? | ? | Depende do comprimento |
| distancia_1 | 14cm | ? | ? | Dist grade1↔grade2, ver robo |
| par_1_2 | 45cm | 45cm | ✅ | 2 paraf × 45 = 90 = comp+24 |
| par_2_3 | 45cm | **0** | ⚠️ | P1 tem 2 parafusos, não 3 |
| modo_distribuicao | NOVA | NOVA | ✅ | Padrão desta obra |

#### Regras Semânticas Descobertas (P1)

1. **NOMENCLATURA CORRETA:** A/B = faces longas (comprimento) | C/D = faces curtas (largura)
2. **GRADE:** grade_1 = comprimento + 22 (extensão 11cm cada lado)
3. **h DISTRIBUIÇÃO:** h1=2(fixo) → chapas 244/122 → h3=sobra
4. **PARAFUSOS (par_N_M):** espaçamentos horizontais ao longo da grade, somam comprimento+24
   - ≤120cm → 2 parafusos (par_1_2, par_2_3 ambos = (comp+24)/2)
   - 121-195cm → 3 parafusos; 196-260cm → 4; 261-330cm → 5; 331-400cm → 6
5. **LAJE:** posicao_laje = nº painel acima do qual a laje está (0=fundo, 5=topo, N=acima painel N)
6. **h4:** extensão dentro da laje só quando laje está ACIMA do pé-direito

#### Bugs Identificados (P1)
- **B1 CRÍTICO:** larg1_B=largura (19) ERRADO — deve ser comprimento (66). Idem larg1_C.
- **B2:** par_2_3=45 para pilar de 66cm — deveria ser 0 (só 2 parafusos nesta faixa)
- **B3:** laje_X sempre 0 — extrator DXF não detecta lajes em faces de pilar

```
Etapa 1.1 — PILAR P1 ✅ CONCLUÍDO (ver tabela acima)

Etapa 1.2 — VIGA V101
  ├─ Abrir DXF: .../LV_TERREO.dxf + FV_TERREO.dxf
  ├─ Perguntar V-01 a V-09 (LV)
  ├─ Perguntar F-01 a F-04 (FV)
  └─ Registrar delta

Etapa 1.3 — LAJE L101
  ├─ Abrir DXF: .../LJ_TERREO.dxf
  ├─ Perguntar L-01 a L-10
  └─ Registrar delta

Etapa 1.4 — VARREDURA COMPLETA (P1..P35, V101..V131, L101..L123)
  ├─ Script: validar_interpretacao.py --obra Obra_TREINO_1
  ├─ Output: interpretation_audit.json com campos suspeitos
  └─ Questões apenas para casos anômalos
```

### Sprint 2 — Obras similares (Obra_TREINO_3, 5, 6)
- Verificar se mesmos campos corretos → confirmar que extração generaliza

### Sprint 3 — Obras complexas (multi-pavimento, pilar especial)
- Pavimentos com `nivel_chegada != 0`
- Pilares com faces E/F/G/H ativas (mais de 4 faces)
- Vigas com `holes.active = true`
- Lajes com `obstaculos` não vazios

### Sprint 4 — Cobertura total (23 obras)
- Pipeline batch + audit automático
- Report: % campos corretos por classe por obra

---

## SCRIPT DE AUDITORIA (a criar)

```bash
# Gera interpretation_audit.json com todos os campos suspeitos
python scripts/auditar_interpretacao.py --obra DADOS-OBRAS/Obra_TREINO_1 [--pavimento "TÉRREO"]

# Output por item:
# P1: {'campo': 'larg1_E', 'valor': 0.0, 'suspeito': 'face E com h2>0 mas larg1=0'}
# V101_A: {'campo': 'grade_h1', 'valor': '0', 'suspeito': 'nenhuma grade detectada em nenhuma viga'}
# L101: {'campo': 'linhas_horizontais', 'valor': [], 'suspeito': 'sempre vazio'}
```

---

## CAMPOS PRIORITÁRIOS (maior impacto no DXF gerado)

| Prioridade | Campo | Impacto se errado |
|------------|-------|-------------------|
| 🔴 CRÍTICO | `comprimento`, `largura` (pilar) | DXF gerado com dimensões erradas |
| 🔴 CRÍTICO | `h1/h2/h3` das faces do pilar | Distribuição das chapas completamente errada |
| 🔴 CRÍTICO | `larg1_A..D` do pilar | Largura das chapas laterais errada |
| 🔴 CRÍTICO | `total_height` da viga | Viga com altura errada |
| 🔴 CRÍTICO | `panel.width` da viga | Comprimento total da viga errado |
| 🟡 ALTO | `grade_1`, `distancia_1`, `par_1_2` | Grade deslocada |
| 🟡 ALTO | `linhas_verticais` da laje | Divisão errada dos painéis |
| 🟡 ALTO | `holes.active` das vigas | Abertura não desenhada |
| 🟢 MÉDIO | `pillar_left/right` | Extremidades de vigas com pilar ausente |
| 🟢 MÉDIO | `linhas_horizontais` da laje | Sempre 0 — impacto desconhecido |
| ⚪ BAIXO | `modo_selecionado`, `unioes_nos_bordes` | Config de interface |

---

## PRÓXIMA AÇÃO IMEDIATA

**Pergunta #1 — PILAR P1 (campo P-01, P-02):**

Abrindo DXF `PL_TERREO.dxf` da Obra_TREINO_1 no AutoCAD/ezdxf:
- O pilar P1 tem dimensões `88cm × 19cm` extraídos automaticamente
- **Confirma que P1 = 88×19cm?** (comprimento=88, largura=19)
- Ou deveria ser `19×88cm` (comprimento=19, largura=88)?

A convenção é: `comprimento` = dimensão H (maior), `largura` = dimensão B (menor)?
```
