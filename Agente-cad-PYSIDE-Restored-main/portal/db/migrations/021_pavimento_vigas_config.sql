-- Escolhas de desenho pertencem ao pavimento; os campos antigos ficam preservados.
CREATE TABLE portal_pavimento_vigas_config (
    obra_id TEXT NOT NULL REFERENCES portal_obras(id) ON DELETE CASCADE,
    pavimento TEXT NOT NULL CHECK (length(trim(pavimento)) > 0),
    comportamento_laterais_vigas TEXT NOT NULL DEFAULT 'sarrafeadas'
        CHECK (comportamento_laterais_vigas IN ('gradeadas','sarrafeadas')),
    fundos_vigas_possui_garfos TEXT NOT NULL DEFAULT 'nao'
        CHECK (fundos_vigas_possui_garfos IN ('sim','nao')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (obra_id,pavimento)
);
