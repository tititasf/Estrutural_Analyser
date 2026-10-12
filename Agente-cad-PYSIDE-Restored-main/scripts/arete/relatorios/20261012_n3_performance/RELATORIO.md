# Desempenho da cadeia N3→N5 — 12/10/2026

Escopo: item 6 de `docs/DIVISAO-FRENTES-2026-10-11.md`, com meta de 8 min. Medições feitas
na VPS, na cadeia real do portal (`POST /obras/<id>/cadeia-completa`, 13_PAV,
Obra_TREINO_1, INI, gradeadas). Os tempos vêm dos recibos em `portal_job_meta`.

## Linha do tempo (cadeia real)

| Job | Mudança | Pré | SA+N3 | N5 PL | N5 LV | FV | LJ | **Total** |
|---|---|---|---|---|---|---|---|---|
| 919ef2de | cache de buffer + N5 PL sem clone | 86 | 706 | 305 | 567 | 12 | 6 | **28 min** |
| f1b63c8a | + N5 LV sem clone | 103 | 608 | 326 | 329 | 11 | 9 | **23 min** |
| 3ba31cc6 | + estado SA lido uma vez por lote | 86 | 651 | 317 | 330 | 11 | 6 | **23 min** |
| 17839d44 | + orçamento de RAM do LV medido (2 workers) | 92 | 641 | 318 | 149 | 13 | 6 | **20 min 19 s** |
| 461cac59 | (nenhuma, portal com horas de uso) | — | headless 771 | — | — | — | — | lenta: 1 worker |
| 7cfc1bc0 | + #6 cache de página + #7 ids no fingerprint (portal recém-reiniciado) | 93 | 640 | 349 | 173 | 16 | 10 | **21 min 21 s** |
| 4a15763b | (nenhuma; tags acertam o cache: 5,8 s) | 102 | 1006 | 399 | 382 | 14 | 8 | **31 min 51 s** |
| 0087a302 | (nenhuma; tags 4,6 s) | 101 | 915 | 394 | 176 | 15 | 10 | **26 min 51 s** |
| bdc6d268 | + #8 auto_publish pula obra com job | 95 | 644 | 342 | 327 | 13 | 8 | **23 min 49 s** |
| f2f62b37 | + #9 orçamento por worker N3 medido + #10 N5 em processo filho | 92 | 614 | 356 | 172 | 13 | 9 | **20 min 56 s** |
| 78f1f09d | (nenhuma; regime estável, tags 3,5 s, gate 59 s) | 112 | 478 | 339 | 157 | 11 | 9 | **18 min 26 s** |

As cadeias 4a15763b e 0087a302 mostram o problema que as correções 8–10 atacam: sem
mudar o código, a mesma cadeia variava de 21 para 32 min conforme o portal acumulava
memória e o poller disputava CPU. Em bdc6d268 e f2f62b37 as tags erraram o cache por
motivo legítimo: o fingerprint inclui o hash do código, e cada publicação o muda.

A medição anterior (11 min 22 s, 08/10) era de um pavimento menor (TIPO_TESTE). Os
números acima são do 13_PAV completo.

## Correções (uma por causa, saída idêntica comprovada)

| # | Causa medida | Correção | Prova | Backup VPS |
|---|---|---|---|---|
| 1 | `extend_normal_soffit` refazia o buffer do mesmo footprint 142 mil vezes, e `merge_opposite_arrivals` recalculava por par | `_buffered_footprint` com lru_cache + memo por linha (`fv_inverted_crossings.py`, `lv_inverted_crossings.py`) | estado idêntico byte a byte; fundos efetivos de 25,6 para 13,1 s | `bak_n3perf_buffer_cache_202610112300` |
| 2 | N5 PL: `finish` fazia 2 `clone()` (write+read do DXF inteiro) por folha | removidos (`n5_ini_frames.py`) | 28 folhas, 57.818 entidades, blocos e layers iguais; de 258 para 162 s | `bak_n5_ini_noclone_202610120330` |
| 3 | N5 LV: 3 `clone()` por peça e por folha, 174 s de 417 s no perfil. Cada peça tem doc próprio (`paginate_ab` relê por janela) e é colocada uma vez | removidos (`lv_ini_packer.py`) | 27 folhas, 29.497 entidades, blocos, layers e manifest iguais; de 176 para 102 s por variante | `bak_lv_ini_noclone_202610121000` |
| 4 | `ler_estado_pavimento` (12,7 s) era refeito por cada variante N5 e por cortes e painéis | `estado_compartilhado()` (ContextVar, só a thread da cadeia, cópia por leitor de 0,24 s) | teste `tests/test_ficha_reader_estado_compartilhado.py`; prova na VPS: 2 variantes, 1 leitura | `bak_estado_lote_202610121130` |
| 5 | N5 serializado por orçamento fixo de 2 GB por worker, de antes dos fixes 2–3 | orçamento de 1 GB quando o lote é só LV (`n5_tasks.py`); pico medido: PL 1,5 GB, LV 0,77 GB | 2 variantes LV em paralelo: 109 s, contra 153 s em série; cadeia N5 LV de 330 para 149 s | idem #4 |

