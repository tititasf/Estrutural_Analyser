# Looping agêntico — interpretação de pilares ABCD

**Objetivo:** validar e refinar a leitura de **pilares (PIL)** no N1 contextual  
(SVG) com **custo baixo**, antes de mexer no motor SA.

**Espelho FV:** `http://…/fundos_viga/V303.html` (SA + 3 camadas cegas)  
Código FV: `src/ui/widgets/fv_hifi_n1_render.py` (`setCtxHighlightMode`, `agent_annotation_boxes_html`).

**Referências:**
- `docs/INTERPRETACAO-PILARES-ABCD.md` — faces A–D, laje/passa/chega/interior, dualidade  
- `docs/PADRAO-TAGS-DESTAQUE-AGENTICO-PIL.md` — tags canônicas (SA **e** camadas)  
- `docs/PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md` — pan/zoom viewBox  
- Código: `scripts/arete/pil_agentic_highlight_draw.py`, `src/core/pil_qa_notes_chrome.py`,  
  `scripts/arete/export_pilares_abcd_fichas.py`, `src/core/pillar_abcd_tables.py`

---

## 1. Arquitetura de camadas (não é opcional)

| Camada | O quê | Tags | Artefato |
|--------|--------|------|----------|
| **SA motor** | Interpretação **atual** do motor (`face_beams` + ABCD) | **Sim — sempre** | `propostas/{P}_sa_motor.svg` + embutido no N1 HTML |
| **Ag.L1** | 1ª proposta QA — **julga o SA** | Mesmas tags | `{P}_qa_L1.svg` (+ alias `_qa_proposta.svg`) |
| **Ag.L2** | Refino — **julga L1** (looping cego) | Mesmas tags | `{P}_qa_L2.svg` |
| **Ag.L3** | Alvo validado **pré-fix** do motor | Mesmas tags | `{P}_qa_L3.svg` |

### Evolução com 3 camadas (como FV V303)

```
        ┌──────────────────────────────────────────────────┐
        │  SA motor (tags V.chega / V.passa / laje …)       │
        │  = leitura ORIGINAL do motor, já legível no N1   │
        └────────────────────┬─────────────────────────────┘
                             │ humano/agente L1 julga
                             ▼
        ┌──────────────────────────────────────────────────┐
        │  Camada 1  — 1ª leitura QA (pode divergir do SA) │
        └────────────────────┬─────────────────────────────┘
                             │ se L1 invalidou / atenção humana
                             │ redesenha como “novo SA” cego
                             ▼
        ┌──────────────────────────────────────────────────┐
        │  Camada 2  — reavalia L1 sem “saber” que é redo  │
        └────────────────────┬─────────────────────────────┘
                             │ idem
                             ▼
        ┌──────────────────────────────────────────────────┐
        │  Camada 3  — alvo estável → só então fix motor   │
        └──────────────────────────────────────────────────┘
```

**Na 1ª geração do pack:** L1 ≈ L2 ≈ L3 ≈ SA (mesma geometria/tags; só o  
**banner** muda). A divergência aparece quando o agente **re-desenha** L2/L3  
após atenção humana (ou looping cego).

### Regras de ouro
1. **SA N1 sempre com tags** — não existe “N1 só vermelho” no export HTML.  
2. **Não** mudar o motor enquanto o humano não **Validou a Camada 3**.  
3. Uma camada **visível por vez** no viewer (sem modo “ambos” — igual FV).  
4. Cada camada tem **veredito + texto** agêntico independentes.  
5. Packs de **10** pilares.

---

## 2. Tags (fonte única)

→ **`docs/PADRAO-TAGS-DESTAQUE-AGENTICO-PIL.md`**

Resumo: chips multilinha `V.chega BC` / nome / dim / nível; cores A–D;  
pontinho chega = centro da viga; pan/zoom **viewBox**.

O **mesmo** `render_agentic_svg(..., layer=sa|l1|l2|l3)` desenha SA e camadas.

---

## 3. Loop operacional

