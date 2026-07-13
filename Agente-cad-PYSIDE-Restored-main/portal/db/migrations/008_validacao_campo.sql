-- 008_validacao_campo.sql — validação de CAMPO individual pelo Portal
-- (2026-07-13, harmonização de validação — selo rosa). Granularidade real de
-- campo, diferente de `portal_validacoes` (por classe inteira) e
-- `portal_sa_validacao` (por pavimento/bruto inteiro). Gera a origem
-- `humano_portal` no app desktop via sync PULL — ver
-- docs/CONVENCAO-SELOS-VALIDACAO.md.
CREATE TABLE IF NOT EXISTS portal_validacoes_campo (
    obra_id      TEXT NOT NULL REFERENCES portal_obras(id),
    pavimento    TEXT NOT NULL,
    classe       TEXT NOT NULL,
    item_id      TEXT NOT NULL,
    field_id     TEXT NOT NULL,
    validado_por TEXT,
    validado_em  TEXT,
    PRIMARY KEY (obra_id, pavimento, classe, item_id, field_id)
);
