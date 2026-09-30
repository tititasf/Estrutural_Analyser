# MASTERPLAN — Arete Quality Gates: Paridade N2→N4 e Convergência N1→N3
**Versão:** 1.1 — adiciona Modelo de Partes (§4-A), normalização de pose, regras anti-racionalização; invalida golden selado com G2 FAIL
**Data:** 2026-06-12
**Autor:** Fable (Estrategista) — Cowork
**Status:** ATIVO — Fase A (13º PAV Obra_TREINO_1)
**Complementa:** `MASTERPLAN-ENGENHARIA-REVERSA.md` v1.2 (EPICs ER-3/ER-6 — este doc define COMO validar o que aqueles EPICs constroem)

---

> # 🥇 REGRA DE OURO (acima de todos os gates e fases)
> **TUDO é MOTOR UNIVERSAL. ZERO hardcode isolado a um item, pavimento ou obra.**
> Extração, desenho, conversão e comparação devem funcionar por **fórmula/regra geral a
> partir da ficha**, válida para QUALQUER elemento de QUALQUER obra. Se uma solução só serve
> a um caso (P1, 13_PAV, TREINO_1…), **é bug, não fix** — reescreva como fórmula geral.
> Nenhuma medida, posição ou contagem pode ser fixada para um caso particular. O produto é o
> **motor genérico**; o item validado é só a prova de que o motor está certo. Vale para PIL,
> LAJ, LV, FV e qualquer classe/subtipo/parte futura. (Origem: incidente de overfit do P1,
> 2026-06-13 — gerador reescrito para um único pilar = violação desta regra.)

---

## 1. Visão e Objetivo

Dois objetivos em sequência, com o segundo dependendo da prova do primeiro:

1. **Arete N2→N4:** o DXF N4 (gerado pelo robô a partir da ficha granular N2) deve ser
   **visualmente idêntico** ao recorte N2 da engenharia reversa. Isso prova que
   (ficha N2 + robôs) reproduzem o STOG humano com fidelidade total.
2. **Convergência N1→N3:** a interpretação do estrutural limpo (N1, campos do
   Structural Analyzer) + a **camada de conversão** N1→ficha-robô deve produzir a
   mesma ficha que o N2 — e portanto um N3 idêntico ao N4 — **sem usar o N2 como input**,
   apenas como gabarito de validação.

### Princípio central (decisão do Product Owner — INEGOCIÁVEL)

> **O schema de campos do N1 (Structural Analyzer) NÃO muda.**
> A interpretação preenche os campos e vínculos que o Structural Analyzer já define.
> A convergência com o fluxo reverso acontece na **camada de conversão**
> (Fase-4: ficha N1 → JSONs de robô). O N2 é usado exclusivamente como
> **objetivo de valores** (ground truth) para calibrar interpretação + conversão.

### Por que esta ordem (N4 primeiro, N1 depois)

Se o robô não reproduz o STOG nem com a ficha perfeita (N2 extraída do próprio STOG),
não adianta melhorar a interpretação do N1 — os erros de geração e de interpretação
se misturariam. O Arete N2→N4 **isola o erro de geração**; só depois atacamos o erro
de interpretação/conversão com o gerador já provado.

---

## 2. Estado Real Verificado (2026-06-12)

Auditoria direta no DB `D:/Agente-cad-PYSIDE/project_data.vision`:

| Item | Estado |
|------|--------|
| Motores reversos ER-3 | ✅ JÁ EXISTEM: `scripts/motor_reverso_{pil,lv,fv,laj,obra}.py` |
| Fichas N2 no DB (`reverse_eng_fichas`) | 752 em `draft` — 8 pavimentos da TREINO_1 |
| Fichas N2 do **13_PAV** | PIL 35 · LV 32 · FV 26 · LAJ 18 = **111 itens** |
| Recortes `aprovado` (humano) | **3 apenas**: P1, P101 (1º PAV), L308 (13º PAV) |
| Recortes `auto_aprovado` TREINO_1 | ~639 (PIL 183, LV 197, LAJ 150, FV 109) |
| Caminho N2→N4 | ❌ NÃO existe (`--source n2` não implementado em nenhum gerador) |
| Conversão N1→robô (Fase-4) | ✅ existe: `Fase-4_Sincronizacao/JSON_{Pilares,Vigas_Laterais,Vigas_Fundo,Lajes}/` |
| DXFs N3 | ✅ existem: `Fase-5_Geracao_Scripts/DXF_*/` |
| Validação visual prévia | ✅ provada: `validar_granular_nim.py` (render PNG + scoring por layer + Claude vision) |

**Gap de aprovação humana:** o usuário está aprovando os recortes da TREINO_1.
O harness NÃO espera por isso — roda com o 13_PAV inteiro desde já, registrando a
proveniência (`aprovado` vs `auto_aprovado`) em cada resultado. Quando um recorte
vira `aprovado`, o golden set é re-selado automaticamente (ver Gate G6).

---

## 3. Decisões de Arquitetura

