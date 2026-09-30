# -*- coding: utf-8 -*-
"""
gerar_lv_n4_fichas.py — Gera DXF N4 LV direto de fichas_lv_v2.json (bypass DB).

Materializa uma pasta temporária com Fase-4 JSON + fichas_lv_v2.json
e chama gerar_lv_dxf_stog.py para cada viga.

Uso:
    python gerar_lv_n4_fichas.py            # gera todos os 32
    python gerar_lv_n4_fichas.py V301       # gera só V301
    python gerar_lv_n4_fichas.py V301 V303  # gera lista
"""

from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import ezdxf
from pathlib import Path

SCRIPTS  = Path(__file__).resolve().parent.parent   # .../scripts/
REPO     = SCRIPTS.parent                            # .../Agente-cad-PYSIDE-Restored-main/
GERADOR  = SCRIPTS / 'gerar_lv_dxf_stog.py'
GERADOR_N4 = Path(__file__).resolve().parent / 'run_lv_generator_n4.py'


def _materialize_dimension_text_overrides(path: Path) -> None:
    """Regrava blocos DIMENSION com o texto contratual já armazenado."""
    doc = ezdxf.readfile(str(path))
    changed = False
    for dim in doc.modelspace().query('DIMENSION'):
        text = str(dim.dxf.get('text', '') or '')
        if not text or text == '<>':
            continue
        dim.override().render()
        changed = True
    if changed:
        doc.saveas(str(path))

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO))

from src.core.lv_draw_contract import LVDrawContractError, validate_n4_ficha
from lv_n4_face_unit_details import augment_face_unit_details

OBRA_DIR    = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1")
FICHAS_PATH = OBRA_DIR / "Fase-6_Execucao_CAD/granular/fichas/fichas_lv_v2.json"
N4_OUT      = OBRA_DIR / "Fase-6_Execucao_CAD/n4"
PROJECT_DB  = Path("D:/Agente-cad-PYSIDE/project_data.vision")


def _entry_from_motor_ficha(elem: str, ficha: dict) -> dict:
    """Converte a ficha live do motor no contrato fichas_lv_v2."""
    h_a = float(ficha.get('h_A', ficha.get('h_cm', 0)) or 0)
    h_b = float(ficha.get('h_B', ficha.get('h_B_cm', h_a)) or h_a)
    b = float(ficha.get('b_geom', ficha.get('b_cm', 19)) or 19)
    lj_sup_a = float(ficha.get('laje_sup_A', 0) or 0)
    lj_inf_a = float(ficha.get('laje_inf_A', 0) or 0)
    lj_sup_b = float(ficha.get('laje_sup_B', 0) or 0)
    lj_inf_b = float(ficha.get('laje_inf_B', 0) or 0)

    # Propagar laje_sup/inf do motor para face_units (o motor calcula via fallback
    # de seção mas não atualiza o campo laje_sup dentro de cada face_unit)
    raw_fus = ficha.get('face_units', [])
    face_units = []
    for fu in raw_fus:
        fu = dict(fu)  # cópia rasa
        side = str(fu.get('side', '')).upper()
        if side == 'A':
            if 'laje_sup' not in fu and lj_sup_a > 0:
                fu['laje_sup'] = lj_sup_a
            if 'laje_inf' not in fu and lj_inf_a > 0:
                fu['laje_inf'] = lj_inf_a
        elif side == 'B':
            if 'laje_sup' not in fu and lj_sup_b > 0:
                fu['laje_sup'] = lj_sup_b
            if 'laje_inf' not in fu and lj_inf_b > 0:
                fu['laje_inf'] = lj_inf_b
        face_units.append(fu)

    return {
        'viga': elem,
        'face': 'A',
        'h_cm': h_a,
        'h_B_cm': h_b,
        'b_cm': b,
        'laje_sup_cm': lj_sup_a,
        'laje_inf_cm': lj_inf_a,
        'laje_sup_B_cm': lj_sup_b,
        'laje_inf_B_cm': lj_inf_b,
        'h_section_cm': float(ficha.get('h_section', 55) or 55),
        'h_section_all': ficha.get('h_section_all', []),
        'tipo_viga': ficha.get('tipo_viga', 'sarrafeada'),
        'section_views': ficha.get('section_views', []),
        'face_units': face_units,
        'segmentos': ficha.get('panels_A', ficha.get('segmentos', [])),
        'segmentos_B': ficha.get('panels_B', ficha.get('segmentos_B', [])),
        'pillar_left': ficha.get('pillar_left', {'active': False}),
        'pillar_right': ficha.get('pillar_right', {'active': False}),
    }


