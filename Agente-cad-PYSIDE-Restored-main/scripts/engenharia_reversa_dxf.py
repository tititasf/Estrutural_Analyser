#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engenharia_reversa_dxf.py — Extração de ground truth a partir de DXFs de entrega STOG.

Lê os DXFs finais (PL=Pilares, LV=Vigas Laterais, FV=Fundos Vigas, LJ=Lajes)
e extrai as fichas de referência (ground truth) para a obra.

Confiança dos dados extraídos:
  - Nomes/IDs dos elementos: ALTA (extraído de labels MTEXT no DXF)
  - Contagem de elementos: ALTA (contagem de labels únicos)
  - Altura (Pé Direito): MEDIA (extraído de DIMENSION com texto "Pé DIREITO")
  - B e H: BAIXA (requer parsing espacial complexo — marcado confidence=0.3)

CLI:
  python scripts/engenharia_reversa_dxf.py \\
    --obra ../DADOS-OBRAS/Obra_TREINO_21 \\
    --pavimento "12 PAV"
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


def _load_ezdxf():
    try:
        import ezdxf
        return ezdxf
    except ImportError:
        print("[ERROR] ezdxf nao instalado: pip install ezdxf")
        sys.exit(1)


def _find_dxf(rev_dir: Path, pattern: str) -> Path | None:
    """Encontra DXF por padrão glob (case insensitive)."""
    for f in rev_dir.iterdir():
        if f.suffix.upper() == '.DXF' and pattern.upper() in f.name.upper():
            return f
    return None


def _extract_pilar_ids_from_pl(dxf_path: Path, ezdxf) -> dict:
    """
    Lê PL (Pilares) DXF e extrai IDs únicos dos pilares.
    Usa MTEXT na layer 'Texto Seção' com labels como 'P1.A', 'P25.D'.
    """
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    pilar_data = {}  # P{n}: {faces: set, positions: [(x,y)]}
    for e in msp:
        if e.dxftype() != 'MTEXT':
            continue
        layer = e.dxf.layer
        if 'Texto Se' not in layer and 'TEXTO' not in layer.upper():
            continue
        try:
            txt = e.plain_text().strip()
        except Exception:
            try:
                txt = e.dxf.text.strip()
            except Exception:
                continue

        matches = re.findall(r'[Pp](\d+)\.([A-H])', txt)
        for num, face in matches:
            pid = f'P{num}'
            if pid not in pilar_data:
                pilar_data[pid] = {'faces': set(), 'positions': []}
            pilar_data[pid]['faces'].add(face)
            try:
                pos = e.dxf.insert
                pilar_data[pid]['positions'].append((pos.x, pos.y))
            except Exception:
                pass

    return pilar_data


def _extract_pe_direito_from_pl(dxf_path: Path, ezdxf) -> float | None:
    """
    Lê dimensão 'Pé DIREITO' do PL DXF.
    Retorna valor em cm ou None.
    """
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    for e in msp:
        if e.dxftype() != 'DIMENSION':
            continue
        try:
            txt = e.dxf.text
            if 'DIREITO' in txt.upper() or 'PE' in txt.upper() or 'ALTURA' in txt.upper():
                m = round(e.get_measurement(), 1)
                if 200 <= m <= 1500:  # range válido para pé direito em cm
                    return m
        except Exception:
            continue
    return None


def _extract_viga_ids_from_lv(dxf_path: Path, ezdxf) -> dict:
    """
    Lê LV (Vigas Laterais) DXF e extrai IDs de vigas.
    Busca TEXTs com padrão 'V{n}' ou 'VG{n}'.
    """
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    viga_data = {}
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = (e.plain_text() if e.dxftype() == 'MTEXT' else e.dxf.text).strip()
        except Exception:
            continue

        # Viga labels: V1.A, V12_A, VG5.B etc
        matches = re.findall(r'[Vv][Gg]?(\d+)[._]([A-H])', txt)
        for num, side in matches:
            vid = f'V{num}'
            if vid not in viga_data:
                viga_data[vid] = {'sides': set()}
            viga_data[vid]['sides'].add(side)

        # Also match just "V{n}" labels
        plain_matches = re.findall(r'\b[Vv](\d+)\b', txt)
        for num in plain_matches:
            vid = f'V{num}'
            if vid not in viga_data:
                viga_data[vid] = {'sides': set()}

    return viga_data


