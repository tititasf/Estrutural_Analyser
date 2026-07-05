# MASTERPLAN — Arete LAJE: N2→N4 → N2↔N1 → N1→N3
**Versão:** 1.0
**Data:** 2026-06-14
**Autor:** Fable (Estrategista) — Cowork
**Status:** ATIVO — frente paralela (não conflita com PIL)
**Complementa:** `MASTERPLAN-ARETE-QUALITY-GATES.md` (gates G0–G6, paridade canônica §G2 v1.2,
treino→motores universais §4-B). Este doc é a instância LAJE + o arco completo de convergência.

---

> # 🥇 REGRA DE OURO (acima de tudo)
> **TUDO é MOTOR UNIVERSAL. ZERO hardcode isolado a uma laje, pavimento ou obra.**
> Toda lógica — extração (motor reverso), desenho (gerador), conversão e comparação — deve
> funcionar por **fórmula/regra geral a partir da ficha**, válida para QUALQUER laje de
> QUALQUER obra. Se uma solução só serve a um item/piso/obra específico, **é bug, não fix** —
> reescreva como fórmula geral. Nenhuma medida, posição ou contagem pode ser fixada para um
> caso particular. O produto é o motor genérico; o item validado é só a prova de que o motor
> está certo. Esta regra vale igualmente para PIL, LAJ, LV, FV e qualquer classe futura.

---

## 0. Por que LAJE em paralelo

LAJE usa **gerador e extrator próprios** — zero conflito de arquivo com PIL:
- Gerador: `scripts/gerar_lj_dxf_stog.py`
- Extrator: `scripts/motor_reverso_laj.py`

Permite **3 frentes simultâneas**: PIL-CIMA, PIL-ABCD e LAJ. Como cada classe tem seu par
gerador/extrator, as sessões não se atropelam (só evitar editar o harness `scripts/arete/`
ao mesmo tempo — esse é compartilhado).

LAJE é a classe **mais simples**: 1 parte de desenho, 1 ficha (sem CIMA/ABCD/EFGH/GRADES).
Bom campo de prova do arco completo N2→N4→N1→N3 antes de aplicar às classes complexas.

---

## 1. Fatos verificados (2026-06-14 — DB `D:/Agente-cad-PYSIDE/project_data.vision`)

- Fichas N2 LAJ no 13_PAV: **18**. Recortes: 1 `aprovado` (humano) + 150 `auto_aprovado`.
- **L308 é o único recorte LAJ aprovado por humano no 13_PAV** → item-âncora (começar por ele).
- Schema da ficha LAJ (16 campos):
  `numero, nome, comprimento, largura, pavimento, coordenadas (polígono),
   area_cm2, linhas_verticais [{value,is_union}], linhas_horizontais [{value,is_union}],
   obstaculos, modo_selecionado (0/1), unioes_nos_bordes (bool), observacoes,
   pontaletes {}, _sa_meta, _er_meta`
- Gerador `gerar_lj_dxf_stog.py`: `draw_laje_planta` (l.253), `draw_laje_card` (l.556),
  `draw_pilars_for_lajes` (l.511). Consome: comprimento, largura, linhas_verticais,
  linhas_horizontais, obstaculos.
- Extrator `motor_reverso_laj.py`: `_extract_laj_from_dxf` (l.24), `extrair_ficha_laje` (l.91).
  **Estado: incompleto** — extrai `linhas_verticais` mas **stuba** `obstaculos=[]`,
  `modo_selecionado=0`, `pontaletes={}`. Esta é a primeira dívida a fechar.

### Semântica de domínio LAJE (já confirmada — `cad-stog-semantica-formas`)
- `comprimento`/`largura`: dimensões em planta; `coordenadas` = polígono fechado da laje.
- `linhas_verticais`/`linhas_horizontais`: **CALCULADAS algoritmicamente** a partir das
  dimensões (Modo 1: verticais 122+60+união; horizontais blocos de 244). NÃO são extraídas
  diretamente — o robô as recalcula. `is_union=True` quando o segmento ≤ ~30cm (tira de junção).