```
1. export_pilares_abcd_fichas.py
   → HTML + SA_motor (tags) + L1/L2/L3 SVG + notes
2. serve_abcd_fichas.py --dir <pack> --open
3. Humano: toggle 🔴 SA | 🔵 L1 | 🟣 L2 | 🟠 L3
4. Humano valida cada destaque + escreve ATENÇÃO
5. Agente L1: julga SA; se inválido, propõe correção visual
6. Agente L2: recebe desenho de L1 “como se fosse SA” (cego)
7. Agente L3: estabiliza alvo
8. Humano Validou L3 → fix genérico no motor SA
9. Reenrich + re-export → SA motor deve coincidir com L3 → Validou SA
```

---

## 3.1 Método de evidência para Ag.L2 (validado no P16, 2026-08-06)

**Problema real observado:** a Camada 1 costuma escrever o fix certo em texto
(`aten_pil_ctx_agent_l1_*`) mas **não redesenha** o SVG — `L1.svg` fica idêntico ao
`SA.svg` (só o banner muda). Sem redesenho, o humano não tem o que validar
visualmente na Camada 1 — e o item trava.

**O que a Camada 2 deve checar antes de aceitar ou redesenhar, sempre com evidência
dura (nunca heurística de texto sozinha):**

1. Pegue o(s) nome(s) de viga citados na atenção humana ou no texto L1.
2. `sqlite3` em `project_data.vision`, tabela `beams`, `data_json` dessa viga →
   campo `links.viga_fundo_seg_N_area_segs.contour` (cada segmento tem 4 pontos =
   retângulo real do trecho da viga, em coordenadas de projeto).
3. Compare cada contorno com a bbox do pilar (`pillars.points_json`). Um segmento
   cuja largura no contorno **bate exatamente** com a largura/altura da face do
   pilar prova toque **de ponta a ponta** naquela face — evidência de canto
   simultâneo nas duas faces perpendiculares, não suposição.
4. Se o `face_beams` do motor já grava esse padrão de um lado (ex. sul: 3 entradas —
   `D.interior`+`A.passa`+`B.passa`) mas não do lado espelhado (ex. norte: só
   `C.interior`), é **assimetria no builder**, não erro humano — proceda a redesenhar.
5. Redesenhe com o **mesmo** `render_agentic_svg(..., layer="l2")`, alimentado com uma
   cópia de `tables` (`build_abcd_tables_from_pillar`) com as linhas novas adicionadas
   (nunca substituindo as existentes). Grave `{P}_qa_L2.svg` + `{P}_qa_L2_tables.json`.
6. Grave o veredito via `POST /api/notes/{P}` (`aten_pil_ctx_agent_l2_*` +
   `aten_pil_ctx_agent_verdict_l2_*`) — **sempre faça `GET` antes e mescle**: o servidor
   (`serve_abcd_fichas.py`) sobrescreve o arquivo inteiro com o que vier no POST, não
   faz merge sozinho.

**Script de apoio (diagnóstico em lote, não substitui o julgamento):**
`scripts/arete/pil_l2_evidence_check.py --pack <pack> --items P9 P12 ...` — cruza
`face_beams` × contornos reais de todas as vigas citadas e aponta faces/cantos onde
existe toque geométrico sem entrada correspondente. Ainda exige leitura humana/agente
do resultado (o script não redesenha nem decide sozinho).

**Caso completo registrado:** `INSIGHTS-QA-L1.md` §8 do pack
`13_PAV_20260804_155556_pilares_abcd` (viga V322, item P16).

**Rasterização SVG→PNG (resolvido, 2026-08-06):** `cairosvg`/`svglib` seguem
indisponíveis (lib nativa ausente no Windows), mas `PySide6.QtSvg.QSvgRenderer`
(já é dependência do projeto) rasteriza qualquer SVG do pack sem lib externa —
`QSvgRenderer(path)` + `QPainter` sobre `QImage`, escala livre (ex. 10x) para
crop em alta resolução. Caso validado no P9 (13_PAV): permitiu ao agente L1
conferir visualmente o cruzamento de setas SA vs L1 redesenhado sem depender do
Browser pane. Preferir isso a heurística de estrutura (contagem de chips/tamanho
de arquivo) sempre que precisar confirmar posição real de tag/seta antes de
fechar uma camada.

