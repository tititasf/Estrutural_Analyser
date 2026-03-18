#!/usr/bin/env python3
"""
patch_synth_sarr.py — Gera linhas sintéticas de sarrafo para vigas sem grade explícita.

Para vigas ROCONTEC (TREINO_10/21/22/3/9) que têm labels "N 1/2pont" mas
sem linhas horizontais de sarrafo desenhadas dentro dos painéis.

Algoritmo:
  1. Para cada panel_label com padrão "N 1/2pont":
     - Extrai N (número de sarrafos)
     - Identifica face (a ou b) por posição y
     - Identifica painel por proximidade x ao centro do painel
     - Gera N linhas horizontais espaçadas uniformemente no painel
  2. Adiciona ao sarr22_lines (layer SARR_2.2x7)
  3. Só aplica a vigas com sarr22_lines sparse (< 12 por label)
"""
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

PARAMS_FILE = Path(r'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v3.json')


def parse_n_from_label(text: str) -> int | None:
    """Extrai N de strings tipo '9 1/2pont', '8 1/2', '10 pont', etc."""
    text = text.strip()
    m = re.match(r'^(\d+)\s*(1/2|½|pont|sarr)', text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.match(r'^(\d+)', text)
    if m:
        n = int(m.group(1))
        if 2 <= n <= 30:  # sanity check
            return n
    return None


def assign_label_to_panel(lx: float, panel_positions: list) -> int | None:
    """Retorna índice do painel mais próximo de lx."""
    if not panel_positions:
        return None
    best_i, best_dist = 0, float('inf')
    for i, pp in enumerate(panel_positions):
        cx = (pp['x_start'] + pp['x_end']) / 2
        d = abs(lx - cx)
        if d < best_dist:
            best_dist = d
            best_i = i
    return best_i


def generate_sarr_lines(x_start: float, x_end: float, y_min: float, y_max: float, n: int) -> list:
    """Gera N linhas horizontais espaçadas uniformemente entre y_min e y_max."""
    if n <= 0 or y_max <= y_min or x_end <= x_start:
        return []
    span = y_max - y_min
    lines = []
    for i in range(1, n + 1):
        y = y_min + (span * i / (n + 1))
        lines.append({
            'x1': x_start + 1,
            'y1': y,
            'x2': x_end - 1,
            'y2': y,
            'layer': 'SARR_2.2x7',
        })
    return lines


def face_panel_y_range(face_data: dict) -> tuple[float | None, float | None]:
    """
    Retorna (y_min, y_max) da AREA DO PAINEL (rectangle principal),
    excluindo a zona do corte de secao acima.
    Usa os hlines para encontrar os dois extremos do retangulo de painel.

    PATCH-E fix: inset 7u from hline boundaries to match where sarrafos
    are actually placed (sarrafos start ~7u above bottom hline and end
    ~7u below top hline based on TREINO_1 ground truth analysis).
    """
    y_min = face_data.get('y_min')
    y_max_full = face_data.get('y_max')
    hlines = face_data.get('face_hlines') or []
    face_w = face_data.get('total_width') or 0

    # PATCH-E: empirical analysis of TREINO_1 ground truth shows:
    #   - sarrafos start at median +0.36u from bottom wide hline (keep as-is)
    #   - sarrafos end at median -2.2u from top wide hline
    # No inset needed for y_min; small inset for y_max improves accuracy.
    INSET_TOP = 3.0  # conservative inset for top boundary

    if y_min is None:
        return None, None

    if not hlines:
        # Sem hlines: usa y_min + uma altura padrao razoavel
        return y_min, y_min + min(150, (y_max_full or y_min + 150) - y_min)

    # Encontra o hline mais alto que seja "largo" (> 30% da largura total)
    # Esse eh o topo do retangulo principal do painel
    threshold = max(face_w * 0.25, 50) if face_w > 0 else 50
    wide_hlines = [h for h in hlines if h.get('len', 0) >= threshold]

    if len(wide_hlines) >= 2:
        ys = sorted(set(h['y'] for h in wide_hlines))
        panel_y_min = min(ys)
        # Segundo y mais alto que seja bem separado do y_min (>= 5 units)
        upper_ys = [y for y in ys if y > panel_y_min + 5]
        if upper_ys:
            panel_y_max = min(upper_ys) - INSET_TOP
        else:
            panel_y_max = panel_y_min + 70  # fallback
    elif wide_hlines:
        panel_y_min = min(h['y'] for h in wide_hlines)
        panel_y_max = panel_y_min + 70  # fallback height
    else:
        panel_y_min = y_min
        panel_y_max = y_min + 70

    # Sanity: ensure y_max > y_min
    if panel_y_max <= panel_y_min:
        panel_y_max = panel_y_min + 56  # minimum panel height

    return panel_y_min, panel_y_max


def main():
    params = json.loads(PARAMS_FILE.read_text(encoding='utf-8'))

    total_synth = 0
    total_vigas = 0

    for v in params:
        panel_labels = v.get('panel_labels') or []
        if not panel_labels:
            continue

        fa = v.get('face_a') or {}
        fb = v.get('face_b') or {}

        fa_y_min, fa_y_max = face_panel_y_range(fa)
        fb_y_min, fb_y_max = face_panel_y_range(fb) if fb.get('panel_count', 0) > 0 else (None, None)

        fa_panels = fa.get('panel_positions') or []
        fb_panels = fb.get('panel_positions') or [] if fb.get('panel_count', 0) > 0 else []

        existing_sarr = v.get('sarr22_lines') or []

        # Conta sarr22 existentes que são linhas HORIZONTAIS (dy~0) dentro da face_a
        def is_horiz_in_face(l, y_min, y_max):
            if y_min is None or y_max is None:
                return False
            dy = abs(l.get('y2', 0) - l.get('y1', 0))
            y = l.get('y1', 0)
            return dy < 2 and y_min <= y <= y_max

        horiz_in_fa = sum(1 for l in existing_sarr if is_horiz_in_face(l, fa_y_min, fa_y_max))
        horiz_in_fb = sum(1 for l in existing_sarr if is_horiz_in_face(l, fb_y_min, fb_y_max))

        synth_lines = []

        for pl in panel_labels:
            text = pl.get('text', '')
            lx = pl.get('x', 0)
            ly = pl.get('y', 0)

            n = parse_n_from_label(text)
            if n is None or n < 2:
                continue

            # Determina face e painel
            # Tenta face_a primeiro, depois face_b
            face_matched = None
            panel_idx = None

            if fa_y_min is not None and fa_y_max is not None and fa_panels:
                y_center_a = (fa_y_min + fa_y_max) / 2
                if abs(ly - y_center_a) < (fa_y_max - fa_y_min) * 2:
                    if horiz_in_fa < n - 1:  # só sintetiza se não tem linhas suficientes
                        face_matched = 'a'
                        panel_idx = assign_label_to_panel(lx, fa_panels)

            if face_matched is None and fb_y_min is not None and fb_y_max is not None and fb_panels:
                y_center_b = (fb_y_min + fb_y_max) / 2
                if abs(ly - y_center_b) < (fb_y_max - fb_y_min) * 2:
                    if horiz_in_fb < n - 1:
                        face_matched = 'b'
                        panel_idx = assign_label_to_panel(lx, fb_panels)

            if face_matched is None:
                # Fallback: usa face_a se existir
                if fa_y_min is not None and fa_y_max is not None and fa_panels and horiz_in_fa < n - 1:
                    face_matched = 'a'
                    panel_idx = assign_label_to_panel(lx, fa_panels)

            if face_matched is None or panel_idx is None:
                continue

            if face_matched == 'a':
                panels = fa_panels
                y_min = fa_y_min
                y_max = fa_y_max
            else:
                panels = fb_panels
                y_min = fb_y_min
                y_max = fb_y_max

            pp = panels[panel_idx]
            new_lines = generate_sarr_lines(pp['x_start'], pp['x_end'], y_min, y_max, n)

            if not new_lines:
                continue
            # Verifica se já existem linhas similares neste painel (evitar duplicatas)
            existing_in_panel = [
                l for l in existing_sarr + synth_lines
                if abs(l.get('y1', 0) - new_lines[0]['y1']) < 5 and
                   l.get('x1', 0) >= pp['x_start'] - 5 and l.get('x2', 0) <= pp['x_end'] + 5
            ]
            if existing_in_panel:
                continue

            synth_lines.extend(new_lines)

        if synth_lines:
            v['sarr22_lines'] = existing_sarr + synth_lines
            total_synth += len(synth_lines)
            total_vigas += 1
            viga = v.get('viga', '?')
            obra = v.get('obra', '?')
            print(f'  {obra}/{viga}: +{len(synth_lines)} linhas sintéticas')

    PARAMS_FILE.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nTotal: {total_synth} linhas sintéticas em {total_vigas} vigas. Salvo: {PARAMS_FILE}')


if __name__ == '__main__':
    main()
