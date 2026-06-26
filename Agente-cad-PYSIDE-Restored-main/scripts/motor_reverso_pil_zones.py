# -*- coding: utf-8 -*-
"""
motor_reverso_pil_zones.py — Extrai 3+1 fichas N2 separadas por zona PIL.

Cada recorte de pilar (PIL_P{id}_motor_*.dxf ou _sel_*.dxf) contém zonas:
  - Zona CIMA (y superior): rótulos de face A/B/C/D + COTA com (GRADE)
  - Zona ABCD (y inferior): seções P{id}.A/B/C/D + cotas de altura

Recortes _sel_ de pilares em U (P26/P27) contêm adicionalmente:
  - Zona EFGH (outra faixa y): seções P{id}.E / P{id}.F com cotas de painel
    → larg1_E, larg1_F (largura de cada braço do U)

O catálogo de grades (PIL_GRADES_sel_*.dxf, 1 por pavimento) mapeia pilares
a grupos G{largura}-{N}X por proximidade em x.

API pública:
    extrair_ficha_abcd(recorte_path, elemento_id, obra_root)  → dict
    extrair_ficha_cima(recorte_path, elemento_id, obra_root)  → dict
    extrair_ficha_grades(obra_root, elemento_id, pavimento)   → dict
    extrair_ficha_efgh(recorte_path, elemento_id, obra_root)  → dict | None
    extrair_fichas_pil_zones(recorte_path, elemento_id,
                              obra_root, pavimento)           → dict com 'ABCD','CIMA','GRADES','EFGH'
"""

from pathlib import Path
import json, re, math

DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _lookup_fase4(elem_id: str, obra_root: Path) -> dict | None:
    p = obra_root / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{elem_id}.json"
    if p.exists():
        return json.loads(p.read_text(encoding='utf-8'))
    return None


def _infer_obra_root(recorte_path: str) -> Path | None:
    p = Path(recorte_path)
    for part in p.parts:
        if part.startswith("Obra_"):
            idx = p.parts.index(part)
            return Path(*p.parts[:idx + 1])
    return None


def _collect_texts(msp) -> list[tuple[str, float, float, str]]:
    """(layer, y, x, text) para TEXT e MTEXT."""
    result = []
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            ins = e.dxf.insert
            result.append((e.dxf.layer, float(ins[1]), float(ins[0]), txt.strip()))
        except Exception:
            pass
    return result


def _y_midpoint(texts: list) -> float:
    """Ponto de corte vertical entre zona CIMA (superior) e ABCD (inferior)."""
    ys = [y for _, y, _, _ in texts]
    if not ys:
        return 0.0
    return (min(ys) + max(ys)) / 2.0


def _calc_n_parafusos(comprimento: float) -> int:
    if comprimento <= 120: return 2
    if comprimento <= 195: return 3
    if comprimento <= 260: return 4
    if comprimento <= 330: return 5
    if comprimento <= 400: return 6
    return 7