---

## 3.2 Calibração cega do agente QA — refinar até convergir com o humano

**Objetivo:** antes de deixar o agente gerar Camada 2 sozinho em lote, provar que ele
chega **dinamicamente** (sem ler a nota humana) nos mesmos apontamentos que o humano —
não só nos casos fáceis. Script: `scripts/arete/pil_blind_l1_calibration.py`.

```bash
py -3.12 scripts/arete/pil_blind_l1_calibration.py --items P1 P2 ... --reveal --port 18765
```

Roda checagens **determinísticas, sem ler `aten_pil_ctx_human_*`**, forma um veredito
`validou`/`invalidou`, e só DEPOIS busca a nota humana pra comparar (`--reveal`).

| # | Checagem | Pega |
|---|----------|------|
| 1 | `analyze_verdict` (motor) | dualidade AC/CA·BC/CB, banda de topo, C multi-seg |
| 2 | papel duplicado | mesma viga+canto em 2 famílias na mesma face |
| 3 | canto faltante (full-span) | viga encosta numa face inteira sem canto simétrico registrado (caso P16, §3.1) |
| 4 | **vínculo com gap grande** | viga linkada como `passa` mas o contorno real está a mais de 10cm da parede — vínculo suspeito |
| 5 | **candidato melhor** | outra viga encosta bem mais perto da mesma face do que a que está linkada — provável troca de identidade |
| 6 | **rótulo órfão** | face totalmente vazia mas há texto de dimensão (`NN/NNN`) no DXF perto dela — viga não vinculada/extraída |
| 7 | **pilar não retangular** | polígono com mais de 4 cantos reais (colineares removidos) — candidato a pilar em L |

**Histórico de calibração (pack `13_PAV_20260804_155556_pilares_abcd`, 31 itens
revisados pelo humano em 2026-08-07):**
- v1 (checagens 1–3 só): **16/31 (52%)** bateram no veredito SA humano.
- v2 (+ checagens 4–7, cada uma nascida de investigar uma divergência real com
  `beams.data_json.links` + DXF bruto, não de suposição): **28/31 (90%)**.
- Casos que continuam sem convergir (P20, P21, P49): erro de **troca de papel** entre
  passa/chega/interior para a MESMA viga em cantos adjacentes de uma face pesada (C),
  sem gap geométrico grande o suficiente pra disparar a checagem 4 — precisa de
  modelagem semântica mais profunda (não é só distância).

**Regra de ouro do refinamento:** achar uma divergência → investigar a causa raiz real
(consultar `beams.data_json.links`, DXF bruto) → virar checagem determinística nova
→ re-rodar a calibração inteira → só gerar Camada 2 em lote nos itens onde a
calibração bateu. Itens que não convergem ficam para revisão manual (método §3.1,
caso P16) até a próxima rodada de refinamento — **nunca** gerar Camada 2 automática
num item que não convergiu na calibração cega.

---

## 3.3 Travas de integridade da Camada 2 (incidente 2026-08-07)

**O que aconteceu:** a 1ª implementação da L2 (`pil_l2_apply_calibrated_fixes.py`)
chamava `build_abcd_tables_from_pillar(pillar)` — **reconstruindo a tabela do zero a
partir do motor SA** — e nunca abria `{P}_qa_L1_tables.json`. Resultado: cada rodada de
L2 revertia silenciosamente todas as correções da Camada 1 e aplicava seus próprios
checks sobre a leitura errada do SA. **25 dos 28 itens perderam trabalho da L1.**

Diagnóstico humano no P24 (bateu 100% com o log): *"a camada 2 ao invés de só ajustar o
solicitado corrompeu e adicionou outras coisas. removeu o viga interior cc, adicionou
viga chega incorretamente ac, e removeu viga passa ac. isso NÃO DEVE OCORRER — UM AJUSTE
NÃO PODE PIORAR AINDA MAIS A QUALIDADE."*

### As três travas (obrigatórias em qualquer camada N+1)

