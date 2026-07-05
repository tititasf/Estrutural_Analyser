# MASTERPLAN — Arete LATERAL DE VIGA (LV): N2→N4 → N2↔N1 → N1→N3
**Versão:** 1.0
**Data:** 2026-06-14
**Autor:** Fable (Estrategista) — Cowork
**Status:** ATIVO — frente paralela (não conflita com PIL/LAJ/FV)
**Complementa:** `MASTERPLAN-ARETE-QUALITY-GATES.md` (gates G0–G6, paridade canônica §G2 v1.2,
treino→motores universais §4-B, modelo de partes §4-A).

---

> # 🥇 REGRA DE OURO (acima de tudo)
> **TUDO é MOTOR UNIVERSAL. ZERO hardcode isolado a uma viga, pavimento ou obra.**
> Extração, desenho, conversão e comparação por **fórmula geral a partir da ficha**, válidas
> para QUALQUER lateral de viga de QUALQUER obra. Solução que só serve a um caso = bug, não fix.
> O produto é o motor genérico; o item validado é só a prova de que o motor está certo.

---

## 0. Por que LV em paralelo

LV tem **gerador e extrator próprios** — zero conflito de arquivo:
- Gerador: `scripts/gerar_lv_dxf_stog.py`
- Extrator: `scripts/motor_reverso_lv.py`

Só não editar `scripts/arete/` (harness compartilhado) simultaneamente com outra sessão.

---

## 1. Modelo de Partes da LATERAL DE VIGA (decisão do usuário, 2026-06-14)

> A lateral de viga tem **2 DIVISÕES no N4** (análogo ao pilar que tem 3 — CIMA/ABCD/GRADES):
>
> | Divisão | O que é | Fichas |
> |---------|---------|--------|
> | **VC** (Visão de Corte) | seção transversal da viga (corpo + extensões das lajes adjacentes) | 1 ficha VC |
> | **Lados A e B** | elevação dos dois lados da lateral (painéis numerados, sarrafos, cotas) | ficha lado A + ficha lado B |
>
> → São **2 divisões de desenho** no viewer N4 (VC | Lados A e B), expressas por **3 fichas**
> (VC, A, B) — porque os 3 itens da lateral precisam ser descritos separadamente.
> Contraste: FV e LAJ têm 1 divisão/1 ficha; PIL tem 3 divisões (CIMA/ABCD/GRADES).

### Estado das fichas (verificado)
- A ficha de **lado** já existe no DB (campo `side` = A/B; ex.: `V13_A`). Schema:
  `number, name (V###_A), floor, side, total_width, total_height,
   panels [{width, height1, height2, grade_h1, ...}], holes, pillar_left, pillar_right,
   sarrafo_left_id, sarrafo_right_id, _er_meta`
- A ficha **VC (visão de corte) NÃO existe ainda** — precisa ser criada (campos: h3/altura
  estrutural, b da viga, sarrafos do corte, extensões/lajes_sup/lajes_inf, hachura de concreto).
  Esta é a primeira entrega estrutural nova do LV.

---

## 2. Fatos verificados (2026-06-14 — DB `D:/Agente-cad-PYSIDE/project_data.vision`)

- Fichas N2 LV no 13_PAV: **32** (lados A/B de várias vigas).
- Gerador `gerar_lv_dxf_stog.py`: `extract_panels_from_json` (l.166), `auto_distribute_panels`
  (l.189). Constantes: `SARR_INSET_H=7.0`, `PAINEL_MIN_LV` (filtro de painéis de borda).
- Extrator `motor_reverso_lv.py`: `_extract_lv_from_dxf` (l.32) — extrai painéis; **stuba**
  holes (4 vazios), pillar_left/right (inativos), sarrafos (0). Dívidas a fechar.

### Semântica de domínio LV (já confirmada — `cad-stog-semantica-formas`, `cad-scr-anatomy-lv`)
- **Lado A = Lado B** em ~100% dos casos (mesma quantidade, mesmas dimensões) — espelhados.
- **VC (visão de corte):** seção à esquerda no STOG; hachura de concreto + sarrafos externos +
  pontalete/X marks; altura h3 (estrutural) varia por viga. Forma livre (não necessariamente "T"):
  depende de quantas lajes em cada lado e em que nível (retângulo, L, T simétrico, assimétrico,
  invertida). Layers numéricos (3,6,7) em obras antigas; MTH-SOMBRA21 em TQS.
