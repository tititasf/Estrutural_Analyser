# HANDOFF — Data Engineer: Schema de Dados do Portal

**Autor:** Dara (Data Engineer / AIOS)
**Data:** 2026-07-05
**Status:** PROPOSTA — pronta para virar migration real (`portal/db/migrations/001_init.sql`)
**Fonte canônica de produto:** `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` (DP-1 a DP-14, gates P0–P6, §3 regra de fronteira, R1–R9)
**Fonte canônica de dados Arete:** `project_data.vision` (SQLite, curadoria) — **fora do escopo de escrita deste schema**

---

## 0. Regra de fronteira (invariante deste documento)

> O portal **lê** artefatos e **grava APENAS**: obras enviadas, jobs, comentários T0.
> **Nunca escreve** em fichas, golden, regras ou tabelas de curadoria. (§3 do masterplan)

Consequência de engenharia de dados, decidida aqui e justificada em §3 abaixo:

- **O portal usa um arquivo SQLite PRÓPRIO e separado: `portal/portal_data.db`.**
- Ele **nunca** abre `project_data.vision` em modo escrita. Se precisar ler algo de lá
  (ex.: status de certificação de uma classe), abre em modo **read-only**
  (`file:...project_data.vision?mode=ro`) — nunca `ATTACH` com escrita, nunca `INSERT`.
- Nenhuma FK deste schema aponta para uma tabela de `project_data.vision` (SQLite não
  reforça FK cross-database de qualquer forma; a separação é física e proposital).

Tabelas do Arete que NÃO devem ser tocadas pela escrita do portal (referência, para não
haver dúvida): `works`, `team_members`, `training_events`, `projects`, `pillars`, `beams`,
`slabs`, `contours`, `generated_scripts`, `pre_processing`, `project_documents`,
`project_specifications`, `clients`, `communication_history`, `beam_elements`.

> Nota sobre nomes que colidem: o Arete já tem `works` e `team_members`. Para não confundir
> os dois mundos, as tabelas do portal usam prefixo semântico próprio
> (`portal_membros`, `portal_obras`, ...). Estão em arquivo diferente, mas o prefixo evita
> erro humano se algum dia alguém fizer `ATTACH`.

---

## 1. Motor de banco (escolha + justificativa)

**Decisão: SQLite em arquivo separado — `portal/portal_data.db`.** Não é o mesmo arquivo
do Arete, não é Postgres.

| Opção | Veredito | Porquê |
|---|---|---|
| Mesmo arquivo `project_data.vision`, tabelas com prefixo | ❌ Rejeitado | Viola o espírito da regra de fronteira: um único handle de escrita no arquivo de curadoria significa que um bug no portal pode corromper a curadoria (o SQLite trava o arquivo inteiro em escrita, não por tabela). Backup/restore acopla os dois. Um `DROP`/migration equivocado do portal atinge a curadoria. Risco assimétrico inaceitável — a curadoria é o produto (DP-9). |
| **SQLite separado `portal_data.db`** | ✅ **Escolhido** | Isolamento físico total: o processo de escrita do portal nunca segura o lock do arquivo do Arete. Backup independente (P5 lista os dois destinos separados). Um reset do portal não arranha a curadoria. Zero servidor a operar — casa com "servidor = workstation do dono" (DP-2) e "3–5 pessoas". Já é o motor do projeto (`project_data.vision` é SQLite), então zero dependência nova. |
| Postgres/Supabase | ❌ Rejeitado | Anti-escopo: "sem porta pública, sem SaaS, sem multi-tenant" (§7). 3–5 usuários locais na VPN não justificam um servidor de banco. Adicionaria dependência de infra que contradiz DP-1/DP-2 (soberania, custo zero). |

**Config do arquivo do portal (aplicar na conexão):**
- `PRAGMA journal_mode=WAL;` — leitura concorrente (o portal FastAPI serve fichas
  enquanto o worker de job grava status). WAL permite N leitores + 1 escritor.
