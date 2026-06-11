# -*- coding: utf-8 -*-
"""Motor Reverso LV — Extrai ficha N2 de recorte DXF STOG lateral viga."""

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

def _lookup_fase4_lv(elem_id: str, obra_root: Path) -> dict | None:
    """Busca JSON_Vigas_Laterais/{elem_id}.json. Aceita 'V1' -> V1_A.json e V1_B.json."""
    # Exact match
    p = obra_root / "Fase-4_Sincronizacao" / "JSON_Vigas_Laterais" / f"{elem_id}.json"
    if p.exists():
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    # Try side variants: V1 -> V1_A, V1_B
    for side in ('A', 'B'):
        p2 = obra_root / "Fase-4_Sincronizacao" / "JSON_Vigas_Laterais" / f"{elem_id}_{side}.json"
        if p2.exists():
            with open(p2, encoding='utf-8') as f:
                return json.load(f)
    return None

def _extract_lv_from_dxf(dxf_path: str) -> dict:
    """Extrai campos LV basicos do DXF recorte."""
    result = {'panels': [], 'holes': [], '_confianca_extracao': 0.4}
    try:
        import ezdxf
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        # Coletar COTA texts — apenas layer "COTA" (excluir "COTA SECAO" que tem dims de corte)
        cota_nums = []
        for e in msp:
            if e.dxftype() != 'TEXT':
                continue
            layer = e.dxf.layer.upper()
            if layer != 'COTA':  # Ignorar COTA SECAO (2X), COTA INTERNA, etc.
                continue
            try:
                cota_nums.append(float(e.dxf.text.strip()))
            except Exception:
                pass

        # Panel widths: chapas tipicas 244, 122, 100, 50... (excluir valores < 50)
        # Usar apenas valores que sejam multiplos razoaveis (nao frações de DXF)
        panel_widths = sorted(
            [round(v) for v in cota_nums if 50 <= v <= 300 and round(v) == int(round(v))],
            reverse=True
        )

        # total_width da viga (espessura): geralmente 14-30cm
        total_w_candidates = [v for v in cota_nums if 5 < v < 50]
        total_width = min(total_w_candidates) if total_w_candidates else 19.0

        # Total height (altura da viga lateral): geralmente 30-100cm
        # Usar valores inteiros no range 30-100 para evitar capturar larguras de chapa
        height_candidates = [v for v in cota_nums if 30 <= v <= 100 and v == round(v)]
        total_height = min(height_candidates) if height_candidates else 50.0

        result['total_width'] = total_width
        result['total_height'] = total_height

        for w in (panel_widths[:6] if panel_widths else []):
            result['panels'].append({
                'width': w, 'height1': total_height, 'height2': total_height,
                'grade_h1': str(w), 'grade_h2': str(w),
            })

        # Padrao 4 holes vazios
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

def extrair_ficha_lateral_viga(
    recorte_path: str,
    elemento_id: str,
    obra_name: str | None = None,
    obra_root: str | Path | None = None,
) -> dict:
    obra_root_path = Path(obra_root) if obra_root else _infer_obra_root(recorte_path)
    if obra_name and obra_root_path is None:
        obra_root_path = DADOS_OBRAS_ROOT / obra_name

    fase4 = _lookup_fase4_lv(elemento_id, obra_root_path) if obra_root_path else None
    dxf_data = _extract_lv_from_dxf(recorte_path)
    dxf_conf = dxf_data.pop('_confianca_extracao', 0.4)
    dxf_data.pop('_extracao_erro', None)

    if fase4:
        result = {k: v for k, v in fase4.items() if k != '_sa_meta'}
        result['_er_meta'] = {'source': 'fase4', 'dxf_path': str(recorte_path), 'confianca': 0.95}
        result['_confianca'] = 0.95
    else:
        elem_num = re.sub(r'[^\d]', '', elemento_id.split('_')[0])
        side = elemento_id.split('_')[-1] if '_' in elemento_id else 'A'
        result = {
            'number': elem_num,
            'name': elemento_id,
            'floor': 'Pavimento',
            'side': side if side in ('A','B') else 'A',
            **dxf_data,
        }
        result['_er_meta'] = {'source': 'dxf_extract', 'dxf_path': str(recorte_path), 'confianca': dxf_conf}
        result['_confianca'] = dxf_conf

    return result


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    elem = sys.argv[2] if len(sys.argv) > 2 else "V1_A"
    obra = sys.argv[3] if len(sys.argv) > 3 else None
    result = extrair_ficha_lateral_viga(path, elem, obra)
    print(json.dumps(result, indent=2, ensure_ascii=False))