| 6 | O limite de workers (`render_worker_limit`) subtraía o `memory.current` do cgroup do cad-portal (MemoryMax 5 GB), e esse valor inclui *page cache*. Com 1,8 GB de cache, sobrava 1 worker: no job 461cac59 o headless levou 771 s (antes 422 s), com N3 LV em 256 s (antes 120) e tags PIL em 196 s (antes 104) | memória em uso = `current - inactive_file`, como no kernel/kubelet (`cad_render_cache.py`) | `tests/test_render_worker_limit_page_cache.py`; teste antigo do orçamento continua passando | `bak_workers_tagcache_202610120755` |
| 7 | O cache de tags PIL nunca acertava, porque o SA grava um `uuid4` novo em cada vínculo de laje (`main.py:11082`) e o fingerprint fazia hash das linhas brutas. Diff bruto entre 2 SA com o mesmo DXF: a única diferença são esses `id`. O exportador não lê esses ids, e o pack não embute nenhum dos 373 | o fingerprint descarta só as chaves `id` com formato uuid4 dentro das colunas JSON e do snapshot (versão 2) (`pillar_tag_cache.py`) | `tests/test_pillar_tag_cache_ids.py`; validação com 2 cadeias seguidas abaixo | idem #6 |

| 8 | O `auto_publish_poller` republica, a cada 60 s, todos os pavimentos de cada obra via `ler_estado_pavimento` (reconcile de fundos + cortes LV), no processo do portal. Depois do SA o cache de fundos é invalidado, e um ciclo chega a minutos (08:36 → 08:42). Ele disputa o GIL com o N5 e as pós-etapas, que rodam no mesmo processo, e pode publicar um estado pela metade. A cadeia B (4a15763b) teve SA+N3 1006 s, PL 399 e LV 382, contra 640/349/173 na A | obra com job na fila ou executando é pulada, e publica no ciclo seguinte ao fim do job (`auto_publish_poller.py`) | `portal/tests/test_portal_auto_publish_job_ativo.py` + 5 testes antigos | `bak_autopub_jobativo_202610120920` |
| 9 | O `render_worker_limit` supunha 1 GB por worker. Os workers spawn do N3 LV/PL medidos (amostrador de 3 s na cadeia bdc6d268) têm pico de 106–138 MB, então com 2,4 GB livres o N3 rodava com 1 worker | parâmetro `worker_bytes` (padrão de 1 GB inalterado); os chamadores N3 (`n3_local_tasks.run_local_tasks`, `pillar_n3_tasks.run_pillar_tasks`) passam 384 MB, cerca de 3× o pico | teste novo em `test_render_worker_limit_page_cache.py`; cadeia f2f62b37 com 3 workers: N3 LV de 122 para 87 s, PL de 128 para 92 s, headless de 444 para 375 s | `bak_n3workers_n5filho_202610120950` |
| 10 | Com 1 worker, o N5 rodava dentro do processo do portal. O PL leva o RSS do portal de 0,5 para 1,9 GB, e o heap não devolve a memória (fica em ~1,1 GB), o que rouba workers das cadeias seguintes | o lote de 1 worker roda num único processo filho (`n5_tasks.assemble_serial`), que mantém a leitura única do estado e devolve a memória no fim | `tests/test_n5_tasks.py` + `test_item_pending_production.py` (10 passaram); portal termina a cadeia f2f62b37 com 515 MB | idem #9 |