- `PRAGMA foreign_keys=ON;` — SQLite desliga FK por padrão; ligar por conexão.
- `PRAGMA busy_timeout=5000;` — espera o lock em vez de erro imediato (fila de 1 job só
  gera contenção rara, mas o web serve leituras em paralelo).

> A **fila de 1 job por vez** NÃO depende do lock do SQLite. Ela usa
> `scripts/arete/single_instance.py::acquire_lock('portal_job')` (trava de arquivo do SO,
> liberada mesmo em crash — DP/P2 do masterplan). O banco só **registra** o estado da fila;
> a exclusão mútua real é a trava de arquivo.

---

## 2. Tabelas (colunas, tipos, constraints)

Convenções (herdadas dos princípios Dara): toda tabela tem PK, `created_at`; tabelas de
entidade mutável têm `updated_at`; timestamps em UTC ISO-8601 (`TEXT`, formato
`YYYY-MM-DDTHH:MM:SSZ`) para casar com o hábito do repo e evitar ambiguidade de fuso.
IDs de entidade são `TEXT` (UUID/slug) para casar com o padrão do Arete (`id TEXT PRIMARY KEY`).

### 2.1 `portal_membros` — login simples por membro (DP-3)

```sql
CREATE TABLE portal_membros (
    id            TEXT PRIMARY KEY,              -- uuid
    login         TEXT NOT NULL UNIQUE,          -- usado no namespace T0 "equipe:<login>"
    nome          TEXT NOT NULL,
    email         TEXT,
    senha_hash    TEXT NOT NULL,                 -- bcrypt/argon2 — NUNCA senha em claro
    papel         TEXT NOT NULL DEFAULT 'membro' -- 'membro' | 'dono'
                  CHECK (papel IN ('membro','dono')),
    drive_folder_id TEXT UNIQUE,                 -- pasta pessoal no Drive (DP-10, 1 por usuário)
    ativo         INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
```
- `login` é a identidade que assina o comentário T0 (`equipe:<login>`), então é UNIQUE e imutável na prática.
- `drive_folder_id` liga o membro à pasta que o poller varre. UNIQUE: uma pasta = um dono (DP-10).
- Sem sistema de permissões complexo (DP-3): `papel` é só 'membro' ou 'dono'.

### 2.2 `portal_obras` — obras enviadas e seu estado

```sql
CREATE TABLE portal_obras (
    id             TEXT PRIMARY KEY,             -- uuid do portal (NÃO é o works.name do Arete)
    membro_id      TEXT NOT NULL REFERENCES portal_membros(id),
    nome           TEXT NOT NULL,                -- nome da obra (derivado da pasta/arquivo)
    pasta_drive_id TEXT NOT NULL,                -- pasta do Drive de origem (DP-10)
    arquivo_drive_id TEXT,                       -- id do arquivo específico detectado (DWG/DXF)
    arquivo_nome   TEXT,                         -- nome do arquivo original
    arquivo_hash   TEXT,                         -- md5/sha256 do conteúdo baixado (dedup + P5 reprodutibilidade)
    estado         TEXT NOT NULL DEFAULT 'aguardando_ingestao'
                   CHECK (estado IN ('aguardando_ingestao','processando','pronta','erro')),
    erro_msg       TEXT,                         -- preenchido quando estado='erro' (R6 quarentena)
    local_path     TEXT,                         -- caminho na workstation após download
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    detectada_em   TEXT,                         -- quando o poller viu (DP-11)
    processada_em  TEXT,                         -- quando terminou o pipeline
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
```
- **Estados** casam com o masterplan: `aguardando_ingestao` (R8 — Drive fora do ar deixa a
  obra aqui, não em erro), `processando`, `pronta`, `erro`.
- `arquivo_hash` serve dedup (poller não reprocessa o mesmo conteúdo) **e** rastreabilidade P5.
- Não há FK para `works` do Arete — o portal é dono do ciclo de vida da obra do lado do portal;
  a ligação com a curadoria é feita por nome/hash quando o dono importa, fora deste schema.

### 2.3 `portal_jobs` — fila de processamento (1 por vez)

