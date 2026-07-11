# Masterplan — OBRAS DRIVE (integração app desktop ↔ portal web)

**Status:** Fase 1 CONCLUÍDA (código) — pendente teste visual do dono na app | **Data:** 2026-07-10

## Objetivo

Permitir que o dono acesse, na app desktop (Gerenciar Projetos + Diagnostic Hub),
as obras que a equipe sobe pelo portal web — mesmo motor de recorte, mesmo dado,
sem precisar baixar a obra inteira manualmente.

**Fase 1 (este masterplan cobre só isso):** sincronizar apenas os **recortes**
(torre_1.dxf), com download sob demanda por arquivo. Ficha/validação SA
compartilhada fica para uma fase futura (fora de escopo aqui).

## Arquitetura atual (mapeada, não hipótese)

| Peça | Onde | Observação |
|------|------|------------|
| Lista de obras locais | `src/ui/widgets/project_manager.py:7528` `load_works_combo()` | Lê `db.get_all_works()` (SQLite `project_data.vision`, tabela `works`, só nome). Já existe precedente de "categoria sentinela" (`"⚠️ Pavimentos Sem Obra"`, `UserRole="__NO_WORK__"`, linha 7543) — é o padrão a reaproveitar. |
| Clique numa obra | `project_manager.py:7562` `load_projects()` | Filtra `db.get_projects()` por `work_name`, monta `ProjectCard`s. Abrir um DXF emite `Signal(str, str)` `request_open_bruto(obra_name, file_path)` (linhas 42-43, 4868). |
| Wiring | `main.py:3068-3080` | `project_manager.request_open_bruto.connect(diagnostic_module.open_bruto)` — é a `MainWindow` quem liga os dois módulos, não um chama o outro direto. |
| Entrada do Hub | `src/ui/modules/diagnostic_hub.py:3688` `open_bruto(obra_name, file_path)` | Usa conexão SQLite própria e hardcoded pro mesmo `project_data.vision`, tabelas **`obra_triagem`** e **`obra_recortes`** (diferentes das tabelas do portal). Identifica obra por **nome (string)**, nunca por UUID. |
| Paths de recorte | `diagnostic_hub.py:22` `DADOS_OBRAS_ROOT` + `:2756` `_get_obra_root_path` | Hardcoded `D:/Agente-cad-PYSIDE/DADOS-OBRAS/<obra_name>/Fase-2_Triagem/recortes/<bruto_stem>/` — mesma convenção do portal (`torre_crop.py`) e do `scripts/obra_crop_engine.py`. |
| Fallback de path já existente | `diagnostic_hub.py:1743` `_resolve_dxf_path()` | Tenta path cru → remapeia raiz do drive → `rglob` pelo nome. **Nunca baixa nada.** Ponto de interceptação natural pro download sob demanda. |
| Cliente HTTP pro portal | — | **Não existe.** `requests` já é dependência (usado em outro lugar). Portal roda em `http://127.0.0.1:{PORTAL_PORT}` (`portal/app/config.py`, default 21380). |
| Endpoint de listagem | `portal/app/routers/obras_routes.py:63` `GET /obras` | **Já existe**, já devolve TODAS as obras se o membro for "dono". Reaproveitar direto. |
| Endpoint de arquivo bruto | `obras_routes.py:390` `GET /obras/{id}/documentos/{doc_id}/arquivo` | Já existe (adicionado nesta sessão), serve `FileResponse` real. |
| Endpoint de arquivo de recorte | — | **Não existe.** Os endpoints de "foto" de recorte só devolvem SVG renderizado (`recortes_routes.py:208`), nunca o `.dxf` cru. **Precisa ser criado.** |

## Gap de identidade (obra local = nome; portal = UUID)

O Hub identifica obra e recorte só por nome de string nas tabelas `obra_triagem`/
`obra_recortes`. Reescrever o Hub pra entender UUID é invasivo demais pra Fase 1.
**Decisão:** obra Drive vira um "espelho" local — mesma pasta
`DADOS-OBRAS/<nome>/Fase-2_Triagem/recortes/<bruto>/`, mesmas linhas em
`obra_triagem`/`obra_recortes` — só que o `.dxf` em si só é baixado quando o
dono efetivamente pede pra ver aquele item. Isso reaproveita 100% do código do
Hub sem reescrevê-lo.

## Plano de execução — Fase 1 (todos os passos concluídos e testados sem GUI real)

1. ✅ **Portal:** `GET /obras/{obra_id}/recortes/brutos/{bruto_id}/{item_id}/arquivo`
   (`FileResponse`) — testado ao vivo contra o servidor real (200, DXF real).
2. ✅ **Desktop — cliente:** `src/core/drive_client.py` — `DriveClient` + singleton
   de processo `obter_cliente_padrao()`/`resetar_cliente_padrao()` (1 login/sessão
   só, reusada pelo dialog E pelo Hub). Testado ao vivo contra o servidor real.
3. ✅ **Desktop — schema:** tabela `drive_obras` (`src/core/database.py`, aditiva) +
   `DatabaseManager.registrar_drive_item/obter_drive_item/obra_e_drive`. Testado
   isolado (sqlite temp).
   **Desktop — espelho local:** `src/core/drive_mirror.py::criar_espelho_local_drive`
   (função pura) — cria linhas em `works`/`obra_triagem`/`obra_recortes`/`drive_obras`
   a partir de 1 item do portal, sem baixar DXF. Testado ponta-a-ponta contra as
   MESMAS queries reais que `diagnostic_hub.py` usa (`_populate_obras_combo`,
   `_refresh_brutos_list`, `_get_recorte_icon`, `_refresh_recortes_list`).
4. ✅ **Desktop — Gerenciar Projetos (revisado após feedback visual do dono):**
   `"☁️ OBRAS DRIVE"` é um **cabeçalho de categoria não-selecionável** em
   `load_works_combo()` (`project_manager.py`) — as obras de verdade aparecem
   ABAIXO dele, cada uma como item normal e clicável, agrupadas por
   sub-cabeçalho de membro (`_carregar_obras_drive_na_sidebar`, deferido via
   `QTimer` pra não travar a sidebar com I/O de rede). Nada de dialog separado
   — descartado (`drive_obras_dialog.py` removido) por fugir do padrão visual
   pedido. Ao selecionar uma obra Drive, `load_projects()` detecta o marcador
   (`UserRole={"tipo": "drive", "obra": {...}}`), chama
   `drive_mirror.espelhar_obra_completa_drive` (espelha TODOS os brutos+itens
   da obra de uma vez, só metadados) e **continua o mesmo fluxo de sempre**
   (cards/triagem/phase_tabs) — a partir da conversão pro nome do espelho
   local, a obra Drive é indistinguível de uma obra local pro resto do código.
   Testado ponta-a-ponta contra o portal REAL rodando (não mock): 2 obras reais
   do dono, 1 delas com 10 brutos/22 itens de recorte espelhados corretamente,
   agrupamento por membro confirmado via `QListWidget` real em modo Qt
   offscreen (`QT_QPA_PLATFORM=offscreen`).
