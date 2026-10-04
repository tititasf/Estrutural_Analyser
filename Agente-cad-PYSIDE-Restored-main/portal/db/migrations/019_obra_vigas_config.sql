-- Preferências da ficha da obra. Não inferir escolhas para obras existentes.
ALTER TABLE portal_obras ADD COLUMN comportamento_laterais_vigas TEXT
    CHECK (comportamento_laterais_vigas IN ('', 'gradeadas', 'sarrafeadas'));
ALTER TABLE portal_obras ADD COLUMN fundos_vigas_possui_garfos TEXT
    CHECK (fundos_vigas_possui_garfos IN ('', 'sim', 'nao'));
