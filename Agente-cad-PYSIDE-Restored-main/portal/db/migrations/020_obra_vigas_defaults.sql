-- Padrões obrigatórios definidos pelo dono: laterais sarrafeadas, sem garfos.
-- Mantém escolhas já informadas e cobre também ingestões sem ficha preenchida.
UPDATE portal_obras
SET comportamento_laterais_vigas = COALESCE(NULLIF(comportamento_laterais_vigas, ''), 'sarrafeadas'),
    fundos_vigas_possui_garfos = COALESCE(NULLIF(fundos_vigas_possui_garfos, ''), 'nao')
WHERE comportamento_laterais_vigas IS NULL OR comportamento_laterais_vigas = ''
   OR fundos_vigas_possui_garfos IS NULL OR fundos_vigas_possui_garfos = '';

CREATE TRIGGER IF NOT EXISTS portal_obras_vigas_default_insert
AFTER INSERT ON portal_obras
WHEN NEW.comportamento_laterais_vigas IS NULL OR NEW.comportamento_laterais_vigas = ''
  OR NEW.fundos_vigas_possui_garfos IS NULL OR NEW.fundos_vigas_possui_garfos = ''
BEGIN
    UPDATE portal_obras
    SET comportamento_laterais_vigas = COALESCE(NULLIF(NEW.comportamento_laterais_vigas, ''), 'sarrafeadas'),
        fundos_vigas_possui_garfos = COALESCE(NULLIF(NEW.fundos_vigas_possui_garfos, ''), 'nao')
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS portal_obras_vigas_default_update
AFTER UPDATE OF comportamento_laterais_vigas, fundos_vigas_possui_garfos ON portal_obras
WHEN NEW.comportamento_laterais_vigas IS NULL OR NEW.comportamento_laterais_vigas = ''
  OR NEW.fundos_vigas_possui_garfos IS NULL OR NEW.fundos_vigas_possui_garfos = ''
BEGIN
    UPDATE portal_obras
    SET comportamento_laterais_vigas = COALESCE(NULLIF(NEW.comportamento_laterais_vigas, ''), 'sarrafeadas'),
        fundos_vigas_possui_garfos = COALESCE(NULLIF(NEW.fundos_vigas_possui_garfos, ''), 'nao')
    WHERE id = NEW.id;
END;