A correção #6 explica por que a cadeia piorava com o uso: o cache de página cresce
entre rodadas, e o paralelismo do N3 caía junto, sem nenhum aviso.

A correção #4 quase não aparece na cadeia: o processo do portal já mantém os caches
de buffer quentes entre leituras. Ela continua valendo para os processos novos.

## Commits

- `350a6df49`: `ficha_reader.estado_compartilhado` + teste. Só o trecho próprio; o
  arquivo tem trabalho de outras sessões.
- `ad821212e`: limite de workers sem *page cache* + teste.
- `7ec3d3b2d`: `auto_publish` pula obra com job ativo + teste.
- `0b5e5ebd4`: `render_worker_limit(worker_bytes=...)` + teste. As linhas dos chamadores
  (`n3_local_tasks.py`, `pillar_n3_tasks.py`, ambos untracked) estão publicadas e sem
  commit. Em `pillar_n3_tasks.py` só a linha própria foi para a VPS: a cópia local tem
  um trecho de outra sessão (contrato U) ainda não publicado.
- `pillar_tag_cache.py` (untracked, de outra sessão): publicado na VPS e com cópia local
  igual, sem commit. O teste `tests/test_pillar_tag_cache_ids.py` vai junto quando o
  módulo for commitado.
- **Sem commit (os arquivos são de outras sessões, untracked ou com drift):**
  - `fv_inverted_crossings.py` (hunk alheio em `merge_opposite_arrivals`);
  - `lv_inverted_crossings.py`, `n5_ini_frames.py`, `lv_ini_packer.py` e `n5_tasks.py` (untracked);
  - `pipeline_runner.py` (o bloco de cortes e painéis só existe no drift).

  Publicados na VPS só nas linhas próprias. As cópias locais têm as mesmas linhas.

## Achado de infraestrutura (precisa de ordem do dono)

`/dev/shm` (RAM) guarda 3,0 GB em pastas `sa-dev-cycle14-*` de 10/10, de ciclos dev
do Codex (`sa-dev-cycle14-guarded-20261010` e `-l410-` com 1,5 GB cada). Isso tira
RAM do N5: com cerca de 3 GB livres, o PL roda 1 worker. Com a RAM liberada, PL e LV
cabem em 3 workers.

O portal reinicia (`systemctl restart cad-portal`) a cada publicação. O amostrador
mostrou que, antes da correção #10, o RSS dele crescia de 0,25 GB para 1,1 GB por
cadeia e não voltava.

## Onde está o tempo agora (job f2f62b37)

- Pré-processamento: 92 s.
- SA+N3, 614 s:
  - headless de 375 s: análise ~60, merge ~28, N3 LV 87, N3 PL 92 + 35, com 3 workers;
  - pós-etapas no portal: cortes e painéis LV 21 s, tags PIL 121 s (erro de cache por
    código novo; com acerto, cerca de 5 s) e gate CAD 88 s.
- N5 PL, 356 s: base + PARA + PASSA em série, num processo filho, com pico de 1,9 GB
  (orçamento de 2 GB por worker).
- N5 LV, 172 s: 4 variantes em 2 workers.

Em regime estável (tags acertando o cache), a cadeia 78f1f09d fechou em 18 min 26 s
(headless 389 s, tags 3,5 s, gate 59 s, cortes 18 s), com as mesmas 60 pendências LV
pré-existentes de todas as cadeias.

## O que falta para 8 min (precisa de decisão)

1. **RAM da VPS (8 GB).** O N5 PL é o maior bloco serial que sobra (356 s): 3 variantes
   com pico de 1,9 GB cada. Com /dev/shm liberado (3 GB, ordem do dono), as 3 variantes
   cabem em paralelo, ~120 s. Um plano com mais RAM dá o mesmo efeito sem tocar em nada
   alheio.
2. **Gerar no N5 só as variantes que a obra usa.** A obra já declara comportamento
   (para/passa) e montagem (gradeadas). Gerar as demais sob demanda corta PL e LV pela
   metade. É decisão de produto.
3. **Gate CAD fora do caminho crítico.** Ele só avisa e nunca derruba o job (60–90 s).
   Rodar depois do N5, ou em paralelo, tira esse tempo do total. A parte PIL do gate
   (56 s de medição) é da Frente 1.
