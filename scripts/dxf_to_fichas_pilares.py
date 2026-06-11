"""
DXF PL (Planta de Fôrma de Pilares) → fichas_pilares.json (FichaFase3Pilar)

Pipeline:
1. Lê DXF real da obra
2. Extrai todos os pilares: nome, comprimento, largura, PD, níveis
3. Gera fichas_pilares.json compatível com fase3_to_fase4_pilares.py

Uso:
    python scripts/dxf_to_fichas_pilares.py \
        --dxf "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/.../ALIMONTI.dxf" \
        --obra "ALIMONTI PARAISO 1PAV" \
        --pavimento "1_PAVIMENTO" \
        --output "D:/Agente-cad-PYSIDE/output_fichas/fichas_pilares.json"
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import ezdxf, math, re, json, argparse, os
from collections import defaultdict

def dist2d(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)


def clusterizar(ocorrencias, raio=1500):
    clusters = []
    for o in ocorrencias:
        colocado = False
        for cl in clusters:
            cx = sum(x['pos'][0] for x in cl) / len(cl)
            cy = sum(x['pos'][1] for x in cl) / len(cl)
            if dist2d(o['pos'], (cx, cy)) < raio:
                cl.append(o)
                colocado = True
                break
        if not colocado:
            clusters.append([o])
    return clusters


def extrair_pilares(dxf_path: str, nome_obra: str, pavimento: str) -> list[dict]:
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    # ── Coleta textos "Texto Seção" ──────────────────────────────────
    secoes_raw = []
    for e in msp:
        if e.dxftype() == 'TEXT' and e.dxf.layer == 'Texto Seção':
            txt = e.dxf.text.strip()
            m = re.match(r'^(P\d+)\.([A-H])$', txt)
            if m:
                secoes_raw.append({
                    'pid': m.group(1),
                    'face': m.group(2),
                    'pos': (e.dxf.insert[0], e.dxf.insert[1]),
                })

    # ── Pré-indexa linhas Painéis ─────────────────────────────────────
    paineis_lines = []
    for e in msp:
        if e.dxftype() == 'LINE' and e.dxf.layer == 'Painéis':
            dx = abs(e.dxf.end[0]-e.dxf.start[0])
            dy = abs(e.dxf.end[1]-e.dxf.start[1])
            L = round(math.sqrt(dx*dx+dy*dy), 1)
            orient = 'H' if dx > dy else 'V'
            mp = ((e.dxf.start[0]+e.dxf.end[0])/2, (e.dxf.start[1]+e.dxf.end[1])/2)
            paineis_lines.append({'mp': mp, 'L': L, 'orient': orient})

    # ── Pré-indexa NOMENCLATURA ───────────────────────────────────────
    nomenclaturas = []
    for e in msp:
        if e.dxftype() == 'MTEXT' and e.dxf.layer == 'NOMENCLATURA':
            pos = e.dxf.insert
            txt = e.text
            m_pd = re.search(r'PD:\s*([\d.]+)', txt)
            m_saida = re.search(r'N[IÍ]VEL DE SA[IÍ]DA:\s*([\d.]+)', txt, re.IGNORECASE)
            m_chegada = re.search(r'N[IÍ]VEL DE CHEGADA:\s*([\d.]+)', txt, re.IGNORECASE)
            m_pav = re.search(r'([\d°º]+\s*PAVIMENTO|T[ÉE]RREO|COBERTURA|SUBSOLO)', txt, re.IGNORECASE)
            if m_pd:
                nomenclaturas.append({
                    'pos': (pos[0], pos[1]),
                    'pd': float(m_pd.group(1)),
                    'saida': float(m_saida.group(1)) if m_saida else None,
                    'chegada': float(m_chegada.group(1)) if m_chegada else None,
                    'pav_txt': m_pav.group(1).strip() if m_pav else '',
                })

    # ── Funções de extração ────────────────────────────────────────────
    def get_face_width(face_pos, raio=150):
        from collections import Counter
        candidatas = []
        for pl in paineis_lines:
            if dist2d(pl['mp'], face_pos) < raio and pl['orient'] == 'H':
                candidatas.append(pl['L'])
        if not candidatas and raio < 350:
            return get_face_width(face_pos, raio=350)
        if not candidatas:
            return None
        c = Counter(round(v, 0) for v in candidatas)
        return c.most_common(1)[0][0]

    def get_nomenclatura(cluster_center, raio=2500):
        """Retorna NOMENCLATURA mais próxima, filtrando textos abaixo das faces."""
        cy = cluster_center[1]
        best = None
        best_d = 9999999
        for n in nomenclaturas:
            # Aceita apenas NOMENCLATURA que esteja próxima ou acima do cluster
            # (y_nom >= cy - 500 para excluir títulos de grupos abaixo)
            if n['pos'][1] < cy - 500:
                continue
            d = dist2d(n['pos'], cluster_center)
            if d < raio and d < best_d:
                best_d = d
                best = n
        # Fallback sem filtro de y
        if best is None:
            for n in nomenclaturas:
                d = dist2d(n['pos'], cluster_center)
                if d < raio and d < best_d:
                    best_d = d
                    best = n
        return best

    # ── Agrupa por pilar ───────────────────────────────────────────────
    pilares_raw = defaultdict(list)
    for s in secoes_raw:
        pilares_raw[s['pid']].append(s)

    # ── Extrai dimensões ───────────────────────────────────────────────
    fichas = []
    for pid in sorted(pilares_raw.keys(), key=lambda x: int(re.search(r'\d+', x).group())):
        clusters = clusterizar(pilares_raw[pid])
        for idx, cl in enumerate(clusters):
            cx = sum(o['pos'][0] for o in cl) / len(cl)
            cy = sum(o['pos'][1] for o in cl) / len(cl)
            center = (cx, cy)

            # Larguras por face
            face_widths = {}
            for o in cl:
                w = get_face_width(o['pos'])
                if w is not None:
                    face_widths[o['face']] = w

            widths = list(face_widths.values())
            comprimento = round(max(widths), 0) if widths else 0.0
            largura = round(min(widths), 0) if widths else 0.0

            # Garante convenção comprimento >= largura
            if largura > comprimento:
                comprimento, largura = largura, comprimento

            # Faces encontradas
            faces_found = sorted(set(o['face'] for o in cl))
            n_faces = len(faces_found)

            # Pilar especial: 5+ faces = L/T/U
            pilar_especial = n_faces > 4
            tipo_especial = "L" if n_faces in (5, 6) else ("T" if n_faces in (7, 8) else "L")

            # NOMENCLATURA → PD, níveis
            nom = get_nomenclatura(center)
            if nom:
                pd = nom['pd']
                saida = nom['saida']
                chegada = nom['chegada']
                pav_txt = nom['pav_txt']
            else:
                pd = 3.0
                saida = None
                chegada = None
                pav_txt = ''

            altura_cm = round(pd * 100, 0)
            nivel_saida = saida if saida is not None else 0.0
            nivel_chegada = chegada if chegada is not None else round(pd, 2)

            # Confidence: baseada na completude dos dados
            confianca = 1.0
            if comprimento <= 0 or largura <= 0:
                confianca -= 0.5
            if nom is None:
                confianca -= 0.3
            if n_faces < 4:
                confianca -= 0.15

            # Número do pilar para ID final
            pid_final = pid if idx == 0 else f"{pid}_{idx+1}"
            numero = re.search(r'\d+', pid).group()

            fichas.append({
                "id": pid_final,
                "numero": numero,
                "pavimento": pavimento,
                "pavimento_numero": 1,
                "obra": nome_obra,
                "comprimento": comprimento,
                "largura": largura,
                "altura_cm": altura_cm,
                "nivel_saida_m": nivel_saida,
                "nivel_chegada_m": nivel_chegada,
                "pavimento_anterior": "",
                "par_1_2": "0", "par_2_3": "0", "par_3_4": "0", "par_4_5": "0",
                "par_5_6": "0", "par_6_7": "0", "par_7_8": "0", "par_8_9": "0",
                "grade_1": "", "distancia_1": "", "grade_2": "", "distancia_2": "", "grade_3": "",
                "pilar_especial": pilar_especial,
                "tipo_pilar_especial": tipo_especial,
                "confidence": round(confianca, 2),
                "revisado_por_humano": False,
                # Extra — não vai para o robô mas útil para debug
                "_faces": faces_found,
                "_face_widths": {k: int(v) for k, v in face_widths.items()},
                "_pd_m": pd,
                "_pav_txt": pav_txt,
            })

    return fichas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dxf', required=True, help='Caminho do DXF PL')
    parser.add_argument('--obra', default='Obra', help='Nome da obra')
    parser.add_argument('--pavimento', default='1_PAVIMENTO', help='Nome do pavimento')
    parser.add_argument('--output', default='output_fichas/fichas_pilares.json', help='Saída JSON')
    args = parser.parse_args()

    print(f"Lendo: {args.dxf}")
    fichas = extrair_pilares(args.dxf, args.obra, args.pavimento)

    # Separa campos internos (_*)
    fichas_export = []
    debug_info = []
    for f in fichas:
        debug = {k: f[k] for k in f if k.startswith('_')}
        clean = {k: f[k] for k in f if not k.startswith('_')}
        fichas_export.append(clean)
        debug_info.append({'id': clean['id'], **debug})

    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as fp:
        json.dump(fichas_export, fp, ensure_ascii=False, indent=2)

    # Debug
    debug_path = args.output.replace('.json', '_debug.json')
    with open(debug_path, 'w', encoding='utf-8') as fp:
        json.dump(debug_info, fp, ensure_ascii=False, indent=2)

    # Relatório
    print(f"\n{'='*60}")
    print(f"{'PILAR':<8} {'COMP':>6} {'LARG':>6} {'PD':>6} {'CONF':>5}  FACES")
    print(f"{'='*60}")
    for f in fichas_export:
        dbg = next(d for d in debug_info if d['id']==f['id'])
        faces = ''.join(dbg.get('_faces', []))
        fw = ', '.join(f"{k}={v}" for k,v in sorted(dbg.get('_face_widths',{}).items()))
        print(f"  {f['id']:<6} {f['comprimento']:>6.0f} {f['largura']:>6.0f} {f['_pd_m'] if False else dbg.get('_pd_m',0):>5.2f}m {f['confidence']:>5.2f}  [{faces}]  {fw}")

    ok = sum(1 for f in fichas_export if f['comprimento'] > 0 and f['largura'] > 0)
    print(f"\nTotal: {len(fichas_export)} pilares  |  {ok} com dimensões  |  Saída: {args.output}")
    print(f"Debug: {debug_path}")


if __name__ == '__main__':
    main()
