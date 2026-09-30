-- D-74/D-78: configuração da obra, separada dos documentos e do SA.
ALTER TABLE portal_obras ADD COLUMN comportamento TEXT NOT NULL DEFAULT 'misto'
    CHECK (comportamento IN ('para', 'passa', 'misto'));

CREATE TABLE IF NOT EXISTS portal_obra_pavimentos (
    obra_id TEXT NOT NULL REFERENCES portal_obras(id) ON DELETE CASCADE,
    pavimento TEXT NOT NULL,
    ordem INTEGER NOT NULL CHECK (ordem >= 0),
    repete_de INTEGER,
    repete_ate INTEGER,
    PRIMARY KEY (obra_id, pavimento),
    UNIQUE (obra_id, ordem),
    CHECK ((repete_de IS NULL AND repete_ate IS NULL) OR
           (repete_de IS NOT NULL AND repete_ate IS NOT NULL AND repete_de >= 1 AND repete_de <= repete_ate))
);
