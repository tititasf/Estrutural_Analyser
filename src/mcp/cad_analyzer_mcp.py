# -*- coding: utf-8 -*-
"""
cad_analyzer_mcp.py — Servidor MCP do CAD-ANALYZER

Expõe 8 loops de qualidade e evolução como ferramentas nativas
para agentes de IA (Claude, Gemini, AgentZero) via Model Context Protocol.

Uso:
    python -m src.mcp.cad_analyzer_mcp          # stdio (padrão para CLIs)
    python -m src.mcp.cad_analyzer_mcp --sse     # SSE (para conexões HTTP)
"""
from __future__ import annotations

import argparse
import hmac
import json
import logging
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import db_bridge

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [MCP] %(message)s")
logger = logging.getLogger("cad-analyzer-mcp")

# ── Inicialização do servidor ─────────────────────────────────────────────────
mcp = FastMCP(
    "CAD-Analyzer",
    instructions=(
        "Servidor MCP do CAD-ANALYZER. "
        "Expõe o banco project_data.vision e os 8 loops de qualidade "
        "(SA, N1-N5, Event Sourcing) como ferramentas para agentes de IA."
    ),
)

# Caminho padrão do DB — pode ser sobrescrito via env var
DB_PATH = Path(os.environ.get("CAD_ANALYZER_DB", "D:/Agente-cad-PYSIDE/project_data.vision"))
PROJECT_ROOT = Path("D:/Agente-cad-PYSIDE")
WRITE_TOKEN = os.environ.get("CAD_MCP_WRITE_TOKEN", "")


def _require_write_token(write_token: str) -> None:
    if not WRITE_TOKEN:
        raise PermissionError("escrita MCP desabilitada: configure CAD_MCP_WRITE_TOKEN")
    if not hmac.compare_digest(str(write_token or ""), WRITE_TOKEN):
        raise PermissionError("token MCP de escrita inválido")


# ═══════════════════════════════════════════════════════════════════════════════
# RECURSOS (Resources) — dados que a IA pode ler passivamente
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.resource("cad://obras")
def resource_obras() -> str:
    """Lista todas as obras cadastradas no banco."""
    obras = db_bridge.get_all_obras(DB_PATH)
    return json.dumps({"obras": obras, "total": len(obras)}, ensure_ascii=False, indent=2)


@mcp.resource("cad://logs/batch")
def resource_batch_log() -> str:
    """Retorna as últimas 200 linhas do log batch_full.log."""
    log_path = PROJECT_ROOT / "batch_full.log"
    if not log_path.exists():
        return json.dumps({"error": "batch_full.log não encontrado"})
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = lines[-200:] if len(lines) > 200 else lines
    return "\n".join(tail)


