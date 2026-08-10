# Procedimento QA — Fundos de Viga (N1 Contextual Unificado)

**Versão:** 1.1  
**Escopo:** somente **N1 / SA — Contextual unificado** da ficha FV  
**Persona:** QA **chato, extremista, de extrema qualidade**  
**Saída:**  
1. caixa **🤖 Anotação agêntica** (`aten_fv_ctx_agent_{obra}_{pav}_{beam}`)  
2. **desenho de proposta** no SVG/PNG (geometrias corretas sugeridas)  
**Não preencher:** anotação humana (só o revisor)

---

## 1. Objetivo

Validar se a **interpretação N1 de fundos de viga** está correta olhando **apenas** a
evidência visual do **contextual unificado** (viga inteira + destaques de todos os
segmentos S1…Sn + DXF estrutural de fundo).

O QA deve dizer, por viga:

- **CERTO** / **ERRADO** / **PARCIAL** (com rigor — PARCIAL só se a maior parte ok e
  falhas pontuais bem delimitadas; na dúvida, **ERRADO**).
- Quais **segmentos** estão errados (S#).
- **Onde** deveria haver ajuste (motor / interpretador / topologia).
- **Por que** errou (hipótese causal).
- **O que o humano deveria ver** no estrutural vs o que o N1 marcou.

---

## 2. Fontes canônicas (obrigatório ler antes)

| Doc | Uso no veredito |
|------|-----------------|
| `docs/ARQUITETURA-INTERPRETADORES-VIGA-N1-ISOLADOS.md` | Dono FV = `FundoVigaInterpreter` / `seg_bottom`; não misturar LV/PIL |
| `docs/CONTEXTUALIZACAO_VIGAS_SEGMENTOS_FUNDOS.md` | Segmento = trecho entre conflitos; lista SA / campos |
| `src/core/beam_interpreters/fundo_viga.py` | Regras: não unir por proximidade atravessando fronteira física; desduplicar só quase-idênticos; descartar contorno envolvente quando há painéis internos |
| Guia de interpretação de fundos da obra (se existir em `interpretacao_fundos.html` do pack) | Semântica local do projeto |
| Ficha HTML HI-FI | Viewer contextual + tags S# + contornos vermelho/rosa |

**Proibido:** usar N2/N3/N4, ficha tabular, ou “chute” sem evidência no PNG/SVG contextual.

---

## 3. O que é um fundo de viga “certo” no contextual

### 3.1 Continuidade da viga

1. A sequência S1…Sn cobre o **eixo/fundo contínuo** da viga sem buracos óbvios no
   trecho principal.
2. Segmentos **não atravessam** pilares, cruzamentos de viga ou mudanças de painel
   que o desenho mostra como fronteira.
3. **Não** existe um único retângulo laranja/rosa cobrindo vários painéis que o
   estrutural separa (over-merge).
4. **Não** faltam painéis intermediários claros no DXF (under-segmentation).
5. Largura visual dos destaques é coerente com a faixa de fundo (não “barra” gorda
   em laje, não “fio” de cota).

### 3.2 Tags e contornos

1. Cada S# tem contorno **fino** sobre um painel real (vermelho/rosa alternados).
2. Tags ~100 cm acima com líder apontando o centroide — se o líder aponta para o
   vazio ou outro elemento, marcar falha de posicionamento (secundária).
3. Numeração **ordenada** ao longo do eixo (crescente esquerda→direita ou no sentido
   do eixo da viga). Inversão total ou S# “saltando” sem motivo → ERRADO/PARCIAL.

### 3.3 Contexto estrutural

1. Pilares / apoios / vigas transversais visíveis no DXF explicam as **quebras** de
   segmento.
2. Se o DXF mostra encontro e o N1 **não** quebra → under-segmentation.
3. Se o N1 quebra no meio de um painel sem encontro → over-segmentation.
4. Contorno “fantasma” fora da viga (laje, cota, outra viga) → contaminação / motor
   geométrico.

### 3.4 Dono do erro (apontar sempre)

| Sintoma | Dono provável |
|---------|----------------|
| Quebras erradas / merge de painéis / envolvente | `FundoVigaInterpreter` (FV) |
| Geometria bruta torta, intervalo/eixo errado | `BeamTracer` / topologia compartilhada |
| Destaque em elemento que não é fundo | classificador / link `viga_fundo_seg_*_area_segs` |
| Tag no lugar errado mas painel ok | apenas ficha/UI (baixo) |

### 3.5 Convenção de pilares, cruzamento por profundidade e leitura do fundo estrutural

**Origem:** achados humanos reais no piloto (V302/V303/V304, 2026-08) — o looping
cego anterior (camadas 1→2→3) julgava só a partir de retângulos/coordenadas
isolados, sem o fundo DXF real (pilares, vigas vizinhas, cotas) na imagem que o
agente via. Corrigido: a evidência agora é o **mesmo PNG HI-FI** que a ficha
mostra (pilares P#, vigas L#/V#, cotas). Estas regras exploram essa evidência.

> 💡 **INSIGHT — pilar é sólido.** Um pilar rotulado (`P#`) que o eixo do fundo
> atravessa é **sempre** um limite físico real. O fundo da viga **nunca** passa
> "por cima"/atravessando um pilar sem quebra. Se o desenho mostra um `P#` sobre
> o eixo do segmento e o N1 não quebra ali → **under-segmentation certa**, não
> "talvez". Não é preciso mais contexto para decidir isso — pilar visível e
> centrado no eixo = quebra obrigatória.

> 💡 **INSIGHT — cruzamento de vigas depende de profundidade, não só de gap.**
> Duas vigas que se cruzam (ambas com fundo) só quebram o fundo *da mais rasa*
> no cruzamento; o fundo *mais profundo* **atravessa contínuo por baixo** — não
> há segmentação nesse ponto para a viga mais funda. Antes de assumir que um gap
> ou uma viga transversal rotulada (`V###`/`L###`) é um "conflito" que quebra o
> segmento, pergunte: **qual das duas é mais profunda aqui?** Se a evidência não
> traz cota de nível/altura que resolva isso, **não presuma quebra automática só
> por existir uma viga cruzando** — registre como achado de confiança **média**
> e peça a informação de profundidade (não é alucinação dizer "não decidível sem
> nível"; é alucinação inventar uma quebra ou uma continuidade sem essa base).
> Ver `docs/QA-PERFIS-CLASSES-SA-N1-N3.md` (conceito análogo PARA/PASSA em PIL:
> "viga mais profunda… neutralização").

> 💡 **INSIGHT — o segmento tem que sentar EXATAMENTE sobre o eixo rotulado da
> própria viga.** A ficha rotula a viga em análise perto da sua faixa (ex.
> `V303` à esquerda, ~mesma altura Y do eixo). Compare a faixa Y do destaque
> S#/P# com a faixa Y da linha de eixo rotulada com o **nome da própria viga**.
> Se os destaques estão alinhados com a faixa de **outra** viga vizinha (uma
> linha de eixo diferente, um "andar" acima ou abaixo no desenho) → **defeito de
> posicionamento em Y**, dono provável `BeamTracer`/topologia compartilhada,
> **não** um problema de segmentação. Isso é visualmente checável: se o destaque
> vermelho/rosa não toca a linha de cota/eixo da viga com o nome certo ao lado,
> é ERRADO — mesmo que a contagem de segmentos pareça razoável.

> 💡 **INSIGHT — slivers finos na borda de vazio/hachura são contaminação, não
> painel.** Segmentos muito curtos (largura « dos vizinhos) posicionados exatamente
> na borda de uma região hachurada (vazio de laje, parede, "VER DET.") são
> tipicamente artefatos do classificador pegando um fragmento de contorno que não
> é fundo real. Sintoma: um segmento "normal" de ~100–400 cm ladeado por um
> segmento de ~10–30 cm colado numa hachura. Tratar como contaminação (dono:
> classificador / link), sugerir remoção, não “preencher gap”.

> 💡 **INSIGHT — segmentos não precisam ser retângulos.** Se a viga faz canto,
> chanfro ou dobra, o painel de fundo correspondente é naturalmente um polígono
> em L (ou trapézio) — não force um retângulo quando o próprio traçado
> estrutural (linhas do DXF de fundo) mostra um canto. Um S# "faltando" um
> pedaço em L pode, na verdade, estar certo — verifique contra as linhas do
> fundo real antes de marcar como erro.

**Resumo operacional (aplicar nesta ordem):**
1. Pilar centrado no eixo sem quebra → ERRADO (under-segmentation), sem exceção.
2. Viga cruzando **mais funda** (≥1,5× altura de seção) que atinge fisicamente
   esta faixa → a mais rasa **deve** quebrar; a mais funda **não**. Se a
   profundidade não está legível na cota `LARG/ALT` → não adivinhar; confiança
   média.
3. Y do destaque não bate com o eixo da viga rotulada com o nome certo → ERRADO
   (dono BeamTracer / reancoragem de faces), independente da contagem de segmentos.
4. Segmento muito curto colado em hachura/vazio → suspeito de contaminação.
5. Formato não-retangular pode ser correto — comparar com as linhas reais antes
   de "corrigir" para um retângulo.
6. **Viga vertical:** tags S#/P# devem ficar **à esquerda e menores**; se a tag
   cobre o fundo, é falha de ficha (baixa), não de topologia.
7. **Viewer:** recorte contextual é **quadrado** (lado = maior dimensão + pad);
   zoom inicial 2× mais próximo. Não julgar “falta de contexto” só porque o
   frame antigo era uma faixa preta retangular.

> 💡 **INSIGHT (2026-08, pós-atenções humanas V302/V304/V308/V309):**
> - **V302:** S1–S4 ok; over-merge em vão longo onde cruzam V320/V322 (mais
>   fundas 19/120 vs 19/55) e trecho final invade cruzamento/pilar — motor deve
>   materializar 3+2 painéis nessas zonas via
>   `split_bottom_spans_at_deeper_crossings` (agora ligado no headless + repair).
> - **Marco Y/X:** se o destaque “desce” ou “anda para a esquerda” em relação às
>   linhas verdes do fundo, dono = reancoragem transversal (faces DXF), não
>   inventar offset hardcoded por viga.
> - **N3 no mesmo viewer:** aba **N3** ao lado de C3 mostra o robô SA; use para
>   comparar SA×N3 dinamicamente, **sem** copiar N3 como gabarito de C1/C2.

---

## 4. Pipeline CLI / chat (ordem fixa)

### 4.1 Pré-requisitos

```text
# Servidor de notas + fichas (grava .notes.json no disco)
python scripts/arete/tmp/fv_notes_server.py
# → http://127.0.0.1:8765/fundos_viga/{BEAM}.html
```

Pack HI-FI de referência:
`scripts/arete/html_fichas/Obra_TREINO_1/..._fundos_viga_hifi/`

### 4.2 Export visual do contextual (sem abrir o browser)

```text
python scripts/arete/tmp/qa_fv_n1_contextual_pipeline.py export --limit 10
# saída: scripts/arete/relatorios/qa_fv_n1_ctx_{ts}/
#   {BEAM}_n1_ctx.png  + manifest.json
```

### 4.3 Análise (agente / CLI vision)

Para **cada** viga do manifest:

1. Abrir o PNG `{BEAM}_n1_ctx.png` com visão.
2. Aplicar checklist §3 (extremista: na dúvida, ERRADO).
3. Preencher o template §5.
4. Gravar na anotação agêntica:

```text
python scripts/arete/tmp/qa_fv_n1_contextual_pipeline.py write-agent \
  --beam V301 --verdict validou --file comentario.md
# ou --verdict invalidou --text "..."
```

**Radio na ficha (seleção única, obrigatório):**

| Opção | Texto obrigatório |
|-------|-------------------|
| **Agente validou** | Compreensão do contextual + por que validou |
| **Agente invalidou** | Comentários de falha (S#, causa, dono, ajuste) |

Chaves em `.notes.json`:
- texto: `aten_fv_ctx_agent_{obra}_{pav}_{beam}`
- radio: `aten_fv_ctx_agent_verdict_{obra}_{pav}_{beam}` = `validou` \| `invalidou`

### 4.3.1 Capacidade de desenho — proposta de correção no SVG

Quando o veredito for **ERRADO** ou **PARCIAL**, o QA **deve** (sempre que
conseguir inferir geometria) **desenhar a correção** sobre o mesmo espaço do
N1 contextual:

| Camada | Cor | Significado |
|--------|-----|-------------|
| N1 atual | vermelho/rosa **fraco** (opacidade baixa) | o que o motor marcou |
| Proposta QA | **ciano** `#00e5ff` / **verde claro** `#69f0ae` (alternados) | geometria correta sugerida |
| Tags | `P1…Pn` (não `S#`) + líder | cada painel proposto |

**Módulo:** `src/ui/widgets/fv_qa_proposal_draw.py`  
**CLI:**

```text
# 1) Escrever JSON da proposta (pontos CAD iguais ao DXF / N1)
#    { "beam":"V301", "proposed":[ {"label":"1","points":[[x,y],...],"note":"..."}, ... ] }

python scripts/arete/tmp/qa_fv_n1_contextual_pipeline.py propose-draw \
  --beam V301 \
  --json path/to/V301_proposta.json

# Saída:
#   {out}/V301_qa_proposta.svg
#   {out}/V301_qa_proposta.png
#   {out}/V301_qa_proposta.json
```

**Regras do desenho**

1. Cada `proposed[]` é um polígono fechado (ou retângulo de 4 cantos) em **coordenadas CAD**.
2. Labels numéricos viram `P1…`; não reutilizar `S#` (S = motor; P = proposta).
3. Alternância ciano/verde por índice (ímpar/par).
4. Incluir `note` curta no JSON se o trecho for especial (L, chanfro, encontro).
5. Referenciar o path do SVG/PNG no final da anotação agêntica (§5).
6. Se não der para propor geometria com segurança: texto-only +
   `desenho: NÃO PRODUZIDO — motivo`.
7. `propose-draw` **instala** o SVG em `fundos_viga/propostas/{BEAM}_qa_proposta.svg`
   para o toggle da ficha HTML.

### 4.3.2 Toggle na ficha (humano compara)

No contextual da ficha HTML há três botões:

| Botão | O que mostra |
|-------|----------------|
| **Destaque SA** | só N1 motor (vermelho/rosa) |
| **C1 / C2 / C3** | propostas agênticas (ciano/verde `P#`) por etapa |

Assim o revisor alterna e vê a diferença sem sair da página.
URL: `http://127.0.0.1:8765/fundos_viga/{BEAM}.html`

**Contrato mínimo do JSON de proposta**

```json
{
  "beam": "V301",
  "proposed": [
    {
      "label": "1",
      "points": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]],
      "note": "quebra no pilar P9"
    }
  ]
}
```



### 4.3.3 Loop dinâmico: destaque agêntico → motor SA

O **Destaque agêntico** (ciano/verde P#) é a superfície de correção **rápida**:
não passa pelo motor. O **Destaque SA** (vermelho/rosa S#) vem do interpretador.

1. Revisor escreve **atenção** na anotação humana (o que está errado no visual).
2. Agente **refatora o destaque agêntico** (proposta SVG) até o revisor marcar
   **Validou** no validador humano «Destaque agêntico».
3. Só então o revisor pode pedir: **alinhar o motor SA** para produzir o mesmo
   resultado geométrico do agêntico validado.
4. Validador humano «Destaque SA» marca se o motor já bate (ou ainda não).

**Validadores humanos** (acima da anotação humana, seleção única cada):

| Controle | Chave `.notes.json` | Significado |
|----------|---------------------|-------------|
| Destaque SA · Validou/Invalidou | `aten_fv_hl_sa_human_{obra}_{pav}_{beam}` | revisor julga o motor |
| Destaque agêntico · Validou/Invalidou | `aten_fv_hl_agent_human_{obra}_{pav}_{beam}` | revisor julga a proposta |

Independente do radio **Agente validou/invalidou** (veredito do QA automático).


### 4.3.4 Looping de camadas (contrato claro)

```
SA (motor)  ──julgado por──►  Agente 1  ──se X gera──►  C1 (desenho)
                                                      │
                               se A1 = Certo: para (ou humano pede refin)
                                                      ▼
C1 (como se fosse SA, cego) ──► Agente 2 ──se X gera──► C2
                                                      │
                               se A2 = Certo: para
                                                      ▼
C2 invalidada ──► gera C3 (só sugestão final, SEM veredito agêntico)
                  humano valida C3 no selo H da aba C3
```

| Etapa | O que o agente **julga** | Veredito | Saída visual |
|-------|---------------------------|----------|-------------|
| **Agente 1** | **SA** (motor) | A1 Certo / A1 X | se X → `*_qa_proposta_c1.svg` |
| **Agente 2** | **C1** (cego, disfarçada de SA) | A2 Certo / A2 X | se X → `*_qa_proposta_c2.svg` |
| **C3** | — (não julga) | **sem** radio agêntico | `*_qa_proposta_c3.svg` só geração |

**Selos nas abas SA | C1 | C2 | C3:**

| Aba | Selo humano | Selo agêntico |
|-----|-------------|---------------|
| SA | H✓ / H✗ (humano no motor) | — |
| C1 | H✓ / H✗ (humano na proposta C1) | **A1 Certo** / **A1 X** (A1 julgou o SA) |
| C2 | H✓ / H✗ (humano na proposta C2) | **A2 Certo** / **A2 X** (A2 julgou a C1) |
| C3 | H✓ / H✗ (humano na sugestão final) | — (não há A3) |

Chaves agent:
- A1: `aten_fv_ctx_agent_c1_*` + `aten_fv_ctx_agent_verdict_c1_*`
- A2: `aten_fv_ctx_agent_c2_*` + `aten_fv_ctx_agent_verdict_c2_*`
- C3 texto: `aten_fv_ctx_agent_c3_*` (sem verdict)

**Não** interpretar o selo A1 como “agente validou a própria C1” — A1 valida o **SA**
e a C1 é a **consequência** geométrica.

### 4.4 Verificação humana

1. Abrir `http://127.0.0.1:8765/fundos_viga/{BEAM}.html`
2. Ler caixa **🤖 Anotação agêntica**
3. Comparar com a caixa **✏️ Anotação humana** (se houver)
4. Julgar eficiência crítica do QA

### 4.5 Escala inicial

- **Piloto:** 10 vigas (complexidade mista — multi-seg + simples).
- Depois: pack inteiro (36).

---

## 5. Template obrigatório da anotação agêntica

```text
## QA FV N1-CTX | {BEAM} | {YYYY-MM-DD}
VEREDITO: CERTO | PARCIAL | ERRADO
CONFIANÇA: alta | média | baixa

### Resumo (1–2 linhas)
...

### Segmentos
- Total tags vistas: N
- OK: S…
- FALHA: S… → motivo curto

### Achados (lista, do pior ao menor)
1. [SEVERIDADE: crítica|alta|média|baixa] …
   Evidência visual: …
   Segmentos: S…
   Dono provável: FundoVigaInterpreter | BeamTracer | link/classificador | UI
   Ajuste sugerido: …

### Por que o motor errou (hipótese)
…

### O que deveria ser
- Quantidade esperada de painéis (se inferível): …
- Onde quebrar / unir: …

### Não analisado / limite do contextual
(ex.: cota ilegível, zoom insuficiente — NÃO inventar)

### Desenho de proposta QA
- SVG: `.../{BEAM}_qa_proposta.svg`
- PNG: `.../{BEAM}_qa_proposta.png`
- JSON: `.../{BEAM}_qa_proposta.json`
- Cores: ciano `#00e5ff` / verde claro `#69f0ae` (P1…Pn); vermelho fraco = N1 atual
- Se sem desenho: `NÃO PRODUZIDO — {motivo}`
```

---

## 6. Critérios de severidade

| Severidade | Exemplos |
|------------|----------|
| **crítica** | Fundo inteiro em 1 segmento indevido; segmentos em outra viga/laje |
| **alta** | Merge de 2+ painéis com encontro claro; buraco de painel no eixo |
| **média** | Over-segmentation sem encontro; ordem S# confusa |
| **baixa** | Tag desalinhada; líder; estética |

Uma **crítica** ou **≥2 altas** ⇒ **ERRADO**.  
Uma alta isolada com resto impecável ⇒ **PARCIAL**.  
Zero achados materiais ⇒ **CERTO** (ainda assim listar “checagens ok”).

---

## 7. Anti-alucinação

1. Só afirmar o que o PNG/SVG mostra.
2. Não “corrigir” com base em N2/N4.
3. Não inventar contagem de pilares sem enxergar.
4. Se a imagem estiver ilegível: `VEREDITO: ERRADO` com motivo
   `evidência contextual insuficiente` e pedir re-export.
5. Não presumir **profundidade/nível** de viga (qual é mais funda num cruzamento)
   sem dado explícito na evidência (cota de nível/altura). Marcar achado como
   confiança **média** e registrar a limitação (§3.5) em vez de adivinhar quebra
   ou continuidade.
6. **Exigir fundo estrutural real na evidência.** Se o PNG mostrar só
   retângulos/tags em fundo preto (sem linhas de pilar, cotas, nomes de viga
   vizinha), a evidência está degradada — não julgar pilares/cruzamentos com ela;
   pedir re-render HI-FI (`render_fv_hifi_n1_svg(..., also_png_path=...)`, PNG
   direto do matplotlib — **nunca** SVG→cairosvg, que já se mostrou capaz de
   descartar o fundo silenciosamente mantendo só os polígonos de destaque).

---

## 8. Comandos de apoio

```text
# listar notas agênticas já gravadas
python scripts/arete/tmp/_fv_notes_agent.py list

# ver uma viga
python scripts/arete/tmp/_fv_notes_agent.py show V301

# pipeline export + (opcional) só lista de chaves agent
python scripts/arete/tmp/qa_fv_n1_contextual_pipeline.py export --limit 10
python scripts/arete/tmp/qa_fv_n1_contextual_pipeline.py keys --beam V301
```

---

## 9. Definição de pronto (piloto 10 vigas)

- [ ] 10 PNG contextuais exportados  
- [ ] 10 anotações agênticas no padrão §5  
- [ ] Cada uma com VEREDITO + segmentos + dono do erro  
- [ ] Humano consegue abrir a ficha e ler o box azul sem reabrir chat  
