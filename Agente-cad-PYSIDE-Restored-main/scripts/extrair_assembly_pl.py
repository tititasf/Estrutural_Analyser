"""
extrair_assembly_pl.py — Extrai dados de montagem do DXF PL (CAD-7.x)
======================================================================
Extrai por pilar:
  - grade_1, grade_2: dimensoes de grade (COTA GRADE annotations)
  - chapa_vert: count de chapas verticais (paineis laterais)
  - chapa_horiz: count de chapas horizontais (conectores)
  - sp_per_face: count de marcadores SP (Screw Points) por face
  - perfil_metalico: count de Perfil Metalico por secao

Uso:
  python scripts/extrair_assembly_pl.py --obra DADOS-OBRAS/Obra_TREINO_21

Input:  Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa/*.dxf (PL)
Output: Fase-3_Interpretacao_Extracao/Pilares/pilares_assembly.json
"""

import os
import sys
import re
import math
import json
import logging
import argparse
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("extrair_assembly_pl")

try:
    import ezdxf
except ImportError:
    print("[ERRO] ezdxf nao instalado. Execute: pip install ezdxf")
    sys.exit(1)

# ===========================================================================
# PARAMETROS
# ===========================================================================
FACE_RADIUS = 700       # raio para associar entidade a face do pilar (cm)
CHAPA_VERT_MAX_W = 10   # w <= 10 = placa vertical (chapa lateral)
CHAPA_HORIZ_MAX_H = 10  # h <= 10 = placa horizontal (conector/grade)
GRADE_KEYWORDS = ["GRADE", "GRADE)"]


def clean_mtext(raw: str) -> str:
    """Remove codigos MTEXT e retorna texto puro."""
    if not raw:
        return ""
    # Remove grupos {...}
    clean = re.sub(r'\{[^}]*\}', '', raw)
    # Remove sequencias \\codigo;
    clean = re.sub(r'\\[^;\\]+;', '', clean)
    # Remove \P (paragraph) e whitespace
    clean = clean.replace('\\P', '\n').strip()
    return clean.split('\n')[0].strip()


def get_insert_xy(e):
    """Retorna (x, y) do ponto de insercao da entidade."""
    if hasattr(e.dxf, 'insert'):
        return (float(e.dxf.insert[0]), float(e.dxf.insert[1]))
    if hasattr(e.dxf, 'defpoint'):
        return (float(e.dxf.defpoint[0]), float(e.dxf.defpoint[1]))
    if hasattr(e.dxf, 'start'):
        return (float(e.dxf.start[0]), float(e.dxf.start[1]))
    return None


def find_pl_dxf(obra_path: Path, pav_hint: str = "12") -> Path | None:
    """Encontra o DXF PL do pavimento solicitado."""
    fase1 = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    if not fase1.exists():
        log.error(f"Pasta Fase-1 nao encontrada: {fase1}")
        return None

    # Preferencia: arquivo especifico do pavimento
    candidates = []
    for f in fase1.iterdir():
        if f.suffix.lower() != '.dxf':
            continue
        fname = f.name.upper()
        if '- PL -' not in fname and '- PL.' not in fname:
            continue
        candidates.append(f)

    if not candidates:
        log.error("Nenhum DXF PL encontrado")
        return None

    # Priorizar por pav_hint
    for f in candidates:
        if pav_hint in f.name:
            return f

    # Fallback: primeiro disponivel
    return candidates[0]


def extract_pilar_labels(msp) -> dict:
    """
    Extrai posicoes das labels de face: P{n}.{face} ou P{n}.{face}-P{m}.{face}
    Returns: {pilar_num: {face: (x, y)}}
    """
    pilar_faces = defaultdict(dict)

    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            if e.dxftype() == 'MTEXT':
                raw = e.text
                txt = clean_mtext(raw)
            else:
                txt = e.dxf.text.strip()
        except Exception:
            continue

        xy = get_insert_xy(e)
        if not xy:
            continue

        # P{n}.{face}
        m = re.match(r'^P(\d+)[.\-]([A-F])$', txt)
        if m:
            pilar_faces[int(m.group(1))][m.group(2)] = xy
            continue

        # P{n}.{face}-P{m}.{face}
        m2 = re.match(r'^P(\d+)\.([A-F])-P\d+\.([A-F])$', txt)
        if m2:
            pilar_faces[int(m2.group(1))][m2.group(2)] = xy
            continue

    return dict(pilar_faces)


