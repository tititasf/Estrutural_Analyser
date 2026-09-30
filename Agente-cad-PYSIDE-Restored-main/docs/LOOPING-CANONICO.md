# LOOPING CANÔNICO — o único loop válido (e a quarentena dos obsoletos)

> **Convenção obrigatória de escrita e execução:** ao citar um gate, registrar sua
> finalidade entre parênteses na primeira menção do bloco: **G0 (sanidade de
> entradas)**, **G1 (round-trip N2→N4→N2′)**, **G2 (paridade canônica N2×N4)**,
> **G3 (UI e persistência)**, **G4 (convergência/interpretação N1)**,
> **G5 (paridade final N3×N4)** e **G6 (golden/regressão)**. Para qualquer gate
> visual — G2-V (N2×N4), N1-V/G4-V (interpretação N1×N2) ou G5-V (N3×N4) — o
> veredito é obrigatoriamente via `g2v_harness.py --backend cli`.
> **Agente CLI julga em PNG** (render full do DXF; vision = pixels).
> **SVG** é obrigatório no HTML da ficha quando há `--persist-db`, app ou
> **portal web** (zoom humano). Headless **sem** persist pode ser só imagem
> (dinâmico). Ver `docs/QA-VISAO-EVIDENCIA-CANONICA.md`. API visual é proibida.

**Data:** 2026-07-03 | **Atualizado:** 2026-07-13 | **Status:** CANÔNICO — consolidação pedida pelo dono após
múltiplas transições/refinamentos dos loops. **Se um script/procedimento de loop não
está na seção 1 deste doc, NÃO use sem ordem explícita do dono.**

> Procedimento detalhado: `ARETE-LOOP-PROCEDIMENTO-GERAL.md` (como executar) e
> `ARETE-TRIAGEM-ERROS.md` (ciclo de triagem). Este doc é o MAPA — diz o que é
> canônico e o que é legado, para nenhuma sessão pegar coisa velha por engano.

---

## 1. O loop canônico (dois eixos, um conjunto de ferramentas)

### Memória operacional autoevolutiva