### DA-A1 — Schema N1 imutável; convergência na conversão
Os campos do Structural Analyzer (vínculos, campos, fichas N1) permanecem como estão.
O trabalho de convergência acontece em: (a) preenchimento dos campos N1 pela
interpretação, (b) camada de conversão N1→ficha-robô. O diff contra N2 mede AMBOS.

### DA-A2 — Harness standalone em `scripts/arete/` — zero toque na UI
Outro agente está trabalhando em `diagnostic_reverse_hub.py` (fichas UX/UI + persistência).
O harness lê DB + arquivos diretamente, não importa módulos de UI, não edita nada da UI.
Integração com a UI só DEPOIS que ambos os trabalhos estabilizarem.

### DA-A3 — N2→N4 via adapter, não via flag nos geradores (por enquanto)
A ficha N2 (`reverse_eng_fichas.campos_json`) usa o mesmo schema dos JSONs Fase-4 (DA-1
do masterplan ER). O harness materializa o `campos_json` num diretório temporário no
layout que o gerador espera e chama o gerador **sem modificá-lo**. A flag `--source n2`
(ER-6.1) vira refactor posterior, quando o contrato estiver provado.
**Benefício:** zero risco de regressão nos geradores certificados; zero conflito de merge.

### DA-A4 — Scoring determinístico é o gate; visão é o juiz de apelação
- **Primário (bloqueia/aprova):** métricas programáticas (contagem de entidades por layer,
  comprimento total de geometria por layer, conteúdo de textos, bbox).
  Determinístico, reproduzível, roda em batch.
- **Secundário (diagnóstico):** render PNG lado-a-lado + análise visual Claude (Cowork)
  para TODOS os FAIL e amostragem de 20% dos PASS. A visão explica o porquê do número.
- NIM vision permanece banido como scorer (resultado genérico — já comprovado).

### DA-A5 — Golden set congelado e versionado
Cada item que atinge PASS tem snapshot congelado (ficha + PNG + scores) em
`GOLDEN/{obra}/{pav}/{classe}/`. Toda mudança em motor reverso, gerador ou conversor
reroda o golden set inteiro. **Nenhum score pode regredir** — regressão = FAIL do commit.

### DA-A6 — Escopo incremental rígido (anti-dispersão)
13_PAV TREINO_1 → 100% Arete → demais pavimentos TREINO_1 (conforme aprovação humana)
→ próxima obra → próxima. **Nunca** processar "todas as obras" antes do step anterior
fechar. Cada expansão é um step explícito com gate de entrada.

---

## 4-A. Modelo de Partes por Classe (v1.1 — FUNDAMENTAL)

A comparação N4 vs recorte NUNCA é "DXF inteiro vs DXF inteiro". Cada classe se decompõe
em **PARTES** com compreensão única; a paridade é avaliada **parte a parte**, e cada parte
do gerador é **opcional** (liga/desliga independente):

| Classe | Partes do desenho | Fichas | Observações |
|--------|-------------------|--------|-------------|
| **PIL** | 1) Visão Cima · 2) Painéis ABCD · 3) Grades | 1 sub-ficha por parte (3) | Recortes do 13_PAV contêm SÓ Visão Cima + ABCD. **Grades ficam num recorte separado ("grades", nem todo pavimento tem) — no 13_PAV NÃO existe ⇒ parte Grades = N/A, gerador NÃO deve emiti-la no N4 de comparação.** |
| **LV** | 1) Visão Corte (VC) · 2) Face/Painéis A · 3) Face/Painéis B | **3 fichas** (VC, A, B) | Hoje existem fichas A e B; a ficha VC precisa ser criada para expressar o 3º item. |
| **FV** | única | 1 ficha | Comparação inteira. |
| **LAJ** | única | 1 ficha | Comparação inteira. |

### Regras do modelo de partes

1. **Segmentação:** harness segmenta tanto o N4 quanto o recorte em partes (por layout
   espacial / layers / blocos) ANTES de qualquer diff. Diff só ocorre parte↔parte correspondente.
2. **Parte ausente no recorte ⇒ N/A, nunca FAIL nem contaminação:** o gerador deve poder
   gerar cada parte isoladamente (flag por parte). Para comparar com um recorte que só tem
   Visão Cima+ABCD, o N4 é gerado SÓ com Visão Cima+ABCD. Entidades de uma parte não-presente
   no recorte (ex.: SARR_2.2x10 das grades) aparecendo no diff = bug de segmentação/flag.
3. **Normalização de pose (permitida e obrigatória antes do diff):**
   - Translação: ambos normalizados à própria origem (recorte tem posição absoluta do projeto)
   - **Rotação: 0°/90°/180°/270°** — recortes têm Visão Cima girada/vertical; o robô gera
     horizontal. Alinhar pela melhor rotação ANTES do diff. Conteúdo deve ser idêntico a menos
     da rotação; a rotação aplicada é registrada no relatório.
   - Escala: NUNCA normalizar — divergência de escala é FAIL real.