5. ✅ **Desktop — download sob demanda:** `diagnostic_hub.py::_garantir_drive_download`
   — chamado ANTES de `_resolve_dxf_path` em `_abrir_dxf_bruto`/`_on_bruto_selected`/
   `_on_recorte_selected`. No-op garantido (testado com mock) pra qualquer obra
   local normal — só age se `db.obra_e_drive(obra_atual)` E existir mapeamento
   exato em `drive_obras` pro path pedido.
6. ✅ **Credenciais:** `.env` na raiz do projeto desktop (`PORTAL_LOGIN`,
   `PORTAL_SENHA`, `PORTAL_BASE_URL`) — já gitignorado por padrão nesse repo
   (não é commitado). `drive_client.py` carrega via `python-dotenv`, ancorado
   no caminho do módulo (não depende do CWD do processo). Login confirmado
   real contra o portal rodando — papel `dono`, vê as obras de todos os membros.

**O que NÃO foi (e não pode ser) testado nesta sessão:** o clique real do
mouse na app rodando de verdade (layout visual da sidebar, se os textos
ficam legíveis, cores/ícones). Toda a lógica por trás de cada clique/seleção
foi validada com dados REAIS do portal rodando — o risco remanescente é
puramente visual, não de correção funcional ou de dados.

## Ronda 2 — feedback do dono testando ao vivo (2026-07-10)

- ✅ **Combobox do Diagnostic Hub (Pré):** `_populate_obras_combo` agrupa
  local vs Drive (ícone `SP_DirIcon`/`SP_DriveNetIcon` + separador entre os
  grupos), mantendo o texto do item idêntico (não quebra `currentTextChanged`).
  Testado contra `project_data.vision` REAL — confirmado: obras locais
  alfabéticas primeiro, separador, depois obras Drive agrupadas no fim.
- 🔍 **Aba "1. Ingestão" vazia ao selecionar obra Drive — investigado, NÃO é
  bug do mirror:** essa aba lê `project_documents`/pasta `Fase-1_Ingestao`
  por **pavimento (`projects.id`)**, sistema DIFERENTE da aba "2. Triagem"
  (que lê `obra_triagem` por OBRA — é isso que o mirror popula, confirmado
  funcionando 100% com os 10 brutos reais). Como Fase 1 não cria `projects`
  por pavimento (fora de escopo, SA/ficha fica pra depois), a aba Ingestão
  fica genuinamente vazia — comportamento esperado, não um bug. Corrigido
  de quebra: o breadcrumb ficava preso mostrando o último pavimento local
  aberto antes de trocar pra obra Drive (`load_projects`, branch de 0 cards,
  agora reseta o breadcrumb com uma mensagem clara).
## Ronda 3 — escopo expandido: Ingestão + SA, só referência (2026-07-10)

Decisão do dono: quer os 3 sistemas (Triagem, Ingestão, SA/pavimentos)
populados pra obras Drive, mas SEM baixar nada além de título/referência ao
selecionar a obra — download real só quando o item específico é aberto no
viewer certo (Diagnostic Hub p/ recortes, Diagnostic Reverse Hub p/ bruto,
Structural Analyzer p/ pavimento).

- ✅ **`drive_documentos`** (tabela nova, `database.py`) — mapeia documento
  inteiro (não-recorte) → `doc_id` do portal, keyed pelo path local exato
  (documentos não têm o par bruto/item que recortes têm).
- ✅ **`DriveClient.baixar_documento`** — usa o endpoint já existente
  `GET /obras/{id}/documentos/{doc_id}/arquivo`. Refatorado `baixar_recorte`
  pra compartilhar o download com `_baixar_arquivo` (zero duplicação).
- ✅ **`drive_mirror.espelhar_obra_completa_drive` estendido:**
  - `_garantir_projeto_pavimento_drive` — 1 linha em `projects` por
    pavimento (`dxf_path` = mesmo `torre_1.dxf` do Diagnostic Hub — mesmo
    motor/dado dos 2 lados). **Bug real encontrado e corrigido:** o portal
    lista 2 "brutos" pro mesmo pavimento (.dwg original + .dxf convertido
    ODA) — só o convertido tem recorte de verdade, então brutos sem nenhum
    item são pulados (senão duplicava pavimento). Confirmado: 10 pavimentos
    reais, não 20.
  - `_garantir_documento_drive` — 1 linha em `project_documents` (aba
    Ingestão) por documento, mapeando `tipo_documento` do portal
    (Bruto/Detalhe, único eixo que o portal distingue) pras 4 categorias
    do `PHASE_CLASSES[1]` da app desktop (heurística por extensão+tipo;
    "Projetos Finalizados p/ Engenharia Reversa" não tem equivalente no
    portal, fica sempre vazio). Documento sem pavimento identificável (3 de
    21 no teste real) não vira linha em `project_documents` (não aparece na
    aba ainda) mas AINDA registra o mapeamento de download.
- ✅ **Helper compartilhado `src/core/drive_download_hook.py`** (novo,
  `garantir_drive_download(db, obra_nome, raw_path)`) — tenta os 2
  mapeamentos (recorte via `drive_obras`, documento via `drive_documentos`).
  `diagnostic_hub.py::_garantir_drive_download` refatorado pra delegar aqui
  (zero duplicação). Plugado em mais 2 lugares mapeados por agente de
  exploração:
  - `main.py::load_project_action` (Structural Analyzer) — antes do
    `os.path.exists(dpath)` que carrega o DXF de fundo do pavimento.
  - `diagnostic_reverse_hub.py::_on_item_selected` (bruto completo) e
    `_on_recorte_selected_wrapper` (recorte granular).
- ✅ Testado ponta-a-ponta contra o portal real: dedup de pavimento (10, não
  20), download de recorte E de documento inteiro (via mock do
  `DriveClient`, path/args corretos), no-op confirmado pra obra local.

**Fora do que foi testado:** o clique real nos 3 viewers rodando de
verdade (só a lógica por trás foi validada, não a UI ao vivo do Structural
Analyzer/Reverse Hub).

