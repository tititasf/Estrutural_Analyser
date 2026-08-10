# Diário SA — FV

Use o modelo de `docs/SA-ANALISE-PROGRESSO-POR-ITEM.md` e o manual
`docs/SA-ANALISE/CLASSES/FV.md`. Entradas são append-only e
registram segmento, contorno local/contextual, dimensão, apoios locais versus limite
global, furos/recortes e N3 FUNDO_C separadamente.

## 2026-07-14 — Obra_TREINO_1/13_PAV — V301, V305, V306, V307, V311

- Etapa: S4/S6 em auditoria; nenhum novo selo humano/Arete.
- Fontes: QA read-only `20260714_013430_review_26790848`; fichas canônicas
  `TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260714_015441`; N3 individual
  V301 em `scripts/arete/relatorios/qa_fv_n3_v301_20260714/`.
- Evidência: V301 tem 7 segmentos e cadeia de apoios P1→P8 no contrato/DXF
  N3; smoke FUNDO_C PASS. Não há furos/recortes FV persistidos neste pavimento.
- Caminho: SVG N1 local+contextual por segmento; vínculo persistido distingue
  `segment_local` de `beam_global`; cache N1 content-addressed.
- Próximo passo: G2-V/N1-V CLI do lote e registrar cada veredito visual; itens
  com exceção real seguem separados, sem inventar recorte.

## 2026-07-16 — Obra_TREINO_1/13_PAV — fechamento S7 e lote corrente

- **V305:** S3/S4 persistidos com contorno fechado local `286×19`, apoios
  `P26→P27`; diagnóstico N1×N2 em 0,05 cm e N1-V CLI PASS. O N3 individual
  veio exclusivamente do contrato N1, passou no smoke e no G5-V CLI N3×N4.
  Próxima evidência é somente a leitura S7 N3×N2; não houve selo agentico.
- **V329:** contorno local `141×19` e diagnóstico N1×N2 de dimensão/contagem
  PASS, mas G5-V encontrou apoio inicial `V331` no N1/N3 versus `P27` no N4.
  Foi devolvida a S5: investigar o contato no DXF/PIL e comparar a ficha, sem
  copiar N4 para N1 e sem atribuir automaticamente culpa ao gerador N3.
- **Harness universal:** G5-V passa a registrar também `apoios_segmento` para
  FV, além do checklist geométrico. É requisito por painel e distingue apoio
  local de limite global da viga.
- **Lote seguinte:** V308, V310, V312, V321 e V322 foram selecionadas porque
  N2 está azul e a comparação canônica já coincide em quantidade e medidas
  (0,05 cm). V308/V322 exercitam múltiplos segmentos. O N1-V SVG foi emitido;
  a regeneração FV isolada foi enfileirada com `--wait`, sem persistir DB,
  porque a ficha disponível era anterior à rodada corrente.

## 2026-07-16 — infraestrutura de microciclos FV

- Causa observada: uma persistência parcial PIL anterior tomou indevidamente a
  fila global, fazendo o microciclo FV aguardar apesar de a classe ser distinta.
- Correção universal: um microciclo `--secao --item` mantém a fila da própria
  classe também com upsert parcial. PIL/FV/LV reservam `headless_sa_beams`, pois
  os três podem serializar o mesmo `beams.data_json`; LAJ permanece concorrente.
  O escritor SQLite é exclusivo somente no lock curto `headless_sa_db_commit`.
- Consequência para FV: uma investigação read-only ou persistência FV não espera
  LAJ; só aguarda PIL/LV que possam produzir snapshot de viga concorrente. HTML,
  estado e diagnóstico continuam por seção/PID. Sem alteração de motor, campos
  N1 ou selos nesta entrada.

## 2026-07-16 — auditoria da fila concorrente

- Diagnóstico: na verificação não havia processo `headless_sa_analise.py` vivo.
  Os registros `headless_sa_pil` e `headless_sa_laj` estavam marcados
  `event=released`; são telemetria de execuções concluídas, não locks presos.
  Nenhum processo/artefato foi encerrado ou apagado.
- Causa histórica comprovada: o plano antigo promovia microciclo granular
  persistente a `headless_sa_global`; isso serializava desnecessariamente
  FV/LV/PIL/LAJ durante toda a análise. O plano modular vigente usa uma fila
  por classe, reserva `headless_sa_beams` somente para writer PIL/FV/LV e
  `headless_sa_db_commit` apenas durante `BEGIN/COMMIT`.
- Prova de regressão: `pytest -q tests/test_headless_partial_dependencies.py
  tests/test_sa_db_persistence.py tests/test_single_instance.py` = **32 PASS**.
  A matriz cobre coexecução LAJ+FV, bloqueio correto de writer de beams,
  lock global para escopo inseguro e liberação do SO.
- Regra operacional FV: investigue/read-only com
  `--secao fundos_viga --item ... --wait`; persista apenas item identificado.
  Se houver writer PIL/LV no mesmo `beams.data_json`, `--wait` deve aguardar
  esse recurso, nunca contorná-lo. A rodada completa permanece exclusiva.

## 2026-07-16 — contrato QA FV: existência não é booleano isolado

- Lote read-only: V309, V320, V325, V327 e V332. O QA encontrava uma pendência
  artificial porque `viga_fundo_seg_N_exists` não possui pontos próprios.
  A fonte estrutural do mesmo campo é o contorno local correspondente em
  `viga_fundo_seg_N_area_segs.contour`.
- Correção universal no auditor: aceita somente o contorno do mesmo índice
  se ele for fechado, tiver área positiva e papel `area_fundo`. O resultado
  permanece `TRILHA_N1_OBSERVADA` (nunca selo ou `apply`); linha/parede, área
  nula e outro índice continuam sem prova.
- Também foi excluído do contrato de ficha o `fv_is_h`/`seg_bottom` raiz:
  são metadados brutos do interpretador e podem divergir legitimamente dos
  painéis FV consolidados. A prova de segmento é `area_segs` e o espelho
  `links.viga_segs.seg_bottom`, não esse contador. Testes QA focados: **54 PASS**.

## 2026-07-17/18 — investigação de deslocamento/sobreposição N1 (V301), causa raiz localizada, sem fix ainda

- **Gatilho:** pedido do dono para validar visualmente (vision PNG full-render) todos os
  N1 de FV do 13_PAV; suspeita reportada de geometrias erradas/deslocadas, sobrepostas
  às linhas das vigas.
- **Método:** regeração headless read-only completa (`--secao fundos_viga`, 36 itens,
  run `TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260717_190752_400822_fundos_viga_8320`);
  diagnóstico numérico N1×N2 fresco (27 alertas, 16 `DIVERGENTE_SEGMENTOS`); leitura
  vision (PNG rasterizado via Playwright a partir do SVG da ficha — script
  `scripts/arete/tmp/_fv_n1_vision_pack.py`, não canônico, só desta sessão) de
  VF202 (6/6 segmentos em fallback sem ancoragem) e V307 (caso diagonal); análise
  direta dos dados persistidos (`beams.data_json`) para todos os 36 itens.
- **Achado 1 (FV-only, `main.py:7379`):** quando a segmentação de `process_beam_fv`
  não encontra um contorno já reparado cujo span bata, o código monta um retângulo
  ingênuo centrado em `b_pos` (posição do rótulo), sem nenhuma ancoragem às linhas
  DXF (`Added ... contour (bbox fallback)`). Atingiu ~50% dos segmentos do
  pavimento nesta rodada. Não confirmado como sempre visualmente errado (VF202
  passou por coincidência de `b_pos` bem centrado), mas é estruturalmente sem prova.
- **Achado 2 (V307, caso diagonal):** ficha N1 local mostra uma linha fina, não uma
  área fechada — já documentado como caso especial sem fórmula geral (`CLASSES/FV.md`).
- **Achado 3 (causa raiz confirmada, o mais grave):** em V301 (viga-referência,
  16 painéis), pares de segmentos consecutivos se sobrepõem fisicamente
  (ex.: seg3 `x=[1622,2040]` vs seg4 `x=[1722,2040]`, overlap de 318cm). Confirmado
  via `geometry_source` persistido: cada par tem um lado com
  `fundo_viga_interpreter_canonical_span_repair` e o outro com
  `fundo_viga_interpreter_overlay_position_repair` — as duas branches de reparo
  de `FundoVigaInterpreter.repair_area_links` (`src/core/beam_interpreters/fundo_viga.py`)
  convergindo para candidatos DIFERENTES para o mesmo índice de segmento, sem
  reconciliação. Instrumentação temporária (revertida) em `beam_tracer.py` confirmou
  que `_classify_lines`/MODO PAINEL (linhas ~1494-1618) produz estruturas de painel
  DIFERENTES (7, 8 ou 16 grupos) em invocações sucessivas para a MESMA viga dentro
  de UMA rodada — a fonte de `merged_bottom_groups_coords` que `canonical_span_repair`
  usa não é estável entre as múltiplas chamadas de `repair_area_links` que
  `process_pillars_action` (main.py:6251, 6348) e o próprio headless fazem por viga.
- **Não é dado stale de sessão anterior:** confirmado via `merge_analysis_item`
  (`src/core/sa_db_persistence.py`) que já existe lógica para descartar links FV não
  travados (`fundo_topology_is_locked`) entre rodadas — o problema é intra-rodada.
- **Escopo do fix (não aplicado nesta sessão):** tocar `repair_area_links` (já 100%
  isolado em `FundoVigaInterpreter`, fundo_viga.py) para fazer as branches
  `canonical_span_repair`/`overlay_position_repair` convergirem/reconciliarem por
  índice em vez de competir; e/ou tornar `_classify_lines`/MODO PAINEL determinístico
  entre chamadas (beam_tracer.py, compartilhado — regressão nas 4 classes se tocado).
  Repro isolado ainda não construído com `SpatialIndex` real (tentativa com dump de
  DXF cru por bbox produziu grupos divergentes do pipeline real, não reaproveitável
  como teste). Próximo passo: instrumentar/testar com fixture real de V301 (via
  `_FakeSpatialIndex` populada a partir dos 150 raw entities já extraídos em
  `scripts/arete/tmp/_v301_raw_lines.json`) antes de escrever o teste de regressão.
