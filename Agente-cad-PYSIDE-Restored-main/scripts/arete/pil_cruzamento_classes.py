#!/usr/bin/env python
"""Cruzamento entre classes — corrobora a interpretação ABCD do pilar com o que
as OUTRAS classes do mesmo pavimento já afirmam sobre as mesmas vigas.

Motivação (pedido do dono, 2026-08-10): ler linha solta de DXF e adivinhar par
de paredes é "leitura básica no chute". As classes FV (fundos) e LV (laterais)
já carregam o dado **medido e validado** sobre a mesma viga:

  FV  `viga_fundo_seg_N_local_ini` / `_local_fim`
      → entre QUAIS apoios cada segmento corre. Se um deles é o pilar, a viga
        TOCA o pilar (apoio/chega). Se o pilar está no meio do eixo entre ini e
        fim, a viga PASSA por dentro dele.
      Ex.: V304 seg_1 ini=P24 fim=P26  → V304 chega no P24.
           V321 seg_1 ini=P33 fim=V304 → o P24 fica no meio → V321 passa.

  LV  `viga_{a,b}_seg_N_abert_pilar_{esq,dir}_{dist,larg}`
      → a ABERTURA do pilar na lateral da viga: onde e com que largura o pilar
        interrompe o painel. É a interface pilar↔viga medida do lado da viga.

Isto é **corroboração independente**: vem de motores já selados, não da mesma
leitura geométrica que se quer verificar. Serve à camada 3 do §3.6 — quando as
fontes discordam, NÃO decidir: reportar.

Uso:
  py -3.12 scripts/arete/pil_cruzamento_classes.py --item P24
  py -3.12 scripts/arete/pil_cruzamento_classes.py --todos
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.arete.pil_agentic_highlight_draw import load_project  # noqa: E402
from scripts.arete.pil_l2_evidence_check import _beam_contours, _is_horizontal  # noqa: E402
from src.core.pillar_abcd_tables import build_abcd_tables_from_pillar  # noqa: E402
from src.core.niveis_extractor import get_pavimento_niveis_abs  # noqa: E402

EMPTY = ("", "—", "-", "nenhuma", None)
SEG_RE = re.compile(r"viga_fundo_seg_(\d+)_local_(ini|fim)$")


def _txt(v):
    """local_ini/fim vem como str ou como dict {'label':[{'text':...}]}."""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        for lb in (v.get("label") or []):
            t = (lb or {}).get("text")
            if t:
                return str(t).strip()
    return ""


def apoios_declarados(bdata: dict) -> dict[int, tuple[str, str]]:
    """{n_segmento: (local_ini, local_fim)} — o que o FV declara."""
    out: dict[int, list] = {}
    for src in (bdata, bdata.get("links") or {}):
        for k, v in src.items():
            m = SEG_RE.match(k)
            if not m:
                continue
            n = int(m.group(1))
            t = _txt(v)
            if not t:
                continue
            slot = out.setdefault(n, ["", ""])
            idx = 0 if m.group(2) == "ini" else 1
            if not slot[idx]:
                slot[idx] = t
    return {n: (a, b) for n, (a, b) in out.items()}


def aberturas_pilar(bdata: dict) -> list[dict]:
    """Aberturas de pilar declaradas pelo LV nas laterais da viga."""
    out = []
    pat = re.compile(r"viga_([ab])_seg_(\d+)_abert_pilar_(esq|dir)_(dist|larg)$")
    acc: dict[tuple, dict] = {}
    for k, v in bdata.items():
        m = pat.match(k)
        if not m:
            continue
        lado, seg, lr, campo = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        d = acc.setdefault((lado, seg, lr), {"lado": lado, "seg": seg, "extremo": lr})
        try:
            d[campo] = float(str(v).replace(",", "."))
        except Exception:
            pass
    for d in acc.values():
        if d.get("larg"):
            out.append(d)
    return sorted(out, key=lambda d: (d["seg"], d["lado"], d["extremo"]))


def _bbox_de(nome: str, mapa: dict):
    return mapa.get(nome)


def cruzar(pillar: dict, beams: list, mapa_pos: dict) -> dict:
    """mapa_pos: nome (pilar ou viga) → (x0,y0,x1,y1)."""
    nome = pillar["name"]
    xs = [p[0] for p in pillar["points"]]
    ys = [p[1] for p in pillar["points"]]
    px0, py0, px1, py1 = min(xs), min(ys), max(xs), max(ys)
    cx, cy = (px0 + px1) / 2, (py0 + py1) / 2

    toca, passa, aberturas = [], [], []
    vinculadas = set()
    for b in beams:
        bn = b.get("name")
        segs = apoios_declarados(b)
        for n, (ini, fim) in segs.items():
            if nome in (ini, fim):
                toca.append({"viga": bn, "seg": n, "ini": ini, "fim": fim,
                             "papel": "apoio/chega (declarado no FV)"})
                vinculadas.add(bn)
                continue
            # PASSA POR DENTRO — exige as DUAS evidências juntas:
            #  (a) geometria: o contorno DESTE segmento é lateralmente alinhado
            #      com o pilar (mesma faixa) e encosta numa face dele;
            #  (b) topologia: o apoio declarado do outro lado é um elemento
            #      DIFERENTE do pilar → a viga continua além dele.
            # Só (a) confunde com viga que morre no pilar; só (b) dá falso
            # positivo em trecho longo. Caso V321 × P24: contorno x idêntico ao
            # do pilar, encosta na face D, e o fim declarado é V304 (ao norte).
            seg_c = next((s for s in _beam_contours(b)
                          if s["field"].startswith(f"viga_fundo_seg_{n}_")), None)
            if not seg_c:
                continue
            lw, lh = px1 - px0, py1 - py0
            alinhado_x = abs(seg_c["x0"] - px0) <= 2 and abs(seg_c["x1"] - px1) <= 2
            alinhado_y = abs(seg_c["y0"] - py0) <= 2 and abs(seg_c["y1"] - py1) <= 2
            encosta_ns = abs(seg_c["y1"] - py0) <= 2 or abs(seg_c["y0"] - py1) <= 2
            encosta_ew = abs(seg_c["x1"] - px0) <= 2 or abs(seg_c["x0"] - px1) <= 2
            if (alinhado_x and encosta_ns) or (alinhado_y and encosta_ew):
                outro = fim if _txt(ini) == "" or nome == ini else fim
                passa.append({"viga": bn, "seg": n, "ini": ini, "fim": fim,
                              "papel": f"alinhada com o pilar e encosta nele; "
                                       f"apoio declarado além = {outro} → passa por dentro"})
                vinculadas.add(bn)

    # 3ª fonte — ADJACÊNCIA DE CONTORNO: segmento encostando no pilar (gap 0).
    # Achado de 2026-08-10: os apoios declarados no FV nomeiam só os EXTREMOS do
    # trecho; um pilar que a viga atravessa no meio não aparece como apoio.
    # Ex.: V301 × P42 — seg2 x[1503,1603] e seg3 x[1622,1722], ambos na MESMA
    # faixa y[2991,3010] do pilar, gap 0 dos dois lados: a viga atravessa o P42,
    # mas os apoios declarados citam P11/V312. Sem esta checagem o cruzamento
    # acusava falso "ninguém confirma" em 46 vínculos legítimos.
    for b in beams:
        bn = b.get("name")
        if bn in vinculadas:
            continue
        for s in _beam_contours(b):
            dx = max(px0 - s["x1"], s["x0"] - px1, 0.0)
            dy = max(py0 - s["y1"], s["y0"] - py1, 0.0)
            if dx <= 1.0 and dy <= 1.0:
                toca.append({"viga": bn, "seg": s["field"], "ini": "", "fim": "",
                             "papel": "contorno encosta no pilar (gap 0) — vínculo geométrico"})
                vinculadas.add(bn)
                break

    # aberturas só das vigas efetivamente vinculadas a ESTE pilar
    for b in beams:
        if b.get("name") in vinculadas:
            for ab in aberturas_pilar(b):
                aberturas.append({"viga": b.get("name"), **ab})
    return {"item": nome, "toca": toca, "passa": passa, "aberturas": aberturas}


def comparar(cruz: dict, tables: dict) -> list[str]:
    """Confronta o cruzamento com a tabela ABCD. Retorna divergências.

    ⚠ CALIBRAÇÃO (dono, 2026-08-10): isto é **sinal para arbitragem, NUNCA
    correção automática**. Nenhuma classe é autoridade sobre a outra:

      - **PIL é hoje a classe mais madura**; FV/LV ainda erram às vezes. Uma
        divergência é, com frequência, erro da OUTRA classe — não do ABCD.
        Caso arbitrado: no P2 o topo é **VF301** (o ABCD estava certo; o FV
        declarava V301).
      - O valor é **bidirecional**: cada divergência é candidata a fix dos dois
        lados. O relatório serve tanto ao QA de pilares quanto ao de FV/LV.

    Por isso a saída nunca "conserta": ela lista o conflito com as duas versões
    e o que a geometria diz, para decisão humana (camada 3 do §3.6).
    """
    na_tabela = {r.get("nome") for face in (tables.get("faces") or {}).values()
                 for k in ("passa", "chega", "interior")
                 for r in (face.get(k) or [])
                 if (r.get("nome") or "") not in EMPTY}
    declaradas = {t["viga"] for t in cruz["toca"]} | {p["viga"] for p in cruz["passa"]}
    geom = {t["viga"] for t in cruz["toca"]
            if "gap 0" in (t.get("papel") or "")}
    out = []
    for v in sorted(declaradas - na_tabela):
        tag = "com geometria" if v in geom else "só declaração (sem geometria)"
        out.append(f"OUTRA CLASSE liga {v} ao pilar [{tag}], mas o ABCD não tem "
                   f"— checar dos DOIS lados")
    for v in sorted(na_tabela - declaradas):
        out.append(f"ABCD tem {v}, nenhuma outra classe confirma "
                   f"— PIL é mais maduro: provável lacuna na outra classe")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--item")
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--obra", default="Obra_TREINO_1")
    ap.add_argument("--pav", default="13_PAV")
    ap.add_argument("--project-id", default="dd238e47-1dc6-4f63-a760-4e7ce19a7386")
    ap.add_argument("--json", action="store_true", help="grava relatório estruturado")
    args = ap.parse_args()

    _dxf, sh, sn, sp, beams, pillars = load_project(
        ROOT.parent / "project_data.vision", args.project_id, args.obra, args.pav)
    niv = get_pavimento_niveis_abs(args.obra, args.pav) or {"chegada_abs": 852.19}
    nv = f"{niv.get('chegada_abs')}cm"

    # mapa nome → bbox (pilares + vigas) para resolver os apoios declarados
    mapa_pos = {}
    for P in pillars:
        xs=[q[0] for q in P["points"]]; ys=[q[1] for q in P["points"]]
        mapa_pos[P["name"]] = (min(xs), min(ys), max(xs), max(ys))
    for b in beams:
        segs = _beam_contours(b)
        if segs:
            mapa_pos.setdefault(b.get("name"), (
                min(s["x0"] for s in segs), min(s["y0"] for s in segs),
                max(s["x1"] for s in segs), max(s["y1"] for s in segs)))

    alvo = pillars if args.todos else [p for p in pillars if p["name"] == args.item]
    if not alvo:
        print("[ERR] informe --item ou --todos")
        return 2

    tot_div = 0
    relatorio = {"schema": "pil.cruzamento.v1", "obra": args.obra, "pav": args.pav,
                 "nota": "sinal para arbitragem, nunca correcao automatica; "
                         "PIL e a classe mais madura hoje (calibracao do dono 2026-08-10)",
                 "itens": []}
    for P in alvo:
        t = build_abcd_tables_from_pillar(P, slab_height_map=sh, slab_nivel_map=sn,
                                          slab_points_map=sp, beams=beams, nivel_viga_default=nv)
        cz = cruzar(P, beams, mapa_pos)
        div = comparar(cz, t)
        tot_div += len(div)
        relatorio["itens"].append({"item": P["name"], "divergencias": div,
                                   "toca": cz["toca"], "passa": cz["passa"],
                                   "aberturas_lv": cz["aberturas"]})
        if args.todos and not div:
            continue
        print(f"\n===== {P['name']} =====")
        if not args.todos:
            for x in cz["toca"]:
                print(f"  [FV] {x['viga']} seg{x['seg']}: {x['ini']} → {x['fim']}  ({x['papel']})")
            for x in cz["passa"]:
                print(f"  [FV] {x['viga']} seg{x['seg']}: {x['ini']} -> {x['fim']}  ({x['papel']})")
            for x in cz["aberturas"][:6]:
                print(f"  [LV] {x['viga']} lado {x['lado']} seg{x['seg']} {x['extremo']}: "
                      f"dist={x.get('dist')} larg={x.get('larg')}")
        for d in div:
            print(f"  ⚠ {d}")
    print(f"\n[RESUMO] divergências entre classes: {tot_div}")
    if args.todos:
        # SEMPRE gravar: regra do dono (2026-08-10) — divergência entre classes
        # nunca pode ser suprimida; o relatório alimenta o QA de PIL **e** o de
        # FV/LV, para as classes irem se harmonizando.
        out = ROOT / "scripts" / "arete" / "qa_memoria" / "cruzamento_classes.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] relatório para AMBAS as classes → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
