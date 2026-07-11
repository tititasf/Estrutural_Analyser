-- 006_sa_validacao.sql — validação "item completo" do Structural Analyzer
-- por pavimento (2026-07-10, Masterplan OBRAS DRIVE Fase 2). Eixo coarse,
-- simétrico ao de recortes (torre_crop.set_recorte_validado) mas guardado no
-- SQLite (não em arquivo) porque não há pasta de crop por pavimento aqui —
-- é o mesmo bruto_id da API de recortes. NÃO guarda campos/fichas — isso
-- fica só na app desktop (project_data.vision), que tem o sistema rico.
CREATE TABLE IF NOT EXISTS portal_sa_validacao (
    obra_id     TEXT NOT NULL REFERENCES portal_obras(id),
    bruto_id    TEXT NOT NULL,
    validado    INTEGER NOT NULL DEFAULT 0,
    validado_por TEXT,
    validado_em TEXT,
    PRIMARY KEY (obra_id, bruto_id)
);