def extract_chapa_entities(msp) -> list:
    """
    Extrai entidades CHAPA LWPOLYLINE com bbox.
    Returns: [(cx, cy, w, h)]
    """
    result = []
    for e in msp:
        if e.dxftype() != 'LWPOLYLINE':
            continue
        if e.dxf.layer != 'CHAPA':
            continue
        try:
            pts = list(e.get_points())
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            cx = (max(xs) + min(xs)) / 2
            cy = (max(ys) + min(ys)) / 2
            w = round(max(xs) - min(xs), 1)
            h = round(max(ys) - min(ys), 1)
            result.append((cx, cy, w, h))
        except Exception:
            pass
    return result


def extract_perfil_entities(msp) -> list:
    """Extrai Perfil Metalico LWPOLYLINE."""
    result = []
    for e in msp:
        if e.dxftype() != 'LWPOLYLINE':
            continue
        if 'Perfil' not in e.dxf.layer and 'PERFIL' not in e.dxf.layer.upper():
            continue
        try:
            pts = list(e.get_points())
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            cx = (max(xs) + min(xs)) / 2
            cy = (max(ys) + min(ys)) / 2
            w = round(max(xs) - min(xs), 1)
            h = round(max(ys) - min(ys), 1)
            result.append((cx, cy, w, h))
        except Exception:
            pass
    return result


def extract_sp_annotations(msp) -> list:
    """
    Extrai marcadores SP (Screw Points) do layer 'texto'.
    SP = '{\\fTahoma|...;\\C4;SP}' ou similar.
    Returns: [(x, y)]
    """
    result = []
    for e in msp:
        if e.dxftype() != 'MTEXT':
            continue
        try:
            raw = e.text
            # Detectar pelo padrao: raw termina com ';SP}'
            if ';SP}' in raw or raw.endswith(';SP}'):
                xy = get_insert_xy(e)
                if xy:
                    result.append(xy)
        except Exception:
            pass
    return result


def extract_grade_annotations(msp) -> list:
    """
    Extrai anotacoes de GRADE dos layers COTA e 'Cota Secao (2x)'.
    Returns: [(x, y, grade_value)]
    """
    result = []
    for e in msp:
        if e.dxftype() != 'DIMENSION':
            continue
        override = getattr(e.dxf, 'text', '') or ''
        is_grade = any(kw in override.upper() for kw in GRADE_KEYWORDS)
        if not is_grade:
            continue
        meas = getattr(e.dxf, 'actual_measurement', None)
        if meas is None:
            continue
        try:
            meas_val = round(float(meas), 1)
        except Exception:
            continue
        if meas_val <= 0:
            continue
        # Get position
        try:
            mx = float(e.dxf.text_midpoint[0])
            my = float(e.dxf.text_midpoint[1])
        except Exception:
            try:
                mx = float(e.dxf.defpoint[0])
                my = float(e.dxf.defpoint[1])
            except Exception:
                continue
        result.append((mx, my, meas_val))
    return result


def assign_to_pilar(pilar_faces: dict, entities: list, radius: float) -> dict:
    """
    Para cada pilar, conta entidades dentro do raio de qualquer face.
    Returns: {pilar_num: count}
    """
    result = {}
    for pnum, faces in pilar_faces.items():
        count = 0
        seen = set()
        for face, (px, py) in faces.items():
            for i, ent in enumerate(entities):
                if i in seen:
                    continue
                ex, ey = ent[0], ent[1]
                if math.dist((px, py), (ex, ey)) <= radius:
                    seen.add(i)
                    count += 1
        result[pnum] = count
    return result


def assign_chapa_per_pilar(pilar_faces: dict, chapa_ents: list, radius: float) -> dict:
    """
    Clasifica CHAPA por tipo e conta por pilar.
    Deduplica pares identicos (DXF duplica cada CHAPA).
    Returns: {pilar_num: {'vert': n, 'horiz': n, 'total_unique': n}}
    """
    result = {}
    for pnum, faces in pilar_faces.items():
        seen = set()  # (round(cx), round(cy), w, h)
        vert = 0
        horiz = 0
        for face, (px, py) in faces.items():
            for cx, cy, w, h in chapa_ents:
                if math.dist((px, py), (cx, cy)) <= radius:
                    key = (round(cx, 0), round(cy, 0), w, h)
                    if key not in seen:
                        seen.add(key)
                        if w <= CHAPA_VERT_MAX_W and h > CHAPA_HORIZ_MAX_H:
                            vert += 1
                        elif h <= CHAPA_HORIZ_MAX_H and w > CHAPA_VERT_MAX_W:
                            horiz += 1
        result[pnum] = {
            "chapa_vert": vert,
            "chapa_horiz": horiz,
            "chapa_total": vert + horiz
        }
    return result


