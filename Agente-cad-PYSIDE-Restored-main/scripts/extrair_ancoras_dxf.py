#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrair_ancoras_dxf.py — Extrai coordenadas absolutas (âncoras) de cada
elemento (P{n}, V{n}, L{n}) nos DXFs STOG originais.

Essas âncoras são necessárias para montar o DXF coletivo (Epic 9) posicionando
cada elemento gerado individualmente na posição correta do pavimento.

Usa parser streaming (sem ezdxf) para suportar DXFs grandes (650MB+) sem OOM.

Saída:
  Fase-3_Interpretacao_Extracao/ancoras_pilares.json
  Fase-3_Interpretacao_Extracao/ancoras_vigas.json
  Fase-3_Interpretacao_Extracao/ancoras_lajes.json

CLI:
  python scripts/extrair_ancoras_dxf.py --obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV"
  python scripts/extrair_ancoras_dxf.py --obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV" --dxf-discovery DADOS-OBRAS/dxf_discovery.json
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def _stream_text_entities(dxf_path) -> list:
    """
    Parser streaming de DXF: lê TEXT/MTEXT sem carregar arquivo inteiro.
    Usa ~1% da RAM do ezdxf. Suporta ASCII, CP1252 e UTF-8.
    Retorna lista de dicts com keys: type, layer, text, x, y.
    """
    WANT_TYPES = {'TEXT', 'MTEXT'}
    results = []

    for encoding in ('utf-8', 'cp1252', 'latin-1'):
        try:
            with open(dxf_path, 'r', encoding=encoding, errors='replace') as fh:
                lines = fh.readlines()
            break
        except Exception:
            continue
    else:
        return results

    i = 0
    n = len(lines)
    while i < n:
        code = lines[i].strip()
        if code == '0' and i + 1 < n:
            etype = lines[i + 1].strip().upper()
            if etype in WANT_TYPES:
                entity = {'type': etype, 'layer': '0', 'text': '', 'x': None, 'y': None}
                i += 2
                while i < n:
                    c = lines[i].strip()
                    if c == '0':
                        break
                    val = lines[i + 1].strip() if i + 1 < n else ''
                    if c == '8':
                        entity['layer'] = val
                    elif c == '1':
                        entity['text'] = val.replace('\\P', '\n').replace('\\p', '\n')
                    elif c == '10' and entity['x'] is None:
                        try:
                            entity['x'] = float(val)
                        except ValueError:
                            pass
                    elif c == '20' and entity['y'] is None:
                        try:
                            entity['y'] = float(val)
                        except ValueError:
                            pass
                    i += 2
                results.append(entity)
                continue
        i += 1

    return results


def centroid(pts: list) -> list:
    """Calcula centróide de lista de pontos (x, y)."""
    n = len(pts)
    return [round(sum(p[0] for p in pts) / n, 2),
            round(sum(p[1] for p in pts) / n, 2)]


# ─────────────────────────────────────────────
# PILARES — layer "Texto Seção" → textos "P{n}.*"
# ─────────────────────────────────────────────

def extrair_ancoras_pilares(pl_dxf_path: str) -> dict:
    """
    Extrai âncoras dos pilares do DXF PL via parser streaming (sem ezdxf).

    Layer "Texto Seção" contém textos como:
      "P1.A", "P1.B", "P1.C", "P1.D"   ← faces de P1
      "P9.A", "P9.B", ...
      "P106.A-P107.A-P108.A"            ← agrupados

    Âncora = centróide de todos os textos do mesmo pilar.

    Retorna: {"P1": [x, y], "P9": [x, y], ...}
    """
    entities = _stream_text_entities(pl_dxf_path)
    grupos: dict = defaultdict(list)

    for ent in entities:
        if ent['type'] not in ('TEXT', 'MTEXT'):
            continue

        txt = ent['text'].strip()
        if not txt:
            continue

        # Extrair TODOS os IDs P{n} do texto (simples ou agrupados)
        all_pids = re.findall(r'P(\d+)', txt, re.IGNORECASE)
        if not all_pids:
            continue

        if ent['x'] is not None and ent['y'] is not None:
            xy = (ent['x'], ent['y'])
            for num in all_pids:
                pid = f"P{num}"
                grupos[pid].append(xy)

    ancoras = {pid: centroid(pts) for pid, pts in grupos.items() if pts}

    print(f"[INFO] Pilares: {len(ancoras)} ancoras extraidas do PL DXF")
    return ancoras


