# ARETE — Procedimento Geral de Looping por Classe (Fichas HTML + Diagnóstico Duplo)

**Versão:** 1.2
**Data:** 2026-07-10
**Status:** CANÔNICO — este é o procedimento que deve ser seguido em todo looping de
classe (PIL, FV, LV, LAJ, e qualquer classe futura), a partir de agora.
**Por que este doc existe:** `LOOPING-EVOLUCAO-N2-VISAO-FICHA.md` (28/06) e
`MASTERPLAN-LOOP-TREINO-MOTOR.md` (20/06) descrevem o loop em termos abstratos (vision +
motor + humano, infra em `transformation_rules`/`training_events`) e ficaram desatualizados
depois que o sistema de **fichas HTML headless + Playwright + triagem por checkbox** foi
construído (01–02/07). Este doc substitui a parte "como executar" dos dois anteriores.
Eles continuam válidos como **histórico de decisões e registro de progresso** (não apagar),
mas o caminho de execução daqui pra frente é o descrito aqui.

> **Integração futura com dados:** o contrato entre este procedimento, MCP, SQLite e RAG
> está em `ARETE-MCP-RAG-HARMONIZACAO.md`. Esse contrato não ativa ingestão; define tiers,
> gates e proveniência para uma ativação futura segura.
>
> **Papel oficial do QA:** `MASTERPLAN-AGENTE-QA-GLOBAL.md` e
> `CONTRATO-QA-RAG-LOOPINGS.md` definem o Agente QA Global como auditor e executor
> assistido deste loop: ele observa, evidencia, propõe/refina causa de motor,
> reverifica e só recebe autoridade progressiva para confirmar campos/vínculos.

LAJ é a classe piloto (é onde este caminho foi validado pela primeira vez, em 02/07). Tudo
abaixo é escrito para ser **genérico por classe** — quando for a vez de PIL/FV/LV, o
caminho é o mesmo; a seção 6 lista o que falta construir em cada classe para chegar na
paridade de infraestrutura que LAJ já tem hoje.

---

## 0. Visão geral do ciclo

```
1. GERAR       → headless_sa_analise.py produz fichas HTML N1/N2/N3/N4 por item
2. DIAGNOSTICAR (DUPLO, em paralelo, sem um bloquear o outro):
   2A. Automático (Claude/agente)  → lê números (N1 vs N2) e/ou screenshots, grava no log
   2B. Humano (dono)               → checkbox na ficha HTML, grava no log via qa_error_review.py
3. RECONCILIAR → mesmo item, duas fontes → concorda? diverge? humano tem peso maior sempre
4. CORRIGIR    → causa-raiz no motor/gerador (nunca na ficha, nunca hardcode por item)
5. REVERIFICAR → regenerar (passo 1) + reler os dois diagnósticos (passo 2) no mesmo item
6. FECHAR      → status = verificado; só então repetir para o próximo lote/causa
```

### 0.1 — Agente QA: executor assistido, não atalho de selo

O Agente QA Global é a camada operacional que conecta os passos acima. Ele não
substitui o dono, o gate visual ou os motores; torna o ciclo rastreável e aprende
com a repetição:

```text
observação read-only
  → dossiê por item/campo/vínculo
  → achado + hipótese de causa geral
  → refinamento do motor por um executor
  → microciclo canônico + leitura visual
  → comparação antes/depois e score de confiança
  → [autoridade comprovada] confirmação humana assistida de campo/vínculo
  → candidato T1/T2 para o RAG
```

Em observação, o QA pode abrir achado, gerar prompt de correção universal e
orquestrar a reverificação; não pode editar N2/Fase-4, inventar geometria ou
selar campo. A autoridade é por **classe + família de campo + evidência**, nunca
por número global de acertos:

| Nível QA | Pode fazer | Pré-requisito |
|---|---|---|
| Q0 Observação | ler fontes, pontuar, perguntar, propor fix e rodar microciclo | escopo explícito |
| Q1 Evidência | confirmar em relatório read-only | cadeia CAD/ficha/coord. sem conflito |
| Q2 Assistência humana | preparar `apply` de confirmações high; humano revisa/autoriza | golden + N1-V da família + decisões estáveis |
| Q3 Autoridade progressiva | aplicar somente allowlist da classe | contrato de proveniência, regressão, RAG T1/T2 citado e aprovação humana prévia |

`Q3` não elimina o dono como juiz final. Um conflito novo, queda de score, mudança
de motor, outra obra/pavimento ou ausência de evidência rebaixa o caso para Q0/Q1.
O contrato QA↔RAG está em `CONTRATO-QA-RAG-LOOPINGS.md`.

Ativação reutilizável: `$qa-global-evidencias` no Codex ou
`/CAD:QAGlobalEvidencias-AIOS` no AIOS. A implementação está em
`squads/qa-global-evidencias/`; ela formaliza o roteamento e os gates, mas não substitui
nenhum script canônico descrito neste procedimento.

O ponto central pedido pelo dono (02/07): **os dois diagnósticos convivem, sempre.** O
automático não é descartado quando o humano discorda — a divergência em si é o dado mais
valioso, porque é como se mede, ao longo do tempo, se o diagnóstico automático está
ajudando ou alucinando. O humano vence a decisão de fix; o automático constrói seu próprio
histórico de acerto para, no futuro, justificar mais autonomia.

### 0.1 — Relação com os gates canônicos G0–G6

Este procedimento define **como executar e diagnosticar**. O significado de PASS e a
nomenclatura pertencem ao `MASTERPLAN-ARETE-QUALITY-GATES.md`:

```text
G0 Sanidade do gabarito
  → G1 Round-trip N2 → N4 → N2'
  → G2 Paridade canônica N4 × recorte N2 (numérico — ver nota abaixo)
  → G2-V Veredito visual: render N2 (humano) × N4 (robô), lido/renderizado ← NÃO PULAR
  → G6 Golden set/regressão

G3 UI/persistência é transversal.

G4 Convergência N1 × N2 (numérico — categorização (c)/(d) exige referência checável)
  → G5 Paridade N3 × N4 — RODA de verdade (G2 + G2-V na amostra), não "por construção"
  → G6 Golden set/regressão
```

