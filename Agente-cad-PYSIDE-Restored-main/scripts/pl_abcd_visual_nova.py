"""Visual ABCD modo NOVA — regras gerais (qualquer pilar/obra).

Motor único: ``enrich_payload_for_abcd_nova`` + desenho em
``apply_face_visual_nova`` / ``gerar_pl_dxf_stog.draw_abcd``.
Nada é por item (P1/P2/…) — só geometria do payload + contrato SA.

Regras:
- PD / níveis: topo do pilar = maior nível de laje/viga em contato; PD = saída−chegada.
- Rebaixo laje = nivel_topo_pilar − nivel_laje (≥0).
- Vazio de laje = espessura_laje + 2 (sempre +2).
- Hatch AR-CONC só nos VAZIOS (aberturas + vazio de laje no miolo; nunca no painel sólido).
- Distribuição painéis: meia-chapa 122cm + sobra; abertura = recorte, não junta.
- Faces longas (A/B): pilha 122 até o topo da face.
- Faces curtas passantes (C/D sem abertura lateral): painel contínuo até o void de topo.
- Void de topo (C/D): vazio_laje | residual N2 | altura de viga passante (dim b/h).
- Cotas: módulos + trecho abertura→junta + rebaixo/vazio (quando dual).
- Pressão HIDDEN só A/B; SARR de abertura com L para dentro do vazio.
"""
from __future__ import annotations

import re
from typing import Any

# Meia-chapa sistema fôrma NOVA (cm). Inteira = 244 = 2×122.
MODULO_PAINEL_NOVA_CM = 122.0
H1_DEFAULT_CM = 2.0
FACES_LONGAS = ("A", "B")
FACES_CURTAS = ("C", "D")
# Filete/painel de forma acima da laje no miolo (mesmo offset do sarrafo 7cm).
# Usado só como fallback quando há laje+vazio dual e os níveis não dão rebaixo>0.
FORMA_STRIP_ACIMA_LAJE_CM = 7.0
# Escala AR-CONC: 0.03 era denso demais no viewer; 0.05 = rosado legível sem tapar traço.
# (1.0 fica ralo; 0.03 fica “chapado”.)
HATCH_AR_CONC_SCALE = 0.05

# Degraus de cotas verticais ABCD (offset cm a partir do bordo direito da face).
# Ver docs/SEMANTICA-PILAR-NOVA.md §2.1
DIM_LVL1_OFF = 17.0   # h1=2 + recortes/aberturas (+5 vs base 12)
DIM_LVL2_OFF = 40.0   # medidas dos painéis (módulos / parts) (+10 vs base 30)
DIM_LVL3_OFF = 63.0   # total de painel unido (soma das parts) (+15 vs base 48)


def parse_paineis_unidos(payload: dict, face_id: str) -> list[dict]:
    """Lê paineis_unidos_{face}: subdivisão manual de um módulo (ex. 100+22).

    Formato:
      [{"interval_index": 0, "parts": [100.0, 22.0]}]
    interval_index → índice em paineis_intervals_{face}.
    parts somam ≈ o valor do interval (tol 0.6).
    """
    raw = payload.get(f"paineis_unidos_{face_id}") or payload.get(
        f"paineis_unidos_{str(face_id).upper()}"
    )
    if not raw:
        return []
    out: list[dict] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("interval_index", item.get("idx", -1)))
        except (TypeError, ValueError):
            continue
        parts_raw = item.get("parts") or item.get("partes") or []
        parts: list[float] = []
        for p in parts_raw:
            try:
                v = float(p)
            except (TypeError, ValueError):
                continue
            if v > 0.5:
                parts.append(round(v, 4))
        if idx < 0 or len(parts) < 2:
            continue
        out.append({"interval_index": idx, "parts": parts})
    return out


def expand_intervals_with_unidos(
    intervals: list[float], unidos: list[dict]
) -> tuple[list[float], list[dict]]:
    """Expande malha: parts viram sub-intervalos; devolve também spans de total N3.

    Returns:
      mesh_deltas: lista de deltas para desenhar H (inclui linhas no meio do unido)
      totals_n3: [{y0_rel, y1_rel, total, parts}] em coord relativas acima de h1
    """
    if not intervals:
        return [], []
    by_idx = {u["interval_index"]: u["parts"] for u in unidos}
    mesh: list[float] = []
    totals: list[dict] = []
    y_rel = 0.0
    for i, iv in enumerate(intervals):
        ivf = float(iv)
        parts = by_idx.get(i)
        if parts and abs(sum(parts) - ivf) <= 0.6:
            y0 = y_rel
            for p in parts:
                mesh.append(float(p))
                y_rel = round(y_rel + float(p), 4)
            totals.append(
                {
                    "y0_rel": y0,
                    "y1_rel": y_rel,
                    "total": round(sum(parts), 4),
                    "parts": list(parts),
                    "interval_index": i,
                }
            )
        else:
            if parts and abs(sum(parts) - ivf) > 0.6:
                # parts inconsistentes: ignora união, mantém módulo inteiro
                pass
            mesh.append(ivf)
            y_rel = round(y_rel + ivf, 4)
    return mesh, totals


