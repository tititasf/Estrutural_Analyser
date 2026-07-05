from pathlib import Path
from types import SimpleNamespace

import scripts.arete.gerar_n4_item as gerar_n4_item


def test_publicar_splits_pil_n4_gera_as_tres_zonas(monkeypatch, tmp_path):
    obra_dir = tmp_path / "materializada"
    temp_out = obra_dir / "Fase-6_Execucao_CAD"
    temp_out.mkdir(parents=True)
    dados_obras = tmp_path / "dados-obras"
    monkeypatch.setattr(gerar_n4_item, "DADOS_OBRAS", dados_obras)

    called_zones = []

    def fake_run(cmd, **_kwargs):
        zone = cmd[cmd.index("--zone") + 1]
        called_zones.append(zone)
        output = temp_out / f"PL_{zone.upper()}_preview_P17.dxf"
        output.write_bytes(f"DXF-{zone}".encode())
        return SimpleNamespace(returncode=0, stdout=f"ok {zone}\n", stderr="")

    monkeypatch.setattr(gerar_n4_item.subprocess, "run", fake_run)

    ok, published, log = gerar_n4_item._publicar_splits_pil_n4(
        obra_dir, "Obra_TREINO_1", "P17"
    )

    assert ok is True
    assert called_zones == ["cima", "abcd", "grades"]
    assert set(published) == {"CIMA", "ABCD", "GRADES"}
    assert "ok grades" in log
    for path in published.values():
        assert Path(path).is_file()
        assert Path(path).parent.name == "n4"


def test_publicar_splits_pil_n4_falha_se_artefato_nao_for_gerado(
    monkeypatch, tmp_path
):
    obra_dir = tmp_path / "materializada"
    (obra_dir / "Fase-6_Execucao_CAD").mkdir(parents=True)
    monkeypatch.setattr(gerar_n4_item, "DADOS_OBRAS", tmp_path / "dados-obras")
    monkeypatch.setattr(
        gerar_n4_item.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout="", stderr=""
        ),
    )

    ok, published, error = gerar_n4_item._publicar_splits_pil_n4(
        obra_dir, "Obra_TREINO_1", "P1"
    )

    assert ok is False
    assert published == {}
    assert "ausente ou vazio" in error


def test_gerar_item_pil_publica_tambem_o_dxf_combinado(monkeypatch, tmp_path):
    obra_dir = tmp_path / "materializada"
    out_dir = obra_dir / "Fase-6_Execucao_CAD"
    out_dir.mkdir(parents=True)
    combined = out_dir / "PL_preview_P5.dxf"
    combined.write_bytes(b"COMBINADO-CIMA-ABCD-GRADES")
    dados_obras = tmp_path / "dados-obras"

    monkeypatch.setattr(gerar_n4_item, "DADOS_OBRAS", dados_obras)
    monkeypatch.setattr(
        gerar_n4_item,
        "query_ficha_item",
        lambda *_args: {
            "obra_name": "Obra_TREINO_1",
            "campos_json": {"nome": "P5"},
        },
    )
    monkeypatch.setattr(
        gerar_n4_item,
        "materializar_item",
        lambda *_args: (obra_dir, obra_dir / "P5.json"),
    )
    monkeypatch.setattr(
        gerar_n4_item, "rodar_gerador", lambda *_args: (True, "ok")
    )
    monkeypatch.setattr(
        gerar_n4_item,
        "get_output_dxf_path",
        lambda *_args: combined,
    )
    monkeypatch.setattr(
        gerar_n4_item,
        "_publicar_splits_pil_n4",
        lambda *_args: (True, {}, ""),
    )

    result = gerar_n4_item.gerar_item("PIL", "P5", verbose=False)

    canonical = (
        dados_obras
        / "Obra_TREINO_1"
        / "Fase-6_Execucao_CAD"
        / "n4"
        / "PL_preview_P5.dxf"
    )
    assert result["ok"] is True
    assert result["dxf_path"] == str(canonical)
    assert canonical.read_bytes() == combined.read_bytes()
