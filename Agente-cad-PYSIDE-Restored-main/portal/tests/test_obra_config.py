"""Bloqueios do comportamento configurado na obra (D-78)."""
import sqlite3

import pytest
from fastapi import HTTPException

from portal.app.routers.n1_routes import _bloquear_modo_oposto
from portal.db import connection, repository as repo


class _Request:
    def __init__(self, **params):
        self.path_params = params
        self.query_params = {}
        self.url = type("URL", (), {"path": "/obras/o/n1/pilares/P1/pilar-n3-ficha"})()


def test_rotas_laterais_e_abas_pilar_respeitam_modo(tmp_path):
    conn = connection.init_db(tmp_path / "portal.db")
    membro = repo.criar_membro(conn, login="a", nome="A", senha_hash="x", drive_folder_id="d")
    obra = repo.criar_obra(conn, membro_id=membro, nome="Obra", pasta_drive_id="p")
    repo.atualizar_cabecalho_obra(conn, obra, comportamento="para")
    for params in ({"behavior": "passa"}, {"classe": "lateral_a_passa"},
                   {"classe": "pilares", "vista": "abcd-passa"},
                   {"classe": "pilares_n3_passa"}):
        with pytest.raises(HTTPException) as exc:
            _bloquear_modo_oposto(_Request(obra_id=obra, **params), conn)
        assert exc.value.status_code == 404
    for params in ({"behavior": "para"}, {"classe": "fundo"}, {"classe": "lajes"},
                   {"classe": "pilares", "vista": "grades-para"}):
        _bloquear_modo_oposto(_Request(obra_id=obra, **params), conn)
    repo.atualizar_cabecalho_obra(conn, obra, comportamento="misto")
    _bloquear_modo_oposto(_Request(obra_id=obra, classe="lateral_a_passa"), conn)
    repo.atualizar_cabecalho_obra(conn, obra, comportamento="passa")
    with pytest.raises(HTTPException):
        _bloquear_modo_oposto(_Request(obra_id=obra, classe="pilares"), conn)
    conn.close()
