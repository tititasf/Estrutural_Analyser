-- schema.sql — DDL do banco do portal (portal_data.db), fisicamente separado de project_data.vision.
-- Regra de fronteira (HANDOFF §0/§3): o portal NUNCA escreve na curadoria Arete.
-- Fonte canônica: docs/HANDOFF-DATAENGINEER-PORTAL.md §2.
-- Este arquivo é a referência do schema; a aplicação real é feita por migrations/001_init.sql.

-- Tabela de controle de versão do schema (HANDOFF §6).
CREATE TABLE IF NOT EXISTS portal_schema_version (
    version     INTEGER PRIMARY KEY,
    aplicada_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    descricao   TEXT
);

-- 2.1 portal_membros — login simples por membro (DP-3).
CREATE TABLE IF NOT EXISTS portal_membros (
    id            TEXT PRIMARY KEY,
    login         TEXT NOT NULL UNIQUE,
    nome          TEXT NOT NULL,
    email         TEXT,
    senha_hash    TEXT NOT NULL,
    papel         TEXT NOT NULL DEFAULT 'membro'
                  CHECK (papel IN ('membro','dono')),
    drive_folder_id TEXT UNIQUE,
    ativo         INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- 2.2 portal_obras — obras enviadas e seu estado.
CREATE TABLE IF NOT EXISTS portal_obras (
    id             TEXT PRIMARY KEY,
    membro_id      TEXT NOT NULL REFERENCES portal_membros(id),
    nome           TEXT NOT NULL,
    pasta_drive_id TEXT NOT NULL,
    arquivo_drive_id TEXT,
    arquivo_nome   TEXT,
    arquivo_hash   TEXT,
    estado         TEXT NOT NULL DEFAULT 'aguardando_ingestao'
                   CHECK (estado IN ('aguardando_ingestao','processando','pronta','erro')),
    erro_msg       TEXT,
    local_path     TEXT,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    detectada_em   TEXT,
    processada_em  TEXT,
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- 2.3 portal_jobs — fila de processamento (1 por vez; exclusão real via single_instance.py).
CREATE TABLE IF NOT EXISTS portal_jobs (
    id             TEXT PRIMARY KEY,
    obra_id        TEXT NOT NULL REFERENCES portal_obras(id),
    status         TEXT NOT NULL DEFAULT 'na_fila'
                   CHECK (status IN ('na_fila','executando','concluido','falhou','cancelado')),
    engine_version TEXT,
    prioridade     INTEGER NOT NULL DEFAULT 0,
    tentativas     INTEGER NOT NULL DEFAULT 0,
    log_path       TEXT,
    run_id         TEXT,
    erro_msg       TEXT,
    enfileirado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    iniciado_em    TEXT,
    finalizado_em  TEXT,
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- 2.4 portal_drive_sync_state — memória do poller (1 estado por usuário, DP-10).
CREATE TABLE IF NOT EXISTS portal_drive_sync_state (
    membro_id       TEXT PRIMARY KEY REFERENCES portal_membros(id),
    pasta_drive_id  TEXT NOT NULL,
    ultimo_arquivo_id   TEXT,
    ultimo_arquivo_hash TEXT,
    ultimo_modified_time TEXT,
    ultimo_page_token   TEXT,
    ultimo_scan_em      TEXT,
    ultimo_scan_status  TEXT DEFAULT 'ok'
                        CHECK (ultimo_scan_status IN ('ok','drive_indisponivel')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- 2.5 portal_comentarios_equipe — evidência T0 assinada (imutável por convenção).
CREATE TABLE IF NOT EXISTS portal_comentarios_equipe (
    id            TEXT PRIMARY KEY,
    obra_id       TEXT NOT NULL REFERENCES portal_obras(id),
    membro_id     TEXT NOT NULL REFERENCES portal_membros(id),
    namespace     TEXT NOT NULL DEFAULT 'equipe'
                  CHECK (namespace = 'equipe'),
    classe        TEXT,
    pavimento     TEXT,
    item_id       TEXT,
    texto         TEXT NOT NULL,
    tipo          TEXT NOT NULL DEFAULT 'observacao'
                  CHECK (tipo IN ('erro','observacao')),
    run_id        TEXT,
    engine_version TEXT,
    exportado_triagem INTEGER NOT NULL DEFAULT 0
                  CHECK (exportado_triagem IN (0,1)),
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- 2.6 portal_n5_releases — auditoria de liberação self-service (DP-13, R9). Append-only.
CREATE TABLE IF NOT EXISTS portal_n5_releases (
    id            TEXT PRIMARY KEY,
    obra_id       TEXT NOT NULL REFERENCES portal_obras(id),
    classe        TEXT NOT NULL
                  CHECK (classe IN ('PL','LV','FV','LJ')),
    pavimento     TEXT NOT NULL DEFAULT 'GERAL',
    liberado_por  TEXT NOT NULL REFERENCES portal_membros(id),
    status_certificacao TEXT NOT NULL
                  CHECK (status_certificacao IN ('certificado','beta')),
    engine_version TEXT,
    job_id        TEXT REFERENCES portal_jobs(id),
    dxf_path      TEXT,
    dxf_hash      TEXT,
    liberado_em   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- Índices (HANDOFF §4).
CREATE INDEX IF NOT EXISTS idx_obras_membro_estado ON portal_obras(membro_id, estado, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_obras_pasta_arquivo ON portal_obras(pasta_drive_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_obras_hash ON portal_obras(arquivo_hash) WHERE arquivo_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_fila ON portal_jobs(status, prioridade DESC, enfileirado_em) WHERE status = 'na_fila';
CREATE INDEX IF NOT EXISTS idx_jobs_obra ON portal_jobs(obra_id, enfileirado_em DESC);
CREATE INDEX IF NOT EXISTS idx_coment_export ON portal_comentarios_equipe(exportado_triagem, created_at) WHERE exportado_triagem = 0;
CREATE INDEX IF NOT EXISTS idx_coment_obra ON portal_comentarios_equipe(obra_id, item_id);
CREATE INDEX IF NOT EXISTS idx_n5_obra ON portal_n5_releases(obra_id, classe, pavimento, liberado_em DESC);
CREATE INDEX IF NOT EXISTS idx_n5_auditoria ON portal_n5_releases(liberado_em DESC);
