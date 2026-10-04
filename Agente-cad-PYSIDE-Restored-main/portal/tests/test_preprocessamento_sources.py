from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from portal.app.preprocessamento.sources import (
    BindingScope,
    ConventionBinding,
    SourceKind,
    SourceResolutionError,
    inventory_floor_sources,
    resolve_crop_source,
    select_convention_bindings,
)


def _write_crop(root: Path, bruto: str, item: str, content: bytes = b"DXF") -> Path:
    path = root / "Fase-2_Triagem" / "recortes" / bruto / f"{item}.dxf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _write_input(root: Path, name: str) -> None:
    path = root / "entrada" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"input")


def test_resolve_identidade_completa_e_hash_de_conteudo(tmp_path):
    _write_crop(tmp_path, "estrutura", "torre_1", b"tower-one")
    source = resolve_crop_source(
        obra_dir=tmp_path,
        obra_id="obra-a",
        pavimento_id="14_PAV",
        bruto_id="estrutura",
        item_id="torre_1",
    )

    assert source.kind is SourceKind.TOWER
    assert source.revision == hashlib.sha256(b"tower-one").hexdigest()
    assert source.relative_path.endswith("estrutura/torre_1.dxf")


def test_mesmo_item_em_obra_torre_ou_pavimento_distinto_nao_colide(tmp_path):
    _write_crop(tmp_path, "estrutura", "torre_1")
    base = dict(obra_dir=tmp_path, bruto_id="estrutura", item_id="torre_1")
    a = resolve_crop_source(**base, obra_id="obra-a", pavimento_id="14_PAV")
    b = resolve_crop_source(**base, obra_id="obra-b", pavimento_id="14_PAV")
    c = resolve_crop_source(**base, obra_id="obra-a", pavimento_id="15_PAV")
    _write_crop(tmp_path, "estrutura", "torre_2")
    d = resolve_crop_source(
        obra_dir=tmp_path, obra_id="obra-a", pavimento_id="14_PAV",
        bruto_id="estrutura", item_id="torre_2",
    )

    assert len({a.source_id, b.source_id, c.source_id, d.source_id}) == 4


@pytest.mark.parametrize("field,value", [("bruto_id", "../fora"), ("item_id", "x/y"), ("bruto_id", "C:drive")])
def test_path_traversal_e_rejeitado(tmp_path, field, value):
    args = dict(
        obra_dir=tmp_path, obra_id="obra-a", pavimento_id="14_PAV",
        bruto_id="estrutura", item_id="torre_1",
    )
    args[field] = value
    with pytest.raises(SourceResolutionError, match="inválido"):
        resolve_crop_source(**args)


def test_inventario_usa_cadastro_do_pavimento_e_ignora_historico(tmp_path):
    _write_input(tmp_path, "A.dxf")
    _write_input(tmp_path, "B.dxf")
    _write_crop(tmp_path, "A", "torre_1")
    _write_crop(tmp_path, "A", "detalhes")
    _write_crop(tmp_path, "B", "torre_1")
    historical = tmp_path / "Fase-2_Triagem" / "recortes_reversos" / "PIL_P1_motor_1.dxf"
    historical.parent.mkdir(parents=True)
    historical.write_bytes(b"old")
    docs = [
        {"arquivo_nome": "A.dxf", "pavimento_confirmado": "14_PAV"},
        {"arquivo_nome": "B.dxf", "pavimento_confirmado": "15_PAV"},
    ]

    sources = inventory_floor_sources(
        obra_dir=tmp_path, obra_id="obra-a", pavimento_id="14_PAV", documents=docs
    )

    assert [(item.bruto_id, item.item_id) for item in sources] == [
        ("A", "detalhes"), ("A", "torre_1")
    ]
    assert all("recortes_reversos" not in item.relative_path for item in sources)


def test_precedencia_de_binding_e_empate_preservado(tmp_path):
    _write_crop(tmp_path, "A", "convencao_pilares", b"floor-1")
    floor_source = resolve_crop_source(
        obra_dir=tmp_path, obra_id="obra-a", pavimento_id="14_PAV",
        bruto_id="A", item_id="convencao_pilares",
    )
    _write_crop(tmp_path, "A", "detalhes", b"tower-1")
    tower_source_1 = resolve_crop_source(
        obra_dir=tmp_path, obra_id="obra-a", pavimento_id="14_PAV",
        bruto_id="A", item_id="detalhes",
    )
    _write_crop(tmp_path, "B", "detalhes", b"tower-2")
    tower_source_2 = resolve_crop_source(
        obra_dir=tmp_path, obra_id="obra-a", pavimento_id="14_PAV",
        bruto_id="B", item_id="detalhes",
    )
    bindings = [
        ConventionBinding(floor_source, "pillars", BindingScope.FLOOR, "obra-a", "14_PAV"),
        ConventionBinding(tower_source_1, "pillars", BindingScope.TOWER, "obra-a", "14_PAV", "rec:torre_1"),
        ConventionBinding(tower_source_2, "pillars", BindingScope.TOWER, "obra-a", "14_PAV", "rec:torre_1"),
    ]

    selected = select_convention_bindings(
        bindings, obra_id="obra-a", pavimento_id="14_PAV",
        tower_recorte_id="rec:torre_1", convention_type="pillars",
    )

    assert {item.source.source_id for item in selected} == {
        tower_source_1.source_id, tower_source_2.source_id
    }


def test_binding_de_outra_obra_e_rejeitado(tmp_path):
    _write_crop(tmp_path, "A", "detalhes")
    source = resolve_crop_source(
        obra_dir=tmp_path, obra_id="obra-a", pavimento_id="14_PAV",
        bruto_id="A", item_id="detalhes",
    )
    with pytest.raises(SourceResolutionError, match="obras diferentes"):
        ConventionBinding(source, "pillars", BindingScope.WORK, "obra-b")