```sql
CREATE TABLE portal_jobs (
    id             TEXT PRIMARY KEY,             -- uuid
    obra_id        TEXT NOT NULL REFERENCES portal_obras(id),
    status         TEXT NOT NULL DEFAULT 'na_fila'
                   CHECK (status IN ('na_fila','executando','concluido','falhou','cancelado')),
    engine_version TEXT,                         -- commit do motor no momento (P5 reprodutibilidade)
    prioridade     INTEGER NOT NULL DEFAULT 0,   -- desempate na fila (maior = antes)
    tentativas     INTEGER NOT NULL DEFAULT 0,   -- re-enfileiramento após falha (R6/R8)
    log_path       TEXT,                         -- caminho do log da run (JSONL de triagem etc.)
    run_id         TEXT,                         -- id da run do pipeline (casa com o modelo de eventos)
    erro_msg       TEXT,
    enfileirado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    iniciado_em    TEXT,
    finalizado_em  TEXT,
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
```
- **1 job por vez** é garantido pela trava `single_instance` (§1); a tabela só reflete estado.
- `engine_version` obrigatório na prática (gravado ao iniciar) — é o P5 do masterplan.
- `run_id` liga o job aos eventos T0 do modelo de eventos (comentários carregam `run_id` + `engine_version`, P2).

### 2.4 `portal_drive_sync_state` — memória do poller (não reprocessar)

```sql
CREATE TABLE portal_drive_sync_state (
    membro_id       TEXT PRIMARY KEY REFERENCES portal_membros(id),  -- 1 estado por usuário (DP-10)
    pasta_drive_id  TEXT NOT NULL,
    ultimo_arquivo_id   TEXT,                    -- último file id do Drive processado
    ultimo_arquivo_hash TEXT,                    -- hash do último conteúdo visto (dedup real)
    ultimo_modified_time TEXT,                   -- Drive files.modifiedTime do último visto (delta query)
    ultimo_page_token   TEXT,                    -- changes.list pageToken (se migrar de polling p/ changes API)
    ultimo_scan_em      TEXT,                    -- quando o poller varreu por último
    ultimo_scan_status  TEXT DEFAULT 'ok'        -- 'ok' | 'drive_indisponivel' (R8: loga, não derruba)
                        CHECK (ultimo_scan_status IN ('ok','drive_indisponivel')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
```
- **Chave = membro_id** (1 pasta por usuário, DP-10). O poller lê este registro para saber
  "o que já vi" e não rebaixar/reprocessar (DP-11).
- Dedup em duas camadas: `ultimo_modified_time` (barato, delta na query do Drive) +
  `ultimo_arquivo_hash` (definitivo, pega arquivo renomeado com mesmo conteúdo).
- `ultimo_scan_status='drive_indisponivel'` implementa R8: registra a falha e a obra
  correspondente fica `aguardando_ingestao` — o serviço não cai.

### 2.5 `portal_comentarios_equipe` — evidência T0 assinada

```sql
CREATE TABLE portal_comentarios_equipe (
    id            TEXT PRIMARY KEY,              -- uuid
    obra_id       TEXT NOT NULL REFERENCES portal_obras(id),
    membro_id     TEXT NOT NULL REFERENCES portal_membros(id),
    namespace     TEXT NOT NULL DEFAULT 'equipe' -- prefixo do funil T0 (§3): marcado_por = 'equipe:<login>'
                  CHECK (namespace = 'equipe'),
    classe        TEXT,                          -- PL|LV|FV|LJ do item comentado (opcional)
    pavimento     TEXT,                          -- pavimento do item (opcional)
    item_id       TEXT,                          -- id do item/ficha (ex.: PL_preview_003) (opcional)
    texto         TEXT NOT NULL,                 -- corpo do comentário / marca de "ERRADA"
    tipo          TEXT NOT NULL DEFAULT 'observacao'
                  CHECK (tipo IN ('erro','observacao')),  -- 'erro' = checkbox ERRADA (§2 do masterplan)
    run_id        TEXT,                          -- run do pipeline sobre a qual comentou
    engine_version TEXT,                         -- commit do motor no momento do comentário (P2)
    exportado_triagem INTEGER NOT NULL DEFAULT 0 -- 0=ainda não entrou no funil Arete; 1=exportado pelo dono
                  CHECK (exportado_triagem IN (0,1)),
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
```
- **Imutável por convenção**: comentário é evidência T0 — não se edita depois, no máximo se
  adiciona outro. (Espelha o modelo de eventos imutáveis da harmonização §7.)