| # | Trava | Implementação |
|---|-------|---------------|
| **T1** | **Base = camada anterior, NUNCA o SA.** | Carrega `{P}_qa_L1_tables.json`. Se não existir, o item é **pulado** — jamais reconstruir do motor. |
| **T2** | **Gate de não-regressão.** | Antes de gravar: diff de assinatura `(face, família, nome, canto)` entre L1 e L2. Toda linha ausente precisa estar em `justified_removals` (duplicata removida por regra, ou identidade trocada — troca é modificação rastreada, não perda). Qualquer remoção não justificada **aborta o item** sem gravar. |
| **T3** | **Sem correção acionável = não toca no desenho.** | `changes` vazio → grava só a nota de pendência, mantém o SVG da L1. Flag `--repair` existe apenas para regenerar SVGs corrompidos por rodadas antigas. |

**Lição de processo:** o gate T2 pegou 13 abortos na 1ª execução — todos falsos positivos
causados por eu não ter classificado *troca de identidade* como mudança rastreada. Isso é
o comportamento desejado: **o gate falha fechado**. Prefira abortar e investigar a
gravar algo que reduz qualidade.

### Detecção ≠ correção (limite honesto do estado atual)

A calibração cega (§3.2) acerta **90% em detectar quais itens estão errados**. Isso
**não** significa saber qual é a resposta certa. Após o reparo, dos 28 itens:
- **18** receberam correção concreta (canto implicado, duplicata, troca de identidade);
- **10** ficaram com L2 == L1 — o checador não achou nada acionável, embora o humano
  tenha apontado erro real (ex. P24: *"faltou viga passa CB e viga chega BC"*).

Ou seja: a L2 hoje **preserva** e **corrige o que sabe provar**, mas ainda não resolve
sozinha os padrões que exigem leitura semântica (papel trocado passa/chega/interior,
identidade por rótulo do DXF). Não anunciar esses itens como resolvidos.

### Backlog estrutural aberto (pedido humano, sem suporte no modelo atual)

- **Blocklist de geometria reprovada** (P12/P13/P14): persistir vínculos que o humano
  invalidou, para o SA nunca religar a mesma geometria e tentar a próxima mais próxima.
- **Pilar especial em L — 6 faces A–F** (P26/P27): o modelo inteiro assume 4 faces.
  Convenção pedida: A/B seguem a definição atual, C e D continuam sendo as tampas
  (lados curtos), e o trecho horizontal do L acrescenta **E** e **F** como lados longos.

---

## 3.4 Memória de QA — atenção estruturada + blocklist (2026-08-07)