def _extract_laje_ids_from_lj(dxf_path: Path, ezdxf) -> dict:
    """
    Lê LJ (Lajes) DXF e extrai IDs de lajes.
    Busca TEXT/MTEXT com padrão 'L{n}'.
    """
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    laje_data = {}
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = (e.plain_text() if e.dxftype() == 'MTEXT' else e.dxf.text).strip()
        except Exception:
            continue

        matches = re.findall(r'\b[Ll](\d+)\b', txt)
        for num in matches:
            lid = f'L{num}'
            if lid not in laje_data:
                laje_data[lid] = {}

    return laje_data


def build_pilares_ground_truth(pilar_data: dict, pe_direito: float | None, pavimento: str) -> dict:
    """Gera fichas de pilares em formato Fase-3."""
    altura = pe_direito if pe_direito else 280.0
    fichas = {}
    for pid in sorted(pilar_data.keys(), key=lambda x: int(x[1:])):
        fichas[pid] = {
            "b": None,       # B: requer análise DXF espacial complexa
            "h": None,       # H: requer análise DXF espacial complexa
            "altura": altura,
            "confidence": 0.30,   # baixo — dims B/H não extraídas automaticamente
            "source": "engenharia-reversa-ezdxf",
            "faces_encontradas": sorted(pilar_data[pid]['faces']),
            "nota": "B e H requerem verificação manual — apenas ID e altura extraídos automaticamente"
        }
    fichas["_meta"] = {
        "total": len(pilar_data),
        "obra": "engenharia-reversa",
        "pavimento": pavimento,
        "pe_direito_cm": pe_direito,
        "extraido_em": datetime.now().strftime("%Y-%m-%d"),
        "confidence_nota": "IDs=ALTA | altura=MEDIA | B/H=BAIXA(requer revisao)"
    }
    return fichas


def build_vigas_ground_truth(viga_data: dict, pavimento: str) -> dict:
    """Gera fichas de vigas em formato Fase-3."""
    fichas = {}
    for vid in sorted(viga_data.keys(), key=lambda x: int(x[1:])):
        fichas[vid] = {
            "b": None,
            "h": None,
            "comprimento": None,
            "confidence": 0.25,
            "source": "engenharia-reversa-ezdxf",
            "sides_encontrados": sorted(viga_data[vid].get('sides', [])),
            "nota": "Dims requerem verificação manual"
        }
    if fichas:
        fichas["_meta"] = {
            "total": len(viga_data),
            "pavimento": pavimento,
            "extraido_em": datetime.now().strftime("%Y-%m-%d")
        }
    return fichas


def build_lajes_ground_truth(laje_data: dict, pavimento: str) -> dict:
    """Gera fichas de lajes em formato Fase-3."""
    fichas = {}
    for lid in sorted(laje_data.keys(), key=lambda x: int(x[1:])):
        fichas[lid] = {
            "comprimento": None,
            "largura": None,
            "coordenadas": [],
            "area_cm2": None,
            "confidence": 0.25,
            "source": "engenharia-reversa-ezdxf",
            "nota": "Dims requerem verificação manual"
        }
    if fichas:
        fichas["_meta"] = {
            "total": len(laje_data),
            "pavimento": pavimento,
            "extraido_em": datetime.now().strftime("%Y-%m-%d")
        }
    return fichas