- **Nenhuma alteração de motor aplicada; nenhum selo tocado.** Achado aberto,
  pronto para vira story própria.

## 2026-07-18 — causa raiz corrigida (V301), extração de isolamento FV, achado novo (guarda de topologia)

- **Correção da hipótese de ontem:** a instrumentação tagueada por call site
  (não só por padrão de saída) provou que `_classify_lines`/MODO PAINEL
  (`beam_tracer.py`) **é estável** — `merged_bottom_groups_coords` de V301 saiu
  idêntico (16 spans, sem overlap) em duas rodadas independentes. O "7/8/16
  grupos diferentes" de ontem eram *call sites diferentes* (baseline interno de
  `_capture_fundo_geometry`, ocorrência FV, ocorrência LV — cada um com seu
  próprio propósito), não nondeterminismo do mesmo cálculo. `beam_tracer.py`
  não precisou ser tocado.
- **Causa raiz real, confirmada por leitura direta do DB:** em
  `FundoVigaInterpreter.repair_area_links` (`src/core/beam_interpreters/fundo_viga.py`),
  o branch `canonical_span_repair` só comparava **comprimento**
  (`abs(current_length - expected_length) > 0.05`) contra o span canônico
  atual — nunca a **posição axial**. Um contorno reaproveitado de rodada
  anterior (índice `viga_fundo_seg_N`, carregado do DB por
  `window.load_project_action()` antes do `repair_area_links` rodar) pode ter
  o comprimento certo mas estar fisicamente na posição de um índice vizinho
  (fronteira reclassificada entre rodadas). O comprimento batendo fazia o
  branch pular o reparo; o contorno stale sobrevivia com um `geometry_source`
  antigo (`overlay_position_repair` de rodada anterior) ao lado do vizinho
  reparado (`canonical_span_repair` da rodada atual) — dois segmentos cobrindo
  o mesmo vão físico.
- **Fix:** `canonical_span_repair` agora também verifica se a posição axial
  atual (`current_min/current_max`) bate com o span canônico (tolerância
  0.5cm); comprimento OU posição errados disparam a reconstrução. Teste de
  regressão sintético
  (`tests/test_beam_interpreters_architecture.py::test_fundo_canonical_span_repair_catches_same_length_wrong_position`)
  reproduz exatamente o padrão V301 (contorno do índice 1 preso na posição do
  índice 2, mesmo comprimento) — falha sem o fix (`0 == 1`), passa com ele.
- **Extração/isolamento (pedido do dono):** o bloco "FASE 1: Processar dados FV"
  do `main.py` (~230 linhas, dentro do método gigante `process_pillars_action`)
  fazia a MESMA decisão de reconciliação (`existing_contour`/`good_contour`/
  `_new_fv_link`) só que com checagem de posição **ainda mais fraca** (overlap
  de só 20% bastava; e `_automatic_contour_matches_dxf` tratava `None`
  (alinhamento ambíguo) como aprovado por omissão — `if match is False`, não
  `if match is not True`). Extraído para
  `FundoVigaInterpreter.reconcile_persisted_segments(...)` (mesmo arquivo do
  `repair_area_links`, já 100% FV-owned) com a MESMA correção de posição
  aplicada (`_fv_existing_contour_matches_canonical_span`, tolerância 0.5cm) e
  o guardrail de alinhamento corrigido (`match is not True` rejeita ambíguo).
  `main.py` agora só monta os parâmetros e chama o método; nenhuma lógica de
  decisão ficou lá.
- **Verificação end-to-end:** microciclo `--secao fundos_viga --item V301`
  antes/depois do fix. Antes: 16 segmentos, pares sobrepostos (mesmo padrão do
  achado de ontem). Depois: **15 segmentos, todos sequenciais, zero overlap**
  (só o índice 15, 41.5cm, ausente — igual antes E depois do fix, não é
  regressão introduzida aqui). Suíte pura (`test_beam_interpreters_architecture.py`
  + `test_fv_rich_segments.py` + `test_fv_n3_n4_contract.py` +
  `test_diagnostico_fv_n1_n2.py` + `test_qa_fv_lv_adapters.py` +
  `test_preficha_segments.py` + `test_database_fv_topology.py`): **120 passed,
  0 regressão**. `test_fv_special_geometry.py` tem 8 falhas pré-existentes
  (N3 DXF de painéis em L/chanfro) confirmadas **idênticas** com e sem o fix
  via `git stash` — não são desta correção, ficam registradas como achado
  separado, fora de escopo desta entrada.
- **Achado novo, não corrigido — guarda de regressão de topologia bloqueia o
  fix em `--persist-db`:** `_non_regressive_beam_dependencies`
  (`scripts/arete/headless_sa_analise.py:390`) recusa uma viga cujo total de
  comprimento OU contagem de segmentos caiu entre rodadas
  (`old_coverage[0] > new_coverage[0]` ou `old_coverage[1] > new_coverage[1] +
  0.5`). Para V301 pós-fix: `old=(16, 5378.498cm)` [inflado pelo overlap] vs
  `new=(15, 3160.999cm)` [correto, sem duplicação] — a métrica não distingue
  "perdemos cobertura real" de "removemos sobreposição espúria", então
  bloqueia o fix como se fosse regressão. Histórico (`grep` nos logs de
  02→18/07) mostra esse MESMO guard recusando dezenas de vigas FV e LAJ há
  semanas — não é específico deste fix, é uma tensão estrutural pré-existente
  entre "proteger contra perda de cobertura" e "permitir correção válida que
  reduz sobreposição". Fora de escopo tocar agora (impacto cross-beam/cross-
  classe, decisão de produto sobre a métrica de comparação). Registrado para
  a próxima sessão: métrica deveria comparar extensão axial coberta
  (min/max do span), não soma de comprimentos, para não penalizar remoção de
  overlap.
- **Pendente para fechar o achado de ontem:** os 3 arquivos temporários em
  `scripts/arete/tmp/` (`_fv_n1_vision_pack.py`, `_v301_raw_lines.json`) são
  scaffolding desta investigação, não canônicos — mantidos só como referência.
  Persistência real (`--persist-db`) do fix em V301 e nos demais itens FV
  segue bloqueada pelo guard acima; decisão de como destravar é do dono.
- **Nenhum selo tocado; nenhuma alteração em `beam_tracer.py` (compartilhado)
  — regressão ficou restrita a FV.**

## 2026-07-18 (cont.) — achado crítico: geometria com bug já está SELADA (13 vigas)

- **Verificação end-to-end completa revelou um bloqueio mais sério que o guard
  de regressão.** Rodada `--secao fundos_viga --item V301` usa o "fast path"
  (`_run_legacy_analysis`, sem `MainWindow`) — exercita `repair_area_links`
  (já corrigido) mas **não** passa por `process_pillars_action`/FASE1
  (`reconcile_persisted_segments`, a extração desta sessão). Resultado limpo
  (15 segmentos, zero overlap) nessa rodada não provava a extração, só o fix
  de posição em `repair_area_links`.
- **Rodada completa (`--secao fundos_viga`, sem `--item`) usa o caminho lento
  (`MainWindow` + `process_pillars_action`, onde a extração vive) e ainda assim
  reexportou a MESMA topologia antiga com overlap para V301**, apesar do log
  mostrar `-> Added ... contour (span canonico)` para os 16 índices (ou seja,
  a reconciliação rodou e decidiu reconstruir do zero — mas reconstruiu com a
  MESMA geometria velha).
- **Causa:** `fundo_topology_is_locked(V301) == True` — verificado direto no
  DB via `src/core/preficha_segments.fundo_topology_is_locked` e
  `src/core/sa_db_persistence._validated_topology_sources`. Os 15 links
  `viga_fundo_seg_N_area_segs` de V301 estão em `validated_link_classes` com
  origem `qa_agente` (timestamp `2026-07-17T21:09:08`, provavelmente de uma
  sessão QA anterior que rodou `qa_evidence_auditor.py apply` usando o
  `FvEvidenceAuditor`). Isso ativa `_lock_beam_topologies`
  (`sa_db_persistence.py`), que **restaura os links antigos do DB por cima de
  qualquer geometria fresca** — inclusive a correta, pós-fix. `process_beam_fv`
  também tem um branch dedicado (`fundo_topology_is_locked`) que lê
  exclusivamente `preficha_fundo_locked_source_keys`, ignorando o cálculo
  canônico atual inteiramente.
- **Escala do problema:** varredura nos 36 beams do projeto mostra **13 vigas
  com FV topology locked**: `V301, V303, V304, V305, V306, V307, V308, V309,
  V326, V329, V331, V332, VF203`. Não confirmei quais das outras 12 têm o
  mesmo padrão de overlap de V301 (não escopo desta sessão), mas TODAS estão
  igualmente protegidas contra qualquer correção futura no motor, corrija ela
  o que corrigir.
- **Por que isso é grave e não é só "mais um guard":** um selo `qa_agente`
  em FV deveria significar "geometria re-derivada e confirmada
  independentemente" (contrato `FvEvidenceAuditor`,
  `docs/PROVENIENCIA-CAMPOS-FV.md`) — mas a auto-validação que gerou esse
  lock **não pegou a sobreposição entre segmentos vizinhos** (só validou
  campo a campo: existência, dimensão, apoio local — não comparou segmentos
  adjacentes entre si). Um selo que deveria proteger geometria correta está,
  neste caso, protegendo o bug.
- **Não desfiz o lock.** Remover `validated_link_classes`/re-liberar a
  topologia de 13 vigas é uma decisão de produto (desfaz selo `qa_agente`
  já aplicado), não uma correção de motor — fica para o dono decidir:
  (a) invalidar/re-rodar os 13 locks FV com o motor corrigido e novo veredito
  visual, ou (b) tratar caso a caso. O fix em si (`repair_area_links` +
  `reconcile_persisted_segments`) está correto e pronto para qualquer viga
  **não travada**; para as 13 travadas, o motor corrigido só passa a valer
  depois que o lock for revisto.

