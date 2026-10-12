-- Modo visual do N3 é uma escolha explícita por obra, pavimento e classe.
CREATE TABLE portal_pavimento_modo_desenho (
    obra_id TEXT NOT NULL REFERENCES portal_obras(id) ON DELETE CASCADE,
    pavimento TEXT NOT NULL CHECK (length(trim(pavimento)) > 0),
    classe_ui TEXT NOT NULL CHECK (classe_ui IN ('ALL','pilares','lajes','fundo','laterais_para','laterais_passa')),
    visual_mode TEXT NOT NULL DEFAULT 'NOVA'
        CHECK (visual_mode IN ('INI','NOVA','MOLDE_1','MOLDE_2','MOLDE_3')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (obra_id, pavimento, classe_ui)
);