# ─────────────────────────────────────────────
# VIGAS — layer "Texto Seção" → textos "V{n}.A" / "V{n}.B"
# ─────────────────────────────────────────────

def _parse_viga_label(txt: str) -> list:
    """
    Parseia labels de viga, incluindo combinados e bare labels.
    Retorna lista de (vid, face) tuples.

    Exemplos:
      "V1.A"          → [("V1", "A")]
      "V1.B"          → [("V1", "B")]
      "V17.A+V18.A"   → [("V17", "A"), ("V18", "A")]
      "V24.A-V24.B"   → [("V24", "A"), ("V24", "B")]
      "V25.A+V26.A"   → [("V25", "A"), ("V26", "A")]
      "V32A.A"        → [("V32A", "A")]
      "V212"          → [("V212", "A"), ("V212", "B")]  ← bare label (TREINO_23)
    """
    txt = txt.strip()
    results = []

    # Separar tokens por '+' ou '-' (separadores de combinados)
    tokens = re.split(r'[+\-]', txt)
    for token in tokens:
        token = token.strip()
        # Padrão com face: V{n|n+letra}.{face}
        m = re.match(r'^V(\d+[A-Z]?)[.\s]+([AB])$', token, re.IGNORECASE)
        if m:
            vid = f"V{m.group(1).upper()}"
            face = m.group(2).upper()
            results.append((vid, face))
            continue
        # Bare label sem face: V{n} (ex: TREINO_23 layer '5')
        # Usar primeira "palavra" para ignorar sufixo de dimensão (ex: "V201\n(14x50)")
        first = token.split()[0] if token.split() else token
        m2 = re.match(r'^V(\d+[A-Z]?)$', first, re.IGNORECASE)
        if m2:
            vid = f"V{m2.group(1).upper()}"
            results.append((vid, 'A'))
            results.append((vid, 'B'))

    return results


def extrair_ancoras_vigas(lv_dxf_path: str) -> dict:
    """
    Extrai âncoras das vigas do DXF LV via parser streaming (sem ezdxf).

    Layer "Texto Seção" contém textos:
      Simples: "V1.A", "V1.B"
      Combinados: "V17.A+V18.A", "V24.A-V24.B", "V25.A+V26.A"

    Âncora = centróide de todos os textos da mesma viga/face.

    Retorna: {"V1": {"A": [x, y], "B": [x, y]}, ...}
    """
    entities = _stream_text_entities(lv_dxf_path)
    grupos: dict = defaultdict(lambda: defaultdict(list))

    for ent in entities:
        if ent['type'] not in ('TEXT', 'MTEXT'):
            continue

        layer = ent['layer'].lower()
        if 'texto' not in layer and 'seção' not in layer and 'secao' not in layer:
            if layer not in ('5', '4', '6'):
                continue

        txt = ent['text'].strip()
        if not txt or not re.match(r'^V\d+', txt, re.IGNORECASE):
            continue

        parsed = _parse_viga_label(txt)
        if not parsed:
            continue

        if ent['x'] is not None and ent['y'] is not None:
            xy = (ent['x'], ent['y'])
            for vid, face in parsed:
                grupos[vid][face].append(xy)

    ancoras = {}
    for vid in sorted(grupos.keys(), key=lambda x: (int(re.search(r'\d+', x).group()), x)):
        ancoras[vid] = {}
        for face in ('A', 'B'):
            pts = grupos[vid].get(face, [])
            if pts:
                ancoras[vid][face] = centroid(pts)
            else:
                ancoras[vid][face] = None

    print(f"[INFO] Vigas: {len(ancoras)} ancoras extraidas do LV DXF")
    return ancoras