def _distribute_pars(total: float, n: int) -> list:
    if n <= 1:
        return []
    unit = round(total / (n - 1), 1)
    return [unit] * (n - 1)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Ficha CIMA — extrai grade_1, comprimento, largura, faces ativas
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_grade_div_a(upper: list, grade_pos: tuple, grade_value: float,
                          comprimento: float, prox: float = 300.0, tol: float = 1.0) -> list:
    """
    Lê grade_1_div_a do recorte: lista de larguras de módulo (somam grade_1)
    correspondente à cota real de divisão da grade desenhada pelo humano.

    Algoritmo geral (sem hardcode de pilar):
    1. Localiza a label de comprimento (valor numérico ~= comprimento, dentro
       da janela `prox` em torno da label "{grade_1}(GRADE)").
    2. Entre os demais valores numéricos da zona CIMA (mesma janela), agrupa
       em "cadeias" alinhadas (mesmo x → cadeia vertical, ou mesmo y → cadeia
       horizontal, tolerância `tol`) cuja soma seja ~= grade_1 (candidatas a
       cota de divisão — o próprio total grade_1 também pode aparecer em
       cadeias coincidentes, ex. cota de parafusos que some o mesmo total).
    3. A cadeia de divisão (div_a) é a que fica POSICIONALMENTE ENTRE a label
       "(GRADE)" e a label de comprimento, no eixo perpendicular à cadeia —
       mesmo padrão observado em P1 (cadeia vertical entre as labels, no eixo
       x) e P11 (cadeia horizontal entre as labels, no eixo y).
    4. Fallback: cadeia com mais elementos, se nenhuma estiver "entre".
    """
    gx, gy = grade_pos
    comp_pos = None
    numeric = []  # (x, y, v) — exclui a label (GRADE) e a 1a ocorrência do comprimento
    for l, y, x, t in upper:
        if 'COTA' not in l.upper():
            continue
        if re.match(r'^(\d+(?:\.\d+)?)\s*\(GRADE\)', t, re.IGNORECASE):
            continue
        try:
            v = float(t)
        except ValueError:
            continue
        if abs(x - gx) > prox or abs(y - gy) > prox:
            continue
        if comp_pos is None and abs(v - comprimento) < 0.5:
            comp_pos = (x, y)
            continue
        numeric.append((x, y, v))

    # Agrupa por mesmo x (cadeia vertical) ou mesmo y (cadeia horizontal)
    chains = []
    for i, (xi, yi, vi) in enumerate(numeric):
        group_x = [(xi, yi, vi)]
        group_y = [(xi, yi, vi)]
        for j, (xj, yj, vj) in enumerate(numeric):
            if j == i:
                continue
            if abs(xj - xi) < tol:
                group_x.append((xj, yj, vj))
            if abs(yj - yi) < tol:
                group_y.append((xj, yj, vj))
        for group, axis in ((group_x, 'x'), (group_y, 'y')):
            if len(group) < 2:
                continue
            total = sum(g[2] for g in group)
            if abs(total - grade_value) < tol:
                key = tuple(sorted(group))
                if (axis, key) not in [(c[0], tuple(sorted(c[1]))) for c in chains]:
                    chains.append((axis, group))

    # Cadeia "entre" a label (GRADE) e a label de comprimento, no eixo
    # perpendicular (só aplicável se a label de comprimento foi localizada).
    best = None
    if comp_pos is not None:
        for axis, group in chains:
            const_coord = group[0][0] if axis == 'x' else group[0][1]
            gp = gx if axis == 'x' else gy
            cp = comp_pos[0] if axis == 'x' else comp_pos[1]
            lo, hi = min(gp, cp), max(gp, cp)
            if lo - tol <= const_coord <= hi + tol:
                best = (axis, group)
                break

    if best is None and chains:
        chains.sort(key=lambda c: -len(c[1]))
        best = chains[0]

    if best is None:
        return []

    axis, group = best
    group_sorted = sorted(group, key=lambda g: g[1] if axis == 'x' else g[0])
    return [round(g[2], 2) for g in group_sorted]


