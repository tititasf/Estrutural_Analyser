-- public_consulta.db — schema da App de Consulta Pública (STORY-01).
--
-- Projeção MÍNIMA e denormalizada de obras publicadas deliberadamente pelo
-- dono/curador. A API pública (consulta-publica-api) abre este arquivo em
-- mode=ro e NUNCA toca portal_data.db nem project_data.vision.
--
-- Colunas propositalmente ausentes (blacklist — nunca adicionar):
--   cliente, criterios_cliente, data_solicitacao, data_entrega, observacoes,
--   membro_id, login, nome, email, senha_hash, descricao, local_path
-- (local_path do PORTAL é substituído por `obra_dir` pré-resolvido pelo
-- Publisher, nunca construído a partir de input do usuário na API pública.)

CREATE TABLE IF NOT EXISTS public_codes (
    code            TEXT PRIMARY KEY,
    -- [2026-07-12] 'pavimento' adicionado — código próprio por pavimento
    -- (a "ficha do pavimento"/recorte limpo da torre), resolvendo direto
    -- pra lista de itens DAQUELE pavimento (não do obra inteiro).
    kind            TEXT NOT NULL CHECK (kind IN ('obra', 'pavimento', 'item')),
    obra_id         TEXT NOT NULL,
    obra_dir        TEXT NOT NULL,
    pavimento       TEXT,
    classe          TEXT,
    item_id         TEXT,
    tipo_elemento   TEXT,
    titulo_publico  TEXT,
    obra_rotulo     TEXT,
    revoked         INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    publish_batch   TEXT
);

CREATE INDEX IF NOT EXISTS idx_public_codes_batch ON public_codes(publish_batch);
CREATE INDEX IF NOT EXISTS idx_public_codes_obra ON public_codes(obra_id);

-- Lookup rápido por (obra_id, pavimento, classe, item_id) para o upsert do
-- Publisher preservar o `code` de itens já publicados (AC 3).
CREATE UNIQUE INDEX IF NOT EXISTS idx_public_codes_item_identity
    ON public_codes(obra_id, pavimento, classe, item_id)
    WHERE kind = 'item';

-- Mesma disciplina de upsert, agora para 1 código por (obra_id, pavimento).
CREATE UNIQUE INDEX IF NOT EXISTS idx_public_codes_pavimento_identity
    ON public_codes(obra_id, pavimento)
    WHERE kind = 'pavimento';
