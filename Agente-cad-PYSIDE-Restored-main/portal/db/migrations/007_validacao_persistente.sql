-- 007_validacao_persistente.sql — persiste a "etapa 5" (validação N1+N3 por
-- classe, que gateia a liberação do N5) que hoje só vive em
-- `request.app.state.validacoes` (memória do processo, perdida a cada
-- restart — ver comentário original em jobs_routes.py). Masterplan OBRAS
-- DRIVE Fase 3: pré-requisito pra sincronizar N3/N5 com a app desktop —
-- não dá pra sincronizar um estado que nem sobrevive a um restart.
CREATE TABLE IF NOT EXISTS portal_validacoes (
    obra_id      TEXT NOT NULL REFERENCES portal_obras(id),
    classe       TEXT NOT NULL CHECK (classe IN ('PL','LV','FV','LJ')),
    n1_ok        INTEGER NOT NULL DEFAULT 0,
    n3_ok        INTEGER NOT NULL DEFAULT 0,
    item_id      TEXT,
    validado_por TEXT,
    validado_em  TEXT,
    PRIMARY KEY (obra_id, classe)
);