- `namespace='equipe'` + `membro.login` reconstrói `marcado_por = 'equipe:<login>'` exigido em §3.
- `exportado_triagem`: o portal **não escreve** em `training_events` do Arete (fronteira). Ele
  marca o comentário como "pronto para triagem"; o **dono**, na cabine PySide6, tria e importa
  para o funil Arete (invariantes 1 e 2 — curadoria exclusiva do dono, R7). Este flag é o
  ponto de entrega, não uma escrita cross-DB.

### 2.6 `portal_n5_releases` — auditoria de liberação self-service (DP-13, R9)

```sql
CREATE TABLE portal_n5_releases (
    id            TEXT PRIMARY KEY,              -- uuid
    obra_id       TEXT NOT NULL REFERENCES portal_obras(id),
    classe        TEXT NOT NULL                  -- N5 é por classe (DP-12); domínio real do assemble_n5
                  CHECK (classe IN ('PL','LV','FV','LJ')),
    pavimento     TEXT NOT NULL DEFAULT 'GERAL', -- N5 é por classe+pavimento (DP-12); 'GERAL' quando único
    liberado_por  TEXT NOT NULL REFERENCES portal_membros(id),  -- self-service (DP-13): quem clicou
    status_certificacao TEXT NOT NULL            -- SNAPSHOT do rótulo Arete NAQUELE momento (R9)
                  CHECK (status_certificacao IN ('certificado','beta')),
    engine_version TEXT,                         -- commit do motor que gerou o N5 (P5)
    job_id        TEXT REFERENCES portal_jobs(id), -- job que produziu o DXF liberado
    dxf_path      TEXT,                          -- N5_{classe}_{pav}.dxf entregue
    dxf_hash      TEXT,                          -- hash do DXF liberado (prova do que foi baixado)
    liberado_em   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
```
- **`status_certificacao` é um SNAPSHOT congelado**, não uma FK viva. É o coração do R9: registra
  se a classe estava `certificado` ou `beta` **no instante da liberação**. Se depois a classe mudar
  de status no Arete, este registro **não muda** — é o que permite auditar "o que ele sabia quando liberou".
- `classe` restrita a `PL/LV/FV/LJ` — domínio real de `assemble_n5` (validado no código;
  `raise ValueError` para outras). `pavimento` casa com o `pav_tag` do nome do arquivo
  `N5_{classe}_{pav}.dxf`.
- Sem UNIQUE em (obra,classe,pavimento): re-liberações após reprocessamento são eventos
  distintos e auditáveis (append-only), não upsert.

---

## 3. Relacionamentos (FKs)

```
portal_membros (1) ──< (N) portal_obras            [membro_id]        quem enviou a obra
portal_membros (1) ──< (N) portal_comentarios_equipe [membro_id]      quem assinou o T0
portal_membros (1) ──< (N) portal_n5_releases      [liberado_por]     quem liberou o N5
portal_membros (1) ──  (1) portal_drive_sync_state [membro_id PK/FK]  estado do poller por usuário

portal_obras   (1) ──< (N) portal_jobs             [obra_id]          jobs da obra
portal_obras   (1) ──< (N) portal_comentarios_equipe [obra_id]        comentários da obra
portal_obras   (1) ──< (N) portal_n5_releases      [obra_id]          liberações da obra

portal_jobs    (1) ──< (N) portal_n5_releases      [job_id, nullable] job que gerou o DXF
```

**Fronteira reforçada:** nenhuma FK cruza para `project_data.vision`. As ligações com a
curadoria (importar comentário para `training_events`, ler status de certificação da classe)
são feitas **em runtime pela cabine do dono**, não por chave estrangeira do banco do portal.