def distribute_paineis_nova(
    usable_cm: float,
    *,
    module: float = MODULO_PAINEL_NOVA_CM,
    split_modules: bool = True,
) -> list[float]:
    """Distribui a altura útil (acima de h1) em painéis NOVA.

    - Empilha meias-chapas de ``module`` (122cm) de baixo para cima.
    - Sobra = último painel (nunca junta inventada no fundo de abertura).
    - ``split_modules=False``: um único painel contínuo (C/D passantes).
    """
    usable = float(usable_cm or 0.0)
    if usable <= 0.5:
        return []
    if not split_modules or usable <= module + 0.5:
        return [round(usable, 4)]
    n_full = int(usable // module)
    rem = round(usable - n_full * module, 4)
    out: list[float] = [float(module)] * n_full
    if rem > 0.5:
        out.append(rem)
    elif abs(rem) > 1e-6 and out:
        out[-1] = round(out[-1] + rem, 4)
    return out if out else [round(usable, 4)]


def paineis_intervals_for_face(
    *,
    face_id: str,
    height_cm: float,
    h1_cm: float = H1_DEFAULT_CM,
    top_void_cm: float = 0.0,
    has_side_openings: bool = False,
    split_long_faces: bool = True,
) -> list[float]:
    """Intervalos de malha H (acima de h1) para uma face — genérico.

    A/B (longas): módulos 122 + sobra até o topo da face.
    C/D passantes (sem abertura lateral): painel contínuo até base do void de topo.
    C/D com abertura lateral: mesma pilha 122 até o topo (como longas).
    """
    h1 = float(h1_cm or 0.0)
    height = float(height_cm or 0.0)
    top_void = max(0.0, float(top_void_cm or 0.0))
    fid = str(face_id or "").upper()
    if fid in FACES_CURTAS and not has_side_openings:
        usable = max(0.0, height - h1 - top_void)
        return distribute_paineis_nova(usable, split_modules=False)
    usable = max(0.0, height - h1)
    return distribute_paineis_nova(usable, split_modules=bool(split_long_faces))


def _parse_dim_pair_heights(text: str) -> list[float]:
    """Extrai alturas de pares b/h em evidências (ex. 'dim: 19/120' → 120)."""
    out: list[float] = []
    for m in re.finditer(
        r"(\d+(?:[.,]\d+)?)\s*[xX/]\s*(\d+(?:[.,]\d+)?)", str(text or "")
    ):
        a = float(m.group(1).replace(",", "."))
        b = float(m.group(2).replace(",", "."))
        if a > 0 and b > 0:
            out.append(max(a, b))
    return out


def resolve_top_void_cm(
    *,
    face_id: str,
    height_cm: float,
    h1_cm: float,
    vazio_laje_cm: float = 0.0,
    vazio_topo_cm: float = 0.0,
    existing_intervals: list | None = None,
    face_data: dict | None = None,
    payload: dict | None = None,
    has_side_openings: bool = False,
) -> float:
    """Void de topo (cm) para faces passantes — sem hardcode de obra/item.

    Prioridade:
      1. vazio_laje (esp+2 da laje da face)
      2. vazio_topo do contrato (se > 0 e não for flag legada isolada)
      3. residual de intervals N2 já no payload (full − sum(intervals))
      4. maior altura de viga passante nas evidências da face (dim b/h)
      5. 0 → painel sobe o PD inteiro
    """
    if has_side_openings:
        return 0.0
    if float(vazio_laje_cm or 0.0) > 0.5:
        return float(vazio_laje_cm)
    if float(vazio_topo_cm or 0.0) > 0.5:
        return float(vazio_topo_cm)
    h1 = float(h1_cm or 0.0)
    height = float(height_cm or 0.0)
    full = max(0.0, height - h1)
    ivs = existing_intervals or []
    try:
        s = sum(float(x) for x in ivs)
        if full > 1.0 and 1.0 < s < full - 1.0:
            return round(full - s, 4)
    except (TypeError, ValueError):
        pass
    # evidências de viga passante (altura)
    texts: list[str] = []
    face_data = face_data or {}
    fontes = face_data.get("fontes_n1") or {}
    for key in ("passa", "chega", "interior", "lajes"):
        for raw in fontes.get(key) or []:
            texts.append(str(raw))
    payload = payload or {}
    for k, v in payload.items():
        if not str(k).startswith(f"abertura_{face_id}"):
            continue
        if isinstance(v, dict):
            texts.append(str(v.get("_viga") or ""))
            texts.append(str(v.get("_origem") or ""))
    depths: list[float] = []
    for t in texts:
        depths.extend(_parse_dim_pair_heights(t))
    if depths:
        # void de topo típico = altura da viga passante (ex. 120)
        d = max(depths)
        if 5.0 < d < full - 5.0:
            return round(d, 4)
    return 0.0


def normalize_opening_y_rel(
    ab: dict,
    *,
    height_cm: float,
    h1_cm: float,
) -> float:
    """y_rel (acima de h1) da abertura — preserva N2 se válido; alinha ao topo se colada."""
    oh = float(ab.get("altura") or ab.get("height") or 0.0)
    h1 = float(h1_cm or 0.0)
    height = float(height_cm or 0.0)
    max_y = max(0.0, height - h1 - oh)
    raw = ab.get("y_rel")
    if raw is None or raw == "":
        return round(max_y, 4)  # default: sobe ao topo da face
    try:
        y_rel = float(raw)
    except (TypeError, ValueError):
        return round(max_y, 4)
    y_rel = max(0.0, min(y_rel, max_y))
    top_gap = (height - h1) - (y_rel + oh)
    # só “gruda” no topo se já está praticamente lá (erro numérico)
    if 0.0 <= top_gap < 1.5:
        return round(max_y, 4)
    return round(y_rel, 4)


def _iter_face_openings(payload: dict, face_id: str) -> list[tuple[str, dict]]:
    """Lista (key, abertura) para face — suporta abertura_A e abertura_A_1..N."""
    fid = str(face_id).upper()
    out: list[tuple[str, dict]] = []
    single = payload.get(f"abertura_{fid}")
    if isinstance(single, dict) and single:
        out.append((f"abertura_{fid}", single))
        return out
    i = 1
    while True:
        key = f"abertura_{fid}_{i}"
        ab = payload.get(key)
        if not isinstance(ab, dict) or not ab:
            break
        out.append((key, ab))
        i += 1
    return out


def _pillar_top_level_from_payload(payload: dict) -> float | None:
    """Topo de contato do pilar p/ rebaixo = maior nível de laje (N:), não PD/saída.

    Nunca usa ``nivel_saida`` (cota do pavimento de cima / PD) — isso inflaria
    o rebaixo para dezenas/centenas de cm. O rebaixo é a diferença entre o
    topo de forma do pilar e a laje da face (tipicamente poucos cm).
    """
    top = None
    contract = payload.get("_sa_mode_contract") or {}
    faces = contract.get("faces") or {}
    for face in faces.values():
        if not isinstance(face, dict):
            continue
        for raw in (face.get("fontes_n1") or {}).get("lajes") or []:
            lv, _ = parse_slab_level_and_esp(str(raw))
            if lv is None:
                continue
            if top is None or lv > top:
                top = lv
        # nível já consolidado na face
        try:
            nl = face.get("nivel_laje")
            if nl is not None:
                lv = float(nl)
                if top is None or lv > top:
                    top = lv
        except (TypeError, ValueError):
            pass
    return top


def _apply_h2_h3_from_intervals(payload: dict, face_id: str, intervals: list[float]) -> None:
    """Espelha h2/h3 a partir da pilha NOVA (documental, sem hardcode de item)."""
    if not intervals:
        return
    mod = MODULO_PAINEL_NOVA_CM
    fulls = [float(x) for x in intervals if abs(float(x) - mod) < 0.6]
    if fulls:
        payload[f"h2_{face_id}"] = round(sum(fulls), 4)
    else:
        payload[f"h2_{face_id}"] = round(float(intervals[0]), 4)
    sobras = [float(x) for x in intervals if abs(float(x) - mod) >= 0.6]
    if len(intervals) > 1 and sobras:
        payload[f"h3_{face_id}"] = round(sobras[-1], 4)
    elif len(intervals) == 1 and abs(float(intervals[0]) - mod) >= 0.6:
        # painel único ≠ módulo: vai em h2; h3=0
        payload[f"h3_{face_id}"] = 0.0


def enrich_payload_for_abcd_nova(
    payload: dict,
    *,
    pillar_top_level: float | None = None,
) -> dict:
    """Enriquece o JSON do pilar para desenho ABCD no modo NOVA (qualquer item).

    Chamado pelo motor geral (``generate_pilar_zone`` / ``generate_pilar``)
    quando visual_mode=NOVA. Idempotente e sem paths de obra/item.

    - rebaixo/vazio por face a partir do contrato SA
    - y_rel de aberturas normalizado (preserva N2 válido)
    - paineis_intervals_* pela distribuição 122+sobra (A/B) ou contínuo (C/D)
    - níveis abs se pillar_top conhecido
    """
    if not isinstance(payload, dict):
        return payload
    # evita re-enriquecer se já marcado nesta sessão com mesma altura
    height = float(
        payload.get("pd_pavimento_cm")
        or payload.get("altura")
        or 280.0
    )
    contract = payload.get("_sa_mode_contract")
    if not isinstance(contract, dict):
        contract = {}
    faces = contract.get("faces")
    if not isinstance(faces, dict):
        faces = {}

    top = pillar_top_level
    if top is None:
        top = _pillar_top_level_from_payload(payload)

    for fid in "ABCDEFGH":
        face = faces.get(fid) if isinstance(faces.get(fid), dict) else {}
        metrics = face_laje_metrics(face or {}, pillar_top_level=top)
        if face is not None and fid in faces:
            face["rebaixo_laje_cm"] = metrics["rebaixo_laje_cm"]
            face["vazio_laje_cm"] = metrics["vazio_laje_cm"]
            face["nivel_laje"] = metrics["nivel_laje"]
            face["espessura_laje"] = metrics["espessura_laje"]
            faces[fid] = face

        # Preferir métricas do contrato; flat do payload só se não houver face/contrato
        # (nunca herdar rebaixo stale absurdo de run anterior, ex. 311cm).
        rebaixo = float(metrics["rebaixo_laje_cm"] or 0.0)
        vazio_laje = float(metrics["vazio_laje_cm"] or 0.0)
        has_face_ctx = bool(face) or bool(
            (face or {}).get("fontes_n1") if isinstance(face, dict) else False
        )
        if not has_face_ctx:
            try:
                flat_r = float(payload.get(f"rebaixo_laje_{fid}") or 0.0)
            except (TypeError, ValueError):
                flat_r = 0.0
            try:
                flat_v = float(payload.get(f"vazio_laje_{fid}") or 0.0)
            except (TypeError, ValueError):
                flat_v = 0.0
            # sanity: rebaixo de laje é faixa de cm, não metros de PD
            if 0.5 <= flat_r <= 40.0 and rebaixo < 0.5:
                rebaixo = flat_r
            if flat_v > 0.5 and vazio_laje < 0.5:
                vazio_laje = flat_v
        if rebaixo > 40.0:
            rebaixo = 0.0

        h1 = float(payload.get(f"h1_{fid}", payload.get(f"h1_geom_{fid}", H1_DEFAULT_CM)) or H1_DEFAULT_CM)
        payload.setdefault(f"h1_{fid}", h1)

        top_void_contract = 0.0
        if face:
            vt = face.get("vazio_topo") or {}
            if isinstance(vt, dict):
                if vt.get("fonte") in (
                    "laje_espessura_mais_2",
                    "laje_rebaixo_e_vazio_separados",
                    "nulo",
                ):
                    # vazio de laje já vai em vazio_laje_cm; não é void de topo C/D
                    top_void_contract = 0.0
                else:
                    try:
                        top_void_contract = float(vt.get("valor_cm") or 0.0)
                    except (TypeError, ValueError):
                        top_void_contract = 0.0

        openings = _iter_face_openings(payload, fid)
        has_side = False
        has_esq = has_dir = False
        openings_to_top = False
        for key, ab in openings:
            lado = str(ab.get("lado") or "").lower()
            if lado in ("esquerdo", "direito", "meio"):
                has_side = True
            if lado == "esquerdo":
                has_esq = True
            if lado == "direito":
                has_dir = True
            ab = dict(ab)
            ab["y_rel"] = normalize_opening_y_rel(ab, height_cm=height, h1_cm=h1)
            # normaliza chave largura
            if "larg" not in ab and "largura" in ab:
                ab["larg"] = ab["largura"]
            # abertura colada no topo da face?
            try:
                oh = float(ab.get("altura") or 0.0)
                yr = float(ab.get("y_rel") or 0.0)
                if abs((yr + oh) - (height - h1)) < 1.5:
                    openings_to_top = True
            except (TypeError, ValueError):
                pass
            payload[key] = ab

        # Painel/filete ACIMA da laje (anatomia P1, universal em todo item):
        #   face_top
        #     | rebaixo  ← filete de forma (ex. 7cm)  draw_rebaixo_strip
        #   rebaixo_bot
        #     | vazio = esp+2
        #   void_bot
        # Níveis dão rebaixo quando há diferença de cota; senão, com vazio de
        # laje presente (fontes_n1 / métricas):
        #   - dual esq+dir (A/B típico) → filete 7 + aberturas coladas no topo
        #   - sem abertura lateral (PASSA / face só laje) → filete 7 full-width
        dual = has_esq and has_dir
        if vazio_laje > 0.5 and rebaixo < 0.5:
            if dual or not has_side:
                rebaixo = float(FORMA_STRIP_ACIMA_LAJE_CM)
        # Dual com vazio: aberturas sobem ao topo da face (como P1 B), mesmo
        # quando o N2 deixou gap = vazio de laje (ex. y_rel 140 em PD 280).
        if dual and vazio_laje > 0.5:
            for key, ab0 in openings:
                ab = dict(payload.get(key) or ab0)
                try:
                    oh = float(ab.get("altura") or ab.get("height") or 0.0)
                except (TypeError, ValueError):
                    oh = 0.0
                max_y = max(0.0, height - h1 - oh)
                ab["y_rel"] = round(max_y, 4)
                if "larg" not in ab and "largura" in ab:
                    ab["larg"] = ab["largura"]
                payload[key] = ab
            openings_to_top = True
        payload[f"rebaixo_laje_{fid}"] = rebaixo
        payload[f"vazio_laje_{fid}"] = vazio_laje
        if face is not None and fid in faces:
            face["rebaixo_laje_cm"] = rebaixo
            face["vazio_laje_cm"] = vazio_laje
            faces[fid] = face

        old_iv = payload.get(f"paineis_intervals_{fid}") or []
        top_void = resolve_top_void_cm(
            face_id=fid,
            height_cm=height,
            h1_cm=h1,
            vazio_laje_cm=vazio_laje,
            vazio_topo_cm=top_void_contract,
            existing_intervals=list(old_iv) if old_iv else None,
            face_data=face,
            payload=payload,
            has_side_openings=has_side,
        )
        # faces longas não usam top_void na pilha (aberturas/recortes não encolhem módulos)
        iv = paineis_intervals_for_face(
            face_id=fid,
            height_cm=height,
            h1_cm=h1,
            top_void_cm=top_void if fid in FACES_CURTAS else 0.0,
            has_side_openings=has_side,
        )
        if iv:
            payload[f"paineis_intervals_{fid}"] = iv
            _apply_h2_h3_from_intervals(payload, fid, iv)

    # Textos de carimbo: chegada = topo de contato (max laje); saida = chegada + PD.
    # Só preenche se ainda não houver cota absoluta confiável.
    if top is not None and top > 20:
        if not payload.get("nivel_chegada_abs"):
            payload["nivel_chegada_abs"] = float(top)
        try:
            saida_exist = float(payload.get("nivel_saida_abs") or 0)
        except (TypeError, ValueError):
            saida_exist = 0.0
        if saida_exist < 20:
            payload["nivel_saida_abs"] = float(top) + height / 100.0
        payload["pd_pavimento_cm"] = height
    payload["modo_distribuicao"] = str(payload.get("modo_distribuicao") or "NOVA")
    if faces:
        contract["faces"] = faces
        contract["schema"] = contract.get("schema") or "pil.n3_mode_contract.v2"
        payload["_sa_mode_contract"] = contract
    payload["_pl_nova_enriched"] = True
    return payload


def ensure_painel_dimstyle(doc) -> None:
    if "PAINEL" in doc.dimstyles:
        return
    ds = doc.dimstyles.new("PAINEL")
    ds.dxf.dimtxt = 10.0
    ds.dxf.dimasz = 3.0
    ds.dxf.dimexe = 3.0
    ds.dxf.dimexo = 3.0
    ds.dxf.dimgap = 3.0
    ds.dxf.dimtad = 1
    ds.dxf.dimtih = 0
    ds.dxf.dimtoh = 0
    try:
        ds.dxf.dimclrd = 4
        ds.dxf.dimclre = 4
        ds.dxf.dimclrt = 240
    except Exception:
        pass


def ensure_pressure_layer(doc) -> None:
    name = "Sarrafo de Pressão"
    if name not in doc.layers:
        doc.layers.add(name, color=42)
    try:
        doc.layers.get(name).dxf.linetype = "HIDDEN"
    except Exception:
        pass
    if "HIDDEN" not in doc.linetypes:
        doc.linetypes.add(
            "HIDDEN",
            pattern=[9.525, 6.35, -3.175],
            description="Hidden __ __ __",
        )


def parse_slab_level_and_esp(evidence: str | None) -> tuple[float | None, float | None]:
    import re
    text = str(evidence or "")
    nivel = esp = None
    m = re.search(r"N:\s*([0-9]+(?:[.,][0-9]+)?)", text, flags=re.I)
    if m:
        nivel = float(m.group(1).replace(",", "."))
    m = re.search(r"esp:\s*([0-9]+(?:[.,][0-9]+)?)", text, flags=re.I)
    if m:
        esp = float(m.group(1).replace(",", "."))
    return nivel, esp


def compute_rebaixo_and_vazio(
    *,
    slab_level: float | None,
    slab_esp: float | None,
    pillar_top_level: float | None,
) -> tuple[float, float]:
    rebaixo = 0.0
    if slab_level is not None and pillar_top_level is not None:
        pt = float(pillar_top_level)
        sl = float(slab_level)
        if pt > 100 and sl > 100:
            rebaixo = max(0.0, (pt - sl) * 100.0)
        else:
            rebaixo = max(0.0, pt - sl)
    vazio = float(slab_esp) + 2.0 if slab_esp and slab_esp > 0 else 0.0
    return round(rebaixo, 4), round(vazio, 4)


def face_laje_metrics(face_data: dict, *, pillar_top_level: float | None) -> dict:
    lajes = (face_data.get("fontes_n1") or {}).get("lajes") or []
    best_level = best_esp = best_ev = None
    for raw in lajes:
        nivel, esp = parse_slab_level_and_esp(str(raw))
        if nivel is not None and (best_level is None or nivel > best_level):
            best_level, best_esp, best_ev = nivel, esp, str(raw)
        elif esp is not None and best_esp is None:
            best_esp, best_ev = esp, str(raw)
    rebaixo, vazio = compute_rebaixo_and_vazio(
        slab_level=best_level, slab_esp=best_esp, pillar_top_level=pillar_top_level
    )
    return {
        "nivel_laje": best_level,
        "espessura_laje": best_esp,
        "rebaixo_laje_cm": rebaixo,
        "vazio_laje_cm": vazio,
        "evidencia_laje": best_ev,
    }


def panel_break_ys(
    *,
    y_h1_top: float,
    intervals_logical: list[float],
    unidos: list[dict] | None = None,
) -> list[float]:
    """Ys onde o sarrafo é seccionado = cruzamentos de painel (módulos lógicos).

    Junções internas de ``paineis_unidos`` (parts 100|22) NÃO entram: o sarrafo
    continua (e aí a cota N3 totaliza o unido).
    """
    ys = [float(y_h1_top)]
    y = float(y_h1_top)
    for iv in intervals_logical or []:
        y = round(y + float(iv), 4)
        ys.append(y)
    return ys


def draw_vertical_sectioned(
    msp,
    *,
    x: float,
    y0: float,
    y1: float,
    break_ys: list[float] | None,
    layer: str,
    linetype: str | None = None,
    skip_breaks: list[float] | None = None,
) -> int:
    """Vertical seccionada nos cruzamentos com painéis (break_ys).

    skip_breaks: Ys de junção unida (parts) — NÃO seccionar (sarrafo contínuo).
    """
    lo, hi = (y0, y1) if y1 >= y0 else (y1, y0)
    if hi - lo < 0.5:
        return 0
    skip = set()
    for s in skip_breaks or []:
        skip.add(round(float(s), 2))
    cuts = [lo, hi]
    for by in break_ys or []:
        byf = float(by)
        if lo + 0.4 < byf < hi - 0.4 and round(byf, 2) not in skip:
            cuts.append(byf)
    cuts = sorted(set(round(c, 4) for c in cuts))
    attrs: dict[str, Any] = {"layer": layer}
    if linetype:
        attrs["linetype"] = linetype
    n = 0
    for a, b in zip(cuts, cuts[1:]):
        if b - a < 0.45:
            continue
        msp.add_lwpolyline([(x, a), (x, b)], close=False, dxfattribs=attrs)
        n += 1
    return n


def draw_pressure_battens_ab(
    msp,
    *,
    x_left,
    x_right,
    y_bot,
    y_top,
    openings,
    sarr_offset: float = 7.0,
    break_ys: list[float] | None = None,
    skip_breaks: list[float] | None = None,
) -> int:
    """Pressão HIDDEN nas linhas de sarr (offset 7), seccionada nos painéis.

    Manual A (abertura direita): esquerda sobe ao topo; direita para no fundo da abertura.
    Manual B dual: 330/404 só corpo até y_bot da abertura.
    Exemplo seccionamento: trechos 122 + 122 + 58 nas juntas da malha.
    """
    n = 0
    xl = x_left + sarr_offset
    xr = x_right - sarr_offset
    stop_l = min((ab["y_bot"] for ab in openings if ab.get("lado") == "esquerdo"), default=y_top)
    stop_r = min((ab["y_bot"] for ab in openings if ab.get("lado") == "direito"), default=y_top)
    has_esq = any(ab.get("lado") == "esquerdo" for ab in openings)
    has_dir = any(ab.get("lado") == "direito" for ab in openings)

    if has_dir and not has_esq:
        y_body_l, y_body_r = stop_r, stop_r
        y_void_l, y_void_r = y_top, None
    elif has_esq and not has_dir:
        y_body_l, y_body_r = stop_l, stop_l
        y_void_l, y_void_r = None, y_top
    elif has_esq and has_dir:
        y_body_l, y_body_r = stop_l, stop_r
        y_void_l, y_void_r = None, None
    else:
        y_body_l = y_body_r = y_top
        y_void_l = y_void_r = None

    def _v(x, y0, y1):
        nonlocal n
        if y1 is None or y0 is None:
            return
        n += draw_vertical_sectioned(
            msp,
            x=x,
            y0=y0,
            y1=y1,
            break_ys=break_ys,
            layer="Sarrafo de Pressão",
            linetype="HIDDEN",
            skip_breaks=skip_breaks,
        )

    _v(xl, y_bot, y_body_l)
    _v(xr, y_bot, y_body_r)
    if y_void_l is not None and y_body_l is not None:
        _v(xl, y_body_l, y_void_l)
    if y_void_r is not None and y_body_r is not None:
        _v(xr, y_body_r, y_void_r)
    return n


def draw_opening_sarrafos(
    msp, *, x_left, x_right, openings, rebaixo_cm: float = 0.0, y_face_top=None,
    vazio_laje_cm: float = 0.0,
    break_ys: list[float] | None = None,
    skip_breaks: list[float] | None = None,
) -> int:
    """SARR de abertura (manual P1):

    Abertura ÚNICA (ex. face A direita 11cm):
      - barra fundo da abertura em SARR (xi→xo)
      - L 7×7 para DENTRO do vazio (não para a parede)
      - vertical SARR a 7cm para dentro, do y_bot até y_face_top (ou y_top abertura)
      - barra horizontal em y_bot-7 do pé do L até a linha de pressão do mesmo lado

    Dual esq+dir: só barras fundo; L/verticais/travessas em draw_dual_marco_sarrs.
    """
    n = 0
    layer = "SARR_2.2x7"
    corner = 7.0
    _is_dual = any(a.get("lado") == "esquerdo" for a in openings) and any(
        a.get("lado") == "direito" for a in openings
    )
    y_top_ref = y_face_top

    for ab in openings:
        lado = ab.get("lado")
        yb, yt = float(ab["y_bot"]), float(ab["y_top"])
        larg = float(ab.get("larg") or ab.get("largura") or 0.0)
        if larg < 0.5 or yt - yb < 0.5:
            continue

        if lado == "direito":
            xi, xo = x_right - larg, x_right
            # Dual: fundo da abertura já é Painéis parcial — NÃO duplicar em SARR.
            # Single: fundo do vão é COTA stub, não SARR full (manual A).
            if _is_dual:
                continue
            # L contínuo parede→vão→pé→pressão (1 polilinha → 1 MLINE no INI,
            # canto alinhado na parede sem quebra de eixo).
            x_sarr = xi - corner  # 150 se xi=157
            x_press_r = x_right - corner
            pts = [(xi, yb), (x_sarr, yb), (x_sarr, yb - corner)]
            if x_press_r - x_sarr > 0.5:
                pts.append((x_press_r, yb - corner))
            msp.add_lwpolyline(pts, close=False, dxfattribs={"layer": layer})
            n += 1
            # vertical SARR seccionada nos cruzamentos de painel
            y_sarr_top = float(y_top_ref) if y_top_ref is not None else yt
            if y_sarr_top - yb > 0.5:
                n += draw_vertical_sectioned(
                    msp,
                    x=x_sarr,
                    y0=yb,
                    y1=y_sarr_top,
                    break_ys=break_ys,
                    layer=layer,
                    skip_breaks=skip_breaks,
                )

        elif lado == "esquerdo":
            xi = x_left + larg  # parede interna
            if _is_dual:
                continue
            x_sarr = xi + corner
            x_press_l = x_left + corner
            pts = [(xi, yb), (x_sarr, yb), (x_sarr, yb - corner)]
            if x_sarr - x_press_l > 0.5:
                pts.append((x_press_l, yb - corner))
            msp.add_lwpolyline(pts, close=False, dxfattribs={"layer": layer})
            n += 1
            y_sarr_top = float(y_top_ref) if y_top_ref is not None else yt
            if y_sarr_top - yb > 0.5:
                n += draw_vertical_sectioned(
                    msp,
                    x=x_sarr,
                    y0=yb,
                    y1=y_sarr_top,
                    break_ys=break_ys,
                    layer=layer,
                    skip_breaks=skip_breaks,
                )

        elif lado == "meio":
            xl = float(ab.get("x_inn_l") or 0.0)
            xr = float(ab.get("x_inn_r") or 0.0)
            msp.add_line((xl, yb), (xr, yb), dxfattribs={"layer": layer})
            n += 1
    return n


def void_rects_for_face(
    *, x_left, x_right, openings, rebaixo_cm, vazio_laje_cm, y_face_top, y_panel_content_top
):
    """Retângulos de hatch — SOMENTE vazios (nunca painel sólido / rebaixo).

    Dual esq+dir (face B típica):
      - hatch na faixa da abertura ESQ (larg × altura do vão)
      - hatch na faixa da abertura DIR
      - hatch no MIOLO só na faixa do vazio de laje (esp+2), entre rebaixo e base do vazio
      NÃO full-width 88×H (isso sobrepõe o miolo sólido e o filete de rebaixo).

    Single (face A): só a faixa da abertura.
    C/D passante / sem abertura: full width × vazio de topo (ou laje).
    """
    rects = []
    esq = [ab for ab in openings if ab.get("lado") == "esquerdo"]
    dir_ = [ab for ab in openings if ab.get("lado") == "direito"]
    rebaixo = max(0.0, float(rebaixo_cm or 0.0))
    vazio = max(0.0, float(vazio_laje_cm or 0.0))

    def _ab_larg(ab) -> float:
        return float(ab.get("larg") or ab.get("largura") or 0.0)

    def _opening_void_rect(ab):
        lado = ab.get("lado")
        yb = float(ab["y_bot"])
        # vão sobe até o topo da face (aberturas de borda coladas no topo)
        yt = max(float(ab.get("y_top") or yb), float(y_face_top))
        # se há rebaixo+vazio no miolo, as aberturas laterais ainda são vazias até o topo
        larg = _ab_larg(ab)
        if larg < 0.5 or yt - yb < 0.5:
            return None
        if lado == "direito":
            return (x_right - larg, yb, larg, yt - yb)
        if lado == "esquerdo":
            return (x_left, yb, larg, yt - yb)
        if lado == "meio":
            xl = float(ab.get("x_inn_l") or x_left)
            xr = float(ab.get("x_inn_r") or x_right)
            return (xl, yb, max(0.0, xr - xl), yt - yb)
        return None

    if esq and dir_:
        # 1) só as faixas de abertura (não o miolo inteiro)
        for ab in openings:
            r = _opening_void_rect(ab)
            if r:
                rects.append(r)
        # 2) miolo: somente vazio de laje (abaixo do rebaixo, acima da base do vazio)
        xl = x_left + max(_ab_larg(ab) for ab in esq)
        xr = x_right - max(_ab_larg(ab) for ab in dir_)
        if vazio > 0.5 and xr - xl > 0.5:
            y_void_top = y_face_top - rebaixo
            y_void_bot = y_void_top - vazio
            if y_void_top > y_void_bot + 0.5:
                rects.append((xl, y_void_bot, xr - xl, y_void_top - y_void_bot))
        return [(x, y, w, h) for x, y, w, h in rects if w > 0.5 and h > 0.5]

    for ab in openings:
        r = _opening_void_rect(ab)
        if r:
            rects.append(r)

    # Vazio de laje full-width só quando NÃO há aberturas laterais no miolo
    # (single com rebaixo full, ou face sem abertura)
    if vazio > 0.5 and not openings:
        y_top_void = y_face_top - rebaixo
        y_bot_void = y_top_void - vazio
        if y_top_void > y_bot_void + 0.5:
            rects.append((x_left, y_bot_void, x_right - x_left, y_top_void - y_bot_void))
    elif vazio > 0.5 and openings and not (esq and dir_):
        # single abertura: se sobra miolo sólido ao lado, vazio de laje só no trecho sólido
        # (acima da abertura o vão já é void; no trecho sem abertura = faixa laje)
        y_top_void = y_face_top - rebaixo
        y_bot_void = y_top_void - vazio
        if y_top_void > y_bot_void + 0.5:
            # cobre só o retângulo de laje no topo full-width menos as aberturas
            # (abertura single já cobre sua coluna até o topo; evita double-hatch)
            solid_parts = [(x_left, x_right)]
            for ab in openings:
                lado = ab.get("lado")
                larg = _ab_larg(ab)
                if lado == "direito" and larg > 0.5:
                    solid_parts = [(a, min(b, x_right - larg)) for a, b in solid_parts if a < x_right - larg]
                elif lado == "esquerdo" and larg > 0.5:
                    solid_parts = [(max(a, x_left + larg), b) for a, b in solid_parts if b > x_left + larg]
            for a, b in solid_parts:
                if b - a > 0.5:
                    rects.append((a, y_bot_void, b - a, y_top_void - y_bot_void))
    return [(x, y, w, h) for x, y, w, h in rects if w > 0.5 and h > 0.5]


def _rects_touch(a, b, tol=1.0) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw < bx - tol or bx + bw < ax - tol or ay + ah < by - tol or by + bh < ay - tol)