# ─────────────────────────────────────────────
# LAJES — layer "AUX00" → MTEXT "L{n}\n{dim1}X{dim2}"
# ─────────────────────────────────────────────

def extrair_ancoras_lajes(lj_dxf_path: str) -> dict:
    """
    Extrai âncoras das lajes do DXF LJ via parser streaming (sem ezdxf).

    Layers com labels de laje:
      - "AUX00", "4", "10", "44", "226": MTEXT/TEXT "L{n}\n..." ou "L{n}"
      - Qualquer layer com "LAJE" ou "AUX" no nome

    Âncora = centróide de todos os textos do mesmo L{n}.

    Retorna: {"L1": [x, y], "L2": [x, y], ...}
    """
    entities = _stream_text_entities(lj_dxf_path)

    LAYERS_ACEITAVEIS = {'AUX00', '4', '10', '44', '226', 'LAJES', 'LAJE', 'TEXT', 'TEXTO',
                         'L-N', 'NOME LAJE', 'ES-LAJE-NOME', 'A-FLOR-IDEN', 'F-LAJES-NOME'}

    grupos: dict = defaultdict(list)

    for ent in entities:
        if ent['type'] not in ('TEXT', 'MTEXT'):
            continue

        layer = ent['layer'].upper().strip()
        if layer not in LAYERS_ACEITAVEIS and 'LAJE' not in layer and 'AUX' not in layer:
            continue

        txt = ent['text'].strip()
        if not txt:
            continue

        # Extrair L{n} da primeira linha
        txt_first = re.split(r'[\n\^]', txt)[0].strip()
        m = re.match(r'^L(\d+)$', txt_first, re.IGNORECASE)
        if not m:
            continue

        lid = f"L{m.group(1)}"
        if ent['x'] is not None and ent['y'] is not None:
            grupos[lid].append((ent['x'], ent['y']))

    ancoras = {}
    for lid in sorted(grupos.keys(), key=lambda x: int(x[1:])):
        pts = grupos[lid]
        if pts:
            ancoras[lid] = centroid(pts)

    print(f"[INFO] Lajes: {len(ancoras)} ancoras extraidas do LJ DXF")
    return ancoras


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def load_dxf_path(obra_path: Path, pavimento: str, tipo: str,
                  discovery_path: Path = None) -> str:
    """Localiza o DXF correto para obra/pav/tipo."""
    # Tentar discovery JSON primeiro
    if discovery_path and discovery_path.exists():
        with open(discovery_path, encoding='utf-8') as f:
            disc = json.load(f)
        obra_nome = obra_path.name
        pav_data = disc.get(obra_nome, {}).get(pavimento, {})
        dxf = pav_data.get(tipo)
        if dxf and Path(dxf).exists():
            return dxf

    # Fallback: scan direto na Fase-1
    fase1 = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    if not fase1.exists():
        return None

    # Buscar arquivo que contenha o tipo no nome
    # Ordena por maior revisão
    candidatos = sorted(fase1.glob(f"*.dxf"), reverse=True)
    pav_norm = pavimento.replace('°', '').replace('º', '').upper().strip()

    for dxf in candidatos:
        nome_upper = dxf.stem.upper()
        if f' - {tipo} - ' not in nome_upper and not nome_upper.endswith(f'- {tipo} -'):
            # Checar padrão alternativo ".- {tipo}"
            if f'.- {tipo} -' not in nome_upper:
                continue
        # Verificar se o pavimento está no nome (normalizado)
        nome_pav_norm = re.sub(r'[°º]', '', nome_upper).strip()
        if pav_norm.replace(' ', '') in nome_pav_norm.replace(' ', ''):
            return str(dxf)

    return None