# ═══════════════════════════════════════════════════════════════════════════════
# FERRAMENTAS — LOOP 1: Refino SA (N1 vs N2 + Vision)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_obra_status(obra_id: str) -> str:
    """
    [Loop 1-4] Retorna o status completo de uma obra:
    projetos/pavimentos, contagem de pilares/vigas/lajes,
    attention notes e training events.
    """
    result = db_bridge.get_obra_status(obra_id, DB_PATH)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def get_n1_n2_divergencies(obra_id: str, classe: str = "ALL") -> str:
    """
    [Loop 1] Retorna as notas de atenção (divergências entre N1 e N2)
    para uma obra. Filtre por classe (PIL, FV, LV, LAJ) ou use ALL.
    O SA usa esses deltas para evoluir suas heurísticas de extração.
    """
    notes = db_bridge.get_attention_notes(obra_id, classe, DB_PATH)
    return json.dumps({
        "obra_id": obra_id,
        "classe_filtro": classe,
        "total_divergencias": len(notes),
        "divergencias": notes,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_training_events(obra_id: str) -> str:
    """
    [Loop 1 & 8] Retorna todos os eventos de treino registrados
    para uma obra (validações, rejeições, sinais de aprendizado).
    """
    events = db_bridge.get_training_events(obra_id, DB_PATH)
    return json.dumps({
        "obra_id": obra_id,
        "total_events": len(events),
        "events": events,
    }, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# FERRAMENTAS — LOOP 2: Validação do Robô (N4 vs N2 + Atenção Humana)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_n4_attention_feedback(obra_id: str, status: str = "PENDENTE") -> str:
    """
    [Loop 2] Retorna o feedback humano anotado sobre o N4
    (erros visuais, cotas ausentes, textos sobrepostos etc.).
    O Robot-Tweaker usa esses dados como roteiro de correção.
    Filtre por status: PENDENTE, EM_ANALISE_IA, RESOLVIDO.
    """
    feedback = db_bridge.get_n4_attention_feedback(obra_id, status, DB_PATH)
    return json.dumps({
        "obra_id": obra_id,
        "status_filtro": status,
        "total_feedback": len(feedback),
        "feedback": feedback,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def save_n4_feedback(
    obra_id: str,
    item_id: str,
    erro_visual_categoria: str,
    descricao_humana: str,
    coord_x: float = 0.0,
    coord_y: float = 0.0,
    write_token: str = "",
) -> str:
    """
    [Loop 2] Registra um feedback de atenção humana sobre o N4.
    Categorias sugeridas: Geometria_Bbox, Texto_Sobreposto,
    Cota_Ausente, Hachura_Incorreta, Layer_Errada.
    """
    _require_write_token(write_token)
    fid = db_bridge.save_n4_feedback(
        obra_id, item_id, erro_visual_categoria,
        descricao_humana, coord_x, coord_y, DB_PATH,
    )
    return json.dumps({
        "status": "ok",
        "feedback_id": fid,
        "message": f"Feedback '{erro_visual_categoria}' salvo para {item_id}",
    }, ensure_ascii=False)


@mcp.tool()
def resolve_n4_feedback(
    feedback_id: str,
    codigo_fonte_ajustado: str = "",
    write_token: str = "",
) -> str:
    """
    [Loop 2] Marca um feedback N4 como resolvido após ajuste no código.
    Opcionalmente registra qual arquivo/função foi alterado.
    """
    _require_write_token(write_token)
    db_bridge.resolve_n4_feedback(feedback_id, codigo_fonte_ajustado, DB_PATH)
    return json.dumps({
        "status": "ok",
        "feedback_id": feedback_id,
        "message": "Feedback marcado como RESOLVIDO",
    }, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════════
# FERRAMENTAS — LOOP 3: Autonomia Cega (N3 vs N4)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def run_n3_n4_comparison(obra_id: str, classe: str = "ALL") -> str:
    """
    [Loop 3] Dispara a comparação rigorosa entre N3 (gerado só com N1)
    e N4 (gerado com N2). Retorna score de equivalência por item.

    NOTA: Esta ferramenta acionará o script de comparação em background.
    O resultado ficará disponível via get_obra_status() após conclusão.
    """
    # TODO: Integrar com o script real de comparação visual/canônica
    # Por agora retorna placeholder indicando que a integração será feita
    return json.dumps({
        "obra_id": obra_id,
        "classe": classe,
        "status": "PENDENTE_INTEGRACAO",
        "message": (
            "Comparação N3 vs N4 será integrada ao motor de comparação visual "
            "existente em comparison_engine.py. Aguardando vinculação ao pipeline."
        ),
    }, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# FERRAMENTAS — LOOP 4: N5 vs Eng. Reversa Inteira
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def run_n5_holistic_validation(obra_id: str, classe: str = "ALL") -> str:
    """
    [Loop 4] Dispara a validação holística do N5 montado contra o
    recorte de engenharia reversa inteiro da obra de treino.

    NOTA: Será integrado ao n5_assembler.py e ao motor de comparação.
    """
    return json.dumps({
        "obra_id": obra_id,
        "classe": classe,
        "status": "PENDENTE_INTEGRACAO",
        "message": (
            "Validação N5 vs Eng. Reversa Inteira será integrada ao "
            "n5_assembler.py. Aguardando vinculação ao pipeline."
        ),
    }, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# FERRAMENTAS — LOOP 5: Self-Validation Obra Nova (Forward-Only)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def run_forward_validation(obra_id: str) -> str:
    """
    [Loop 5] Dispara validação heurística para obras sem gabarito N2.
    Usa RAG + métricas históricas de obras de treino para avaliar
    se a extração N1 e geração N3 são confiáveis.

    NOTA: Será integrado ao pipeline de obras novas.
    """
    # Verificar se a obra tem projetos cadastrados
    status = db_bridge.get_obra_status(obra_id, DB_PATH)
    return json.dumps({
        "obra_id": obra_id,
        "projetos_encontrados": len(status["projetos"]),
        "status": "PENDENTE_INTEGRACAO",
        "message": (
            "Forward validation (sem N2) será integrado ao pipeline "
            "heurístico com RAG e ChromaDB."
        ),
    }, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# FERRAMENTAS — LOOP 6: Topologia Espacial (Cross-Class)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def run_topology_validation(obra_id: str) -> str:
    """
    [Loop 6] Valida a coerência espacial entre classes diferentes.
    Verifica se vigas apoiam corretamente nos pilares, se lajes
    encostam nas bordas de vigas, etc.

    NOTA: Será integrado ao spatial_index.py e geometry_engine.py.
    """
    return json.dumps({
        "obra_id": obra_id,
        "status": "PENDENTE_INTEGRACAO",
        "message": (
            "Validação topológica cross-class será integrada ao "
            "spatial_index.py e geometry_engine.py existentes."
        ),
    }, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# FERRAMENTAS — LOOP 7: Sanitização (Raw DWG vs Clean DXF)
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_crop_learning_events(obra_id: str = "") -> str:
    """
    [Loop 7 & 8] Retorna eventos de aprendizado de recorte:
    bbox ajustado, confidence recalibrada, etc.
    """
    events = db_bridge.get_crop_learning_events(obra_id, DB_PATH)
    return json.dumps({
        "obra_id": obra_id or "TODAS",
        "total_events": len(events),
        "events": events,
    }, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# FERRAMENTAS — LOOP 8: Active Learning & Event Sourcing
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_human_overrides_log(obra_id: str = "", only_unprocessed: bool = True) -> str:
    """
    [Loop 8] Retorna o log de edições humanas feitas via UI.
    Cada registro contém o estado ANTES e DEPOIS da edição,
    os campos que mudaram e o contexto da UI onde a edição ocorreu.

    Use only_unprocessed=True para ver apenas lições que a IA
    ainda não absorveu via RAG.
    """
    logs = db_bridge.get_human_overrides_log(obra_id, only_unprocessed, DB_PATH)
    return json.dumps({
        "obra_id": obra_id or "TODAS",
        "only_unprocessed": only_unprocessed,
        "total_overrides": len(logs),
        "overrides": logs,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def query_active_learning_memory(
    query: str,
    include_candidates: bool = False,
    limit: int = 5,
) -> str:
    """
    Consulta memória MCP. Por padrão retorna somente APPROVED/INDEXED T1+.
    `include_candidates=True` é exclusivo para investigação: retorna PROPOSED/T0
    claramente rotulado e nunca deve ser usado como verdade de produção.
    """
    scripts_dir = PROJECT_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from active_learning_query import query_active_learning

    results = query_active_learning(
        query,
        limit=max(1, min(int(limit), 20)),
        include_candidates=bool(include_candidates),
    )
    return json.dumps(
        {
            "scope": "active_learning_candidates" if include_candidates else "active_learning_approved",
            "is_global_truth": False if include_candidates else True,
            "total": len(results),
            "results": results,
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def get_active_learning_patterns() -> str:
    """Retorna padrões T0 para investigação; nunca regras globais."""
    path = PROJECT_ROOT / "data" / "active_learning_patterns" / "patterns.json"
    if not path.exists():
        return json.dumps(
            {"scope": "active_learning_pattern_candidates", "patterns": []},
            ensure_ascii=False,
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["is_global_truth"] = False
    return json.dumps(payload, ensure_ascii=False, indent=2)


@mcp.tool()
def save_human_edit_event(
    obra_id: str,
    classe: str,
    item_id: str,
    fase_editada: str,
    ui_context: str,
    estado_anterior_json: str,
    estado_novo_json: str,
    motivo_humano: str = "",
    source_agent: str = "mcp_client",
    write_token: str = "",
) -> str:
    """
    [Loop 8] Registra uma edição humana na UI como evento de aprendizado.
    Deve ser chamado pelos botões Salvar do DiagnosticHub, SA, PreAnalise etc.

    Parâmetros:
        fase_editada: 'N1', 'N2', 'N4', 'Pre-Analise-SA', 'VisaoCorte', etc.
        ui_context: 'DiagnosticReverse', 'DiagnosticPreHub', 'ComparisonEngine', etc.
        estado_anterior_json: JSON do estado da ficha ANTES da edição
        estado_novo_json: JSON do estado da ficha DEPOIS da edição
    """
    _require_write_token(write_token)
    anterior = json.loads(estado_anterior_json)
    novo = json.loads(estado_novo_json)
    log_id = db_bridge.save_human_edit_event(
        obra_id=obra_id,
        classe=classe,
        item_id=item_id,
        fase_editada=fase_editada,
        ui_context=ui_context,
        estado_anterior=anterior,
        estado_novo=novo,
        nota_usuario=motivo_humano,
        source_agent=source_agent,
        db_path=DB_PATH,
    )
    return json.dumps({
        "status": "ok",
        "log_id": log_id,
        "campos_alterados": db_bridge._diff_keys(anterior, novo),
        "message": f"Edição humana registrada: {fase_editada}/{item_id} em {ui_context}",
    }, ensure_ascii=False)


@mcp.tool()
def mark_override_as_learned(
    log_id: str,
    rag_vector_id: str = "",
    write_token: str = "",
) -> str:
    """
    [Loop 8] Marca uma edição humana como já absorvida pela base RAG.
    Usado após o ChromaDB/FAISS ter vetorizado a lição.
    """
    _require_write_token(write_token)
    changed = db_bridge.mark_event_as_processed(log_id, rag_vector_id, DB_PATH)
    return json.dumps({
        "status": "ok" if changed else "not_changed",
        "log_id": log_id,
        "message": (
            "Proposta aprovada marcada como indexada"
            if changed else
            "Evento não aprovado; nenhuma alteração realizada"
        ),
    }, ensure_ascii=False)


@mcp.tool()
def approve_learning_proposal(
    log_id: str,
    approved_by: str,
    reason: str,
    write_token: str = "",
) -> str:
    """Gate humano explícito: promove uma proposta T0 para T1."""
    _require_write_token(write_token)
    approved = db_bridge.approve_event_candidate(
        log_id,
        approved_by=approved_by,
        reason=reason,
        validation_origin="human_ui",
        db_path=DB_PATH,
    )
    return json.dumps({"status": "approved" if approved else "not_changed", "log_id": log_id})


@mcp.tool()
def reject_learning_proposal(
    log_id: str,
    rejected_by: str,
    reason: str,
    write_token: str = "",
) -> str:
    """Rejeita/revoga a proposta e preserva o histórico como TX."""
    _require_write_token(write_token)
    rejected = db_bridge.reject_event_candidate(
        log_id,
        rejected_by=rejected_by,
        reason=reason,
        db_path=DB_PATH,
    )
    return json.dumps({"status": "rejected" if rejected else "not_changed", "log_id": log_id})


# ═══════════════════════════════════════════════════════════════════════════════
# FERRAMENTAS — PIPELINE E ORQUESTRAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def trigger_cad_pipeline(
    obra_id: str,
    start_fase: str = "1",
    end_fase: str = "8",
) -> str:
    """
    [Orquestrador] Dispara o pipeline CAD em background para uma obra.
    Retorna um job_id para tracking.

    NOTA: Será integrado ao cad_pipeline_cli.py existente.
    """
    # TODO: Integrar com o script real de pipeline
    # Placeholder mostrando que o esqueleto está pronto
    return json.dumps({
        "obra_id": obra_id,
        "fases": f"{start_fase}-{end_fase}",
        "status": "PENDENTE_INTEGRACAO",
        "message": (
            "Pipeline trigger será integrado ao cad_pipeline_cli.py. "
            "O job rodará em subprocess isolado."
        ),
    }, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="CAD-Analyzer MCP Server")
    parser.add_argument(
        "--sse", action="store_true",
        help="Usar transporte SSE em vez de stdio",
    )
    parser.add_argument(
        "--port", type=int, default=21345,
        help="Porta para SSE (faixa permitida: 21300-21399)",
    )
    args = parser.parse_args()
    if args.sse and not 21300 <= args.port <= 21399:
        parser.error("--port deve estar entre 21300 e 21399")

    # Garantir que as tabelas de Event Sourcing existam
    logger.info("Garantindo tabelas de Event Sourcing...")
    db_bridge.ensure_event_sourcing_tables(DB_PATH)
    logger.info(f"Banco: {DB_PATH}")

    if args.sse:
        mcp.settings.host = "127.0.0.1"
        mcp.settings.port = args.port
        logger.info(f"Iniciando MCP Server via SSE na porta {args.port}...")
        mcp.run(transport="sse")
    else:
        logger.info("Iniciando MCP Server via stdio...")
        mcp.run()


if __name__ == "__main__":
    main()