- **Painéis (lados):** segmentação módulo 122cm (pode variar); 3 sarrafos horizontais por face;
  numeração "30, 1, 2, 3..."; cotas em vermelho abaixo + total acumulado.
- **PAINEL_MIN_LV ATUAL ESTÁ ERRADO** (=30): o reverso humano preserva mini-painéis de 6–8cm
  (V3=8, V8/9=11.5, V36=6, V20/21=23.5) — reduzir para ≤5cm. Fix POR FÓRMULA.
- `paineis_alturas` + `paineis_alturas2`: 2 alturas quando há laje em nível intermediário.
- `lajes_sup`/`lajes_inf` por painel; `texto_esq`/`texto_dir` = labels dos extremos do segmento.
- Cruzamento viga×viga: ambos os lados PARAM no cruzamento; lado A "vê" a viga transversal
  (obstáculo), lado B não.

---

## 3. O Arco Completo (3 fases)

```
FASE LV-A  N2 → N4   3 fichas (VC + A + B) completas geram N4 idêntico ao recorte N2,
                     em 2 divisões de desenho (VC | Lados A e B).
FASE LV-B  N2 ↔ N1   Obter no N1 a mesma info do N2 via interpretação do estrutural limpo.
FASE LV-C  N1 → N3   Com N1, gerar N3 idêntico ao N4, sem N2 como input.
```

Princípio: schema N1 imutável; convergência na conversão; N2 = gabarito.

---

## 4. FASE LV-A — N2 → N4 (Arete de geração)

Escopo: 32 fichas LV do 13_PAV. Paridade canônica **por divisão** (VC e Lados A/B).

| Story | Entrega | Critério de pronto |
|-------|---------|--------------------|
| LV-A.0 | Adapter LV no harness: materializa ficha N2 → `gerar_lv_dxf_stog.py`; gera N4 de 1 viga sem erro | N4 gerado |
| LV-A.1 | **Criar a ficha VC** (visão de corte): definir schema (h3, b, sarrafos do corte, lajes_sup/inf, hachura) + extração no `motor_reverso_lv` a partir da seção de corte do recorte | ficha VC existe e reflete o corte |
| LV-A.2 | **Completar `motor_reverso_lv`** (lados): extrair painéis reais (incl. mini-painéis ≤5cm), holes, pilares left/right, sarrafos; lado A = lado B validado | fichas A/B refletem o recorte |
| LV-A.3 | Segmentar N4 e recorte em **2 divisões** (VC, Lados A/B) + normalização de pose (§4-A) | divisões isoladas dos 2 lados |
| LV-A.4 | Forma canônica LV por divisão (painéis [{w,h}], sarrafos, cotas-valor, textos, contagens; VC: corpo+extensões+hachura) — dos DOIS lados | forma canônica por divisão |
| LV-A.5 | **G2 canônico LV** no `arete_runner` (por divisão) | runner roda LV 13_PAV |
| LV-A.6 | Loop de Arete: **Lados A/B primeiro** (mais maduros), depois VC | Lados PASS → VC PASS, golden selado |
| LV-A.7 | Fix `PAINEL_MIN_LV` ≤5cm (preserva mini-painéis) — POR FÓRMULA, com regressão | mini-painéis reproduzidos |
| LV-A.8 | Expandir às 32 fichas; documentar exceções; selar golden incremental | 32/32 PASS ou BLOCKED justificado |

**Loop:** VALOR vem do recorte STOG; POSIÇÃO/estilo da cota vem do robô SCR de LV
(`_ROBOS_ABAS/Robo_Laterais_de_Vigas`); fix POR FÓRMULA em `gerar_lv_dxf_stog.py` ou
`motor_reverso_lv.py`; preview PNG → inspeção visual → arete → regenera lote. Um fix por causa.

