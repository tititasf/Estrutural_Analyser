# -*- coding: utf-8 -*-
"""Regua N3 x N4 das laterais de viga.

O N4 (gerado a partir do N2, a ficha extraida do desenho humano) e' a
REFERENCIA: as vigas listadas em `APROVADAS` foram validadas pelo dono segmento
a segmento. O N3 nasce do N1/SA e hoje nao chega perto. Este script mede a
distancia com numero, para que o refino do SA tenha criterio de pronto em vez
de impressao.

Nao escreve nada. Le o DB de producao e o recorte N2 vivo.

Uso:
    python scripts/arete/comparar_lv_n3_n4.py
    python scripts/arete/comparar_lv_n3_n4.py V301 V304 --detalhe
    python scripts/arete/comparar_lv_n3_n4.py --projeto <uuid>
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ARETE = Path(__file__).resolve().parent
SCRIPTS = ARETE.parent
REPO = SCRIPTS.parent
for _p in (REPO, SCRIPTS, ARETE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from src.core.lv_generation_contract import (  # noqa: E402
    build_lv_generation_contracts,
)

DB = Path('D:/Agente-cad-PYSIDE/project_data.vision')

# `torre_1` do TMC-EST-PE-6000-13P-R03 — o projeto que a pagina do portal abre.
PROJETO_13PAV = 'dd238e47-1dc6-4f63-a760-4e7ce19a7386'

# Vigas com N4 aprovado pelo dono, na ordem em que foram fechadas.
# V13 NAO entra: ela nao existe neste projeto (esta' em TMC-EST-EX-5000-TIP).
APROVADAS = ('V301', 'V302', 'V303', 'V304')

TOL = 1.0   # cm

# Comportamento que o N4 do corpus representa. DECLARACAO DO DONO
# (2026-09-20): "das vigas que fizemos tinha aberturas de pilar, entao
# provavelmente todo N4 e' na convencao de vigas PASSAM".
#
# Nao consegui confirmar isso na ficha N4 e registro o porque: `holes`
# (abertura de pilar) sai ZERO nas cinco — mas isso e' gap de extracao
# conhecido, entao ausencia ali nao prova nada; e o vao de `pilar + 22` entre
# corridas de sarrafo, que e' a assinatura descrita no guia, so' aparece em
# V302.A (150, 36) e V304.A (41, 34) — nas outras oito faces nao ha' vao.
#
# Fica como declaracao, nao como medicao. `None` volta a escolher o
# comportamento que chega mais perto do N4.
COMPORTAMENTO = 'Passa'


def _carregar_n3(projeto: str, vigas: tuple[str, ...]) -> dict:
    """Contratos N3 por viga, direto do N1 (beams.data_json.links)."""
    with sqlite3.connect(str(DB)) as conn:
        bboxes = {}
        for nome, pts_raw in conn.execute(
                'SELECT name, points_json FROM pillars WHERE project_id=?',
                (projeto,)):
            try:
                pts = json.loads(pts_raw or '[]')
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                if xs and ys:
                    bboxes[str(nome)] = (min(xs), min(ys), max(xs), max(ys))
            except Exception:
                continue
        out = {}
        for viga in vigas:
            row = conn.execute(
                'SELECT data_json FROM beams WHERE project_id=? AND name=?',
                (projeto, viga),
            ).fetchone()
            if not row:
                out[viga] = None
                continue
            beam = json.loads(row[0] or '{}')
            out[viga] = {
                'contratos': build_lv_generation_contracts(
                    beam, beam_name=viga, floor='13_PAV',
                    pillar_bboxes=bboxes,
                ),
                'fields': beam.get('fields') or {},
                'dimensao_rotulo': (beam.get('fields') or {}).get('dimensao'),
            }
    return out


def _carregar_n4(vigas: tuple[str, ...]) -> dict:
    """Ficha N4 por viga, do recorte N2 vivo (a referencia aprovada)."""
    from arete.gerar_lv_n4_fichas import _entry_from_live_recorte
    out = {}
    for viga in vigas:
        try:
            entrada = _entry_from_live_recorte(viga)
        except Exception as exc:                     # pragma: no cover
            out[viga] = {'erro': str(exc)}
            continue
        lados = {}
        for lado in ('A', 'B'):
            unidades = [u for u in (entrada.get('face_units') or [])
                        if str(u.get('side') or '').upper() == lado]
            larguras = []
            for u in unidades:
                larguras += [round(float(p.get('width', 0) or 0), 1)
                             for p in (u.get('panels') or [])]
            # Altura de referencia = h_TOTAL da unidade (corpo + laje), que e'
            # o que a regra rigida `secao + 4` prediz. O campo `h_cm` da ficha
            # NAO serve: medido nas cinco aprovadas, as vezes ele traz o total
            # (V13 59, V301 124) e as vezes so' o corpo (V302 43 com laje 16,
            # V303.A 43 com laje 15) — comparar contra ele e' somar pera com
            # maca. Com `h_total` a regra fecha nas cinco:
            #   V13 55+4=59 | V301 120+4=124 | V302 55+4=59 | V303 55+4=58/59
            alturas = sorted({round(float(u.get('h_total') or 0), 1)
                              for u in unidades if float(u.get('h_total') or 0) > 0})
            lados[lado] = {
                'desenhos': len(unidades),
                'larguras': larguras,
                'total': round(sum(larguras), 1),
                'h': max(alturas) if alturas else 0.0,
                'alturas': alturas,
            }
        out[viga] = {
            'lados': lados,
            'secao_n2': entrada.get('h_section_all'),
            'b': entrada.get('b_cm'),
        }
    return out


def _cmp_multiset(a: list[float], b: list[float]) -> tuple[int, int]:
    """(quantos do A sem par em B, quantos do B sem par em A), com tolerancia."""
    restante = list(b)
    sobra_a = 0
    for valor in a:
        alvo = next((x for x in restante if abs(x - valor) <= TOL), None)
        if alvo is None:
            sobra_a += 1
        else:
            restante.remove(alvo)
    return sobra_a, len(restante)


def comparar(vigas: tuple[str, ...], projeto: str, detalhe: bool = False) -> int:
    n3 = _carregar_n3(projeto, vigas)
    n4 = _carregar_n4(vigas)

    print()
    print('REGUA N3 x N4 — laterais de viga')
    print(f'projeto {projeto}')
    print(f'referencia: N4 das vigas aprovadas pelo dono  |  tolerancia {TOL} cm')
    print('comportamento cobrado: '
          + (f'{COMPORTAMENTO}  (DECLARADO pelo dono, nao medido — ver topo '
             'do arquivo)' if COMPORTAMENTO
             else 'o que chegar mais perto do N4'))
    print()

    pendencias = 0
    for viga in vigas:
        item3, item4 = n3.get(viga), n4.get(viga)
        print(f'=== {viga} ' + '=' * 58)
        if item3 is None:
            print('   N3: viga AUSENTE neste projeto (sem linha em beams)')
            pendencias += 1
            continue
        if not item4 or item4.get('erro'):
            print(f'   N4: indisponivel ({(item4 or {}).get("erro")})')
            pendencias += 1
            continue

        ct = item3['contratos']
        print(f'   secao: rotulo da viga = {item3["dimensao_rotulo"]}  |  '
              f'N2 mede {item4["secao_n2"]}  |  b_N2 = {item4["b"]}')

        for lado in ('A', 'B'):
            ref = item4['lados'][lado]
            # O N4 e' UM desenho, logo corresponde a UM comportamento. Cobrar
            # `Para` e `Passa` ao mesmo tempo conta erro onde nao ha': por
            # construcao um dos dois TEM de divergir. A regua mede os dois,
            # marca qual chega mais perto (`<<`) e cobra so' esse.
            #
            # Quando os dois saem IDENTICOS (`==`) o desenho nao os distingue,
            # e' esperado em viga curta que nao cruza pilar (regra do dono,
            # 2026-09-20) e nao ha' o que escolher.
            medidas = {}
            for comportamento in ('Para', 'Passa'):
                c = ct[comportamento][lado]
                larg3 = [round(float(p['width']), 1) for p in c['panels']]
                falta, sobra = _cmp_multiset(larg3, ref['larguras'])
                dh = float(c['total_height'] or 0) - ref['h']
                dt = float(c['total_length'] or 0) - ref['total']
                medidas[comportamento] = {
                    'larg': larg3, 'falta': falta, 'sobra': sobra,
                    'h': float(c['total_height'] or 0), 'dh': dh, 'dt': dt,
                    'total': float(c['total_length'] or 0),
                    # Distancia ao N4. Painel sem par pesa mais que centimetro
                    # de comprimento: e' diferenca de DIVISAO, nao de medida.
                    'dist': abs(dh) + abs(dt) / 100.0 + 10.0 * (falta + sobra),
                }
            empate = (medidas['Para']['larg'] == medidas['Passa']['larg']
                      and abs(medidas['Para']['dt']
                              - medidas['Passa']['dt']) <= 0.05)
            if COMPORTAMENTO:
                melhor = COMPORTAMENTO
            else:
                melhor = min(medidas, key=lambda k: medidas[k]['dist'])
            for comportamento in ('Para', 'Passa'):
                m = medidas[comportamento]
                ok = (abs(m['dh']) <= TOL and abs(m['dt']) <= TOL
                      and m['falta'] == 0 and m['sobra'] == 0)
                marca = ('==' if empate
                         else '<<' if comportamento == melhor else '  ')
                if COMPORTAMENTO and comportamento == COMPORTAMENTO:
                    marca = '==' if empate else '**'
                print(
                    f'   {lado} {comportamento:5s} {marca} '
                    f'{"OK " if ok else "DIF"} | '
                    f'h {m["h"]:6.1f} vs {ref["h"]:6.1f} ({m["dh"]:+6.1f}) | '
                    f'total {m["total"]:8.1f} vs '
                    f'{ref["total"]:8.1f} ({m["dt"]:+8.1f}) | '
                    f'paineis {len(m["larg"]):3d} vs {len(ref["larguras"]):3d} '
                    f'(so N3 {m["falta"]}, so N4 {m["sobra"]})'
                )
                if detalhe and (empate or comportamento == melhor):
                    print(f'        N3: {m["larg"]}')
                    print(f'        N4: {ref["larguras"]}  '
                          f'({ref["desenhos"]} desenhos)')
            if empate:
                print('        (Para e Passa IDENTICOS — o desenho nao os '
                      'distingue)')
            # UMA pendencia por lado: a do comportamento escolhido.
            mm = medidas[melhor]
            if not (abs(mm['dh']) <= TOL and abs(mm['dt']) <= TOL
                    and mm['falta'] == 0 and mm['sobra'] == 0):
                pendencias += 1
            fonte = ct['Para'][lado]['_sa_meta']['dimension_source']
            print(f'        fonte da dimensao = {fonte}  |  '
                  f'h_section = {ct["Para"][lado]["h_section"]}  |  '
                  f'regra = {ct["Para"][lado]["h_face_rule"]}  |  '
                  f'alturas medidas no N4 = {ref["alturas"]}')

        # Sinais de isolamento que o contrato promete (PROVENIENCIA-CAMPOS-LV).
        a_para = [round(float(p['width']), 1) for p in ct['Para']['A']['panels']]
        b_para = [round(float(p['width']), 1) for p in ct['Para']['B']['panels']]
        if a_para == b_para:
            print('        !! lado A e lado B saem IDENTICOS no N3 '
                  '(o contrato exige faces nao intercambiaveis)')
        print()

    print(f'lados com diferenca: {pendencias} de {len(vigas)*2}  '
          f'(um comportamento por lado — o N4 e UM desenho)')
    return 0 if pendencias == 0 else 1


def main() -> int:
    global DB, COMPORTAMENTO
    ap = argparse.ArgumentParser()
    ap.add_argument('vigas', nargs='*', default=list(APROVADAS))
    ap.add_argument('--projeto', default=PROJETO_13PAV)
    ap.add_argument('--detalhe', action='store_true',
                    help='lista as larguras dos paineis dos dois lados')
    ap.add_argument('--comportamento', default=COMPORTAMENTO,
                    choices=['Para', 'Passa', 'melhor'],
                    help='qual comportamento o N4 representa (declaracao do '
                         'dono; "melhor" escolhe o que chega mais perto)')
    ap.add_argument('--db', default=str(DB),
                    help='DB a ler (use uma COPIA para testar refino do SA '
                         'sem tocar em producao)')
    args = ap.parse_args()
    DB = Path(args.db)
    COMPORTAMENTO = (None if args.comportamento == 'melhor'
                     else args.comportamento)
    return comparar(tuple(args.vigas or APROVADAS), args.projeto, args.detalhe)


if __name__ == '__main__':
    raise SystemExit(main())
