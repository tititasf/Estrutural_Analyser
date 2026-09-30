-- Pacotes internos e versionados de pré-processamento. O índice guarda somente
-- metadados e um caminho relativo; os resultados vivem no diretório da obra.
CREATE TABLE IF NOT EXISTS portal_preprocess_runs (
    run_id                 TEXT PRIMARY KEY,
    obra_id                TEXT NOT NULL REFERENCES portal_obras(id) ON DELETE CASCADE,
    pavimento_id           TEXT NOT NULL,
    recorte_id             TEXT NOT NULL,
    job_id                 TEXT REFERENCES portal_jobs(id) ON DELETE SET NULL,
    input_manifest_hash    TEXT NOT NULL,
    source_revision        TEXT NOT NULL,
    schema_version         INTEGER NOT NULL,
    engine_version         TEXT,
    status                 TEXT NOT NULL
                           CHECK (status IN ('complete','partial','failed','stale')),
    manifest_relative_path TEXT NOT NULL,
    started_at             TEXT,
    finished_at            TEXT,
    created_at             TEXT NOT NULL,
    indexed_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_preprocess_runs_scope
    ON portal_preprocess_runs(obra_id, pavimento_id, recorte_id, created_at DESC);