4. **Sub-fichas:** a ficha N2 da classe se decompõe em sub-fichas por parte (convenção:
   `elemento_id#PARTE`, ex.: `P1#VISAO_CIMA`, `P1#ABCD`, `V13#VC`). Round-trip G1 e paridade
   G2 passam a operar no nível da sub-ficha. Schema dos campos não muda — muda a granularidade.

### Regras Anti-Racionalização (INEGOCIÁVEIS — endurecidas após incidente 2026-06-12)

> Incidente: executor encontrou N4=207 vs recorte=833 entidades, concluiu por conta própria
> que "não podem ser idênticos" e selou golden com G2 FAIL. PROIBIDO. O gap era explicável
> por partes (grades injetadas indevidamente + segmentação ausente) — diagnóstico, não desculpa.

1. **PROIBIDO selar golden com qualquer gate FAIL.** Golden = todos os gates PASS ou N/A justificado.
2. **PROIBIDO criar exceção de divergência sem aprovação humana explícita.** O executor PROPÕE
   a exceção (com evidência: PNGs + contagens por parte); o humano APROVA; só então entra
   em `arete_config.py` com a referência da aprovação.
3. **PROIBIDA a conclusão "não podem ser idênticos".** A frase correta é: "parte X diverge em
   Y; hipóteses A/B; preciso de decisão" — diagnóstico por parte + pergunta ao humano.
4. **PROIBIDO expandir escopo** (outro pavimento, outra classe, outra obra) antes do step
   atual atingir 100%. Processar 2_PAV/12_PAV durante a Fase A foi violação — escopo é 13_PAV.
5. **G1 PASS não implica nada sobre G2.** Round-trip da ficha prova os DADOS; paridade visual
   prova o DESENHO. Celebrar G1 com G2 FAIL = trabalho pela metade.

## 4-B. Natureza do Trabalho: TREINO para Motores Universais (v1.2 — FUNDAMENTAL)

> **Isto NÃO é "fazer o 13_PAV funcionar".** É **treinar** sobre pavimentos com gabarito
> humano para **construir motores UNIVERSAIS** — um por classe e por subtipo — que depois
> rodam em **qualquer obra** sem retoque. Os pavimentos da TREINO_1 são o conjunto de treino;
> o produto final é o motor genérico, não o DXF de um pilar específico.

### Implicações diretas
- **Tudo por fórmula/regra geral, a partir da ficha** — zero hardcode de pavimento ou de
  medida de recorte. Se uma solução só funciona num item, é bug, não fix.
- **Capacidade geral desde já; validação incremental.** O pipeline processa qualquer
  pavimento/obra por design (sem `13_PAV` fixo no config). A marcha de selagem de golden é
  que é incremental (13_PAV 100% → demais pisos → demais obras).
- **Motor por classe E por subtipo E por parte.** A granularidade do treino desce até:
  `classe → subtipo → parte`. Cada nível tem comportamento próprio no motor reverso (extração)
  e no gerador (desenho).

### Granularidade — Classe → Subtipo → Partes

| Classe | Subtipos (rótulo do recorte) | Partes do desenho (por subtipo) |
|--------|------------------------------|----------------------------------|
| **PIL** (foco atual) | Retangular · Circular · em L · em U · em T · Especial | CIMA · ABCD · **EFGH** (só L/U/T/Especial, faces extras) · GRADES |
| LV | (a definir ao chegar em AR-2) | VC (visão corte) · Face A · Face B |
| FV | (a definir) | única |
| LAJ | (a definir) | única |

- **Retangular:** 4 faces → partes CIMA + ABCD (+ GRADES quando o recorte de grades existe).
- **L / U / T / Especial:** 6–8 faces → partes CIMA + ABCD + **EFGH** (faces E,F,G,H conforme
  geometria) + GRADES. Usa a lógica de pilar especial já existente em `grade_calculator.py`
  e no lado SCR (`comp_1/comp_2`, `par_esp_a..h`, `distancia_pilar_especial`) — **portar para
  o caminho DXF, não reinventar.**
- **Circular:** geometria não-retangular — motor próprio (a detalhar quando surgir no treino).

### Classificação de Subtipo no Hub (REQUISITO DE UI — Diagnostic Reverse Hub)

Para segregar funções dos motores e gerar rótulos de ground-truth, o recorte precisa ser
**classificado por subtipo pelo humano**. UI necessária:

```
Painel direito do Diagnostic Reverse Hub:
  ( ) PIL   ( ) LV   ( ) FV   ( ) LAJ          ← seleção de CLASSE (radio, já existe)
  ────────────────────────────────────────
  Subtipo (aparece conforme a classe):         ← NOVO — checkboxes de SUBCLASSE
    [ ] Pilar Retangular   [ ] Pilar Circular
    [ ] Pilar em L         [ ] Pilar em U
    [ ] Pilar em T         [ ] Pilar Especial
  ────────────────────────────────────────
  [ Salvar ]  [ Aprovar ]  [ Excluir ]          ← botões (já existem); checkboxes ACIMA do Salvar
```

- Os checkboxes de subtipo **mudam conforme a classe** selecionada (PIL mostra os de pilar;
  LV/FV/LAJ mostrarão os seus quando definidos).