> **G2 numérico sozinho não autoriza "golden selado" (decisão do dono, 03/07 —
> `docs/LOOPING-CANONICO.md` §1.5).** "PASS" nas stories acima significa G2 canônico
> (numérico); a selagem de golden exige também G2-V (veredito visual registrado —
> render do recorte N2 humano × DXF N4 do robô, os dois sempre juntos).

**Atenção LV-específica:** Lado A deve sair idêntico ao Lado B (validar invariante). VC tem forma
livre (não force "T") — derive do nº de lajes e níveis. Cruzamento viga×viga gera quebra de
segmento POR GEOMETRIA, nunca hardcode.

---

## 5. FASE LV-B — N2 ↔ N1 (aprender a interpretar)

Pré-requisito: seção LV na **Tabela de Proveniência de Campos**:
- **(a) extraível do N1** — b/h da viga (texto "30/60"), comprimento, pilares de extremo,
  cruzamentos, níveis das lajes adjacentes (para a VC)
- **(b) algorítmico** — segmentação 122cm, sarrafos (regra por altura 2/4/8), grade_h
- **(c) só-no-N2** — mini-painéis preservados, decisões de estilo do projetista
- **(d) teto estrutural** — pavimento sem LV/FV no DXF, viga só em carimbo composto

| Story | Entrega |
|-------|---------|
| LV-B.1 | Seção LV (incl. VC) na Tabela de Proveniência (a/b/c/d) |
| LV-B.2 | `conversao_n1_diff` LV: convert(campos_N1_SA) vs 3 fichas N2 (VC/A/B) por categoria, no 13_PAV |
| LV-B.3 | Loop de fixes: deltas (a)/(b) → extratores SA / conversor N1→ficha-robô |
| LV-B.4 | Campos (c) por estilo/RAG reverso; (d) excluídos com referência |

**Meta:** delta médio (a)+(b) ≤ tolerância em 100% das vigas do 13_PAV (VC + A + B).

---

## 6. FASE LV-C — N1 → N3 (fechar pipeline)

| Story | Entrega |
|-------|---------|
| LV-C.1 | convert(N1) → 3 fichas-robô LV (VC/A/B) → `gerar_lv_dxf_stog.py` → DXF N3 (2 divisões) |
| LV-C.2 | G2 canônico N3 vs N4 por divisão (mesmo comparador da Fase LV-A) no 13_PAV |
| LV-C.3 | LV 13_PAV: N3 ≅ N4 (Arete end-to-end sem N2 como input) |

LV-B PASS (a+b) ⇒ LV-C PASS por construção.

---

## 7. Critérios de Arete LV (por divisão)

**Lados A/B:** painéis com mesma contagem + cada um ±0,5cm (incl. mini-painéis); sarrafos
conforme regra de altura; cotas-valor + textos (numeração/labels) batem; A==B.
**VC:** corpo da viga (b, h3) ±0,5cm; extensões das lajes (lajes_sup/inf) corretas; hachura de
concreto presente; sarrafos do corte conforme recorte.
**Geral:** estilo do robô (layers-padrão), nada de layer humana sintetizada; veredito visual
Claude sem divergência. Pavimento em Arete = 100% das fichas não-BLOCKED, nas 2 divisões.

---

## 8. Roadmap LV

| Fase | Foco | Escopo | Status |
|------|------|--------|--------|
| LV-A | N2→N4 (criar ficha VC + completar lados) | Lados → VC → 32 fichas 13_PAV | ⏳ Iniciar |
| LV-B | N2↔N1 | 13_PAV | Após LV-A |
| LV-C | N1→N3 | 13_PAV | Após LV-B |
| LV-D | Expansão | demais pisos TREINO_1 → outras obras | Em steps |

---

## 9. Regras (herdadas — INEGOCIÁVEIS)
Regra de Ouro (motor universal) · comparação canônica por divisão (conteúdo, não layer cru) ·
tudo por fórmula · nunca sintetizar layer humana · nunca selar com FAIL · schema N1 imutável ·
exceção só com aprovação humana · um fix por causa + regressão · renderizar e LER os PNGs nos FAIL.

*Fable (Estrategista) — Cowork | 2026-06-14*