def _entry_from_live_recorte(elem: str) -> dict | None:
    """Lê novamente o recorte N2 aprovado antes de materializar o N4.

    ``fichas_lv_v2.json`` é um cache regenerável. Ele pode ter sido produzido
    por uma versão anterior do reverso e, nesse caso, conter painel/cota que já
    não existe no recorte humano. N4 deve sempre preferir a extração atual do
    próprio recorte aprovado; o cache continua como fallback seguro se o DB ou
    a extração não estiverem disponíveis.
    """
    try:
        import sqlite3
        from motor_reverso_lv import extrair_ficha_lateral_viga

        if not PROJECT_DB.is_file():
            return None
        with sqlite3.connect(PROJECT_DB) as conn:
            row = conn.execute(
                """
                SELECT recorte_path
                  FROM reverse_eng_recortes
                 WHERE UPPER(elemento_id) = ? AND UPPER(classe) = 'LV'
                 ORDER BY id DESC
                 LIMIT 1
                """,
                (str(elem).upper(),),
            ).fetchone()
        if not row:
            return None
        ficha = extrair_ficha_lateral_viga(str(row[0]), f"{elem}_A")
        confidence = float(ficha.get("_confianca", 0.0) or 0.0)
        if confidence < 0.55 or not ficha.get("panels_A"):
            return None
        return _entry_from_motor_ficha(elem, ficha)
    except Exception as exc:
        print(f"[{elem}] recorte N2 live indisponível: {exc}")
        return None


def _make_fake_fase4(viga_name: str, entry: dict, fase4_dir: Path) -> None:
    """Cria _A.json e _B.json fake na pasta Fase-4 a partir da ficha."""
    elem_base = viga_name

    def _panels_to_gerador(segs: list, h_face: float) -> list:
        return [
            {
                'width':            float(s.get('largura_cm', s.get('width', 0)) or 0),
                'height1':          float(s.get('height1', h_face) or h_face),
                'height2':          float(s.get('height2', 0) or 0),
                'grade_h1':         float(s.get('grade_h1', 0) or 0),
                'grade_h2':         float(s.get('grade_h2', 0) or 0),
                'laje_central_alt': float(s.get('laje_central_alt', 0) or 0),
                'laje_sup_local':   float(s.get('laje_sup_local', s.get('slab_top', 0)) or 0),
                'laje_inf_local':   float(s.get('laje_inf_local', s.get('slab_bottom', 0)) or 0),
                'slab_top':         float(s.get('slab_top', s.get('laje_sup_local', 0)) or 0),
                'slab_bottom':      float(s.get('slab_bottom', s.get('laje_inf_local', 0)) or 0),
                'holes':            s.get('holes', []),
                'reuse':            bool(s.get('reuse', False)),
                'reuse_regions':    s.get('reuse_regions', []),
                'panel_type':       s.get('panel_type', 'Sarrafeado'),
            }
            for s in segs if float(s.get('largura_cm', s.get('width', 0)) or 0) > 0
        ]

    h_A = float(entry.get('h_cm', 0) or 0)
    h_B = float(entry.get('h_B_cm', h_A) or h_A)
    b   = float(entry.get('b_cm', 19.0) or 19.0)

    common = {
        'total_width':  b,
        'total_height': h_A,
        'b_geom':       b,
        'h_A':          h_A,
        'h_B':          h_B,
        'h_section':    float(entry.get('h_section_cm', 55.0) or 55.0),
        'laje_sup_A':   float(entry.get('laje_sup_cm', 0) or 0),
        'laje_inf_A':   float(entry.get('laje_inf_cm', 0) or 0),
        'laje_sup_B':   float(entry.get('laje_sup_B_cm', 0) or 0),
        'laje_inf_B':   float(entry.get('laje_inf_B_cm', 0) or 0),
        'tipo_viga':    entry.get('tipo_viga', 'sarrafeada'),
        'continuation': entry.get('continuation', ''),
        'text_left':    entry.get('text_left', ''),
        'text_right':   entry.get('text_right', ''),
        'floor':        '13_PAV',
        'holes':        entry.get('holes', []),
        'pillar_left':  entry.get('pillar_left', {'active': False, 'width': 0.0, 'length': 0.0}),
        'pillar_right': entry.get('pillar_right', {'active': False, 'width': 0.0, 'length': 0.0}),
        'generation_ready': True,
        'draw_contract': entry.get('_motor_contract', {}),
    }

    # Fase-4 _A.json
    json_a = dict(common)
    json_a['side']   = 'A'
    json_a['name']   = elem_base + '_A'
    json_a['number'] = re.sub(r'[^\d]', '', elem_base) or '0'
    units = entry.get('face_units', [])
    def _segments_for_side(side: str) -> list:
        collected = []
        for unit in units:
            if str(unit.get('side') or '').upper() == side:
                collected.extend(unit.get('segments') or unit.get('panels') or [])
        return collected

    segs_a = entry.get('segmentos', []) or _segments_for_side('A')
    json_a['panels'] = _panels_to_gerador(segs_a, h_A)
    json_a['panels_A'] = json_a['panels']
    segs_b = entry.get('segmentos_B', []) or _segments_for_side('B')
    json_a['panels_B'] = _panels_to_gerador(segs_b, h_B)
    json_a['face_units'] = entry.get('face_units', [])
    json_a['section_views'] = entry.get('section_views', [])

    path_a = fase4_dir / f"{elem_base}_A.json"
    path_a.write_text(json.dumps(json_a, indent=2, ensure_ascii=False), encoding='utf-8')

    # Fase-4 _B.json
    json_b = dict(common)
    json_b['side']   = 'B'
    json_b['name']   = elem_base + '_B'
    json_b['number'] = re.sub(r'[^\d]', '', elem_base) or '0'
    json_b['total_height'] = h_B
    json_b['panels'] = _panels_to_gerador(segs_b, h_B) or json_a['panels']
    json_b['panels_A'] = json_a.get('panels_A', [])
    json_b['panels_B'] = json_b['panels']
    json_b['face_units'] = entry.get('face_units', [])
    json_b['section_views'] = entry.get('section_views', [])

    path_b = fase4_dir / f"{elem_base}_B.json"
    path_b.write_text(json.dumps(json_b, indent=2, ensure_ascii=False), encoding='utf-8')