def merge_void_rects(rects):
    if not rects:
        return []
    # um único HATCH com um path por retângulo (como manual multi-path)
    paths = []
    for x, y, w, h in rects:
        paths.append([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])
    return paths


def draw_void_hatches(msp, paths) -> int:
    """Hatch AR-CONC dos vazios — visual do gabarito manual.

    Manual: layer COTA (cor 241 rosada BYLAYER), pattern AR-CONC.
    scale default 0.05 (0.03 chapava; 1.0 ficava ralo).
    """
    if not paths:
        return 0
    # Manual: layer COTA (cor 241 rosada) + BYLAYER no entity.
    # ezdxf default color=7 apaga o rosado — forçar 256 (BYLAYER).
    hatch = msp.add_hatch(dxfattribs={"layer": "COTA"})
    try:
        hatch.dxf.color = 256  # BYLAYER
    except Exception:
        pass
    for poly in paths:
        hatch.paths.add_polyline_path(poly, is_closed=True)
    scale = float(HATCH_AR_CONC_SCALE)
    try:
        hatch.set_pattern_fill("AR-CONC", scale=scale, angle=0.0)
    except Exception:
        try:
            hatch.set_pattern_fill("ANSI31", scale=max(scale, 0.1), angle=45.0)
        except Exception:
            hatch.set_solid_fill(color=241)
    # reforça scale/cor no DXF (set_pattern_fill pode resetar attrs)
    try:
        hatch.dxf.pattern_scale = scale
        hatch.dxf.pattern_angle = 0.0
        hatch.dxf.color = 256
    except Exception:
        pass
    return 1


