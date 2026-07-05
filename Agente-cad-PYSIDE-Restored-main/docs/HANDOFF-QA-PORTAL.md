# HANDOFF-QA — Estratégia de Testes do Portal Soberano

**Autor:** Quinn (Guardian — Test Architect & Quality Advisor)
**Data:** 2026-07-05
**Escopo:** WS-B (portal & serviço), gates **P1–P5** do `MASTERPLAN-PRODUCAO-SOBERANIA.md`
**Status:** ATIVO — este documento é a especificação de testes. Vira arquivos `tests/test_portal_*.py` reais.
**Não relitiga produto:** decisões DP-1 a DP-14 e riscos R1–R9 são premissas fechadas. Este doc só **comprova** os critérios PASS já definidos.

---

## 0. Princípios da estratégia (por que testar assim)

1. **Cada teste amarra a um critério PASS de gate.** Nenhum teste "solto" — a §7 é a matriz de rastreabilidade (teste → gate).
2. **Degradação, não queda.** R5/R8 são o coração da soberania operacional: dependência externa fora do ar = `logar + reagendar`, nunca `crash`. Testes de degradação são de **primeira classe**, não afterthought.
3. **Reusar o que existe.** A exclusão mútua da fila estende `scripts/arete/single_instance.py` (já testado em `tests/test_single_instance.py`) — não reinventar lock. A validação E2E chama o pipeline headless **real** (`scripts/arete/headless_sa_analise.py`), não um dublê.
4. **Fronteira de escrita é invariante testável.** O portal **lê** artefatos e **grava apenas** obras/jobs/comentários. Um teste de fronteira prova que ele nunca escreve em `GOLDEN/`, fichas, regras ou tabelas de curadoria (§3 do masterplan, invariantes 1–2 da harmonização).
5. **Parsing nunca executa conteúdo.** ezdxf apenas (`ezdxf.readfile`/`ezdxf.recover`), jamais `exec`/`eval`/`pickle.load`/import dinâmico de arquivo recebido (R6).

**Framework:** pytest (config em `pyproject.toml`, sem `pytest.ini`). Testes headless/sem-GUI rodam com `python -m pytest tests/`. Testes que tocam Qt vão no `collect_ignore` do `conftest.py` (mesmo padrão dos `test_fundo_*`). Os testes do portal são **todos sem GUI** (FastAPI + poller + fila são headless) — não precisam de sessão desktop.

**Nomenclatura de arquivos-alvo (a criar):**

| Arquivo de teste | Cobre | Código-alvo (a criar em WS-B) |
|---|---|---|
| `tests/test_portal_drive_poller.py` | §1 poller | `scripts/portal/drive_poller.py` |
| `tests/test_portal_upload_parsing.py` | §1 parsing/R6 | `scripts/portal/upload_guard.py` |
| `tests/test_portal_job_queue.py` | §2 fila/exclusão mútua | `scripts/portal/job_queue.py` (estende `single_instance`) |
| `tests/test_portal_e2e_obra.py` | §3 E2E | pipeline headless real |
| `tests/test_portal_security.py` | §4 R6/R8 | `upload_guard.py` + `drive_poller.py` |
| `tests/test_portal_n5_release_label.py` | §5 R9 | `scripts/portal/n5_release.py` |
| `tests/test_portal_service_recovery.py` | §6 P3/P5 smoke | serviço FastAPI + supervisor |

> **Nota de contrato:** os módulos `scripts/portal/*` ainda **não existem** — estes testes definem a **interface** que o @dev deve implementar. Cada assinatura abaixo é um contrato executável. Escrever os testes primeiro (TDD) é recomendado, mas não obrigatório.

---

## 1. Testes unitários

### 1.1 Poller do Google Drive (`test_portal_drive_poller.py`)

**Código-alvo:** `scripts/portal/drive_poller.py` — função `poll_once(drive_client, seen_store, download_dir) -> list[IngestedFile]` (uma varredura; o loop periódico chama isto).

**A API do Drive é sempre mockada.** Nenhum teste toca a rede. O `drive_client` é injetado (dependency injection) — em teste, um fake que retorna `files().list()` pré-programado.