def _extract_cima_from_dxf(dxf_path: str, comprimento_hint: float | None = None) -> dict:
    """
    Lê a zona superior (y > midpoint) do recorte e extrai campos CIMA.
    Campos alvo: grade_1, comprimento, largura, faces_ativas, grade_1_div_a.

    `comprimento_hint`: comprimento real do item (ex.: de Fase-4), usado para
    localizar a label de comprimento no recorte ao buscar grade_1_div_a. Sem
    o hint, usa-se grade_value-22 (válido apenas quando grade_1==chapa_full_w).
    """
    import ezdxf
    result: dict = {}
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        texts = _collect_texts(msp)
        if not texts:
            return result

        mid = _y_midpoint(texts)
        upper = [(l, y, x, t) for l, y, x, t in texts if y >= mid]

        grade_value = None
        grade_pos = None
        cota_nums = []
        faces_ativas: set[str] = set()

        for l, y, x, t in upper:
            lu = l.upper()
            # Grade: "{n}(GRADE)" no layer COTA
            if 'COTA' in lu:
                gm = re.match(r'^(\d+(?:\.\d+)?)\s*\(GRADE\)', t, re.IGNORECASE)
                if gm:
                    grade_value = float(gm.group(1))
                    grade_pos = (x, y)
                    continue
                try:
                    v = float(t)
                    cota_nums.append(v)
                except ValueError:
                    pass
            # Faces: letras A-H em TEXTO_GERAL
            if 'TEXTO_GERAL' in lu or 'TEXTO' in lu:
                tu = t.upper().strip()
                if tu in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'):
                    faces_ativas.add(tu)

        if grade_value:
            result['grade_1'] = grade_value
            result['comprimento'] = round(grade_value - 22, 2)

        # Largura: menor COTA razoável < comprimento
        if cota_nums and 'comprimento' in result:
            comp = result['comprimento']
            candidates = [v for v in cota_nums if 5 < v < comp]
            if candidates:
                result['largura'] = min(candidates)

        # grade_1_div_a: cota real de divisão da grade desenhada pelo humano
        comp_for_div = comprimento_hint if comprimento_hint is not None else result.get('comprimento')
        if grade_value and grade_pos and comp_for_div is not None:
            div_a = _extract_grade_div_a(upper, grade_pos, grade_value, comp_for_div)
            if div_a:
                result['grade_1_div_a'] = div_a

        result['_faces_cima'] = sorted(faces_ativas)
        result['_confianca'] = 0.80 if grade_value else 0.4

    except Exception as ex:
        result['_erro_cima'] = str(ex)
        result['_confianca'] = 0.2

    return result


def extrair_ficha_cima(
    recorte_path: str,
    elemento_id: str,
    obra_root: str | Path | None = None,
) -> dict:
    """
    Ficha CIMA: campos usados pela zona CIMA do gerador.
    Campos: nome, comprimento, largura, grade_1, grade_1_div_a
    (+ pd_pavimento_cm de Fase-4).
    """
    obra_root_path = Path(obra_root) if obra_root else _infer_obra_root(recorte_path)
    fase4 = _lookup_fase4(elemento_id, obra_root_path) if obra_root_path else None
    comprimento_hint = fase4.get('comprimento') if fase4 else None
    dxf_cima = _extract_cima_from_dxf(recorte_path, comprimento_hint=comprimento_hint)

    if fase4:
        result = {
            'nome':          fase4.get('nome', elemento_id),
            'comprimento':   fase4.get('comprimento', 0.0),
            'largura':       fase4.get('largura', 0.0),
            'grade_1':       fase4.get('grade_1', 0.0),
            'pd_pavimento_cm': fase4.get('pd_pavimento_cm', 0.0),
        }
        # Enriquecer com extração DXF onde Fase-4 não tem
        if dxf_cima.get('grade_1') and not result['grade_1']:
            result['grade_1'] = dxf_cima['grade_1']
        result['_er_meta'] = {
            'zone': 'CIMA',
            'source': 'fase4',
            'dxf_grade_1': dxf_cima.get('grade_1'),
            'confianca': 0.95,
        }
    else:
        result = {
            'nome':          elemento_id,
            'comprimento':   dxf_cima.get('comprimento', 0.0),
            'largura':       dxf_cima.get('largura', 0.0),
            'grade_1':       dxf_cima.get('grade_1', 0.0),
            'pd_pavimento_cm': 0.0,
        }
        result['_er_meta'] = {
            'zone': 'CIMA',
            'source': 'dxf_extract',
            'confianca': dxf_cima.get('_confianca', 0.4),
        }

    # grade_1_div_a: prioriza a cota REAL extraída deste recorte (verdade do
    # STOG humano para este item); cai para Fase-4 se a extração não achou
    # uma cadeia válida (ex. recorte sem cota de divisão desenhada).
    div_a = dxf_cima.get('grade_1_div_a') or (fase4.get('grade_1_div_a') if fase4 else None)
    if div_a:
        result['grade_1_div_a'] = div_a
        result['_er_meta']['grade_1_div_a_source'] = (
            'dxf_extract' if dxf_cima.get('grade_1_div_a') else 'fase4'
        )

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Ficha ABCD — extrai dimensões, parafusos, faces de section
# ═══════════════════════════════════════════════════════════════════════════════

