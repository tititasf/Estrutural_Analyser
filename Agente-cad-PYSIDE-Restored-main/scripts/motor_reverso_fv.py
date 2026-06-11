# -*- coding: utf-8 -*-
"""Motor Reverso FV — Extrai ficha N2 de recorte DXF STOG fundo de viga."""

from pathlib import Path
import json, re

DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")

def _infer_obra_root(recorte_path: str) -> Path | None:
    p = Path(recorte_path)
    for part in p.parts:
        if part.startswith("Obra_"):
            idx = p.parts.index(part)
            return Path(*p.parts[:idx+1])
    return None

def _lookup_fase4_fv(elem_id: str, obra_root: Path) -> dict | None:
    """Busca JSON_Vigas_Fundo/{elem_id}_fundo.json."""
    # Remove side suffix if present (V1_A -> V1)
    base = elem_id.split('_')[0] if '_' in elem_id else elem_id
    p = obra_root / "Fase-4_Sincronizacao" / "JSON_Vigas_Fundo" / f"{base}_fundo.json"
    if p.exists():
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    # Try exact elem_id
    p2 = obra_root / "Fase-4_Sincronizacao" / "JSON_Vigas_Fundo" / f"{elem_id}_fundo.json"
    if p2.exists():
        with open(p2, encoding='utf-8') as f:
            return json.load(f)
    return None

def _extract_fv_from_dxf(dxf_path: str) -> dict:
    """Extrai campos FV basicos do DXF recorte.

    Para FV o recorte é uma vista de planta do fundo da viga.
    total_height = espessura do fundo (largura da viga, tipicamente 14-30cm)
    panel widths = comprimentos dos paineis fundo (tipicamente 244cm max)
    """
    result = {'panels': [], 'holes': [], '_confianca_extracao': 0.4}
    try:
        import ezdxf
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        # Apenas layer COTA exato (sem COTA SECAO etc.)
        cota_nums = []
        for e in msp:
            if e.dxftype() != 'TEXT':
                continue
            if e.dxf.layer.upper() != 'COTA':
                continue
            try:
                cota_nums.append(float(e.dxf.text.strip()))
            except Exception:
                pass
        # Panel widths: comprimentos de chapa >= 50cm, valores inteiros
        panel_widths = sorted(
            [round(v) for v in cota_nums if 50 <= v <= 300 and round(v) == int(round(v))],
            reverse=True
        )
        # Espessura do fundo (largura da viga): 14-30cm
        w_candidates = [v for v in cota_nums if 14 <= v <= 30]
        total_w = min(w_candidates) if w_candidates else 19.0
        # Altura do fundo (h do painel fundo): normalmente 14-30cm tambem
        # Nao usar range 30-150 pois captura comprimentos de panel
        h_candidates = [v for v in cota_nums if 14 <= v <= 30]
        total_h = min(h_candidates) if h_candidates else total_w
        result['total_width'] = total_w
        result['total_height'] = total_h
        for w in (panel_widths[:8] if panel_widths else []):
            result['panels'].append({'width': w, 'height1': total_h, 'height2': total_h, 'grade_h1': str(w), 'grade_h2': str(w)})
        result['holes'] = [{'active': False, 'width': 0.0, 'height': 0.0, 'position': 0.0}] * 4
        result['pillar_left'] = {'active': False, 'width': 0.0, 'length': 0.0}
        result['pillar_right'] = {'active': False, 'width': 0.0, 'length': 0.0}
        result['sarrafo_left_id'] = 0
        result['sarrafo_right_id'] = 0
        result['_confianca_extracao'] = 0.6 if panel_widths else 0.35
    except Exception as ex:
        result['_extracao_erro'] = str(ex)
        result['_confianca_extracao'] = 0.3
    return result

def extrair_ficha_fundo_viga(
    recorte_path: str,
    elemento_id: str,
    obra_name: str | None = None,
    obra_root: str | Path | None = None,
) -> dict:
    obra_root_path = Path(obra_root) if obra_root else _infer_obra_root(recorte_path)
    if obra_name and obra_root_path is None:
        obra_root_path = DADOS_OBRAS_ROOT / obra_name
    fase4 = _lookup_fase4_fv(elemento_id, obra_root_path) if obra_root_path else None
    dxf_data = _extract_fv_from_dxf(recorte_path)
    dxf_conf = dxf_data.pop('_confianca_extracao', 0.4)
    dxf_data.pop('_extracao_erro', None)
    if fase4:
        result = {k: v for k, v in fase4.items() if k != '_sa_meta'}
        result['_er_meta'] = {'source': 'fase4', 'dxf_path': str(recorte_path), 'confianca': 0.95}
        result['_confianca'] = 0.95
    else:
        base_id = elemento_id.split('_')[0] if '_' in elemento_id else elemento_id
        elem_num = re.sub(r'[^\d]', '', base_id)
        result = {
            'number': elem_num, 'name': elemento_id, 'floor': 'Pavimento',
            **dxf_data,
        }
        result['_er_meta'] = {'source': 'dxf_extract', 'dxf_path': str(recorte_path), 'confianca': dxf_conf}
        result['_confianca'] = dxf_conf
    return result


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    elem = sys.argv[2] if len(sys.argv) > 2 else "V1"
    obra = sys.argv[3] if len(sys.argv) > 3 else None
    result = extrair_ficha_fundo_viga(path, elem, obra)
    print(json.dumps(result, indent=2, ensure_ascii=False))