| # | Teste | Given / When / Then |
|---|---|---|
| U1.1 | Detecção de arquivo novo | **Given** store vazio e Drive fake com 1 arquivo `obra_x.dxf` (id=`f1`) na pasta do usuário **When** `poll_once` roda **Then** retorna 1 `IngestedFile` com `user_login`, `file_id=f1`, e o arquivo aparece baixado em `download_dir` |
| U1.2 | **Idempotência (o núcleo)** | **Given** store já contém `f1` (marcado como visto) **When** `poll_once` roda com o mesmo Drive fake **Then** retorna `[]` — não rebaixa, não reprocessa. Verificar via contador de chamadas de download no fake (`assert fake.download_calls == 0`) |
| U1.3 | Idempotência por conteúdo, não só por id | **Given** `f1` já visto; Drive retorna `f1` com `md5Checksum` **inalterado** **When** poll **Then** ignora. **Given** mesmo `file_id` mas `md5Checksum` mudou (usuário reenviou obra corrigida) **Then** reprocessa (novo job). O store guarda `(file_id, md5)` — teste prova ambos os ramos |
| U1.4 | Multi-usuário isolado | **Given** 2 pastas (`equipe:ana`, `equipe:bruno`), cada uma 1 arquivo **When** poll **Then** 2 `IngestedFile`, cada um com `user_login` correto — nunca cruza atribuição de autoria |
| U1.5 | Persistência do "visto" entre reinícios | **Given** store é arquivo (SQLite/JSON em disco), não memória **When** processo reinicia e um novo `DrivePoller` é criado apontando pro mesmo store **Then** `f1` continua visto → não reprocessa. (Amarra ao smoke test §6 e ao gate P5 "2 semanas sem perda de dado".) |

**Fixtures:** `tests/fixtures/portal/drive_list_*.json` (respostas `files().list()` gravadas). Fake client em `tests/fixtures/portal/fake_drive.py` com contadores `list_calls`/`download_calls`.

### 1.2 Parsing de upload (`test_portal_upload_parsing.py`)

**Código-alvo:** `scripts/portal/upload_guard.py` — `validate_upload(path) -> UploadVerdict` onde `UploadVerdict = {ok: bool, reason: str, classe_hint: str|None}`. **Parsing exclusivamente via `ezdxf`** (mesma lib de `src/core/dxf_loader.py::ezdxf.readfile`).

| # | Teste | Given / When / Then |
|---|---|---|
| U2.1 | DXF válido passa | **Given** DXF mínimo gerado com `ezdxf.new()` salvo em tmp **When** `validate_upload` **Then** `ok=True` |
| U2.2 | Extensão não permitida rejeitada | **Given** arquivo `.exe`/`.zip`/`.py`/`.dwg-que-é-txt` **When** validate **Then** `ok=False`, `reason` legível (`"formato não suportado"`). Só `.dxf` (e `.dwg` que vai pra fila do ODA) são aceitos |
| U2.3 | DXF corrompido não estoura | **Given** arquivo `.dxf` com bytes lixo (não é DXF) **When** validate **Then** `ok=False` com `reason` de parse — **sem** exceção propagada (usa `ezdxf.recover` ou try/except `ezdxf.DXFStructureError`) |
| U2.4 | Nunca executa conteúdo | **Given** `.dxf` contendo texto que parece código/script embutido num TEXT/MTEXT **When** validate **Then** trata como **dado geométrico** — nenhum `exec/eval`. Teste garante que `upload_guard.py` não importa `pickle`/`marshal` e não chama `exec`/`eval`/`__import__` (assert via `ast` sobre o fonte, ou `inspect.getsource`) |
| U2.5 | Limite de tamanho | **Given** arquivo acima de `MAX_UPLOAD_BYTES` **When** validate **Then** `ok=False`, `reason="excede limite"` — checagem por `stat().st_size` **antes** de abrir com ezdxf (não carregar arquivo gigante na RAM) |

---

## 2. Testes de integração — fila de jobs com exclusão mútua (`test_portal_job_queue.py`)