**Descoberta que motiva o desenho:** no 13_PAV, 30 itens tinham atenção escrita mas
apenas **17 textos distintos** — 63% eram repetição do mesmo padrão (5× "faltou viga
chega bb", 4× o padrão do lado D, 3× "geometria vinculada errada", 3× "V310 dimensão
errada"). O humano não estava corrigindo 30 casos, e sim **~6 padrões recorrentes**.

Consequência de arquitetura: o remédio **não** é RAG semântico difuso. A geometria já é
verdade exata no DB (`beams.links.*_area_segs.contour`); busca por similaridade e
pixels são fontes *piores* que coordenadas. Visão serve para **auto-conferência do
desenho** (tags sobrepostas, ponto fora do lugar) — nunca como base para decidir a
interpretação.

### Camada 1 — atenção estruturada (vocabulário controlado)

`scripts/arete/_patch_abcd_struct_atencao.py <pack>` injeta na ficha um formulário
de apontamento. Plugga no autosave existente via `<textarea hidden data-atkey>`
(o `collectNotes()` do chrome já varre esses campos) — **não altera
`src/core/pil_qa_notes_chrome.py`**, que é core compartilhado.

Vocabulário derivado das atenções REAIS (não inventado):

| Ação | Significado |
|------|-------------|
| `falta` / `sobra` | elemento ausente / que não deveria estar |
| `papel_errado` | existe, mas é passa/chega/interior diferente do gravado |
| `identidade_errada` / `dim_errada` | nome da viga errado / dimensão errada |
| `canto_errado` / `duplicado` | posição errada / entrada repetida |
| `geometria_invalida` | vínculo geométrico do pilar reprovado → **vai para a blocklist** |
| `pilar_especial` | precisa mais faces (L: A B C D E F) |
| `desenho` | tag sobreposta / ponto no lugar errado (render, não tabela) |

Campos: face (A–F) · canto (AC…DD) · papel · nome · obs. Chave:
`aten_pil_struct_{obra}_{pav}_{item}` (JSON array).

### Camada 2 — memória consolidada

`scripts/arete/pil_qa_memoria.py build --pack <pack>` gera, **fora do pack** (sobrevive
a re-export) e **sem tocar no schema N1** (regra 1 do CLAUDE.md — side-car, nunca
`pillars.extra_data`):

- `scripts/arete/qa_memoria/blocklist_vinculos.json` — vínculos reprovados. Consulta
  pública `is_blocked(obra, pav, item, nome=, face=, canto=)`; já integrada ao
  `pil_l2_apply_calibrated_fixes.py`, que **nunca propõe um candidato bloqueado** —
  vira pendência explícita em vez de religar o que o humano já reprovou.
  (Pedido humano: P12/P13/P14.)
- `scripts/arete/qa_memoria/dataset_correcoes.jsonl` — todo apontamento + assinatura
  estrutural do item. É o dataset rotulado que calibra as checagens do §3.2.

### Assinatura estrutural — validação da camada de precedente (futura)

`structural_signature()` = `orientação | dims | por face: {família:qtd}`. Agrupando os
46 pilares do 13_PAV, os grupos **reproduzem exatamente** o agrupamento que o humano fez
sozinho ao repetir a mesma atenção:

| Grupo por assinatura | Atenção humana |
|---|---|
| P29,P30,P31,P32 | mesma nota 4× ✔ |
| P12,P13,P14 | mesma nota 3× ✔ |
| P20,P21,P22 | mesma nota 3× ✔ |
| P15,P16 | mesma nota 2× ✔ |
| P43,P45,P47 + P42,P46 | o humano tratou os 5 como um grupo; a assinatura separa em 2 (vertical/horizontal) |

Isso valida empiricamente a camada de precedente: decidir 1 item e propagar a decisão
para o grupo (**sempre exibindo o precedente para confirmação humana**, nunca aplicando
em silêncio). O caso P42/46 vs P43/45/47 mostra que o nível de abstração da assinatura
é uma decisão de produto — não deve ser chutado pelo agente.

---

## 3.5 Apontamento estruturado POR CAMADA + desenho derivado (2026-08-07)

**Correção de rumo:** a 1ª versão do formulário estruturado ficou no lado humano.
Errado — o humano não preenche formulário e isso não pode ser requisito dele. O
apontamento estruturado pertence à **caixa agêntica de cada camada** (L1/L2/L3),
preenchido pelo **agente QA**; a camada seguinte desenha a partir dele **sem
reinterpretar português**. Chaves `aten_pil_struct_l1|l2|l3_{obra}_{pav}_{item}`.

### Pipeline

```
L(n) tabelas  +  aten_pil_struct_l(n)  →  pil_layer_from_struct.py  →  L(n+1) tabelas + SVG
                                                                    ↓
                                              pil_layer_selfcheck.py → veredito do próprio agente
```

- `_patch_abcd_struct_atencao.py <pack>` — injeta o bloco em cada caixa agêntica.
- `pil_layer_from_struct.py --item P24 --base L1 --alvo L3 --struct-layer l2`
  — aplica os apontamentos (mantém T1/T2/T3 do §3.3) e redesenha.
- `pil_layer_selfcheck.py --item P24 --layer L3 --gravar` — o agente confere o
  **próprio** desenho contra a geometria e grava validou/invalidou. Classifica cada
  linha em `OK` (contato medido) · `CONVENCAO` (regra do doc, ex. dualidade) ·
  `SEM_BASE` (sem sustentação → invalida).

### Correção conceitual: ALINHAMENTO, não sobreposição

Dois bugs no predicado geométrico, ambos achados conferindo o P24:

1. gap e extensão eram medidos **separadamente** → uma viga reportava "100% de
   contato na face C" e "gap de 80cm da face C" ao mesmo tempo. Evidência
   contraditória = evidência inútil.
2. **Erro conceitual:** o predicado exigia *sobreposição de polígonos*. O doc
   `INTERPRETACAO-PILARES-ABCD.md` é explícito: *"a classificação é determinada
   pelo **alinhamento geométrico**, não pelo simples toque de polígonos"*.
   Uma viga N–S **colinear** com o pilar (mesma faixa de 19 cm) tem suas paredes
   coincidindo com as faces A e B — ela **passa nos 4 cantos** (AC/AD/BC/BD) ainda
   que o contorno guardado no DB fique inteiramente ao sul do pilar.
   Caso real: V321 × P24 — o agente lia "SEM_BASE"; o humano corrigiu com print.

`pil_geom_contato.py` agora discrimina por **direção de corrida da viga vs direção
da face**: mesma direção + parede colinear + adjacência axial → **passa**;
direção cruzada + encosta + extensão parcial → **chega**.

### Ponto da tag "chega" vem da MEDIÇÃO

`ancorar_por_medicao()` preenche `dist_esq`/`dist_dir` de toda linha `chega` com o
trecho **realmente medido** na face. Assim o pontinho cai no **centro da viga que
chega** (padrão PADRAO-TAGS), não numa fração fixa nem na esquina do pilar.
Verificado no P24: V304 ocupa y 2422–2441; ponto calculado = **2431.5** = centro exato.

### Resultado do teste ponta a ponta (P24)

| Etapa | Resultado |
|---|---|
| L3 desenhada só do estruturado | ✔ aplicou os 3 apontamentos + âncora, sem ler texto livre |
| Bate com o pedido humano | ✔ `+C.passa@CB`, `B@BC passa→chega`, `+B.passa V321@BC`, L1 preservada |
| Auto-avaliação | OK=6 · CONVENCAO=1 · **SEM_BASE=1** → **INVALIDOU** a si mesma |

O `SEM_BASE` restante é `C.interior V321@CC`, herdado da L1: V321 está 80 cm ao sul
da face C, sem sustentação geométrica. Fica para arbitragem humana — o agente **não**
removeu porque a instrução humana no ciclo anterior foi "mantenha todos que estão".

---

## 3.6 Visão como 2ª camada de raciocínio — OBRIGATÓRIA antes de fechar camada

> **Regra:** nenhuma camada agêntica (L1/L2/L3) pode ser dada por concluída sem que o
> agente **rasterize o próprio desenho e o leia**. Número e tabela sozinhos não fecham
> camada — é a mesma regra do `QA-VISAO-EVIDENCIA-CANONICA.md` aplicada ao loop ABCD.

### Por que (motivado por falhas reais, não por teoria)

Cada uma destas passou pelas checagens numéricas e **só caiu quando alguém olhou**:

| Falha | O que a tabela dizia | O que o desenho mostrava |
|---|---|---|
| V321 × P24 | "SEM_BASE em A e B" | a viga é colinear com o pilar — **passa** nos 4 cantos (§3.5) |
| ponto da chega BC | `dist_esq/dist_dir` corretos | ponto colado na parede, sumido no meio de 3 outros pontos |
| tags sobrepostas | nada — não é campo de tabela | ilegível (atenção humana recorrente) |

Ou seja: existe uma classe inteira de erro — **legibilidade e plausibilidade
espacial** — que é invisível para checagem numérica **por construção**.

### As três camadas de raciocínio (cada uma pega o que a anterior não pega)

```
   ┌───────────────────────────────────────────────────────────────┐
   │ 1. GEOMETRIA   — o dado sustenta?                             │
   │    contorno real × bbox do pilar (pil_geom_contato.relacao)   │
   │    → OK / CONVENCAO / SEM_BASE          [pil_layer_selfcheck] │
   └────────────────────────────┬──────────────────────────────────┘
                                │ passou
   ┌────────────────────────────▼──────────────────────────────────┐
   │ 2. VISÃO       — o desenho comunica isso?                     │
   │    rasteriza (QSvgRenderer) + o agente LÊ a imagem            │
   │    → tag no elemento certo? ponto no corpo da viga?           │
   │      sobreposição? leitura bate com a tabela?                 │
   └────────────────────────────┬──────────────────────────────────┘
                                │ passou
   ┌────────────────────────────▼──────────────────────────────────┐
   │ 3. CONTRADIÇÃO — as duas concordam?                           │
   │    divergiu → NÃO decide sozinho: registra apontamento        │
   │    estruturado e devolve para arbitragem humana               │
   └───────────────────────────────────────────────────────────────┘
```

**A camada 3 é a que dá confiança.** Quando geometria e visão discordam, o certo é
**parar**, não escolher. Foi exatamente assim que o erro do V321 apareceu: a geometria
dizia SEM_BASE, o humano olhou e disse "passa" — e quem estava errado era o predicado.
Se o agente tivesse "resolvido" sozinho, teria apagado a leitura certa.

### Como rasterizar (sem depender do Browser pane)

`cairosvg`/`svglib` não funcionam neste ambiente (lib nativa ausente no Windows).
Use `PySide6.QtSvg.QSvgRenderer`, que já é dependência do projeto:

```python
from PySide6.QtGui import QImage, QPainter, QGuiApplication
from PySide6.QtSvg import QSvgRenderer
app = QGuiApplication([])
r = QSvgRenderer(svg_path)
img = QImage(9000, 4166, QImage.Format_ARGB32); img.fill(Qt.black)
p = QPainter(img); p.setRenderHint(QPainter.Antialiasing); r.render(p); p.end()
img.copy(W//2-380, H//2-450, 760, 900).save(png_path)   # o render é centrado no pilar
```

**Truque que funcionou:** para conferir UMA tag, zere as outras famílias da `tables`
e renderize só ela. Com 8 tags juntas é impossível saber de quem é cada ponto; isolada,
o erro salta. Foi assim que o ponto da chega BC foi diagnosticado.

### Checklist de leitura visual (o que o agente procura na imagem)

1. Cada tag aponta para o elemento que ela nomeia?
2. `chega` → o ponto está **dentro do corpo da viga que chega** (não colado na parede,
   não na esquina do pilar)?
3. `passa` → o ponto está na esquina declarada?
4. Alguma tag sobreposta / ilegível / fora da área visível?
5. O que a imagem mostra bate com a tabela — ou apareceu viga/laje que a tabela ignora?

Achou divergência → **apontamento estruturado** (`aten_pil_struct_l*`), não conserto
silencioso.

### Custo

Rasterizar ~2 s por item. Rodar em **todo** item ao fechar camada é barato perto do
custo real: um lote inteiro redesenhado errado (25 itens corrompidos em 2026-08-07,
§3.3) — que teria sido pego na primeira leitura visual.

### ⚠ O contorno do DB pode NÃO bater com o DXF — medir no desenho

**Achado de 2026-08-08 (V304 × P24), encontrado só porque o humano olhou:**

| Fonte | V304 na face B do P24 |
|---|---|
| DXF (linhas reais) | y **2441 → 2460** (centro 2450.5) |
| `beams.links.viga_fundo_seg_1_area_segs` | y **2422 → 2441** (centro 2431.5) |

O contorno guardado no DB está deslocado **exatamente uma largura de viga (19 cm)**.
Ancorar o ponto por ele o colocava **fora** da viga — visível de imediato no desenho,
invisível para qualquer checagem que só leia o DB. Pior: o SA original já trazia
`de=61cm dd=0cm`, que bate com o DXF — a "correção" automática **piorou** um dado
que estava certo.

**Regra:** para posicionar tags/pontos, a ordem de confiança é
**1) linhas do DXF** (`pil_geom_contato.medir_no_dxf`) → **2) contorno do DB** (fallback)
→ **3) fração fixa** (último recurso). O DXF é o que o humano vê; é ele que manda.