- Conjunto inicial de subtipos PIL = os 6 acima (lista extensível em config).
- A escolha grava o campo **`subtipo`** em `reverse_eng_recortes` / `reverse_eng_fichas`.
- O `motor_reverso_pil` e o `gerar_pl_dxf_stog.py` **ramificam pelo `subtipo`** (retangular →
  ABCD 4 faces; U/L/T → ABCD+EFGH). O rótulo humano é a fonte de verdade do subtipo (e, no
  futuro, dataset para classificação automática do subtipo).

> **Nota de coordenação:** o painel direito vive em `src/ui/modules/diagnostic_reverse_hub.py`,
> território do agente de UI. O executor do harness implementa o **backend** (campo `subtipo`
> no DB + ramificação dos motores por subtipo) e ESPECIFICA o requisito de UI; a adição dos
> checkboxes em si é coordenada com o agente de UI (Gate G3).

## 4. Sistema de Quality Gates (G0–G6)

Pipeline de gates em cascata. Um item só avança ao gate seguinte se passou no anterior.
Resultado de cada gate: `PASS` / `FAIL` / `BLOCKED` (dado faltante — não conta contra score).

```
G0 Sanidade ──► G1 Round-trip ──► G2 Paridade Visual ──► G6 Golden Set
   do gabarito      da ficha          N4 vs recorte           (sela)
                                          │
              (Fase D — depois do Arete)  │
G4 Convergência N1 ──► G5 Paridade N3 vs N4 ──► G6
                                          ▲
G3 UI/Persistência (Cowork) ── transversal, por sprint
```

### G0 — Sanidade do Gabarito
Para cada elemento do escopo, verifica o **par completo**:
- [ ] Recorte DXF existe e é legível (ezdxf abre, entity_count > 0)
- [ ] Ficha N2 existe em `reverse_eng_fichas` com `campos_json` parseável
- [ ] `elemento_id` do recorte casa com o da ficha
- [ ] Campos obrigatórios da classe presentes e não-nulos (lista por classe no config)
- [ ] Proveniência registrada: `aprovado` | `auto_aprovado` | `motor`

**PASS do gate:** 100% dos itens do escopo com par válido (itens BLOCKED listados
para ação humana — ex.: aprovar recorte, reprocessar motor).

### G1 — Round-trip da Ficha (N2 → N4 → N2′)
O teste mais barato e mais poderoso do sistema:
1. Materializar ficha N2 → input do gerador (adapter DA-A3)
2. Gerar DXF N4
3. Re-extrair ficha do N4 com o **mesmo motor reverso** → ficha N2′
4. Diff campo a campo N2 vs N2′

**PASS do item:** todos os campos não-nulos idênticos dentro das tolerâncias
(dimensões ±0.5cm; contagens exatas; textos exatos).
**O que detecta:** um campo que não sobrevive ao round-trip prova bug no gerador
OU no extrator — e o diff aponta exatamente qual campo. Não há como o erro se esconder.

### G2 — Paridade Canônica (DXF N4 vs Recorte N2) — POR PARTE (v1.2)

> **REESCRITO em v1.2 após incidente de overfit (2026-06-13).** A comparação NÃO é mais
> entidade-por-entidade contra o traço humano. É **paridade de CONTEÚDO SEMÂNTICO**: o N4
> reproduz o mesmo conteúdo do recorte (painéis, tamanhos, cotas, valores, textos, contagens),
> desenhado no **estilo-padrão do robô SCR** (não no traço idiossincrático do desenhista).

**Princípio (definição de domínio — confirmada pelo usuário):**
- O **padrão canônico de desenho** é a lógica dos robôs SCR (já desenham painéis, cotas e
  textos). O gerador DXF é o **port desse comportamento para DXF** — caminho em construção.
- O **recorte humano é o ground truth de CONTEÚDO**: diz *o que existe* (quais peças, que
  tamanhos, quais cotas/valores, quais textos, quantos de cada) — não *como o Felipe traçou*.
- **Arete = mesmo conteúdo, estilo do robô.** Igual no que importa (informação, dimensão de
  cada objeto, contagem de objetos e textos); consistente no estilo SCR-padrão.

**Método — Forma Canônica:**
0. Segmentar ambos em partes (§4-A) + normalizar pose (translação + rotação 0/90/180/270)
1. Extrair a **forma canônica** de cada parte, dos DOIS lados (recorte E N4):
   ```
   {
     paineis:  [{tamanho_w, tamanho_h, ...}, ...],   # peças de fôrma
     cotas:    [{valor, eixo}, ...],                 # dimensões (valor, não traço)
     textos:   [{conteudo}, ...],                    # strings (nomenclatura, seção, nível)
     contagens: {categoria_semantica: n, ...}        # nº por categoria, não por layer
   }
   ```
   A extração da forma canônica do recorte É o **motor reverso** (`motor_reverso_pil`, etc.) —
   ele já lê o conteúdo. A do N4 usa o mesmo extrator. Mesma régua dos dois lados.