## Ronda 4 — combobox, obra faltando, status real, validação bidirecional (2026-07-10)

- ✅ **Combobox do Diagnostic Hub reformulado de novo:** agora busca as
  obras do portal DIRETO (`drive_client.listar_obras()`), não só as já
  espelhadas — corrige "faltou listar a obra de pavimento único"
  (`TMC-EST-PE-6000-13P-R03` nunca tinha sido clicada em Gerenciar
  Projetos, por isso não aparecia). Agrupado com cabeçalho "☁ OBRAS DRIVE"
  + sub-cabeçalho por membro (ambos não-clicáveis, `setEnabled(False)`,
  mesmo padrão da sidebar) — texto das obras reais nunca é decorado (não
  quebra `currentTextChanged`). Selecionar uma obra Drive AINDA NÃO
  espelhada dispara `espelhar_obra_completa_drive` na hora — testado
  (offscreen): `obra_e_drive` vira True, `projects`/`obra_triagem` populados.
- ✅ **Bug real corrigido — status de recorte estava sempre 'approved':**
  `criar_espelho_local_drive` hardcodeava `status='approved'` pra TODO
  recorte espelhado, ignorando o campo `validado` real que o portal já
  expõe por item. Corrigido: usa `item_portal['validado']`. No
  re-espelhamento, `status` só é adotado do portal se o local AINDA NÃO
  estiver `'approved'` (protege validação local ou já puxada antes —
  implementa a regra "nenhum lado sobrescreve o que o outro já validou").
- ✅ **Validação bidirecional de recorte (item completo):** novo
  `DriveClient.validar_recorte` (usa o endpoint já existente
  `POST /obras/{id}/recortes/brutos/{bruto_id}/{item_id}/validar`) +
  `drive_mirror.empurrar_validacao_recorte` (no-op pra obra local). Plugado
  em `diagnostic_hub.py::_approve_current_crop` — aprovar um recorte de
  obra Drive no app agora empurra a aprovação pro portal. Testado (mock)
  contra dados reais.
- ✅ **Bug real corrigido — bruto cru não baixava:** o path do bruto cru
  (`entrada/<nome>`, convenção de `obra_triagem`) nunca tinha mapeamento de
  download registrado (só o path de `Fase-1_Ingestao/<categoria>/` tinha).
  Corrigido: `espelhar_obra_completa_drive` cruza `documentos` com os
  `brutos` pelo nome de arquivo e registra o mapeamento pelos 2 paths.
  Testado contra o portal real: download do bruto cru confirmado.
## Fase 2 — Validação SA bidirecional "item completo" (2026-07-10, CONCLUÍDA)

Decisão do dono: quer a mesma harmonia de recortes pro SA — nenhum lado
sobrescreve validação já feita no outro. Web continua só com validação de
item completo (sem campos); campos ricos ficam só na app (já protegidos
via `trust_current_validation`, achado real no código).

- ✅ **Portal:** migration `006_sa_validacao.sql` — tabela
  `portal_sa_validacao` (obra_id, bruto_id, validado, validado_por,
  validado_em). 3 endpoints novos em `obras_routes.py`:
  `GET /obras/{id}/sa` (lote), `GET /obras/{id}/sa/{bruto_id}`,
  `POST /obras/{id}/sa/{bruto_id}/validar`. Portal reiniciado (autorizado
  pelo dono) e testado ao vivo via curl — GET/POST/GET round-trip real,
  valores corretos.
- ✅ **Desktop — schema:** `projects.validado_sa` +
  `validado_sa_em` (aditivo, `_migrate_db`). `DatabaseManager.obter_portal_obra_id`
  novo (resolve UUID do portal a partir do nome do espelho local).
- ✅ **Desktop — cliente:** `DriveClient.obter_validacao_sa/listar_validacoes_sa/validar_sa`
  (+ `_post` compartilhado, elimina duplicação com `validar_recorte`).
  Testados contra o portal real.
- ✅ **Pull protetivo:** `_garantir_projeto_pavimento_drive` agora recebe
  `validado_sa_portal` e faz merge protetivo (`CASE WHEN projects.validado_sa=1
  THEN 1 ELSE excluded.validado_sa END`) — NUNCA rebaixa validação local já
  feita, mesmo se o portal reportar False depois (testado: valida no portal
  → espelha → confirma 1 → portal "esquece" (False) → re-espelha → continua
  1, não rebaixou).
- ✅ **Push:** `drive_mirror.empurrar_validacao_sa` (no-op pra obra local,
  testado) — conectado no botão novo "☐/☑ Validar SA (item completo)" na
  aba Structural Analyzer (`main.py`, ao lado do combo de pavimentos) —
  toggle salva local + empurra pro portal se for obra Drive; ao trocar de
  pavimento, o botão reflete o estado salvo daquele pavimento.

**Não testado (não dá pra sem GUI real):** o clique físico no botão de
validar SA rodando na app de verdade — testei toda a lógica por trás
(DB update, push, merge protetivo) isoladamente, mas não o widget Qt em si.

## Fase 4 — Combobox unificado (4 telas) + N1/N3/N5 bidirecional (2026-07-10)

- ✅ **`src/ui/drive_obras_combo.py`** (novo módulo compartilhado) — extrai o
  padrão de combobox (locais + cabeçalho ☁ OBRAS DRIVE + sub-cabeçalho por
  membro, ícones, itemData espelha texto pra compatibilidade com
  `currentText()` E `currentData()`) usado agora nos 4 lugares:
  Diagnostic Hub (refatorado pra usar o módulo), Structural Analyzer
  (`main.py`, `sa_cmb_obras`), Comparison Engine (`cmb_obra` do
  `Fase8Panel`), Diagnostic Reverse Hub (`cmb_obra` do `_LeftPanel`).
  Testado offscreen com dados reais nos 2 padrões de consumo.
- 🔍 **Investigado — o que são N3/N5 de verdade:** N3 = DXF gerado por robô
  a partir da ficha SA (Fase 4→6); N5 = consolidação de 1 DXF final por
  classe a partir dos N3. O portal JÁ TEM um pipeline de 6 etapas
  (ingestão→triagem→recortes→sa→**validação**→N5), com N5 GATEADO pela
  validação N1+N3 por classe — mas essa validação (etapa 5) só existia em
  **memória do processo** (`request.app.state.validacoes`), perdida a cada
  restart (achado real, comentário no próprio código confirma).
