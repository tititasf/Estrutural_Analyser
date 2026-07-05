import shutil
from pathlib import Path
from types import SimpleNamespace

import src.ui.modules.comparison_engine as comparison_engine
from src.ui.modules.comparison_engine import ComparisonEngineModule


def test_pil_n4_ui_gera_combinado_no_mesmo_ciclo_dos_splits(
    monkeypatch, tmp_path
):
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        temp_root = Path(command[command.index("--obra") + 1])
        item_id = command[command.index("--item") + 1]
        if "--zone" in command:
            zone = command[command.index("--zone") + 1].upper()
            filename = f"PL_{zone}_preview_{item_id}.dxf"
        else:
            filename = f"PL_preview_{item_id}.dxf"
        output = temp_root / "Fase-6_Execucao_CAD" / filename
        output.write_bytes(filename.encode())
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    def fake_promote(source, canonical, **_kwargs):
        canonical.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, canonical)
        return canonical

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(comparison_engine, "guarded_promote", fake_promote)

    fake = SimpleNamespace(
        fase8_panel=SimpleNamespace(current_pav_key="13_PAV"),
        _get_recorte_dxf_for_er=lambda *_args, **_kwargs: None,
        _get_pd_pavimento_cm=lambda *_args, **_kwargs: None,
        _visual_mode_for=lambda *_args: "NOVA",
    )
    obra_dir = tmp_path / "Obra_TREINO_1"

    zones = ComparisonEngineModule._generate_pil_zones_n4(
        fake,
        obra_dir,
        "Obra_TREINO_1",
        "P5",
        {"nome": "P5", "comprimento": 66, "largura": 19, "altura": 280},
    )

    official = obra_dir / "Fase-6_Execucao_CAD" / "n4"
    assert (official / "PL_preview_P5.dxf").is_file()
    assert set(zones) == {"ABCD", "CIMA", "GRADES"}
    assert all(path.is_file() for path in zones.values())
    assert len(calls) == 4
    assert "--zone" not in calls[0]