> **G2 sozinho NÃO autoriza G6 (decisão do dono, 03/07 — `docs/LOOPING-CANONICO.md` §1.5
> e `MASTERPLAN-ARETE-QUALITY-GATES.md` §4).** G2 é matemática semântica (contagens,
> valores) — cego para cota em cima de texto, painel torto, sobreposição. "100% PASS"
> sem G2-V (veredito visual registrado, não só "olhei depois") é candidato, não golden.
> **G2-V compara sempre o mesmo par: recorte N2 (humano) × DXF N4 (robô).** Primeira
> selagem de classe/pavimento = varredura visual de 100% dos itens; re-selagem pós-fix =
> 100% dos itens tocados + amostra de 20% dos demais.
>
> **G5 não é mais "por construção" (fix 03/07 — `MASTERPLAN-ARETE-QUALITY-GATES.md`
> §4, gate G5).** A redação antiga assumia G5 PASS automaticamente de G4 PASS, sem rodar
> nada — pior que o problema do G2 (nem o numérico rodava). Agora G5 exige rodar o
> harness G2+G2-V de fato entre N3 e N4 numa amostra (100% na primeira vez que a
> classe/pavimento atinge G4; 20% depois).

**Escopo atual:** as fichas e a triagem já ajudam a investigar qualquer card N1–N4, mas
o fechamento do robô reverso ocorre primeiro em G0/G1/G2/G2-V. N4 não é gabarito visual
antes de G1/G2 PASS. G5 só é válido depois de N4 certificado em G1/G2/G2-V e da conversão
N1 passar G4. O aprendizado de recorte é um trilho CROP separado e não recebe novo número
G0–G6.

---

## 0.1 — Selecionar o microciclo pela camada alterada

O headless canônico é obrigatório para refinar **N1**, pois a interpretação e
os vínculos dependem do contexto estrutural completo. Ele não deve ser usado
para uma alteração restrita ao desenho N3/N4, que já recebe uma ficha/payload
estável e não precisa reconstruir o SA.

1. **Hipótese de campo/vínculo persistido:** rode `qa_n1_field_probe.py` com
   somente os campos necessários. Ele pode cruzar classes e testar overlay sem
   persistir; o resultado vale apenas para os checks declarados.
   Se a hipótese já consta no perfil da classe, use `qa_profile_probe.py` com
   escopo explícito. O exemplo do perfil nunca seleciona projeto implicitamente.
2. **Cobertura do item persistido:** rode o Agente QA Global em `review`; é
   read-only e responde em segundos. Serve para inventário e proveniência do DB.
3. **Contrato puro:** rode testes unitários contrato→payload, incluindo slots,
   vazios, espelhamento e neutralização. Não abra Qt nem DB.
4. **Motor visual N3/N4:** gere somente o item com o CLI da classe e publique
   primeiro o smoke com `qa_n3_smoke.py`, depois uma ficha com
   `ficha_motor_item.py`. Use `qa_artifact_parity.py` para campos
   declarados e compare o SVG/PNG; a paridade não substitui o veredito visual.
5. **Extrator/interpretação N1:** rode `headless_sa_analise.py --secao --item
   --wait`; somente essa camada requer reconstrução contextual do pavimento.
6. **Fechamento:** regressão completa e gate visual continuam obrigatórios.

Exemplo de ficha visual focada, válido para PIL/LAJ/FV/LV:

```bash
python scripts/arete/ficha_motor_item.py \
  --classe PIL --item P35 --nivel N3 \
  --artefato PARA=D:/.../para/PL_ABCD_preview_P35.dxf \
  --json PARA=D:/.../para/P35.json \
  --contract PARA=D:/.../para/P35_contract.json \
  --artefato PASSA=D:/.../passa/PL_ABCD_preview_P35.dxf \
  --json PASSA=D:/.../passa/P35.json --open
```

Essa ficha não altera o DB, não disputa a trava headless e não pode receber
veredito de N1. Seu manifesto contém hashes para provar que o JSON mostrado é o
mesmo artefato que foi revisado.

O cache local de render/probe é regenerável e só reutiliza resultado quando
versão do motor e hashes de todas as entradas coincidem. Ele reduz iteração, não
eleva autoridade nem dispensa regressão. Ver
`docs/QA-FASTPATHS-CAMPOS-ARTEFATOS.md`.
Para a semântica de PIL/LAJ/FV/LV, ler também
`docs/QA-PERFIS-CLASSES-SA-N1-N3.md`.

## 1. Passo 1 — Geração headless (N1 contextual, pronto para qualquer classe)

```bash
# Rodada completa (certificação/regressão do pavimento)
C:/Users/Thierry/AppData/Local/Programs/Python/Python312/python.exe \
    scripts/arete/headless_sa_analise.py --obra {OBRA} --pav {PAV} --wait

# Microciclo N1: um item ou conjunto de itens de uma única seção
C:/Users/Thierry/AppData/Local/Programs/Python/Python312/python.exe \
    scripts/arete/headless_sa_analise.py \
    --obra {OBRA} --pav {PAV} --secao lajes --item L318 L319 L326 --wait
```

Produz `scripts/arete/html_fichas/{OBRA}/{RUN}/{secao}/{item}.html` para
`pilares/`, `lajes/`, `fundos_viga/` e `laterais_viga/`. Cada ficha empilha 4
`.evidence-card`: N1 (Structural Analyzer), N2 (recorte humano/STOG), N3 (robô via N1),
N4 (robô via N2).

### 1.1 — Microciclo N1 localizado: investigar → corrigir → reverificar

Use `--secao` e `--item` quando a triagem, o diagnóstico ou a leitura visual já isolou a
causa em um item ou em um pequeno conjunto. `--item` aceita nomes separados por espaço ou
vírgula e **exige** `--secao` (`pilares`, `lajes`, `fundos_viga`, `laterais_viga`). Assim a
rodada entrega somente as fichas HTML e os diagnósticos daqueles itens, tornando o ciclo de
evolução do motor mais rápido sem mudar o caminho de produção.

O recorte não é um atalho sem contexto: o `headless_sa_analise.py` continua executando a
análise SA completa, reparos e consolidação usuais; filtra apenas a materialização para
ficha/diagnóstico/persistência. Portanto, o resultado do item percorre a mesma cadeia da
rodada completa. Sempre usar `--wait`: há uma única fila headless e nunca se encerra quem
está com a trava.

#### Protocolo por causa

1. Escolher os itens que compartilham a mesma hipótese de causa-raiz no JSONL de triagem.
2. Rodar o microciclo com `--secao` e todos os `--item` relevantes.
3. Ler a ficha HTML e o diagnóstico filtrado; para N1×N2, revisar com o dono a ficha N1
   convertida contra a ficha N2, campo a campo. Número, bbox ou área isoladamente não fecham
   a interpretação. `g2v_harness.py --par n1xn2 --backend cli` só é admissível se seus dois
   cards forem as fichas comparáveis; geometria bruta do SA contra recorte N2 é inconclusiva,
   não é PASS nem FAIL.
4. Corrigir a regra geral do motor/extrator, nunca os nomes daqueles itens.
5. Repetir o microciclo e a leitura visual até a causa desaparecer; gravar a transição no
   log de triagem em append-only.
