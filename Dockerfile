# =============================================================================
# CAD-ANALYZER - Dockerfile Multi-Stage Build
# Python 3.14 | Tamanho Otimizado < 500MB
# =============================================================================

# -----------------------------------------------------------------------------
# STAGE 1: Builder - Instala dependências e compila assets
# -----------------------------------------------------------------------------
FROM python:3.14-slim AS builder

# Definir variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    DEBIAN_FRONTEND=noninteractive

# Instalar dependências de sistema necessárias para compilação
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libtesseract-dev \
    tesseract-ocr \
    tesseract-ocr-por \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Criar diretório de trabalho
WORKDIR /build

# Copiar requirements primeiro para cache de layers
COPY requirements-phases.txt .

# Instalar dependências Python em diretório específico
RUN pip install --prefix=/install -r requirements-phases.txt

# Copiar código fonte
COPY src/ ./src/
COPY tests/ ./tests/

# -----------------------------------------------------------------------------
# STAGE 2: Runtime - Imagem final mínima
# -----------------------------------------------------------------------------
FROM python:3.14-slim AS runtime

# Definir variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/app" \
    CAD_ANALYZER_VERSION="3.0.0" \
    CAD_ANALYZER_ENV="production"

# Criar usuário não-root para segurança
RUN groupadd --gid 1000 cad-analyzer && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home cad-analyzer

# Instalar apenas runtime dependencies (sem build-essential)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libtesseract5 \
    tesseract-ocr \
    tesseract-ocr-por \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && rm -rf /tmp/* /var/tmp/*

# Copiar dependências instaladas do builder
COPY --from=builder --chown=cad-analyzer:cad-analyzer /install /install

# Criar diretório de aplicação
WORKDIR /app

# Copiar código fonte do builder
COPY --from=builder --chown=cad-analyzer:cad-analyzer /build/src ./src
COPY --from=builder --chown=cad-analyzer:cad-analyzer /build/tests ./tests

# Criar diretórios para dados persistentes
RUN mkdir -p /app/data/obras /app/data/cache /app/logs /app/output && \
    chown -R cad-analyzer:cad-analyzer /app

# Mudar para usuário não-root
USER cad-analyzer

# Health check - verifica se o orchestrator está funcional
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from src.orchestrator.pipeline_orchestrator import PipelineOrchestrator; print('OK')" || exit 1

# Expor porta para métricas (opcional, para monitoramento)
EXPOSE 8080

# Definir volumes para dados persistentes
VOLUME ["/app/data/obras", "/app/data/cache", "/app/logs", "/app/output"]

# ENTRYPOINT para CLI
ENTRYPOINT ["python", "-m", "src.orchestrator.pipeline_orchestrator"]

# CMD padrão (pode ser sobrescrito)
CMD ["--help"]

# =============================================================================
# INSTRUÇÕES DE USO:
# =============================================================================
# Build: docker build -t cad-analyzer:3.0.0 .
# Run:   docker run -v ./data:/app/data -v ./logs:/app/logs cad-analyzer:3.0.0
# CLI:   docker run cad-analyzer:3.0.0 --obra OBRA_001 --fase 1
# =============================================================================
