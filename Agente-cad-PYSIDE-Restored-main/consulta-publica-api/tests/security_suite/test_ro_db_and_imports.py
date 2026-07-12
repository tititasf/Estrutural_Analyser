"""AC6 — `public_consulta.db` está de fato aberto `mode=ro` (não só por
convenção de código). AC7 — nenhum import proibido em `consulta-publica-api/**`.
AC10 — CORS bloqueia origem não autorizada mesmo em endpoint real com dado."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from conftest import requisitar

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_IMPORTS_PROIBIDOS = (
    "portal.app.auth", "portal.app.access", "portal.app.repository",
    "portal.db.connection", "lv_generation_contract", "PySide6", "PyQt",
)
_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.MULTILINE)


def test_conexao_real_da_api_e_fisicamente_read_only(duas_obras):
    """AC6 — usa a MESMA função (`db.connection.get_ro_connection`) e o
    MESMO arquivo de banco que a API pública abre em produção; tenta
    escrever através dela e espera falha físical (não validação de app)."""
    from db.connection import get_ro_connection

    db_path, _raiz, _codigos = duas_obras
    conn = get_ro_connection(db_path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                "INSERT INTO public_codes (code, kind, obra_id, obra_dir) "
                "VALUES ('HACKED0001', 'item', 'x', 'y')"
            )
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("UPDATE public_codes SET revoked = 0 WHERE 1=1")
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM public_codes")
    finally:
        conn.close()


def test_nenhum_arquivo_da_api_publica_importa_modulo_proibido():
    """AC7 — expande `tests/test_isolation.py::test_no_forbidden_imports`
    com `lv_generation_contract`/PySide6/PyQt (STORY-12) na mesma varredura,
    consolidando a checagem completa da Architecture §5.4 num só lugar."""
    self_path = Path(__file__).resolve()
    violacoes: list[str] = []
    for path in _PROJECT_ROOT.rglob("*.py"):
        if path.resolve() == self_path:
            continue
        texto = path.read_text(encoding="utf-8", errors="replace")
        for match in _IMPORT_RE.finditer(texto):
            modulo = match.group(1)
            for proibido in _IMPORTS_PROIBIDOS:
                if modulo == proibido or modulo.startswith(proibido + "."):
                    violacoes.append(f"{path.relative_to(_PROJECT_ROOT)}: import {modulo}")
    assert not violacoes, "Imports proibidos encontrados:\n" + "\n".join(violacoes)


def test_cors_bloqueia_origem_nao_autorizada_em_endpoint_real_com_dado(duas_obras):
    """AC10 — não basta testar `/health` (STORY-04); reconfirma contra um
    endpoint que retorna dado real (`/ficha/{code}`)."""
    db_path, raiz, codigos = duas_obras

    resp_hostil = requisitar(
        db_path, raiz, "GET", f"/api/v1/ficha/{codigos['pilar_a']}",
        headers={"Origin": "http://site-hostil.exemplo.com"},
    )
    # Requisição simples (GET) não é bloqueada pelo browser preflight, mas o
    # header de resposta NUNCA deve ecoar a origem hostil.
    assert resp_hostil.headers.get("access-control-allow-origin") != "http://site-hostil.exemplo.com"

    resp_legitima = requisitar(
        db_path, raiz, "GET", f"/api/v1/ficha/{codigos['pilar_a']}",
        headers={"Origin": "http://127.0.0.1:21391"},
    )
    assert resp_legitima.headers.get("access-control-allow-origin") == "http://127.0.0.1:21391"
