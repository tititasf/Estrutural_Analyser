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
