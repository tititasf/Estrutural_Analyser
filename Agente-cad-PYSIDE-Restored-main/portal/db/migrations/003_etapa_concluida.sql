-- 003_etapa_concluida.sql — rastreio preciso de qual etapa do pipeline já
-- rodou (2026-07-06). Achado real testando o modo rápido: `atualizar_estado_obra`
-- marcava a obra como "pronta" (etapa 4, Validação) após QUALQUER job bem
-- sucedido — inclusive triagem sozinha — porque triagem/recortes usavam o MESMO
-- código de sucesso que sa. Isso fazia a UI mostrar "Recortes (concluída)" e
-- "SA (concluída)" sem nenhum dos dois ter rodado. Sem coluna própria, não há
-- como distinguir "só a triagem rodou" de "o SA completo rodou" só olhando o
-- enum `estado` (que nem tem valores para os estados intermediários).
ALTER TABLE portal_obras ADD COLUMN etapa_concluida TEXT;
