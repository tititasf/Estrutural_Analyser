"""
Sprint-A: Validação do TextProximitySearch nas 23 obras de treino.

Compara:
  - Nome atual das lajes no DB (ground truth)
  - Nome encontrado por TextProximitySearch no DXF

Métricas:
  - accuracy: % lajes com nome correto
  - resolvidas: % lajes que tiveram pelo menos 1 candidato
  - sem_candidato: % lajes sem nenhum candidato encontrado
"""
import os, sys, json, math, re, sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    import ezdxf
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False
    print("ERRO: ezdxf não instalado. Rodar: pip install ezdxf")
    sys.exit(1)

# ── Configuração ───────────────────────────────────────────────────────────
DB_PATH       = Path(__file__).parent.parent / 'project_data.vision'
DADOS_DIR     = Path(__file__).parent.parent / 'DADOS-OBRAS'
RAIO_BUSCA    = 600.0      # mm — expandir bbox da laje em cada direção
RAIO_EXTRA    = 1200.0     # mm — segunda passagem se não achar
CONF_AUTO     = 0.75       # confiança mínima para auto-assign
REGEX_LAJE    = re.compile(r'^(L\d+[A-Za-z]?|Y\d+[A-Za-z]?|X\d+[A-Za-z]?|LAJ[-_]?\d+|LAJE[-_\s]*\d+)$', re.IGNORECASE)
GEOCOORD_THRESHOLD = 50000  # coords > this are geographic (UTM), skip

# ── Funções auxiliares ─────────────────────────────────────────────────────

def bbox_from_points(pts):
    """Retorna (xmin, xmax, ymin, ymax) de lista de pontos."""
    if not pts:
        return 0, 0, 0, 0
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), max(xs), min(ys), max(ys)

def centroid(pts):
    if not pts:
        return 0, 0
    return sum(p[0] for p in pts)/len(pts), sum(p[1] for p in pts)/len(pts)

def dist2(ax, ay, bx, by):
    return math.sqrt((ax-bx)**2 + (ay-by)**2)

def _get_mtext_content(e) -> str:
    """Extrai conteúdo de MTEXT com compatibilidade entre versões do ezdxf."""
    for method in ['plain_text', 'plain_mtext']:
        try:
            fn = getattr(e, method, None)
            if callable(fn):
                result = fn()
                if result:
                    return str(result)
        except Exception:
            pass
    # Fallback: e.text attribute
    for attr in ['text']:
        try:
            val = getattr(e, attr, None) or getattr(e.dxf, attr, None)
            if val:
                # Strip MTEXT formatting codes: \P \n \\ \fFont; \H...; etc.
                clean = re.sub(r'\\[A-Za-z][^;]*;', '', str(val))
                clean = re.sub(r'\\[\\{}|]', '', clean)
                return clean.strip()
        except Exception:
            pass
    return ''


def extract_texts_from_dxf(dxf_path):
    """Extrai entidades TEXT/MTEXT do DXF como lista de dicts."""
    texts = []
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        for e in msp:
            try:
                etype = e.dxftype()
                txt = ''
                if etype == 'TEXT':
                    txt = (getattr(e.dxf, 'text', None) or '').strip()
                elif etype == 'MTEXT':
                    txt = _get_mtext_content(e)
                if txt:
                    insert = e.dxf.insert
                    texts.append({'text': txt, 'x': float(insert.x), 'y': float(insert.y), 'layer': getattr(e.dxf, 'layer', '')})
            except Exception:
                pass
    except Exception as ex:
        print(f"  [WARN] Erro lendo {dxf_path.name}: {ex}")
    return texts

def detectar_escala(pts_all) -> float:
    """Detecta se o DXF está em metros (retorna fator multiplicador para raio mm→m)."""
    if not pts_all:
        return 1.0
    max_coord = max(max(abs(p[0]), abs(p[1])) for p in pts_all if p)
    if max_coord < 200:
        return 0.005  # metros: raio efetivo = 600*0.005 = 3m (unidade m, não mm)
    return 1.0