## 2026-07-18/19 (cont.) — decisão do dono: selo `qa_agente` não trava topologia

- **Instrução direta do dono:** "que o selo do qa não travem". Implementado —
  não é mais decisão pendente.
- **Fix em duas funções, mesma regra:**
  `src/core/sa_db_persistence._validated_topology_sources` e
  `src/core/preficha_segments._reviewed_fundo_topology` (a segunda é a fonte
  de `fundo_topology_is_locked`, usada por `process_beam_fv` e por
  `lock_fundo_topology`). Regra: um campo/link só trava a topologia quando
  tem origem humana (`humano_app`/`humano_portal`, incluindo dado legado
  migrado por `migrar_validated_fields_legado` — que já era tratado como
  humano) **ou** quando não há nenhum rastro de origem em `validated_fields`
  (link marcado `validated=True` direto, fluxo anterior a 2026-07-13 —
  comportamento conservador preservado para não regredir cenários sem
  rastreamento). Origem **só** `qa_agente` não trava mais.
- **Por que essa regra e não "remove o lock inteiro":** o objetivo é
  desarmar especificamente o caso que causou o bug (auto-validação sem
  comparar segmentos vizinhos travando geometria errada), sem enfraquecer
  proteção de dado genuinamente humano nem mudar o comportamento de quem
  nunca passou pelo agente QA. `docs/CONVENCAO-SELOS-VALIDACAO.md` já
  documenta FV como `diagnostic_only` para o agente — este fix alinha o
  código compartilhado (que ainda tratava `qa_agente` com o mesmo peso de
  selo humano nesse ponto específico) a essa política já declarada.
- **Verificado direto no DB real (sem re-selar nada, só nova leitura da
  mesma linha):** `fundo_topology_is_locked('V301')` foi de `True` para
  `False` — o único lock de V301 era 100% `qa_agente`. Das 13 vigas
  originalmente travadas, 12 continuam travadas
  (`V303, V304, V305, V306, V307, V308, V309, V326, V329, V331, V332,
  VF203`) porque têm pelo menos um campo com origem `humano_app` genuína
  (conferido em V305: `{'humano_app'}`) — proteção humana preservada.
- **Regressão:** suíte completa (`test_beam_interpreters_architecture.py` +
  `test_fv_rich_segments.py` + `test_fv_n3_n4_contract.py` +
  `test_diagnostico_fv_n1_n2.py` + `test_qa_fv_lv_adapters.py` +
  `test_preficha_segments.py` + `test_database_fv_topology.py`): **120
  passed**. Cinco testes de `test_preficha_segments.py` quebraram na
  primeira versão do fix (exigia origem humana explícita, sem fallback
  conservador) — corrigido pela regra "sem rastro de origem = trava" acima;
  todos passam agora.
- **Escopo real do fix:** `_validated_topology_sources` também cobre LV
  (mesma função, `_topology_class` reconhece `FV` e `LV_{A,B}_{PARA,PASSA}`)
  — LV também é `diagnostic_only` pela mesma convenção, então a mudança é
  coerente para as duas classes. PIL/LAJ não são afetados (usam
  `_preserve_geometry_root`, mecanismo separado, já autorizado a travar por
  `qa_agente` desde 2026-07-15 conforme `CONVENCAO-SELOS-VALIDACAO.md`).
- **Tentativa de fix para o grupo `extractor_bug` (V309A/V311/V319/V320) —
  REVERTIDA, não funcionou.** Investigação: os 4 itens têm 1 segmento cada,
  contagem batendo com N2 mas comprimento divergindo por um delta que
  coincide exatamente com a largura/altura de um pilar `SEGUE` (V309A: 19cm =
  P10; V311: 24cm = P28; V319: 38cm = 2×19 = P32; V320 seg1: 19cm = P51
  `NASCE`) adjacente à extremidade curta. Hipótese: `main.py` (linha ~6215)
  só isenta pilares `NASCE` de virar obstáculo `PILAR_SOLIDO` — `SEGUE`
  (viga continua através do pilar) também vira `PILAR_SOLIDO`, cortando o
  fundo na face próxima quando o N2 espera a face distante. Tentei tratar
  `SEGUE` igual a `NASCE` (`PILAR_NASCENTE`, elegível a `_bridge_nascent_pillars`)
  em `main.py` e no fast path (`headless_sa_analise.py`). **Resultado: não
  mudou nada em V309A/V311/V319/V320 (comprimentos idênticos) e QUEBROU
  V301** (16 segmentos corretos → 9 segmentos com comprimentos sem sentido
  como 655cm) — a ponte usada para `NASCE` uniu painéis de V301 que têm uma
  junta física real entre si, não relacionada ao pilar `SEGUE` mais próximo.
  **Revertido nos dois arquivos.** Achado real, mas a causa dos 4 itens não é
  simplesmente "SEGUE não deveria cortar" — precisa de investigação mais
  funda (provavelmente inspeção direta do DXF nesses 4 pontos, não só
  inferência pela diferença numérica) antes de tentar de novo. Suíte
  purista (120 testes) confirmada limpa após o revert, com `--basetemp`
  isolado (havia colisão de `.pytest-tmp` com outra sessão rodando testes
  em paralelo no mesmo diretório — falso alarme, não regressão).
- **Verificação end-to-end fechada (2026-07-19):** rodada completa
  (`--secao fundos_viga`, sem `--item`, caminho `process_pillars_action`,
  read-only) rodou depois que a outra sessão (`pid=552`, persist-db) liberou
  o lock — sem intervenção, só aguardou na fila como manda a regra. Varredura
  de overlap nos 36 beams (`scripts/arete/tmp/_fv_overlap_scan.py`):
  **84 segmentos, 48 pares consecutivos, 0 overlaps** — zero em qualquer
  viga, não só V301. V301 especificamente: **16/16 índices presentes
  (1 a 16, nenhum faltando desta vez), todos sequenciais, zero sobreposição**
  — confirma a cadeia completa (`repair_area_links` +
  `reconcile_persisted_segments` + selo `qa_agente` não travando mais)
  funcionando ponta a ponta pelo caminho de produção real, não só pelo fast
  path ou pela leitura direta do DB. Fix fechado e verificado.

## 2026-07-19 (cont.) — triagem granular dos 26 alertas restantes: 11 não são bug, 6+ são causas distintas não-triviais

- **Contexto:** pedido do dono para investigação granular completa e garantia de
  que o motor funcione em TODOS os itens do 13_PAV, não só V301.
- **Quase-perda de trabalho:** outra sessão rodou `git stash` na árvore de
  trabalho inteira (compartilhada), revertendo temporariamente
  `fundo_viga.py`, `main.py`, o teste de regressão e este diário. Recuperado
  sem `pop`/sem tocar no stash (`git checkout stash@{0} -- <arquivo>`,
  cirúrgico por arquivo) — 120/120 testes confirmam integridade. **Risco real
  de árvore de trabalho compartilhada entre sessões concorrentes sem
  coordenação — o dono foi avisado.**
- **11 itens `INDETERMINADO` — NÃO são bug, fechados por triagem:**
  10 (V313/314/315/316/317/318/323/324/326/328) simplesmente não têm ficha N2
  para comparar (`n2 is None`) — sem gabarito, `PENDENTE` por definição, não
  falha do motor. **V303** é diferente: N1 retorna vazio (`n1 is None`) no
  diagnóstico, mas o estado bruto TEM os 6 segmentos com contagem/medida
  batendo N2 — todos com `status: "ignore"` (decisão humana explícita na
  preficha, `preficha_geometry_policy`). O motor está reagindo corretamente a
  uma escolha humana de pular o item; não é um gap do motor.
- **Grupo `extractor_bug` (contagem bate, medida diverge) — 3 causas
  DIFERENTES confirmadas, nenhuma corrigida ainda:**
  1. **V309A/V311/V319 (delta = múltiplo exato de largura de pilar):**
     instrumentação real (`_classify_lines`, revertida após uso) mostrou que
     `resolve_attached_support_faces` ancora a fronteira numa linha DXF real
     (ex.: V309A, `y=2661.038`, `x=[1197.9,1380.4]`) que É uma "face" válida
     pela definição geométrica atual (transversal, longa, dentro do vão do
     cap) mas **não pertence à V309A** — é o segmento de uma grade/referência
     de fundo compartilhada por VÁRIAS vigas ao longo da mesma linha (a
     mesma família de linhas que V301 usa legitimamente para os PRÓPRIOS
     limites, confirmado nos mesmos `x`). A função não verifica se a face
     pertence à viga sendo resolvida, só a posição geométrica. **Tentativa de
     fix (tratar pilar SEGUE como NASCE/não-obstáculo) testada e
     REVERTIDA — não mudou nada nesses 3 itens e quebrou V301** (16→9
     segmentos com medidas sem sentido). Corrigir de verdade exige um
     critério de "pertencimento" da face à viga (não só geometria/posição),
     ainda não desenhado nem testado.
  2. **V310/V331 (segmento extra de ~19cm colado ao segmento correto):**
     achado por DXF direto — o fundo real tem quina chanfrada/notched
     (borda esquerda mais longa que a direita, ex. V310: esquerda
     `y=[2490,2661]`=171cm, direita `y=[2509,2661]`=152cm, unidas por um
     conector horizontal em `y=2509`). O motor cria DOIS segmentos separados
     em vez de um polígono não-retangular único — mesma família de problema
     do chanfro do V307 (`interpretacao_fundos.html`: "chanfro diagonal:
     polígono segue borda real"), não uma regra geral simples.
  3. **V307 (diagonal):** já documentado antes, geometria degenerada
     (linha, não área) — caso especial sem fórmula geral.
  4. **V306:** delta de 0.10cm (254.10 vs 254.00) — dentro do ruído de
     precisão geométrica real, tolerância do comparador (0.05cm) é mais
     apertada que a variação legítima de coordenada DXF. Provavelmente não é
     bug, é tolerância excessivamente rígida do comparador — não confirmado
     com certeza, baixa prioridade.
- **Grupo `schema_gap DIVERGENTE_SEGMENTOS` (contagem de segmentos diverge)
  — pelo menos 2 padrões distintos, nenhum corrigido:**
  - **V322:** N1 tem 3 segmentos, N2 tem 2, mas o comprimento TOTAL bate
    exatamente (380=380) — N1 divide em dois o que deveria ser um segmento
    contínuo de 262cm (`112+150=262`). Causa ainda não localizada no DXF.
  - **V302/V304/VF202/VF203/VF301/V330:** divergências maiores, ainda sem
    diagnóstico de causa — não investigados em profundidade nesta sessão por
    limite de tempo. VF301 e VF203 têm divergência muito grande (N1 captura
    uma fração pequena do que N2 espera) — merecem prioridade alta na
    próxima rodada, podem ser um problema de captura mais sério que os
    outros (viga inteira mal detectada, não só um segmento).
- **Avaliação honesta do pedido "garanta que funcione em todos":** NÃO
  cumprido nesta sessão. O que está garantido e verificado: zero sobreposição
  de segmentos em qualquer viga (achado original, corrigido). O que
  permanece: pelo menos 4-6 causas-raiz distintas e não-triviais nos
  15 itens com divergência numérica real (excluindo os 11
  `INDETERMINADO`/`ignore` que não são bugs). Cada uma exige o mesmo nível de
  investigação que V301 recebeu (instrumentação real, DXF direto, teste de
  regressão, verificação end-to-end) — não é seguro nem honesto aplicar um
  fix genérico sem essa base para cada uma, dado que a única tentativa feita
  sem essa base (SEGUE→não-obstáculo) regrediu V301.

## 2026-07-20 — `split_bottom_spans_at_deeper_crossings` (regra de cruzamento por
profundidade) implementado, verificado end-to-end e **REVERTIDO** por regressão real

