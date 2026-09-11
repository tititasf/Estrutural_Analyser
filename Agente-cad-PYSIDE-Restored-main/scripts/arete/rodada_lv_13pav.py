#!/usr/bin/env python3
"""Rodada de revisao granular LV — uma pagina por viga + indice.

OBJETIVO
    Dar ao revisor, para CADA viga LV do pavimento, a mesma superficie granular
    que foi construida na V301: cada segmento N2 recortado ao lado do seu
    segmento N4 correspondente, com marcacao de ponto e nota por cartao, e as
    visoes de corte logo abaixo. A partir dos apontamentos, o motor e' ajustado
    e a viga e' regerada individualmente ate' ficar Arete.

PROCEDIMENTO
    1. Gerar os N4 da rodada (nao escreve na producao):
         python scripts/arete/gerar_lv_n4_fichas.py <vigas...> --out <rodada>/n4
       `--refresh-from-recorte` e' o padrao; a fonte da ficha e' impressa.
    2. Rodar esta rodada:
         python scripts/arete/rodada_lv_13pav.py
       Para cada viga: gate de geometria (--no-regen) + pagina de revisao.
    3. Abrir <rodada>/INDEX_VIGAS.html e revisar item por item.
    4. Ao achar um problema: corrigir o motor, regerar SO aquela viga
         python scripts/arete/gerar_lv_n4_fichas.py <viga> --out <rodada>/n4
         python scripts/arete/rodada_lv_13pav.py --item <viga>
       e reabrir a pagina da viga.
    5. Antes de publicar em producao, comparar contagem de entidades contra o
       arquivo existente (queda grande = ficha stale, abortar).

NOTA
    Os N4 selados em DADOS-OBRAS/.../n4 estao somente-leitura de proposito.
    A rodada le e escreve apenas dentro de relatorios/g2v/, via LV_N4_DIR.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ARETE = Path(__file__).resolve().parent
REPO = ARETE.parent.parent
RODADA = ARETE / "relatorios" / "g2v" / "lv_13pav_rodada_20260911"
N4 = RODADA / "n4"
PY = sys.executable

VIGAS = ("V13 V301 V302 V303 V304 V305 V306 V308 V310 V311 V312 V314 V315 V316 "
         "V317 V318 V319 V320 V321 V322 V323 V324 V325 V326 V327 V328 V329 V330 "
         "V331 V332 VF203 VF301").split()


def _run(cmd: list[str], env: dict) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                           cwd=str(REPO), env=env)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return False, "timeout"


def processar(viga: str) -> dict:
    env = dict(os.environ)
    env["LV_N4_DIR"] = str(N4)
    env["PYTHONIOENCODING"] = "utf-8"
    st = {"viga": viga, "gate": False, "pagina": None, "erro": ""}

    if not (N4 / f"LV_preview_{viga}_A.dxf").exists():
        st["erro"] = "N4 ausente (viga nao gerou: ver contrato)"
        return st

    ok, log = _run([PY, str(ARETE / "run_geometry_gate_lv.py"), viga,
                    "--no-regen", "--no-open"], env)
    st["gate"] = ok
    if not ok:
        st["erro"] = "gate falhou: " + log.strip().splitlines()[-1][:160]
        return st

    ok, log = _run([PY, str(ARETE / "_build_segments_html_v301.py"), viga], env)
    if not ok:
        st["erro"] = "pagina falhou: " + log.strip().splitlines()[-1][:160]
        return st
    pag = (ARETE / "relatorios" / "g2v" / f"{viga.lower()}_geometry_gate"
           / f"{viga}_SEGMENTS_E2E.html")
    st["pagina"] = pag if pag.exists() else None
    if not st["pagina"]:
        st["erro"] = "pagina nao encontrada apos build"
    return st


def montar_indice(estados: list[dict]) -> Path:
    import json
    import re
    css = """
body{font-family:system-ui,sans-serif;background:#0b1220;color:#e5e7eb;margin:0}
header{padding:18px 22px;background:#0f172a;border-bottom:1px solid #1f2937}
h1{margin:0 0 6px;font-size:1.25rem}.mut{color:#94a3b8;font-size:.9rem}
main{padding:18px 22px 60px;max-width:1100px;margin:0 auto}
ul{list-style:none;padding:0;margin:0}
li{border-bottom:1px solid #1f2937}
a.item{display:flex;justify-content:space-between;gap:12px;align-items:center;
 padding:12px 10px;color:#e5e7eb;text-decoration:none}
a.item:hover{background:#111827}
.viga{font-weight:700;font-size:1rem}
.meta{color:#94a3b8;font-size:.85rem}
.bad{color:#f87171;font-weight:700}.warn{color:#fbbf24}.ok{color:#34d399}
"""
    ind = {}
    p_ind = RODADA / "indice_n2.json"
    if p_ind.exists():
        ind = {r["viga"]: r for r in json.loads(p_ind.read_text(encoding="utf-8"))}

    linhas = []
    for st in estados:
        v = st["viga"]
        r = ind.get(v, {})
        if st["pagina"]:
            try:
                h = st["pagina"].read_text(encoding="utf-8")
                n_cards = len(re.findall(r'data-key="([^"]+)"', h))
            except Exception:
                n_cards = 0
            href = os.path.relpath(st["pagina"], RODADA).replace("\\", "/")
            extra = f"{n_cards} cartões"
            cls = "ok"
        else:
            href = ""
            extra = st["erro"] or "sem página"
            cls = "bad"
        meta = (f"face_units={r.get('fu_vivo', '?')} · "
                f"seções={r.get('secoes_vivo', '?')} · "
                f"<span class='{cls}'>{extra}</span>")
        if href:
            linhas.append(f"<li><a class='item' href='{href}'>"
                          f"<span class='viga'>{v}</span>"
                          f"<span class='meta'>{meta}</span></a></li>")
        else:
            linhas.append(f"<li><div class='item'>"
                          f"<span class='viga'>{v}</span>"
                          f"<span class='meta'>{meta}</span></div></li>")

    html = (f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>LV 13_PAV — vigas</title><style>{css}</style></head><body>"
            f"<header><h1>LV 13_PAV — revisão granular por viga</h1>"
            f"<div class='mut'>Clique numa viga para abrir os cartões N2×N4 por "
            f"segmento e as visões de corte. Produção não é alterada por esta "
            f"rodada.</div></header><main><ul>"
            + "".join(linhas) +
            "</ul></main></body></html>")
    out = RODADA / "INDEX_VIGAS.html"
    out.write_text(html, encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--item", action="append",
                    help="Processar só esta viga (pode repetir)")
    args = ap.parse_args()
    alvos = args.item or VIGAS

    estados = []
    for v in alvos:
        print(f"[{v}] ...", end=" ", flush=True)
        st = processar(v)
        estados.append(st)
        print("OK" if st["pagina"] else f"FALHOU — {st['erro']}")

    if not args.item:
        out = montar_indice(estados)
        print("\nINDICE:", out)
    ok = sum(1 for s in estados if s["pagina"])
    print(f"{ok}/{len(estados)} paginas geradas")


if __name__ == "__main__":
    main()
