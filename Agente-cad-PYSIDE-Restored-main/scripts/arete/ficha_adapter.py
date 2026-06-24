# -*- coding: utf-8 -*-
"""
ficha_adapter.py — Adapter N2→Fase-4 layout (DA-A3 do masterplan).

Estratégia: materializa campos_json da ficha N2 (DB) em pasta temporária
com o layout exato que os geradores STOG esperam, sem modificar os geradores.

API pública:
    query_fichas(classe, pavimento=PAV_13) → list[dict]
    materializar_item(row, tmp_base)       → (obra_dir: Path, json_path: Path)
    get_recorte_path(elemento_id, classe, row=None)  → Path | None
    smoke_test(classe, elemento_id)        → bool  (adapter + gerador sem erro)
"""

import json
import re
import sqlite3
import subprocess
import sys
import shutil
from pathlib import Path

# Adiciona repo ao path para poder importar motores reversos
sys.path.insert(0, str(Path(__file__).parent.parent))

from arete_config import (
    DB_PATH, TMP_DIR, GERADORES, REPO_ROOT, DADOS_OBRAS,
    FASE4_SUBDIR, FASE4_SUFIXO, GERADOR_OUTPUT_PREFIX,
    RECORTES_ROOT, RECORTE_PASTA_PAT, RECORTE_FILE_PREFIX,
    PAV_13, CAMPOS_OBRIGATORIOS, PD_PAVIMENTO_CM, MOTOR_FUNC,
)


# ═════════════════════════════════════════════════════════════════════════════
# 1. Consulta DB
# ═════════════════════════════════════════════════════════════════════════════