def run(obra_path: str, pavimento: str, discovery_path: str = None) -> None:
    obra = Path(obra_path)
    disc_path = Path(discovery_path) if discovery_path else None

    fase3 = obra / "Fase-3_Interpretacao_Extracao"
    fase3.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] === extrair_ancoras_dxf.py | {obra.name} | {pavimento} ===")

    # ── Pilares (PL DXF) ──────────────────────────────
    pl_path = load_dxf_path(obra, pavimento, 'PL', disc_path)
    if pl_path:
        print(f"[INFO] PL DXF: {Path(pl_path).name}")
        ancoras_pilares = extrair_ancoras_pilares(pl_path)
        out = fase3 / "ancoras_pilares.json"
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(ancoras_pilares, f, indent=2, ensure_ascii=False)
        print(f"[INFO] Salvo: {out} ({len(ancoras_pilares)} pilares)")
    else:
        print(f"[WARN] PL DXF nao encontrado para '{pavimento}'")
        ancoras_pilares = {}

    # ── Vigas (LV DXF) ────────────────────────────────
    lv_path = load_dxf_path(obra, pavimento, 'LV', disc_path)
    if lv_path:
        print(f"[INFO] LV DXF: {Path(lv_path).name}")
        ancoras_vigas = extrair_ancoras_vigas(lv_path)
        out = fase3 / "ancoras_vigas.json"
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(ancoras_vigas, f, indent=2, ensure_ascii=False)
        print(f"[INFO] Salvo: {out} ({len(ancoras_vigas)} vigas)")
    else:
        print(f"[WARN] LV DXF nao encontrado para '{pavimento}'")
        ancoras_vigas = {}

    # ── Lajes (LJ DXF) ────────────────────────────────
    lj_path = load_dxf_path(obra, pavimento, 'LJ', disc_path)
    if lj_path:
        print(f"[INFO] LJ DXF: {Path(lj_path).name}")
        ancoras_lajes = extrair_ancoras_lajes(lj_path)
        out = fase3 / "ancoras_lajes.json"
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(ancoras_lajes, f, indent=2, ensure_ascii=False)
        print(f"[INFO] Salvo: {out} ({len(ancoras_lajes)} lajes)")
    else:
        print(f"[WARN] LJ DXF nao encontrado para '{pavimento}'")
        ancoras_lajes = {}

    # ── Sumário ───────────────────────────────────────
    print(f"\n[RESULTADO]")
    print(f"  Pilares: {len(ancoras_pilares)} ancoras")
    print(f"  Vigas:   {len(ancoras_vigas)} ancoras")
    print(f"  Lajes:   {len(ancoras_lajes)} ancoras")

    cobertura_ok = (
        len(ancoras_pilares) >= 20 and
        len(ancoras_vigas) >= 20 and
        len(ancoras_lajes) >= 10
    )
    print(f"\n  STATUS: {'OK (cobertura suficiente)' if cobertura_ok else 'PARCIAL (cobertura baixa)'}")


def main():
    parser = argparse.ArgumentParser(description='Extrai ancoras de elementos nos DXFs STOG')
    parser.add_argument('--obra', required=True, help='Path da obra')
    parser.add_argument('--pavimento', default='12 PAV', help='Nome do pavimento (default: "12 PAV")')
    parser.add_argument('--dxf-discovery', default=None,
                        help='Path para dxf_discovery.json (opcional)')
    args = parser.parse_args()

    disc = args.dxf_discovery
    if disc is None:
        # Tentar achar discovery no diretório pai da obra
        default_disc = Path(args.obra).parent / "dxf_discovery.json"
        if default_disc.exists():
            disc = str(default_disc)

    run(args.obra, args.pavimento, disc)


if __name__ == '__main__':
    main()