- ✅ **Corrigido — validação N1+N3 agora persistida:** migration
  `007_validacao_persistente.sql` (tabela `portal_validacoes`), reescrevi
  `POST /obras/{id}/validacao` pra gravar no banco (com merge protetivo —
  nunca rebaixa `n1_ok`/`n3_ok` já True) + 2 GETs novos (lote e por classe).
  Gating do N5 atualizado pra ler do banco em vez da memória. Portal
  reiniciado e testado ao vivo: persistência + proteção confirmadas.
- ✅ **Desktop:** tabela local `validacoes_n1n3` (obra+classe) +
  `DatabaseManager.obter_validacao_n1n3/set_validacao_n1n3` (merge
  protetivo espelhado). `DriveClient.obter_validacao_classe/listar_validacoes_classe/validar_classe`
  + `listar_n5_releases` (somente leitura — liberar N5 é ação self-service
  do portal, não da app). `drive_mirror.empurrar_validacao_n1n3`/`puxar_validacoes_n1n3`
  (chamado automaticamente dentro de `espelhar_obra_completa_drive`).
  Botão novo **"☐ Validar N1+N3 (classe)"** no Comparison Engine
  (`TriLevelArea`, ao lado do botão N5 Montagem) — toggle salva local +
  empurra pro portal se Drive, reflete estado ao trocar obra/pavimento/classe.
- ✅ Testado ponta-a-ponta contra o portal real: validei PL no portal →
  espelhei → puxou corretamente → tentei rebaixar no portal (bloqueado,
  como esperado) → re-espelhei → app manteve validado. Push (mock) e
  no-op de obra local confirmados.

**Efeito colateral de teste a saber:** a classe PL da obra real
"Obra-Teste-Inicial2" ficou marcada como `n1_ok=true, n3_ok=true` no
portal (não dá pra desfazer via API normal — é assim por design, protege
contra rebaixamento). Se não for validação real, avise que eu reseto
direto no banco.

## Fase 5 — Decisão final: validação é SÓ PULL, nunca push (2026-07-10)

Análise estratégica com o dono: bidirecional de verdade tem risco real de
um clique/teste na app sobrescrever validação real da equipe na web — e
isso ACONTECEU de fato durante os testes desta sessão (a classe PL da
Obra-Teste-Inicial2 ficou marcada como validada por causa de um teste meu,
não de uma validação real). Decisão: só o dono usa a app pra curar/revisar;
a validação segue **só portal → app**, nunca o contrário.

- ✅ Removido de `diagnostic_hub.py::_approve_current_crop`: a chamada que
  empurrava aprovação de recorte pro portal. A aprovação local continua
  normal, só não sai mais daqui.
- ✅ Removido de `main.py` (botão "Validar SA") e `comparison_engine.py`
  (botão "Validar N1+N3"): as chamadas de push. Os 2 botões agora são
  **flags 100% locais** (lembrete do dono) — salvam em `projects.validado_sa`
  / `validacoes_n1n3` mas nunca escrevem no portal.
- ✅ Removido de `drive_mirror.py`: `empurrar_validacao_recorte`,
  `empurrar_validacao_sa`, `empurrar_validacao_n1n3` (código morto, sem
  chamador). `puxar_validacoes_n1n3` (pull) continua.
- ✅ Removido de `drive_client.py`: `validar_recorte`, `validar_sa`,
  `validar_classe`, `_post` (o helper HTTP genérico de POST — sem chamador
  restante, era usado só pelos 3 métodos de push). O `DriveClient` agora só
  tem métodos de leitura + download — nenhuma forma de escrever no portal.
- ✅ Endpoints `POST` no portal (`/recortes/.../validar`, `/sa/{bruto_id}/validar`,
  `/validacao`) foram MANTIDOS — são o caminho de escrita legítimo da
  própria web (ou de uma equipe usando o portal), não da app desktop.
- ✅ Testado: pull continua funcionando idêntico a antes (SA e N1+N3
  confirmados puxando do portal real); `DriveClient` confirmado sem
  nenhum método de push restante (`hasattr` checado nos 4 removidos).

## Fase 6 — Isolamento de IDs + referência ao SA da web (2026-07-10)

Achado real ao investigar `pipeline_runner.py` (portal): quando a web roda o
"4 sa" (etapa do próprio pipeline do portal), ela chama `headless_sa_analise.py`
de verdade (subprocess) e registra o `projects` via `_garantir_project_
registrado` (função já existente, corrigida em sessão anterior) — usando
`work_name = str(obra_dir)` (path bruto do servidor), um esquema de
identidade TOTALMENTE diferente do `drive:{bruto_id}` que meu espelhamento
usa. Confirmado: **nunca colidem** (uuid4 local vs `drive:string` vs path
bruto do servidor — formatos incompatíveis por construção).

- ✅ **`projects.web_sa_project_id`** (coluna nova, aditiva) — em
  `_garantir_projeto_pavimento_drive`, detecta (via `work_name = obra['local_path']`
  + mesmo `pavement_name`, match exato) se já existe um project da web pra
  esse MESMO pavimento real, e guarda só a REFERÊNCIA — nunca funde os dois
  registros. Testado contra a `project_data.vision` real: os 9 pavimentos
  reais da obra vincularam certinho ao id que a web usa (confirmado 1:1 com
  o que foi mapeado na Ronda 1 desta sessão).
- ✅ **`DatabaseManager.contar_elementos_sa(project_id)`** — pilares/vigas/lajes
  de 1 project_id, usado pra comparar espelho local vs SA da web sem fundir.
- ✅ **Structural Analyzer (`main.py`)**: label nova abaixo do botão "Validar
  SA" — se detectar SA já rodado na web pra esse pavimento (contagem > 0),
  mostra "🌐 SA já rodado na WEB: X pilares, Y vigas, Z lajes (registro
  isolado — rode aqui pra comparar/divergir)". Puramente informativo — rodar
  aqui cria/atualiza SEU PRÓPRIO registro isolado (`drive:...`), nunca
  sobrescreve o da web.
- ✅ Testado ponta-a-ponta: isolamento de IDs confirmado (`web_sa_project_id`
  nunca aparece no conjunto de ids locais), detecção 1:1 com os 9 pavimentos
  reais, contagem funcionando (0/0/0 pros dois lados hoje — SA nunca foi de
  fato executado nesse pavimento nem lá nem aqui, confirmado via query direta).

## Fase 7 — SA via web grava de verdade + toggle Dados WEB/Local (2026-07-11)

A pedido do dono: "rodar via web deve gravar igual roda na app, tipo os
loopings já fazem". Investigado e corrigido — 2 bugs reais encontrados na
tentativa de reproduzir:

- ✅ **Bug 1 (encoding):** `subprocess.run(...)` sem `encoding`/`errors`
  explícitos usa `locale.getpreferredencoding()` (cp1252 nesta máquina) —
  headless imprime UTF-8, derruba a thread de leitura silenciosamente
  (`ok=True` só que log vazio, 0 elementos). Fix: `encoding="utf-8",
  errors="replace"` em `pipeline_runner.py`.
- ✅ **Bug 2 (achado real, o motivo de nunca persistir):** `montar_comando_headless`
  nunca passava `--persist-db` — o MESMO flag que os loopings já usam
  (`docs/PERSISTENCIA-HEADLESS-SA.md`, gate de 4 diagnósticos + transação
  `BEGIN IMMEDIATE` + preserva campo validado, já maduro e documentado).
  Fix: adiciona `--persist-db` quando a execução é completa (sem `--secao`,
  que o próprio script exige).
- ✅ Testado ponta-a-ponta contra a obra real: rodei via web (portal
  precisou ser reiniciado sob Python 3.12 — 3.14 quebra um check do
  CAD-ANALYZER) — **38 pilares, 35 vigas, 25 lajes gravados de verdade**,
  auditado em `sa_persistence_runs` (status `COMMITTED`).
- ✅ **Structural Analyzer (`main.py`):** toggle "🌐 Dados WEB" / "💻 Dados
  Locais" abaixo do combo de pavimento — só aparece pra obra Drive com
  `web_sa_project_id`. NUNCA altera `current_project_id`/`active_project_id`
  (sempre o local) — troca só o que é renderizado (pilares/vigas/lajes +
  DXF de fundo), e desabilita os botões de escrita (Iniciar Análise, Salvar,
  Sincronizar Fase-4, etc) quando em modo WEB — defesa extra contra gravar
  sem querer no motor de produção. Testado: `load_pillars/beams/slabs` +
  `dxf_path` do project_id da web carregam os 38/35/25 reais corretamente.
- ✅ **Comparison Engine:** versão mais conservadora — label + botão
  "📂 Abrir pasta SA da WEB" abaixo do combo de pavimento (em vez do toggle
  completo). Motivo: `_on_obra_pav_changed` já tem lógica de
  auto-disparar Análise Geral em background e cancelamento de workers N2-N5
  — redirecionar esse pipeline pra um `project_id`/obra_dir diferente sem
  entender 100% os efeitos colaterais era risco desnecessário. A pasta HTML
  real (`sa_persistence_runs.html_dir`) abre no Explorer sob demanda —
  visão real do que a web gerou, sem tocar no pipeline N1-N5.
- ✅ `DatabaseManager.obter_ultimo_html_dir_sa` (novo) testado contra dado
  real — path existe em disco, `None` corretamente quando não há
  `--persist-db` rodado ainda pro project_id.

## Fase 8 — Bug real do N1 + toggle completo no Comparison Engine (2026-07-11)

- ✅ **Bug real corrigido — N1 quebrava sempre que um pilar tinha laje
  contígua real:** `ficha_reader.py::_normalizar_pilar` fazia
  `", ".join(p.get("lajes"))` assumindo lista de strings, mas o dado real é
  lista de dicts (`{'laje': 'L101', 'side': 'D', ...}`) — `TypeError`,
  endpoint `/n1/classes` e `/n1/{classe}` quebravam com 500 pra qualquer
  pavimento com dado de laje real. Provavelmente a causa raiz do "0 lajes"
  observado no início desta sessão. Corrigido (extrai `.get("laje")` de
  cada dict, com fallback pra string pura). Testado: N1 agora reporta 35
  pilares normais + 3 especiais = 38 (bate com SA), 25 lajes (bate), 17
  cortes, segmentos de viga populados — tudo coerente.
- 🔍 **N3 investigado:** vazio pra essa obra por não ter sido gerado ainda
  (etapa manual separada, não é bug). **N5 investigado:** 1 release
  existente é artefato dos meus próprios testes de gate (criado antes de
  qualquer N3 existir, por isso `ok:false` — coerente, não é bug).
- ✅ **Prova empírica: local e web usam o MESMO motor.** Rodei
  `headless_sa_analise.py --persist-db` apontando pro `project_id` isolado
  da app (mesmo DXF, hash idêntico ao da web) — resultado: **38 pilares,
  35 vigas, 25 lajes, com os MESMOS NOMES** (P1, P10, P101...) que a web
  produziu. Confirma: motor idêntico, resultado idêntico, registros
  continuam isolados.
- ✅ **Comparison Engine — toggle completo implementado** (a pedido
  explícito do dono, avisado do risco antes): "🌐 Dados WEB" / "💻 Dados
  Locais" abaixo do combo de pavimento, redireciona
  `tri_level.set_obra_pav`/`nav_sidebar.set_obra` pro `obra_dir` real da
  web (via `projects.web_sa_project_id` → `work_name`) sem nunca perder a
  referência da obra local (usa `obra_local` pra sempre re-achar a
  referência, mesmo já em modo WEB). Investigação prévia importante: o
  "auto-dispara Análise Geral em background" desse fluxo é na verdade
  Fase-3/engenharia reversa (`engenharia_reversa_dxf.py`), NÃO o motor
  SA/pillars-beams-slabs que eu vinha protegendo — roda contra a pasta
  Fase-3 da própria obra_dir (local OU web, dependendo do toggle), mesmo
  padrão idempotente que já roda pra qualquer obra local hoje.
  Testada a cadeia de resolução de dados (local→web_id→work_name→obra_dir)
  contra o banco real — bate exato com a pasta real da web.

**Não testado:** o clique real do toggle rodando na app de verdade (só a
lógica de dados por trás — a mesma limitação de sempre pra PySide6).

- 🔍 **Investigado (não implementado) — sincronia SA/ficha app↔web:**
  Hoje NÃO existe nenhum push da app pro portal (só pull, esta fase toda é
  só download sob demanda). A app JÁ protege campos validados localmente
  em re-análise (`DatabaseManager.save_pillar/save_beam/save_slab`,
  parâmetro `trust_current_validation` — merge que preserva
  `validated_fields_json`/valores antigos, achado real no código, não
  hipótese). O que NÃO existe: qualquer conexão entre esse sistema rico de
  campos da app e a validação simples "item completo" do portal — pra
  sincronizar de verdade precisaria de endpoint novo no portal + schema
  novo pra guardar estado de campo (fora do escopo desta fase — é feature
  nova, não mirror de documento). Recomendação: tratar como masterplan
  separado quando o dono quiser priorizar.