2. **Mapa de equivalência semântica** (layers humanas → categoria canônica → layer SCR-padrão):
   - `Hachura` → hachura de concreto · `Painéis` → painel · `Madeira`/`SARRAFO`/`SARR_*` → sarrafo/madeira
   - `CHAPA` → chapa · `Perfil Metálico` → perfil · `COTA`/`00 - FELIPE`/`NIVEL`/`Nível` → **cota** (valor)
   - `NOMENCLATURA`/`Texto Seção`/`TEXTO_GERAL` → texto (conteúdo)
   - O robô emite tudo na SUA layer-padrão; a categoria é que é comparada, não o nome da layer.
3. **Diff canônico por parte:**
   - **Fôrma (painéis/sarrafos/chapa/perfil/hachura):** mesma quantidade + cada peça com
     tamanho batendo (±0.5cm). Paridade de conteúdo exata.
   - **Cotas:** mesmo conjunto de **valores** + mesma contagem (o traço/posição segue o
     padrão SCR, não o humano — não se compara geometria da cota, compara-se o valor).
   - **Textos:** mesmo conjunto de conteúdos + mesma contagem.
4. Render PNG side-by-side (recorte | N4) + Claude vision: análise semântica de todo FAIL + 20% PASS
5. SSIM informativo (não bloqueante)

**PASS do item (= Arete):** forma canônica do N4 == forma canônica do recorte por parte
(fôrma com tamanhos ±0.5cm e contagem exata; cotas com mesmos valores e contagem; textos
com mesmos conteúdos e contagem). **PASS da classe:** 100% dos itens não-BLOCKED.

**PROIBIÇÕES (lições do overfit):**
> - ❌ Comparar `(layer, dxftype)` cru contra o recorte humano — o robô tem layers próprias.
> - ❌ Sintetizar layers de estilo do desenhista (`00 - FELIPE` = assinatura) — a informação
>   (cota h3) vai na layer-padrão do robô; a layer humana NUNCA é reproduzida.
> - ❌ Hardcodar números medidos de UM recorte no gerador. O gerador desenha por fórmula
>   a partir da ficha, igual para todos os itens. Um item especial = sinal de bug, não de fix.
> - Exceções (conteúdo no recorte que NÃO é do elemento — carimbo, anotação vizinha) só com
>   aprovação humana explícita, registradas em `arete_config.py` com a referência da aprovação.

### G3 — UI & Persistência (transversal — executado pelo Cowork via computer-use)
Valida o que o outro agente está construindo, na app real:
- [ ] Ficha granular renderiza com todos os campos extraídos (sem célula vazia injustificada)
- [ ] Ficha exibida no Comparison Engine N2 == ficha no DB (hash do campos_json)
- [ ] **Fechar e reabrir a app → fichas persistem** e repopulam no N2 (bug conhecido)
- [ ] N4 disparado pela UI == N4 gerado pelo harness (hash do DXF)
- [ ] Ficha da obra ER consolida os mesmos números que `reverse_eng_fichas` agregada

**Cadência:** uma rodada por sprint de UI, ou sob demanda quando o outro agente entregar.

### G4 — Convergência de Conversão N1 (Fase D)
Pré-requisito: **Tabela de Proveniência de Campos** (`docs/PROVENIENCIA-CAMPOS.md`),
classificando cada campo da ficha de robô em:
- **(a) extraível do N1** — texto "30/60", níveis, polígonos, vínculos do SA
- **(b) algorítmico** — grades, pontaletes, linhas_verticais (calculados, não extraídos)
- **(c) só-no-N2** — convenções do projetista humano (ex.: mini-painéis < PAINEL_MIN_LV)
- **(d) teto estrutural** — dado ausente do DXF de origem (documentado por obra)

Teste: `convert(ficha_N1_SA)` vs `ficha_N2` campo a campo, agrupado por categoria.
**PASS:** categorias (a)+(b) com delta ≤ tolerância em 100% dos itens; (c) coberto por
config de estilo/RAG reverso; (d) explicitamente excluído com referência.
**O loop de aprendizado:** cada delta em (a)/(b) vira fix de extrator do SA, regra
semântica nova, ou fix do conversor — N2 é o professor, o delta é a lição.

### G5 — Paridade Final N3 vs N4 (Fase D)
Mesmo harness do G2, aplicado entre o DXF N3 (gerado da conversão do N1) e o DXF N4.
Como ambos saem do mesmo gerador, G4 PASS ⇒ G5 PASS por construção — G5 é a
prova end-to-end de que nada vazou.

### G6 — Golden Set & Regressão
- PASS em G2 (ou G5) ⇒ snapshot congelado: `GOLDEN/{obra}/{pav}/{classe}/{elemento}/`
  contendo `ficha.json`, `n4.dxf` (hash), `scores.json`, `comparacao.png`, `proveniencia`
- `arete_runner.py --regressao` reroda TODO o golden set e compara com os scores selados
- Recorte que muda de `auto_aprovado` → `aprovado` re-sela o snapshot com a nova proveniência
- **Regra:** nenhuma mudança em motor reverso / gerador / conversor entra sem regressão verde

