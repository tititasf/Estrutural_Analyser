-- 002_documentos.sql — obra vira CONTAINER de documentos (2026-07-06).
--
-- Achado testando com Obra_TREINO_1 real: uma obra de verdade é uma pasta que
-- recebe VÁRIOS documentos (um por pavimento x classe — ex.: "ALIMONTI - PARAISO
-- - 13° PAV.- PL - R00.dxf", "...- LV - R00.dxf", etc.), não "1 upload = 1 obra"
-- como o portal fazia até aqui. O dono cria a obra (nome + descrição), depois
-- envia quantos documentos quiser; a triagem classifica TODOS de uma vez.
--
-- portal_obras.arquivo_nome/arquivo_hash/arquivo_drive_id ficam MANTIDOS (não
-- removidos — SQLite não tem DROP COLUMN barato e a obra de teste já criada em
-- 2026-07-06 os usa) mas viram OPCIONAIS/legado: obras criadas pelo NOVO fluxo
-- (POST /obras/criar) os deixam NULL — os documentos de verdade moram em
-- portal_documentos. estado='aguardando_ingestao' é reusado como "container
-- criado, aguardando documentos" (evita migrar o CHECK constraint do enum).
--
-- Nao idempotente por si so' (ALTER TABLE ADD COLUMN nao aceita IF NOT EXISTS
-- no SQLite) — depende do runner (connection.py::migrate) nunca reaplicar uma
-- versao ja registrada em portal_schema_version, mesmo padrao de 001_init.sql.

ALTER TABLE portal_obras ADD COLUMN descricao TEXT;

CREATE TABLE IF NOT EXISTS portal_documentos (
    id                    TEXT PRIMARY KEY,
    obra_id               TEXT NOT NULL REFERENCES portal_obras(id),
    arquivo_nome          TEXT NOT NULL,
    arquivo_drive_id      TEXT,
    arquivo_hash          TEXT,
    local_path            TEXT,
    -- sugestao automatica (classificador por nome de arquivo) — NUNCA confiada
    -- sem revisao humana (triagem = "humano confirma/edita", masterplan §0).
    classe_sugerida       TEXT,
    pavimento_sugerido    TEXT,
    -- confirmacao humana (ou aceite automatico da sugestao na triagem, se clara)
    classe_confirmada     TEXT,
    pavimento_confirmado  TEXT,
    status                TEXT NOT NULL DEFAULT 'pendente'
                          CHECK (status IN ('pendente','classificado','revisar','erro')),
    erro_msg              TEXT,
    created_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- dedup: mesmo arquivo (hash) nao duplica DENTRO da mesma obra; pode existir em
-- obras diferentes sem colisao.
CREATE UNIQUE INDEX IF NOT EXISTS idx_documentos_obra_hash
    ON portal_documentos(obra_id, arquivo_hash) WHERE arquivo_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_documentos_obra_status
    ON portal_documentos(obra_id, status, created_at);
