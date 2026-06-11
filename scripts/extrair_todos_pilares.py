"""
Extrai dados reais de todos os pilares de um DXF PL (planta de fôrma).

Algoritmo:
1. Para cada pilar (P1..Pn): coleta posições das faces (P1.A, P1.B, etc.)
2. Agrupa por cluster (raio 1500) para separar pilares com mesmo nome em andares diferentes
3. Para cada face: mede a largura das linhas do layer Painéis próximas
4. comprimento = max(face_widths), largura = min(face_widths)
5. PD = texto NOMENCLATURA mais próximo (regex "PD: X.XX")

Saída: lista {pilar, comprimento_cm, largura_cm, pd_m, faces}
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import ezdxf, math, re
from collections import defaultdict

DXF = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa/ALIMONTI - PARAISO - 1° PAV.- PL - R00.dxf"

doc = ezdxf.readfile(DXF)
msp = doc.modelspace()

def dist2d(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

# ── 1. Coleta todos os textos "Texto Seção" com padrão Pn.X ───────────
secoes_raw = []
for e in msp:
    if e.dxftype() == 'TEXT' and e.dxf.layer == 'Texto Seção':
        txt = e.dxf.text.strip()
        m = re.match(r'^(P\d+)\.([A-H])$', txt)
        if m:
            pid, face = m.group(1), m.group(2)
            pos = (e.dxf.insert[0], e.dxf.insert[1])
            secoes_raw.append({'pid': pid, 'face': face, 'pos': pos})

# ── 2. Agrupa por pilar e por cluster (pode ter 2 ocorrências por pilar) ──
pilares_raw = defaultdict(list)
for s in secoes_raw:
    pilares_raw[s['pid']].append(s)

# Agrupa faces em clusters (raio 1500 entre si)
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

# ── 3. Pré-indexa linhas Painéis ──────────────────────────────────────
paineis_lines = []
for e in msp:
    if e.dxftype() == 'LINE' and e.dxf.layer == 'Painéis':
        mp = ((e.dxf.start[0]+e.dxf.end[0])/2, (e.dxf.start[1]+e.dxf.end[1])/2)
        dx = abs(e.dxf.end[0]-e.dxf.start[0])
        dy = abs(e.dxf.end[1]-e.dxf.start[1])
        L = round(math.sqrt(dx*dx + dy*dy), 1)
        orient = 'H' if dx > dy else 'V'
        paineis_lines.append({'mp': mp, 'L': L, 'orient': orient, 'e': e})

# ── 4. Pré-indexa textos NOMENCLATURA ─────────────────────────────────
nomenclaturas = []
for e in msp:
    if e.dxftype() == 'MTEXT' and e.dxf.layer == 'NOMENCLATURA':
        pos = e.dxf.insert
        txt = e.text
        m = re.search(r'PD:\s*([\d.]+)', txt)
        if m:
            pd = float(m.group(1))
            nomenclaturas.append({'pos': (pos[0], pos[1]), 'pd': pd, 'txt': txt})

def get_face_width(face_pos, raio=150):
    """Mede largura horizontal das linhas Painéis próximas à face."""
    candidatas = []
    for pl in paineis_lines:
        if dist2d(pl['mp'], face_pos) < raio and pl['orient'] == 'H':
            candidatas.append(pl['L'])
    if not candidatas:
        return None
    # Retorna o valor mais frequente entre as linhas horizontais
    from collections import Counter
    c = Counter(round(v, 0) for v in candidatas)
    return c.most_common(1)[0][0]

def get_pd(cluster_center, raio=2000):
    """Retorna o PD do NOMENCLATURA mais próximo."""
    best = None
    best_d = 9999999
    for n in nomenclaturas:
        d = dist2d(n['pos'], cluster_center)
        if d < raio and d < best_d:
            best_d = d
            best = n['pd']
    return best

# ── 5. Extrai dimensões de cada pilar ─────────────────────────────────
resultados = []

for pid in sorted(pilares_raw.keys(), key=lambda x: int(re.search(r'\d+', x).group())):
    clusters = clusterizar(pilares_raw[pid])
    for idx, cl in enumerate(clusters):
        cx = sum(o['pos'][0] for o in cl) / len(cl)
        cy = sum(o['pos'][1] for o in cl) / len(cl)
        center = (cx, cy)

        face_widths = {}
        for o in cl:
            w = get_face_width(o['pos'], raio=150)
            if w is not None:
                face_widths[o['face']] = w

        if not face_widths:
            # tenta raio maior
            for o in cl:
                w = get_face_width(o['pos'], raio=300)
                if w is not None:
                    face_widths[o['face']] = w

        widths = list(face_widths.values())
        comprimento = round(max(widths), 0) if widths else None
        largura = round(min(widths), 0) if widths else None

        pd = get_pd(center)

        faces_found = sorted(set(o['face'] for o in cl))

        resultados.append({
            'pid': pid,
            'cluster': idx+1,
            'n_clusters': len(clusters),
            'center': center,
            'faces': faces_found,
            'face_widths': face_widths,
            'comprimento': comprimento,
            'largura': largura,
            'pd': pd,
        })

# ── 6. Imprime resultados ──────────────────────────────────────────────
print(f"{'='*75}")
print(f"{'PILAR':<8} {'COMP':>6} {'LARG':>6} {'PD':>6}  FACES  FACE_WIDTHS")
print(f"{'='*75}")

for r in resultados:
    pid = r['pid']
    if r['n_clusters'] > 1:
        pid += f"[{r['cluster']}]"
    comp = f"{r['comprimento']:.0f}" if r['comprimento'] else "?"
    larg = f"{r['largura']:.0f}" if r['largura'] else "?"
    pd_s = f"{r['pd']:.2f}m" if r['pd'] else "?"
    faces_s = ''.join(r['faces'])
    fw_s = ', '.join(f"{f}={v:.0f}" for f,v in sorted(r['face_widths'].items()))
    print(f"{pid:<8} {comp:>6} {larg:>6} {pd_s:>6}  [{faces_s}]  {fw_s}")

print(f"\nTotal: {len(resultados)} entradas ({len(set(r['pid'].split('[')[0] for r in resultados))} pilares únicos)")

# ── 7. Resumo por pilar único (usa o maior cluster, ignorando duplicatas) ──
print(f"\n{'='*75}")
print("RESUMO CONSOLIDADO (1 linha por pilar):")
print(f"{'='*75}")

seen = {}
for r in resultados:
    pid_base = r['pid']
    if pid_base not in seen or (r['comprimento'] and not seen[pid_base]['comprimento']):
        seen[pid_base] = r

for pid in sorted(seen.keys(), key=lambda x: int(re.search(r'\d+', x).group())):
    r = seen[pid]
    comp = f"{r['comprimento']:.0f}cm" if r['comprimento'] else "?"
    larg = f"{r['largura']:.0f}cm" if r['largura'] else "?"
    pd_s = f"{r['pd']:.2f}m" if r['pd'] else "?"
    print(f"  {pid:<6}: {comp} x {larg}  PD={pd_s}  faces={r['faces']}")
