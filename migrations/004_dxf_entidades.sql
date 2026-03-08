-- Migration 004: Tabela dxf_entidades
-- GAP-7: Criar tabela dxf_entidades para Fases 1-2 funcionarem em testes
-- Data: 2026-03-05

-- ============================================================================
-- TABELA: dxf_entidades
-- Descrição: Entidades extraídas de arquivos DXF (usada pela Fase 2)
-- ============================================================================

CREATE TABLE IF NOT EXISTS dxf_entidades (
    id TEXT PRIMARY KEY,
    obra_id TEXT,
    arquivo_origem TEXT,
    tipo TEXT,
    layer TEXT,
    dados_json TEXT,
    posicao_x REAL,
    posicao_y REAL,
    FOREIGN KEY (obra_id) REFERENCES obras(id)
);

CREATE INDEX IF NOT EXISTS idx_entidades_obra ON dxf_entidades(obra_id);