_FACE_LABEL_RE = re.compile(r'^P\d+\.([A-H])$', re.IGNORECASE)


def _extract_abcd_from_dxf(dxf_path: str, elemento_id: str) -> dict:
    """
    Lê a zona inferior (y < midpoint) do recorte e extrai campos ABCD.
    Campos alvo: altura, pd_pavimento_cm, faces P{id}.A/B/C/D, cotas h1-h5.
    """
    import ezdxf
    result: dict = {}
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        texts = _collect_texts(msp)
        if not texts:
            return result

        mid = _y_midpoint(texts)
        lower = [(l, y, x, t) for l, y, x, t in texts if y < mid]

        cota_nums: list[float] = []
        faces_abcd: set[str] = set()
        pd_cm: float | None = None

        # pd_pavimento_cm: busca em ALL texts (carimbo pode estar acima do midpoint)
        for l, y, x, t in texts:
            lu = l.upper()
            if 'NOMENCLATURA' in lu or 'NIVEL' in lu:
                m = re.search(r'PD:\s*([\d]+[.,][\d]+)', t, re.IGNORECASE)
                if m:
                    pd_cm = float(m.group(1).replace(',', '.')) * 100.0
                    break
                # Numeric "321" on NIVEL layer
                try:
                    v = float(t.replace(',', '.'))
                    if 200 < v < 1000 and 'NIVEL' in lu:
                        pd_cm = v
                except ValueError:
                    pass

        for l, y, x, t in lower:
            lu = l.upper()

            # (pd already searched in all texts above)

            # Faces de seção: "P1.A", "P1.B" etc.
            if 'TEXTO' in lu or 'SECO' in lu.replace('Ã', 'A').replace('ã', 'a') or 'SE' in lu:
                fm = _FACE_LABEL_RE.match(t)
                if fm:
                    faces_abcd.add(fm.group(1).upper())

            # COTA numérica
            if 'COTA' in lu:
                try:
                    cota_nums.append(float(t))
                except ValueError:
                    pass

        # Altura: maior valor COTA na zona ABCD (tipicamente h total ~280)
        altura_cands = [v for v in cota_nums if 200 < v < 700]
        if altura_cands:
            result['altura'] = max(altura_cands)

        if pd_cm is not None:
            result['pd_pavimento_cm'] = pd_cm

        result['_faces_abcd'] = sorted(faces_abcd) or ['A', 'B', 'C', 'D']
        result['_cota_abcd'] = sorted(cota_nums)
        result['_confianca'] = 0.75 if faces_abcd else 0.45

    except Exception as ex:
        result['_erro_abcd'] = str(ex)
        result['_confianca'] = 0.2

    return result