- `obstaculos`: furos/shafts = polígonos fechados DENTRO do polígono da laje.
- `pontaletes`: cálculo estrutural NBR 7190 — **a entrega do robô é painéis + uniões**, NÃO
  pontaletes. ⇒ pontaletes ficam FORA da paridade DXF (são cálculo, não desenho de fôrma).
- `HLAZ`: hachura nas tiras de união (marcação visual; não é pontalete).
- `modo_selecionado`: 0 = painéis longitudinais; 1 = transversais.

**Consequência crítica para a comparação:** o conteúdo "primário" a extrair do recorte é
o **polígono** (comprimento/largura/coordenadas/obstáculos) + o **modo**. A grade de painéis
(linhas_vert/horiz) é **derivada por algoritmo** — então o teste real é: dado o polígono,
o algoritmo do robô reproduz a MESMA divisão de painéis/uniões que o recorte humano mostra?

---

## 2. O Arco Completo (3 fases) — o que cada uma prova

```
FASE LJ-A  N2 → N4    Ficha N2 completa gera N4 idêntico ao recorte N2.
                      Prova: extrator + gerador reproduzem o STOG humano.

FASE LJ-B  N2 ↔ N1    Obter no N1 (campos do Structural Analyzer) a mesma informação
                      que temos no N2, usando o motor de interpretação N1 + os campos N1.
                      Prova: aprendemos a INTERPRETAR o estrutural limpo. N2 = professor.

FASE LJ-C  N1 → N3    Com o N1 interpretado, gerar N3 idêntico ao N4 (mesmo gerador).
                      Prova: o pipeline fecha SEM usar N2 como input — só N1.
```

Princípio inegociável (herdado do masterplan global): **o schema do N1 (Structural Analyzer)
NÃO muda**. A convergência acontece na **camada de conversão** N1→ficha-de-robô. O N2 é
gabarito de valores, nunca input do caminho N1.

### Trava anti-vazamento N2/N4 -> N3

O N3 de LAJ deve nascer exclusivamente do N1 produzido pelo Structural Analyzer puro. N2 e N4
podem ser usados para medir score, comparar geometria, diagnosticar gaps e treinar regras do
motor, mas nunca para preencher a ficha N3/Robo. E proibido copiar para N3 qualquer campo do
N2/N4 (`coordenadas`, `comprimento`, `largura`, `area_cm2`, `linhas_verticais`,
`linhas_horizontais`, `_hlaz`, `_stog_pose`, `unioes_nos_bordes`, modo ou equivalentes).

Se uma rodada N3 vs N4 atingir 100% porque a ficha N3 recebeu valores do N2/N4, essa rodada e
invalida: deve ser registrada como vazamento de gabarito e o motor SA->N1 precisa ser corrigido
ate reproduzir a geometria dinamicamente. A mesma regra se aplica por analogia a FV, LV, PIL e
classes futuras.

---

## 3. FASE LJ-A — N2 → N4 (Arete de geração)

**Objetivo:** N4 (DXF gerado da ficha N2) idêntico ao recorte N2, por paridade canônica
(§G2 v1.2 do masterplan global). Escopo: 18 lajes do 13_PAV; **L308 primeiro** (aprovado).

| Story | Entrega | Critério de pronto |
|-------|---------|--------------------|
| LJ-A.0 | Adapter LAJ no harness: `ficha_adapter` materializa ficha LAJ N2 → input do `gerar_lj_dxf_stog.py`; gera N4 de L308 sem erro | N4 de L308 gerado |
| LJ-A.1 | **Completar `motor_reverso_laj`**: extrair de verdade `obstaculos` (polígonos internos), `modo_selecionado` (orientação dos painéis), e validar `coordenadas`/comprimento/largura contra o recorte | ficha de L308 reflete o recorte real |
| LJ-A.2 | Extrator de **forma canônica LAJ** (1 parte): painéis [{w,h}], uniões, obstáculos, cotas-valor, textos, contagens — aplicável a recorte E N4 | forma canônica sai dos 2 lados |
| LJ-A.3 | **G2 canônico LAJ** no `arete_runner`: diff de conteúdo (painéis ±0,5cm + contagem; uniões; obstáculos; cotas-valor; textos) — pontaletes EXCLUÍDOS (cálculo, não fôrma) | runner roda LAJ 13_PAV |
| LJ-A.4 | Loop de Arete em **L308** até idêntico (algoritmo de divisão de painéis reproduz a grade do recorte; HLAZ nas uniões; obstáculos no lugar) | L308 PASS, golden selado |
| LJ-A.5 | Expandir às 18 lajes do 13_PAV; documentar exceções aprovadas; selar golden incremental | 18/18 PASS ou BLOCKED justificado |