def gerar_lv_n4(elem: str, entry: dict,
                out_dir: Path = N4_OUT,
                tmp_root: Path | None = None,
                visual_mode: str = 'NOVA') -> dict:
    """Gera N4 para 1 viga. Retorna {ok, dxf_path, log}."""
    result = {
        'elem': elem,
        'ok': False,
        'dxf_path': None,
        'view_paths': {},
        'log': '',
    }

    try:
        entry = validate_n4_ficha(entry, item=elem)
    except LVDrawContractError as exc:
        result['log'] = f'[CONTRATO N4 INVALIDO] {exc}'
        return result

    tmp_base = Path(tmp_root) if tmp_root else Path(tempfile.mkdtemp(prefix='lv_n4_'))
    obra_dir = tmp_base / f"LV_13PAV_{elem}"
    obra_dir.mkdir(parents=True, exist_ok=True)

    # Fase-4 dir
    fase4_dir = obra_dir / 'Fase-4_Sincronizacao' / 'JSON_Vigas_Laterais'
    fase4_dir.mkdir(parents=True, exist_ok=True)
    _make_fake_fase4(elem, entry, fase4_dir)

    # fichas_lv_v2.json local (só esta viga, para o gerador ter precedência)
    fichas_dir = obra_dir / 'Fase-6_Execucao_CAD' / 'granular' / 'fichas'
    fichas_dir.mkdir(parents=True, exist_ok=True)
    (fichas_dir / 'fichas_lv_v2.json').write_text(
        json.dumps([entry], indent=2, ensure_ascii=False), encoding='utf-8'
    )

    # Pasta de saída
    out_fase6 = obra_dir / 'Fase-6_Execucao_CAD'
    out_fase6.mkdir(exist_ok=True)

    # Gerar o combinado e os três artefatos dedicados. O Comparison Engine
    # usa CORTE/A/B separadamente; depender do bbox do combinado deixa Corte
    # preto quando a seção fica fora do autofit.
    base_cmd = [
        sys.executable, str(GERADOR_N4),
        '--obra', str(obra_dir),
        '--item', elem + '_A',
        '--max', '1',
        '--visual-mode', visual_mode,
        '--strict-contract',
    ]
    try:
        for view in ('ALL', 'CORTE', 'A', 'B'):
            r = subprocess.run(
                [*base_cmd, '--view', view], capture_output=True, text=True,
                timeout=90, cwd=str(REPO),
            )
            result['log'] += (r.stdout or '') + (r.stderr or '')
            if r.returncode != 0:
                result['log'] += f'\n[{view} rc={r.returncode}]'
                return result
            suffix = {
                'ALL': f'{elem}_A', 'CORTE': f'{elem}_CORTE',
                'A': f'{elem}_VIEW_A', 'B': f'{elem}_VIEW_B',
            }[view]
            generated_view = out_fase6 / f'LV_preview_{suffix}.dxf'
            if generated_view.exists():
                augment_face_unit_details(generated_view, entry, view, GERADOR)

        # O gerador define overrides como 65/44/59 depois da primeira
        # renderizacao da DIMENSION. Materialize esses textos nos blocos
        # graficos antes de publicar os quatro artefatos.
        for generated in out_fase6.glob(f'LV_preview_{elem}_*.dxf'):
            _materialize_dimension_text_overrides(generated)

        # Copiar DXF N4 para out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        dxf_src = out_fase6 / f"LV_preview_{elem}_A.dxf"
        if not dxf_src.exists():
            # tentar nome sem _A
            cands = list(out_fase6.glob(f"LV_*{elem}*.dxf"))
            dxf_src = cands[0] if cands else None

        if dxf_src and dxf_src.exists():
            dxf_dst = out_dir / dxf_src.name
            if dxf_src.resolve() != dxf_dst.resolve():
                shutil.copy2(dxf_src, dxf_dst)
            result['dxf_path'] = str(dxf_dst)
            result['view_paths']['ALL'] = str(dxf_dst)

            for view, suffix in (
                ('CORTE', 'CORTE'), ('A', 'VIEW_A'), ('B', 'VIEW_B'),
            ):
                src = out_fase6 / f"LV_preview_{elem}_{suffix}.dxf"
                if not src.exists():
                    result['log'] += f'\n[{view} DXF não encontrado em {out_fase6}]'
                    return result
                dst = out_dir / src.name
                if src.resolve() != dst.resolve():
                    shutil.copy2(src, dst)
                result['view_paths'][view] = str(dst)

            result['ok'] = True
        else:
            result['log'] += f'\n[DXF não encontrado em {out_fase6}]'
    except subprocess.TimeoutExpired:
        result['log'] = '[TIMEOUT]'
    except Exception as e:
        result['log'] = str(e)

    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('elementos', nargs='*', help='V301 V303 ...')
    parser.add_argument('--out', default=str(N4_OUT))
    parser.add_argument('--obra', default=str(OBRA_DIR))
    parser.add_argument('--entry-json',
                        help='Ficha live do motor para um unico elemento')
    parser.add_argument('--visual-mode', choices=['NOVA', 'INI'], default='NOVA',
                        help='Perfil visual do DXF (padrao: NOVA)')
    parser.add_argument(
        '--refresh-from-recorte', action='store_true',
        help='Reextrai a ficha do recorte N2 antes de gerar. Por padrao, a '
             'ficha fornecida e autoritativa e nao e substituida.',
    )
    args = parser.parse_args()

    if args.entry_json:
        raw_entry = json.loads(
            Path(args.entry_json).read_text(encoding='utf-8'))
        elem = args.elementos[0] if args.elementos else (
            raw_entry.get('viga') or raw_entry.get('name'))
        if not elem:
            raise SystemExit('Elemento ausente em --entry-json')
        entry = (
            raw_entry if raw_entry.get('viga')
            else _entry_from_motor_ficha(elem, raw_entry)
        )
        if args.refresh_from_recorte:
            entry = _entry_from_live_recorte(elem) or entry
        fichas_map = {elem: entry}
    else:
        fichas_path = (
            Path(args.obra)
            / "Fase-6_Execucao_CAD/granular/fichas/fichas_lv_v2.json"
        )
        fichas = json.loads(fichas_path.read_text(encoding='utf-8'))
        fichas_map = {e['viga']: e for e in fichas}

    elems = args.elementos or sorted(fichas_map.keys())
    out_dir = Path(args.out)

    ok = 0
    for elem in elems:
        # N4 rigido: a ficha selecionada e a entrada autoritativa. Reextracao
        # pertence ao interpretador e precisa ser solicitada explicitamente.
        entry = fichas_map.get(elem)
        if args.refresh_from_recorte:
            entry = _entry_from_live_recorte(elem) or entry
        if not entry:
            print(f'[{elem}] Não encontrado em fichas_lv_v2.json')
            continue
        print(f'[{elem}] gerando...', end=' ', flush=True)
        r = gerar_lv_n4(elem, entry, out_dir, visual_mode=args.visual_mode)
        if r['ok']:
            ok += 1
            print(f'OK => {r["dxf_path"]}')
        else:
            print(f'FAIL')
            print(r['log'][-200:] if r['log'] else '(sem log)')

    print(f'\n{ok}/{len(elems)} OK | N4 em: {out_dir}')