def extrair_ficha_abcd(
    recorte_path: str,
    elemento_id: str,
    obra_root: str | Path | None = None,
) -> dict:
    """
    Ficha ABCD: campos usados pela zona ABCD do gerador.
    Campos: nome, comprimento, largura, altura, pd_pavimento_cm.
    """
    obra_root_path = Path(obra_root) if obra_root else _infer_obra_root(recorte_path)
    fase4 = _lookup_fase4(elemento_id, obra_root_path) if obra_root_path else None
    dxf_abcd = _extract_abcd_from_dxf(recorte_path, elemento_id)

    if fase4:
        result = {
            'nome':             fase4.get('nome', elemento_id),
            'comprimento':      fase4.get('comprimento', 0.0),
            'largura':          fase4.get('largura', 0.0),
            'altura':           fase4.get('altura', 280.0),
            'pd_pavimento_cm':  fase4.get('pd_pavimento_cm', 0.0),
        }
        # PD extraído do recorte tem prioridade sobre Fase-4 (varia por sub-bloco)
        if dxf_abcd.get('pd_pavimento_cm'):
            result['pd_pavimento_cm'] = dxf_abcd['pd_pavimento_cm']
        result['_er_meta'] = {
            'zone': 'ABCD',
            'source': 'fase4',
            'dxf_faces': dxf_abcd.get('_faces_abcd'),
            'confianca': 0.95,
        }
    else:
        result = {
            'nome':             elemento_id,
            'comprimento':      0.0,
            'largura':          0.0,
            'altura':           dxf_abcd.get('altura', 280.0),
            'pd_pavimento_cm':  dxf_abcd.get('pd_pavimento_cm', 0.0),
        }
        result['_er_meta'] = {
            'zone': 'ABCD',
            'source': 'dxf_extract',
            'confianca': dxf_abcd.get('_confianca', 0.45),
        }

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Ficha GRADES — parseia catálogo PIL_GRADES_sel_*.dxf
# ═══════════════════════════════════════════════════════════════════════════════

_G_HDR_RE = re.compile(r'^G(\d+)-(\d+)X$', re.IGNORECASE)
_P_LBL_RE = re.compile(r'^P(\d+)\.([A-H])\s*-\s*(\d+)X$', re.IGNORECASE)


def _find_grades_sel(obra_root: Path, pavimento: str | None) -> Path | None:
    """
    Encontra PIL_GRADES_sel_*.dxf em recortes_reversos para o pavimento.
    Heuristica: nome do diretorio de recorte contem parte do nome do pavimento.

    Retorna None se nenhum catalogo casar com o pavimento -- IDs de pilar
    (P3, P10, ...) se repetem entre pavimentos/plantas-tipo mas referem-se
    a pilares FISICAMENTE DIFERENTES com grade_1 diferente. Por isso NAO
    ha fallback "primeiro catalogo disponivel": um catalogo de outro
    pavimento pode conter um "P3"/"P10" cujo grade_1 nao tem relacao com
    o elemento pedido. Sem catalogo do proprio pavimento,
    `extrair_ficha_grades` cai para o grade_1 de Fase-4 (que ja vem da
    extracao da vista CIMA do proprio recorte do item).
    """
    recortes_base = obra_root / "Fase-2_Triagem" / "recortes_reversos"
    if not recortes_base.is_dir():
        return None

    if not pavimento:
        return None

    pav_norm = pavimento.upper().replace('°', '').replace('Â°', '').strip()
    for d in recortes_base.iterdir():
        if not d.is_dir():
            continue
        d_norm = d.name.upper().replace('°', '').replace('°', '').strip()
        if 'PL' in d_norm and any(part in d_norm for part in pav_norm.split()):
            gs = sorted(d.glob("PIL_GRADES_sel_*.dxf"))
            if gs:
                return gs[0]

    return None


def parse_grades_catalog(grades_sel_path: str | Path) -> dict[str, float]:
    """
    Parseia PIL_GRADES_sel_*.dxf e retorna {elem_id → grade_largura}.

    Layout: G-headers (ex: 'G88-6X') e P-labels (ex: 'P3.A - 1X') têm a
    mesma coordenada x (dentro de tolerância ~100u). Atribui grade por
    proximidade em x.
    """
    import ezdxf
    result: dict[str, float] = {}
    try:
        doc = ezdxf.readfile(str(grades_sel_path))
        msp = doc.modelspace()
        texts = _collect_texts(msp)

        g_headers: list[tuple[float, float]] = []  # (x, largura)
        p_labels: list[tuple[float, str]] = []      # (x, elem_id)

        for l, y, x, t in texts:
            gm = _G_HDR_RE.match(t)
            if gm:
                g_headers.append((x, float(gm.group(1))))
                continue
            pm = _P_LBL_RE.match(t)
            if pm:
                p_labels.append((x, f"P{pm.group(1)}"))

        if not g_headers:
            return result

        # Atribuir cada P-label ao G-header mais próximo por x
        for px, elem_id in p_labels:
            best_largura = min(g_headers, key=lambda h: abs(h[0] - px))[1]
            result[elem_id] = best_largura

    except Exception:
        pass

    return result


