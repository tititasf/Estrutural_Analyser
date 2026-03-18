#!/usr/bin/env python3
"""
extrair_vigas_lv.py — Extrai comprimento e altura_lateral de vigas do LV DXF
via spatial proximity em layers "Cota Seção (2x)" e "COTA".

Story: CAD-5.2
Usage: python scripts/extrair_vigas_lv.py --obra PATH --pavimento "12 PAV"
"""
import argparse, json, math, re, sys
from pathlib import Path

# Filtro de referências cruzadas "VEM DA V{n}" — não são vigas reais do pavimento
_VEM_DA_VIGA = re.compile(r'VEM\s+DA\s+V\d+', re.IGNORECASE)

try:
    import ezdxf
except ImportError:
    print("ERROR: pip install ezdxf")
    sys.exit(1)


def dist2d(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _extract_viga_ids_from_text(txt, pos, viga_labels):
    """
    Extrai IDs de vigas de um texto e associa com posicao.

    Formatos suportados:
    - 'V4.A' ou 'V32A.B'  (simples com face)
    - '(VA2+V16+V17).A'   (composto entre parenteses com face)
    - 'V524-V727-V525.A'  (grupo dash/plus com face no ultimo elemento)
    - 'V40' ou 'V32'      (simples sem face — assume A+B)
    """
    # Formato composto: (V...).face — extrai todos IDs do grupo
    compound = re.match(r'\(([^)]+)\)\.([A-Z])', txt, re.IGNORECASE)
    if compound:
        face = compound.group(2).upper()
        inner = compound.group(1)
        vids_raw = re.findall(r'V(\d+[A-Z]?)', inner, re.IGNORECASE)
        for vid_raw in vids_raw:
            if len(vid_raw) > 4:
                continue
            vid = 'V' + vid_raw.upper()
            if vid not in viga_labels:
                viga_labels[vid] = {}
            if face not in viga_labels[vid]:
                viga_labels[vid][face] = pos
        return

    # Formato grupo dash/plus com face no ultimo: "V524-V727-V525-V728-V526.A"
    # Face aplica-se a todos os IDs da sequencia
    trailing_face = re.match(r'^(V\d+(?:[+\-]V\d+)+)\.([A-Z])$', txt.strip(), re.IGNORECASE)
    if trailing_face:
        face = trailing_face.group(2).upper()
        for num in re.findall(r'V(\d+)', trailing_face.group(1), re.IGNORECASE):
            if 1 <= len(num) <= 4:
                vid = 'V' + num.upper()
                if vid not in viga_labels:
                    viga_labels[vid] = {}
                if face not in viga_labels[vid]:
                    viga_labels[vid][face] = pos
        return

    # Formato simples com face: V4.A, V32A.B
    matches = re.findall(r'V(\d+[A-Z]?)\.([A-Z])', txt, re.IGNORECASE)
    for vid_raw, face in matches:
        if len(vid_raw) > 4:
            continue
        vid = 'V' + vid_raw.upper()
        if vid not in viga_labels:
            viga_labels[vid] = {}
        face = face.upper()
        if face not in viga_labels[vid]:
            viga_labels[vid][face] = pos

    # Formato simples sem face: V40 (assume ambas as faces)
    if not matches:
        m = re.match(r'^V(\d+[A-Z]?)$', txt.strip(), re.IGNORECASE)
        if m and len(m.group(1)) <= 4:
            vid = 'V' + m.group(1).upper()
            if vid not in viga_labels:
                viga_labels[vid] = {}
            for face in ('A', 'B'):
                if face not in viga_labels[vid]:
                    viga_labels[vid][face] = pos

    # Fallback: bare V{n} em qualquer posição (cobre "V601+V801", "V803-V804", etc.)
    if not compound and not matches and not re.match(r'^V(\d+[A-Z]?)$', txt.strip(), re.IGNORECASE):
        bare_ids = re.findall(r'\bV(\d+)\b', txt, re.IGNORECASE)
        for vid_raw in bare_ids:
            if 1 <= len(vid_raw) <= 4:
                vid = 'V' + vid_raw.upper()
                if vid not in viga_labels:
                    viga_labels[vid] = {}
                # Se a viga ja tem faces registradas (ex: NOMENCLATURA), nao adicionar
                # faces com posicao de label de grupo (caption/legenda) — posicoes erradas
                if viga_labels[vid]:
                    continue
                for face in ('A', 'B'):
                    if face not in viga_labels[vid]:
                        viga_labels[vid][face] = pos


def extract_viga_labels(msp, doc=None):
    """
    Extrai posicoes dos labels de vigas. Ordem de prioridade:

    1a. NOMENCLATURA: labels com face (V671.A), posicoes no detalhe estrutural
    1b. 'Texto Secao*': labels com face (V501.A), posicoes no detalhe estrutural
    1c. 'Texto' plain: labels de grupo (V501-V502-V503), area de legenda
    2.  Layer '5': labels simples (V501), fallback final
    3.  Block-scan CARIMBO: IDs confirmados em definicoes de bloco (nao MSP)
    4.  VEM DA recovery: adiciona vigas 'VEM DA' se confirmadas em bloco CARIMBO

    Ordem garante que posicoes de face-labels (proximas de COTAs) tenham
    prioridade sobre posicoes de group-labels (em legendas/cabecalhos distantes).
    """
    viga_labels = {}

    def _process_layer(layer_cond):
        for e in msp:
            if e.dxftype() not in ('TEXT', 'MTEXT'):
                continue
            if not layer_cond(e.dxf.layer):
                continue
            try:
                txt = e.plain_text().strip() if e.dxftype() == 'MTEXT' else e.dxf.text.strip()
                pos = (e.dxf.insert.x, e.dxf.insert.y)
            except Exception:
                continue
            if _VEM_DA_VIGA.search(txt):
                continue
            _extract_viga_ids_from_text(txt, pos, viga_labels)

    # 1a: NOMENCLATURA — face-specific labels, melhor posicao
    _process_layer(lambda lyr: 'NOMENCLATURA' in lyr.upper())

    # 1b: Layers tipo 'Texto Seção' — contêm face notation (.A/.B), boas posicoes
    # Inclui: 'Texto Seção', 'TEXTO SEÇÃO', 'Texto Se\xe7\xe3o', etc.
    # Exclui: 'TEXTO' exato (sem sufixo) e 'NOMENCLATURA'
    _process_layer(lambda lyr: ('TEXTO' in lyr.upper() and
                                lyr.upper() != 'TEXTO' and
                                'NOMENCLATURA' not in lyr.upper()))

    # 1c: 'TEXTO' plain — group labels ou simples (preenche gaps restantes)
    _process_layer(lambda lyr: lyr.upper() == 'TEXTO')

    # Estrategia 2 (fallback): layer '5' para obras com labels simples
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        if e.dxf.layer != '5':
            continue
        try:
            txt = e.plain_text().strip() if e.dxftype() == 'MTEXT' else e.dxf.text.strip()
            pos = (e.dxf.insert.x, e.dxf.insert.y)
        except Exception:
            continue
        # Excluir referências cruzadas "VEM DA V{n}"
        if _VEM_DA_VIGA.search(txt):
            continue
        # Apenas labels simples V{n} sem face (para nao conflitar com estrategia 1)
        m = re.match(r'^V(\d+[A-Z]?)$', txt.strip(), re.IGNORECASE)
        if m and len(m.group(1)) <= 4:
            vid = 'V' + m.group(1).upper()
            if vid not in viga_labels:  # nao sobrescreve estrategia 1
                viga_labels[vid] = {}
            for face in ('A', 'B'):
                if face not in viga_labels[vid]:
                    viga_labels[vid][face] = pos

    # Estrategia 3: Block-scan CARIMBO — coleta IDs confirmados em blocos nao-MSP
    # O parser streaming lê blocos; o ezdxf MSP não. Isso alinha extração com GT.
    confirmed_ids = set()
    if doc is not None:
        _msp_names = {'*Model_Space', '*Paper_Space', '*Model_Space_0'}
        for block in doc.blocks:
            if block.name in _msp_names or block.name.startswith('*'):
                continue
            for e in block:
                if e.dxftype() not in ('TEXT', 'MTEXT'):
                    continue
                if 'CARIMBO' not in e.dxf.layer.upper():
                    continue
                try:
                    txt = e.plain_text().strip() if e.dxftype() == 'MTEXT' else e.dxf.text.strip()
                except Exception:
                    continue
                if _VEM_DA_VIGA.search(txt):
                    continue
                for num in re.findall(r'\bV(\d+)\b', txt, re.IGNORECASE):
                    if 1 <= len(num) <= 4:
                        confirmed_ids.add('V' + num.upper())

        # Estrategia 4: VEM DA recovery — vigas so visíveis como "VEM DA" no MSP
        # Adiciona apenas IDs confirmados no bloco CARIMBO (evita alucinações)
        if confirmed_ids:
            for e in msp:
                if e.dxftype() not in ('TEXT', 'MTEXT'):
                    continue
                try:
                    txt = e.plain_text().strip() if e.dxftype() == 'MTEXT' else e.dxf.text.strip()
                    pos = (e.dxf.insert.x, e.dxf.insert.y)
                except Exception:
                    continue
                if not _VEM_DA_VIGA.search(txt):
                    continue
                # Extrai ID após "VEM DA " e adiciona se confirmado
                clean = re.sub(r'VEM\s+DA\s+', '', txt, flags=re.IGNORECASE).strip()
                temp = {}
                _extract_viga_ids_from_text(clean, pos, temp)
                for vid, faces in temp.items():
                    if vid not in confirmed_ids:
                        continue
                    if vid not in viga_labels:
                        viga_labels[vid] = {}
                    for face, fpos in faces.items():
                        if face not in viga_labels[vid]:
                            viga_labels[vid][face] = fpos

    return viga_labels


def extract_secao_dims(msp):
    """Extrai DIMENSIONs do layer Cota Seção (2x) — altura_lateral das vigas."""
    dims = []
    for e in msp:
        if e.dxftype() != 'DIMENSION':
            continue
        lyr_upper = e.dxf.layer.upper()
        if 'COTA SE' not in lyr_upper or '2X' not in lyr_upper:
            continue
        try:
            val = round(abs(e.get_measurement()), 1)
            defpt = e.dxf.defpoint
            dims.append({'val': val, 'center': (defpt.x, defpt.y)})
        except Exception:
            continue
    return dims


def extract_cota_dims(msp):
    """Extrai DIMENSIONs do layer COTA — comprimento total das vigas."""
    dims = []
    for e in msp:
        if e.dxftype() != 'DIMENSION':
            continue
        if e.dxf.layer != 'COTA':
            continue
        try:
            val = round(abs(e.get_measurement()), 1)
            defpt = e.dxf.defpoint
            dims.append({'val': val, 'center': (defpt.x, defpt.y)})
        except Exception:
            continue
    return dims


def find_altura_lateral(label_pos, secao_dims):
    """Encontra altura_lateral da viga (DIMENSION mais próxima em Cota Seção 2x)."""
    if not secao_dims:
        return None, None, None
    with_dist = sorted([(dist2d(label_pos, d['center']), d) for d in secao_dims],
                       key=lambda x: x[0])
    nearest_dist, nearest = with_dist[0]
    val = nearest['val']
    # Filtro: 20-400cm válido para altura lateral de viga
    if val < 20 or val > 400:
        # Procura próxima no range válido
        for d, dim in with_dist[1:]:
            if 20 <= dim['val'] <= 400:
                nearest_dist, val = d, dim['val']
                break
        else:
            return None, None, None

    if nearest_dist < 500:
        conf = 0.90
    elif nearest_dist < 1500:
        conf = 0.80
    elif nearest_dist < 3000:
        conf = 0.65
    else:
        conf = 0.50

    return val, conf, nearest_dist


def find_comprimento(face_pos, cota_dims, radius=800, min_val=100):
    """Encontra comprimento da viga: maior COTA >= min_val dentro do raio."""
    large = [(dist2d(face_pos, d['center']), d['val'])
             for d in cota_dims if d['val'] >= min_val]
    within = [(d, v) for d, v in large if d <= radius]
    if not within:
        # Fallback: estender raio para 1500
        within = [(d, v) for d, v in large if d <= 1500]
        if not within:
            return None, None, None, 'no_cota_found'
        source = 'fallback_radius_1500'
    else:
        source = 'inverse_proximity'

    max_val = max(v for d, v in within)
    max_dist = next(d for d, v in within if v == max_val)

    if max_dist < 500:
        conf = 0.88
    elif max_dist < 800:
        conf = 0.78
    elif max_dist < 1200:
        conf = 0.65
    else:
        conf = 0.50

    return max_val, conf, max_dist, source


def extract_vigas(dxf_path):
    """Pipeline principal de extração."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    viga_labels = extract_viga_labels(msp, doc)
    secao_dims = extract_secao_dims(msp)
    cota_dims = extract_cota_dims(msp)

    print(f"  Labels encontrados: {len(viga_labels)} vigas")
    print(f"  Cota Seção (2x): {len(secao_dims)} dims")
    print(f"  COTA: {len(cota_dims)} dims")

    results = {}
    for vid in sorted(viga_labels.keys(), key=lambda x: (len(x), x)):
        faces = viga_labels[vid]
        result = {
            'id': vid,
            'sides': sorted(faces.keys()),
            'altura_lateral_cm': None,
            'altura_conf': None,
            'comprimento_cm': None,
            'comprimento_conf': None,
            'comprimento_source': None,
            'confidence': None,
        }

        # --- Altura Lateral ---
        # Usa o label de face A preferencialmente, senão B
        face_for_altura = faces.get('A') or faces.get('B') or (list(faces.values())[0] if faces else None)
        if face_for_altura:
            alt, alt_conf, alt_dist = find_altura_lateral(face_for_altura, secao_dims)
        else:
            alt, alt_conf = None, None
        result['altura_lateral_cm'] = alt
        result['altura_conf'] = alt_conf

        # --- Comprimento ---
        # Usa posição da face A (ou disponível) como âncora
        face_for_comp = faces.get('A') or faces.get('B') or (list(faces.values())[0] if faces else None)
        if face_for_comp:
            comp, comp_conf, comp_dist, comp_src = find_comprimento(face_for_comp, cota_dims)
        else:
            comp, comp_conf, comp_dist, comp_src = None, None, None, 'no_position'
        result['comprimento_cm'] = comp
        result['comprimento_conf'] = comp_conf
        result['comprimento_source'] = comp_src

        # Confiança geral
        confs = [c for c in [alt_conf, comp_conf] if c is not None]
        result['confidence'] = round(sum(confs) / len(confs), 2) if confs else 0.0

        results[vid] = result

    return results


def _dxf_from_discovery(obra_path, pavimento, tipo):
    """Busca caminho DXF no dxf_discovery.json por obra/pavimento/tipo.

    Tenta match exato; se falhar, tenta sufixo e containment
    (ex: 'TIPO 14 AO 17 PAV' casa com 'RES.DIAMOND - TORRE 1 - TIPO 14 AO 17 PAV').
    """
    import json as _json
    obra = Path(obra_path)
    disc = obra.parent / "dxf_discovery.json"
    if not disc.exists():
        return None
    try:
        with open(disc, encoding='utf-8') as f:
            d = _json.load(f)
        obra_data = d.get(obra.name, {})
        # 1) Exact match
        pav_data = obra_data.get(pavimento, {})
        # 2) Suffix match
        if not pav_data:
            pav_upper = pavimento.upper()
            for key, val in obra_data.items():
                if key.upper().endswith(pav_upper):
                    pav_data = val
                    break
        # 3) Contains match
        if not pav_data:
            for key, val in obra_data.items():
                if pav_upper in key.upper():
                    pav_data = val
                    break
        p = pav_data.get(tipo)
        return Path(p) if p else None
    except Exception:
        return None


def find_lv_dxf(obra_path, pavimento):
    """Localiza o arquivo LV DXF para o pavimento especificado."""
    # Discovery JSON primeiro (mais preciso)
    disc_path = _dxf_from_discovery(obra_path, pavimento, 'LV')
    if disc_path and disc_path.exists():
        return [disc_path]

    fase1 = Path(obra_path) / 'Fase-1_Ingestao' / 'Projetos_Finalizados_para_Engenharia_Reversa'
    dxfs = list(fase1.glob('*.dxf')) + list(fase1.glob('*.DXF'))
    # Filtro: LV e pavimento (12 = "12")
    pav_num = re.search(r'\d+', pavimento)
    pav_num = pav_num.group() if pav_num else pavimento

    candidates = [f for f in dxfs if 'LV' in f.name.upper() and pav_num in f.name]
    # Deduplicate
    seen, unique = set(), []
    for f in candidates:
        if f.name not in seen:
            seen.add(f.name)
            unique.append(f)
    return unique


def main():
    parser = argparse.ArgumentParser(description='Extrair dimensões de vigas do LV DXF')
    parser.add_argument('--obra', required=True, help='Path da obra (ex: ../DADOS-OBRAS/Obra_TREINO_21)')
    parser.add_argument('--pavimento', default='12 PAV', help='Pavimento (ex: 12 PAV)')
    parser.add_argument('--output', default=None, help='Path do output JSON')
    args = parser.parse_args()

    obra_path = Path(args.obra)
    dxf_files = find_lv_dxf(obra_path, args.pavimento)

    if not dxf_files:
        print(f"ERRO: Nenhum LV DXF encontrado para pavimento '{args.pavimento}' em {obra_path}")
        sys.exit(1)

    dxf_path = dxf_files[0]
    print(f"DXF: {dxf_path.name}")

    results = extract_vigas(dxf_path)

    # Output path
    if args.output:
        out_path = Path(args.output)
    else:
        out_dir = obra_path / 'Fase-3_Interpretacao_Extracao' / 'Vigas'
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / 'vigas_dim.json'

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Resumo
    total = len(results)
    com_alt = sum(1 for v in results.values() if v['altura_lateral_cm'] is not None)
    com_comp = sum(1 for v in results.values() if v['comprimento_cm'] is not None)
    com_ambos = sum(1 for v in results.values() if v['altura_lateral_cm'] and v['comprimento_cm'])
    avg_conf = sum(v['confidence'] for v in results.values()) / total if total else 0

    print(f"\n=== RESULTADO ===")
    print(f"  Total vigas: {total}")
    print(f"  Com altura_lateral: {com_alt}/{total}")
    print(f"  Com comprimento: {com_comp}/{total}")
    print(f"  Com ambos: {com_ambos}/{total}")
    print(f"  Confiança média: {avg_conf:.0%}")
    print(f"  Output: {out_path}")
    print()
    print(f"{'Viga':<8} {'Alt(cm)':<10} {'Comp(cm)':<12} {'Conf':<8} {'Sides'}")
    print("-" * 55)
    for vid, v in sorted(results.items(), key=lambda x: (len(x[0]), x[0])):
        alt = f"{v['altura_lateral_cm']:.0f}" if v['altura_lateral_cm'] else "None"
        comp = f"{v['comprimento_cm']:.0f}" if v['comprimento_cm'] else "None"
        conf = f"{v['confidence']:.0%}" if v['confidence'] else "0%"
        sides = '+'.join(v['sides'])
        print(f"{vid:<8} {alt:<10} {comp:<12} {conf:<8} {sides}")


if __name__ == '__main__':
    main()
