-- Migration 005: Cache e Otimizações de Performance
-- SPRINT 13: Reduzir tempo do pipeline de 20min para < 5min
-- Data: 2026-03-06

-- ============================================================================
-- TABELAS DE CACHE
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TABELA: cache_dxf
-- Descrição: Cache de arquivos DXF processados para evitar reprocessamento
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cache_dxf (
    id TEXT PRIMARY KEY,
    arquivo_path TEXT UNIQUE NOT NULL,
    arquivo_hash TEXT NOT NULL,
    arquivo_size INTEGER,
    arquivo_mtime REAL,
    entidades_json TEXT,
    layers_json TEXT,
    blocks_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hit_count INTEGER DEFAULT 0,
    last_hit_at TIMESTAMP
);

-- Índices para cache_dxf
CREATE INDEX IF NOT EXISTS idx_cache_dxf_hash ON cache_dxf(arquivo_hash);
CREATE INDEX IF NOT EXISTS idx_cache_dxf_path ON cache_dxf(arquivo_path);
CREATE INDEX IF NOT EXISTS idx_cache_dxf_mtime ON cache_dxf(arquivo_mtime);

-- ----------------------------------------------------------------------------
-- TABELA: cache_transformacao
-- Descrição: Cache de regras de transformação aplicadas
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cache_transformacao (
    id TEXT PRIMARY KEY,
    regra_hash TEXT NOT NULL,
    entrada_hash TEXT NOT NULL,
    resultado_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    hit_count INTEGER DEFAULT 0
);

-- Índices para cache_transformacao
CREATE INDEX IF NOT EXISTS idx_cache_trans_regra ON cache_transformacao(regra_hash);
CREATE INDEX IF NOT EXISTS idx_cache_trans_entrada ON cache_transformacao(entrada_hash);

-- ----------------------------------------------------------------------------
-- TABELA: cache_fichas
-- Descrição: Cache de fichas geradas (pilares, vigas, lajes)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cache_fichas (
    id TEXT PRIMARY KEY,
    obra_id TEXT NOT NULL,
    pavimento TEXT,
    tipo TEXT NOT NULL,
    codigo TEXT NOT NULL,
    entidade_hash TEXT NOT NULL,
    ficha_json TEXT,
    confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (obra_id) REFERENCES obras(id)
);

-- Índices para cache_fichas
CREATE INDEX IF NOT EXISTS idx_cache_fichas_obra ON cache_fichas(obra_id);
CREATE INDEX IF NOT EXISTS idx_cache_fichas_pavimento ON cache_fichas(pavimento);
CREATE INDEX IF NOT EXISTS idx_cache_fichas_tipo ON cache_fichas(tipo);
CREATE INDEX IF NOT EXISTS idx_cache_fichas_codigo ON cache_fichas(codigo);

-- ============================================================================
-- TABELA DE CHECKPOINT DO PIPELINE
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TABELA: pipeline_checkpoint
-- Descrição: Checkpoints detalhados por fase para permitir resume
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pipeline_checkpoint (
    id TEXT PRIMARY KEY,
    obra_id TEXT NOT NULL,
    fase INTEGER NOT NULL,
    estado_json TEXT NOT NULL,
    progresso REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (obra_id) REFERENCES obras(id)
);