def buscar_nome_laje(pts, textos, raio):
    """
    Busca nome de laje por proximidade textual.
    Retorna (nome_encontrado, confianca) ou (None, 0).
    """
    if not pts:
        return None, 0.0

    xmin, xmax, ymin, ymax = bbox_from_points(pts)
    cx, cy = centroid(pts)

    # Bbox expandida
    xmin_e = xmin - raio
    xmax_e = xmax + raio
    ymin_e = ymin - raio
    ymax_e = ymax + raio

    candidatos = []
    for t in textos:
        tx, ty, txt = t['x'], t['y'], t['text']
        if xmin_e <= tx <= xmax_e and ymin_e <= ty <= ymax_e:
            # Limpar texto (remover quebras de linha, espaços)
            txt_clean = txt.replace('\n', ' ').replace('\r', '').strip()
            # Testar regex (linha por linha também)
            for parte in [txt_clean] + txt_clean.split():
                parte = parte.strip()
                if REGEX_LAJE.match(parte):
                    d = dist2(cx, cy, tx, ty)
                    candidatos.append((d, parte.upper()))
                    break

    if not candidatos:
        return None, 0.0

    # Melhor candidato = mais próximo
    candidatos.sort(key=lambda x: x[0])
    melhor_dist, melhor_nome = candidatos[0]

    # Confiança inversamente proporcional à distância normalizada
    # dist=0 → conf=1.0 ; dist=raio → conf=0.3
    conf = max(0.1, 1.0 - (melhor_dist / (raio * 2.0)) * 0.7)

    return melhor_nome, conf

def get_local_dxf_path(db_dxf_path, obra):
    """Converte path do DB (Ryzen) para path local."""
    if not db_dxf_path:
        return None
    # Strip old machine prefix, reconstruct with local DADOS-OBRAS
    fname = Path(db_dxf_path).name
    local = DADOS_DIR / obra / 'Fase-2_Triagem' / 'Estruturais_Pavimentos_Limpos' / fname
    if local.exists():
        return local
    # Tentar todas as subpastas
    base = DADOS_DIR / obra
    for root, dirs, files in os.walk(str(base)):
        if fname in files:
            return Path(root) / fname
    return None

# ── Pipeline principal ─────────────────────────────────────────────────────

def validar_obra(conn, obra, verbose=False):
    """Valida TextProximitySearch para uma obra. Retorna dict de métricas."""
    projects = conn.execute(
        "SELECT id, name, dxf_path FROM projects WHERE work_name=?", (obra,)
    ).fetchall()

    if not projects:
        return {'obra': obra, 'skip': True, 'reason': 'no projects'}

    total_lajes = 0
    corretas = 0
    resolvidas = 0
    sem_candidato = 0
    erros_nome = []

    for proj_id, pav_name, dxf_path_db in projects:
        # Pegar lajes do projeto
        slabs = conn.execute(
            "SELECT id, name, points_json FROM slabs WHERE project_id=?", (proj_id,)
        ).fetchall()

        if not slabs:
            continue

        # Encontrar DXF local
        dxf_path = get_local_dxf_path(dxf_path_db, obra)
        if not dxf_path:
            if verbose:
                print(f"  [SKIP] {pav_name}: DXF não encontrado")
            continue

        # Extrair textos do DXF (uma vez por pavimento)
        textos = extract_texts_from_dxf(dxf_path)
        if not textos:
            if verbose:
                print(f"  [WARN] {pav_name}: nenhum texto extraído")
            continue

        # Detectar escala e geocoordenadas
        all_slab_pts = []
        for _, _, pj in slabs:
            all_slab_pts.extend(json.loads(pj or '[]'))
        if all_slab_pts:
            max_c = max(max(abs(p[0]), abs(p[1])) for p in all_slab_pts if p)
            if max_c > GEOCOORD_THRESHOLD:
                if verbose:
                    print(f"  [SKIP] {pav_name}: geocoordenadas detectadas (max={max_c:.0f})")
                continue
        escala = detectar_escala(all_slab_pts)

        for slab_id, slab_name, points_json in slabs:
            if not slab_name or slab_name == '?':
                continue  # não tem ground truth

            pts = json.loads(points_json or '[]')
            if not pts:
                continue

            total_lajes += 1

            # Ajustar raio pela escala detectada
            raio_1 = RAIO_BUSCA * escala
            raio_2 = RAIO_EXTRA * escala

            # Buscar com raio normal
            nome_enc, conf = buscar_nome_laje(pts, textos, raio_1)

            # Segunda passagem com raio maior
            if nome_enc is None:
                nome_enc, conf = buscar_nome_laje(pts, textos, raio_2)

            if nome_enc is None:
                sem_candidato += 1
                if verbose:
                    print(f"    [NO MATCH] {pav_name} / {slab_name}")
            else:
                resolvidas += 1
                # Normalizar para comparação
                gt = slab_name.upper().strip()
                enc = nome_enc.upper().strip()
                if gt == enc:
                    corretas += 1
                else:
                    erros_nome.append((pav_name, gt, enc))
                    if verbose:
                        print(f"    [WRONG] {pav_name} | GT={gt} ENC={enc}")

    return {
        'obra': obra,
        'total': total_lajes,
        'corretas': corretas,
        'resolvidas': resolvidas,
        'sem_candidato': sem_candidato,
        'accuracy': corretas / max(1, total_lajes),
        'resolve_rate': resolvidas / max(1, total_lajes),
        'erros': erros_nome[:5],
    }


