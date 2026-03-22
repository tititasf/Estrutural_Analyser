#!/usr/bin/env python3
"""
mcp_rag_cad.py — MCP Server para RAG CAD-ANALYZER
Expõe busca semântica FAISS ao Claude Code via MCP stdio transport.

Configuração em ~/.claude.json:
  "mcpServers": {
    "rag-cad": {
      "command": "python",
      "args": ["D:/Agente-cad-PYSIDE/scripts/mcp_rag_cad.py"]
    }
  }
"""
import sys, os, json
from pathlib import Path

# Garante encoding UTF-8 no stdout/stderr
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Adiciona o diretório de scripts ao path para importar rag_commons
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, CallToolResult

# Importação EAGER do RAG (pré-carrega modelo no startup para evitar timeout)
_rag_loaded = False
_rag_query = None
_rag_stats = None

try:
    import rag_commons
    # Força carregamento do modelo no startup
    _ = rag_commons.load_registry()
    _rag_query = rag_commons.query
    _rag_stats = rag_commons.load_registry
    _rag_loaded = True
    # Pré-aquecer o modelo com uma query dummy
    try:
        _ = rag_commons.query(text="warmup", k=1, threshold=0.99)
    except Exception:
        pass
    sys.stderr.write("[rag-cad] Model loaded + warmed up OK\n")
    sys.stderr.flush()
except Exception as e:
    sys.stderr.write(f"[rag-cad] WARN: model load failed: {e}\n")
    sys.stderr.flush()


def _ensure_rag():
    """Verifica se RAG está carregado."""
    global _rag_loaded
    if _rag_loaded:
        return True
    return False, "RAG não carregou no startup"


def do_rag_search(query_text: str, tipo: str | None, obra: str | None,
                  k: int, threshold: float) -> list[dict]:
    """Wrapper para rag_commons.query() com resultado serializado."""
    import rag_commons
    results = rag_commons.query(
        text=query_text,
        tipo=tipo,
        obra=obra,
        k=k,
        threshold=threshold,
    )
    # Serializar para retorno MCP
    out = []
    for r in results:
        m = r['meta']
        dados = m.get('dados', {})
        chunk = {
            'score': round(r['score'], 4),
            'tipo': m.get('tipo', '?'),
            'id': m.get('id', '?'),
            'obra': m.get('obra', '?'),
            'pavimento': m.get('pavimento', '?'),
            'text': m.get('text', ''),
            'dados': dados,
        }
        out.append(chunk)
    return out


def do_rag_stats() -> dict:
    """Retorna estatísticas do índice FAISS."""
    import rag_commons
    reg = rag_commons.load_registry()
    total = reg.get('total', {})
    obras = [r['obra'] for r in reg.get('ingestoes', [])]
    return {
        'total_vetores': total.get('geral', 0),
        'pilares': total.get('pilares', 0),
        'vigas': total.get('vigas', 0),
        'lajes': total.get('lajes', 0),
        'obras_indexadas': obras,
        'ultima_atualizacao': reg.get('ultima_atualizacao', '?'),
    }


# ── MCP SERVER ───────────────────────────────────────────────────────────────

app = Server("rag-cad")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="rag_search",
            description=(
                "Busca semântica no corpus CAD-ANALYZER (pilares, vigas, lajes). "
                "Retorna elementos estruturais similares à query por similaridade cosine (FAISS). "
                "Use para validar plausibilidade, encontrar precedentes e injetar contexto de obra."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Texto de consulta. Ex: 'viga de balanco 15x45' ou 'pilar chanfrado pillar_left'"
                    },
                    "tipo": {
                        "type": "string",
                        "enum": ["pilar", "viga", "laje"],
                        "description": "Filtrar por tipo de elemento (opcional)"
                    },
                    "obra": {
                        "type": "string",
                        "description": "Filtrar por obra específica. Ex: 'Obra_TREINO_1' (opcional)"
                    },
                    "k": {
                        "type": "integer",
                        "default": 5,
                        "description": "Número de resultados (1-20, default=5)"
                    },
                    "threshold": {
                        "type": "number",
                        "default": 0.20,
                        "description": "Score mínimo de similaridade 0.0-1.0 (default=0.20)"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="rag_stats",
            description=(
                "Retorna estatísticas do índice RAG CAD-ANALYZER: total de vetores, "
                "contagem por tipo (pilares/vigas/lajes), obras indexadas e última atualização."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    ok = _ensure_rag()
    if ok is not True:
        err = ok[1] if isinstance(ok, tuple) else "rag_commons não disponível"
        return [TextContent(type="text", text=json.dumps({
            "error": f"RAG offline: {err}",
            "hint": "Execute: python scripts/rag_ingestor.py --rebuild"
        }, ensure_ascii=False))]

    if name == "rag_search":
        query_text = arguments.get("query", "")
        tipo       = arguments.get("tipo")
        obra       = arguments.get("obra")
        k          = min(int(arguments.get("k", 5)), 20)
        threshold  = float(arguments.get("threshold", 0.20))

        try:
            results = do_rag_search(query_text, tipo, obra, k, threshold)
            payload = {
                "query": query_text,
                "tipo_filtro": tipo,
                "obra_filtro": obra,
                "n_resultados": len(results),
                "resultados": results,
            }
            return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]

    elif name == "rag_stats":
        try:
            stats = do_rag_stats()
            return [TextContent(type="text", text=json.dumps(stats, ensure_ascii=False, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]

    return [TextContent(type="text", text=json.dumps({"error": f"Tool desconhecida: {name}"}))]


# ── ENTRY POINT ──────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