**Corolário mais amplo:** `links.*_area_segs` serve para *topologia* (qual viga toca
qual face), **não** para *posicionamento fino*. Onde a diferença de alguns centímetros
importa — ponto de tag, cota, d.esq/d.dir — medir no DXF.

**Nunca sobrescrever `dist_esq`/`dist_dir` já preenchidos pelo SA sem antes conferir
no DXF**: no P24 os valores do SA estavam corretos e foram substituídos por valores
derivados do contorno errado. Hoje `ancorar_por_medicao` **pula** linhas que já têm
medida — só preenche o que está vazio.

### Aferição da medição no DXF (2026-08-10) — 51 chegadas do 13_PAV

Comparando `medir_no_dxf` contra os `d.esq/d.dir` que o SA já calcula:

| Orientação do pilar | SA == DXF | divergem |
|---|---|---|
| **vertical** | 33 | 8 |
| **horizontal** | **0** | **10** |

Duas correções saíram daí:

1. **Convenção de cantos** (`FACE_CORNERS`): a origem da medida é o canto
   *esquerdo* de cada face, e ela **não é sempre a coordenada baixa**. Lendo
   `_beam_seg_on_face` face a face: em pilar **vertical**, A e D contam do extremo
   ALTO (invertem); B e C, do baixo. Em **horizontal**, todas contam do baixo.
   Antes disso a medida saía espelhada e 29 de 51 divergiam.