**Código-alvo:** `scripts/portal/job_queue.py` — `JobQueue.run_next()` que **reusa `single_instance`** para garantir 1 job por vez. Estende o padrão de `tests/test_single_instance.py`.

**Contrato:** a fila NUNCA roda dois jobs pesados (headless/accoreconsole/ODA) em paralelo. O segundo tentativa **enfileira ou aborta com código claro**, nunca corrompe estado. Reusa o lock `single_instance` — a trava é liberada pelo SO mesmo em crash (prova inter-processo já existe no teste base).

| # | Teste | Given / When / Then |
|---|---|---|
| I2.1 | Dois jobs → segundo enfileira | **Given** job A segurando o lock `'portal_worker'` (subprocesso, padrão de `test_lock_sobrevive_entre_processos`) **When** job B chama `run_next()` sem `--wait` **Then** B não roda o payload; retorna status `QUEUED`/`BUSY`, **não corrompe** o job de A (nenhum artefato de A é tocado) |
| I2.2 | Segundo aguarda com wait | **Given** job A segura o lock por ~2s (padrão `test_wait_adquire_quando_liberar`) **When** job B usa `wait_for_lock('portal_worker', poll_s=0.5, timeout_s=30)` **Then** B adquire quando A libera e processa — sem race |
| I2.3 | Crash do job A libera a fila | **Given** subprocesso A com lock é **morto** (`proc.kill()`) **When** B tenta adquirir **Then** SO já liberou → B adquire e roda (anti-órfão, espelha `test_lock_sobrevive_entre_processos` linhas 79-82) |
| I2.4 | accoreconsole nunca paralelo | **Given** dois jobs cujo payload chamaria o conversor DWG→DXF (ODA/accoreconsole) **When** ambos disparam **Then** o lock serializa — assert que só 1 subprocesso de conversão está vivo por vez (contador de PIDs). Comprova a restrição explícita do P2 ("nunca paralelizar accoreconsole") |
| I2.5 | Estado da fila é durável | **Given** fila com jobs `PENDING`/`RUNNING` persistidos **When** processo reinicia **Then** job que estava `RUNNING` sem lock vivo é reconciliado (→ `PENDING` de novo ou `FAILED` claro), nenhum job "some". Amarra ao smoke §6 |

**Reuso concreto:** os testes I2.1–I2.3 copiam a mecânica de subprocesso de `tests/test_single_instance.py` (Popen segurando lock + readline `'LOCKED'`), trocando o nome do lock para `'portal_worker'` e envolvendo em `JobQueue`.

---

## 3. Teste E2E — 1 obra TREINO fake ponta a ponta (`test_portal_e2e_obra.py`)

**Roda contra o pipeline headless REAL** (`scripts/arete/headless_sa_analise.py`), não um mock. Único ponto simulado: a **ingestão do Drive** (arquivo é colocado na `download_dir` como se o poller o tivesse baixado — reusa fake da §1.1).

**Fluxo coberto (as 6 etapas do DP-14):** upload simulado → triagem → recortes → processamento (SA headless) → validação → liberação de N5.

```
Given  uma obra TREINO pequena (ou Obra_TREINO_1 com --secao para 1 classe, p/ tempo)
       colocada em download_dir pelo poller-fake (etapa upload)
When   JobQueue.run_next() processa o job:
         - triagem/recortes: fases do pipeline
         - processamento: headless_sa_analise.main() com --obra <t> --pav <p> --secao <c>
         - validação: fichas HTML preficha_*.html geradas
         - liberação: n5_release cria N5 via assemble_n5(obra_dir, classe, pavimento=...)
Then   (a) fichas HTML existem em html_dir (result['html_dir'] do run_analysis)
       (b) assemble_n5 retorna N5AssemblyResult com ok_count > 0 e missing_count == 0
       (c) o DXF N5 existe em obra_dir/Fase-6_Execucao_CAD/n5/N5_<classe>_<pav>.dxf
       (d) SAÍDA IDÊNTICA ao caminho atual: hash/contagem do DXF N5 e nº de fichas
           batem com um baseline golden gravado (critério PASS do P1)
```