O agente deve evoluir o motor e a documentação juntos: evidência nova → hipótese
geral → teste/fix autorizado → regressão → triagem/diário/manual da classe atualizados.
Item BLUE, solicitação humana e selo laranja são gatilhos de registro. HTML/**SVG**
(persist/app/web) e packs **PNG** de vision (agente) validados são candidatos
multimodais, não promoção automática: ao fechar uma classe/pavimento, o agente
consolida e pede validação humana para curadoria RAG;
ao fechar a obra, pede validação humana da compreensão global antes de propor RAG geral.
Ver `SA-ANALISE-PROGRESSO-POR-ITEM.md` e `SA-ANALISE/CLASSES/README.md`.

### Eixo A — Qualidade de GERAÇÃO (N2→N4, gates G0/G1/G2/G6)
```bash
python scripts/arete/arete_runner.py --classe {PIL|LV|FV|LAJ} --pav {PAV} [--regressao]
```
Compara N4 (gerado da ficha N2) contra o recorte humano; sela golden em PASS.

#### Painel dinâmico de depuração humana N2×N4 (companheiro do Eixo A, 24/07)

Passo **obrigatório** ao abrir/retomar o trabalho de geração (Eixo A) de uma classe num
pavimento novo: gerar o painel HTML de comparação N2×N4 com pan/zoom real, ANTES de
qualquer sessão de refinamento do gerador. É o caminho do dono para apontar erro visual
item a item e do agente corrigir a causa geral no motor — mais rápido que abrir
`g2v_harness.py` a cada iteração (esse continua obrigatório só para o veredito de
selagem/certificação, não para iteração).

```bash
python scripts/arete/revisao_laj_n2_n4_html.py --pav {PAV} --serve --port {PORTA}   # LAJ, sobe servidor + abre navegador
python scripts/arete/revisao_pil_n2_n4_html.py --pav {PAV}   # PIL (ainda so localStorage/export, ver pendencia abaixo)
```

Gera `scripts/arete/relatorios/revisao_{classe}_n2_n4_{timestamp}/index_panzoom.html`,
um por item. Cada card tem checkbox "Validado" + campo de nota "Atenção". **LAJ (27/07):
persistência real em arquivo**, não mais localStorage/export manual — `--serve` sobe
`servidor_revisao_pil.py` (script genérico, serve qualquer pasta de revisão) apontado
para a pasta gerada; o JS do painel faz `fetch('/api/state', POST)` a cada mudança
(debounce 400ms) e `fetch('revisoes_humanas.json', GET)` ao carregar — grava direto em
`revisoes_humanas.json` dentro da pasta do relatório, sobrevive a fechar o navegador,
sem passo manual de exportar/importar. **Escolher uma porta livre** (já há sessões
concorrentes ocupando 8765-8768 nesta máquina; checar com
`Get-NetTCPConnection -State Listen` no PowerShell antes de fixar uma). Sem `--serve`
(ou para PIL ainda não migrado), cai no modo antigo localStorage — não altera o banco,
não sela gate, é só apresentação/triagem humana (mesma ressalva de sempre: HTML/checkbox
não é prova Arete).

- **LAJ** (`revisao_laj_n2_n4_html.py`, 24/07): **3 imagens lado a lado** — N2 puro
  (recorte humano), N2 com a área demarcada em laranja translúcido (o MESMO
  marco/contorno que o Comparison Engine desenha, via
  `src/core/n2_marco_highlight.py::motor_poly_from_recorte` — não é um cálculo novo, é
  o motor dinâmico real) e N4 (gerado da ficha, motor mais atual).
- **PIL** (`revisao_pil_n2_n4_html.py`, script original 21/07): 2 imagens (N2, N4),
  ainda sem o marco laranja, sem a 3ª imagem, e sem `--serve`/persistência em arquivo
  (só localStorage/export) — pendência se o dono pedir paridade com LAJ (extensão
  direta: mesmo padrão de `motor_poly_from_recorte` equivalente de PIL se existir +
  `highlight_polys` no render + o mesmo bloco `--serve`/`fetch('/api/state')` do LAJ).

**Fluxo de trabalho esperado:** dono abre o `index_panzoom.html`, navega pelos itens
(scroll do mouse = zoom, arraste = pan), escreve no campo "Atenção" o que está errado
item a item → agente lê as notas, identifica a causa geral no gerador (nunca hardcode
por item), corrige, regenera o N4 (`arete_runner.py --classe {C} --pav {PAV} --item
...` ou sem `--item` pra classe toda), roda o script de revisão de novo (mesmo comando,
timestamp novo) e volta pro dono conferir. Isso repete até o dono não ter mais
"atenção" nenhuma pra marcar — só então parte para o veredito formal de selagem
(`g2v_harness.py --backend cli`, agente lê PNG, ver §1.5).

Script fonte: `scripts/arete/revisao_laj_n2_n4_html.py` (adaptado de
`scripts/arete/revisao_pil_n2_n4_html.py`, mesmo padrão, ainda não generalizado num
único script parametrizado por classe — pendência futura, não bloqueia uso).
Marco laranja implementado como parâmetro opcional `highlight_polys` em
`scripts/arete/dxf_to_svg_casos.py::render()` (patch matplotlib sobre o mesmo `ax` do
DXF, mesma cor `Semantic.WARNING #ff9800` do Comparison Engine) — reutilizável por
qualquer ficha/painel futuro que precise do mesmo marco.

### Eixo B — Qualidade de INTERPRETAÇÃO (N1, diagnóstico duplo + triagem)
```bash
# 1. Gerar fichas (ÚNICO headless de fichas; --wait obrigatório em automação)
python scripts/arete/headless_sa_analise.py --obra {OBRA} --pav {PAV} [--secao classe] --wait
#    → fichas HTML N1-N4 (SVG) + 4 diagnósticos automáticos + arete_manifest.json

# 2. Triagem humana (dono marca checkbox nas fichas)
python scripts/arete/qa_error_review.py open --dir .../{secao}
python scripts/arete/qa_error_review.py read --dir ... --json   # Claude interpreta → JSONL

# 3. Concordância auto×humano (métrica de autonomia)
python scripts/arete/triagem_concordancia.py

# 4. Corrigir causa-raiz no motor (1 fix por causa) → regenerar (passo 1) → reverificar
```

#### Agente QA Global — orquestrador assistido do Eixo B

`scripts/arete/qa_evidence_auditor.py` é o auditor/executor assistido oficial
do Eixo B. Ele **não cria um segundo loop**: consome os artefatos e comandos
canônicos deste mapa, produz dossiê/scores/perguntas/achados e encaminha a mesma
causa pelo ciclo marcar → logar → corrigir → reverificar.

```bash
# Inventário de contrato por classe, sem mutação.
python scripts/arete/qa_evidence_auditor.py discover \
    --project-id {PROJECT_ID} --classe {LAJ|FV|PIL|LV|ALL} --include-sealed

# Revisão de item/campo/vínculo: usa o mesmo escopo do microciclo.
python scripts/arete/qa_evidence_auditor.py review \
    --project-id {PROJECT_ID} --classe {LAJ|FV|PIL|LV|ALL} --item {ITENS} --include-sealed
```

O QA pode iniciar um microciclo com o `headless_sa_analise.py` canônico e ler o
G2-V/N1-V resultante; não pode tratar o próprio relatório como prova visual,
executar script legado ou usar N2/N4 para alimentar N1/N3. Só um adaptador de
classe promovido e uma autorização humana explícita podem usar `apply`.

O RAG é parceiro consultivo do QA, não um segundo juiz: regras/exemplos T1/T2
citam fonte e ajudam a formular hipótese; evidência do item atual e veredito
visual continuam mandatórios. Ver `CONTRATO-QA-RAG-LOOPINGS.md`.

Microciclos com múltiplas tentativas usam o estado persistente oficial:

```bash
python scripts/arete/qa_loop_executor.py start \
    --project-id {PROJECT_ID} --classe {CLASSE} --item {ITEM} --nivel {N1|N3|N4}
python scripts/arete/qa_loop_executor.py list \
    --project-id {PROJECT_ID} --classe {CLASSE} --item {ITEM} --nivel {N1|N3|N4}
python scripts/arete/qa_loop_executor.py resume --run {RUN_ID}
```

Ele apenas orquestra os entry points desta seção, registra `state.json`,
`events.jsonl` e `RESUME.md`, limita tentativas e devolve a próxima ação. Não é
headless, gerador, comparador ou scorer alternativo. Regra ambígua, veredito visual,
QG7 e promoção RAG continuam checkpoints humanos.

O mesmo fluxo pode ser ativado pela skill Codex `$qa-global-evidencias` ou pelo
comando AIOS `/CAD:QAGlobalEvidencias-AIOS`. Ambos são apenas orquestradores: devem
chamar os entry points desta seção e jamais criar headless, gerador, comparador ou
scorer alternativo. PIL/FV/LV em revisão genérica produzem
`TRILHA_N1_OBSERVADA`, não selo de interpretação/painel.

#### Roteamento rápido: vínculo, N1 contextual ou motor visual

Não usar o headless SA para toda alteração. Escolha o menor teste que realmente
exercita a camada modificada:

| Alteração | Teste inicial | Headless SA? |
|---|---|---|
| hipótese de campo/vínculo **já persistido** | `qa_n1_field_probe.py --request ...` (inclusive cross-classe) | não; lê somente as colunas declaradas |
| hipótese já modelada no perfil da classe | `qa_profile_probe.py --classe ... --probe ... --item ... --project-id ...` | não; escopo obrigatório e PASS só dos checks |
| cobertura/proveniência do item persistido | `qa_evidence_auditor.py review --classe ... --item ...` | não; leitura do DB, segundos |
| cobertura PIL por identidade/faces/PARA/PASSA/montagem | `qa_pil_coverage.py --project-id ... --item ... --run-probes` | não; diagnóstico sem apply |
| investigação iterativa retomável | `qa_loop_executor.py list|start|resume|status` | só usa headless se a rota canônica exigir; nunca o inventa |
| fórmula pura de contrato N3 | `pytest` focado contrato→payload | não |
| geometria/estilo/cotas de gerador N3/N4 | gerador da classe `--item` + `ficha_motor_item.py` | não |
| paridade de campos contrato→payload→DXF→HTML | `qa_artifact_parity.py --spec ...` | não; não substitui visual |
| smoke N3 por contrato/variante | `qa_n3_smoke.py --classe ... --item ...` | não; identidade/texto/camadas, não geometria |
| extração/interpretação N1, associação CAD ou vínculo novo | `headless_sa_analise.py --secao --item --wait` | **sim**, contexto completo |
| certificação/regressão final | headless completo + gates aplicáveis | **sim** |

O QA rápido de vínculos testa o snapshot persistido; ele detecta incoerência e
falta de proveniência, mas não prova que uma mudança nova no extrator reconstruirá
o mesmo vínculo. Após tocar no motor N1, rode o microciclo headless.

O probe ultragranular declara cada campo, fonte, caminho e check. Pode cruzar
PIL/FV/LV/LAJ para responder uma hipótese localizada, mas seu `PASS` nunca aprova
o item ou a ficha completos. Overlay testa candidato sem gravar DB. Cache é
chaveado por versão, request, overlay e hashes das linhas mínimas consultadas.
Formato e exemplos: `docs/QA-FASTPATHS-CAMPOS-ARTEFATOS.md`. Premissas e
famílias específicas: `docs/QA-PERFIS-CLASSES-SA-N1-N3.md`.

Para inspecionar qualquer DXF N3/N4 isoladamente, sem Qt, DB ou trava global:

```bash
python scripts/arete/ficha_motor_item.py \
  --classe {PIL|LAJ|FV|LV} --item {ITEM} --nivel {N3|N4} \
  --artefato ROTULO={CAMINHO_DXF} [--json ROTULO={CAMINHO_JSON}] \
  [--contract ROTULO={CAMINHO_CONTRATO}] --open
```

A ficha individual registra caminho e SHA-256 de contrato, DXF, JSON, SVG e HTML. Ela é evidência de
iteração visual, não interpreta N1 e não substitui G2-V/G5-V quando o gate exigir
comparação canônica.

#### Microciclo N1 por item ou conjunto (canônico para iteração rápida)

Quando já existe um achado localizado, a investigação não precisa reabrir as fichas de
todo o pavimento. Use o **mesmo** entry point headless canônico, com a seção e os itens
alvo. Ele executa primeiro a análise SA completa para preservar o contexto estrutural e,
só então, filtra as fichas, os diagnósticos e a persistência para o conjunto pedido.

```bash
# Um item
python scripts/arete/headless_sa_analise.py \
    --obra {OBRA} --pav {PAV} --secao lajes --item L318 --wait

# Lote relacionado à mesma causa (também aceita lista separada por vírgula)
python scripts/arete/headless_sa_analise.py \
    --obra {OBRA} --pav {PAV} --secao lajes --item L318 L319 L326 --wait
```

Seções válidas: `pilares`, `lajes`, `fundos_viga`, `laterais_viga`. `--item` exige
`--secao`, para que um nome não seja associado à classe errada. A saída contém apenas os
cards e o diagnóstico dos itens pedidos; o diagnóstico numérico continua cego e exige
N1-V para qualquer decisão de interpretação:

**Concorrência por classe:** uma rodada **read-only** com exatamente uma `--secao`
(com ou sem `--item`) entra somente na fila da classe (`headless_sa_pil`, `_laj`,
`_fv` ou `_lv`). O lote completo de uma classe não espera as outras apenas porque
`--item` foi omitido. Microciclo persistente continua nessa fila somente com
`--secao --item`, pois é upsert parcial. Persistência de PIL/FV/LV reserva também
`headless_sa_beams`: esses donos escrevem o mesmo `beams.data_json` e não podem
calcular snapshots concorrentes dele. LAJ continua isolada dessa reserva.
PIL e LAJ, por exemplo, podem rodar simultaneamente sem compartilhar snapshot ou pasta
HTML: o estado é `estado_{PAV}_{secao}.json` e o pack recebe seção + PID. Dois ciclos da
mesma classe continuam serializados. A persistência granular faz somente upsert dos
itens pedidos e `delete_missing=False`; `headless_sa_db_commit` serializa somente o
curto BEGIN/COMMIT SQLite, em vez de bloquear as análises e os SVGs de outra classe.
Rodada sem `--secao`, multiclasse ou persistência sem identidade de item adquire
`headless_sa_global` e as quatro filas antes de começar; portanto espera os
microciclos ativos e executa com exclusividade. `--wait` permanece obrigatório.

```bash
python scripts/arete/g2v_harness.py \
    --classe {PIL|LV|FV|LAJ} --pav {PAV} --par n1xn2 --backend cli --item {ITENS}
```

**Integridade do ciclo:** o microciclo é para descobrir e reverificar uma causa com
rapidez, nunca para certificar o pavimento. Corrigir a fórmula geral (nunca um caso
hardcoded), rodar de novo os mesmos itens, ler os SVGs-fonte/HTML e registrar a triagem em
append-only. Todo toque em extrator compartilhado ou motor exige depois o headless
completo (`sem --secao/--item`, sempre `--wait`), comparação dos quatro diagnósticos e a
regressão/gate aplicável antes de fechar ou selar. `--persist-db` no microciclo só pode
ser usado com `--secao --item`: faz upsert dos itens selecionados e não apaga os demais.

#### Roteamento arquitetural obrigatório para N1 de FV, LV e PIL

Antes do passo 4, identificar o dono do erro conforme
`ARQUITETURA-INTERPRETADORES-VIGA-N1-ISOLADOS.md`:

- `BeamTracer`: somente captura de topologia/geometria bruta compartilhada;
- FV: `FundoVigaInterpreter`;
- LV: quatro contratos isolados — A Para, B Para, A Passa e B Passa;
- PIL: dois contratos isolados e exclusivos — Viga Para e Viga Passa.

Fix específico de uma classe não entra no `BeamTracer` e não pode escrever no slot de
outro contrato. Mudança legítima no `BeamTracer` exige regressão headless completa das
quatro classes, comparação das contagens de alerta e N1-V da classe afetada. O schema
N1 permanece imutável e N2/N4 nunca são entrada de interpretação.

### Sempre, ao fim de qualquer rodada
```bash
python scripts/arete/gerar_status.py   # docs/STATUS.md = fonte de verdade de números
```

## 1.4 — Registro de progresso por item (SA)

Além dos relatórios/JSONL canônicos, cada análise precisa acrescentar uma entrada
append-only no diário da sua classe, com fontes, hipóteses rejeitadas, decisão e
próximo gate. O modelo e a ordem especial de obras de treino (N2→N4→N1→N3)
estão em `docs/SA-ANALISE-PROGRESSO-POR-ITEM.md`; antes de cada item, abrir o manual
de classe em `docs/SA-ANALISE/CLASSES/{PIL,LAJ,FV,LV}.md`; os diários estão em
`docs/SA-ANALISE/HISTORICO/{PIL,LAJ,FV,LV}.md`. Esse diário não é fonte de
campos nem selo — aponta para DB, ficha, SVG e triagem schema v2.

## 1.5 — HIERARQUIA DE VALIDAÇÃO: G2 sozinho NÃO é Arete (decisão do dono, 03/07)

> **G2 é a validação de MAIS BAIXO NÍVEL.** Ele lê metadados do DXF e confere
> matemática semântica (contagens, valores de cota, tamanhos ±0.5cm). É deliberada e
> estruturalmente CEGO para: cota renderizada em cima de texto, painel torto,
> sobreposições, posição/estética — tudo que um humano vê em 2 segundos.
> **"G2 100% PASS" sem confirmação visual é ILUSÃO de Arete** — consome tokens dando
> voltas sem gerar resultado (palavras do dono). Jamais se apoiar só nele.

```
Nível 0 — G1 round-trip           dados da ficha sobrevivem N2→N4→N2′
Nível 1 — G2 canônico             matemática semântica (contagens/valores)  ← MÍNIMO, nunca suficiente
Nível 2 — G2-V veredito visual    SVGs-fonte lado a lado do recorte N2 (humano) × DXF N4 (robô);
                                  DOM/SVG preserva texto exato, cotas e geometria vetorial —
                                  REGISTRADO no relatório
Nível 3 — Dono (humano)           juiz final; único gabarito onde não há N2 (ex.: GRADES)
```

> **Quem dá o veredito do Nível 2:** a visão do agente CLI (Claude Code / Codex) lendo
> os SVGs-fonte e o manifesto vetorial — **única fonte de qualidade comprovada e a ÚNICA
> permitida hoje** (`g2v_harness.py --backend cli`). Backends de API permanecem proibidos;
> o harness não contém API nem captura raster. Caminhos explorados e decisões anteriores:
> `docs/VISION-VALIDACAO-CAMINHOS.md`.

**Regras operacionais (valem para TODA classe, TODA rodada):**
1. **Selar golden exige Nível 2 no mínimo:** G2 PASS torna o item *candidato*;
   a selagem só após veredito visual registrado (paths dos SVGs e leitura no
   relatório da rodada). Primeira selagem de uma classe/pavimento = varredura visual
   de 100% dos itens; re-selagens pós-fix = 100% dos itens tocados + amostra de 20%
   dos demais (alinha com DA-A4 do masterplan, agora endurecido).
2. **Declarar "Arete atingido" exige Nível 2 + Nível 3** (dono viu e não reclamou —
   silêncio após revisão dele conta; ausência de revisão NÃO conta).
3. **Relatório que diz "100% PASS" sem seção de veredito visual está INCOMPLETO** —
   tratar como candidato, não como resultado.
4. **A regra vale para TODO gate visual, não só o G2.** Todo número que compara desenhos
   tem um par visual obrigatório, sempre via `g2v_harness.py` (mesmo prompt, mesmo
   schema, backend cli):

   | Gate numérico (cego) | Veredito visual obrigatório | Comando |
   |---|---|---|
   | G2 paridade (N2×N4) | **G2-V** | `g2v_harness.py --par n2xn4 --backend cli` |
   | diagnostico_*_n1_n2 (N1×N2) | **N1-V** | `g2v_harness.py --par n1xn2 --backend cli` |
   | paridade N3×N4 (G5) | **G5-V** | `g2v_harness.py --par n3xn4 --backend cli` |
   | GRADES do PIL — onde HÁ recorte de grades (1º/2º/14º/TÉRREO/TIPO) | **GRADES-V** | `g2v_harness.py --classe PIL --par grades --backend cli` |
   | GRADES do PIL — onde NÃO há recorte (ex. 13_PAV) | **dono (Nível 3)** | ele olha o N4 grades, não há comparador |

   Aprovar/avançar qualquer um desses só com o número = alucinação de aprovação. NUNCA.
   > Nota GRADES: o recorte de grades é por SHEET do pavimento (todos os pilares numa
   > folha), não por pilar (masterplan AR-1'.E). O `--par grades` hoje entrega a leitura
   > visual do N4 grades via ficha HTML (para o agente/dono); o comparador NUMÉRICO
   > per-sheet recorte×N4 é a story AR-1'.E, ainda pendente. Onde não há recorte
   > (13_PAV), é só o dono — não force comparação.

> **Nota de estado (03/07):** os goldens selados hoje (FV 26/26, LAJ 31/31, PIL
> 35/35 do 13_PAV) foram selados no Nível 1 apenas — são CANDIDATOS aguardando a
> varredura visual das sessões de looping em andamento. Não re-anunciar como Arete
> concluído até o veredito visual passar.

### Scripts canônicos (a lista completa — nada além disto)

| Script (`scripts/arete/`) | Papel |
|---|---|
| `headless_sa_analise.py` | ÚNICO entry point de fichas (4 classes, `--secao`, `--item`, `--wait`). Rodada read-only de uma classe (com ou sem `--item`) usa fila e snapshot isolados por classe; microciclo persistente de classe/item também é parcial. Sem `--secao`, multiclasse ou persistência sem item usa lock global + quatro locks. Mantém análise SA contextual; execução completa mantém o commit único conforme `PERSISTENCIA-HEADLESS-SA.md` |
| `arete_runner.py` (+ `roundtrip_ficha`, `paridade_visual`, `ficha_adapter`, `gerar_n4_item`) | Gates N2→N4 + golden |
| `diagnostico_{pil,fv,lv,laj}_n1_n2.py` + `diagnostico_common.py` | Diagnóstico NUMÉRICO N1×N2 (já rodam DENTRO do headless; CLI avulso só p/ debug) — **cego, exige N1-V** |
| `g2v_harness.py` | **VEREDITO VISUAL obrigatório** de todo gate visual: `--par n2xn4`(G2-V) / `n1xn2`(N1-V) / `n3xn4`(G5-V), `--backend cli` (agente lê a imagem). Ver §1.5 e `VISION-VALIDACAO-CAMINHOS.md` |
| `revisao_{laj,pil}_n2_n4_html.py` (+ `dxf_to_svg_casos.render(..., highlight_polys=)`) + `servidor_revisao_pil.py --serve` | Painel dinâmico N2×N4 com pan/zoom pra depuração humana do Eixo A, persistência real em `revisoes_humanas.json` via servidor local (LAJ, 27/07) — companheiro do `arete_runner.py`, não substitui `g2v_harness.py` na selagem — ver §"Painel dinâmico" logo acima |
| `qa_error_review.py` | Triagem humana (abrir/ler checkboxes) |
| `playwright_loop.py` | Legado de captura raster; não usar para gates. O veredito QA usa SVGs-fonte exportados por `g2v_harness.py --backend cli`. |
| `triagem_concordancia.py` | Rollup de concordância auto×humano |
| `gerar_status.py` | STATUS.md gerado (nunca escrever número à mão) |
| `single_instance.py` | Trava anti-OOM (biblioteca) |

---

## 2. QUARENTENA — gerações anteriores do loop (NÃO usar como entry point)

Inventário verificado no disco + grep de referências em 2026-07-03:

### 2a. Bibliotecas da app (o código importa; NUNCA rodar como loop)
| Script | Quem usa | Nota |
|---|---|---|
| `scripts/engrev_laj_recorte_loop.py` | `src/ui/modules/comparison_engine.py` | função interna da UI |
| `scripts/fv_loop_runner.py` | `src/ui/widgets/project_manager.py`, `analise_geral_headless` | idem |
| `scripts/laje_loop_runner.py` | `src/ui/widgets/project_manager.py` | idem |
| `scripts/fv_render_loop.py` | `analise_geral_headless` (→ `main.py`) | idem |
| `scripts/analise_geral_headless.py`, `laje_analise_geral_headless.py` | `main.py` / `laje_loop_runner` | bibliotecas apesar do nome "headless" |
| `scripts/arete/gerar_html_preficha_headless.py` | `playwright_loop` | CLI DESCONTINUADO (aborta sem `--legacy`); só biblioteca |

### 2b. Órfãos (zero referências — presumidos obsoletos, geração "vision loop" de 30/06)
`lj_vision_loop.py` · `lj_refinamento_loop_vision.py` · `lv_ab_prod_pav_loop_runner.py`
— superados pela decisão SVG/DOM (visão só para gestalt). Candidatos a mover para
`scripts/_loops_legado/` numa story futura, com ordem do dono.

### 2c. Cluster LV legado (25/06 — só se referenciam entre si + 1 masterplan antigo)
`lv_n2_vision_loop_runner.py` · `lv_n4_unit_loop_runner.py` ·
`lv_section_prod_pav_loop_runner.py` · `lv_section_visual_loop_runner.py`
— presumidos superados pelo harness LV novo (03/07: `preficha_lateral_html` +
`diagnostico_lv_n1_n2`). **Confirmar com a sessão LV antes de qualquer remoção.**
`docs/MASTERPLAN-LOOP-LV-N2-VISION-N4.md` referencia este cluster → marcar como
histórico quando o cluster for aposentado.

### 2d. Docs de loop superseded (história, não procedimento)
`LOOPING-EVOLUCAO-N2-VISAO-FICHA.md` · `MASTERPLAN-LOOP-TREINO-MOTOR.md` ·
`MASTERPLAN-LOOP-LV-N2-VISION-N4.md` — não seguir como execução.

---

## 3. Regra de contaminação zero

1. Sessão nova SÓ usa o que está na seção 1. Dúvida = perguntar ao dono, não improvisar.
2. Script legado que ainda for útil vira FUNÇÃO importada pelo caminho canônico —
   nunca um segundo entry point.
3. Todo refinamento futuro do loop ATUALIZA este mapa na mesma entrega (o refinamento
   que não atualiza o mapa é a origem exata da contaminação que este doc mata).