2. **Horizontal está BLOQUEADO.** Mesmo com a convenção certa, a varredura casa
   paredes de outros elementos e erra o par (ex. P42/46/48/50/51: DXF devolve
   `de=16,dd=15` — centro — onde o SA diz `de=0,dd=31` — canto). Enquanto não
   houver desambiguação por identidade de viga, `ancorar_por_medicao` **não mede
   em pilar horizontal**: melhor sem medida do que com medida errada.

**Regra de processo que isso confirma:** validar em pilar **vertical E horizontal**
antes de propagar qualquer mudança de geometria para lote. A correção do ponto foi
provada no P24 (vertical, n=1) e teria espelhado/deslocado pontos em todos os
horizontais do lote se tivesse ido direto.

---

## 4. Geração (sempre on)

```bash
# Export = SA+tags + L1/L2/L3 (não precisa --with-agentic)
py -3.12 scripts/arete/export_pilares_abcd_fichas.py \
  --project-id <id> --obra Obra_TREINO_1 --pav 13_PAV \
  --item P1 P2 P3 P4 P5 P6 P7 P8 P9 P10

# Re-desenhar só uma camada (looping)
py -3.12 scripts/arete/pil_agentic_highlight_draw.py \
  --pack <pack> --items P2
  # process_item(..., only_layer="l2") via API interna

# Servir
py -3.12 scripts/arete/serve_abcd_fichas.py --dir <pack> --open
```