## Fase 9 — Bug real do N1 frontend: "Nenhum item nesta classe" (2026-07-11)

- ✅ **Bug real corrigido — clique em qualquer classe N1 não listava
  itens**, mesmo com contagem certa na sidebar. Causa: em
  `obra_detalhe.html`, `carregarClassesGenerico` (lista de classes) já
  passava `?pavimento=`, mas 3 outras fetches não passavam, caindo no
  `settings.pav_default` (13_PAV) do backend em vez do pavimento
  selecionado (ex.: TERREO):
  - `carregarItensClasseParaPainel3` (linha ~1636) — lista de itens de
    uma classe.
  - `carregarDetalheItemN1` (linha ~1699) — ficha/detalhe de um item N1.
  - `carregarDetalheItemN3` (linha ~1759) — ficha/detalhe de um item N3.
  Todas agora anexam `(_pavimentoSelecionado ? '?pavimento=' + ... : '')`,
  igual ao padrão já usado em `carregarClassesGenerico`. Backend
  (`n1_routes.py`) já aceitava o parâmetro em todas as rotas — só o
  frontend não mandava.
- ✅ **Testado ao vivo** contra a obra real (Obra-Teste-Inicial2/TERREO,
  project_id `156f05b4-...`) via Claude Browser: login real, expandi
  TERREO, abri SA/N1, cliquei em 4 classes diferentes (`lateral_a_para`,
  `pilares`, `lajes`, `cortes`) — todas agora retornam **200 OK** tanto
  na lista (`/n1/{classe}?pavimento=TERREO`) quanto no detalhe
  (`/n1/{classe}/{item_id}?pavimento=TERREO`), confirmado via
  `read_network_requests` (antes: 404 no detalhe, lista vinha do
  pavimento errado). Ficha do item V101 (segmento 1, classe
  lateral_a_para) renderizou completa: campos (Nome, Segmento, Lado,
  Comportamento, Comprimento, Largura, Status) + desenho HTML SA.
  Como a correção está nas 3 funções genéricas usadas por TODAS as
  classes (não por classe específica), as 7 classes não testadas
  individualmente (pilares_especiais, fundos, lateral_b_para,
  lateral_a_passa, lateral_b_passa, convenção de pilares, convenção de
  níveis) usam o mesmo código-caminho e devem se comportar igual —
  não há lógica per-classe divergente nesses 3 pontos.
- Não precisou restart do portal (mudança só em template Jinja/JS
  estático, servido fresco a cada request).

## Fase 10 — Corte/laje parity + Pilares N3 Para/Passa na web (2026-07-11)

- ✅ **Ficha do Visão de Corte agora mostra dados da laje referenciada** —
  `_normalizar_corte` (ficha_reader.py) buscava `own_laje`/`neigh_laje` só
  pelo nome. Adicionado `_laje_ref_texto` que cruza com `estado["slabs"]` e
  mostra Nível+Altura junto (ex: `"L101 (Nível ?, Altura ?)"`), permitindo
  validar a interpretação do corte a partir da perspectiva da própria laje,
  sem abrir a ficha da laje à parte. Testado ao vivo (200 OK, campo
  populado). Placeholder `"�"` (encoding legado) tratado como "Nenhuma".
- ✅ **2 listas de N3 de pilares (Para/Passa) adicionadas na web** —
  confirmado com o dono: cada pilar SEMPRE gera 2 fichas N3 (mesma
  interpretação SA, resultados diferentes), replicando o que
  `comparison_engine.py` já faz no desktop (`_pil_strip_pp`/
  `_pil_pp_from_id`, contrato `n3_variants/{para,passa}/PL_ABCD_preview_*.dxf`
  gerado por `gerar_pl_dxf_stog.py`, hoje só materializado pelo desktop).
  Adicionadas classes `pilares_n3_para`/`pilares_n3_passa` em
  `ficha_reader.py` (`CLASSES_N1`, `TITULOS_CLASSE`,
  `_normalizar_pilar_n3_variante`) — item_id vira `P1_Para`/`P1_Passa`
  (mesma convenção do desktop), incluem TODOS os pilares (normais +
  especiais, já que a divisão N1 é só por formato/geometria, não relevante
  pro N3). Testado ao vivo: 38 pilares em cada lista, ficha individual
  (`P1_Para`) traz `"Variante N3":"Para"` + todos os campos de interpretação
  do pilar. `foto_n3` retorna `null` honestamente (motor de renderização
  DXF→web pra essas variantes ainda não existe no portal — só no desktop —
  fora do escopo desta fase; não fingir dado que não existe).
- ✅ **Bug evitado: double-counting no `/stats-globais`** — como as 2 classes
  novas reprojetam os mesmos pilares de `pilares`/`pilares_especiais`,
  excluí-las do loop de `n1_total` (senão cada pilar contava 2x nos
  stats de N1) e excluí `pilares`/`pilares_especiais` do loop de `n3_total`
  (senão cada pilar contava 4x em N3: base×2 + variantes×2). Testado ao
  vivo: `n1.total` continua **453** (idêntico ao valor antes da mudança),
  `n3.total` **545** (soma coerente incluindo as variantes, sobre 2
  pavimentos com estado real).
- 🔍 **Investigado, não implementado — selo verde (validação) sincronizar
  com N1 da web:** confirmado que é um gap real. Desktop já tem a
  infraestrutura (`is_validated`/`is_fully_validated` como colunas reais em
  `pillars`/`beams`/`slabs`, badge verde vs azul em `detail_card.py:784`) e
  o portal já retorna `validado` por item em `/n1/{classe}` — mas nada
  conecta os dois hoje (`diagnostic_hub.py`/`sa_db_persistence.py` não
  chamam o portal). Próximo passo: método novo em `drive_client.py`
  (`{item_id: validado}` por classe/pavimento) + hook no commit da SA
  (`sa_db_persistence.py`, ponto único compartilhado local/web) marcando
  `is_validated=True` só pra obras Drive quando bater com o `validado` da
  web. Não implementado ainda (aguardando próxima sessão/priorização).

## Fase 11 — N3 real de LV (Laterais de Viga) via web/headless (2026-07-11)

- 🔍 **Diagnóstico completo do "Processar N1 (Todos/Pavimento) → N3":**
  `jobs.py:86` (`etapa_efetiva = etapa if etapa in ETAPAS_SUBPROCESS else
  "sa"`) — como `"n3"` não está em `ETAPAS_SUBPROCESS = ("triagem",
  "recortes", "sa")`, o botão sempre reexecuta o SA/N1 completo (~10min),
  nunca um passo dedicado de N3. Confirmado ao vivo via processo real rodando
  (`headless_sa_analise.py --pav TERREO --persist-db`).
