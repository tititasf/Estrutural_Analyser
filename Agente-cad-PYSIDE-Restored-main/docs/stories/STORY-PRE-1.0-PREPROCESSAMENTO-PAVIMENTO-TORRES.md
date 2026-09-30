# STORY PRE-1.0 — Pré-processamento por pavimento e torre

**Status:** Ready for Dev — escopo e continuidade autorizados pelo dono em 2026-09-22.
**Tipo:** full-stack incremental; CLI primeiro, depois fila/API/botão e consumo assistido.
**Fonte de requisitos:** [plano de execução](../PLANO-PREPROCESSAMENTO-PAVIMENTO-TORRES.md), especialmente seções 0, 4–10; [contrato de consumo SA](../preprocessamento/CONTRATO-CONSUMO-SA.md); [baseline](../preprocessamento/BASELINE.md).

## História

Como operador de uma obra, quero pré-processar um pavimento a partir de seus recortes validados, com fatos e conflitos separados por torre e consolidados por pavimento/obra, para que uma análise SA posterior possa usar contexto verificável sem misturar torres, alterar resultados estruturais existentes ou depender de RAG/ML.

## Escopo aprovado

- O botão fica em **Pré-processamento · pavimento**, entre Recortes do Estrutural e Detalhamento de Etapas. Aciona todas as torres elegíveis daquele pavimento; opções restritas por torre/desatualizadas podem ser secundárias.
- Interface desta entrega: confirmação do escopo, estado da fila e progresso real por unidades concluídas. **Não** criar páginas de resultados de pilares, cortes ou níveis (P18–P22 adiadas).
- Entradas confiáveis são recortes validados. Em 14_PAV da obra `781becd6-b113-4bec-8d5a-2027f10a65a8`, o portal mostra Torre 1, Detalhes e Convenção de Pilares validados; Convenção de Níveis ainda não está disponível. A aplicação deve conferir essa condição no servidor, não confiar no indicador visual.
- Detalhes participa como fonte/inventário, sem interpretador genérico nesta versão. Ausência de convenção ou de módulo suportado produz cobertura parcial explícita, nunca certeza inventada.
- O pré-processamento não dispara SA/N3/N5, não modifica schema N1 e não limpa resultados ou validações da torre. RAG/ML e treinamento ficam fora do escopo.
- Consumo pelo SA só pode ser ativado depois de prova A/B do ponto de entrada e da chave de cache; gravar JSON sem consumidor **não** satisfaz a história.

## Critérios de aceitação

1. A CLI executa em Python 3.12 sobre recortes autorizados e validados; `--preview` é explicitamente provisório. Nenhuma escrita ocorre fora do armazenamento próprio, nem em tabelas/artefatos SA/N3/N5. [Plano §§0, 5, P05, P14]
2. Cada fato possui obra, pavimento, recorte de torre, revisão/hash de fonte, proveniência e estado. P1/L1 homônimos em duas torres ou obras permanecem distintos; nível zero difere de desconhecido. [Plano §§0.1, 4, 5.2, matriz §10]
3. O lote produz pacotes por torre, consolidado do pavimento e índice versionado da obra, atualizados atomicamente. Falha de uma torre deixa cobertura parcial; fonte alterada durante execução não vira pacote atual. [Plano §§0.1, 4.1, P14]
4. Convenções, pilares, cortes e níveis só são vinculados com evidência/abrangência comprovada. Ambiguidade ou conflito preserva alternativas; porcentagem de confiança não é fabricada. Detalhes sem interpretador aparece `not_supported`. [Plano §§1, 4, 5.2–5.3, P06–P12]
5. Reprocessar Detalhes ou convenções invalida apenas fatos dependentes e preserva SA/N3/N5. O pacote anterior permanece auditável como revisão antiga. [Plano §6, P13]
6. API autenticada usa a fila persistente do portal e deduplica obra+escopo+manifesto+versão; dois cliques não criam dois jobs. Progresso representa unidades reais, nunca tempo/95% fictício; job não transita pelos efeitos colaterais de SA. [Plano §7, P15–P16]
7. O botão do pavimento confirma torres/fontes e informa pendências; mostra status após refresh/restart sem visualizar o conteúdo interpretado. [Plano §§0, 3, 7, P17]
8. Comparação consultiva com SA exige mesma torre, fonte e revisão e não escreve no SA. Sem correspondência inequívoca, indica indisponibilidade. [Plano §8, P23]
9. O consumo assistido pelo SA fica desligado por padrão; quando habilitado, teste isolado prova que o SA leu contexto antes da decisão, registra `context_run_id`/hash e não reutiliza cache stale. Ausência ou conflito reproduz semanticamente o fluxo anterior; geometria, vínculos e N3/N5 passam regressão A/B. Se não existir interface segura sem alterar o núcleo, registrar o impedimento e **não** declarar este critério concluído. [Plano §§0, 0.2, P26–P28; contrato de consumo SA]
10. A publicação na VPS só ocorre após testes focados, regressão relevante, isolamento em cópia, migração aditiva e health check; feature flag permite desligar sem apagar pacotes. [Plano P24–P25]

