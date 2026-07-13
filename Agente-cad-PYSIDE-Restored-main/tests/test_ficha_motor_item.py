from __future__ import annotations

import json

import ezdxf

from scripts.arete.ficha_motor_item import build_ficha
from scripts.arete.qa_content_cache import ContentAddressedCache


def test_build_ficha_motor_item_embeds_dxf_json_and_hashes(tmp_path):
    dxf = tmp_path / 'item.dxf'
    doc = ezdxf.new('R2010')
    doc.modelspace().add_line((0, 0), (10, 5))
    doc.saveas(dxf)
    payload = tmp_path / 'item.json'
    payload.write_text(
        json.dumps({'abertura_A_1': {'largura': 11, 'altura': 59}}),
        encoding='utf-8',
    )

    index = build_ficha(
        classe='PIL', item='P1', nivel='N3',
        artifacts=[('PASSA', dxf)], jsons={'PASSA': payload},
        output_dir=tmp_path / 'ficha',
    )

    document = index.read_text(encoding='utf-8')
    manifesto = json.loads((index.parent / 'manifesto.json').read_text(encoding='utf-8'))
    assert '<svg' in document
    assert 'abertura_A_1' in document
    assert manifesto['authority'].startswith('visual_iteration_only')
    assert len(manifesto['artifacts'][0]['dxf_sha256']) == 64


def test_build_ficha_reuses_svg_cache_and_tracks_contract(tmp_path):
    dxf = tmp_path / 'item.dxf'
    doc = ezdxf.new('R2010')
    doc.modelspace().add_line((0, 0), (10, 5))
    doc.saveas(dxf)
    payload = tmp_path / 'item.json'
    payload.write_text(json.dumps({'abertura_A_1': {'largura': 11}}), encoding='utf-8')
    contract = tmp_path / 'contract.json'
    contract.write_text(json.dumps({'slot': 'abertura_A_1', 'largura': 11}), encoding='utf-8')
    cache = ContentAddressedCache(tmp_path / 'cache')

    first = build_ficha(
        classe='PIL', item='P1', nivel='N3', artifacts=[('PARA', dxf)],
        jsons={'PARA': payload}, contracts={'PARA': contract}, cache=cache,
        output_dir=tmp_path / 'first',
    )
    second = build_ficha(
        classe='PIL', item='P1', nivel='N3', artifacts=[('PARA', dxf)],
        jsons={'PARA': payload}, contracts={'PARA': contract}, cache=cache,
        output_dir=tmp_path / 'second',
    )
    first_manifest = json.loads((first.parent / 'manifesto.json').read_text(encoding='utf-8'))
    second_manifest = json.loads((second.parent / 'manifesto.json').read_text(encoding='utf-8'))
    assert first_manifest['artifacts'][0]['render_cache_hit'] is False
    assert second_manifest['artifacts'][0]['render_cache_hit'] is True
    assert first_manifest['input_signature'] == second_manifest['input_signature']
    assert len(second_manifest['artifacts'][0]['contract_sha256']) == 64
    assert 'Contrato exato' in second.read_text(encoding='utf-8')