- **Contexto:** continuação de sessão (via export/retomada). A regra ficou
  implementada e testada só em unidade na sessão anterior (caso sintético
  V302×V320×V322, resultado 418/418/367.5 batendo com N2), mas a verificação
  end-to-end ficada pendente era exatamente o próximo passo.
- **Armadilha do fast path:** a primeira tentativa de verificação
  (`--secao fundos_viga --item V302 --wait`) rodou pelo **fast path**
  (`_fast_microcycle_section` em `headless_sa_analise.py` ativa esse atalho
  sempre que `--secao` + `--item` vêm juntos), que substitui
  `window.process_pillars_action` por um snapshot direto e **nunca chama o
  bloco de `main.py` onde o fix vive**. Esse caminho não prova nem refuta
  nada sobre o fix — só reflete o estado pré-fix. A verificação real exige
  rodar a seção inteira **sem** `--item` (caminho lento, via `MainWindow`).
- **Verificação end-to-end real (rodada completa, sem `--item`,
  `20260720_151540`):** comparada item a item contra o último baseline limpo
  (`20260719_173935`, 36 vigas, 27 alertas, 16 DIVERGENTE_SEGMENTOS + 9
  EXCELENTE + 11 INDETERMINADO):
  - **V302 (o caso-alvo do fix) continuou sem bater** — N1 passou de 6 para 7
    segmentos, ainda divergindo dos 6 segmentos lógicos esperados por N2
    (`[405.0, 418.0, 404.75, 418.0, 380.75, 223.28, 129.9]` vs N2
    `[375, 387.5, 418×4, 735, 238.5, 97.5]`). O fix não resolveu o problema
    que motivou sua criação.
  - **3 vigas que antes eram EXCELENTE regrediram para DIVERGENTE_SEGMENTOS:**
    - `V308`: N1 ganhou um estilhaço espúrio de 19cm colado ao segmento
      correto (`[253.0, 19.0]` vs N2 `[253.0, 291.0]` — o próprio N2 já
      divergia antes, mas o N1 piorou).
    - `V327`: fragmentação grave — N1 virou `[260, 18.55, 132.2, 260]` onde
      N2 espera um único segmento de 260cm.
    - `V332`: parte do fundo sumiu — N1 caiu para `343.25` sozinho onde N2
      espera 442cm.
  - Total: alertas subiu de 27→30, DIVERGENTE_SEGMENTOS de 16→19. **Mesmo
    padrão de risco já documentado no revert do SEGUE→não-obstáculo:** um fix
    geral testado só no item-alvo (ou só em unidade sintética) pode quebrar
    vigas não relacionadas quando a heurística de "zona de cruzamento" é
    aplicada com um critério de posição que não confirma que o cruzamento
    realmente acontece no ponto certo do vão — precisa de instrumentação
    real (por que V308/V327/V332 entraram numa `crossing_zone` sem ter,
    aparentemente, cruzamento perpendicular relevante) antes de tentar de
    novo.
- **Ação:** revertido por completo — `split_bottom_spans_at_deeper_crossings`
  removido de `fundo_viga.py`, chamada removida de `main.py` (loop FASE1
  volta a chamar `process_beam_fv` direto, sem pré-split), os 2 testes de
  unidade sintéticos removidos de
  `tests/test_beam_interpreters_architecture.py`. Suíte purista: 120/120
  (mesmo número de antes do fix, confirmando revert limpo). Verificação
  end-to-end pós-revert (`20260720_191445`, rodada completa sem `--item`):
  **idêntica ao baseline `20260719_173935` item a item** — 27 alertas, 16
  DIVERGENTE_SEGMENTOS, 9 EXCELENTE, 11 INDETERMINADO, nenhuma diferença de
  classificação em nenhuma das 36 vigas.
- **Estado da classe FV agora:** volta a ser exatamente o baseline de
  19/07 — zero overlap (achado original) corrigido e mantido; a regra de
  cruzamento por profundidade permanece uma hipótese não comprovada, precisa
  ser redesenhada com critério mais estrito de "o cruzamento realmente
  acontece dentro do vão desta viga" antes de qualquer nova tentativa.

## 2026-07-20 (cont.) — `split_bottom_spans_at_deeper_crossings` v2: 3 critérios
geométricos novos, causa raiz da regressão confirmada por instrumentação real,
zero regressão end-to-end, V308/V332 exatos, V302 melhora sem fechar

- **Instrumentação real (não sintética):** criado
  `scripts/arete/tmp/_fv_crossing_diag.py` — chama `_run_legacy_analysis`
  (mesmo motor canônico do fast path, com cache) e dumpa
  nome/pos/is_h/dimensao/`merged_bottom_groups_coords` das 36 vigas reais do
  13_PAV em `scripts/arete/tmp/_fv_all_beams_dump.json`. Script auxiliar, não
  canônico, mas reutilizável (mesmo padrão do `_fv_overlap_scan.py`).
- **Causa raiz confirmada com dados reais (não mais suposição):** a v1 só
  comparava a posição axial do "outro" feixe contra o vão próprio. Rodando a
  mesma lógica da v1 contra os 36 feixes reais, ficou provado:
  - **V308×V325:** V325 (19/120) tem posição x coincidente com o vão de
    V308, mas o PRÓPRIO vão de V325 (eixo y, `[2680.038, 3141.038]`) nunca
    chega perto de `y=1944.877` (posição transversal de V308) — 738cm de
    distância. Falso positivo puro por coincidência de coordenada em linhas
    diferentes do pavimento.
  - **V332×V301:** mesmo padrão — V301 (19/120) nunca alcança
    `x=4690.35` (posição transversal de V332) com nenhum de seus 16 vãos
    próprios.
  - **V327×V305:** este É um cruzamento geometricamente real (V305 alcança
    fisicamente `x=4383.5`), mas V305 (altura 55) e V327 (altura 50) são o
    MESMO patamar estrutural do 13_PAV — a distribuição real de alturas das
    36 vigas tem um gap claro (`{50:8, 55:17, 60:1, 66:1, 120:8, 192:1}`,
    nada entre 70 e 110cm); só o patamar 120/192 domina de verdade o
    patamar 50/66. 5cm de diferença nominal não é dominância.
  - Adicionalmente, tanto V308 quanto V332 (v1) geravam lascas de 10-19cm ao
    cortar perto da borda do vão — nem sempre a mesma causa do erro de
    alcance, um segundo defeito independente (corte sem validar tamanho do
    resultado).
- **3 critérios novos em `split_bottom_spans_at_deeper_crossings` (v2,
  `fundo_viga.py`):**
  1. **Alcance físico:** o outro feixe só conta se o PRÓPRIO
     `merged_bottom_groups_coords` dele contém a posição transversal desta
     viga (com margem de meia-largura). Elimina falsos positivos de
     coordenada coincidente em linha diferente do pavimento.
  2. **Dominância de profundidade (`_DEEPER_CROSSING_RATIO = 1.5`):** o
     outro feixe precisa ser pelo menos 1.5× mais fundo, não só nominalmente
     maior — justificado pelo gap real na distribuição de alturas do 13_PAV,
     não por ajuste ao caso V327 isoladamente.
  3. **Fragmento mínimo:** um corte que deixaria um pedaço menor que a
     largura do próprio feixe que cruza é descartado (artefato de borda, não
     painel real).
- **4 testes de unidade com coordenadas REAIS do 13_PAV** (não sintéticas)
  em `tests/test_beam_interpreters_architecture.py`: V302×V320×V322×V330
  (splita, 3 critérios passam), V308×V325 (não splita, critério 1),
  V327×V305 (não splita, critério 2), + 1 sintético isolando só o critério 3
  (fragmento mínimo, mais fácil de construir um caso controlado que com
  dados reais). Suíte purista: **124/124** (120 base + 4 novos).
- **Verificação end-to-end (rodada completa, sem `--item`, `20260720_202428`)
  comparada item a item contra o baseline `20260719_173935`:** **zero
  diferença de classificação em qualquer uma das 36 vigas** — 27 alertas, 16
  DIVERGENTE_SEGMENTOS, 9 EXCELENTE, 11 INDETERMINADO, idêntico. V308 e V332
  confirmados com **match exato** internamente
  (`n1=[253.0,291.0]==n2`, `n1=[442.0]... ` já não aparecem mais como
  candidatos a quebrar — permanecem EXCELENTE como estavam). V327 permanece
  EXCELENTE (nenhum corte, critério de dominância bloqueia V305).