def extrair_ficha_grades(
    obra_root: str | Path,
    elemento_id: str,
    pavimento: str | None = None,
    grades_sel_path: str | Path | None = None,
) -> dict:
    """
    Ficha GRADES: grade_1 (largura do módulo) extraída do catálogo por pavimento.

    Retorna dict com: nome, comprimento, largura, altura, grade_1, grade_2.
    grade_1 vem do catálogo; demais campos de Fase-4.
    Retorna dict vazio com '_sem_grades': True se o pilar não usa grades.
    """
    obra_root_path = Path(obra_root)
    fase4 = _lookup_fase4(elemento_id, obra_root_path)

    # Encontrar catalogo do proprio pavimento (None se nao houver match).
    sel_path = Path(grades_sel_path) if grades_sel_path else _find_grades_sel(obra_root_path, pavimento)
    catalog: dict[str, float] = {}
    if sel_path and sel_path.exists():
        catalog = parse_grades_catalog(sel_path)

    grade_1_catalog = catalog.get(elemento_id.upper()) or catalog.get(elemento_id)

    # Verificar se tem grades (grade_1 > 0 em Fase-4 ou no catálogo)
    fase4_grade = float((fase4 or {}).get('grade_1', 0))
    if not grade_1_catalog and not fase4_grade:
        return {
            '_sem_grades': True,
            'nome': elemento_id,
            '_er_meta': {'zone': 'GRADES', 'source': 'none', 'confianca': 0.0},
        }

    result = {
        'nome':        (fase4 or {}).get('nome', elemento_id),
        'comprimento': (fase4 or {}).get('comprimento', 0.0),
        'largura':     (fase4 or {}).get('largura', 0.0),
        'altura':      (fase4 or {}).get('altura', 280.0),
        'grade_1':     grade_1_catalog or fase4_grade,
        'grade_2':     (fase4 or {}).get('grade_2', 0.0),
    }
    result['_er_meta'] = {
        'zone': 'GRADES',
        'source': 'catalog' if grade_1_catalog else 'fase4',
        'grades_sel': str(sel_path) if sel_path else None,
        'catalog_grade_1': grade_1_catalog,
        'fase4_grade_1': fase4_grade,
        'confianca': 0.90 if grade_1_catalog else 0.75,
    }
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Ficha EFGH — faces E/F do pilar em U (AR-1'.C)
# ═══════════════════════════════════════════════════════════════════════════════

_EF_FACE_RE = re.compile(r'^P(\d+)\.([EF])$', re.IGNORECASE)


def _extract_ef_from_dxf(dxf_path: str, elemento_id: str) -> dict | None:
    """
    Detecta faces E/F no recorte DXF (pilar em U) e extrai larguras de painel.

    Algoritmo:
      1. Encontra labels `P{id}.E` e `P{id}.F` em `Texto Seção`
      2. Para cada face, encontra o COTA > 100 mais próximo em x
         → larg1_E / larg1_F (largura do braço do U no desenho STOG)
      3. h1=2, h2=244, h3=34 (mesma distribuição padrão que ABCD)

    Retorna None se o pilar não for U (ausência de labels E/F).
    """
    import ezdxf
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        texts = _collect_texts(msp)
    except Exception:
        return None

    elem_num = re.sub(r'[^\d]', '', elemento_id)
    ef_labels: dict[str, tuple[float, float]] = {}  # face → (x, y)

    for l, y, x, t in texts:
        m = _EF_FACE_RE.match(t)
        if m and m.group(1) == elem_num:
            face = m.group(2).upper()
            ef_labels[face] = (x, y)

    if len(ef_labels) < 2:
        return None  # não é U-shape (sem faces E/F)

    # Região vertical onde os labels EF ficam
    y_ef_vals = [v[1] for v in ef_labels.values()]
    y_min = min(y_ef_vals) - 250
    y_max = max(y_ef_vals) + 350

    # COTAs grandes (> 100) nessa região
    large_cotas: list[tuple[float, float]] = []  # (x, valor)
    for l, y, x, t in texts:
        if 'COTA' not in l.upper():
            continue
        if not (y_min <= y <= y_max):
            continue
        try:
            v = float(t)
            if v > 100:
                large_cotas.append((x, v))
        except ValueError:
            pass

    if not large_cotas:
        return None

    # Atribuir cada face ao COTA grande mais próximo em x
    larg_ef: dict[str, float] = {}
    used: set[int] = set()
    for face in ('E', 'F'):
        if face not in ef_labels:
            continue
        fx, _ = ef_labels[face]
        best_i, best_dist, best_val = -1, float('inf'), 0.0
        for i, (cx, cv) in enumerate(large_cotas):
            if i in used:
                continue
            d = abs(cx - fx)
            if d < best_dist:
                best_dist, best_i, best_val = d, i, cv
        if best_i >= 0:
            larg_ef[face] = best_val
            used.add(best_i)

    if len(larg_ef) < 2:
        return None

    return {
        'larg1_E': larg_ef.get('E', 0.0),
        'larg1_F': larg_ef.get('F', 0.0),
        'h1_E':    2.0,
        'h2_E':  244.0,
        'h3_E':   34.0,
        'h1_F':    2.0,
        'h2_F':  244.0,
        'h3_F':   34.0,
        '_faces_ef': sorted(ef_labels.keys()),
        '_confianca': 0.80,
    }


def _find_sel_recorte(obra_root: Path, elemento_id: str, pavimento: str | None) -> Path | None:
    """Encontra o recorte _sel_ para o elem em qualquer pavimento da obra."""
    base = obra_root / "Fase-2_Triagem" / "recortes_reversos"
    if not base.is_dir():
        return None

    candidates: list[Path] = []
    for d in base.iterdir():
        if not d.is_dir() or 'PL' not in d.name.upper():
            continue
        for f in d.glob(f"PIL_{elemento_id}_sel_*.dxf"):
            candidates.append(f)

    if not candidates:
        return None

    # Preferir pavimento correspondente se indicado
    if pavimento:
        pav_norm = pavimento.upper().replace('°', '').replace('\xb0', '').strip()
        for c in candidates:
            d_norm = c.parent.name.upper().replace('°', '').replace('\xb0', '').strip()
            if any(p in d_norm for p in pav_norm.split()):
                return c

    return candidates[0]  # fallback: primeiro disponível


def extrair_ficha_efgh(
    recorte_path: str,
    elemento_id: str,
    obra_root: str | Path | None = None,
    pavimento: str | None = None,
) -> dict | None:
    """
    Ficha EFGH: campos das faces E/F do pilar em U.

    Tenta extrair de `_sel_` primeiro (tem ambas as zonas ABCD+EF),
    depois de recorte_path. Retorna None se o pilar não é U-shape.
    """
    obra_root_path = Path(obra_root) if obra_root else _infer_obra_root(recorte_path)
    fase4 = _lookup_fase4(elemento_id, obra_root_path) if obra_root_path else None

    # Tentar _sel_ primeiro (tem zona EF)
    sel_path = _find_sel_recorte(obra_root_path, elemento_id, pavimento) if obra_root_path else None
    ef_data = None
    if sel_path:
        ef_data = _extract_ef_from_dxf(str(sel_path), elemento_id)
    if ef_data is None:
        ef_data = _extract_ef_from_dxf(str(recorte_path), elemento_id)

    if ef_data is None:
        return None  # pilar não é U-shape (sem faces E/F)

    def _h(field: str, default: float) -> float:
        v = float((fase4 or {}).get(field, 0.0))
        return v if v > 0 else ef_data.get(field, default)

    result = {
        'nome':    (fase4 or {}).get('nome', elemento_id),
        'larg1_E': ef_data.get('larg1_E', 0.0),
        'larg1_F': ef_data.get('larg1_F', 0.0),
        'h1_E':    _h('h1_E',  2.0),
        'h2_E':    _h('h2_E', 244.0),
        'h3_E':    _h('h3_E', 34.0),
        'h1_F':    _h('h1_F',  2.0),
        'h2_F':    _h('h2_F', 244.0),
        'h3_F':    _h('h3_F', 34.0),
    }
    result['_er_meta'] = {
        'zone':    'EFGH',
        'source':  'dxf_extract',
        'sel_path': str(sel_path) if sel_path else None,
        'faces':   ef_data.get('_faces_ef'),
        'confianca': ef_data.get('_confianca', 0.7),
    }
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 5. API principal — 3+1 fichas de uma vez
# ═══════════════════════════════════════════════════════════════════════════════

def extrair_fichas_pil_zones(
    recorte_path: str,
    elemento_id: str,
    obra_root: str | Path | None = None,
    pavimento: str | None = None,
) -> dict:
    """
    Extrai fichas N2 para as zonas PIL: ABCD, CIMA, GRADES (+ EFGH se U-shape).

    Returns:
        {
          'ABCD':   dict com campos da zona ABCD,
          'CIMA':   dict com campos da zona CIMA,
          'GRADES': dict com campos da zona GRADES
                    (pode ter '_sem_grades': True se pilar não tem grade),
          'EFGH':   dict com larg1_E/larg1_F + h1-h3 por face E/F,
                    ou None se o pilar não é subtipo U.
        }
    """
    obra_root_path = Path(obra_root) if obra_root else _infer_obra_root(recorte_path)
    return {
        'ABCD':   extrair_ficha_abcd(recorte_path, elemento_id, obra_root_path),
        'CIMA':   extrair_ficha_cima(recorte_path, elemento_id, obra_root_path),
        'GRADES': extrair_ficha_grades(obra_root_path, elemento_id, pavimento),
        'EFGH':   extrair_ficha_efgh(recorte_path, elemento_id, obra_root_path, pavimento),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys, argparse

    parser = argparse.ArgumentParser(
        description='Extrai fichas N2 por zona PIL (ABCD/CIMA/GRADES)')
    parser.add_argument('recorte', help='Caminho do recorte DXF do pilar')
    parser.add_argument('elemento_id', help='ID do elemento (ex: P1)')
    parser.add_argument('--obra', help='Caminho da obra (infere se omitido)')
    parser.add_argument('--pavimento', help='Nome do pavimento (para lookup GRADES)')
    parser.add_argument('--zone', choices=['abcd', 'cima', 'grades', 'efgh', 'all'],
                        default='all', help='Zona a extrair (default: all)')
    args = parser.parse_args()

    obra = args.obra
    pav  = args.pavimento

    if args.zone == 'all':
        result = extrair_fichas_pil_zones(args.recorte, args.elemento_id, obra, pav)
    elif args.zone == 'abcd':
        result = extrair_ficha_abcd(args.recorte, args.elemento_id, obra)
    elif args.zone == 'cima':
        result = extrair_ficha_cima(args.recorte, args.elemento_id, obra)
    elif args.zone == 'grades':
        obra_path = Path(obra) if obra else _infer_obra_root(args.recorte)
        result = extrair_ficha_grades(obra_path, args.elemento_id, pav)
    elif args.zone == 'efgh':
        result = extrair_ficha_efgh(args.recorte, args.elemento_id, obra, pav)

    print(json.dumps(result, indent=2, ensure_ascii=False))
