# MASTERPLAN — Arete FUNDO DE VIGA (FV): N2→N4 → N2↔N1 → N1→N3
**Versão:** 1.0
**Data:** 2026-06-14
**Autor:** Fable (Estrategista) — Cowork
**Status:** ATIVO — frente paralela (não conflita com PIL/LAJ/LV)
**Complementa:** `MASTERPLAN-ARETE-QUALITY-GATES.md` (gates G0–G6, paridade canônica §G2 v1.2,
treino→motores universais §4-B).

---

> # 🥇 REGRA DE OURO (acima de tudo)
> **TUDO é MOTOR UNIVERSAL. ZERO hardcode isolado a uma viga, pavimento ou obra.**
> Extração, desenho, conversão e comparação por **fórmula geral a partir da ficha**, válidas
> para QUALQUER fundo de viga de QUALQUER obra. Solução que só serve a um caso = bug, não fix.
> O produto é o motor genérico; o item validado é só a prova de que o motor está certo.

---

## 0. Por que FV em paralelo

FV tem **gerador e extrator próprios** — zero conflito de arquivo:
- Gerador: `scripts/gerar_fv_dxf_stog.py`
- Extrator: `scripts/motor_reverso_fv.py`

FV é classe de **1 parte / 1 ficha** (sem divisões de viewer). Junto com LAJ, é dos campos
de prova mais limpos do arco N2→N4→N1→N3. Só não editar `scripts/arete/` (harness compartilhado)
simultaneamente com outra sessão.

---

## 1. Fatos verificados (2026-06-14 — DB `D:/Agente-cad-PYSIDE/project_data.vision`)

- Fichas N2 FV no 13_PAV: **26**.
- Schema da ficha FV (mesmo schema do LV):
  `number, name (V###_A), floor, side, total_width, total_height,
   panels [{width, height1, height2, grade_h1, ...}], holes [{active,width,height,position}],
   pillar_left {active,width,length}, pillar_right {active,width,length},
   sarrafo_left_id, sarrafo_right_id, _er_meta`
- Gerador `gerar_fv_dxf_stog.py`: `compute_panels` (l.266), `draw_sarr` (l.171),
  `draw_escoras` (l.243), divisores verticais entre painéis. Layers: `Paineis` (LWPOLYLINE +
  LINE dividers), `NOMENCLATURA`, `5`, `SARR_2.2x7`, `COTA`.
- Extrator `motor_reverso_fv.py`: `_extract_fv_from_dxf` (l.32), `extrair_ficha_fundo_viga` (l.82).
  **Estado: extração parcial** — validar painéis/holes/pilares contra recorte real.

### Semântica de domínio FV (já confirmada — `cad-stog-semantica-formas`)
- FV = **contorno físico real do fundo da viga** para fabricação (diferente da visão de corte TQS).
- `b_fv = b_viga` (largura da viga, ex.: 19 ou 30cm) — sempre igual ao campo de largura.
- Composto por **segmentos** (painéis) que mudam quando: a viga cruza um pilar (abertura/recorte
  no contorno), a profundidade muda (desnível), ou a largura varia (raro).
- **Chanfros:** vértices extras nas esquinas do contorno.
- **Aberturas:** onde um pilar atravessa a viga → segmento com gap (`pillar_left`/`pillar_right`).
- **Escoras:** suportes da fôrma do fundo.
- Painéis modulados (padrão ~244cm); `holes` = aberturas na fôrma.
- **Prefichas e Obstáculos Visuais (AUXÍLIO INFORMACIONAL PARA TREINO/LOOP):** O motor reverso e a análise geral N1 precisam distinguir obstáculos reais de desenhos apenas visuais no DXF.
  - **Pilares (NASCE):** Pilares "Nasce" sobre a viga e anomalias de geometria visual não cortam o fundo da viga; devem ser transpassados (bridging).
  - **Visão Corte de Vigas:** Representações de vigas cruzando transversalmente (VISAO_CORTE) são ignoradas como interrupção física do fundo. O segmento do fundo da viga continua direto por baixo do corte visual.

---

## 2. O Arco Completo (3 fases)

```
FASE FV-A  N2 → N4   Ficha N2 completa gera N4 idêntico ao recorte N2 (contorno do fundo).
FASE FV-B  N2 ↔ N1   Obter no N1 a mesma info do N2 via interpretação do estrutural limpo.
FASE FV-C  N1 → N3   Com N1, gerar N3 idêntico ao N4 (mesmo gerador), sem N2 como input.
```

Princípio: schema N1 (Structural Analyzer) **imutável**; convergência na camada de conversão.
N2 = gabarito de valores.

---

## 3. FASE FV-A — N2 → N4 (Arete de geração)

Escopo: 26 fundos de viga do 13_PAV. Paridade canônica (§G2 v1.2), **1 parte** (FV inteiro).