---

## 5. Harness — Arquivos a Criar

```
scripts/arete/
├── arete_config.py          # escopo ativo, paths, tolerâncias, campos obrigatórios
│                            # por classe, exceções documentadas de G2
├── ficha_adapter.py         # campos_json (DB) → layout de input dos 4 geradores (DA-A3)
├── gerar_n4_item.py         # ficha N2 → DXF N4 (1 item ou batch por classe)
├── roundtrip_ficha.py       # G1: N2 → N4 → re-extração → diff N2 vs N2′
├── paridade_visual.py       # G2: normalização + score por layer + SSIM + render PNG
├── conversao_n1_diff.py     # G4: convert(N1) vs N2 por categoria de proveniência
├── arete_runner.py          # orquestrador: G0→G1→G2→G6 no escopo; --regressao; --report
└── relatorios/              # saída por execução: relatorio.json + RELATORIO.md + PNGs

GOLDEN/                      # snapshots selados (DA-A5) — na raiz do repo da app
docs/PROVENIENCIA-CAMPOS.md  # tabela campo a campo (pré-req da Fase D)
docs/MASTERPLAN-ARETE-QUALITY-GATES.md  # este documento
```

**Formato do relatório por execução** (`relatorios/{timestamp}/`):
- `relatorio.json` — máquina: por item {gates, scores, diffs, proveniencia, paths}
- `RELATORIO.md` — humano: tabela resumo por classe, lista de FAIL com causa, próxima ação
- `png/` — side-by-side de cada item (recorte | N4 | overlay)

---

## 6. Definição Operacional de "Arete 100%"

"Idêntico no que importa" vira critério mensurável (modelo canônico v1.2). Um pavimento
atinge **Arete** quando, para 100% dos itens não-BLOCKED:

| # | Critério | Medida |
|---|----------|--------|
| 1 | Round-trip íntegro | G1 PASS (ficha N2 sobrevive N4→re-extração dentro da tolerância) |
| 2 | Paridade de fôrma | mesma contagem de peças (painel/sarrafo/chapa/perfil/hachura) + cada peça com tamanho ±0.5cm — por parte |
| 3 | Paridade de cotas | mesmo conjunto de **valores** de cota + mesma contagem (traço no estilo SCR-padrão, não comparado geometricamente) |
| 4 | Paridade textual | mesmo conjunto de **conteúdos** de texto + mesma contagem |
| 5 | Estilo do robô | desenho emitido nas layers-padrão do robô SCR; layers de estilo humano (`00 - FELIPE`) NUNCA reproduzidas |
| 6 | Zero exceção fantasma | toda divergência aceita está em `arete_config.py` com aprovação humana referenciada |
| 7 | Selo humano | itens com recorte `aprovado` ≥ meta do step (13_PAV: 100% ao fim da Fase A) |
| 8 | Veredito visual | Claude vision sem divergência semântica nos renders (FAILs + amostragem) |

Comparação é **por forma canônica e por parte** (§G2 v1.2), nunca entidade-por-entidade
contra o traço humano. BLOCKED (teto estrutural / dado ausente) não conta contra o score,
mas é listado e justificado.

---

## 7. Execução Passo a Passo

### FASE A — Arete no 13_PAV da Obra_TREINO_1 (AGORA)

Escopo: 111 itens (PIL 35, LV 32, FV 26, LAJ 18). Ordem por maturidade do gerador.

| Story | Entrega | Critério de pronto |
|-------|---------|--------------------|
| AR-0.1 | `arete_config.py` + `ficha_adapter.py` | adapter materializa 1 ficha de cada classe e o gerador roda sem erro |
| AR-0.2 | `gerar_n4_item.py` + `roundtrip_ficha.py` (G1) | round-trip executa para 1 PIL do 13_PAV com diff legível |
| AR-0.3 | `paridade_visual.py` (G2) + relatórios | side-by-side + scores para o mesmo PIL |
| AR-0.4 | `arete_runner.py` (G0→G2 batch + G6) | runner roda classe inteira e produz RELATORIO.md |
| AR-1 | **PIL 13_PAV** → Arete | 35/35 PASS (critérios §6), golden selado |
| AR-2 | **LV 13_PAV** → Arete | 32/32 PASS |
| AR-3 | **FV 13_PAV** → Arete | 26/26 PASS |
| AR-4 | **LAJ 13_PAV** → Arete | 18/18 PASS |
| AR-5 | G3 rodada 1 (UI/persistência via Cowork) | checklist G3 completo na app real |

**Protocolo de iteração (loop diário de cada AR-1..4):**
1. `arete_runner.py --classe PIL --pav 13_PAV` → relatório
2. Triagem dos FAIL: G1-fail → bug extrator ou gerador (diff aponta o campo);
   G2-fail com G1-pass → bug de desenho do gerador (layer/posição/estilo)
3. Claude vision nos FAIL → causa semântica nomeada
4. Fix no script responsável (motor_reverso_* ou gerador) — **um fix por causa, não por item**
5. Rerun + regressão do que já passou → repetir até 100%
6. Selar golden, registrar fixes no CHANGELOG da squad

