"""Recorte por torre/detalhes (2026-07-07) — motor REAL de review visual.

Achado ao vivo com o dono: o que a aba Recortes do portal mostrava até agora
(RecorteMotor, classes PIL/LV/FV/LAJ) é o motor de ENGENHARIA REVERSA (usado
por `scripts/engrev_laj_recorte_loop.py` pra treinar o SA por elemento — 1
recorte por laje/pilar/viga), não o que o dono quer REVISAR na aba Recortes.

O motor certo pra revisão é `scripts/obra_crop_engine.py` (DBSCAN): recorta o
bruto inteiro em "torre 1" (cluster principal, planta limpa inteira) +
"detalhes" (clusters menores unificados — notas, cotas de referência,
convenções). É o mesmo motor do diagnostic_hub.py real (torre/detalhe).

Rodamos as funções PURAS de detecção/recorte (`detect_regions`, `crop_dxf`,
`crop_dxf_multi`) com paths explícitos do obra_dir do portal — NUNCA a
`process_pavimento_crops`/`ensure_recortes_in_db` do script original, que
assume `DADOS_ROOT/<obra_name>/...` (sem a pasta de e-mail do membro, usada
pelo desktop) e grava em `project_data.vision` (proibido pela regra de
fronteira do portal — HANDOFF §3, só leitura de arquivo em disco aqui).
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def _dir_recortes_bruto(obra_dir: Path, bruto_stem: str) -> Path:
    return obra_dir / "Fase-2_Triagem" / "recortes" / bruto_stem



def _ler_validacao(out_dir: Path) -> dict:
    vf = out_dir / "validado.json"
    if vf.is_file():
        import json
        try:
            return json.loads(vf.read_text(encoding="utf-8"))
        except:
            return {}
    return {}

def _salvar_validacao(out_dir: Path, data: dict):
    vf = out_dir / "validado.json"
    import json
    vf.write_text(json.dumps(data), encoding="utf-8")

def set_recorte_validado(obra_dir: Path, bruto_stem: str, item_id: str, validado: bool):
    out_dir = _dir_recortes_bruto(obra_dir, bruto_stem)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = _ler_validacao(out_dir)
    data[item_id] = validado
    
    # Anti-repetição: se invalidou, extrai o bbox do DXF e salva como bad_bbox
    if not validado and item_id.startswith("torre"):
        dxf_path = out_dir / f"{item_id}.dxf"
        if dxf_path.is_file():
            from portal.app.dxf_preview import obter_bbox_dxf
            bbox = obter_bbox_dxf(dxf_path)
            if bbox:
                bad_bboxes = data.get("bad_bboxes", [])
                bad_bboxes.append(bbox)
                data["bad_bboxes"] = bad_bboxes
                
    _salvar_validacao(out_dir, data)

def gerar_recortes_bruto(
    obra_dir: Path, dxf_bruto_path: Path, bruto_stem: str, *, n_torres: int = 1, force: bool = False,
) -> dict:
    """Detecta e recorta torre(s)+detalhes de um DXF bruto. Idempotente (skip
    se já existir, a menos que force=True). Nunca inventa geometria — se o
    DBSCAN não achar cluster, devolve erro explícito (sem gerar arquivo)."""
    from scripts.obra_crop_engine import crop_dxf, crop_dxf_multi, detect_regions

    out_dir = _dir_recortes_bruto(obra_dir, bruto_stem)
    validados = _ler_validacao(out_dir)
    bad_bboxes = validados.get("bad_bboxes", None)

    if not force and out_dir.exists() and any(out_dir.glob("torre_*.dxf")):
        return {"cached": True, "out_dir": str(out_dir)}

    regions = detect_regions(dxf_bruto_path, n_torres=n_torres, bad_bboxes=bad_bboxes)
    if regions.get("error"):
        return {"cached": False, "out_dir": str(out_dir), "error": regions["error"]}

    out_dir.mkdir(parents=True, exist_ok=True)
    resultado: dict = {"cached": False, "out_dir": str(out_dir), "torres": [], "detalhes": None, "error": None}

    for i, torre in enumerate(regions["torres"], 1):
        nome_torre = f"torre_{i}"
        out_path = out_dir / f"{nome_torre}.dxf"
        if validados.get(nome_torre) and out_path.is_file():
            resultado["torres"].append({"nome": nome_torre, "path": str(out_path), "entidades": 0, "cached": True})
            continue

        out_path = out_dir / f"torre_{i}.dxf"
        crop = crop_dxf(dxf_bruto_path, out_path, torre["bbox"], padding_pct=0.01)
        if crop.get("error"):
            resultado["error"] = f"torre_{i}: {crop['error']}"
            continue
        resultado["torres"].append({"nome": f"torre_{i}", "path": str(out_path),
                                     "entidades": crop["entities_copied"]})

    if regions["detalhes"]:
        out_path = out_dir / "detalhes.dxf"
        if validados.get("detalhes") and out_path.is_file():
            resultado["detalhes"] = {"nome": "detalhes", "path": str(out_path), "entidades": 0, "cached": True}
        else:
            bboxes = [d["bbox"] for d in regions["detalhes"]]
            crop = crop_dxf_multi(dxf_bruto_path, out_path, bboxes, padding_pct=0.01)
            if crop.get("error"):
                resultado["error"] = f"detalhes: {crop['error']}"
            else:
                resultado["detalhes"] = {"nome": "detalhes", "path": str(out_path),
                                          "entidades": crop["entities_copied"]}

    return resultado


def listar_recortes_bruto(obra_dir: Path, bruto_stem: str) -> list[dict]:
    """Itens já gerados (torre_1, torre_2..., detalhes) pra um bruto — só lê o
    disco, não gera nada (geração é ação explícita via gerar_recortes_bruto)."""
    out_dir = _dir_recortes_bruto(obra_dir, bruto_stem)
    if not out_dir.exists():
        return []
    validados = _ler_validacao(out_dir)
    itens = []
    for p in sorted(out_dir.glob("*.dxf")):
        if p.stem == "detalhes":
            titulo = "Detalhes e Convenções Gerais"
        else:
            titulo = p.stem.replace("_", " ").title()
        itens.append({
            "item_id": p.stem,
            "titulo": titulo,
            "path": str(p),
            "validado": validados.get(p.stem, False)
        })
    return itens


def obter_recorte_bruto(obra_dir: Path, bruto_stem: str, item_id: str) -> dict | None:
    for item in listar_recortes_bruto(obra_dir, bruto_stem):
        if item["item_id"] == item_id:
            return item
    return None


def excluir_recorte(obra_dir: Path, bruto_stem: str, item_id: str):
    idx_path = _index_path(obra_dir, bruto_stem)
    if not idx_path.exists():
        return
    with open(idx_path, 'r', encoding='utf-8') as f:
        linhas = [L.strip() for L in f if L.strip()]
    
    novas_linhas = []
    excluido = False
    import json
    for L in linhas:
        try:
            doc = json.loads(L)
            if doc.get("item_id") == item_id:
                excluido = True
                # Podemos tambem apagar os arquivos (o dxf e a thumb svg).
                path_dxf = Path(doc.get("path", ""))
                if path_dxf.exists():
                    try: path_dxf.unlink()
                    except: pass
                # A thumbnail fica em .previews/{item_id}.svg
                try: 
                    cache_dir = obra_dir / ".previews"
                    (cache_dir / f"{item_id}.svg").unlink(missing_ok=True)
                except: pass
                continue
            novas_linhas.append(L)
        except Exception:
            novas_linhas.append(L)
            
    if excluido:
        # Atomic write back to avoid corruption
        temp_idx = idx_path.with_suffix('.tmp')
        with open(temp_idx, 'w', encoding='utf-8') as f:
            for L in novas_linhas:
                f.write(L + '\n')
        temp_idx.replace(idx_path)