def assign_sp_per_face(pilar_faces: dict, sp_positions: list, radius: float) -> dict:
    """
    Conta SP por face do pilar.
    Returns: {pilar_num: {face: sp_count}}
    """
    result = {}
    for pnum, faces in pilar_faces.items():
        face_sp = {}
        for face, (px, py) in faces.items():
            cnt = sum(1 for sx, sy in sp_positions
                      if math.dist((px, py), (sx, sy)) <= radius)
            face_sp[face] = cnt
        result[pnum] = face_sp
    return result


def assign_grades_per_pilar(pilar_faces: dict, grade_annotations: list, radius: float) -> dict:
    """
    Extrai grade_1 e grade_2 por pilar usando nearest-pilar assignment.
    Cada anotacao GRADE e atribuida ao pilar mais proximo (previne cross-contaminacao).
    Returns: {pilar_num: {'grade_1': val, 'grade_2': val or None}}
    """
    # Build flat list of (pnum, face, px, py) for all pilar faces
    all_faces = []
    for pnum, faces in pilar_faces.items():
        for face, (px, py) in faces.items():
            all_faces.append((pnum, face, px, py))

    # Per-pilar grade accumulator
    pilar_grades = defaultdict(set)

    for gx, gy, gval in grade_annotations:
        if not all_faces:
            continue
        # Find nearest pilar face
        best_dist = float('inf')
        best_pnum = None
        for pnum, face, px, py in all_faces:
            d = math.dist((gx, gy), (px, py))
            if d < best_dist:
                best_dist = d
                best_pnum = pnum
        # Only assign if within radius
        if best_pnum is not None and best_dist <= radius:
            pilar_grades[best_pnum].add(round(gval, 1))

    # Fallback: pilares sem grade → buscar mais proximo dentro de radius*2
    FALLBACK_RADIUS = radius * 2
    for pnum, faces in pilar_faces.items():
        if pnum not in pilar_grades or not pilar_grades[pnum]:
            best_gval = None
            best_gdist = float('inf')
            for face, (px, py) in faces.items():
                for gx, gy, gval in grade_annotations:
                    d = math.dist((gx, gy), (px, py))
                    if d < best_gdist and d <= FALLBACK_RADIUS:
                        best_gdist = d
                        best_gval = round(gval, 1)
            if best_gval is not None:
                pilar_grades[pnum] = {best_gval}

    result = {}
    for pnum in pilar_faces:
        grades_unique = sorted(pilar_grades.get(pnum, set()), reverse=True)
        source = "cota-grade-nearest" if grades_unique else "no-grade"
        if grades_unique and pnum not in [p for p, g in pilar_grades.items() if g]:
            source = "cota-grade-fallback"
        result[pnum] = {
            "grade_1": grades_unique[0] if len(grades_unique) >= 1 else None,
            "grade_2": grades_unique[1] if len(grades_unique) >= 2 else None,
            "grade_count": len(grades_unique),
            "source": source
        }
    return result