---

## 4. Índices e queries mais importantes

```sql
-- Q1: "listar obras de um usuário com status" (tela principal do membro)
CREATE INDEX idx_obras_membro_estado ON portal_obras(membro_id, estado, created_at DESC);
--   SELECT * FROM portal_obras WHERE membro_id=? ORDER BY created_at DESC;

-- Q2: "última obra por pasta do Drive para o poller" (DP-11, não reprocessar)
CREATE INDEX idx_obras_pasta_arquivo ON portal_obras(pasta_drive_id, created_at DESC);
CREATE UNIQUE INDEX idx_obras_hash ON portal_obras(arquivo_hash) WHERE arquivo_hash IS NOT NULL;
--   dedup real: antes de inserir obra nova, o poller checa se o hash já existe.
--   drive_sync_state.membro_id (PK) já dá lookup O(1) do "último visto" por usuário.

-- Q3: "próximo job da fila" (worker de 1 job por vez)
CREATE INDEX idx_jobs_fila ON portal_jobs(status, prioridade DESC, enfileirado_em)
    WHERE status = 'na_fila';
--   SELECT * FROM portal_jobs WHERE status='na_fila'
--   ORDER BY prioridade DESC, enfileirado_em LIMIT 1;

-- Q4: "jobs de uma obra" (histórico/estado na página de resultado)
CREATE INDEX idx_jobs_obra ON portal_jobs(obra_id, enfileirado_em DESC);

-- Q5: "comentários T0 ainda não triados" (bandeja do dono na cabine)
CREATE INDEX idx_coment_export ON portal_comentarios_equipe(exportado_triagem, created_at)
    WHERE exportado_triagem = 0;

-- Q6: "comentários de uma obra" (render na página de ficha)
CREATE INDEX idx_coment_obra ON portal_comentarios_equipe(obra_id, item_id);

-- Q7: auditoria de liberações N5 (R9) — por obra e cronológico global
CREATE INDEX idx_n5_obra ON portal_n5_releases(obra_id, classe, pavimento, liberado_em DESC);
CREATE INDEX idx_n5_auditoria ON portal_n5_releases(liberado_em DESC);
```

`portal_membros.login` e `portal_membros.drive_folder_id` já ganham índice implícito por serem UNIQUE.

---

## 5. Rollup de auditoria N5 — "quem liberou o quê, quando, e a classe estava certificada?"

O R9 do masterplan é atendido por **três colunas append-only** em `portal_n5_releases`:
`liberado_por`, `liberado_em`, `status_certificacao` (snapshot). Como o status é **congelado
no momento da liberação** (§2.6), a query de auditoria é direta e não depende do estado atual
do Arete:

```sql
-- Trilha de auditoria completa: quem, o quê, quando, e o rótulo NAQUELE momento
SELECT
    r.liberado_em,
    m.login                AS liberado_por,
    o.nome                 AS obra,
    r.classe,
    r.pavimento,
    r.status_certificacao  AS status_no_momento_da_liberacao,  -- snapshot congelado (R9)
    r.engine_version,
    r.dxf_hash
FROM portal_n5_releases r
JOIN portal_membros m ON m.id = r.liberado_por
JOIN portal_obras   o ON o.id = r.obra_id
ORDER BY r.liberado_em DESC;
```

Perguntas que isso responde sem cálculo extra:
- **"Quem liberou N5 de classe `beta`?"** → `WHERE status_certificacao = 'beta'` — expõe
  exatamente os casos de risco do R9 (usuário liberou algo ainda em treino).
- **"Quando a obra X teve seu FV liberado e com qual motor?"** →
  `WHERE obra_id=? AND classe='FV'` devolve `liberado_em` + `engine_version`.
- **"Este DXF entregue corresponde a qual run?"** → `dxf_hash` + `job_id` → `portal_jobs.run_id`.