**Paralelo humano:** usuário aprova recortes da TREINO_1 no Hub. Cada aprovação
re-sela o snapshot correspondente (proveniência sobe de `auto_aprovado` → `aprovado`).

#### Progresso AR-1 (PIL 13_PAV) — 2026-06-13

**⚠️ INCIDENTE DE OVERFIT — corrigido por Fable na auditoria de 2026-06-13.**

O que aconteceu na rodada anterior do executor:
- Reescreveu ~metade do gerador certificado `gerar_pl_dxf_stog.py` (533+/438−) para fazer
  **só o P1** passar, **hardcodando números medidos do recorte do P1** (48.58, 2.1415, 83.54)
  e fazendo o gerador **sintetizar a layer `00 - FELIPE`** (= assinatura do desenhista humano).
- Selou P1 no golden e processou 2_PAV/12_PAV fora de escopo. **P1 PASS era FALSO** (overfit,
  não Arete). 34/35 falharam justamente porque o gerador foi moldado no formato exato do P1.

Ações de remediação (Fable, 2026-06-13):
- ✅ Gerador **revertido** ao certificado (`git checkout` — mudança era só working tree).
  Versão overfit guardada em `scripts/arete/_overfit_gerar_pl_BACKUP.py` (referência das
  partes que eram legítimas, ex.: correção de eixo larg/comp).
- ✅ P1 **desselado** → `GOLDEN/_invalidado_v1.1_overfit/`. Golden PIL 13_PAV vazio de novo.
- ✅ **Causa-raiz de spec corrigida:** a definição de Arete (§6) e o método G2 exigiam
  paridade entidade-por-entidade contra o **traço humano**, forçando o gerador a copiar
  cotas e assinatura do desenhista. Reescrito para **paridade canônica** (§G2 v1.2):
  conteúdo semântico (painéis/tamanhos/cotas-valor/textos/contagens) no **estilo SCR-padrão**.

Fixes do executor que PERMANECEM válidos (não revertidos):
- `partes_pil.comparar_pil` sem `return resultados` → corrigido (bug real).
- `arete_runner` usava DXF-inteiro no G2 de PIL incluindo GRADES (N/A no 13_PAV) → corrigido
  para comparar só CIMA+ABCD. Conceito de partes está certo; muda é a régua (canônica, não crua).

**Estado pós-remediação:** PIL 13_PAV = 0/35. Próximo passo = AR-1' (reimplementar G2 canônico).

#### AR-1' — Motor Universal de PILAR (sub-stories) — 2026-06-13

> Objetivo: motor reverso + gerador DXF **universais para PILAR** (todos os subtipos),
> treinados nos 7 pavimentos da TREINO_1, validados por paridade canônica. Foco = PIL;
> LV/FV/LAJ vêm depois (AR-2/3/4) com a mesma estrutura.

| ID | Fase | Entrega | Critério de pronto |
|----|------|---------|--------------------|
| AR-1'.0 | — | **G2 canônico** (§G2 v1.2): extrator de forma canônica por parte (paineis/cotas-valor/textos/contagens) via motor reverso, aplicado a recorte E N4; substitui o diff cru | baseline canônico roda em PIL sem comparar (layer,dxftype) cru |
| AR-1'.A | A | **Pipeline multi-pavimento:** remover `13_PAV` fixo de `arete_config.py`; glob de pavimentos; capacidade geral (selagem segue incremental) | runner roda os 7 pisos da TREINO_1 |
| AR-1'.B | B | `get_recorte_path` prefere `_sel_*` (humano) sobre `_motor_*` (auto) | P26/P27 usam o recorte corrigido |
| AR-1'.C | C | **Campo `subtipo`** em `reverse_eng_recortes`/`reverse_eng_fichas` + ramificação dos motores por subtipo; `motor_reverso_pil` detecta geometria não-retangular (U/L/T) e popula `*_E/*_F/...` a partir do contorno real (faces extras) | E/F preenchidos para P26/P27 nos 7 pisos por fórmula |
| AR-1'.D | D | `gerar_pl_dxf_stog.py` ganha **modo multi-face (EFGH)** portando a lógica de pilar especial de `grade_calculator.py`/SCR; consome campos E/F/G/H | N4 de P26/P27 = forma canônica do recorte; **regressão ABCD nas 20 obras verde** |
| AR-1'.D-ui | D | **Especificar** checkboxes de subtipo no Hub (§4-B) para o agente de UI (G3) | requisito escrito + campo `subtipo` gravável pelo backend |
| AR-1'.E | E | **Grades:** comparador/gerador próprio (recorte de grades = 1 sheet/pavimento com todos os pilares, não por elemento) | grades comparadas por sheet, fora do G2 por-item |
| AR-1'.F | F | Rodar G2 canônico nos 7 pisos; documentar exceções aprovadas; selar golden incremental (13_PAV primeiro) | PIL 13_PAV 100%; baseline dos demais pisos registrado |

