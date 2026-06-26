"""
gerar_obras_salvas.py — Gerador de obras_salvas.json no formato do Robo_Pilares
================================================================================
Converte os dados das Fases 3 e 4 para o formato JSON que o PilarAnalyzer.exe
(robô de geração DXF) espera como input.

Uso:
  python scripts/gerar_obras_salvas.py --obra DADOS-OBRAS/Obra_TREINO_21
  python scripts/gerar_obras_salvas.py --obra DADOS-OBRAS/Obra_TREINO_21 --nome-obra "NIK SUNSET" --pavimento "12 PAV"
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("gerar_obras_salvas")

FACES = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
STANDARD_PANEL_WIDTH = "244"   # STOG padrão 244cm
DEFAULT_POSICAO_LAJE = "5"
DEFAULT_DISTANCIA = "14"       # distancia_1 default STOG


def empty_aberturas() -> dict:
    """Estrutura de aberturas vazia (2 esquerda + 2 direita)."""
    ab = {}
    for side in ("esquerda", "direita"):
        ab[side] = {}
        for i in range(1, 3):
            ab[side][str(i)] = {
                "distancia": "", "largura": "", "profundidade": "",
                "posicao": "", "tipo": ""
            }
    return ab


def build_paineis(pilar_json: dict) -> dict:
    """
    Constrói o dict 'paineis' por face (A-H) a partir dos campos h1_A..h5_A,
    larg1_A..larg3_A do JSON de pilar Fase-4.
    """
    paineis = {}
    for face in FACES:
        h1 = pilar_json.get(f"h1_{face}", 0.0)
        h2 = pilar_json.get(f"h2_{face}", 0.0)
        h3 = pilar_json.get(f"h3_{face}", 0.0)
        h4 = pilar_json.get(f"h4_{face}", 0.0)
        h5 = pilar_json.get(f"h5_{face}", 0.0)
        larg1 = pilar_json.get(f"larg1_{face}", 0.0)
        larg2 = pilar_json.get(f"larg2_{face}", 0.0)
        larg3 = pilar_json.get(f"larg3_{face}", 0.0)

        # Usar painel padrão 244 se largura não foi calculada
        if larg1 == 0.0:
            larg1_str = STANDARD_PANEL_WIDTH
        else:
            larg1_str = str(int(larg1))

        paineis[face] = {
            "laje": "",
            "posicao_laje": DEFAULT_POSICAO_LAJE,
            "larg1": larg1_str,
            "larg2": str(int(larg2)) if larg2 else "0",
            "larg3": str(int(larg3)) if larg3 else "0",
            "h1": str(int(h1)) if h1 else "0",
            "h2": str(int(h2)) if h2 else "0",
            "h3": str(int(h3)) if h3 else "0",
            "h4": str(int(h4)) if h4 else "0",
            "h5": str(int(h5)) if h5 else "0",
            "aberturas": empty_aberturas()
        }
    return paineis


def build_parafusos() -> dict:
    """Parafusos vazios — o robô recalcula baseado em grade_1/comprimento."""
    return {
        "par_1_2": "0", "par_2_3": "0", "par_3_4": "0", "par_4_5": "0",
        "par_5_6": "0", "par_6_7": "0", "par_7_8": "0", "par_8_9": "0"
    }


def build_grades(pilar_json: dict) -> dict:
    """Popula grades com dados do assembly (CAD-7.1)."""
    g1 = pilar_json.get("grade_1", 0.0)
    g2 = pilar_json.get("grade_2", 0.0)
    d1 = pilar_json.get("distancia_1", 14.0)

    return {
        "grade_1": str(int(g1)) if g1 else "0",
        "distancia_1": str(int(d1)) if d1 else DEFAULT_DISTANCIA,
        "grade_2": str(int(g2)) if g2 else "",
        "distancia_2": "",
        "grade_3": ""
    }


def pilar_json_to_obras(pilar_json: dict, obra_nome: str,
                         pavimento: str, pav_numero: str = "1",
                         nivel_chegada: float = 0.0,
                         nivel_saida: float = 280.0) -> dict:
    """Converte JSON_Pilares/P{n}.json → formato dados de obras_salvas."""
    numero = str(pilar_json.get("numero", "0"))
    nome = pilar_json.get("nome", f"P{numero}")
    comprimento = pilar_json.get("comprimento", 0.0)
    largura = pilar_json.get("largura", 0.0)
    altura = pilar_json.get("altura", 280.0)

    dados = {
        "numero": numero,
        "nome": nome,
        "obra": obra_nome,
        "comprimento": str(int(comprimento)),
        "largura": str(int(largura)),
        "pavimento": pavimento,
        "pavimento_numero": pav_numero,
        "pavimento_anterior": pavimento,
        "nivel_saida": str(nivel_saida),
        "nivel_chegada": str(nivel_chegada),
        "nivel_diferencial": "",
        "altura": str(int(altura)),
        "parafusos": build_parafusos(),
        "grades": build_grades(pilar_json),
        "pilar_especial": False,
        "detalhes_grades": {},
        "altura_detalhes_grades": "",
        "grades_grupo2": {},
        "detalhes_grades_grupo2": {},
        "altura_detalhes_grades_b": "",
        "ruler_grupo1": {},
        "paineis": build_paineis(pilar_json),
        "modo_calculo": "automatico",
        "tipo_distribuicao_largura": "padrao",
        "checkbox_descontar_laje": False,
        "checkbox_descontar_aberturas": False,
        "hachura_paineis": False,
        "m2_total": 0.0
    }
    return dados


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--obra", required=True, help="Path da obra")
    parser.add_argument("--nome-obra", default=None, help="Nome da obra (default: dirname)")
    parser.add_argument("--pavimento", default="12 PAV", help="Nome do pavimento")
    parser.add_argument("--pav-numero", default="1", help="Número do pavimento")
    parser.add_argument("--nivel-chegada", type=float, default=0.0)
    parser.add_argument("--nivel-saida", type=float, default=280.0)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    obra_nome = args.nome_obra or obra_path.name
    pav = args.pavimento

    json_pilares_dir = obra_path / "Fase-4_Sincronizacao" / "JSON_Pilares"
    if not json_pilares_dir.exists():
        log.error(f"JSON_Pilares/ nao encontrado: {json_pilares_dir}")
        sys.exit(1)

    # Coletar todos os JSON de pilares
    pilar_files = sorted(json_pilares_dir.glob("P*.json"),
                         key=lambda p: int(p.stem[1:]) if p.stem[1:].isdigit() else 999)

    if not pilar_files:
        log.warning("Nenhum arquivo P*.json encontrado em JSON_Pilares/ - obras_salvas gerado sem pilares")

    log.info(f"Processando {len(pilar_files)} pilares → obras_salvas.json")

    # Estrutura: {obra_nome: {pavimento: {numero: {dados: {...}, item_id: ..., locks: {}}}}}
    obras_salvas: Dict[str, Any] = {
        obra_nome: {
            pav: {}
        }
    }

    count = 0
    for pf in pilar_files:
        with open(pf, encoding="utf-8") as f:
            pj = json.load(f)

        numero = str(pj.get("numero", pf.stem[1:]))
        dados = pilar_json_to_obras(
            pj,
            obra_nome=obra_nome,
            pavimento=pav,
            pav_numero=args.pav_numero,
            nivel_chegada=args.nivel_chegada,
            nivel_saida=args.nivel_saida
        )

        item_id = f"{numero}_{pav}"
        obras_salvas[obra_nome][pav][numero] = {
            "dados": dados,
            "item_id": item_id,
            "locks": {}
        }
        count += 1
        g1 = dados["grades"]["grade_1"]
        log.info(f"  P{numero}: {dados['comprimento']}x{dados['largura']}cm grade_1={g1}")

    # Salvar obras_salvas.json
    out_path = obra_path / "Fase-4_Sincronizacao" / "obras_salvas.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(obras_salvas, f, ensure_ascii=False, indent=2)

    log.info(f"✅ obras_salvas.json gerado: {count} pilares → {out_path}")

    # Gerar também pavimentos_lista.json
    pavimentos_lista = {
        obra_nome: {
            "pavimentos": [pav],
            "pavimentos_data": {
                pav: {
                    "nome": pav,
                    "numero": args.pav_numero,
                    "nivel_chegada": str(args.nivel_chegada),
                    "nivel_saida": str(args.nivel_saida)
                }
            }
        }
    }
    pav_path = obra_path / "Fase-4_Sincronizacao" / "pavimentos_lista.json"
    with open(pav_path, "w", encoding="utf-8") as f:
        json.dump(pavimentos_lista, f, ensure_ascii=False, indent=2)
    log.info(f"✅ pavimentos_lista.json gerado → {pav_path}")


if __name__ == "__main__":
    main()