**Loop de trabalho (idêntico ao PIL):** VALOR vem do recorte STOG; POSIÇÃO/estilo da cota vem
do robô SCR de lajes (`_ROBOS_ABAS/Robo_Lajes`); fix POR FÓRMULA em `gerar_lj_dxf_stog.py` ou
`motor_reverso_laj.py`; preview PNG → inspeção visual → arete → regenera lote. Um fix por causa.

> **G2 numérico sozinho não autoriza "golden selado" (decisão do dono, 03/07 —
> `docs/LOOPING-CANONICO.md` §1.5).** "PASS" nas stories acima significa G2 canônico
> (numérico); a selagem de golden exige também G2-V (veredito visual registrado —
> render do recorte N2 humano × DXF N4 do robô, os dois sempre juntos).

**Atenção LAJ-específica:** se a grade de painéis (linhas_vert/horiz) do N4 não bate com o
recorte, o fix é no **algoritmo de cálculo** (`calcular_modo1` / lógica de uniões), por fórmula
— nunca hardcodar a divisão de uma laje. Validar `modo_selecionado` (0 vs 1) é parte do match.

---

## 4. FASE LJ-B — N2 ↔ N1 (aprender a interpretar)

**Objetivo:** preencher os campos do **Structural Analyzer (N1)** com a mesma informação que
o N2 tem, usando o motor de interpretação do N1 sobre o **estrutural limpo** — e treinar os
campos/vínculos comparando contra o N2 (gabarito).

Pré-requisito: **Tabela de Proveniência de Campos LAJ** (parte do `docs/PROVENIENCIA-CAMPOS.md`),
classificando cada campo da ficha de robô LAJ em:
- **(a) extraível do N1** — polígono da laje, dimensões, nível, obstáculos (do estrutural limpo)
- **(b) algorítmico** — linhas_vert/horiz, uniões, pontaletes (calculados das dimensões)
- **(c) só-no-N2** — convenções do projetista (ex.: modo_selecionado escolhido pelo humano)
- **(d) teto estrutural** — dado ausente do DXF de origem

| Story | Entrega |
|-------|---------|
| LJ-B.1 | Seção LAJ na Tabela de Proveniência (a/b/c/d) |
| LJ-B.2 | `conversao_n1_diff` para LAJ: `convert(campos_N1_SA)` vs ficha N2, agrupado por categoria, no 13_PAV |
| LJ-B.3 | Loop de fixes: deltas (a)/(b) → fixes nos extratores do Structural Analyzer / no conversor N1→ficha-robô |
| LJ-B.4 | Campos (c): default por estilo + (futuro) consulta RAG reverso; (d) excluídos com referência |

**Meta:** delta médio categorias (a)+(b) ≤ tolerância em 100% das lajes do 13_PAV.
**O loop é o treino:** cada divergência N1-vs-N2 é uma lição — vira fix de extrator, regra
semântica nova, ou campo de estilo. O N1 não muda de schema; aprende a se preencher certo.

---

## 5. FASE LJ-C — N1 → N3 (fechar o pipeline)

**Objetivo:** com o N1 interpretado (Fase LJ-B), gerar N3 (mesmo `gerar_lj_dxf_stog.py`) e
provar N3 ≅ N4.

| Story | Entrega |
|-------|---------|
| LJ-C.1 | `convert(N1)` → ficha-robô LAJ → `gerar_lj_dxf_stog.py` → DXF N3 |
| LJ-C.2 | G2 canônico N3 vs N4 (mesmo comparador da Fase LJ-A) no 13_PAV |
| LJ-C.3 | LAJ 13_PAV: N3 ≅ N4 (Arete end-to-end sem N2 como input) |