CREATE INDEX IF NOT EXISTS idx_pipeline_checkpoint_obra ON pipeline_checkpoint(obra_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_checkpoint_fase ON pipeline_checkpoint(fase);

-- ============================================================================
-- ÍNDICES DE PERFORMANCE ADICIONAIS
-- ============================================================================

-- Índices compostos para dxf_entidades (queries frequentes)
CREATE INDEX IF NOT EXISTS idx_entidades_obra_tipo ON dxf_entidades(obra_id, tipo);
CREATE INDEX IF NOT EXISTS idx_entidades_obra_layer ON dxf_entidades(obra_id, layer);
CREATE INDEX IF NOT EXISTS idx_entidades_completo ON dxf_entidades(obra_id, tipo, layer);

-- Índices para fase3_fichas (queries de interpretação)
CREATE INDEX IF NOT EXISTS idx_fichas_obra_tipo ON fase3_fichas(obra_id, tipo);
CREATE INDEX IF NOT EXISTS idx_fichas_obra_pavimento ON fase3_fichas(obra_id, pavimento);
CREATE INDEX IF NOT EXISTS idx_fichas_completo ON fase3_fichas(obra_id, tipo, pavimento);

-- Índices para pipeline_state
CREATE INDEX IF NOT EXISTS idx_pipeline_state_fase ON pipeline_state(fase_atual);
CREATE INDEX IF NOT EXISTS idx_pipeline_state_status ON pipeline_state(fase_em_andamento);

-- ============================================================================
-- TABELA DE METRICAS DE PERFORMANCE
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TABELA: performance_metrics
-- Descrição: Registro de métricas de performance por execução de fase
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS performance_metrics (
    id TEXT PRIMARY KEY,
    obra_id TEXT NOT NULL,
    fase INTEGER NOT NULL,
    tempo_inicio TIMESTAMP,
    tempo_fim TIMESTAMP,
    tempo_total_seg REAL,
    arquivos_processados INTEGER DEFAULT 0,
    entidades_processadas INTEGER DEFAULT 0,
    cache_hits INTEGER DEFAULT 0,
    cache_misses INTEGER DEFAULT 0,
    memoria_peak_mb REAL,
    workers_usados INTEGER,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (obra_id) REFERENCES obras(id)
);

CREATE INDEX IF NOT EXISTS idx_performance_metrics_obra ON performance_metrics(obra_id);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_fase ON performance_metrics(fase);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_tempo ON performance_metrics(tempo_inicio);

-- ============================================================================
-- VIEW: Estatísticas de Cache
-- ============================================================================

CREATE VIEW IF NOT EXISTS v_cache_stats AS
SELECT 
    'dxf' as tipo_cache,
    COUNT(*) as total_entries,
    SUM(hit_count) as total_hits,
    SUM(arquivo_size) as total_size_bytes,
    AVG(hit_count) as avg_hits_per_entry
FROM cache_dxf
UNION ALL
SELECT 
    'transformacao' as tipo_cache,
    COUNT(*) as total_entries,
    SUM(hit_count) as total_hits,
    0 as total_size_bytes,
    AVG(hit_count) as avg_hits_per_entry
FROM cache_transformacao
UNION ALL
SELECT 
    'fichas' as tipo_cache,
    COUNT(*) as total_entries,
    0 as total_hits,
    0 as total_size_bytes,
    0 as avg_hits_per_entry
FROM cache_fichas;

-- ============================================================================
-- VIEW: Performance do Pipeline por Obra
-- ============================================================================

CREATE VIEW IF NOT EXISTS v_pipeline_performance AS
SELECT 
    o.id as obra_id,
    o.nome as obra_nome,
    o.fase_atual,
    o.status,
    COUNT(DISTINCT pm.id) as execucoes_count,
    SUM(pm.tempo_total_seg) as tempo_total_seg,
    AVG(pm.tempo_total_seg) as tempo_medio_seg,
    SUM(pm.cache_hits) as total_cache_hits,
    SUM(pm.cache_misses) as total_cache_misses
FROM obras o
LEFT JOIN performance_metrics pm ON o.id = pm.obra_id
GROUP BY o.id, o.nome, o.fase_atual, o.status;

-- ============================================================================
-- TRIGGER: Atualizar updated_at automaticamente
-- ============================================================================

-- Trigger para cache_dxf
CREATE TRIGGER IF NOT EXISTS trg_cache_dxf_updated_at 
AFTER UPDATE ON cache_dxf
BEGIN
    UPDATE cache_dxf SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Trigger para cache_fichas
CREATE TRIGGER IF NOT EXISTS trg_cache_fichas_updated_at 
AFTER UPDATE ON cache_fichas
BEGIN
    UPDATE cache_fichas SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Trigger para pipeline_checkpoint
CREATE TRIGGER IF NOT EXISTS trg_pipeline_checkpoint_updated_at 
AFTER UPDATE ON pipeline_checkpoint
BEGIN
    UPDATE pipeline_checkpoint SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- ============================================================================
-- DADOS INICIAIS
-- ============================================================================

-- Inserir configuração padrão de workers
INSERT OR IGNORE INTO ingestao_metadata (obra_id, dxf_count, pdf_count, fotos_count, entidades_count, tempo_total)
VALUES ('_config', 0, 0, 0, 0, 0);

-- ============================================================================
-- COMENTÁRIOS DAS TABELAS (via tabela auxiliar)
-- ============================================================================

-- Nota: SQLite não suporta comentários nativamente em tabelas.
-- Esta tabela serve como documentação do schema.
CREATE TABLE IF NOT EXISTS _schema_documentation (
    tabela TEXT PRIMARY KEY,
    descricao TEXT,
    colunas_principais TEXT,
    observacoes TEXT
);

INSERT OR REPLACE INTO _schema_documentation (tabela, descricao, colunas_principais, observacoes)
VALUES 
    ('cache_dxf', 'Cache de arquivos DXF processados', 'arquivo_path, arquivo_hash, entidades_json', 'Usa hash SHA-256 para detectar mudanças'),
    ('cache_transformacao', 'Cache de regras de transformação', 'regra_hash, entrada_hash, resultado_json', 'Suporta TTL para expiração'),
    ('cache_fichas', 'Cache de fichas de elementos estruturais', 'obra_id, tipo, codigo, ficha_json', 'Evita regeneração de fichas'),
    ('pipeline_checkpoint', 'Checkpoints de execução do pipeline', 'obra_id, fase, estado_json', 'Permite resume de qualquer fase'),
    ('performance_metrics', 'Métricas de performance por execução', 'fase, tempo_total_seg, cache_hits', 'Usado para benchmarking');