def draw_rebaixo_strip(msp, *, x_left, x_right, openings, rebaixo_cm, y_face_top) -> int:
    """Painel/filete de forma ACIMA da laje (miolo dual ou faixa single).

    Anatomia (miolo dual, de cima para baixo):
      y_face_top ── H topo miolo (intervals)
        |  rebaixo_cm  ← laterais V em Painéis+COTA (painel acima da laje)
      y_bot = y_face_top - rebaixo
        |  vazio laje (esp+2)  ← hatch + travessa SARR em y_bot
      void_bot

    Dual: só laterais do miolo (xl/xr = paredes internas das aberturas).
    Single: retângulo full width do rebaixo.
    """
    if rebaixo_cm < 0.5:
        return 0
    y_bot = y_face_top - float(rebaixo_cm)
    esq = [ab for ab in openings if ab.get("lado") == "esquerdo"]
    dir_ = [ab for ab in openings if ab.get("lado") == "direito"]
    if esq and dir_:
        xl = x_left + max(float(ab.get("larg") or ab.get("largura") or 0.0) for ab in esq)
        xr = x_right - max(float(ab.get("larg") or ab.get("largura") or 0.0) for ab in dir_)
    else:
        xl, xr = x_left, x_right
    if xr - xl < 0.5:
        return 0
    n = 0
    # Dual: topo do miolo já vem dos intervals — NÃO duplicar H em y_face_top.
    # Laterais do painel acima da laje (Painéis + COTA, como manual).
    for layer in ("Painéis", "COTA"):
        msp.add_line((xl, y_bot), (xl, y_face_top), dxfattribs={"layer": layer})
        msp.add_line((xr, y_bot), (xr, y_face_top), dxfattribs={"layer": layer})
        n += 2
    if not (esq and dir_):
        # single: fecha topo + base do rebaixo full width
        msp.add_line((xl, y_face_top), (xr, y_face_top), dxfattribs={"layer": "Painéis"})
        msp.add_line((xl, y_bot), (xr, y_bot), dxfattribs={"layer": "Painéis"})
        n += 2
    return n