## Tarefas / subtarefas

- [x] P00–P04: confirmar baseline, contratos, identidades, vínculos, armazenamento/índices e testes de atomicidade já iniciados; não marcar pela mera existência dos arquivos. (AC 1–3)
- [ ] P26: concluir investigação do consumidor SA, ordem de leitura, cache e mapeamento campo a campo no contrato; registrar lacunas sem editar o núcleo. (AC 9)
- [ ] P05–P09: certificar CLI isolada e adapters de legenda/pilares/níveis/inventário em fixtures com revisão, geometria e cobertura; adicionar testes para 14_PAV com cópias de recortes validados, nunca mutar produção. (AC 1, 2, 4)
- [ ] P10–P13: cortes, níveis por item, conflitos/ciclos e invalidação seletiva, com proveniência e testes de duas torres. (AC 4, 5)
- [ ] P14: orquestrar lote por pavimento e publicar consolidado/índice geral atomicamente, com status parcial e checagem de fonte no commit. (AC 3)
- [ ] P15–P16: integrar fila, progresso persistente e API com auth/escopo de obra e deduplicação. (AC 6)
- [ ] P17: implementar botão/status no hub; teste de UI, sem páginas de resultados. (AC 7)
- [ ] P23–P24: comparar consultivamente e provar isolamento, hashes e não regressão em cópias. (AC 8, 10)
- [ ] P27–P28: adapter de consumo assistido e validação A/B por item/classe, somente se o gate P26 provar interface segura. Caso contrário, documentar bloqueio explícito. (AC 9)
- [ ] P25: preparar e publicar de forma controlada somente após gates; verificar execução e estado real na VPS. (AC 10)

Cada Pxx exige checkpoint com arquivos alterados, testes, resultado e próxima tarefa. P18–P22 ficam fora desta story.

## Notas técnicas e limites

- Código já iniciado em `portal/app/preprocessamento/`, `scripts/preprocessamento_pavimento.py` e `portal/tests/test_preprocessamento_*.py`; [status local](../preprocessamento/STATUS-IMPLEMENTACAO-2026-09-22.md) registra 49 testes focados aprovados, mas sem botão/API/consumo e com 17 falhas da suíte ampla ainda não atribuídas. Verificar de novo antes de avançar.
- Fila existente: `portal/db/repository.py::enfileirar_job_unico_por_meta` e `portal/app/jobs.py::JobWorker`; hub: `portal/app/static/drill_grade.js`. [Plano §§2, 7]
- Proibido chamar `PreProcessAllWorker` no portal ou sobrescrever `estado_<pav>.json`, `convencao_pilares.json` legado e JSONs Fase-4. Não editar `main.py`, `headless_sa_analise.py`, geradores, motores nem widgets compartilhados para contornar a falta de contrato. [Baseline; Plano §§5.1, 11; `CLAUDE.md`]
- Dados de produção são somente leitura durante desenvolvimento/testes. Deploy exige evidência de não regressão e não é implícito na criação desta story. [`CLAUDE.md`; Plano P24–P25]