- **V302 (caso-alvo original) — progresso real, mas ainda não fecha:** N1
  passou a ter 3 segmentos de exatamente 418cm (`[418.0, 418.0, 404.75,
  418.0, 380.75, 223.28, 131.72]`) contra 2 antes de qualquer fix; N2 espera
  4× 418cm + 375 + 387.5 + 735 + 238.5 + 97.5. Ainda DIVERGENTE_SEGMENTOS
  (delta 0.317, era 0.126 no baseline sem fix nenhum — pior em módulo, mas
  não regride a classificação porque já era DIVERGENTE antes). **Causa
  provável do gap restante:** a reconciliação final de segmentos acontece
  em `process_beam_fv`/`reconcile_persisted_segments` (suporte, obstáculos,
  merge de vãos adjacentes) DEPOIS do pré-split — este pré-split só corrige
  a entrada bruta (`merged_bottom_groups_coords`), não é dono da lógica de
  segmentação final. Investigar essa camada é o próximo passo, fora do
  escopo desta rodada.
- **Artefatos desta investigação:** `scripts/arete/tmp/_fv_crossing_diag.py`
  (dump real dos 36 feixes) e `scripts/arete/tmp/_fv_all_beams_dump.json`
  (snapshot usado nesta análise — pode ficar desatualizado se o motor N1
  mudar, reexecutar o script para refrescar).

## 2026-07-20 — mini-RAG (B1) estendido a FV: usar `--session-index` no `review`

MR-3 (`scripts/arete/relatorios/20260718_minirag_d0d1/MR3-RELATORIO.md`) mediu
que `qa_evidence_auditor.py review --classe FV --session-index <índice>` traz
**+7 entradas reais de `human_event_logs`** (status `CAPTURED`) que o `review`
sem `--session-index` não alcança — mesmo padrão de ganho que MR-1 provou em
LAJ. Regressão zero confirmada: 526/526 decisões idênticas com/sem o índice no
13_PAV. **Recomendação para próximas sessões FV:** passar `--session-index
scripts/arete/relatorios/qa_session_index/<obra>_<pav>` (construir com
`qa_session_index.py build` se não existir/estiver stale) nas revisões reais —
é consultivo, nunca confirma campo sozinho, só evita redescobrir contexto já
registrado em `human_event_logs`.

## 2026-07-20 (cont.) — VF202×V306: tentativa de "bônus de continuidade de
cadeia" em `_label_owns_points`, causa raiz real confirmada, fix revertido por
introduzir duplicação (não é o mesmo bug do crossing rule, é novo)

- **Contexto:** próxima causa raiz já mapeada (achado 3 da entrada
  17-18/07): VF202 rouba geometria de V306 em `_label_owns_points`
  (`beam_tracer.py`), função compartilhada FV/LV/PIL. Pergunta ao dono já
  respondida em sessão anterior (AskUserQuestion, ver `transcript.jsonl`
  exportado): **"Exigir proximidade mínima absoluta"**.
- **Instrumentação real:** `scripts/arete/tmp/_fv_label_dispute_diag.py`
  (monkeypatch de `_label_owns_points`, loga toda disputa envolvendo
  VF202/V306/VF203/VF301 com os scores reais). Achado: VF202 vence V306 numa
  cadeia CONTÍNUA de 2200cm (x=1603→3807), sempre pela MESMA margem quase
  constante (~22 unidades), porque os rótulos de VF202 (x=1393,75) e V306
  (x=1371,85) ficam a só 43 unidades um do outro — não é erro de distância
  pontual, é a ausência total de noção de "quem já é dono de uma cadeia
  contínua" no algoritmo (decisão ponto-a-ponto pura). V306 tem só 1
  ocorrência de rótulo no DXF (confirmado via `DXFLoader`), não tem uma
  segunda etiqueta mais perto do trecho distante pra vencer lá.
- **Análise que evitou um fix ilusório:** graph-distance (BFS/Dijkstra sobre
  a malha de entidades conectadas) foi cogitado e DESCARTADO por análise —
  para uma viga reta, distância de caminho ≈ distância euclidiana; um
  Dijkstra multi-fonte teria dado o MESMO vencedor (VF202), não teria
  corrigido nada. O sinal que falta não é geométrico, é "quem estabeleceu
  posse contínua primeiro" (momentum), não "quem está mais perto por
  qualquer métrica de distância".
- **v1 tentada:** `connection_bonus` em `_label_owns_points` — quando um
  candidato toca fisicamente (endpoint a ≤20 unidades) um ponto já
  capturado da PRÓPRIA cadeia em crescimento, credita 100 unidades de
  distância efetiva (justificado por ~5x a largura típica de fundo do
  13_PAV, suficiente pra vencer a margem real de ~22 unidades observada).
  Verificado com a mesma instrumentação: **V306 passou a vencer a cadeia
  inteira**, exatamente como esperado.
- **Regressão nova descoberta pela verificação end-to-end (não pular esta
  etapa nunca):** o bônus quebra a SIMETRIA da decisão. Antes, `_owns` era
  uma função pura de `(candidato, my_name)` — a mesma resposta objetiva não
  importa quem pergunta, por isso nunca havia duplicação apesar de N buscas
  BFS sequenciais independentes por rótulo. Com o bônus, CADA viga pode
  "vencer" pela própria perspectiva (minha distância-bônus < distância crua
  do outro) sem nenhuma visão de que o OUTRO, na sua própria vez, também
  vence pela mesma lógica. Resultado real (dump de
  `merged_bottom_groups_coords`): **V306 e VF202 passaram a capturar a
  MESMA faixa inteira de 2439cm, idêntica**, recriando sobreposição — a
  mesma classe de bug desta investigação inteira, só que entre nomes
  diferentes em vez de dentro da mesma viga.
- **Por que não é um patch simples:** a correção de verdade exige trocar N
  buscas BFS sequenciais independentes (uma por rótulo) por UMA competição
  simultânea multi-fonte (tipo Dijkstra/BFS por nível, com fila de
  prioridade global e exclusividade — quem reivindica primeiro globalmente
  tranca o candidato pros demais). É uma reescrita bem maior da função
  compartilhada por FV/LV/PIL, com risco maior do que qualquer fix desta
  sessão até agora. Ordenar o processamento por rótulo (quem processa
  primeiro vence) foi cogitado e descartado: a ordem no DXF é arbitrária
  (VF202 aparece ANTES de V306 nos `texts`, índice 359 vs 368) e não é um
  critério defensável — usar essa ordem faria VF202 vencer por acidente de
  posição no arquivo, não por estar certo.
- **Ação:** revertido por completo (`git checkout -- src/core/beam_tracer.py`
  — nenhuma mudança na árvore antes do checkout tinha sido commitada).
  Suíte purista revalidada: 124/124 (inalterada, o bônus não tinha teste de
  unidade próprio ainda — a regressão só apareceu na verificação end-to-end
  com dados reais, prova de que unit test sozinho não bastaria aqui).
- **Estado de VF202×V306 agora:** sem alteração, causa raiz confirmada com
  evidência real e completa, fix desenhado mas não implementado com
  segurança. Próxima tentativa precisa ser a competição multi-fonte
  simultânea com exclusividade global, não um bônus local — desenhar e
  testar isoladamente antes de tocar `beam_tracer.py` de novo, dado que a
  função é compartilhada por FV/LV/PIL e um erro aqui pode vazar para as
  outras duas classes sem que o harness de FV perceba.
- **Artefato desta investigação:**
  `scripts/arete/tmp/_fv_label_dispute_diag.py` (monkeypatch instrumentado,
  reutilizável pra qualquer disputa de rótulo — não canônico, só desta
  sessão).

## 2026-07-20 (cont.) — V306 (delta 0.10cm): tentativa de afrouxar tolerância
do comparador, REVERTIDA por teste nomeado já existente

- **Achado:** V306 diverge por só 0.1037cm (254.10 vs 254.00) — a geometria
  N1 mede a coordenada real do DXF, N2 vem de uma cota digitada arredondada.
  Análise isolada sugeria tolerância do comparador (`SEGMENT_LENGTH_TOLERANCE_CM
  = 0.05` em `diagnostico_fv_n1_n2.py`) mais apertada que a precisão real de
  anotação manual.
- **Tentativa:** afrouxar para 0.15cm. Rodada real confirmou o efeito
  isolado esperado (V306→EXCELENTE, nenhuma outra viga mudou, 27→26
  alertas) — mas rodar a suíte de testes do comparador antes de aceitar
  revelou `tests/test_diagnostico_fv_n1_n2.py::test_segment_measures_reject_tenth_cm_delta`,
  um teste NOMEADO explicitamente para garantir que um delta de 0.1cm seja
  reprovado — prova de uma decisão de QA já tomada deliberadamente em
  sessão anterior, contradizendo minha leitura isolada do caso V306.
- **Ação:** revertido (`git checkout --`), tolerância volta a 0.05cm. Lição:
  rodar a suíte de testes relevante ANTES de aceitar um fix, não só depois —
  um teste nomeado é evidência de intenção de design, não só cobertura.
- **Estado:** V306 permanece como falso-positivo conhecido do comparador
  (não é bug do motor, é 1mm de diferença entre geometria medida e cota
  arredondada) — não vale a pena reabrir sem entender por que a decisão
  anterior optou por manter 0.05cm estrito (pode haver um caso real de
  0.1cm que PRECISA reprovar, ainda não identificado).

## 2026-07-20 (cont.) — V310/V331 (quina chanfrada): fragmento residual de
~19cm identificado e descartado em `_classify_lines` (`beam_tracer.py`)