| Story | Entrega | Critério de pronto |
|-------|---------|--------------------|
| FV-A.0 | Adapter FV no harness: materializa ficha N2 → `gerar_fv_dxf_stog.py`; gera N4 de 1 viga sem erro | N4 gerado |
| FV-A.1 | **Completar `motor_reverso_fv`**: extrair painéis (widths), aberturas/holes, pilares cruzados (left/right), chanfros, b_fv, total_height contra o recorte | ficha reflete o recorte real |
| FV-A.2 | Forma canônica FV (1 parte): painéis [{w,h}], divisores, aberturas, escoras, cotas-valor, textos, contagens — dos DOIS lados | forma canônica sai dos 2 lados |
| FV-A.3 | **G2 canônico FV** no `arete_runner` | runner roda FV 13_PAV |
| FV-A.4 | Loop de Arete: começar por uma viga simples (sem pilar cruzado) → depois com aberturas | viga simples PASS, golden selado |
| FV-A.5 | Expandir às 26 vigas; documentar exceções aprovadas; selar golden incremental | 26/26 PASS ou BLOCKED justificado |

**Loop:** VALOR vem do recorte STOG; POSIÇÃO/estilo da cota vem do robô SCR de FV
(`_ROBOS_ABAS/Robo_Fundos_de_Vigas`); fix POR FÓRMULA em `gerar_fv_dxf_stog.py` ou
`motor_reverso_fv.py`; preview PNG → inspeção visual → arete → regenera lote. Um fix por causa.

**Atenção FV-específica:** a segmentação do contorno (onde abre por causa de pilar cruzado) deve
sair da geometria (pilares adjacentes), POR FÓRMULA — nunca hardcodar a abertura de uma viga.
Vigas de fundação (VF*) podem não ter cobertura no DXF → BLOCKED documentado (teto estrutural).

---

## 4. FASE FV-B — N2 ↔ N1 (aprender a interpretar)

Pré-requisito: seção FV na **Tabela de Proveniência de Campos** (`docs/PROVENIENCIA-CAMPOS.md`):
- **(a) extraível do N1** — b_viga (texto "30/60"), comprimento (vão entre apoios), pilares cruzados
- **(b) algorítmico** — segmentação em painéis (módulo ~244), escoras, posição de divisores
- **(c) só-no-N2** — convenções do projetista
- **(d) teto estrutural** — VF sem cobertura, pavimento sem FV no DXF

| Story | Entrega |
|-------|---------|
| FV-B.1 | Seção FV na Tabela de Proveniência (a/b/c/d) |
| FV-B.2 | `conversao_n1_diff` FV: convert(campos_N1_SA) vs ficha N2 por categoria, no 13_PAV |
| FV-B.3 | Loop de fixes: deltas (a)/(b) → fixes nos extratores SA / conversor N1→ficha-robô |
| FV-B.4 | Campos (c) por estilo/RAG reverso; (d) excluídos com referência |

**Meta:** delta médio (a)+(b) ≤ tolerância em 100% das vigas do 13_PAV.

---

## 5. FASE FV-C — N1 → N3 (fechar pipeline)

| Story | Entrega |
|-------|---------|
| FV-C.1 | convert(N1) → ficha-robô FV → `gerar_fv_dxf_stog.py` → DXF N3 |
| FV-C.2 | G2 canônico N3 vs N4 (mesmo comparador da Fase FV-A) no 13_PAV |
| FV-C.3 | FV 13_PAV: N3 ≅ N4 (Arete end-to-end sem N2 como input) |

FV-B PASS (a+b) ⇒ FV-C PASS por construção (mesmo gerador).

---

## 6. Critérios de Arete FV

1. b_fv e comprimento batem (±0,5cm); 2. painéis: mesma contagem + cada um ±0,5cm; divisores
no lugar; 3. aberturas (pilar cruzado) coincidem em posição/largura; 4. escoras conforme recorte;
5. cotas-valor + textos batem em conteúdo e contagem; 6. estilo do robô (layers-padrão), nada de
layer humana sintetizada; 7. veredito visual Claude sem divergência semântica.
Pavimento em Arete = 100% das vigas não-BLOCKED.

---

## 7. Roadmap FV

| Fase | Foco | Escopo | Status |
|------|------|--------|--------|
| FV-A | N2→N4 | 1 viga simples → 26 do 13_PAV | ⏳ Iniciar |
| FV-B | N2↔N1 | 13_PAV | Após FV-A |
| FV-C | N1→N3 | 13_PAV | Após FV-B |
| FV-D | Expansão | demais pisos TREINO_1 → outras obras | Em steps |

---

## 8. Regras (herdadas — INEGOCIÁVEIS)
Regra de Ouro (motor universal) · comparação canônica (conteúdo, não layer cru) · tudo por
fórmula · nunca sintetizar layer humana · nunca selar com FAIL · schema N1 imutável · exceção
só com aprovação humana · um fix por causa + regressão · renderizar e LER os PNGs nos FAIL.

*Fable (Estrategista) — Cowork | 2026-06-14*