def draw_cd_triple_sarrafos(msp, *, x_left, x_right, y_bot, y_panel_top, h1) -> int:
    width = x_right - x_left
    if width < 5:
        return 0
    # Manual: 3 linhas próximas ao centro (offset ~7 e meio)
    # posições ~ x_left+7, meio, x_right-7 se width~19 → 547,552 e um terceiro?
    # Manual C: 547 e 552 only TWO lines in data — actually 2 pairs = 4?
    # Earlier: 2 polys for C at 547 and 552. So 2 lines for width 19.
    # Use 2 for narrow (<25) and 3 for wider
    y0 = y_bot + h1
    n = 0
    if width <= 25:
        xs = [x_left + 7.0, x_right - 7.0]
        if xs[1] - xs[0] < 1:
            xs = [x_left + width * 0.35, x_left + width * 0.65]
    else:
        xs = [x_left + width * 0.25, x_left + width * 0.5, x_left + width * 0.75]
    for x in xs:
        msp.add_lwpolyline([(x, y0), (x, y_panel_top)], close=False, dxfattribs={"layer": "SARR_2.2x7"})
        n += 1
    return n


def draw_void_outer_cota(
    msp, *, x_left, x_right, openings, y_face_top
) -> int:
    """Contorno externo do vazio em COTA.

    Manual A (só dir): V em x_right de y_bot→topo + H stub fundo abertura (larg).
    Manual B dual: V em x_left e x_right de y_bot→topo.
    NÃO desenha V no lado sólido (esquerda de A sobe em Painéis).
    """
    n = 0
    if not openings:
        return 0
    has_esq = any(ab.get("lado") == "esquerdo" for ab in openings)
    has_dir = any(ab.get("lado") == "direito" for ab in openings)
    is_dual = has_esq and has_dir
    for ab in openings:
        yb = float(ab["y_bot"])
        larg = float(ab.get("larg") or ab.get("largura") or 0.0)
        if ab.get("lado") == "esquerdo":
            msp.add_line((x_left, yb), (x_left, y_face_top), dxfattribs={"layer": "COTA"})
            n += 1
            # stub H fundo só em abertura única (manual A); dual usa Painéis no fundo
            if (not is_dual) and larg > 0.5:
                msp.add_line((x_left, yb), (x_left + larg, yb), dxfattribs={"layer": "COTA"})
                n += 1
        elif ab.get("lado") == "direito":
            msp.add_line((x_right, yb), (x_right, y_face_top), dxfattribs={"layer": "COTA"})
            n += 1
            if (not is_dual) and larg > 0.5:
                # stub H fundo do vão em COTA (manual A: 168→157 em y=-200)
                msp.add_line((x_right - larg, yb), (x_right, yb), dxfattribs={"layer": "COTA"})
                n += 1
    return n



