-- Migration 003: Pipeline State Management
-- GAP-7: Implementar Pipeline Orchestrator com estado persistente por obra
-- Data: 2026-03-05

-- ============================================================================
-- TABELA: obras
-- Descrição: Cadastro de obras/projetos com metadados e status do pipeline
-- ============================================================================

CREATE TABLE IF NOT EXISTS obras (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    pasta_origem TEXT NOT NULL,
    data_ingestao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fase_atual INTEGER DEFAULT 1,
    status TEXT DEFAULT 'iniciado',
    CHECK (status IN ('iniciado', 'em_processamento', 'pausado', 'completo', 'erro'))
);

-- ============================================================================
-- TABELA: pipeline_state
-- Descrição: Estado persistente do pipeline por obra (permite retomar processamento)
-- ============================================================================

CREATE TABLE IF NOT EXISTS pipeline_state (
    obra_id TEXT PRIMARY KEY,
    fase_atual INTEGER DEFAULT 1,
    fases_completas TEXT DEFAULT '[]',  -- JSON array de fases completas
    fase_em_andamento TEXT,             -- JSON com detalhes da fase atual
    ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (obra_id) REFERENCES obras(id)
);

-- ============================================================================
-- TABELA: fase3_fichas
-- Descrição: Fichas da Fase 3 (Interpretação) - pilares, vigas, lajes
-- ============================================================================

CREATE TABLE IF NOT EXISTS fase3_fichas (
    id TEXT PRIMARY KEY,
    obra_id TEXT,
    pavimento TEXT,
    tipo TEXT,  -- pilar|viga|laje
    codigo TEXT,
    dados_json TEXT,
    confidence REAL,
    revisado BOOLEAN DEFAULT FALSE,
    revisado_por TEXT,
    data_revisao TIMESTAMP,
    FOREIGN KEY (obra_id) REFERENCES obras(id)
);

-- ============================================================================
-- ÍNDICES PARA PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_fichas_obra ON fase3_fichas(obra_id);
CREATE INDEX IF NOT EXISTS idx_fichas_tipo ON fase3_fichas(tipo);
CREATE INDEX IF NOT EXISTS idx_fichas_pavimento ON fase3_fichas(pavimento);
CREATE INDEX IF NOT EXISTS idx_obras_status ON obras(status);
CREATE INDEX IF NOT EXISTS idx_obras_nome ON obras(nome);