Como N3 e N4 saem do MESMO gerador, LJ-B PASS (categorias a+b) ⇒ LJ-C PASS por construção.
LJ-C é a prova de que nada vazou da interpretação para o desenho.

---

## 6. Critérios de Arete LAJ (definição operacional)

> **ESCOPO DO PRODUTO DO ROBÔ DE LAJE (decisão do usuário, 2026-06-14):**
> O que importa é a **ÁREA INTERNA da laje**. O produto do robô = **CONTORNO** (outline) +
> **LINHAS INTERNAS** da laje (divisões de painel, uniões, HLAZ) + as **cotas dessas divisões
> internas**. Vigas e pilares são parte do contorno — info útil/necessária para reconhecer e
> posicionar, mas **NÃO são produto do robô de laje**. Portanto:
> - **CONTEÚDO (entra na paridade):** polígono do contorno, linhas internas, cotas internas
>   (122/167/102/20/61), HLAZ nas uniões, nome da laje, obstáculos internos, modo.
> - **CONTEXTO (exceção documentada, info-only):** dimensões das vigas de contorno (ex.
>   `19/120, 19/55, 19/66, 19/71`), labels de pilares vizinhos (`P8`, `P49`), nível (`852.12`),
>   espessura anotada (`h=13`). São anotações da estrutura circundante, não geometria gerada
>   pelo robô de laje. Ficam fora da paridade (em `arete_config.py`, lista `LJ_CONTEXTO`).
> - **CRUFT DO GERADOR (remover do gerador):** textos que o N4 emite e o recorte NÃO tem
>   (AUX00 `L308 122X102`, `c=...`, labels duplicados por painel). Excluir no G2 é PROIBIDO —
>   esconde divergência. Fix no `gerar_lj_dxf_stog.py`.

Uma laje atinge Arete quando:
1. **Integridade do contorno:** polígono outline reconhecido e gerado idêntico (vértices,
   comprimento/largura ±0,5cm; obstáculos internos no lugar)
2. **Linhas internas:** grade de painéis com mesma contagem + cada painel ±0,5cm; uniões
   (is_union) coincidem; `modo_selecionado` correto
3. **Cotas internas:** mesmos VALORES + contagem (122/167/102/20/61…); nome da laje presente
4. **HLAZ** nas uniões presente conforme recorte
5. Pontaletes EXCLUÍDOS (cálculo NBR, não fôrma); contexto (viga/pilar/nível/h=) EXCLUÍDO
   como `LJ_CONTEXTO` documentado; cruft do gerador (AUX00/c=) REMOVIDO do gerador
6. Estilo do robô (layers-padrão); nada de layer de estilo humano sintetizada
7. Veredito visual: Claude vision sem divergência semântica no PNG lado a lado

Pavimento em Arete = 100% das lajes não-BLOCKED.

---

## 7. Roadmap LAJ

| Fase | Foco | Escopo | Status |
|------|------|--------|--------|
| LJ-A | N2→N4 (extrator+gerador) | L308 → 18 lajes 13_PAV | ⏳ Iniciar |
| LJ-B | N2↔N1 (interpretação) | 13_PAV | Após LJ-A |
| LJ-C | N1→N3 (fechar pipeline) | 13_PAV | Após LJ-B |
| LJ-D | Expansão | demais pisos TREINO_1 → outras obras | Em steps |

---

## 8. Regras (herdadas do masterplan global — INEGOCIÁVEIS)

- Comparação **canônica** (conteúdo), não (layer,dxftype) cru contra o traço humano.
- **Tudo por fórmula** a partir da ficha; zero hardcode de medida de uma laje.
- Nunca sintetizar layer de estilo humano; nunca selar golden com FAIL; nunca expandir
  escopo antes do step atual a 100%.
- Schema N1 imutável; convergência na conversão.
- Exceção só com aprovação humana explícita, registrada em `arete_config.py`.
- Um fix por causa; regressão após cada toque no gerador; renderizar e LER os PNGs nos FAIL.

---

*Fable (Estrategista) — Cowork | 2026-06-14*