| # | Detalhe do E2E |
|---|---|
| E3.1 | **Baseline determinístico:** gravar 1x o hash SHA-256 do DXF N5 e a contagem de entidades/fichas de uma run limpa em `tests/fixtures/portal/e2e_baseline.json`. O teste compara contra ele (mesmo espírito do "hash/contagem" do P1). |
| E3.2 | **Marca `slow`:** decorar com `@pytest.mark.slow` — a run headless leva minutos. CI rápido pula; gate P1 roda explícito (`pytest -m slow`). |
| E3.3 | **Serialização:** o E2E adquire o lock `'portal_worker'` — prova que E2E e fila usam a MESMA trava (não há caminho paralelo escondido). |
| E3.4 | **Isolamento de escrita:** rodar em `tmp_path`/cópia da obra; ao fim, `assert` que `GOLDEN/` e o `project_data.vision` de produção **não** foram modificados (mtime/hash antes-depois). Prova a fronteira §3. |

> Se a obra TREINO real for muito pesada até com `--secao`, usar uma obra sintética mínima (1 classe, poucos itens) desde que ela exercite o caminho real `run_analysis → assemble_n5`. O que **não** é aceitável é substituir o motor por um dublê — o E2E existe justamente para pegar regressão no pipeline real.

---

## 4. Testes de segurança (`test_portal_security.py`)

### 4.1 R6 — upload malicioso/corrompido → quarentena, nunca execução

| # | Teste | Given / When / Then |
|---|---|---|
| S6.1 | Binário disfarçado de DXF | **Given** um `.exe`/PE renomeado para `.dxf` **When** o job o processa **Then** cai em **quarentena** (`job.status == "QUARANTINED"`, arquivo movido p/ `quarantine/`), `reason` claro, **nenhum** subprocesso/exec disparado. Assert: `mock` de `subprocess.Popen`/`os.system` **não** chamado |
| S6.2 | DXF estruturalmente corrompido | **Given** DXF truncado no meio de um BLOCK **When** processa **Then** quarentena com erro de parse legível — o **serviço continua vivo** e pega o próximo job (não derruba a fila) |
| S6.3 | Zip-bomb / arquivo gigante | **Given** arquivo acima do limite **When** upload **Then** rejeitado antes de abrir (§1.2 U2.5) — não há OOM |
| S6.4 | Payload de path traversal no nome | **Given** nome de arquivo `../../GOLDEN/x.dxf` vindo do Drive **When** ingestão salva **Then** nome é **sanitizado** (reusar `_safe_name` de `n5_assembler.py`) — grava dentro de `download_dir`, jamais escapa. Assert que o path resolvido está sob `download_dir` |
| S6.5 | Quarentena não bloqueia a fila | **Given** um job quarentenado seguido de um job válido **When** a fila avança **Then** o válido processa normalmente — 1 arquivo ruim não trava a operação |

### 4.2 R8 — Drive API indisponível → serviço não cai, loga e reagenda

| # | Teste | Given / When / Then |
|---|---|---|
| S8.1 | API fora do ar (exceção de rede) | **Given** `drive_client.files().list()` levanta `TransportError`/`HttpError 503` **When** `poll_once` roda **Then** **não propaga** exceção; retorna `[]`, **loga** o erro, agenda próxima varredura. Assert: nenhuma exceção sai de `poll_once`; log contém a causa |
| S8.2 | Cota estourada (429) | **Given** `HttpError 429 rateLimitExceeded` **When** poll **Then** degrada igual a S8.1 + respeita backoff (próximo poll adiado). Obra fica "aguardando ingestão", **não** vira job com erro |
| S8.3 | Credencial revogada (401/403) | **Given** service account revogada (`401 invalid_grant`) **When** poll **Then** loga em nível crítico (dono precisa reautenticar), serviço **continua servindo** as obras já ingeridas via VPN. Não crasha. |
| S8.4 | Recuperação transparente | **Given** poll #1 falhou (S8.1) **When** poll #2 roda e a API voltou **Then** detecta os arquivos que chegaram durante a queda — nada é perdido (a idempotência §1.1 garante que não reprocessa o que já tinha visto antes da queda) |