6. Antes de chamar o lote de resolvido, rodar a regressão proporcional: mudança em motor ou
   extrator compartilhado exige headless completo, comparação dos quatro diagnósticos e os
   gates visuais aplicáveis. A certificação final continua sendo a rodada completa.

`--persist-db` é opcional e só é permitido no microciclo junto de `--secao --item`; ele faz
upsert dos itens pedidos e preserva todos os registros não selecionados. Nunca usar o
microciclo para apagar ausentes, reescrever JSON Fase-4 ou substituir o golden/regressão.

---

## 2. Passo 2A — Diagnóstico automático (Claude)

### 2A.1 — O que já existe (hoje, só em LAJ)

`main.py` tem uma rotina de dump (~L14060-14204) que compara `self.slabs_found` (estado
carregado na UI) contra o N2 (`projects_repo/{project_id}/laje_data/obras.json`) e escreve
`debug_slab_pav13.json` com, por item: `polygon_dims` (detectado), `n2_comparison`
(`comprimento_n2`/`largura_n2`/`dim_delta`/`match_quality` em EXCELENTE/BOM/REGULAR/RUIM).

**Limitações conhecidas desta implementação (a resolver antes de generalizar, ver §6):**
- Depende do estado da UI (`self.slabs_found`) — não roda headless, não é reprodutível por
  linha de comando isolada.
- Nome de arquivo fixo `debug_slab_pav13.json` — não versiona por obra/pavimento/run, um
  rodada sobrescreve a anterior.