def run(obra_path: str, pavimento: str) -> None:
    ezdxf = _load_ezdxf()
    obra = Path(obra_path)
    rev_dir = obra / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    out_dir = obra / "Fase-3_Interpretacao_Extracao"

    if not rev_dir.exists():
        print(f"[ERROR] Diretório de engenharia reversa não encontrado: {rev_dir}")
        sys.exit(1)

    print(f"[INFO] === engenharia_reversa_dxf.py | Obra: {obra.name} | Pav: {pavimento} ===")
    print(f"[INFO] Diretório: {rev_dir}")

    # --- Pilares (PL) ---
    pl_dxf = _find_dxf(rev_dir, "- PL -") or _find_dxf(rev_dir, "PL -") or _find_dxf(rev_dir, "PL_")
    if pl_dxf:
        print(f"[INFO] PL DXF: {pl_dxf.name}")
        pilar_data = _extract_pilar_ids_from_pl(pl_dxf, ezdxf)
        pe_direito = _extract_pe_direito_from_pl(pl_dxf, ezdxf)
        pilares_gt = build_pilares_ground_truth(pilar_data, pe_direito, pavimento)
        out_p = out_dir / "Pilares" / "pilares_ground_truth.json"
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, 'w', encoding='utf-8') as f:
            json.dump(pilares_gt, f, indent=2, ensure_ascii=False)
        n = pilares_gt["_meta"]["total"]
        print(f"[INFO] Pilares extraídos: {n} IDs | Pé Direito: {pe_direito}cm -> {out_p}")
    else:
        print("[WARN] PL DXF não encontrado — pulando pilares")
        pilar_data = {}
        pilares_gt = {}

    # --- Vigas Laterais (LV) ---
    lv_dxf = _find_dxf(rev_dir, "- LV -") or _find_dxf(rev_dir, "LV -") or _find_dxf(rev_dir, "LV_")
    if lv_dxf:
        print(f"[INFO] LV DXF: {lv_dxf.name}")
        viga_data = _extract_viga_ids_from_lv(lv_dxf, ezdxf)
        vigas_gt = build_vigas_ground_truth(viga_data, pavimento)
        if vigas_gt:
            out_v = out_dir / "Vigas" / "vigas_ground_truth.json"
            out_v.parent.mkdir(parents=True, exist_ok=True)
            with open(out_v, 'w', encoding='utf-8') as f:
                json.dump(vigas_gt, f, indent=2, ensure_ascii=False)
            n = vigas_gt.get("_meta", {}).get("total", 0)
            print(f"[INFO] Vigas extraídas: {n} IDs -> {out_v}")
        else:
            print("[INFO] Nenhuma viga identificada no LV DXF")
    else:
        print("[WARN] LV DXF não encontrado — pulando vigas")

    # --- Lajes (LJ) ---
    lj_dxf = _find_dxf(rev_dir, "- LJ -") or _find_dxf(rev_dir, "LJ -") or _find_dxf(rev_dir, "LJ_")
    if lj_dxf:
        print(f"[INFO] LJ DXF: {lj_dxf.name}")
        laje_data = _extract_laje_ids_from_lj(lj_dxf, ezdxf)
        lajes_gt = build_lajes_ground_truth(laje_data, pavimento)
        if lajes_gt:
            out_l = out_dir / "Lajes" / "lajes_ground_truth.json"
            out_l.parent.mkdir(parents=True, exist_ok=True)
            with open(out_l, 'w', encoding='utf-8') as f:
                json.dump(lajes_gt, f, indent=2, ensure_ascii=False)
            n = lajes_gt.get("_meta", {}).get("total", 0)
            print(f"[INFO] Lajes extraídas: {n} IDs -> {out_l}")
        else:
            print("[INFO] Nenhuma laje identificada no LJ DXF")
    else:
        print("[WARN] LJ DXF não encontrado — pulando lajes")

    # --- Resumo ---
    n_pilares = pilares_gt.get("_meta", {}).get("total", 0) if pilares_gt else 0
    print(f"[INFO] === RESULTADO: {n_pilares} pilares (ground truth) ===")
    print(f"[INFO] NOTA: IDs e count são CONFIÁVEIS. B/H requerem revisão manual ou análise visual.")
    print(f"[INFO] Ground truth salvo em: {out_dir}")


def main():
    parser = argparse.ArgumentParser(description='Extrai ground truth de DXFs de engenharia reversa STOG')
    parser.add_argument('--obra', required=True, help='Path para o diretório da obra')
    parser.add_argument('--pavimento', required=True, help='Identificador do pavimento (ex: "12 PAV")')
    args = parser.parse_args()
    run(args.obra, args.pavimento)


if __name__ == '__main__':
    main()
