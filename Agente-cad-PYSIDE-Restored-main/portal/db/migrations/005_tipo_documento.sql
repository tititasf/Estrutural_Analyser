-- 005_tipo_documento.sql — tipo de documento (2026-07-07): eixo NOVO e
-- diferente de classe estrutural (PIL/LV/FV/LAJ/GF). Um documento é Bruto
-- (planta a recortar), Detalhe (desenho de detalhe/convenção) ou PDF/Outro
-- (material de referência, não entra no pipeline DXF). Mesmo padrão
-- sugerido/confirmado de classe_sugerida/classe_confirmada — a triagem
-- sempre pode corrigir a sugestão automática.
ALTER TABLE portal_documentos ADD COLUMN tipo_documento_sugerido TEXT;
ALTER TABLE portal_documentos ADD COLUMN tipo_documento_confirmado TEXT;