def query_fichas(classe: str, pavimento: str = PAV_13) -> list[dict]:
    """
    Retorna todas as fichas N2 de uma classe/pavimento do DB.
    Cada dict tem: id, obra_name, pavimento, classe, elemento_id,
                   campos_json (dict Python já parseado), recorte_path,
                   confianca, status.
    """
    conn = sqlite3.connect(f'file:{DB_PATH}?immutable=1', uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """SELECT id, obra_name, pavimento, classe, elemento_id,
                  campos_json, recorte_path, confianca, status
           FROM reverse_eng_fichas
           WHERE classe = ? AND pavimento = ?
           ORDER BY elemento_id""",
        (classe, pavimento),
    )
    rows = []
    for r in cur.fetchall():
        d = dict(r)
        try:
            d["campos_json"] = json.loads(d["campos_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            d["campos_json"] = {}
        rows.append(d)
    conn.close()
    return rows


def query_ficha_item(classe: str, elemento_id: str,
                     pavimento: str = PAV_13) -> dict | None:
    """Retorna 1 ficha ou None."""
    conn = sqlite3.connect(f'file:{DB_PATH}?immutable=1', uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """SELECT id, obra_name, pavimento, classe, elemento_id,
                  campos_json, recorte_path, confianca, status
           FROM reverse_eng_fichas
           WHERE classe = ? AND pavimento = ? AND elemento_id = ?
           LIMIT 1""",
        (classe, pavimento, elemento_id),
    )
    r = cur.fetchone()
    conn.close()
    if r is None:
        return None
    d = dict(r)
    try:
        d["campos_json"] = json.loads(d["campos_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        d["campos_json"] = {}
    return d


# ═════════════════════════════════════════════════════════════════════════════
# 2. Materializar ficha → layout Fase-4
# ═════════════════════════════════════════════════════════════════════════════

def _clean_campos_json(campos: dict) -> dict:
    """
    Remove _er_meta (metadado N2) antes de escrever o JSON para o gerador.
    O gerador lê apenas os campos estruturais — metadados não atrapalham, mas
    manter limpo evita confusão em diffs de round-trip.
    """
    return {k: v for k, v in campos.items() if k != "_er_meta"}


_PD_RE = re.compile(r"PD:\s*([\d]+[.,][\d]+)", re.IGNORECASE)


def _extract_pd_cm(recorte_path: Path) -> float | None:
    """
    Lê o cabeçalho do recorte ("X PAVIMENTO - PD: Y.YY", em metros) e
    retorna o PD em cm. PD NÃO é constante por pavimento — varia por
    sub-bloco/torre dentro do mesmo `pavimento` do DB (ex.: 1_PAV tem
    P1-P35 com PD:4.25 e P101-P135 com PD:4.08) — por isso é lido do
    PRÓPRIO recorte de cada item, não de uma tabela por pavimento.
    Retorna None se não encontrar (fallback para PD_PAVIMENTO_CM).
    """
    try:
        import ezdxf
        doc = ezdxf.readfile(str(recorte_path))
        for e in doc.modelspace():
            if e.dxftype() not in ("TEXT", "MTEXT"):
                continue
            txt = e.dxf.text if e.dxftype() == "TEXT" else e.text
            m = _PD_RE.search(txt)
            if m:
                return float(m.group(1).replace(",", ".")) * 100.0
    except Exception:
        pass
    return None


def _enriquecer_lv_campos(campos: dict, elemento_id: str,
                          row: dict | None = None) -> None:
    """
    Enriquece *in-place* os campos de uma ficha LV naive com geometria extraída
    do DXF recorte N2.  Chamado pelo materializar_item quando h_A está ausente.
    """
    try:
        # Importar o motor (está no diretório pai de scripts/arete/)
        from motor_reverso_lv import _extract_lv_geom_from_dxf

        recorte = get_recorte_path(elemento_id, "LV", row=row)
        if recorte is None or not recorte.exists():
            return

        geom = _extract_lv_geom_from_dxf(str(recorte), elemento_id)
        geom.pop('_extracao_erro', None)
        conf = geom.pop('_confianca_extracao', 0.4)

        if geom.get('h_A', 0) <= 0:
            return  # extração não produziu dados úteis

        # h_A/h_B: preservar valor N2 se já existir — o N2 tem a altura total correta
        # (ex: 71cm). O geom extraído do recorte tem a altura do painel bruto (ex: 44cm).
        # O patch de h_body nas face_units (em materializar_item) corrige o h_body para
        # usar o valor N2. Nunca sobrescrever h_A/h_B que já vieram do DB.
        if not campos.get('h_A'):
            campos['h_A'] = geom['h_A']
        if not campos.get('h_B'):
            campos['h_B'] = geom.get('h_B', campos['h_A'])
        campos['b_geom']        = geom.get('b_geom', campos.get('total_width', 19.0))
        campos['h_section']     = geom.get('h_section', 55.0)
        campos['h_section_all'] = geom.get('h_section_all', [])
        campos['laje_sup_A']    = geom.get('laje_sup_A', 0.0)
        campos['laje_inf_A']    = geom.get('laje_inf_A', 0.0)
        campos['laje_sup_B']    = geom.get('laje_sup_B', 0.0)
        campos['laje_inf_B']    = geom.get('laje_inf_B', 0.0)
        campos['tipo_viga']     = geom.get('tipo_viga', 'sarrafeada')
        campos['section_views'] = geom.get('section_views', [])
        campos['face_units']    = geom.get('face_units', [])
        campos['panels_A']      = geom.get('panels_A', [])
        campos['panels_B']      = geom.get('panels_B', [])

        # Atualizar total_width/total_height para compatibilidade com gerador legacy
        campos.setdefault('total_width', campos['b_geom'])
        campos['total_height'] = campos['h_A']

        # panels (para o _A.json) — se ainda não tiver, usar panels_A
        if not campos.get('panels') and campos['panels_A']:
            h_a = campos['h_A']
            campos['panels'] = [
                {
                    'width': float(p.get('width', 0)),
                    'height1': h_a, 'height2': h_a,
                    'grade_h1': 0.0, 'grade_h2': 0.0,
                    'laje_central_alt': 0.0, 'reuse': False,
                    'panel_type': str(p.get('panel_type', 'Sarrafeado')),
                }
                for p in campos['panels_A'] if float(p.get('width', 0)) > 0
            ]

        if campos.get('_er_meta'):
            campos['_er_meta']['enriched_by_dxf'] = True
            campos['_er_meta']['dxf_conf'] = conf

    except Exception:
        pass  # enriquecimento é best-effort — jamais bloquear materialização


def _criar_fichas_lv_v2(obra_dir: Path, elemento_id: str, campos: dict) -> None:
    """
    Cria (ou atualiza) fichas_lv_v2.json em obra_dir com os dados da ficha
    enriquecida.  O gerador lê este arquivo com prioridade máxima para
    h_cm, b_cm, laje_sup/inf, largura_cm e panel_type por segmento.
    """
    vname = re.sub(r'_[AB]$', '', elemento_id)
    b_cm  = float(campos.get('b_geom', campos.get('total_width', 19.0)) or 19.0)

    def _make_seg(p: dict, h_face: float) -> dict:
        w = float(p.get('largura_cm', p.get('width', 0)) or 0)
        return {
            'largura_cm':      w,
            'panel_type':      p.get('panel_type', 'Sarrafeado'),
            'height1':         h_face,
            'height2':         h_face,
            'grade_h1':        float(p.get('grade_h1', 0) or 0),
            'grade_h2':        float(p.get('grade_h2', 0) or 0),
            'laje_sup_local':  float(p.get('slab_top', p.get('laje_sup_local', 0)) or 0),
            'laje_inf_local':  float(p.get('slab_bottom', p.get('laje_inf_local', 0)) or 0),
            'slab_top':        float(p.get('slab_top', 0) or 0),
            'slab_bottom':     float(p.get('slab_bottom', 0) or 0),
            'slab_center':     float(p.get('slab_center', 0) or 0),
            'laje_central_alt':float(p.get('laje_central_alt', 0) or 0),
            'holes':           p.get('holes', []),
            'is_first':        bool(p.get('is_first', False)),
            'is_last':         bool(p.get('is_last', False)),
            'reuse':           bool(p.get('reuse', False)),
            'codigos_forma':   p.get('codigos_forma', []),
        }

    # Consolidar numa única entrada por viga (face A + B juntos)
    h_A  = float(campos.get('h_A', 0) or 0)
    h_B  = float(campos.get('h_B', h_A) or h_A)
    if h_A <= 0 and h_B <= 0:
        return

    panels_A = campos.get('panels_A', campos.get('panels', []))
    panels_B = campos.get('panels_B', [])
    segs_A = [_make_seg(p, h_A) for p in panels_A
               if float(p.get('largura_cm', p.get('width', 0)) or 0) > 0]
    segs_B = [_make_seg(p, h_B) for p in panels_B
               if float(p.get('largura_cm', p.get('width', 0)) or 0) > 0]

    entry = {
        'viga':          vname,
        'face':          'A',
        'h_cm':          h_A,
        'h_B_cm':        h_B,
        'b_cm':          b_cm,
        'laje_sup_cm':   float(campos.get('laje_sup_A', 0) or 0),
        'laje_inf_cm':   float(campos.get('laje_inf_A', 0) or 0),
        'laje_sup_B_cm': float(campos.get('laje_sup_B', 0) or 0),
        'laje_inf_B_cm': float(campos.get('laje_inf_B', 0) or 0),
        'h_section_cm':  float(campos.get('h_section', 55.0) or 55.0),
        'h_section_all': campos.get('h_section_all', []),
        'tipo_viga':     campos.get('tipo_viga', 'sarrafeada'),
        'section_views': campos.get('section_views', []),
        'face_units':    campos.get('face_units', []),
        'segmentos':     segs_A,
        'segmentos_B':   segs_B,
        'pillar_left':   campos.get('pillar_left', {'active': False}),
        'pillar_right':  campos.get('pillar_right', {'active': False}),
    }
    fichas_dir = obra_dir / 'Fase-6_Execucao_CAD' / 'granular' / 'fichas'
    fichas_dir.mkdir(parents=True, exist_ok=True)
    fichas_path = fichas_dir / 'fichas_lv_v2.json'

    # Mesclar com entradas existentes (preservar outras vigas no mesmo arquivo)
    existing: list = []
    if fichas_path.exists():
        try:
            existing = json.loads(fichas_path.read_text(encoding='utf-8'))
        except Exception:
            existing = []

    # Remover entradas antigas desta viga e adicionar a nova (1 por viga)
    existing = [e for e in existing if e.get('viga') != vname]
    existing.append(entry)

    fichas_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False), encoding='utf-8'
    )


def extrair_ficha_dinamica(recorte_path: Path, classe: str,
                           elemento_id: str) -> dict:
    """
    Extrai ficha N2 dinamicamente do recorte DXF via motor_reverso — mesmo
    pipeline que o Comparison Engine usa ao selecionar um item na lista.

    Retorna dict com os campos extraídos, ou {'_extracao_erro': msg} em caso
    de falha.  Nunca lança exceção.
    """
    import importlib
    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    mod_name, func_name = MOTOR_FUNC[classe]
    try:
        mod  = importlib.import_module(mod_name)
        func = getattr(mod, func_name)
        result = func(str(recorte_path), elemento_id)
        return result or {}
    except Exception as exc:
        return {"_extracao_erro": str(exc)}


def get_real_n4_path(obra_name: str, classe: str, elemento_id: str) -> Path:
    """
    Path canônico do N4 no diretório real da obra — o mesmo arquivo que a CE
    exibe no viewer após clicar 'Gerar N4'.

    Estrutura: {DADOS_OBRAS}/{obra_name}/Fase-6_Execucao_CAD/n4/{prefix}{id}.dxf
    """
    prefix = GERADOR_OUTPUT_PREFIX[classe]
    return (DADOS_OBRAS / obra_name / "Fase-6_Execucao_CAD" / "n4"
            / f"{prefix}{elemento_id}.dxf")


def materializar_item(row: dict, tmp_base: Path | None = None,
                      campos_override: dict | None = None) -> tuple[Path, Path]:
    """
    Materializa a ficha N2 em disco no layout esperado pelo gerador.

    Args:
        row: dict retornado por query_fichas / query_ficha_item
        tmp_base: pasta-base para criar o obra_dir (default: TMP_DIR)

    Returns:
        (obra_dir, json_path)
        - obra_dir : pasta raiz passada para --obra do gerador
        - json_path: caminho do JSON escrito
    """
    base = tmp_base or TMP_DIR
    base.mkdir(parents=True, exist_ok=True)

    classe      = row["classe"]
    elemento_id = row["elemento_id"]

    if campos_override is not None:
        # Modo dinâmico: ficha extraída ao vivo pelo motor_reverso.
        # O motor já extraiu pd_pavimento_cm do próprio recorte — não sobrescrever.
        campos = _clean_campos_json(campos_override)
    else:
        # Modo legado: ficha estática do DB.
        campos = _clean_campos_json(row["campos_json"])
        # Enriquecimento de pavimento (carimbo, nao do elemento): PD do
        # cabecalho ABCD, lido do PROPRIO recorte do item (ver _extract_pd_cm —
        # PD nao e' constante por pavimento, varia por sub-bloco/torre). Fallback
        # para PD_PAVIMENTO_CM se o recorte nao tiver o cabecalho legivel.
        pd_cm = None
        recorte_path = get_recorte_path(elemento_id, classe, row=row)
        if recorte_path:
            pd_cm = _extract_pd_cm(recorte_path)
        if pd_cm is None:
            pd_cm = PD_PAVIMENTO_CM.get(row.get("pavimento"))
        if pd_cm is not None:
            campos.setdefault("pd_pavimento_cm", pd_cm)

    # Pasta única por item (idempotente: sobrescreve se já existia).
    # Inclui o pavimento na chave (Fase A, multi-pavimento): elemento_id se
    # repete entre pavimentos (ex.: P10 existe em 12_PAV E 14_PAV) — sem o
    # pavimento na chave, runs paralelos/sequenciais de pavimentos diferentes
    # colidem na mesma pasta TMP e corrompem o JSON/PD um do outro.
    pavimento = row.get("pavimento", "SEMPAV")
    obra_dir = base / f"{classe}_{pavimento}_{elemento_id}"
    obra_dir.mkdir(parents=True, exist_ok=True)

    # Sub-pasta Fase-4
    json_subdir = obra_dir / FASE4_SUBDIR[classe]
    json_subdir.mkdir(parents=True, exist_ok=True)

    # Para LV: enriquecer campos com geometria extraída do DXF ANTES de escrever
    # qualquer JSON, para que _A.json e _B.json já tenham os dados completos.
    if classe == "LV" and (not campos.get("h_A") or not campos.get("face_units")):
        _enriquecer_lv_campos(campos, elemento_id, row=row)

    # Patch h_body/h_total nas face_units com h_A/h_B do N2 (sempre, fora do enricher,
    # para cobrir face_units que já vêm do DB com h_body do recorte — ex: V301 com 8 units
    # a h_body=126 no DB mas h_A=132 no N2).
    if classe == "LV" and campos.get("face_units"):
        _h_a = float(campos.get("h_A", 0) or 0)
        _h_b = float(campos.get("h_B", _h_a) or _h_a)
        if _h_a > 0:
            for _fu in campos["face_units"]:
                if isinstance(_fu, dict):
                    _side = str(_fu.get("side", "A")).upper()
                    _h    = _h_b if _side == "B" else _h_a
                    _fu["h_body"]  = _h
                    _fu["h_total"] = _h
                    for _fp in _fu.get("panels") or _fu.get("segments") or []:
                        if isinstance(_fp, dict):
                            _fp["height1"] = _h
                            _fp["height2"] = _h

    # Arquivo JSON (_A.json para LV, único para PIL/FV/LAJ)
    sufixo   = FASE4_SUFIXO[classe]
    filename = f"{elemento_id}{sufixo}.json"
    json_path = json_subdir / filename
    json_path.write_text(
        json.dumps(campos, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if classe == "LV":
        # _B.json: mesmos campos mas com panels_B como panels (se disponível).
        campos_b = dict(campos)
        campos_b["side"] = "B"
        campos_b["name"] = re.sub(r"_A$", "", campos_b.get("name", elemento_id)) + "_B"
        if campos.get("panels_B"):
            h_b = float(campos.get("h_B", campos.get("h_A", 0)) or 0)
            panels_b_full = []
            for p in campos["panels_B"]:
                panels_b_full.append({
                    "width":            float(p.get("width", 0)),
                    "height1":          h_b,
                    "height2":          h_b,
                    "grade_h1":         float(p.get("grade_h1", 0) or 0),
                    "grade_h2":         float(p.get("grade_h2", 0) or 0),
                    "laje_central_alt": 0.0,
                    "reuse":            bool(p.get("reuse", False)),
                    "panel_type":       str(p.get("panel_type", "Sarrafeado")),
                })
            campos_b["panels"] = panels_b_full
        b_path = json_subdir / f"{elemento_id}_B.json"
        b_path.write_text(
            json.dumps(campos_b, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # fichas_lv_v2.json: fonte de h_cm, b_cm, laje_sup/inf, largura_cm por segmento.
        # É lida pelo gerador com prioridade máxima sobre qualquer fórmula.
        if campos.get("h_A", 0):
            _criar_fichas_lv_v2(obra_dir, elemento_id, campos)

    # Criar Fase-6_Execucao_CAD/ (destino do DXF gerado)
    (obra_dir / "Fase-6_Execucao_CAD").mkdir(parents=True, exist_ok=True)

    return obra_dir, json_path


def get_output_dxf_path(obra_dir: Path, classe: str,
                         elemento_id: str) -> Path:
    """Retorna o path esperado do DXF N4 gerado."""
    prefix = GERADOR_OUTPUT_PREFIX[classe]
    return obra_dir / "Fase-6_Execucao_CAD" / f"{prefix}{elemento_id}.dxf"


# ═════════════════════════════════════════════════════════════════════════════
# 3. Localizar recorte N2 (gabarito)
# ═════════════════════════════════════════════════════════════════════════════

def get_recorte_path(elemento_id: str, classe: str,
                     recortes_root: Path | None = None,
                     row: dict | None = None) -> Path | None:
    """
    Encontra o DXF do recorte N2 (gabarito) para um elemento.

    Estrategia (Fase A+B — multi-pavimento + preferencia `_sel_` > `_motor_`):
    1. Se `row` (ficha do DB) tiver `recorte_path`, usa a PASTA desse path —
       ja' e' a pasta correta do pavimento/obra do item (gravada pelo
       Diagnostic Reverse Hub), sem precisar adivinhar nome de pasta.
       Dentro dela: prefere `{prefix}{elemento_id}_sel_*.dxf` (re-recorte
       manual mais recente) sobre `{prefix}{elemento_id}_motor_*.dxf`
       (extracao automatica original); entre varios candidatos do mesmo
       tipo, usa o de mtime mais recente.
    2. Fallback: varre RECORTES_ROOT pelo padrao generico da classe
       (RECORTE_PASTA_PAT) e repete a mesma preferencia na primeira pasta
       com match.

    Returns: Path do DXF ou None se não encontrado.
    """
    root   = recortes_root or RECORTES_ROOT
    prefix = RECORTE_FILE_PREFIX[classe]

    def _pick(pasta: Path) -> Path | None:
        for tag in ("_sel_", "_motor_"):
            candidates = sorted(
                pasta.glob(f"{prefix}{elemento_id}{tag}*.dxf"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                return candidates[0]
        return None

    if row and row.get("recorte_path"):
        pasta = Path(row["recorte_path"]).parent
        if pasta.is_dir():
            found = _pick(pasta)
            if found:
                return found
            stored = Path(row["recorte_path"])
            if stored.exists():
                return stored

    pat_pasta = RECORTE_PASTA_PAT[classe]
    for pasta in root.glob(pat_pasta):
        if not pasta.is_dir():
            continue
        found = _pick(pasta)
        if found:
            return found

    return None


# ═════════════════════════════════════════════════════════════════════════════
# 4. Rodar gerador (subprocess)
# ═════════════════════════════════════════════════════════════════════════════

def rodar_gerador(obra_dir: Path, classe: str,
                  elemento_id: str) -> tuple[bool, str]:
    """
    Chama o gerador STOG via subprocess com --obra {obra_dir} --item {elemento_id}.

    Returns:
        (ok: bool, log: str)
    """
    gerador = GERADORES[classe]
    cmd = [
        sys.executable, str(gerador),
        "--obra", str(obra_dir),
        "--item", elemento_id,
        "--max", "1",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(REPO_ROOT),
        )
        log = (result.stdout or "") + (result.stderr or "")
        ok  = result.returncode == 0
        return ok, log
    except subprocess.TimeoutExpired:
        return False, "[TIMEOUT] gerador demorou >120s"
    except Exception as exc:
        return False, f"[EXCEPTION] {exc}"


# ═════════════════════════════════════════════════════════════════════════════
# 5. Smoke test
# ═════════════════════════════════════════════════════════════════════════════

def smoke_test(classe: str, elemento_id: str,
               pavimento: str = PAV_13) -> dict:
    """
    Smoke test de 1 item: query DB → materializar → rodar gerador.

    Returns dict com: ok, classe, elemento_id, campos_ok, gerador_ok,
                      dxf_path, log, erro.
    """
    result = {
        "classe": classe, "elemento_id": elemento_id,
        "ok": False, "campos_ok": False, "gerador_ok": False,
        "dxf_path": None, "log": "", "erro": "",
    }

    # 1. Query DB
    row = query_ficha_item(classe, elemento_id, pavimento)
    if row is None:
        result["erro"] = f"Ficha não encontrada no DB: {classe}/{elemento_id}/{pavimento}"
        return result

    # 2. Validar campos obrigatórios
    campos = row["campos_json"]
    obrig  = CAMPOS_OBRIGATORIOS.get(classe, [])
    faltam = [c for c in obrig if not campos.get(c)]
    if faltam:
        result["erro"] = f"Campos obrigatórios faltando: {faltam}"
        return result
    result["campos_ok"] = True

    # 3. Materializar
    obra_dir, json_path = materializar_item(row)

    # 4. Rodar gerador
    ok_gen, log = rodar_gerador(obra_dir, classe, elemento_id)
    result["gerador_ok"] = ok_gen
    result["log"] = log

    if not ok_gen:
        result["erro"] = f"Gerador falhou (rc≠0). Ver log."
        return result

    # 5. Verificar DXF gerado
    dxf_path = get_output_dxf_path(obra_dir, classe, elemento_id)
    if dxf_path.exists() and dxf_path.stat().st_size > 0:
        result["dxf_path"] = str(dxf_path)
        result["ok"] = True
    else:
        result["erro"] = f"DXF não gerado ou vazio: {dxf_path}"

    return result


def smoke_test_all_classes(pavimento: str = PAV_13) -> dict:
    """
    Roda smoke_test para 1 item de cada classe do pavimento.
    Usa o primeiro elemento_id encontrado no DB por classe.
    """
    exemplos = {
        "PIL": "P1",
        "LV":  "V13",
        "FV":  "V301",
        "LAJ": "L301",
    }
    resultados = {}
    for cls, elem in exemplos.items():
        print(f"\n── Smoke test {cls}/{elem} ──")
        r = smoke_test(cls, elem, pavimento)
        resultados[cls] = r
        status = "✓ PASS" if r["ok"] else f"✗ FAIL — {r['erro']}"
        print(f"  {status}")
        if not r["ok"] and r["log"]:
            # Mostrar últimas 5 linhas do log
            tail = "\n".join(r["log"].splitlines()[-5:])
            print(f"  LOG:\n{tail}")
    return resultados


# ═════════════════════════════════════════════════════════════════════════════
# 6. Limpeza
# ═════════════════════════════════════════════════════════════════════════════

def limpar_tmp(classe: str | None = None, elemento_id: str | None = None,
               pavimento: str | None = None):
    """Remove pasta(s) de tmp. Sem args: limpa tudo."""
    if classe and elemento_id:
        if pavimento:
            ps = [TMP_DIR / f"{classe}_{pavimento}_{elemento_id}"]
        else:
            ps = list(TMP_DIR.glob(f"{classe}_*_{elemento_id}"))
        for p in ps:
            if p.exists():
                shutil.rmtree(p)
    elif TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)


# ═════════════════════════════════════════════════════════════════════════════
# CLI: python ficha_adapter.py smoke [PIL P1] | all
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Ficha Adapter — Arete AR-0.1")
    sub = p.add_subparsers(dest="cmd")

    s1 = sub.add_parser("smoke", help="Smoke test de 1 item")
    s1.add_argument("classe",     help="PIL|LV|FV|LAJ")
    s1.add_argument("elemento_id", help="ex: P1, V13, L301")
    s1.add_argument("--pav", default=PAV_13)

    sub.add_parser("all",  help="Smoke test de 1 item de cada classe")
    sub.add_parser("list", help="Lista fichas disponíveis no DB")

    args = p.parse_args()

    if args.cmd == "smoke":
        r = smoke_test(args.classe, args.elemento_id, args.pav)
        print(json.dumps(r, indent=2, ensure_ascii=False, default=str))

    elif args.cmd == "all":
        rs = smoke_test_all_classes()
        n_ok = sum(1 for r in rs.values() if r["ok"])
        print(f"\n═══ Resultado: {n_ok}/{len(rs)} PASS ═══")

    elif args.cmd == "list":
        for cls in ("PIL", "LV", "FV", "LAJ"):
            rows = query_fichas(cls)
            ids  = [r["elemento_id"] for r in rows]
            print(f"{cls}: {len(rows)} fichas — {ids[:5]}{'...' if len(ids)>5 else ''}")

    else:
        p.print_help()
