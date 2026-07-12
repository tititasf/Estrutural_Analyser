"""AC4 — path traversal via `code`/`nivel` nunca lê arquivo fora de
`DADOS_OBRAS_ROOT`. Consolida `tests/test_path_traversal.py` (STORY-06) e
`tests/test_paineis_lv_endpoint.py::test_paineis_lv_obra_dir_fora_da_raiz_404`
(STORY-12) num único lugar, exercitando ambos os endpoints que leem
arquivo (`/svg/{nivel}`, `/paineis-lv`)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from conftest import requisitar

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _montar_obra_fora_da_raiz(tmp_path: Path) -> tuple[Path, Path]:
    """`obra_dir` real (com dado de verdade) MAS fisicamente fora da árvore
    que `dados_obras_root` permite — simula um registro corrompido/malicioso
    em `public_codes.obra_dir`."""
    raiz_permitida = tmp_path / "DADOS-OBRAS-PERMITIDO"
    raiz_permitida.mkdir()
    obra_dir = tmp_path / "fora_da_raiz" / "obra_maliciosa"
    obra_dir.mkdir(parents=True)

    estado = {
        "pilares": [{"name": "P1", "points": [[0, 0], [30, 0], [30, 30], [0, 30]],
                     "classification": "OK", "lado_A": "V1", "nivel_str": "N1"}],
        "slabs": [], "cortes": [],
        "segmentos": {"fundo": [], "lateral_a_para": [], "lateral_b_para": [],
                      "lateral_a_passa": [], "lateral_b_passa": []},
    }
    (obra_dir / "estado_TERREO.json").write_text(json.dumps(estado), encoding="utf-8")
    run_dir = obra_dir / "TERREO_20260101_000000"
    (run_dir / "pilares").mkdir(parents=True)
    (run_dir / "arete_manifest.json").write_text("{}", encoding="utf-8")
    (run_dir / "pilares" / "P1.html").write_text(
        '<div class="face-card">N1 <svg class="img-geo" viewbox="0 0 10 10"></svg></div>',
        encoding="utf-8",
    )
    return raiz_permitida, obra_dir


def _db_com_item_fora_da_raiz(tmp_path: Path, obra_dir: Path) -> Path:
    db_path = tmp_path / "public_traversal.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "('ITEMFORA01', 'item', 'obra-x', ?, 'TERREO', 'pilares', 'P1', 'pilar', 'Pilar P1', 0)",
        (str(obra_dir),),
    )
    conn.commit()
    conn.close()
    return db_path


def test_svg_nunca_le_arquivo_fora_de_dados_obras_root(tmp_path: Path):
    raiz_permitida, obra_dir = _montar_obra_fora_da_raiz(tmp_path)
    db_path = _db_com_item_fora_da_raiz(tmp_path, obra_dir)

    resp = requisitar(db_path, raiz_permitida, "GET", "/api/v1/ficha/ITEMFORA01/svg/n1")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}
    # Nunca vaza o conteúdo real do arquivo (prova que não foi lido).
    assert "<svg" not in resp.text


def test_paineis_lv_nunca_le_arquivo_fora_de_dados_obras_root(tmp_path: Path):
    raiz_permitida, obra_dir = _montar_obra_fora_da_raiz(tmp_path)
    # Reescreve o item como viga_lateral com um "contrato LV" fora da raiz.
    lv_dir = obra_dir / "Fase-4_Sincronizacao" / "JSON_Vigas_Laterais" / "LV-PARA"
    lv_dir.mkdir(parents=True)
    (lv_dir / "VIGA1_A.json").write_text(
        json.dumps({"total_width": 999, "h_section": 1, "panels": [{"width": 1, "height1": 1, "height2": 1, "panel_type": "x"}]}),
        encoding="utf-8",
    )
    db_path = tmp_path / "public_traversal2.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "('ITEMFORA02', 'item', 'obra-x', ?, 'TERREO', 'lateral_a_para', 'a-VIGA1', 'viga_lateral', 'Viga', 0)",
        (str(obra_dir),),
    )
    conn.commit()
    conn.close()

    resp = requisitar(db_path, raiz_permitida, "GET", "/api/v1/ficha/ITEMFORA02/paineis-lv")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}
    assert "999" not in resp.text


def test_codigo_com_payloads_de_traversal_conhecidos_sempre_404(duas_obras):
    """`code` (chave de lookup, NUNCA componente de caminho) com payloads
    clássicos de traversal — todos devem cair no 404 genérico de
    `/resolve`, nunca num 200/500."""
    db_path, raiz, _codigos = duas_obras

    payloads = [
        "..%2F..%2Fetc%2Fpasswd",
        "....//....//etc/passwd",
        "..\\..\\windows\\win.ini",
        "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        "AAAAAAAAAA%00.svg",
    ]
    for payload in payloads:
        resp = requisitar(db_path, raiz, "GET", f"/api/v1/resolve/{payload}")
        assert resp.status_code in (404, 400), f"payload {payload!r} -> {resp.status_code}"
        assert resp.status_code != 200


def test_nivel_com_traversal_nao_alcanca_arquivo_fora_da_raiz(duas_obras):
    db_path, raiz, codigos = duas_obras
    resp = requisitar(db_path, raiz, "GET", f"/api/v1/ficha/{codigos['pilar_a']}/svg/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code == 404
    assert "root:" not in resp.text  # conteúdo típico de /etc/passwd nunca vaza