def draw_sp_markers(msp, *, x_left, x_right, y_face_bot) -> int:
    """Marcadores SP sob as faces A/B — alinhados ao manual (leaders para fora).

    Manual: leader parte ~22cm abaixo do fundo da face, junto às bordas;
    texto SP ~60cm abaixo, fora do painel (esquerda/direita).
    """
    n = 0
    y_start = float(y_face_bot) - 22.0
    # esquerdo e direito: espelha o caminho do manual
    specs = [
        # (x_start, sign_out, text_x_off)
        (x_left - 2.0, -1.0, -23.0),
        (x_right + 6.0, +1.0, +26.0),
    ]
    for x0, sign, tx_off in specs:
        pts = [
            (x0, y_start),
            (x0 + sign * 16.0, y_start - 12.0),
            (x0 + sign * 15.0, y_start - 25.0),
            (x0 + sign * 20.0, y_start - 35.0),
        ]
        try:
            msp.add_lwpolyline(
                pts,
                close=False,
                dxfattribs={"layer": "COTA", "color": 4},
            )
            n += 1
        except Exception:
            pass
        tx = x0 + tx_off
        ty = y_start - 39.0
        try:
            msp.add_mtext(
                "SP",
                dxfattribs={
                    "layer": "texto",
                    "insert": (tx, ty),
                    "char_height": 7.5,
                    "color": 4,
                },
            )
            n += 1
        except Exception:
            msp.add_text(
                "SP",
                dxfattribs={
                    "layer": "texto",
                    "insert": (tx, ty),
                    "height": 7.5,
                    "color": 4,
                },
            )
            n += 1
    return n


