# -*- coding: utf-8 -*-
"""Motor Reverso LAJ — Extrai ficha N2 de recorte DXF STOG laje."""

from pathlib import Path
import json, re, math

DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")

def _infer_obra_root(recorte_path: str) -> Path | None:
    p = Path(recorte_path)
    for part in p.parts:
        if part.startswith("Obra_"):
            idx = p.parts.index(part)
            return Path(*p.parts[:idx+1])
    return None

def _lookup_fase4_laj(elem_id: str, obra_root: Path) -> dict | None:
    p = obra_root / "Fase-4_Sincronizacao" / "JSON_Lajes" / f"{elem_id}.json"
    if p.exists():
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    return None

def _extract_laj_from_dxf(dxf_path: str) -> dict:
    """Extrai campos LAJ do DXF recorte."""
    result = {'_confianca_extracao': 0.4}
    try:
        import ezdxf
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        # Bounding box da laje via Hachura ou maior LWPOLYLINE
        best_poly = None
        best_area = 0
        for e in msp:
            if e.dxftype() == 'LWPOLYLINE':
                pts = list(e.get_points())
                if len(pts) >= 4:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    area = abs(max(xs)-min(xs)) * abs(max(ys)-min(ys))
                    if area > best_area:
                        best_area = area
                        best_poly = (min(xs), min(ys), max(xs), max(ys))

        if best_poly:
            x0, y0, x1, y1 = best_poly
            comp = round(abs(x1-x0), 2)
            larg = round(abs(y1-y0), 2)
            result['comprimento'] = comp
            result['largura'] = larg
            result['area_cm2'] = round(comp * larg, 2)
            result['coordenadas'] = [[0,comp],[larg,comp],[larg,0],[0,0],[0,comp]]

        # COTA texts -> linhas verticais/horizontais
        cota_nums = []
        for e in msp:
            if e.dxftype() == 'TEXT' and 'COTA' in e.dxf.layer.upper():
                try:
                    cota_nums.append(float(e.dxf.text.strip()))
                except Exception:
                    pass

        # Valores tipicos de linha: 122cm, 244cm, etc.
        linhas_v = []
        linhas_h = []
        if cota_nums:
            comp = result.get('comprimento', 0)
            larg = result.get('largura', 0)
            for v in sorted(set(cota_nums)):
                if 50 < v < comp:
                    linhas_v.append({'value': v, 'is_union': False})
                elif 50 < v < larg:
                    linhas_h.append({'value': v, 'is_union': False})

        result['linhas_verticais'] = linhas_v
        result['linhas_horizontais'] = linhas_h
        result['obstaculos'] = []
        result['modo_selecionado'] = 0
        result['unioes_nos_bordes'] = False
        result['observacoes'] = ''
        result['pontaletes'] = {}

        result['_confianca_extracao'] = 0.75 if best_poly else 0.35

    except Exception as ex:
        result['_extracao_erro'] = str(ex)
        result['_confianca_extracao'] = 0.3
    return result

def extrair_ficha_laje(
    recorte_path: str,
    elemento_id: str,
    obra_name: str | None = None,
    obra_root: str | Path | None = None,
) -> dict:
    obra_root_path = Path(obra_root) if obra_root else _infer_obra_root(recorte_path)
    if obra_name and obra_root_path is None:
        obra_root_path = DADOS_OBRAS_ROOT / obra_name
    fase4 = _lookup_fase4_laj(elemento_id, obra_root_path) if obra_root_path else None
    dxf_data = _extract_laj_from_dxf(recorte_path)
    dxf_conf = dxf_data.pop('_confianca_extracao', 0.4)
    dxf_data.pop('_extracao_erro', None)
    if fase4:
        result = dict(fase4)
        result['_er_meta'] = {'source': 'fase4', 'dxf_path': str(recorte_path), 'confianca': 0.95}
        result['_confianca'] = 0.95
    else:
        elem_num = re.sub(r'[^\d]', '', elemento_id)
        result = {
            'numero': int(elem_num) if elem_num else 0,
            'nome': elemento_id,
            'pavimento': 'Pavimento',
            **dxf_data,
        }
        result['_er_meta'] = {'source': 'dxf_extract', 'dxf_path': str(recorte_path), 'confianca': dxf_conf}
        result['_confianca'] = dxf_conf
    return result


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    elem = sys.argv[2] if len(sys.argv) > 2 else "L1"
    obra = sys.argv[3] if len(sys.argv) > 3 else None
    result = extrair_ficha_laje(path, elem, obra)
    print(json.dumps(result, indent=2, ensure_ascii=False))
