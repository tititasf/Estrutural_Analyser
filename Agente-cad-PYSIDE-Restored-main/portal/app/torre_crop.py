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

# [novo, a pedido do dono] classes fixas do Modo Recorte Manual — mesmas
# classes que a arvore de Recortes ja usa (torre_N do DBSCAN + detalhes),
# mais as 2 convencoes e "outros" que so' existiam via texto livre ate' agora.
# Titulo aqui e' so' pra exibicao (acentuado); o item_id/nome de arquivo em
# disco continua ASCII (sanitizado em manual_crop_endpoint).
CLASSES_RECORTE_MANUAL = (
    ("torre_1", "Torre 1"),
    ("torre_2", "Torre 2"),
    ("detalhes", "Detalhes e Convenções Gerais"),
    ("convencao_pilares", "Convenção de Pilares"),
    ("convencao_niveis", "Convenção de Níveis"),
    ("outros", "Outros"),
)
_TITULOS_RECORTE = dict(CLASSES_RECORTE_MANUAL)


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

def contar_entidades(dxf_path: Path) -> int:
    """Entidades do modelspace de um DXF já em disco. 0 se ilegível.

    [2026-07-30] Existe porque o caminho de cache reportava `entidades: 0` fixo
    para recortes já validados pelo humano. O arquivo tinha conteúdo real, mas a
    UI recebia 0 e a região aparecia como vazia/quebrada — e o teste do crop de
    torre falhava com `assert 0 > 0` sem que houvesse defeito de geometria.
    """
    try:
        import ezdxf
        doc = ezdxf.readfile(str(dxf_path))
        return sum(1 for _ in doc.modelspace())
    except Exception as exc:  # noqa: BLE001 - DXF corrompido não pode derrubar a listagem
        log.warning("falha ao contar entidades de %s: %s", dxf_path, exc)
        return 0


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
            # Validado pelo humano: NÃO regenerar (sobrescreveria trabalho aprovado),
            # mas contar o arquivo real — 0 fixo aqui fazia a torre parecer vazia.
            resultado["torres"].append({
                "nome": nome_torre, "path": str(out_path),
                "entidades": contar_entidades(out_path), "cached": True,
            })
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
            resultado["detalhes"] = {
                "nome": "detalhes", "path": str(out_path),
                "entidades": contar_entidades(out_path), "cached": True,
            }
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
        if p.stem in _TITULOS_RECORTE:
            titulo = _TITULOS_RECORTE[p.stem]
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


def excluir_recorte(obra_dir: Path, bruto_stem: str, item_id: str) -> bool:
    """Apaga o .dxf de 1 item de recorte + sua entrada em validado.json —
    usado quando o dono quer descartar um recorte errado antes de gerar um
    novo manualmente (Modo Recorte Manual). Nunca mexe nos outros itens do
    mesmo bruto.

    [FIX] a versao anterior assumia um "indice" JSONL (`_index_path`, funcao
    que nunca existiu neste arquivo) — modelo de dados que este motor nunca
    usou de verdade. O real e' bem mais simples: cada item e' so' um
    `<item_id>.dxf` solto dentro da pasta do bruto (glob, ver
    `listar_recortes_bruto`), com o estado de validacao centralizado em
    `validado.json`. Devolve True se de fato havia algo pra apagar.
    """
    out_dir = _dir_recortes_bruto(obra_dir, bruto_stem)
    dxf_path = out_dir / f"{item_id}.dxf"
    existia = dxf_path.is_file()
    if existia:
        dxf_path.unlink()

    data = _ler_validacao(out_dir)
    if item_id in data:
        del data[item_id]
        _salvar_validacao(out_dir, data)

    return existia