def draw_dual_marco_sarrs(
    msp,
    *,
    x_left,
    x_right,
    openings,
    rebaixo_cm,
    vazio_laje_cm,
    y_face_top,
    break_ys: list[float] | None = None,
    skip_breaks: list[float] | None = None,
) -> int:
    """Verticais SARR no MARCO (miolo) a 7cm das paredes de abertura — manual 341/375.

    Também: barras H em y_bot-7 ligando pé do L à pressão (330←341 e 375→404).
    """
    esq = [ab for ab in openings if ab.get("lado") == "esquerdo"]
    dir_ = [ab for ab in openings if ab.get("lado") == "direito"]
    if not (esq and dir_):
        return 0
    n = 0
    layer = "SARR_2.2x7"
    corner = 7.0
    yb = min(float(ab["y_bot"]) for ab in openings)
    y_reb_bot = y_face_top - max(0.0, float(rebaixo_cm))
    y_top_sarr = y_reb_bot - max(0.0, float(vazio_laje_cm))  # -97 manual
    if y_top_sarr - yb < 0.5:
        y_top_sarr = y_reb_bot
    # paredes internas das aberturas
    x_inner_l = x_left + max(float(ab["larg"]) for ab in esq)   # 334
    x_inner_r = x_right - max(float(ab["larg"]) for ab in dir_)  # 382
    # inset para o MARCO (centro)
    x_sarr_l = x_inner_l + corner  # 341
    x_sarr_r = x_inner_r - corner  # 375
    for x in (x_sarr_l, x_sarr_r):
        n += draw_vertical_sectioned(
            msp,
            x=x,
            y0=yb,
            y1=y_top_sarr,
            break_ys=break_ys,
            layer=layer,
            skip_breaks=skip_breaks,
        )
    # L contínuo em cada canto do marco (parede→vão→pé→pressão) — 1 MLINE no INI.
    x_press_l = x_left + corner   # 330
    x_press_r = x_right - corner  # 404
    y_bar = yb - corner
    pts_l = [(x_inner_l, yb), (x_sarr_l, yb), (x_sarr_l, y_bar)]
    if x_sarr_l - x_press_l > 0.5:
        pts_l.append((x_press_l, y_bar))
    msp.add_lwpolyline(pts_l, close=False, dxfattribs={"layer": layer})
    pts_r = [(x_inner_r, yb), (x_sarr_r, yb), (x_sarr_r, y_bar)]
    if x_press_r - x_sarr_r > 0.5:
        pts_r.append((x_press_r, y_bar))
    msp.add_lwpolyline(pts_r, close=False, dxfattribs={"layer": layer})
    n += 2
    # travessas: rebaixo em SARR (y_reb_bot); base do vazio em Painéis (manual -97)
    if x_inner_r > x_inner_l + 0.5:
        msp.add_line((x_inner_l, y_reb_bot), (x_inner_r, y_reb_bot), dxfattribs={"layer": layer})
        n += 1
        if vazio_laje_cm > 0.5:
            msp.add_line(
                (x_inner_l, y_top_sarr),
                (x_inner_r, y_top_sarr),
                dxfattribs={"layer": "Painéis"},
            )
            n += 1
    return n