- **Achado por DXF direto (não inferência):** V310 tem 4 entidades reais na
  layer 3 formando um polígono L (não retangular): borda esquerda
  `x=1380.38` contínua de `y=2490` a `2661` (171cm); borda direita
  `x=1394.38` só de `y=2509` a `2661` (152cm); conector horizontal em
  `y=2509` ligando as duas; fecho em `y=2661`. O "divisor" real detectado
  pelo motor em `y=2509` é genuíno (existe um traço DXF ali), mas o split
  produz um fragmento de 19cm (`[2490,2509]`) que N2 nunca conta como
  segmento — nem soma seu comprimento ao painel vizinho (N2 = 152.0 exato,
  não 171). V331 tem o padrão idêntico (fragmento de 19cm colado a um
  painel de 201cm). Nenhuma outra das 36 vigas do 13_PAV tem esse padrão de
  fragmentos tocando (`gap≈0`) com um lado ≤25cm — confirmado por scan
  completo do dump antes de aceitar o fix.
- **Fix:** pós-processamento em `_classify_lines` (MODO PAINEL,
  `beam_tracer.py`) logo após `split_panels`: um fragmento ≤30cm que toca
  (`gap≤0.5`) um vizinho >30cm é descartado (não mesclado — o limite do
  vizinho grande não se move, replicando exatamente o comportamento do N2).
  Limiar de 30cm justificado pela distribuição real: menor painel FV
  confirmado no 13_PAV é 41.5cm (V301); a lasca observada é 19cm nos dois
  casos reais — 30cm fica no meio, sem risco de comer segmento real.
- **Verificação:** V310 → `[152.0]` exato a N2; V331 → `[201.0]` exato a
  N2. Suíte purista: 124/124 (inalterada — o fix não tem teste de unidade
  próprio ainda, adicionar antes de fechar). 2 falhas em
  `test_lv_canonical_face_units.py` confirmadas PRÉ-EXISTENTES (mesmo
  resultado com `beam_tracer.py` revertido via `git stash push -- <arquivo
  único>`), não relacionadas a este fix.
- **Pendente:** rodada end-to-end completa (`--secao fundos_viga`, sem
  `--item`) disparada para confirmar zero regressão nas outras 34 vigas
  antes de considerar fechado — ver próxima entrada com o resultado.

## 2026-07-20 (cont.) — verificação end-to-end do fix de fragmento residual:
V310 fechado, V331 revela um SEGUNDO bug pré-existente (duplicidade), zero
regressão nas outras 34 vigas

- **Rodada completa (`20260720_234245`, 36 itens, sem `--item`) comparada
  item a item contra o baseline imediatamente anterior (`20260720_202428`):
  única mudança de classificação é V310 (DIVERGENTE→EXCELENTE)**. 27→26
  alertas. Nenhuma das outras 34 vigas mudou.
- **V331 continua DIVERGENTE, mas por uma causa DIFERENTE, já existente
  antes deste fix:** antes, N1 mostrava `[19.0, 201.0]` com `larguras:
  [14.0, 19.0]` — o comparador só via a lasca de 19cm goma-mascarando um
  problema mais sério. Removida a lasca, sobrou `[201.0, 201.0]` — **duas
  detecções duplicadas do MESMO vão físico, com larguras diferentes (14cm e
  19cm)**, não uma. Confirmado que essa duplicidade já existia antes deste
  fix (evidência antiga já tinha `larguras: [14.0, 19.0]` — só o total de
  220cm, 19+201, escondia que eram 2 detecções, não 1 lasca + 1 painel).
  Causa raiz ainda não investigada — suspeita: duas ocorrências de rótulo
  "V331" (fv_is_h vs lv_is_h) produzindo geometria própria sem dedupe por
  centro, mesma família de risco do `_label_owns_points` (múltiplas
  ocorrências de texto por viga). **Não é regressão desta sessão, é um bug
  que já estava lá, agora visível.**
- **Estado fechado:** V310 confirmado EXCELENTE ponta a ponta. V331 seguiu
  como próximo achado a investigar (causa nova, duplicidade de detecção, não
  fragmento residual).

## 2026-07-20/21 (cont.) — V331: hipótese de índice órfão no DB testada e
DESCARTADA por verificação end-to-end; causa real ainda desconhecida

- **Hipótese investigada:** inspeção estática do DB (`beams.data_json` para
  V331, `project_id=dd238e47...`) mostrou exatamente 2 contornos persistidos
  — `viga_fundo_seg_1_area_segs` (19cm, largura 14, span antigo
  `[2441.038,2460.038]`) e `viga_fundo_seg_2_area_segs` (201cm, largura 19,
  span `[2460.038,2661.038]`), nenhum `validated=True`. Hipótese: com o fix
  do fragmento residual (V310/V331 acima) reduzindo o vão físico fresco de
  2→1, `reconcile_persisted_segments` só toca o índice que existe na
  computação atual (seg_index=1), deixando o índice 2 antigo órfão no
  dicionário `links` sem nenhum código removendo-o — reaparecendo como
  segmento fantasma na ficha final.
- **Fix implementado (mantido, é seguro mesmo não resolvendo V331):**
  `reconcile_persisted_segments` (`fundo_viga.py`) agora rastreia
  `touched_indices` durante o loop principal e, ao final, limpa qualquer
  `viga_fundo_seg_N_area_segs` cujo índice não foi tocado NESTA rodada E
  não tem `validated=True` em nenhum contorno (dado humano nunca é
  apagado). 2 testes de unidade novos com os dados reais do V331
  (`test_reconcile_persisted_segments_clears_orphaned_index_without_human_validation`,
  `test_reconcile_persisted_segments_never_clears_human_validated_orphan`).
  Suíte purista: 126/126.
- **Verificação end-to-end (rodada completa, sem `--item`, `20260721_002328`)
  comparada contra o checkpoint anterior (`20260720_234245`): ZERO diferença
  de classificação em qualquer viga — V331 continua exatamente igual
  (`n1=[201.0,201.0]` larguras `[14.0,19.0]`, idêntico byte a byte à
  evidência de antes do fix).** O fix não teve efeito mensurável nenhum no
  pipeline real (nem positivo nem negativo) — prova de que a hipótese do
  índice órfão estava ERRADA (ou incompleta) como explicação para V331,
  apesar de bater exatamente com o que a inspeção estática do DB sugeria.
- **Lição:** inspecionar o DB estaticamente e encontrar um padrão que
  "faz sentido" não é prova de que é a causa real — só a verificação
  end-to-end prova. A causa raiz verdadeira de V331 continua desconhecida;
  precisa de instrumentação AO VIVO de `reconcile_persisted_segments`
  (logar `segments` recebido de fato pelo caminho lento/`process_beam_fv`
  para V331 nesta rodada específica) antes de tentar de novo — não repetir
  o padrão de "parece óbvio pela leitura estática do código/DB".
- **Ação:** fix de limpeza de órfãos MANTIDO (seguro, testado, não regride
  nada, é uma melhoria estrutural genuína para o caso geral onde a
  contagem de segmentos diminui) — mas V331 permanece aberto, causa raiz
  real não identificada.
- **Fechamento da sessão 2026-07-20/21:** placar final desta rodada —
  10/36 EXCELENTE (era 9 no início da sessão), 15/36 DIVERGENTE (era 16),
  11/36 sem gabarito. Ganho líquido real e verificado: **+1 viga fechada
  (V310)**. Duas tentativas mais ambiciosas (cruzamento por profundidade
  v1, disputa de rótulo VF202×V306) foram corretamente revertidas após a
  verificação end-to-end revelar regressão ou quebra de simetria — nenhuma
  delas ficou no código final. Causas mapeadas e documentadas para retomada
  futura: V320/V322/V330 (mesmo território de risco do SEGUE/obstáculo que
  já quebrou V301 uma vez — não reabrir sem harness amplo), VF202×V306
  (precisa de competição multi-fonte, reescrita maior), V331 (causa real
  ainda desconhecida, próxima instrumentação precisa ser ao vivo não
  estática), V307/V309A/V311/V319 (não tocados nesta sessão).

## 2026-07-21 — 10 itens sem gabarito (INDETERMINADO) escaneados: nada
suspeito encontrado; V309A fechado (causa raiz real, não a suposição do
SEGUE) e V322 fechado de bônus

- **Scan dos 10 itens sem N2** (V313/314/315/316/317/318/323/324/326/328,
  excluindo V303 que já é `ignore` humano confirmado): nenhuma sobreposição,
  nenhum fragmento residual, nenhuma geometria degenerada. Os "trios
  idênticos" (V313=V315=V317 com a mesma geometria `[2067.038,2423.038]`;
  V314=V318 com `[2759.038,2991.038]+[2991.038,3141.038]`) são vigas em
  posições x DIFERENTES (2036.6/2473.6/2910.6 — espaçamento ~437cm
  constante) com o MESMO y — grade repetitiva real de colunas, confirmado
  por `pos` de cada rótulo, não duplicação/alias. Nada a reportar aqui.
- **V309A — causa raiz REAL encontrada por instrumentação ao vivo (não a
  hipótese antiga do SEGUE):** `resolve_attached_support_faces`
  (`fundo_viga.py`) exige que a "face" que prova a fronteira caia
  ESTRITAMENTE dentro do vão do cap (`cap_min+tol < face_axis <
  cap_max-tol`). A face que fecha a PRÓPRIA chapa de V309A senta
  EXATAMENTE na borda do cap (`face_axis == cap_max == 2680.038`) — a
  desigualdade estrita a descarta, sobrando só uma face mais distante (de
  V301, a mesma grade compartilhada já suspeitada) estritamente dentro do
  cap, que move a fronteira para 2661.038 (errado, produz 480cm em vez dos
  461cm reais). Instrumentação: `scripts/arete/tmp/_fv_support_face_diag.py`
  (monkeypatch que rastreia `_capture_fundo_geometry`→`resolve_attached_support_faces`
  por nome real da viga, dump de `caps`/`faces` reais).
- **V311/V319 NÃO passam por este mecanismo** (`resolve_attached_support_faces`
  retorna `panels_in == panels_out` sem nenhum candidato) — a suposição
  anterior de "mesma família" estava errada; causa real ainda não
  investigada para esses dois.
