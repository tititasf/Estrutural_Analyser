from __future__ import annotations

import hashlib
import json

from scripts.arete import arete_runner


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_g6_rejects_pass_without_complete_checklist(tmp_path, monkeypatch):
    recorte = tmp_path / "n2.dxf"
    n4 = tmp_path / "n4.dxf"
    recorte.write_bytes(b"n2-current")
    n4.write_bytes(b"n4-current")
    report_dir = tmp_path / "g2v" / "20260706_170000"
    report_dir.mkdir(parents=True)
    report = {
        "par": "n2xn4",
        "itens": [{
            "classe": "LAJ",
            "elemento_id": "L318",
            "evidencia_fontes": {
                "n2": {"sha256": _hash(recorte)},
                "n4": {"sha256": _hash(n4)},
            },
            "vereditos": {
                "cli": {
                    "veredito": "PASS",
                    "checklist_visual": {"cotas_posicao_legibilidade": None},
                }
            },
        }],
    }
    (report_dir / "relatorio.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    monkeypatch.setattr(arete_runner, "RELATORIOS_DIR", tmp_path)
    monkeypatch.setattr(
        arete_runner, "get_recorte_path", lambda *args, **kwargs: recorte
    )

    valid, reason = arete_runner.g2v_pass_atual(
        {"classe": "LAJ", "elemento_id": "L318"}, n4
    )

    assert not valid
    assert "checklist" in reason


def test_g6_accepts_strict_pass_for_current_sources(tmp_path, monkeypatch):
    recorte = tmp_path / "n2.dxf"
    n4 = tmp_path / "n4.dxf"
    recorte.write_bytes(b"n2-current")
    n4.write_bytes(b"n4-current")
    report_dir = tmp_path / "g2v" / "20260706_170001"
    report_dir.mkdir(parents=True)
    report = {
        "par": "n2xn4",
        "itens": [{
            "classe": "LAJ",
            "elemento_id": "L318",
            "evidencia_fontes": {
                "n2": {"sha256": _hash(recorte)},
                "n4": {"sha256": _hash(n4)},
            },
            "vereditos": {
                "cli": {
                    "veredito": "PASS",
                    "checklist_visual": {
                        "fonte_atual_confirmada": True,
                        "cotas_posicao_legibilidade": True,
                    },
                }
            },
        }],
    }
    (report_dir / "relatorio.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    monkeypatch.setattr(arete_runner, "RELATORIOS_DIR", tmp_path)
    monkeypatch.setattr(
        arete_runner, "get_recorte_path", lambda *args, **kwargs: recorte
    )

    valid, _ = arete_runner.g2v_pass_atual(
        {"classe": "LAJ", "elemento_id": "L318"}, n4
    )

    assert valid