def apply_face_visual_nova(
    msp,
    *,
    fid: str,
    x_left: float,
    x_right: float,
    y_bot: float,
    y_face_top: float,
    y_panel_content_top: float,
    h1: float,
    openings: list[dict],
    pj: dict[str, Any],
    intervals_logical: list[float] | None = None,
) -> int:
    n = 0
    rebaixo = float(pj.get(f"rebaixo_laje_{fid}", 0.0) or 0.0)
    vazio_laje = float(pj.get(f"vazio_laje_{fid}", 0.0) or 0.0)

    # Ys de seccionamento de sarrafo = juntas de módulos lógicos (não parts unidas)
    _ivs = intervals_logical
    if _ivs is None:
        _ivs = pj.get(f"paineis_intervals_{fid}") or []
    unidos = parse_paineis_unidos(pj, fid)
    break_ys = panel_break_ys(
        y_h1_top=y_bot + h1,
        intervals_logical=[float(x) for x in _ivs],
        unidos=unidos,
    )
    # skip_breaks = Ys internos das parts (sarrafo contínuo no unido)
    skip_breaks: list[float] = []
    if unidos:
        _, totals = expand_intervals_with_unidos([float(x) for x in _ivs], unidos)
        for t in totals:
            y = y_bot + h1 + float(t["y0_rel"])
            for p in t["parts"][:-1]:
                y = round(y + float(p), 4)
                skip_breaks.append(y)

    if fid in ("A", "B"):
        n += draw_pressure_battens_ab(
            msp,
            x_left=x_left,
            x_right=x_right,
            y_bot=y_bot + h1,
            y_top=y_face_top,
            openings=openings,
            break_ys=break_ys,
            skip_breaks=skip_breaks,
        )
        n += draw_opening_sarrafos(
            msp,
            x_left=x_left,
            x_right=x_right,
            openings=openings,
            rebaixo_cm=rebaixo,
            y_face_top=y_face_top,
            vazio_laje_cm=vazio_laje,
            break_ys=break_ys,
            skip_breaks=skip_breaks,
        )
        n += draw_dual_marco_sarrs(
            msp,
            x_left=x_left,
            x_right=x_right,
            openings=openings,
            rebaixo_cm=rebaixo,
            vazio_laje_cm=vazio_laje,
            y_face_top=y_face_top,
            break_ys=break_ys,
            skip_breaks=skip_breaks,
        )
        n += draw_rebaixo_strip(
            msp,
            x_left=x_left,
            x_right=x_right,
            openings=openings,
            rebaixo_cm=rebaixo,
            y_face_top=y_face_top,
        )
        n += draw_void_outer_cota(
            msp,
            x_left=x_left,
            x_right=x_right,
            openings=openings,
            y_face_top=y_face_top,
        )
        n += draw_sp_markers(
            msp, x_left=x_left, x_right=x_right, y_face_bot=y_bot,
        )
    elif fid in ("C", "D"):
        # C/D: secciona nos cruzamentos se houver vários módulos
        n_cd = 0
        width = x_right - x_left
        y0s = y_bot + h1
        y1s = y_panel_content_top
        if width > 5 and y1s - y0s > 0.5:
            if width <= 25:
                xs = [x_left + 7.0, x_right - 7.0]
                if xs[1] - xs[0] < 1:
                    xs = [x_left + width * 0.35, x_left + width * 0.65]
            else:
                xs = [x_left + width * 0.25, x_left + width * 0.5, x_left + width * 0.75]
            for x in xs:
                n_cd += draw_vertical_sectioned(
                    msp,
                    x=x,
                    y0=y0s,
                    y1=y1s,
                    break_ys=break_ys,
                    layer="SARR_2.2x7",
                    skip_breaks=skip_breaks,
                )
        n += n_cd

    rects = void_rects_for_face(
        x_left=x_left,
        x_right=x_right,
        openings=openings,
        rebaixo_cm=rebaixo,
        vazio_laje_cm=vazio_laje,
        y_face_top=y_face_top,
        y_panel_content_top=y_panel_content_top,
    )
    if fid in ("C", "D") and not openings and y_face_top > y_panel_content_top + 0.5:
        rects.append((x_left, y_panel_content_top, x_right - x_left, y_face_top - y_panel_content_top))
    paths = merge_void_rects(rects)
    n += draw_void_hatches(msp, paths)
    return n