> R8 reusa **exatamente** o padrão de degradação do R5 (RAG/NIM opcional): a dependência externa fora do ar rebaixa a fila, não a quebra. Os testes S8.* espelham essa filosofia.

---

## 5. Teste específico do R9 — rótulo certificado/beta na liberação do N5 (`test_portal_n5_release_label.py`)

**Risco R9:** usuário libera N5 self-service (DP-13) de uma classe ainda `beta` sem perceber. **Mitigação testável:** o rótulo `certificado`/`beta` da classe **precisa estar presente na tela/payload de liberação do N5** — não só na listagem de resultados.

**Código-alvo:** `scripts/portal/n5_release.py` — `build_release_view(obra, classe, pavimento) -> ReleaseView` onde `ReleaseView` inclui obrigatoriamente `cert_status: Literal["certificado","beta"]`. A fonte da verdade do status é o mesmo dado já existente (`cad_pipeline_cli.py`/`gerar_status.py`, campo `certificado`).

| # | Teste | Given / When / Then |
|---|---|---|
| S9.1 | Classe certificada → rótulo visível | **Given** classe com `certificado=True` no status **When** `build_release_view` **Then** `cert_status == "certificado"` e o campo **não é None/vazio** |
| S9.2 | Classe beta → rótulo visível | **Given** classe com `certificado=False` **When** build **Then** `cert_status == "beta"` — presente e correto |
| S9.3 | **Invariante anti-omissão (o coração do R9)** | Para **toda** combinação classe×pavimento que o portal ofereça para liberação, `build_release_view` **nunca** retorna sem `cert_status`. Teste parametrizado sobre PL/LV/FV/LJ + assert `view.cert_status in {"certificado","beta"}` sempre. Falha se algum caminho omitir o rótulo |
| S9.4 | Render inclui o rótulo | **Given** o template HTML da tela de liberação **When** renderizado com uma classe `beta` **Then** a string `beta` aparece no HTML servido (grep no output) — garante que o dado chega à **UI**, não só ao objeto. Espelha a exigência do R3/P4 ("rótulo em toda página de resultado") estendida à tela de liberação |
| S9.5 | Self-service ≠ certificação | **Given** usuário libera seu N5 (validou N1+N3 dele) numa classe `beta` **When** o download é liberado **Then** o `cert_status` continua `beta` — reconcilia DP-13: liberar o *download* não promove o *status de certificação* da classe. Assert que a liberação do usuário **não altera** o campo `certificado` da classe |

---

## 6. Smoke test de P3/P5 — reinício e recuperação automática (`test_portal_service_recovery.py`)

**Critério P3:** "máquina reinicia → serviço volta → processa 1 item → serve a ficha." **Critério P5:** "2 semanas sem perda de dado."

Não dá para reinicar a máquina no CI — o smoke test **simula reinício** matando e resubindo o processo do serviço, provando que o estado durável sobrevive e o trabalho retoma sozinho.

| # | Teste | Given / When / Then |
|---|---|---|
| SM6.1 | Serviço sobe sozinho | **Given** o serviço FastAPI iniciado como subprocesso (uvicorn) **When** o processo é morto e o supervisor/rotina de start o reinicia **Then** o healthcheck (`GET /health`) responde 200 dentro de N s — sem intervenção manual |
| SM6.2 | Job pendente retoma após reinício | **Given** 1 obra ingerida + job `PENDING` no store durável **When** o serviço é morto e resubido **Then** o worker pega o job pendente e o processa (reusa reconciliação I2.5) — nada fica travado |
| SM6.3 | "Visto" do poller sobrevive | **Given** poller já viu `f1` (§1.1 U1.5) **When** reinício **Then** não rebaixa `f1` — prova que o store de idempotência é durável (P5: sem reprocessamento espúrio nem perda) |
| SM6.4 | Ficha servida pós-reinício | **Given** obra já processada com fichas em disco **When** reinício + `GET /obra/<id>/ficha` **Then** a ficha HTML é servida 200 — o resultado persiste no filesystem, não em memória do processo (critério P3 literal) |
| SM6.5 | Backup capturou o essencial (P5) | **Given** a rotina de backup diário rodou **When** inspecionamos o destino **Then** contém `project_data.vision`, `GOLDEN/`, logs de triagem, LanceDB e o store de jobs/vistos do portal — assert de presença dos artefatos que "não podem sumir" |