Por que snapshot e não FK viva para o status atual da classe: se guardássemos só um ponteiro
para o status corrente do Arete, uma classe que virou `certificado` depois apagaria a evidência
de que foi liberada quando era `beta` — destruindo justamente a auditoria que o R9 pede. O
snapshot preserva a verdade histórica. (Princípio Dara: trilha de auditoria imutável.)

O portal **lê** o status corrente da classe de `project_data.vision` em modo read-only apenas
para (a) exibir o rótulo na tela de liberação (R3/R9) e (b) gravar o snapshot. Nunca escreve lá.

---

## 6. Migração / versionamento do schema (leve — 3–5 usuários)

Nada de Alembic/ferramenta pesada. Padrão de **migrations SQL numeradas + tabela de versão**,
idempotente, aplicável no boot do serviço.

```
portal/db/migrations/
  001_init.sql          -- cria todas as tabelas + índices desta proposta
  002_xxx.sql           -- próximas alterações, sempre aditivas quando possível
```

Tabela de controle (primeira coisa que `001_init.sql` cria):

```sql
CREATE TABLE IF NOT EXISTS portal_schema_version (
    version     INTEGER PRIMARY KEY,
    aplicada_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    descricao   TEXT
);
```

Runner mínimo (pseudo-Python, roda no startup do FastAPI, dentro de transação por arquivo):

```python
def migrate(conn, migrations_dir):
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""CREATE TABLE IF NOT EXISTS portal_schema_version(
        version INTEGER PRIMARY KEY, aplicada_em TEXT
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')), descricao TEXT)""")
    atual = conn.execute("SELECT COALESCE(MAX(version),0) FROM portal_schema_version").fetchone()[0]
    for path in sorted(migrations_dir.glob("*.sql")):        # 001, 002, ...
        ver = int(path.stem.split("_")[0])
        if ver <= atual:
            continue
        with conn:                                           # transação por migration
            conn.executescript(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO portal_schema_version(version, descricao) VALUES(?,?)",
                         (ver, path.stem))
```

Regras de disciplina (herdadas dos princípios de migração segura):
- **Idempotência**: todo DDL usa `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`.
- **Aditivo primeiro**: preferir `ADD COLUMN` a recriar tabela (SQLite não faz `DROP COLUMN`
  fácil; evita perda de dado).
- **Backup antes de migrar** (casa com P5): copiar `portal_data.db` → `portal_data.db.bak-{version}`
  antes de aplicar uma migration que não seja puramente `IF NOT EXISTS`. Nunca criar tabela de
  backup dentro do próprio arquivo — usar cópia de arquivo (o SQLite permite `sqlite3 .backup`).
- **Rollback**: para 3–5 usuários, rollback = restaurar o `.bak-{version}`. Cada migration não
  trivial deve ter um `NNN_rollback.sql` comentado com o passo de reversão manual.
- **Nunca `DROP` sem aprovação explícita** (governança SQL do agente).

---

## Resumo (≤150 palavras)

Projetei o schema do **portal como banco SQLite fisicamente separado** (`portal/portal_data.db`),
nunca escrevendo em `project_data.vision` (regra de fronteira §3) — justifiquei a rejeição de
"mesmo arquivo com prefixo" (lock único acopla a curadoria ao portal, risco assimétrico) e de
Postgres (anti-escopo). Entreguei 6 tabelas + tabela de versão: `portal_membros`, `portal_obras`
(estados `aguardando_ingestao/processando/pronta/erro`), `portal_jobs` (fila com `engine_version`,
exclusão via `single_instance`), `portal_drive_sync_state` (memória do poller por usuário, dedup
por hash+modifiedTime), `portal_comentarios_equipe` (T0 `equipe:*`, imutável, flag de export para
triagem do dono) e `portal_n5_releases` (`PL/LV/FV/LJ`, snapshot congelado de certificação para o
R9). Ancorei tudo no código real (`assemble_n5`, `single_instance`, `training_events`). Incluí FKs,
7 índices para as queries-chave, a query de auditoria N5 e migrations SQL numeradas idempotentes.

Arquivo: `D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\docs\HANDOFF-DATAENGINEER-PORTAL.md`
</content>
</invoke>