- 🔍 **Achado: N3 já funcionava, mas só pra FV.** `_generate_fv_n3_nova_previews`
  (headless_sa_analise.py) já chamava `gerar_fv_dxf_stog.py` em pasta
  temporária isolada. LV/PL/LJ nunca eram chamados — por isso só a classe
  "Segmentos Fundos" tinha `foto_n3` ao vivo; Pilares/Lajes/Laterais
  mostravam "artefato ausente" (confirmado abrindo o HTML bruto gerado).
- ✅ **Implementado: N3 real de LV (Para/Passa × Visão Corte/Lateral A/Lateral B)**,
  reaproveitando 100% dos contratos que o SA já calcula
  (`beam['lv_generation_contracts']`, via `_attach_lv_generation_contracts`
  → `build_lv_generation_contracts`, já existia — só nunca era consumido
  pra gerar DXF real):
  - `scripts/gerar_lv_dxf_stog.py`: adicionados `--input-dir`/`--output-dir`
    (LJ já tinha o equivalente; FV também; só LV não tinha) — permite gerar
    isolado sem tocar `Fase-4_Sincronizacao`/`Fase-6_Execucao_CAD` reais da
    obra.
  - `headless_sa_analise.py`: nova `_generate_lv_n3_nova_previews` — escreve
    os 4 contratos (`V{n}_A.json`/`V{n}_B.json` × Para/Passa) na pasta
    temp isolada (mesma do FV) e roda `gerar_lv_dxf_stog.py --behavior
    {Para,Passa} --view {CORTE,A,B}` (6 chamadas/viga), removendo
    `CAD_MOTOR_HEADLESS` do env do subprocess (mesmo motivo do FV: destino já
    isolado, não deixar `guarded_saveas` desviar pra candidato). Chamada
    adicionada dentro do `with tempfile.TemporaryDirectory(...)` do
    `run_analysis()`, ao lado do FV.
  - **Bug adicional achado e corrigido**: `pre_validation_dialog.py
    ._find_beam_dxf` só tratava diretório isolado (`_n3_preview_dir`) pra
    `prefix == 'FV'` — LV caía sempre na pasta real `Fase-6_Execucao_CAD`
    (nunca acharia o isolado). Estendido pra `{'FV', 'LV'}`. Além disso a
    ficha (`preficha_lateral_html.py`) buscava `LV_preview_{beam}_{suffix}.dxf`
    sem o behavior no nome, mas o robô gera
    `LV_preview_{beam}_{Para|Passa}_{suffix}.dxf` (behavior no meio) — nomes
    nunca bateriam mesmo gerando certo. Corrigido: os 2 call-sites de
    `_find_beam_dxf` no estágio N3 agora embutem `behavior` na posição certa
    do nome.
  - Confirma o que o dono explicou: Visão de Corte NÃO é uma classe separada
    — é o mesmo robô LV com `--view CORTE` (vs `--view A`/`--view B`),
    consumindo os mesmos contratos SA por viga, um artefato por
    comportamento (Para/Passa) × vista.
- ✅ **Testado ao vivo, ponta a ponta**, via o próprio botão da web (job real,
  obra 156f05b4.../TERREO): rodou em ~10min45s, log reportou
  `N3 LV isolado: 174 gerado(s), 18 ausente(s)`. Verificados individualmente
  as 4 combinações lado×comportamento pro item V101 — `lateral_a_para`,
  `lateral_a_passa`, `lateral_b_para`, `lateral_b_passa` — todas com
  `foto_n3` presente e coerente com o `Comportamento`/`Lado` da ficha.
  Os 18 ausentes (3 vigas: V103, V108, V132 × 2 behaviors × 3 views) são
  gap de DADOS real, não da minha mudança: `build_lv_generation_contracts`
  não achou a cota LV (`dimension_status: "missing"`) pra essas 3 vigas —
  o robô honestamente recusa gerar em vez de inventar (mesmo princípio já
  usado no resto do sistema). Não investigado o motivo raiz (fora de escopo
  desta fase).
- ⚠️ **CORREÇÃO (2026-07-11) — N3 PL Para/Passa NÃO é pendência de decisão
  manual.** Diagnóstico da Fase 11 misturou duas coisas diferentes:

  | Conceito | O que é de verdade |
  |----------|--------------------|
  | **N3 PL PARA + PASSA** | **Sempre as duas** por pilar. Não é escolha binária “este pilar é Para ou Passa”. O SA/desktop monta **duas projeções** da mesma interpretação N1. |
  | **`lv_para_passa` (N2)** | Atenção humana no CE/recortes reverso — UI de revisão. **Não** é a fonte do N3 de pilar. |

  **Já implementado no desktop (fonte de verdade):**
  1. `pre_validation_dialog.py` → `_build_n3_mode_contract(row, pillar, mode)`
     para `mode in ('para','passa')` — contrato `pil.n3_mode_contract.v2`
     derivado do N1 (vigas que param / passam / chegam / lajes por face).
  2. `_materialize_n3_variant` gera JSON + DXF ABCD/GRADES e publica em
     `DADOS-OBRAS/.../Fase-6_Execucao_CAD/n3_variants/{para|passa}/`
     (`{item}.json`, `PL_ABCD_preview_{item}.dxf`, `PL_GRADES_preview_…`).
  3. Comparison Engine lista virtual `P1_Para` / `P1_Passa` e só fica verde
     se o contrato derivado existir (`n3_variants/...`).

  **Pergunta “manual vs automático” está ENCERRADA:** automático dual no
  SA desktop. Não replicar classificação N2; consumir `n3_variants`.

  **Headless PL (implementado 2026-07-11):**
  - `headless_sa_analise._generate_pl_n3_nova_previews` +
    `PreValidationDialog.materialize_pl_n3_variants` — **sempre PARA+PASSA**
    por pilar; publica em `Fase-6/.../n3_variants/{para|passa}/` (mesmo
    path do CE). Rodado no `run_analysis` junto com FV/LV.
  - Portal: listas `pilares_n3_para`/`passa` já existem (Fase 10); `foto_n3`
    de PL no pack HTML usa o DXF materializado quando o export renderiza.

## Fase 12 — N3 real de LJ (Lajes) + selo verde Drive (2026-07-11)

