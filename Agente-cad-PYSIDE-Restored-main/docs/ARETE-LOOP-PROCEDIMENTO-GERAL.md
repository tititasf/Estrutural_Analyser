# ARETE — Procedimento Geral de Looping por Classe (Fichas HTML + Diagnóstico Duplo)

**Versão:** 1.0
**Data:** 2026-07-02
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
  → G2 Paridade canônica N4 × recorte N2
  → G6 Golden set/regressão

G3 UI/persistência é transversal.

G4 Convergência N1 × N2
  → G5 Paridade N3 × N4
  → G6 Golden set/regressão
```

**Escopo atual:** as fichas e a triagem já ajudam a investigar qualquer card N1–N4, mas
o fechamento do robô reverso ocorre primeiro em G0/G1/G2. N4 não é gabarito visual antes
de G1/G2 PASS. G5 só é válido depois de N4 certificado em G1/G2 e da conversão N1 passar
G4. O aprendizado de recorte é um trilho CROP separado e não recebe novo número G0–G6.

---

## 1. Passo 1 — Geração headless (já genérico, pronto para qualquer classe)

```bash
C:/Users/Thierry/AppData/Local/Programs/Python/Python312/python.exe \
    scripts/arete/headless_sa_analise.py --obra {OBRA} --pav {PAV}
```

Produz `scripts/arete/html_fichas/{OBRA}/{RUN}/{secao}/{item}.html` para
`pilares/`, `lajes/`, `fundos_viga/` (LV ainda não confirmado nesse pipeline — checar ao
iniciar o looping de LV). Cada ficha empilha 4 `.evidence-card`: N1 (Structural Analyzer),
N2 (recorte humano/STOG), N3 (robô via N1), N4 (robô via N2). Runtime ~3min para o
pavimento inteiro (todas as classes juntas) — **não há hoje uma flag para gerar só uma
classe**; ver gap de performance na seção 6.

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

## 6. Checklist de generalização por classe

O que LAJ já tem e as outras classes ainda não, para chegar na mesma paridade de
infraestrutura:

| Peça | LAJ | PIL | FV | LV |
|---|---|---|---|---|
| Geração headless HTML N1-N4 | ✓ `headless_sa_analise.py` | ✓ | ✓ | ? (checar antes de iniciar looping LV) |
| SVG inline nos cards N1-N4 (leitura via DOM, sem visão) | ✓ (02/07) | ✓ (02/07) | ✓ (02/07) | ✗ — mesma função compartilhada, só falta confirmar se LV usa o mesmo gerador de ficha granular |
| Checkbox de erro + `localStorage` (`_error_marker_block`) | ✓ `preficha_laje_html.py` | ✓ (02/07) `pre_validation_dialog.py::_error_marker_block_pil` | ✓ (02/07) `preficha_fundo_html.py` | ✗ — criar no gerador de páginas LV |
| Diagnóstico numérico N1×N2 automático (schema v2 nativo, headless/CLI) | parcial/legado (preso à UI, nome de arquivo fixo, ver §2A.1 — não migrado) | ✓ (02/07) `scripts/arete/diagnostico_pil_n1_n2.py` | ✓ (02/07) `scripts/arete/diagnostico_fv_n1_n2.py` | ✗ |
| Log de triagem JSONL | ✓ (schema v1 legado, sem `marcado_por: "auto"` ainda — ver item 2 abaixo) | saída própria `triagem_auto_pil.jsonl` já em schema v2; não fundida ao log de triagem humana da classe ainda | saída própria `triagem_auto_fv.jsonl` já em schema v2; idem | ✗ |
| Schema v2 do log (dual diagnóstico, `concordancia`) | **a migrar** (este doc) | nativo no diagnóstico automático; falta unificar com triagem humana | nativo no diagnóstico automático; falta unificar com triagem humana | a criar |

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
2. **Migrar o log de LAJ para o schema v2 pragmático** (§4) — gerar uma linha por causa,
   adicionar `finding_id`/`run_id`/`updated_at` e `confianca`/`evidencia`/`concordancia`.
   Preservar as linhas existentes como legado; novas escritas seguem o schema atual.
3. **Headlessizar o diagnóstico numérico de LAJ** — tirar a dependência de `self.slabs_found`
   (rodar a partir do JSON de saída do `headless_sa_analise.py` ou equivalente), nome de
   arquivo versionado por obra/pav/run em vez do fixo `debug_slab_pav13.json`.
4. **Script de rollup de concordância** (`scripts/arete/triagem_concordancia.py`, §4.3).
5. ~~**Levar `_error_marker_block` + diagnóstico numérico para PIL e FV**~~ — **CONCLUÍDO
   02/07/2026 para ambas as classes.** PIL: `_error_marker_block_pil` +
   `_sidebar_error_flags_script_pil` em `pre_validation_dialog.py` (chave
   `aten_erro_pil_{obra}_{pav}_{nome}`, mesmo padrão de LAJ/FV) + `scripts/arete/
   diagnostico_pil_n1_n2.py` (compara bbox N1 vs `comprimento`/`largura` do N2 por
   melhor orientação; pilares não-retangulares — `em L`/`em U`/`Circular`/`Especial`,
   via `_pilar_formato` reimplementado sem dependência de Qt — ficam
   deliberadamente fora do diagnóstico de dimensão, porque bbox de planta não-retangular
   não é comparável a comprimento×largura; ver docstring do módulo). FV:
   `scripts/arete/diagnostico_fv_n1_n2.py` (já existia antes desta entrada). Ambos os
   scripts usam `scripts/arete/diagnostico_common.py` (helpers extraídos:
   `resolve_state_path`, `classify_delta`, deltas, etc. — reuso pronto para quando LV
   entrar). Testado contra Obra_TREINO_1/13_PAV real: PIL 46 N1 × 35 N2, 24 alertas, 2
   pilares especiais corretamente excluídos do diagnóstico de dimensão. Testes:
   `tests/test_diagnostico_pil_n1_n2.py` (7 casos) + `tests/test_diagnostico_fv_n1_n2.py`.
   Checkbox validado via Playwright real (marcar → `qa_error_review.py read` → limpar),
   sem regressão nas 63 outras suítes relacionadas. LV segue pendente, quando o looping
   de LV começar (roadmap por classe do `MASTERPLAN-LOOP-TREINO-MOTOR.md` §6).
6. **Flag `--secao` em `headless_sa_analise.py`** para gerar só uma classe (hoje sempre
   gera pilares+lajes+vigas juntos, ~3min por rodada mesmo quando só uma classe está em
   loop) — gap de performance já apontado na revisão de qualidade de 20/06, ainda aberto.
7. **Visão macro do estrutural com layers toggláveis** (§5.1) — depende do item 1 (SVG);
   é o HTML único com grupos por classe e toggle via JS. Cross-classe, não bloqueia
   nenhuma classe individual.

Itens 1 e 5 concluídos (02/07/2026); os outros 5 seguem registrados aqui como próximo
passo, a executar sob ordem explícita do dono (gating já em vigor para todo o Arete).

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