- **Fix:** condição trocada de estritamente-dentro para inclusiva
  (`cap_min-tol <= face_axis <= cap_max+tol`) — a regra de desempate já
  existente (`min(candidates, key=lambda v: abs(v-endpoint))`, prefere o
  candidato mais perto do limite atual) já escolhe certo assim que a face
  própria participa da disputa; não precisou de nenhuma lógica nova de
  pertencimento. Teste de unidade com os dados reais do V309A
  (`test_fv_keeps_boundary_when_own_face_sits_exactly_at_cap_edge`) +
  confirmação de que `test_fv_uses_proven_inner_support_faces_not_outer_cap_edges`
  (o teste que já protegia o cenário real do V301) continua passando sem
  alteração. Suíte purista: 127/127.
- **Verificação end-to-end (rodada completa, sem `--item`, `20260721_004432`)
  comparada contra o checkpoint anterior (`20260721_002328`): 26→24
  alertas, 10→12 EXCELENTE.** Duas vigas fecharam: **V309A** (o alvo,
  461cm exato) e **V322** (bônus não previsto — mesma causa raiz real:
  cruzamento com V307/pilar perto de x=3784-3807 tinha o mesmo padrão de
  face-na-borda-do-cap). Zero regressão em qualquer uma das outras 34
  vigas, incluindo V301 (idêntico byte a byte às 8 fronteiras já
  verificadas antes).
- **Placar atualizado desta sessão (2026-07-20/21 combinadas):** 12/36
  EXCELENTE (era 9 no início), 13/36 DIVERGENTE (era 16), 11/36 sem
  gabarito. Ganho líquido real e verificado nesta sessão: **+3 vigas
  fechadas** (V310, V309A, V322), todas com instrumentação real e
  verificação end-to-end antes de aceitar — nenhum fix aceito só por
  "parecer certo" na leitura estática do código.

## 2026-07-21 (cont.) — revisão visual (vision) dos 13 divergentes via
subagente; V320 investigado, fix tentado e revertido por quebrar cap
terminal do V301 (mesma pergunta SEGUE/NASCE de sempre)

- **Vision pack gerado** para os 13 itens divergentes
  (`scripts/arete/tmp/_fv_n1_vision_pack.py`, PNGs em
  `scripts/arete/tmp/vision_divergentes/`) e revisado por subagente
  (contextual N1 + N2 par a par). Achados relevantes que não estavam nos
  números:
  - **VF202 e VF301 têm imagens quase pretas/em branco** — indício de
    bounding-box de auto-fit explodindo por coordenada outlier, sugerindo
    geometria em local fisicamente errado (rouba de vizinho), não só
    déficit de medida. VF202 confirmado roubando território perto de
    V319/V330.
  - **V330**: o realce N1 para exatamente em V330/P18; o segundo vão
    inteiro que N2 espera (183cm, rumo a VF301) está visivelmente ausente
    — não é erro de medida, é um vão inteiro nunca capturado.
  - **V331**: confirmação visual direta da duplicação (os 2 segmentos N1
    realçam a MESMA área hachurada, já suspeitado numericamente antes).
  - **V307**: confirmação visual do chanfro diagonal em P25 — já
    documentado como caso especial sem fórmula geral.
  - **Padrão novo identificado pelo subagente**: V311/V319/V320 têm déficit
    batendo com a largura de seção do pilar adjacente — sugestão de "corte
    pela face do pilar em vez do eixo".
- **V320 investigado com instrumentação real** (`_fv_support_face_diag.py`
  estendido): o painel bruto de V320 JÁ chegava correto em
  `resolve_attached_support_faces` — `panels_in` já tinha
  `(2661.038, 2781.538)` = 120.5cm, batendo exato com N2. A própria função
  desfaz isso, movendo para `(2680.038, 2781.538)` = 101.5cm (errado) via
  o fallback "sem face longa, chapa ocupa material, recua por padrão" —
  não há face comprovando o corte, mas o fallback corta mesmo assim.
- **Tentativa:** remover esse fallback por completo. Resultado real via a
  mesma instrumentação: **V320 corrigido** (painel fica 120.5, sem
  mudança), V309A/V311/V319 inalterados — **mas V301 quebrou**: o painel
  final (terminal, 4259→4552) que deveria virar `(4244.0, 4533.0)` (cap
  TERMINAL genuíno, protegido pelo teste
  `test_fv_uses_proven_inner_support_faces_not_outer_cap_edges`) passou a
  virar `(4244.0, 4552.0)` — incluindo indevidamente o pilar que realmente
  é o apoio final da viga ali.
- **Diagnóstico da causa do impasse:** V320 (pilar que a viga ATRAVESSA,
  corte errado) e V301 terminal (pilar que É o apoio real, corte certo)
  são estruturalmente IDÊNTICOS do ponto de vista desta função — mesmo
  padrão geométrico (painel já toca a borda do cap, sem face provando),
  resultado oposto esperado. A única distinção real é SEGUE (atravessa,
  não corta) vs NASCE/apoio real (termina, corta) — a mesma classificação
  de pilar cuja tentativa de uso já regrediu V301 uma vez antes (achado
  17-18/07, revertido). Essa classificação não chega até
  `resolve_attached_support_faces` hoje (a função só recebe linhas de
  evidência geométrica, sem semântica de pilar).
- **Ação:** revertido (`if candidates: continue` + fallback restaurados
  exatamente como estavam). Suíte purista: 127/127, idêntica.
  `test_fv_uses_proven_inner_support_faces_not_outer_cap_edges` voltou a
  passar. Comentário no código documenta a tentativa e a lição para quem
  retomar.
- **Próximo passo real, se alguém quiser fechar V320 (e possivelmente
  V311/V319, mesma família):** threading da classificação SEGUE/NASCE do
  pilar até `resolve_attached_support_faces` (hoje só existe em
  `pavimento_pillar_report`, acessível em `main.py`, não em
  `beam_tracer.py`/`fundo_viga.py`) — precisa de um parâmetro novo na
  assinatura da função, testado contra TODOS os caps terminais conhecidos
  (não só V301) antes de aceitar. Não tentar de novo sem esse dado.
- **Placar fechado desta sessão (2026-07-20/21, sem mudança desde o
  último checkpoint):** 12/36 EXCELENTE, 13/36 DIVERGENTE, 11/36 sem
  gabarito. Ganho líquido total da sessão: **+3 vigas fechadas** (V310,
  V309A, V322), 3 tentativas adicionais corretamente revertidas
  (cruzamento v1, disputa de rótulo VF202×V306, fallback SEGUE/NASCE do
  V320) — todas por verificação end-to-end real, nunca por assumir que
  "parece certo" bastava.

## 2026-07-21 (cont.) — protocolo Aegis (skill qa-global-evidencias) aplicado
retroativamente: N1-V (Nível 2) selado para V310/V309A/V322 via g2v_harness real

- **Contexto:** sessão ativou o skill `/qa-global-evidencias` (persona Aegis).
  Doutrina lida (`LOOPING-CANONICO.md` §1.5,
  `ARETE-LOOP-PROCEDIMENTO-GERAL.md`, `MASTERPLAN-AGENTE-QA-GLOBAL.md`,
  `CONTRATO-QA-RAG-LOOPINGS.md`): **G2/diagnóstico numérico sozinho NÃO é
  Arete** — todo fix desta sessão até aqui só tinha Nível 1 (numérico via
  `diagnostico_fv_n1_n2.py`). Faltava o veredito visual N1-V registrado via
  `g2v_harness.py --backend cli` antes de considerar V310/V309A/V322
  realmente fechados.
- **Achado de execução:** `g2v_harness.py --par n1xn2 --backend cli` emite
  SVG vetorial cru standalone (não embutido em HTML) — ilegível como texto
  puro (79k tokens só para 1 card). Construído
  `scripts/arete/tmp/_svg_to_png.py` (Playwright, navega direto no arquivo
  `.svg`, screenshot do elemento) para renderizar em PNG e permitir leitura
  visual real, consistente com a doutrina ("agente lê PNG").
- **Veredito visual real registrado** (não fabricado) em
  `scripts/arete/relatorios/g2v/20260721_011557/relatorio.json`:
  - **V310**: N1 local mostra faixa única (152cm) alinhada ao eixo
    estrutural entre V303/V302; N2 (V310.C) confirma 152cm exato, sem a
    lasca de 19cm de antes do fix. PASS.
  - **V309A**: N1 local mostra faixa contínua de P10 a P1 (461cm) alinhada
    ao eixo; N2 (V309A.C) confirma 461cm (244+217). PASS.
  - **V322**: N1 local (seg_1) alinhado ao eixo perto de P16; N2 (V322.C)
    confirma os 2 painéis esperados (118 e 262, este com marca interna
    122+140). PASS.
  - `inventario_minimo_extraido` marcado **false** com honestidade — o
    inventário mínimo formal (`QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md`)
    não foi construído como artefato JSON/MD separado nesta rodada; a
    evidência primária citada é o diagnóstico numérico + os SVGs/PNGs
    listados. Isso significa: **confirmação visual real e positiva, mas
    ainda não é o selo institucional QG3 completo** (falta essa peça do
    checklist formal) — registrado assim para não inflar o veredito.
- **STATUS.md regenerado** (`gerar_status.py`) ao fim da rodada, conforme
  doutrina — mas nota: aquele arquivo reflete o Eixo A (golden G0-G6,
  selado 03/07 em 26/26), não o Eixo B (interpretação N1×N2) que esta
  sessão trabalhou o dia todo. O placar real desta investigação continua
  neste diário + os JSONs de `diagnosticos_fv/`.
- **Aprendizado registrado para a squad:** o protocolo formal (Aegis,
  checklist de 15 campos, inventário mínimo, RAG citado, `qa_loop_executor`
  persistente) é mais pesado que o ciclo ad-hoc que esta sessão vinha
  usando (instrumentação real → hipótese → fix → teste unitário → E2E) —
  mas os DOIS convergem no mesmo princípio raiz: **número sozinho nunca
  fecha nada, só a leitura real (visual ou de dados brutos) prova**. As
  três reversões desta sessão (crossing v1, VF202×V306, fallback V320)
  já seguiam esse princípio antes mesmo do skill ser ativado — o skill
  formaliza e força o registro que a disciplina ad-hoc já vinha aplicando
  na prática.