def main():
    conn = sqlite3.connect(str(DB_PATH))
    obras = [r[0] for r in conn.execute("SELECT name FROM works ORDER BY name").fetchall()]
    obras = [o for o in obras if 'TREINO' in o or 'TESTE' in o]

    print(f"TextProximitySearch — Validando {len(obras)} obras")
    print(f"Raio: {RAIO_BUSCA}mm (2ª passagem: {RAIO_EXTRA}mm)")
    print("=" * 70)

    totais = {'total': 0, 'corretas': 0, 'resolvidas': 0, 'sem_candidato': 0}
    resultados = []

    for obra in obras:
        r = validar_obra(conn, obra, verbose=False)
        if r.get('skip'):
            continue
        resultados.append(r)
        for k in totais:
            totais[k] += r.get(k, 0)

        status = 'OK' if r['accuracy'] >= 0.6 else 'WARN' if r['accuracy'] >= 0.3 else 'FAIL'
        print(f"{status} {obra:30} | acc={r['accuracy']:.1%}  res={r['resolve_rate']:.1%}  "
              f"n={r['total']:3} ok={r['corretas']:3}")

    print("=" * 70)
    acc_global = totais['corretas'] / max(1, totais['total'])
    res_global = totais['resolvidas'] / max(1, totais['total'])
    sem_global = totais['sem_candidato'] / max(1, totais['total'])

    print(f"\n[RESULTADO GLOBAL]")
    print(f"   Total lajes:      {totais['total']}")
    print(f"   Accuracy:         {acc_global:.1%}  (meta: 65%)")
    print(f"   Resolve rate:     {res_global:.1%}  (% com algum candidato)")
    print(f"   Sem candidato:    {sem_global:.1%}  (% sem texto próximo)")

    if acc_global >= 0.65:
        print("\n   [META ATINGIDA] TextProximitySearch pronto para producao!")
    elif acc_global >= 0.40:
        print("\n   [PARCIAL] Parcialmente funcional - ajustar raio ou regex")
    else:
        print("\n   [FALHA] Abaixo da meta - investigar erros")

    # Erros mais comuns
    all_erros = []
    for r in resultados:
        all_erros.extend(r.get('erros', []))
    if all_erros:
        print(f"\n   Amostra de erros (GT → Encontrado):")
        for pav, gt, enc in all_erros[:8]:
            print(f"     {gt} → {enc}  [{pav}]")

    conn.close()
    return acc_global


if __name__ == '__main__':
    acc = main()
    sys.exit(0 if acc >= 0.5 else 1)
