#!/usr/bin/env python3
"""Gold N2 de uma viga LV — medido do recorte cru, para o dono arbitrar.

POR QUE EXISTE
    O gate compara ledger N2 x ledger N4, mas o cabecalho do ledger N2 e'
    emprestado da ficha: se o extrator errou, os DOIS lados carregam o mesmo
    erro e o veredito nao sabe dizer de quem e' a culpa (achado 2026-09-11 na
    V13: ledger N2 dizia h_body=154.3 enquanto o DXF mostra 44.0).

    O Gold e' a terceira ponta, medida do DXF SEM olhar a ficha. Com ele saem
    dois vereditos independentes:

        Gold  x  Ficha        -> julga o motor de INTERPRETACAO (N2)
        Ficha x  Ledger N4    -> julga o motor de DESENHO (N4)

COMO E' MEDIDO (so' geometria, sem heuristica de face)
    * bandas de face: pares de linhas horizontais da layer `Painéis` com a
      mesma extensao em X; a altura do par e' o h_body;
    * divisores: linhas verticais de `Painéis` dentro da banda; as larguras
      sao os intervalos entre divisores consecutivos e a borda direita;
    * cotas escritas: textos da layer `COTA` na faixa da banda.

    Quando a cota escrita diverge da geometria, o Gold registra AS DUAS e
    marca `arbitrar`. Convencao do projeto (ver
    `_materialize_dimension_text_overrides`): o texto e' contratual e vence —
    mas a divergencia fica anotada para o dono confirmar.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ezdxf

ARETE = Path(__file__).resolve().parent
GOLD_DIR = ARETE / "gold" / "lv"
TOL = 0.6


def _bandas_de_face(msp) -> list[dict]:
    """Pares de horizontais `Painéis` de mesma extensao = uma face."""
    horiz: dict = {}
    for e in msp.query("LINE"):
        if e.dxf.layer != "Painéis":
            continue
        s, t = e.dxf.start, e.dxf.end
        if abs(s[1] - t[1]) > TOL:
            continue
        chave = (round(min(s[0], t[0]), 1), round(max(s[0], t[0]), 1))
        horiz.setdefault(chave, []).append(round(s[1], 1))

    # Verticais de `Painéis`: o que distingue um painel de verdade do VAO
    # entre duas faces. Duas horizontais consecutivas so' formam banda se
    # houver vertical fechando a altura delas (na V13, o par 3057.4/3226.3
    # virava uma "face" de 168.9 que nao existe).
    verticais = []
    for e in msp.query("LINE"):
        if e.dxf.layer != "Painéis":
            continue
        s, t = e.dxf.start, e.dxf.end
        if abs(s[0] - t[0]) > TOL:
            continue
        verticais.append((round(float(s[0]), 1),
                          round(min(s[1], t[1]), 1),
                          round(max(s[1], t[1]), 1)))

    bandas = []
    for (x0, x1), ys in horiz.items():
        ys = sorted(set(ys))
        for i in range(len(ys) - 1):
            y_bot, y_top = ys[i], ys[i + 1]
            alt = y_top - y_bot
            if alt <= 1.0:
                continue
            fecha = any(
                abs(vy0 - y_bot) <= TOL and abs(vy1 - y_top) <= TOL
                and x0 - TOL <= vx <= x1 + TOL
                for vx, vy0, vy1 in verticais
            )
            if not fecha:
                continue
            bandas.append({
                "x_ini": x0, "x_fim": x1,
                "y_bot": y_bot, "y_top": y_top,
                "h_body": round(alt, 1),
                "largura_geom": round(x1 - x0, 1),
            })
    bandas.sort(key=lambda b: -b["y_top"])
    return bandas


def _larguras_geom(msp, banda: dict) -> list[float]:
    """Intervalos entre divisores verticais de `Painéis` dentro da banda."""
    xs = set()
    for e in msp.query("LINE"):
        if e.dxf.layer != "Painéis":
            continue
        s, t = e.dxf.start, e.dxf.end
        if abs(s[0] - t[0]) > TOL:
            continue
        y0, y1 = min(s[1], t[1]), max(s[1], t[1])
        if y0 >= banda["y_bot"] - TOL and y1 <= banda["y_top"] + TOL:
            if banda["x_ini"] - TOL <= s[0] <= banda["x_fim"] + TOL:
                xs.add(round(float(s[0]), 1))
    xs.add(banda["x_ini"])
    xs.add(banda["x_fim"])
    ordenados = sorted(xs)
    return [round(b - a, 1) for a, b in zip(ordenados, ordenados[1:]) if b - a > 1.0]


def _cotas_escritas(msp, banda: dict, alcance: float = 75.0) -> list[dict]:
    out = []
    for e in msp.query("TEXT"):
        if e.dxf.layer != "COTA":
            continue
        ix, iy = float(e.dxf.insert[0]), float(e.dxf.insert[1])
        if not (banda["y_bot"] - alcance <= iy <= banda["y_top"] + alcance):
            continue
        if not (banda["x_ini"] - 60 <= ix <= banda["x_fim"] + 60):
            continue
        try:
            val = float(e.dxf.text.strip())
        except ValueError:
            continue
        out.append({"valor": val, "x": round(ix, 1), "y": round(iy, 1)})
    out.sort(key=lambda c: (-c["y"], c["x"]))
    return out


def construir(item: str, n2_path: Path) -> dict:
    msp = ezdxf.readfile(str(n2_path)).modelspace()
    bandas = _bandas_de_face(msp)
    faces = []
    for idx, b in enumerate(bandas):
        larg = _larguras_geom(msp, b)
        cotas = _cotas_escritas(msp, b)
        # Sub-cotas = valores na MESMA linha de cota. Agrupa por y com
        # tolerancia: o mesmo texto de cota aparece em y=3207.9 e 3208.0, e
        # agrupar por igualdade exata perdia a linha inteira.
        por_linha: list = []
        for c in sorted(cotas, key=lambda c: (-c["y"], c["x"])):
            for grupo in por_linha:
                if abs(grupo[0]["y"] - c["y"]) <= 1.5:
                    grupo.append(c)
                    break
            else:
                por_linha.append([c])
        sub = []
        for grupo in por_linha:
            if len(grupo) >= len(larg) and len(grupo) > 1:
                sub = [g["valor"] for g in sorted(grupo, key=lambda g: g["x"])]
                break
        divergencia = None
        if sub and len(sub) == len(larg):
            difs = [round(s - g, 1) for s, g in zip(sub, larg)]
            if any(abs(d) > 1.0 for d in difs):
                divergencia = {
                    "larguras_cota": sub,
                    "larguras_geometria": larg,
                    "diferenca": difs,
                }
        faces.append({
            "ordem": idx,
            "h_body": b["h_body"],
            "larguras": sub or larg,
            "total": round(sum(sub or larg), 1),
            "origem_larguras": "cota escrita" if sub else "geometria",
            "medido_geometria": {
                "larguras": larg,
                "total": b["largura_geom"],
                "x": [b["x_ini"], b["x_fim"]],
                "y": [b["y_bot"], b["y_top"]],
            },
            "arbitrar": divergencia,
        })
    return {
        "item": item,
        "classe": "LV",
        "schema": "gold_lv_v1",
        "fonte_n2": str(n2_path),
        "aprovado": False,
        "faces": faces,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("item")
    ap.add_argument("--n2", help="Recorte N2 (default: do gate do item)")
    ap.add_argument("--salvar", action="store_true")
    args = ap.parse_args()

    if args.n2:
        n2 = Path(args.n2)
    else:
        gate = (ARETE / "relatorios" / "g2v" / f"{args.item.lower()}_geometry_gate"
                / f"{args.item}_GEOMETRY_GATE.json")
        n2 = Path(json.loads(gate.read_text(encoding="utf-8"))["n2"])

    gold = construir(args.item, n2)
    print(json.dumps(gold, indent=2, ensure_ascii=False))
    if args.salvar:
        GOLD_DIR.mkdir(parents=True, exist_ok=True)
        out = GOLD_DIR / f"{args.item}.json"
        out.write_text(json.dumps(gold, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        print("\nGOLD:", out, file=sys.stderr)


if __name__ == "__main__":
    main()