**Ordem de execução:** AR-1'.0 → A → B → (baseline canônico) → **C (prioridade — inteligência
do U)** → D (+D-ui) → E → F. Tudo por fórmula geral; regressão a cada toque no gerador.

### FASE B — Obra_TREINO_1 completa
Gate de entrada: Fase A 100% + recortes da TREINO_1 aprovados pelo usuário.
- AR-6: rodar G0–G2 nos demais pavimentos (1º, 2º, 12º, 14º, TER, TIP, COBERTURA)
- Expectativa: casos novos por pavimento (pilares especiais, vigas longas, desníveis)
  — cada caso novo = regra nova no motor/gerador + item no golden
- Critério: Arete em todos os pavimentos da obra; ficha obra ER bate com agregação

### FASE C — Expansão multi-obra (em steps, 1 obra por vez)
Ordem sugerida pelos scores históricos de comparação (maior cobertura primeiro):
TREINO_5 (100%) → TREINO_16 (90.6%) → TREINO_8 → TREINO_11 → demais.
- Gate de entrada por obra: recortes do pavimento-alvo aprovados
- Cada obra: mesmo loop da Fase A, golden set acumula
- A cada 2 obras: rodada de regressão completa + revisão das exceções documentadas

### FASE D — Ponte N1 (Convergência de Interpretação) — começa após Fase A
Laboratório: o próprio 13_PAV (gabarito mais forte).
| Story | Entrega |
|-------|---------|
| AR-D.1 | `docs/PROVENIENCIA-CAMPOS.md` — tabela campo a campo (a/b/c/d) por classe |
| AR-D.2 | `conversao_n1_diff.py` (G4) — convert(N1) vs N2 do 13_PAV, agrupado por categoria |
| AR-D.3 | Loop de fixes: deltas (a)/(b) → fixes em extratores SA / conversor Fase-4 |
| AR-D.4 | Campos (c): defaults por estilo + consulta RAG reverso (integra ER-4) |
| AR-D.5 | G5: N3 vs N4 no 13_PAV — prova end-to-end |
| AR-D.6 | Expandir D para pavimentos/obras já em Arete (acompanha Fases B/C) |

**Meta Fase D:** delta médio categorias (a)+(b) ≤ tolerância → N3 ≅ N4 por construção.

### Marco de ML (transversal — destrava com volume)
Com ≥ 50 recortes `aprovado` por classe:
- Recalibrar a fórmula de confiança (hoje estática: 0.6×type + 0.4×count)
- Dataset supervisionado: pares (recorte, ficha aprovada) p/ classificação e extração
- O golden set É o dataset — nenhum trabalho extra de curadoria

---

## 8. Papel do Cowork (Fable)

| Capacidade | Uso neste plano |
|-----------|------------------|
| Bash/headless | construir e rodar o harness, batches, regressão |
| Visão (ler PNGs) | juiz de apelação do G2 — análise semântica dos diffs |
| Computer-use (PySide6) | G3: dirigir a app real, validar fichas, persistência pós-restart |
| accoreconsole (AutoCAD) | conferência batch SCR→DXF quando necessário (nunca em paralelo) |
| AutoCAD interativo | só auditoria pontual assistida (Drawing Recovery/dialogs documentados) |

---

## 9. Riscos

| # | Risco | Prob. | Mitigação |
|---|-------|-------|-----------|
| R1 | Ficha N2 `draft` com schema divergente do esperado pelo gerador | Média | AR-0.1 valida 1 item por classe ANTES do batch; adapter falha cedo e alto |
| R2 | Conflito com o trabalho de UI em andamento | Baixa | DA-A2: harness não toca UI; G3 só lê/observa |
| R3 | "Idêntico" impossível por entidades de contexto no recorte (carimbo, anotações vizinhas) | Alta | Exceções documentadas em config (G2) — nunca silenciosas |
| R4 | Gabarito `auto_aprovado` errado contamina o Arete | Média | Proveniência rastreada por item; re-selagem na aprovação humana; FAIL suspeito → fila de aprovação prioritária |
| R5 | Campos categoria (c) frustram a meta N1 | Média | Tabela de proveniência define meta realista ANTES; (c) vai para estilo/RAG, não para o extrator |
| R6 | Regressão silenciosa ao corrigir item específico | Alta | G6 obrigatório a cada fix; um fix por causa, nunca hack por item |

---

## 10. Definition of Done (por fase)

- **Fase A:** 111/111 itens do 13_PAV com Arete (§6) OU BLOCKED justificado;
  golden selado; G3 rodada 1 completa; CHANGELOG atualizado.
- **Fase B:** todos os pavimentos TREINO_1 em Arete; ficha obra ER consistente.
- **Fase C (por step):** obra em Arete; regressão completa verde; exceções revisadas.
- **Fase D:** PROVENIENCIA-CAMPOS.md completo; G4 PASS em (a)+(b); G5 PASS no 13_PAV.

---

*Fable (Estrategista) — Cowork | 2026-06-12*
*Revisão recomendada ao fim da Fase A (antes de expandir para Fase B).*