## Plano de testes / qualidade

- Python 3.12; unitários de contratos, fontes, adapters, atomicidade, deduplicação e autorização.
- Integração CLI→store→fila→API→botão em cópia de 14_PAV, incluindo fonte modificada durante job, duas torres homônimas, convenção ausente e falha parcial.
- Snapshot lógico e hashes SA/N3/N5 antes/depois; A/B sem contexto versus contexto válido/conflitante. Não aprovar precisão por contagem isolada.
- Revisão de segurança de paths e escopo, acessibilidade do botão, regressão portal e health check antes da VPS.
- CodeRabbit pré-commit: focar autorização, path traversal, efeitos colaterais de jobs, atomicidade e cache externo; não afirmar aprovação sem execução.

## Dev Agent Record

### Checkpoints

- 2026-09-22: story criada após autorização explícita do dono. Implementação prévia permanece parcial; nenhuma tarefa foi marcada concluída por esta story.
- 2026-09-22: P00–P04 conferidos contra `BASELINE.md`, contratos, resolver de fontes, store e testes; `python -m pytest portal/tests -k preprocessamento -q`: 49 passed. P05–P09 ainda têm cobertura parcial, e P26 não prova consumo pelo SA.
- 2026-09-22: regressão `python -m pytest portal/tests -q --tb=line`: 429 passed, 17 failed, 1 warning (7m37s). Falhas em `test_portal_ficha_reader.py`, `test_portal_n1_routes.py`, `test_portal_pillar_n3_ficha.py` e `test_portal_viewer_routes.py`; predominam fixtures/expectativas N1 ausentes ou divergentes. Não há baseline pré-mudança equivalente para atribuir causalidade. Gate de publicação permanece fechado.
- 2026-09-22: P15–P17 iniciados para o inventário parcial: POST/GET autenticados, deduplicação da fila, ramo do worker sem transição SA, botão com confirmação e estado sem porcentagem fictícia. `pytest portal/tests -k preprocessamento -q`: 53 passed; `pytest portal/tests/test_preprocessamento_job.py portal/tests/test_portal_job_queue.py -q`: 16 passed, 1 warning após repetir um teste intermitente de lock; `node --check portal/app/static/drill_grade.js`: OK. Não marcar P15–P17 completos: faltam progresso granular, contexto consolidado e testes HTTP/visuais. Sem deploy.
- 2026-09-22: P26 rechecado no headless e no runner do portal: cache anterior à leitura externa, `convention={}` no diálogo e ausência de argumento de manifesto contextual. Impedimento e interface mínima registrados em `CONTRATO-CONSUMO-SA.md`; P27/P28 permanecem desligados.
- 2026-09-22: smoke de registro FastAPI via `create_app().openapi()` confirmou `POST /obras/{obra_id}/preprocessamento/jobs` e `GET /obras/{obra_id}/preprocessamento`; nenhum servidor ou job de produção foi iniciado.

### File List

- `docs/stories/STORY-PRE-1.0-PREPROCESSAMENTO-PAVIMENTO-TORRES.md` (esta story)
- `portal/app/preprocessamento/preprocess_runner.py` (novo)
- `portal/app/routers/preprocessamento_routes.py` (novo)
- `portal/app/main.py`
- `portal/app/jobs.py`
- `portal/app/static/drill_grade.js`
- `portal/app/static/portal.css`
- `portal/tests/test_preprocessamento_job.py` (novo)
- `docs/preprocessamento/CONTRATO-CONSUMO-SA.md`
- `docs/preprocessamento/STATUS-IMPLEMENTACAO-2026-09-22.md`

### Completion Notes

- Pendente.

### Change Log

- 2026-09-22: criação a partir do plano vigente; escopo visual futuro excluído.