- Só compara dimensão (comprimento×largura) — não sabe distinguir *por que* a dimensão
  está errada (ex.: não diferencia "laje invadiu viga vizinha" de "laje invadiu outra
  laje" de "erro de escala"). Essa distinção é exatamente o que o humano identifica melhor
  hoje (ver caso real abaixo).
- Só existe para LAJ.

### 2A.2 — O que o diagnóstico automático deve produzir, por causa

Independente da fonte (número cru do JSON de debug, ou leitura de screenshot via
`playwright_loop.py` + visão do próprio Claude), a saída deve ter uma entrada por
`item + causa_raiz`, na **mesma forma** do diagnóstico humano (§3), com
`marcado_por: "auto"`. Um item pode gerar vários achados independentes:

- `causa_raiz`: um slug técnico, escolhido a partir do vocabulário já em uso no log (ex.:
  `n1_overlap_viga`, `n1_overlap_laje`, `n3_geometria_complexa_e_cotagem_n4`,
  `schema_gap`, `extractor_bug`) — reaproveitar taxonomia existente antes de inventar slug
  novo.
- `causa_descricao`: uma frase, igual ao padrão humano.
- `confianca`: 0.0–1.0 — obrigatório no automático (não existe no humano, que é sempre
  definitivo). Baixa confiança (ex. <0.5) deve ser tratada como "levanta suspeita, não
  decide" — não dispara fix sozinho.
- `evidencia`: os números/observações que embasaram o diagnóstico (ex.:
  `{"dim_delta": 0.1821, "detected": [2831.12, 201.0], "n2": [2413.0, 152.0]}`), para
  permitir auditoria posterior sem precisar re-rodar o cálculo.

### 2A.3 — Regra de uso: número primeiro, vision quando o número não explica

1. Rodar/ler o comparador numérico (quando existir para a classe) — é barato, cobre 100%
   dos itens, e já aponta *quais* itens têm dimensão/geometria fora do esperado.
2. Para os itens que o número não consegue explicar sozinho (ex.: dimensão bate mas a
   *forma* está errada; ou o `dim_delta` é alto e não está claro se é overlap com viga,
   overlap com laje vizinha, crop cortando borda, etc.) — gerar e **ler o PNG** (headless
   estrutural + vínculos, `capture_granular_item_pages` de `playwright_loop.py`) antes de
   decidir a `causa_raiz`. Não escrever um fix genérico "no escuro" a partir só do número —
   foi exatamente esse erro que fez o ciclo de 02/07 corrigir o eixo errado do problema em
   L318 (ver caso real, §4).

---

## 3. Passo 2B — Diagnóstico humano (dono)

Já documentado em detalhe em `ARETE-TRIAGEM-ERROS.md` — não duplicar aqui, só resumir:

1. Dono abre `scripts/arete/qa_error_review.py open --dir .../{secao}` (perfil de navegador
   persistente), navega pelas fichas, marca checkbox "ERRADA" + nota livre onde achar
   problema. Some sozinho, sem precisar salvar.
2. Claude lê com `qa_error_review.py read --dir ... --json`, interpreta a nota crua e grava
   uma entrada por causa identificada no item, com `marcado_por: "humano"`. Se a nota
   apontar erro N1/N3 e outro erro N4, são dois achados, não uma linha agregada.

Hoje o checkbox (`_error_marker_block`) só existe em `preficha_laje_html.py` — é o item #1
do checklist de generalização (§6).

---

## 4. Passo 3 — Log de Triagem unificado (schema estendido)

Arquivo: `scripts/arete/relatorios/triagem_erros/{obra}_{pav}_{secao}.jsonl` (já existe
para lajes; um arquivo por seção/classe, igual ao padrão atual).

Schema por linha (campos em **negrito** são novos nesta versão; o resto já existia):

| Campo | Humano | Automático | Significado |
|---|---|---|---|
| `finding_id` | sim | sim | ID estável do achado; identifica atualizações posteriores |
| `run_id` | sim | sim | geração headless cujas evidências foram avaliadas |
| `data` | sim | sim | timestamp da entrada (não da marcação original) |
| `obra`, `pavimento`, `classe`, `item` | sim | sim | identificação |
| `marcado_por` | `"humano"` | `"auto"` | quem gerou esta entrada |
| `nota_original` | texto do dono | — (null) | só existe pro humano |
| `causa_raiz` | sim | sim | slug técnico — mesmo vocabulário para os dois |
| `causa_descricao` | sim | sim | frase explicando a causa |
| **`confianca`** | — (null, humano é definitivo) | **sim (0.0-1.0)** | só automático |
| **`evidencia`** | — (opcional: link do screenshot) | **sim (números/observação)** | o que embasou o diagnóstico |
| `campos_afetados` | sim | sim | lista de N1/N2/N3/N4 impactados |
| **`concordancia`** | preenchido depois, quando existir par | preenchido depois, quando existir par | `"concorda"` / `"diverge"` / `"pendente"` |
| `status` | sim | sim (mas ver regra de precedência abaixo) | aberto → em_correcao → corrigido → verificado |
| `fix_aplicado` | sim | sim | descrição do que mudou + arquivo |
| `verificado_em` | sim | sim | timestamp da confirmação pós-regeneração |
| `updated_at` | sim | sim | última atualização atômica do registro |
| `supersedes_finding_id` | opcional | opcional | liga reabertura a um achado anterior |

### 4.1 — Granularidade e persistência atuais

- A unidade é uma **causa em um item**, não o item inteiro.
- A chave lógica é `item + causa_raiz + marcado_por + run_id`; `finding_id` é a identidade
  persistente usada pelos scripts.
- No estágio atual (uma obra, uma pessoa, baixo volume), o JSONL é um registro operacional
  versionado: `status`, `fix_aplicado`, `updated_at` e `verificado_em` podem ser atualizados
  por script com reescrita atômica do arquivo.
- Não editar linhas manualmente nem reutilizar o mesmo `finding_id` para outra causa.
- Reabrir um achado verificado cria novo `finding_id` e pode apontar para o anterior com
  `supersedes_finding_id`.
- Event sourcing imutável completo fica registrado como evolução futura em
  `ARETE-MCP-RAG-HARMONIZACAO.md`; não é requisito da implementação atual.

### 4.2 — Regra de precedência (humano sempre vence a decisão)

- Se só existe entrada **auto** para um item: ela é hipótese de trabalho, pode disparar
  investigação e até fix se `confianca` for alta — mas o item continua etiquetado como
  não confirmado por humano (`concordancia: "pendente"`) até o dono revisar aquela ficha.
- Se só existe entrada **humana**: é definitiva, vira a causa-raiz do fix diretamente
  (fluxo que já existia antes desta versão).
- Se **ambas existem** para o mesmo item:
  - `causa_raiz` iguais (ou equivalentes) → `concordancia: "concorda"` nos dois registros.
    Prossegue com confiança alta.
  - `causa_raiz` diferentes → `concordancia: "diverge"` nos dois registros. **A causa-raiz
    do humano é a que orienta o fix.** A divergência NÃO é apagada nem "corrigida" — fica
    registrada como está, porque é o dado que mede a precisão do diagnóstico automático.

### 4.3 — Métrica de confiança do diagnóstico automático (para medir autonomia futura)

Rollup simples, calculável a qualquer momento a partir do JSONL (script a construir,
`scripts/arete/triagem_concordancia.py` — ver §6):

```
taxa_concordancia(classe, causa_raiz, janela_de_tempo) =
    nº entradas auto com concordancia="concorda" / nº entradas auto com par humano
```

Uso: enquanto a taxa de concordância de uma `causa_raiz` for baixa, o diagnóstico
automático dessa causa específica continua sendo hipótese, nunca decisão. Quando a taxa
for alta e estável em várias rodadas/obras, isso é o critério objetivo pra reduzir a
dependência da revisão humana naquele tipo de causa especificamente — não é uma decisão
"no chute", é olhar o histórico. Isso é o que viabiliza a autonomia futura sem perder o
controle de qualidade.

---

## 5. Passos 4-6 — Corrigir, Reverificar, Fechar

Sem mudança em relação ao já documentado em `ARETE-TRIAGEM-ERROS.md` e ao `CLAUDE.md` da
missão: corrigir a causa-raiz no motor (nunca a ficha, nunca hardcode por item), um fix por
causa resolve todos os itens daquela causa, rodar regressão antes de marcar `corrigido`,
regenerar headless e reler os dois diagnósticos no item antes de marcar `verificado`.

**Regra nova, a partir de agora:** todo fix deve atualizar as entradas do JSONL que ele
pretende resolver (`fix_aplicado` + `status`) **antes** de considerar o ciclo fechado — foi
a omissão exata do ciclo de 02/07 (fix aplicado em `slab_tracer.py`, log nunca tocado).

---

## 5.1 — Visão macro do estrutural (decisão 02/07/2026)

Motivação: fichas granulares (por item) já resolvem leitura fina de dimensão/texto, mas
não dão a visão de conjunto — "essa laje destacada está mesmo onde deveria, olhando o
pavimento inteiro?". Ideia original do dono: gerar 1 HTML gigante do estrutural limpo do
SA + 4 variantes com destaque por classe (lajes/fundos/laterais/pilares), pra leitura
macro dinâmica via Playwright.

**Restrição técnica real (checada 02/07, ver conversa da sessão):** o limite de resolução
de imagem em visão (long-edge ~2576px / ~4784 visual tokens nos modelos atuais) faz um
raster único do pavimento inteiro perder texto pequeno de cota — a orientação de tiling
oficial é "detectar região de interesse estruturalmente, então aplicar visão só no recorte"
— exatamente o que as fichas granulares por item já fazem. **A visão macro serve para
orientação/gestalt (this item is roughly here, faz sentido espacialmente), não para leitura
fina — essa continua sendo função da ficha granular por item.**

**Decisão de implementação:** as fichas hoje embutem PNG raster (base64, via
`ezdxf`+matplotlib) — texto ali é pixel, não é dado. Para a visão macro, gerar o estrutural
como **SVG nativo** (mesma stack ezdxf/matplotlib, só trocar `savefig(..., format="svg")`
em vez de PNG) com texto como elemento `<text>` real do DOM. Isso permite ao Playwright ler
rótulos/coordenadas **sem visão nenhuma** (via accessibility snapshot ou
`page.evaluate` no DOM) — zero custo de token, zero risco de alucinação de leitura — e ainda
permite screenshot recortado (`page.screenshot(clip=...)`) em qualquer zoom sem perda,
para os casos que exigem julgamento visual de verdade (hachura, cruzamento de linha,
contorno). É a combinação recomendada: **DOM/accessibility tree para texto exato, vision
só para geometria/julgamento visual.**

**Refinamento sobre "5 arquivos":** em vez de exportar 5 HTMLs completos (5 fontes de
verdade pra manter sincronizadas), gerar **1 HTML** com os elementos de cada classe em
grupos SVG separados (`<g id="layer-lajes">`, `<g id="layer-fundos">`, etc.) e toggle via
checkbox/JS — mesmo padrão já usado no `_error_marker_block`. Playwright troca a visibilidade
antes de cada screenshot (equivalente às "5 versões"), e o dono também pode alternar ao
vivo no navegador. Mais barato de construir e manter que 5 exports separados.

**Ferramenta de automação:** manter Playwright (já validado no repo, bug de paint-culling
já resolvido em `ARETE-PLAYWRIGHT-QA-VISUAL.md`). Não trocar para Puppeteer — o Puppeteer
MCP só oferece screenshot (força leitura 100% visual), enquanto o Playwright MCP tem modo
accessibility-tree por padrão, que é exatamente o que a leitura via SVG precisa. Não usar
OCR aqui: o texto já existe como dado exato dentro do DXF (via `ezdxf`) e, com SVG, também
como DOM — rodar OCR em cima disso seria reintroduzir erro de reconhecimento sobre um dado
que já é limpo.

**Achado (02/07, verificado no código):** a conversão pra SVG é mais barata e mais
importante do que parecia — **não são 4 renderizações por classe, são 2 funções únicas,
compartilhadas por todas as classes**, ambas em `src/ui/widgets/pre_validation_dialog.py`:
- `_render_ezdxf_b64()` (~L4826) — renderiza N2/N3/N4 de QUALQUER classe (ezdxf+matplotlib,
  `fig.savefig(buf, format='png', ...)`).
- `_render_pilar_dxf_context_b64()` (~L5292) — renderiza o card N1 (contexto estrutural
  com o item destacado) de QUALQUER classe, via `focus_mode` (já reusada para laje com
  `focus_mode="slab"`; FV/LV devem seguir o mesmo padrão de `focus_mode`).

Trocar `format='png'` por `format='svg'` (com um parâmetro pra escolher) nessas duas
funções resolve SVG para os cards N1-N4 de **LAJ, PIL, FV e LV de uma vez só** — é o mesmo
ponto de alavancagem que a visão macro, só que ainda mais valioso: é exatamente nas fichas
granulares que o diagnóstico automático e o Claude ficam comparando texto/dimensão pixel a
pixel hoje (foi o caso do L318). Com SVG, essa leitura vira consulta de DOM, exata, sem
gastar visão nem token.

**Isso muda a prioridade e o sequenciamento:** por tocar em `pre_validation_dialog.py`
(arquivo compartilhado por todas as classes, já citado no `CLAUDE.md` como "não editar
sem confirmar que nenhum outro agente trabalha nele em paralelo"), esta tarefa **não deve
entrar dentro de um prompt scoped a uma classe** (ex.: não bundlar no prompt de FV) — deve
ser feita em UMA sessão dedicada, sem nenhum outro chat de classe mexendo no mesmo arquivo
ao mesmo tempo, idealmente antes de abrir os loopings paralelos de PIL/FV/LV (o ganho vale
pra todas ao mesmo tempo, então não há razão pra esperar).

**Status:** CONCLUÍDO 02/07/2026 (ver item 1 do checklist §6) — para N1-N4 de LAJ/PIL/FV.
A visão macro com layers toggláveis em si (1 HTML, grupos por classe) ainda não foi
construída — isso ficou como item 7 do checklist, depende deste item mas é entrega
separada.

## 5.2 — Estado real de LV (auditoria 03/07/2026)

Antes de abrir o looping de LV, uma auditoria do estado atual encontrou uma situação
diferente da de PIL/FV (que só precisavam de 2 entregas incrementais em cima de um harness
já harmonizado). LV está em outro patamar: **não existe harness granular nenhum ainda.**

- **O que funciona:** `self._segment_data['lateral_a_para'|'lateral_b_para'|
  'lateral_a_passa'|'lateral_b_passa']` chega populado no headless (dados reais, todas as
  vigas do 13_PAV aparecem). Mas cai no branch **genérico** de `_export_html_snapshot`
  (`pre_validation_dialog.py`, ~L6322-6345 — o mesmo "1 página com N linhas de tabela" que
  `lajes`/`fundo` usavam antes de ganhar `write_laje_pages`/`write_fundo_pages`), gerando
  `preficha_lateral_{a,b}_{para,passa}.html` — 4 páginas tabulares, uma por combinação.
- **Imagens estáticas, não vivas:** essas 4 páginas usam `_find_n4_png`/`_find_n2_png`
  (~L4898/L5345), que buscam PNG **pré-renderizado** em
  `scripts/arete/relatorios/{timestamp}/png/LV_*.png` — o lote mais recente é de
  **24/06/2026**, ou seja, as imagens de N4/N2 mostradas hoje têm mais de uma semana e não
  refletem nenhum fix feito desde então. Só o card N1 (via `_photo()`, Qt/QPainter) é
  renderizado ao vivo. Nenhum destes três é SVG.
- **Existe um protótipo abandonado, não confundir com harness ativo:** em
  `scripts/arete/html_fichas/Obra_TREINO_1/13_PAV_20260630_203509/laterais_viga/` há uma
  estrutura `{a_para,a_passa,b_para,b_passa}/{VIGA}_{N}.html` com sidebar+nav+cards por
  segmento — **mas o script Python que a gerou não existe mais no repo** (não achado por
  grep de nenhuma string/classe CSS distintiva desse HTML) e ela não é regenerada por
  nenhum run desde 30/06. O CSS/layout dela (`.sb-list`, `.kv`, `.badge-src`, `.src-n1`
  etc.) diverge completamente do padrão LAJ/FV/PIL (`.evidence-card`, `.img-geo`, `.sec`).
  **Não ressuscitar essa arquitetura** — ela criaria uma 4ª linguagem visual em vez de
  consolidar numa só. Serve só como referência histórica de uma ideia de agrupamento
  (por side, com segmentos dentro), não como base de código.
- **⚠️ Proteger `interpretacao_laterais.html`** (mesma pasta do protótipo acima) — é um
  guia de interpretação com diagramas SVG feitos à mão em sessão anterior (sarrafo
  gradeado × sarrafeado, cotas, etc.), analogamente a `interpretacao_abcd.html` do PIL.
  **Não sobrescrever, não regenerar, não tocar.**
- **A plumbing de DXF já suporta LV** — `_find_beam_dxf('LV', item_name, n4=...)` e
  `_find_n2_recorte_dxf('LV', item_name)` (`pre_validation_dialog.py`) já aceitam `'LV'`
  como `class_prefix` genericamente. Confirmado por evidência real de arquivo
  (`DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/`): DXFs existem como
  `LV_preview_{VIGA}.dxf` (bare), `LV_preview_{VIGA}_A.dxf`, `LV_preview_{VIGA}_B.dxf`
  (por lado) e variantes `_CORTE`/`_VIEW_A`/`_VIEW_B` (visão de corte — 3ª ficha ainda não
  criada, ver `HANDOFF-ARETE-EXECUTOR.md` v1.1 item 6; **fora de escopo desta rodada**,
  focar só em Face A/Face B).
- **Granularidade correta do N2 é por VIGA, não por lado** — `reverse_eng_fichas` (classe
  `LV`, 32 fichas no 13_PAV) tem `elemento_id` = nome bare da viga (`V301`), e o
  `campos_json` já contém `panels_A`/`panels_B`/`h_A`/`h_B`/`laje_sup_A`/`laje_sup_B`
  juntos numa ficha só. Ou seja: **uma ficha N2 cobre os dois lados** — o diagnóstico
  numérico futuro deve comparar por viga (como FV/LAJ), não duplicar por lado.

## 6. Checklist de generalização por classe

O que LAJ já tem e as outras classes ainda não, para chegar na mesma paridade de
infraestrutura:

| Peça | LAJ | PIL | FV | LV |
|---|---|---|---|---|
| Geração headless HTML N1-N4 | ✓ `headless_sa_analise.py` | ✓ | ✓ | ✓ (03/07) `preficha_lateral_html.py` — 1 página por VIGA com seções Lado A/Lado B (ver §5.2 e item 5 abaixo) |
| SVG inline nos cards N1-N4 (leitura via DOM, sem visão) | ✓ (02/07) | ✓ (02/07) | ✓ (02/07) | ✓ (03/07) — nasceu direto em SVG, sem retrofit |
| Checkbox de erro + `localStorage` (`_error_marker_block`) | ✓ `preficha_laje_html.py` | ✓ (02/07) `pre_validation_dialog.py::_error_marker_block_pil` | ✓ (02/07) `preficha_fundo_html.py` | ✓ (03/07) `preficha_lateral_html.py`, chave `aten_erro_lv_...` |
| Diagnóstico numérico N1×N2 automático (schema v2 nativo, headless/CLI) | ✓ (03/07) `scripts/arete/diagnostico_laj_n1_n2.py` — legado (`main.py::_debug_works_pavements_documents`) mantido só como histórico, não usar mais | ✓ (02/07) `scripts/arete/diagnostico_pil_n1_n2.py` | ✓ (02/07) `scripts/arete/diagnostico_fv_n1_n2.py` | ✓ (03/07) `scripts/arete/diagnostico_lv_n1_n2.py` — causa `schema_gap` com confiança média (0.6), não `extractor_bug`; ver achado não resolvido no docstring do módulo |
| Log de triagem JSONL | schema v1 legado (16 achados humanos, 02/07) + saída própria `triagem_auto_laj.jsonl` (03/07) já em schema v2; não fundidos ainda | saída própria `triagem_auto_pil.jsonl` já em schema v2; não fundida ao log de triagem humana da classe ainda | saída própria `triagem_auto_fv.jsonl` já em schema v2; idem | saída própria `triagem_auto_lv.jsonl` já em schema v2; idem |
| Schema v2 do log (dual diagnóstico, `concordancia`) | nativo no diagnóstico automático (03/07); reconciliação manual já rodada uma vez (ver item 2 abaixo) | nativo no diagnóstico automático; falta unificar com triagem humana | nativo no diagnóstico automático; falta unificar com triagem humana | nativo no diagnóstico automático; falta unificar com triagem humana |

Itens de infraestrutura pendentes, priorizados:

1. ~~**SVG em `_render_ezdxf_b64` e `_render_pilar_dxf_context_b64`** (§5.1)~~ — **CONCLUÍDO
   02/07/2026.** `_render_ezdxf_b64`, `_render_pilar_dxf_context_b64` e
   `_render_n2_recorte_b64` (`pre_validation_dialog.py`) ganharam parâmetro `fmt='png'|'svg'`
   (default continua `'png'`, zero mudança de comportamento pra quem não passar `fmt`). Os
   cards N1-N4 de LAJ (`preficha_laje_html.py`), FV (`preficha_fundo_html.py`) e PIL
   (`_write_pilar_pages` em `pre_validation_dialog.py`) passaram a pedir `fmt='svg'`
   explicitamente. Helper novo `src/ui/widgets/svg_embed_utils.py`
   (`strip_fixed_size`/`embed_visual`) — módulo neutro pra evitar import circular entre
   `pre_validation_dialog.py` e os geradores de ficha por classe. Verificado com Playwright
   real: `page.eval_on_selector('svg.img-geo', ...)` extraiu 144 elementos `<text>` da
   ficha L318 (incluindo rótulos de pilar como "P19") sem gastar 1 token de visão; screenshot
   confere que o visual não mudou. Testes (`test_preficha_laje_html.py`,
   `test_preficha_fundo_html.py`) atualizados para esperar `svg` em vez de `img`. Fallback
   Qt (`_photo`/`_widget_to_b64_png`, usado quando não há `self._dxf_data`) continua PNG —
   não convertido (pipeline Qt/QPainter, não matplotlib; baixo uso, é só fallback). Relatório
   antigo tabular de PIL (`_pil_extra_td`) também não convertido — fora do padrão de ficha
   granular N1-N4, baixa prioridade.
2. ~~**Migrar o log de LAJ para o schema v2 pragmático**~~ / ~~**Headlessizar o
   diagnóstico numérico de LAJ**~~ (itens 2 e 3 antigos, fechados juntos em 03/07/2026 —
   mesmo trabalho). `scripts/arete/diagnostico_laj_n1_n2.py` novo, substituindo
   `main.py::_debug_works_pavements_documents` (mantido só como histórico, não chamar
   mais): lê geometria N1 do estado headless (`estado_*.json → slabs[].points` — chave
   que precisou ser ADICIONADA ao snapshot, antes só tinha name/nivel/height; mudança
   aditiva de 4 linhas em `pre_validation_dialog.py::_export_html_snapshot`, bloco
   `slabs_serial`), lê N2 direto de `reverse_eng_fichas` (classe='LAJ', não mais o cache
   `projects_repo/.../obras.json`), saída JSON+JSONL versionada por run (nunca mais o
   `debug_slab_pav13.json` fixo). Reusa `diagnostico_common.footprint_delta` (extraída de
   `diagnostico_pil_n1_n2.py` nesta mesma entrada — `_footprint_delta` local do PIL virou
   duplicata depois disso, removida, PIL agora importa a versão compartilhada; testes de
   PIL continuam 7/7 passando, sem regressão).

   **Testado contra Obra_TREINO_1/13_PAV real: 31 N1 × 31 N2 (única classe com
   cobertura 100%), 4 alertas** (L312, L315 novos; L318 RUIM 0.18; L319 REGULAR 0.058 —
   os dois já conhecidos do caso do §7).

   **Reconciliação com a triagem humana (16 achados de 02/07) — rodada uma vez,
   manualmente, achado real:** dos 16 itens marcados `n1_overlap_viga` pelo humano, **14
   já aparecem EXCELENTE/BOM no diagnóstico automático de hoje** (L303, L308, L310, L327-
   331 em EXCELENTE delta≤0.005; L317, L321-325 em BOM delta≈0.02-0.03) — ou seja, o fix
   `_reject_overlapping_row_expansions` (aplicado em `slab_tracer.py` antes desta entrada,
   ver §7) parece ter corrigido a dimensão desses 14 itens depois que a nota humana foi
   escrita. **Verificado visualmente (não só pelo número) em 1 amostra — L303:**
   screenshot da ficha confere N1/N2/N3/N4 mostrando o mesmo retângulo limpo
   (418×183, sem sobreposição de pilar/viga), confirmando que não é coincidência
   numérica. Só L318 e L319 continuam divergentes nos dois lados (`concordancia:
   "diverge"` — humano diz `n1_overlap_viga`, específico; automático diz
   `extractor_bug`, genérico — ver docstring do módulo sobre por que essa distinção
   ainda não é automática). **Ação recomendada, NÃO executada aqui** (não é decisão de
   um diagnóstico automático sozinho, é o próprio dono ou uma sessão de triagem visual
   que deve confirmar): reabrir a ficha desses 14 itens em `qa_error_review.py`,
   confirmar visualmente, e só então gravar uma nova entrada `status: "verificado"` no
   log (append-only, não editar as 16 linhas existentes). L312/L315 (novos, sem nota
   humana) e L318/L319 (já sabidos, ainda quebrados) são os que realmente precisam de
   atenção agora. Teste: `tests/test_diagnostico_laj_n1_n2.py` (6 casos, incluindo um
   caso que reproduz literalmente a geometria real do L318). Suíte completa (73 testes
   relacionados) sem regressão.
4. ~~**Script de rollup de concordância**~~ — **CONCLUÍDO 03/07/2026**
   (`STORY-EXEC-05-RECONCILIACAO-CONCORDANCIA.md`, ver
   `docs/HANDOFF-PRODUCAO-EXECUTOR.md`). `scripts/arete/triagem_concordancia.py`: lê o
   run mais recente de cada `triagem_auto_{classe}.jsonl` + todos os `triagem_erros/
   *.jsonl` humanos, agrupa por classe/causa_raiz, calcula `taxa_concordancia` (só entre
   itens com par nos dois lados — sem par vira `None`, não zero) e lista `abertos_reais`.
   2 testes em `tests/test_triagem_concordancia.py`. Reconciliação aplicada a PIL (24
   alertas → 13 abertos reais + 11 estruturais/sem cobertura N2), FV (34 → 22 + 12,
   destaque: 6 itens já fechados por `STORY-EXEC-01-FV-SARR5CM.md` continuam abertos
   NESTE eixo — aquele fix resolveu um problema de config do comparador G2 visual,
   diferente da divergência de dimensão N1×N2 medida aqui) e LV (20 → 14 + 6). Achado
   lateral relevante: durante a reconciliação, outra sessão concorrente fechou
   `STORY-EXEC-04-LAJ-LINHAS-HORIZONTAIS.md` e seus 23 itens corroboraram
   independentemente 2 dos achados novos desta rodada (L312, L315) — dois diagnósticos
   diferentes convergindo no mesmo item é sinal forte de achado real. Nenhum motor foi
   tocado; todos os "abertos reais" ficaram listados (não corrigidos) em
   `scripts/arete/relatorios/triagem_erros/RECONCILIACAO-2026-07-03.md`, prontos para
   virarem story própria cada um.
5. ~~**Levar `_error_marker_block` + diagnóstico numérico para PIL e FV**~~ — **CONCLUÍDO
   02/07/2026 para PIL e FV, 03/07/2026 para LV (as 4 classes fecham este item).** PIL:
   `_error_marker_block_pil` + `_sidebar_error_flags_script_pil` em
   `pre_validation_dialog.py` (chave `aten_erro_pil_{obra}_{pav}_{nome}`, mesmo padrão de
   LAJ/FV) + `scripts/arete/diagnostico_pil_n1_n2.py` (compara bbox N1 vs
   `comprimento`/`largura` do N2 por melhor orientação; pilares não-retangulares — `em
   L`/`em U`/`Circular`/`Especial`, via `_pilar_formato` reimplementado sem dependência de
   Qt — ficam deliberadamente fora do diagnóstico de dimensão, porque bbox de planta
   não-retangular não é comparável a comprimento×largura; ver docstring do módulo). FV:
   `scripts/arete/diagnostico_fv_n1_n2.py` (já existia antes desta entrada). Ambos os
   scripts usam `scripts/arete/diagnostico_common.py` (helpers extraídos:
   `resolve_state_path`, `classify_delta`, deltas, etc.).
   Testado contra Obra_TREINO_1/13_PAV real: PIL 46 N1 × 35 N2, 24 alertas, 2
   pilares especiais corretamente excluídos do diagnóstico de dimensão. Testes:
   `tests/test_diagnostico_pil_n1_n2.py` (7 casos) + `tests/test_diagnostico_fv_n1_n2.py`.
   Checkbox validado via Playwright real (marcar → `qa_error_review.py read` → limpar),
   sem regressão nas 63 outras suítes relacionadas.

   **LV (03/07/2026) — a mais trabalhosa das três**, porque diferente de PIL/FV, LV **não
   tinha harness algum** (ver §5.2): as 4 combinações lado×comportamento caíam num
   relatório tabular genérico com PNGs estáticos de 24/06. Construído do zero:
   `src/ui/widgets/preficha_lateral_html.py` (`write_lateral_pages`) — 1 página por VIGA
   (não por lado, não por lado×comportamento) com seções "Lado A"/"Lado B", cada uma
   reunindo os segmentos Para+Passa daquele lado; decisão baseada em evidência real de
   arquivo (ficha N2 é uma por viga com `panels_A`/`panels_B` juntos; DXFs N3/N4 são por
   lado — `LV_preview_{VIGA}_A.dxf`/`_B.dxf`). Nasceu direto em SVG + checkbox (sem
   retrofit, diferente de LAJ/FV/PIL que precisaram de conversão depois). Wire-up em
   `pre_validation_dialog.py::_export_html_snapshot`: as 4 `reports` de
   `lateral_{a,b}_{para,passa}` são consolidadas ANTES do loop de dispatch genérico (não
   viram 4 páginas/sidebars separados).
   `scripts/arete/diagnostico_lv_n1_n2.py`: comparação por viga (não por lado, mesma
   razão da ficha N2); método de comparação **deliberadamente por conjunto de números,
   não por posição** — o campo `width` do N1 é uma string tipo `"19/55"` cuja ordem
   NÃO é estável entre vigas (confirmado com dado real: a maioria é `"b/h"`, mas `V308`
   é `"h/b"` invertido). Achado não resolvido, registrado no docstring do módulo: em
   14/30 vigas do 13_PAV, o número `120` aparece no N1 sem corresponder a nenhum campo
   numérico da ficha N2 (nem `h_section`/`h_section_all`, nem alturas de painel
   `panels_A/B`) — causa-raiz gravada como `schema_gap` com confiança 0.6 (não
   `extractor_bug` — não afirma que o motor está errado, só que a correspondência de
   campos ainda não foi confirmada por humano lendo o recorte). Testado contra
   Obra_TREINO_1/13_PAV real: 34 vigas N1 × 32 N2, 20 alertas. Testes:
   `tests/test_preficha_lateral_html.py` (2 casos) + `tests/test_diagnostico_lv_n1_n2.py`
   (7 casos). Checkbox validado via Playwright real (mesmo protocolo de PIL/FV). Suíte
   completa (67 testes relacionados) sem regressão. **NÃO integrado** ao
   auto-diagnóstico embutido em `headless_sa_analise.py` (`_run_fv_diagnostic_postprocess`
   / `_publish_arete_manifest`, que hoje só chama o diagnóstico de FV automaticamente) —
   isso ficou fora de escopo desta entrada, é infraestrutura nova que a FV introduziu
   depois do meu trabalho original em PIL; PIL também não está integrado lá. Ver item 8.
6. **Flag `--secao` em `headless_sa_analise.py`** para gerar só uma classe (hoje sempre
   gera pilares+lajes+vigas juntos, ~3min por rodada mesmo quando só uma classe está em
   loop) — gap de performance já apontado na revisão de qualidade de 20/06, ainda aberto.
7. **Visão macro do estrutural com layers toggláveis** (§5.1) — depende do item 1 (SVG);
   é o HTML único com grupos por classe e toggle via JS. Cross-classe, não bloqueia
   nenhuma classe individual.
8. **Estender o auto-diagnóstico embutido no headless para PIL e LV** (achado 03/07,
   descoberto ao concluir o item 5 para LV) — `headless_sa_analise.py` hoje só chama
   automaticamente `diagnostico_fv_n1_n2.py` + publica `arete_manifest.json` no final da
   rodada (`_run_fv_diagnostic_postprocess`/`_publish_arete_manifest`); PIL e LV têm
   scripts de diagnóstico prontos e testados, mas ainda rodam só manualmente via CLI.
   Generalizar essas duas funções pra aceitar lista de classes, em vez de hardcode em FV.

## 6.1 — Auditoria de consistência cross-classe (03/07/2026)

Depois de fechar o item 5 nas 4 classes, comparação linha a linha dos 4 diagnósticos e
das 4 fichas granulares — resultado: **o núcleo (SVG, checkbox, schema v2 de saída,
CLI) está de fato idêntico entre LAJ/PIL/FV/LV** (mesmos argumentos, mesmos campos de
schema, mesma convenção de pasta). Dois furos reais encontrados e já fechados:

1. ~~**Inconsistência `lj` vs `laj`**~~ — **NÃO é bug introduzido por nenhuma sessão
   recente; é pré-existente e não deve ser "corrigido" por rename.** O checkbox de LAJ
   (`preficha_laje_html.py::_error_marker_block`) e `_find_beam_dxf("LJ", ...)`/arquivos
   `LJ_preview_*.dxf` usam o código `lj`; o banco (`reverse_eng_fichas.classe='LAJ'`,
   centenas de linhas em produção) e os scripts de diagnóstico automático usam `laj`.
   São duas convenções independentes, cada uma com dado real dependente do nome atual
   (marcações humanas já gravadas em localStorage com `aten_erro_lj_*`; fichas de
   produção no DB com `classe='LAJ'`) — renomear qualquer uma arrisca perder/quebrar
   dado sem ganho funcional (`qa_error_review.py` já casa por prefixo genérico
   `aten_erro_*`, então a duplicidade não quebra nada na prática). **Ajuste feito:**
   nota de nomenclatura cruzada adicionada nas docstrings de
   `_error_marker_block` (`preficha_laje_html.py`) e do módulo
   `diagnostico_laj_n1_n2.py`, para o próximo leitor não se confundir.
2. ~~**PIL sem teste unitário dedicado**~~ — **CONCLUÍDO.** LAJ/FV/LV cada um tem seu
   `tests/test_preficha_{classe}_html.py` testando a página inteira, porque cada um tem
   gerador em módulo próprio. PIL não tem módulo próprio (`_write_pilar_pages` é uma
   função aninhada dentro de `_export_html_snapshot`, não isolável sem mockar dezenas de
   atributos do dialog) — por isso o teste novo, `tests/test_pilar_error_marker.py` (3
   casos), cobre diretamente as duas funções puras e independentes que compõem o
   checkbox de PIL (`_error_marker_block_pil`, `_sidebar_error_flags_script_pil`), sem
   tentar montar a página inteira. Suíte completa (76 testes relacionados) sem
   regressão.

Itens 1, 2, 3, 4 e 5 concluídos (02/07 PIL/FV; 03/07 LV, LAJ e a reconciliação
cross-classe); os outros 3 (6, 7, 8) seguem registrados aqui como próximo passo, a
executar sob ordem explícita do dono (gating já em vigor para todo o Arete).

---

## 7. Caso real que motivou este doc (02/07/2026)

Contexto completo em memória de sessão; resumo: um fix genérico em `slab_tracer.py`
(`_reject_overlapping_row_expansions`, protege contra laje sobrepor **laje vizinha**) foi
escrito e validado só com o comparador numérico (`debug_slab_pav13.json`). Melhorou vários
itens (L319, L321-325) sem regredir os que já batiam com N2. Mas o item mais grave (L318)
continuou errado — porque o log de triagem humana (gravado *antes* do fix, nunca
consultado) já dizia que a causa real era **laje sobrepondo viga**, não laje sobrepondo
laje. O fix resolveu o eixo errado do problema porque pulou a leitura da fonte de
diagnóstico mais precisa que já existia. Este é o exemplo concreto do porquê o diagnóstico
duplo (§2) e a checagem do log **antes** de escrever qualquer fix (§4.2) agora são passo
obrigatório, não opcional.

---

## 8. Referências

- `docs/ARETE-TRIAGEM-ERROS.md` — mecânica detalhada do ciclo marcar→logar→corrigir→reverificar
- `docs/ARETE-PLAYWRIGHT-QA-VISUAL.md` — captura de screenshot, bug de paint-culling, quando usar cada função
- `docs/LOOPING-EVOLUCAO-N2-VISAO-FICHA.md` — histórico/conceitual, pré-headless (superseded na parte de execução)
- `docs/MASTERPLAN-LOOP-TREINO-MOTOR.md` — infra de aprendizado no DB (`transformation_rules`, `training_events`), roadmap por classe (superseded na parte de execução)
- `docs/MASTERPLAN-ARETE-QUALITY-GATES.md` — definição de Arete, gates G0-G6
- `../../docs/MCP-ACTIVE-LEARNING-SPEC.md` (raiz do workspace) — servidor MCP próprio do
  projeto (`src/mcp/cad_analyzer_mcp.py`). A captura de edições T0 pela UI já está ativa;
  servidor, propostas, promoção e indexação continuam inativos. O JSONL Arete permanece o
  registro operacional da triagem até o gatilho de integração descrito no contrato.
- `docs/HANDOFF-ARETE-EXECUTOR.md` — protocolo de autonomia, restrições rígidas (ainda válidas)
