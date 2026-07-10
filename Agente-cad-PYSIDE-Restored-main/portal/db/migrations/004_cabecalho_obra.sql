-- 004_cabecalho_obra.sql — cabeçalho de referência da obra/processamento
-- (2026-07-07). Achado com o dono: a obra fica só com o nome do arquivo
-- bruto como "nome" (tanto no modo rápido quanto no fluxo completo) — sem
-- espaço pra dizer QUEM pediu, prazo, critérios do cliente etc. Também falta
-- um nome de exibição por documento (diferente do arquivo_nome cru) pra
-- poder renomear na Triagem sem mexer no arquivo físico.
ALTER TABLE portal_obras ADD COLUMN cliente TEXT;
ALTER TABLE portal_obras ADD COLUMN data_solicitacao TEXT;
ALTER TABLE portal_obras ADD COLUMN data_entrega TEXT;
ALTER TABLE portal_obras ADD COLUMN criterios_cliente TEXT;
ALTER TABLE portal_obras ADD COLUMN observacoes TEXT;

ALTER TABLE portal_documentos ADD COLUMN nome_exibicao TEXT;