`--with-agentic` no export é **no-op** (legado).  
`--no-layers` só em caso excepcional (SA tags sem gravar L*).

---

## 5. UI / chaves `aten_pil_*`

```
aten_pil_ctx_human_{obra}_{pav}_{pilar}
aten_pil_ctx_agent_l1|l2|l3_{...}          # texto por camada
aten_pil_ctx_agent_verdict_l1|l2|l3_{...}
aten_pil_hl_sa_human_{...}
aten_pil_hl_l1|l2|l3_human_{...}
# legado L1: aten_pil_ctx_agent_ / aten_pil_hl_agent_human_
```

Código: `src/core/pil_qa_notes_chrome.py` (`pil_keys`, toggle, abas L1/L2/L3).

---

## 6. Artefatos

```
{pack}/
  pilares/{P}.html
  pilares/{P}.notes.json
  propostas/{P}_sa_motor.svg
  propostas/{P}_qa_L1.svg
  propostas/{P}_qa_L2.svg
  propostas/{P}_qa_L3.svg
  propostas/{P}_qa_proposta.svg   # alias L1
  propostas/{P}_qa_proposta.json
```

---

## 7. Critérios de pronto (piloto pack)

- [ ] SA N1 HTML **com tags** sem flag extra  
- [ ] Toggle SA / Camada1 / Camada2 / Camada3 (uma por vez)  
- [ ] 10 pilares com `_sa_motor` + `_qa_L1/L2/L3`  
- [ ] Validadores humanos SA + L1 + L2 + L3  
- [ ] Abas de anotação agêntica por camada  
- [ ] Após L3 Validou → fix motor → re-export → SA Validou  

---

*Atualizado 2026-08 — SA sempre tagged; 3 camadas espelho FV V303.*