def process_pl_dxf(dxf_path: Path) -> dict:
    """
    Processa o PL DXF e retorna dados de assembly por pilar.
    """
    log.info(f"Lendo: {dxf_path.name}")
    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception as e:
        log.error(f"Erro ao ler DXF: {e}")
        return {}

    msp = doc.modelspace()

    # 1. Extrair labels dos pilares
    pilar_faces = extract_pilar_labels(msp)
    log.info(f"Pilares encontrados (secoes): {len(pilar_faces)}")

    if not pilar_faces:
        log.warning("Nenhum pilar encontrado no DXF PL")
        return {}

    # 2. Extrair entidades
    chapa_ents = extract_chapa_entities(msp)
    perfil_ents = extract_perfil_entities(msp)
    sp_positions = extract_sp_annotations(msp)
    grade_anns = extract_grade_annotations(msp)

    log.info(f"CHAPA: {len(chapa_ents)} | Perfil: {len(perfil_ents)} | SP: {len(sp_positions)} | GRADE: {len(grade_anns)}")

    # 3. Associar por pilar
    chapa_per_pilar = assign_chapa_per_pilar(pilar_faces, chapa_ents, FACE_RADIUS)
    perfil_per_pilar = assign_to_pilar(pilar_faces, perfil_ents, FACE_RADIUS)
    sp_per_face = assign_sp_per_face(pilar_faces, sp_positions, FACE_RADIUS)
    grades_per_pilar = assign_grades_per_pilar(pilar_faces, grade_anns, FACE_RADIUS * 1.5)

    # 4. Consolidar
    assembly = {}
    for pnum in sorted(pilar_faces.keys()):
        pilar_id = f"P{pnum}"
        chapa = chapa_per_pilar.get(pnum, {})
        grades = grades_per_pilar.get(pnum, {})
        sp_faces = sp_per_face.get(pnum, {})
        perfil_count = perfil_per_pilar.get(pnum, 0)

        assembly[pilar_id] = {
            "pilar": pilar_id,
            "faces_found": list(pilar_faces[pnum].keys()),
            # Chapas
            "chapa_vert": chapa.get("chapa_vert", 0),
            "chapa_horiz": chapa.get("chapa_horiz", 0),
            "chapa_total": chapa.get("chapa_total", 0),
            # Grades
            "grade_1": grades.get("grade_1"),
            "grade_2": grades.get("grade_2"),
            "grade_source": grades.get("source", ""),
            # Perfil Metalico
            "perfil_metalico": perfil_count,
            # SP markers per face
            "sp_per_face": sp_faces,
            "sp_total": sum(sp_faces.values()),
            # Confidence
            "confidence": 0.85 if grades.get("grade_1") else 0.60
        }

    return assembly


def main():
    parser = argparse.ArgumentParser(description="Extrai dados de assembly do DXF PL")
    parser.add_argument("--obra", required=True, help="Path da obra (ex: DADOS-OBRAS/Obra_TREINO_21)")
    parser.add_argument("--pav", default="12", help="Hint do pavimento para selecao do DXF (default: 12)")
    parser.add_argument("--output", default=None, help="Path alternativo para output JSON")
    parser.add_argument("--pavimento", default=None, help="Pavimento (alias para --pav, ignorado aqui)")
    args, _ = parser.parse_known_args()

    obra_path = Path(args.obra)
    if not obra_path.exists():
        log.error(f"Obra nao encontrada: {obra_path}")
        sys.exit(1)

    # Output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_dir = obra_path / "Fase-3_Interpretacao_Extracao" / "Pilares"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "pilares_assembly.json"

    # Encontrar DXF PL
    dxf_path = find_pl_dxf(obra_path, args.pav)
    if not dxf_path:
        log.error("DXF PL nao encontrado")
        sys.exit(1)

    log.info(f"DXF PL: {dxf_path.name}")

    # Processar
    assembly = process_pl_dxf(dxf_path)

    if not assembly:
        log.error("Nenhum dado extraido")
        sys.exit(1)

    # Salvar
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(assembly, f, indent=2, ensure_ascii=False)

    log.info(f"Output: {output_path}")
    log.info(f"Pilares processados: {len(assembly)}")

    # Resumo
    has_grade = sum(1 for v in assembly.values() if v.get("grade_1"))
    has_chapa = sum(1 for v in assembly.values() if v.get("chapa_total", 0) > 0)
    has_sp = sum(1 for v in assembly.values() if v.get("sp_total", 0) > 0)

    print("\n=== RESUMO ===")
    print(f"Pilares: {len(assembly)}")
    print(f"Com grade_1: {has_grade}/{len(assembly)}")
    print(f"Com CHAPA: {has_chapa}/{len(assembly)}")
    print(f"Com SP markers: {has_sp}/{len(assembly)}")

    # Sample
    sample_keys = list(assembly.keys())[:3]
    for k in sample_keys:
        v = assembly[k]
        print(f"  {k}: grade_1={v.get('grade_1')} chapa_total={v.get('chapa_total')} sp={v.get('sp_total')} perf={v.get('perfil_metalico')}")


if __name__ == "__main__":
    main()