- ✅ **N3 real de LJ implementado** — ao contrário do que eu tinha concluído
  antes, LJ JÁ tem um mecanismo de materialização automática funcionando no
  desktop: `MainWindow._materialize_slabs_for_n1_n3_and_robo` (main.py:14897)
  converte `slabs_found` → `_slab_to_n1_robot_ficha` → `_merge_lj_n3_teacher`
  (sem gabarito N2/N4) → grava `JSON_Lajes/{nome}.json` → roda
  `gerar_lj_dxf_stog.py`. Só não rodava no headless porque
  `_sa_read_only_run=True` desativa essa materialização de propósito
  (`if _sa_read_only: n_lj_json, n_lj_el = 0, 0`, main.py:6973) — proteção
  contra escrever na obra real, correta, mas por isso LJ nunca tinha N3.
  Implementado `_generate_lj_n3_nova_previews` (headless_sa_analise.py) que
  chama os MESMOS `_slab_to_n1_robot_ficha`/`_merge_lj_n3_teacher` do
  `window`, mas grava em pasta temp isolada (mesmo padrão do FV/LV) em vez de
  `Fase-4_Sincronizacao`/`Fase-6_Execucao_CAD` reais. `gerar_lj_dxf_stog.py`
  já tinha `--json-dir`/`--out-dir` (não precisou adicionar, diferente de LV).
  `_find_beam_dxf` (pre_validation_dialog.py) estendido pra tratar isolamento
  também pra `LJ` (antes só FV/LV). **Testado ao vivo** via o botão real da
  web: 25/25 lajes geradas (0 falhas) — `foto_n3` confirmado presente e
  coerente pra L101.
- ✅ **Selo verde (validação) sincronizado do N1 web → SA da app —
  implementado.** `drive_client.listar_itens_n1(obra_id, classe, pavimento)`
  (novo — reusa `/n1/{classe}` já existente) + `MainWindow.
  _sincronizar_selo_verde_drive` (main.py, chamado em `load_project_action`
  logo após carregar pillars/slabs do DB, só quando `not _sa_read_only_run`
  — nunca roda no headless/servidor, só na app). Pra obras Drive
  (`db.obra_e_drive`), busca `pilares`/`pilares_especiais`/`lajes` validados
  no N1 da web e marca `is_validated=True` (selo verde) nos itens locais
  cujo nome bate — nunca mexe no selo azul (`is_fully_validated`, completude
  de campos local) nem rebaixa um selo já setado. **Vigas ficaram de fora**
  de propósito: as classes N1 da web são por SEGMENTO
  (`lateral_a_para` etc.), não por viga inteira — falta decidir a regra de
  agregação (todos os segmentos validados = viga validada?) antes de
  implementar sem inventar comportamento.
- 🔍 **"Ficha de interpretação das lajes" — investigado, não existe em
  lugar nenhum.** O portal (`ficha_reader.py`) espera
  `convencao_niveis/interpretacao_niveis.html` e
  `convencao_pilares/interpretacao_pilares.html`, mas **nada no repo
  inteiro escreve esses arquivos** — nem desktop nem headless. O que existe
  de fato é a aba "Convenção de Níveis" do desktop
  (`pre_validation_dialog.py:3949`), que é uma **tabela Qt interativa ao
  vivo** (`QTableWidget` + render de DXF em thread), nunca serializada pra
  HTML estático. Portanto essas 2 classes N1 sempre vão mostrar vazio no
  portal — não é bug pontual, é uma feature nunca implementada dos dois
  lados. Pendente: dono explicar o conteúdo esperado (igual fez pra LV)
  antes de eu implementar um exportador HTML pra essa tabela.

## Fase 13 — Cache/expiração dos arquivos baixados do Drive (2026-07-11)

- ✅ **Implementado: invalidação por versão, nunca por tempo.**
  - Schema (`database.py`): coluna `remoto_versao` (aditiva, via
    `_check_and_add_column`) em `drive_obras` e `drive_documentos` — guarda o
    header HTTP `Last-Modified` do portal no momento do último download.
    Testado ao vivo contra `project_data.vision` real: coluna aplicada nas
    duas tabelas sem erro.
  - `drive_client.py`: `_baixar_arquivo` agora guarda
    `self.ultimo_last_modified` (do header da resposta); novo
    `obter_last_modified(url)` faz **HEAD** (sem baixar corpo) só pra
    comparar; novos `url_recorte`/`url_documento` (extraídos de
    `baixar_recorte`/`baixar_documento` pra reuso).
  - `database.py`: `atualizar_drive_item_versao`/
    `atualizar_drive_documento_versao` (gravam a versão após download) +
    `tem_item_validado_para_obra(obra_nome)` — true se QUALQUER pilar/laje/
    viga de QUALQUER pavimento dessa obra já tem selo verde. Testado ao vivo:
    retornou `False` pra Obra-Teste-Inicial2 (nenhum item validado ainda,
    coerente).
  - `drive_download_hook.py` (`garantir_drive_download`) reescrito: antes só
    baixava se o arquivo NÃO existisse local. Agora, mesmo existindo, faz o
    HEAD leve e compara com `remoto_versao` conhecida — só re-baixa se
    mudou. Se mudou E a obra já tem item validado, **não sobrescreve**
    (só loga aviso) — protege trabalho de validação em andamento. Sem
    `Last-Modified` dos dois lados pra comparar, mantém a cópia local (nunca
    expira "no escuro").
- Escopo da proteção é a OBRA inteira (todos os pavimentos), não só o
  pavimento do arquivo em questão — decisão deliberada de errar pro lado
  de proteger demais.

## Fora de escopo (fases futuras, não implementadas agora)

- Sincronizar ficha/validação SA campo-a-campo entre web e app (dono decidiu: NÃO — ver Fase 12/instrução do dono, app é só treino/validação interna, sem upload app→portal).
- Selo verde de VIGAS (segmentos web × viga inteira local) — falta decidir regra de agregação (ver Fase 12).
- Exportador HTML da ficha "Convenção de Níveis"/"Convenção de Pilares" — não existe em nenhum lugar hoje (ver Fase 12), pendente de explicação do dono sobre o conteúdo esperado.
- Portal: polish de `foto_n3` PL em todos os pavimentos (materialização headless
  já grava `n3_variants`; render web pode ainda falhar em edge cases).
- Upload no sentido reverso (app → portal) — decidido que NÃO vai ter.
- Confirmação/aviso interativo (dialog) quando a atualização é pulada por item validado — hoje só loga; poderia virar um prompt visível na UI se o dono quiser.
- Cache/expiração de arquivos baixados — recomendação dada (invalidação por versão + proteção de item já validado localmente, nunca sobrescrever silenciosamente), aguardando decisão do dono se implementa agora.