## 2026-07-21 (cont.) — V330: 3ª tentativa no território pilar/obstáculo,
achado real forte, fix revertido (rouba geometria de V308)

- **Achado por DXF direto:** V330 para exatamente na borda de um pilar
  (cap fechado, `y=[2960.038, 3010.038]`), mas existe geometria estrutural
  REAL continuando do outro lado (`layer=3`, `x=4533.3825` e `x=4552.3825`,
  `y=[3010.038, 3207.038]`) que o BFS nunca captura — confirmado via
  instrumentação (`scripts/arete/tmp/_fv_capture_diag.py`, dump de
  `raw_bottoms` antes de qualquer merge): a captura bruta pára exatamente
  em `3010.038`, nunca alcança as linhas reais além do pilar.
- **Causa raiz localizada:** `_endpoint_connected` (dentro de
  `_capture_geometry_with_native_lines_experimental`, `beam_tracer.py`)
  tem uma regra deliberada — "uma LINE nativa não pode usar um apoio
  compacto como ponte para o vão do outro lado" — que existe pra evitar
  falsa travessia, mas bloqueia esta travessia REAL também. O pilar em
  si tem prova geométrica dos dois lados (arestas reais tocando as duas
  bordas do mesmo cap), mas a regra não distingue.
- **Fix tentado:** ponte condicional — só permite atravessar um apoio
  compacto quando existe uma linha JÁ CAPTURADA do outro lado do MESMO
  cap com a MESMA posição transversal (tolerância 2cm), provando que é a
  mesma aresta continuando (não coincidência). Testado isoladamente:
  **V330 capturou o vão que faltava** (299+197≈496cm vs 494cm esperado,
  quase exato).
- **Regressão real encontrada na verificação end-to-end:** V308 (antes
  EXCELENTE) passou a capturar 3 segmentos gigantes (413/413/415.5cm,
  ~1241cm) que pertencem a OUTRA viga — a mesma coordenada transversal
  (x ou y) se repete entre vigas DIFERENTES na grade estrutural regular do
  13_PAV (mesmo padrão de risco do caso VF202×V306: coordenada
  compartilhada não prova identidade da mesma viga). **Revertido**
  (`git checkout --`). Suíte purista: 127/127, idêntica.
- **Conclusão depois de 3 tentativas reais nesta mesma área hoje**
  (fallback `resolve_attached_support_faces` para V320, classificação
  SEGUE em `main.py` — já revertida em sessão anterior — e agora a ponte
  geométrica para V330): **qualquer heurística local (classificação de
  pilar, geometria de borda, coordenada transversal) generaliza mal
  neste ponto do motor**, porque a mesma pergunta ("esse pilar interrompe
  o fundo ou a viga atravessa?") tem respostas OPOSTAS em contextos
  geometricamente idênticos (cap tocado nos dois lados por uma aresta
  real). Provar "mesma viga" exige uma identidade mais forte que posição
  (ex.: rastro de conectividade desde o próprio rótulo, não só coordenada
  compartilhada) — arquitetura maior, mesma classe de problema do
  VF202×V306 (competição multi-fonte), não um ajuste local.
- **Recomendação para retomada:** não tentar mais heurísticas locais nesta
  função sem antes resolver a arquitetura de identidade de viga (rastro
  de conectividade desde o rótulo). V320, V330, V311, V319 e
  provavelmente parte de V301/V302/V304 compartilham essa mesma raiz —
  resolver uma resolve as outras juntas, mas exige a reescrita maior já
  documentada para VF202×V306.

## 2026-07-21 (cont.) — V331 (2ª tentativa): dedup real implementado e
seguro em `restore_locked_fundo_topology`, mas NÃO é a causa da duplicação
observada — causa real ainda mais profunda (incremental/process_beam_fv)

- **Instrumentação AO VIVO (não estática) desta vez**
  (`scripts/arete/tmp/_fv_v331_live_diag.py`, monkeypatch em
  `reconcile_persisted_segments`, caminho lento real sem `--item`): capturado
  o log real `"DEBUG: Fundo validado de V331 restaurado sem permitir novos
  segmentos"` e confirmado que `process_beam_fv` já entrega 2 segmentos
  com **coordenada idêntica** (`seg_index=1` e `seg_index=2`, ambos
  `coord=(2460.038, 2661.038)`, `length=201.0`) ANTES mesmo de
  `reconcile_persisted_segments` rodar.
- **Fix implementado (seguro, mantido):** `_drop_duplicate_locked_contours`
  em `preficha_segments.py` — quando `restore_locked_fundo_topology`
  restaura topologia travada (dado legado sem rastro de proveniência,
  protegido por padrão contra perda de possível dado humano), índices com
  contorno BYTE-IDÊNTICO (mesmos pontos, mesmo comprimento) colapsam para
  1 — geometria idêntica nunca pode ser 2 segmentos humanos distintos.
  Teste com dados reais do V331
  (`test_locked_fundo_restoration_drops_exact_duplicate_index`). Suíte
  purista: 128/128.
- **Verificação end-to-end: SEM EFEITO no resultado real.** V331 continua
  `n1=[201.0, 201.0]` idêntico a antes do fix. Isso prova que
  `restore_locked_fundo_topology` NÃO é a fonte real da duplicação neste
  item — o log "Fundo validado restaurado" dispara, mas a duplicação
  observada em `reconcile_persisted_segments` se forma DEPOIS, na própria
  `process_beam_fv` (`scripts/analise_geral_headless.py`) ou na interação
  com `preserved_beams`/restauração incremental (`main.py`, ~L5897-5909 —
  snapshot de `self.beams_found` ANTES da reanálise, usado pra preservar
  campos humanos, mas a fonte de onde ele lê antes disso — DB direto vs.
  algum cache intermediário — ainda não foi confirmada com instrumentação
  real).
- **Ação:** fix de dedup MANTIDO (correto e seguro para o caso geral, zero
  regressão) — mas V331 permanece aberto. **Duas tentativas reais
  hoje, duas causas erradas eliminadas com evidência real** (índice órfão
  não é a causa; contorno duplicado no lock não é a causa) — a causa
  verdadeira precisa de instrumentação dentro de
  `scripts/analise_geral_headless.py::process_beam_fv` diretamente, não
  mais na camada de reconciliação/lock.
- **Padrão que se repete nesta sessão inteira:** eliminar uma causa
  candidata com instrumentação real e prova concreta — mesmo sem resolver
  o item — é progresso genuíno, não fracasso. Cada tentativa reduz o
  espaço de busca pra próxima sessão.

## 2026-07-21 (cont.) — margem decisiva em `_label_owns_points`: simulada
ANTES de tocar no código, descartada com evidência real (quebraria V301)

- **Motivação:** a regressão do V308 (achado da tentativa da ponte
  geométrica do V330, revertida) e a disputa VF202×V306 são o MESMO
  problema raiz — vitória por margem fina (~22 unidades) numa distância
  longa (até 2400cm) em `_label_owns_points`. Hipótese: exigir margem
  decisiva (não só "qualquer tanto mais perto") pra confirmar posse,
  senão devolver `False` (não reivindicado por ninguém — vira lacuna, não
  erro positivo).
- **Simulação ANTES de qualquer edição de código** (script standalone,
  monkeypatch read-only de `_label_owns_points`, captura toda vitória com
  competidor real na margem transversal — 245 vitórias únicas nas 36 vigas
  do 13_PAV): testadas 3 configurações de margem (10%/10cm, 20%/15cm,
  5%/5cm). **Mesmo a configuração mais conservadora (5%/5cm) reverteria
  61 vitórias para "ambíguo" — incluindo o PRÓPRIO V301**
  (`my_dist=1272.1 vs other_dist=1291.0`, diff=18.9, abaixo da margem
  mínima de 63.6 exigida a 5%). V301 é a viga mais validada e protegida
  desta investigação inteira (16/16 segmentos, zero overlap, testada
  exaustivamente) — quebrá-la não é uma opção.
- **Conclusão com evidência real (não suposição):** margem fina numa
  distância longa é **comum e LEGÍTIMA** neste pavimento, não é um sinal
  confiável de erro — a mesma assinatura numérica (diferença absoluta
  ~20-25 unidades sobre uma distância de milhares) aparece tanto em casos
  ERRADOS (VF202 roubando V306) quanto em casos CORRETOS (V301). Nenhum
  limiar de margem, por mais conservador, consegue separar os dois sem
  sacrificar o segundo.
- **Ação:** ideia descartada SEM tocar em `beam_tracer.py` — nenhum
  código escrito, nenhum revert necessário. A pré-simulação evitou
  exatamente o padrão das 5 tentativas anteriores desta sessão (escrever
  → testar end-to-end → descobrir regressão → reverter). Esta é a
  primeira vez hoje que uma hipótese arquitetural foi eliminada SEM
  custar um ciclo completo de edição+verificação+revert.
- **Conclusão final sobre este território (5 tentativas reais hoje: v1
  cruzamento, bônus de cadeia, fallback SEGUE/NASCE, ponte geométrica,
  margem decisiva):** todas as abordagens baseadas em distância/geometria
  local falham pela mesma razão estrutural — coordenada ou proximidade
  nunca prova "mesma viga" numa grade regular de colunas. O fix real
  precisa de identidade rastreada por conectividade (grafo desde o
  próprio rótulo, competição multi-fonte simultânea com exclusividade
  global), não mais matemática de distância em qualquer forma. Essa é
  uma reescrita arquitetural de verdade — fora do escopo seguro de
  qualquer tentativa pontual adicional. V320/V330/V311/V319/VF202/VF203/
  VF301 (e possivelmente parte de V301/V302/V304) permanecem bloqueados
  por essa mesma causa raiz até essa reescrita ser feita, com harness
  amplo (FV completo + LV + PIL, já que a função é compartilhada) numa
  sessão dedicada.