> SM6.1/SM6.2 usam subprocesso real (`subprocess.Popen(["uvicorn", ...])`) + `requests`/`httpx` contra `127.0.0.1` numa porta de teste. Marcar `@pytest.mark.slow`. Sem tocar rede externa.

---

## 7. Matriz de rastreabilidade — qual teste comprova qual gate PASS

| Gate | Critério PASS (masterplan §4) | Testes que comprovam |
|---|---|---|
| **P1** | 1 obra TREINO processada por comando único, saída **idêntica** ao caminho atual (hash/contagem) | E3.1 (baseline hash/contagem), E3.2/E3.3 (run headless real serializada), E3.4 (não polui GOLDEN) |
| **P2** | Obra na pasta Drive do usuário é **detectada pelo poller**, processada, e o usuário navega fichas + libera N5 pelo navegador sem o dono tocar | U1.1–U1.5 (poller detecta), I2.* (fila 1-por-vez), E3.* (processa→ficha→N5), S9.* (liberação N5 com rótulo) |
| **P3** | Membro externo faz upload e recebe resultado **sem intervenção manual** do dono | U1.4 (multi-usuário isolado), SM6.1/SM6.2/SM6.4 (serviço volta e retoma sozinho), S8.4 (ingestão automática robusta) |
| **P4** | Piloto real ≥2 membros, resultado **rotulado** certificado/beta | S9.* (rótulo presente e correto por classe), U1.4 (autoria por membro preservada) — piloto humano em si é manual, mas o rótulo que P4 exige é testado aqui |
| **P5** | 2 semanas de uso **sem perda de dado** e sem intervenção não documentada | U1.5/SM6.3 (idempotência durável), I2.5/SM6.2 (jobs não somem), SM6.5 (backup do essencial), S8.* (degradação não perde obra) |

**Riscos cobertos:** R5/R8 → S8.* ; R6 → S6.* + U2.* ; R9 → S9.* ; R3/R9 rótulo → S9.4. R7 (comentários poluírem triagem) e R1/R2/R4 são de produto/infra, fora do escopo de teste automatizado do portal.

**Como rodar (proposto para o @dev/CI):**
```bash
# unit + integração rápidos (CI a cada commit)
python -m pytest tests/test_portal_drive_poller.py tests/test_portal_upload_parsing.py \
                 tests/test_portal_job_queue.py tests/test_portal_security.py \
                 tests/test_portal_n5_release_label.py

# gates pesados P1/P3/P5 (explícito, antes de fechar o gate)
python -m pytest -m slow tests/test_portal_e2e_obra.py tests/test_portal_service_recovery.py
```

---

## 8. Veredito de QA sobre a estratégia

**Gate de estratégia: PASS (com CONCERNS registrados).**

A estratégia cobre integralmente P1–P5 e os riscos automatizáveis (R6/R8/R9). Concerns a resolver na implementação:

1. **[CONCERN — médio]** Módulos `scripts/portal/*` ainda não existem; as assinaturas aqui são contratos. Se o @dev divergir da interface (`poll_once`, `JobQueue.run_next`, `build_release_view`, `validate_upload`), os testes precisam ser ajustados junto — manter este doc e o código em sincronia.
2. **[CONCERN — médio]** O E2E depende de uma obra TREINO leve o suficiente para o CI. Se nem `--secao` de 1 classe couber no tempo, definir a **obra sintética mínima** antes de fechar P1 — mas **jamais** substituir o motor real por dublê (perderia o poder de pegar regressão).
3. **[CONCERN — baixo]** Backup (SM6.5) é infra de P5; o teste valida *presença* dos artefatos, não a restauração completa. Um teste de restore real (restaurar num tmp e reabrir) é recomendável antes de declarar P5 fechado.

**Constraint honrada:** este documento é advisory e de teste; não modifica código-fonte da aplicação nem toca `main.py` (§5 do masterplan — sem big-bang).

— Quinn, guardião da qualidade 🛡️
