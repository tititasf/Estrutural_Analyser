"""Montagem da ficha pública de 1 item (STORY-05).

Reusa DIRETAMENTE `portal.app.ficha_reader` (módulo já puro — zero import de
auth/access/repository, confirmado por inspeção estática) em vez de copiar a
lógica de leitura de `estado_<pav>.json`/fichas HTML. Escape hatch aplicado
só para `encontrar_dir_fichas`: essa função vive em `portal.app.pipeline_runner`,
um módulo MUITO maior com subprocess/DB (fora do escopo de reuso seguro aqui,
mesmo não estando na blacklist literal de imports) — copiada isolada, com
teste de paridade contra o original (`test_ficha_reader_paridade.py`).

SVG nunca é embutido aqui — só a URL (`/ficha/{code}/svg/{nivel}`, STORY-06).
`tem_lv` é só checagem de existência de arquivo, nunca lê/executa o motor LV.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from portal.app import ficha_reader  # noqa: E402

from .code_lookup import code_do_pavimento

_PAVIMENTO_LABELS = {
    "TERREO": "Térreo",
    "TIPO": "Pavimento Tipo",
    "COBERTURA": "Cobertura",
    "ATICO": "Ático",
    "FUNDACAO": "Fundação",
}


def encontrar_dir_fichas(obra_dir: Path) -> Optional[Path]:
    """Cópia isolada de `portal.app.pipeline_runner.encontrar_dir_fichas`
    (escape hatch — ver docstring do módulo). Acha o diretório de fichas
    HTML mais recente gerado pelo SA real: `<obra_dir>/<pavimento>_<run_id>/`
    (timestamp por rodada), identificável pelo `arete_manifest.json` dentro.
    Runs mais recentes ordenam por último (timestamp no nome ordena
    lexicograficamente)."""
    if not obra_dir.exists():
        return None
    candidatos = sorted(
        (d for d in obra_dir.iterdir() if d.is_dir() and (d / "arete_manifest.json").is_file()),
        key=lambda d: d.name,
    )
    return candidatos[-1] if candidatos else None


def pavimento_label(pavimento: str) -> str:
    """Rótulo amigável do pavimento — nunca a string crua interna
    (`"13_PAV"`) exposta sem formatação (AC 6)."""
    pav = str(pavimento or "").strip()
    if pav in _PAVIMENTO_LABELS:
        return _PAVIMENTO_LABELS[pav]
    if pav.upper().endswith("_PAV"):
        numero = pav.upper().removesuffix("_PAV")
        if numero.isdigit():
            return f"{numero}º Pavimento"
    return pav.replace("_", " ").title() or "Pavimento"


def tem_lv(obra_dir: Path, beam_name: str) -> bool:
    """Existe contrato LV persistido pra esta viga (Fase-4)? Só checagem de
    arquivo — leitura completa é a STORY-12 (AC 5)."""
    if not beam_name:
        return False
    base = obra_dir / "Fase-4_Sincronizacao" / "JSON_Vigas_Laterais"
    for behavior_dir in ("LV-PARA", "LV-PASSA"):
        for side in ("A", "B"):
            if (base / behavior_dir / f"{beam_name}_{side}.json").is_file():
                return True
    return False


_PILARES_N3 = {"pilares_n3_para", "pilares_n3_passa"}


def payload_do_row(row) -> dict:
    """`payload_json` da linha (dict vazio se ausente/ilegível) — [2026-09-28]
    LV traz {modo, viga, segmentos}, pilar traz {modo_pilar}."""
    if "payload_json" not in row.keys() or not row["payload_json"]:
        return {}
    try:
        payload = json.loads(row["payload_json"])
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def segmento_do_row(row, seg: int) -> Optional[dict]:
    segmentos = payload_do_row(row).get("segmentos") or []
    return segmentos[seg] if 0 <= seg < len(segmentos) else None


def classe_das_fotos(classe: str) -> str:
    """As variantes N3 do pilar usam a mesma ficha HTML do pilar (N1/N3
    clássicos); as vistas por variante vêm do `views_service`."""
    return "pilares" if classe in _PILARES_N3 else classe


def resolver_item_e_fichas(
    row, *, classe: Optional[str] = None, item_id: Optional[str] = None,
) -> Optional[tuple[Path, dict, Optional[Path]]]:
    """Resolve `(obra_dir, item, dir_fichas)` a partir de uma linha de
    `public_codes` (`kind='item'`) — núcleo comum reusado por `montar_ficha`
    (STORY-05) e `svg_service.obter_svg` (STORY-06). Retorna None se
    `kind != 'item'` ou se o item não existir mais na fonte real.
    `classe`/`item_id` trocam a âncora da linha por 1 segmento do payload."""
    if row["kind"] != "item":
        return None

    obra_dir = Path(row["obra_dir"])
    pavimento = row["pavimento"]
    classe = classe or row["classe"]
    item_id = item_id or row["item_id"]

    estado = ficha_reader.ler_estado_pavimento(obra_dir, pavimento)
    if not estado:
        return None
    item = ficha_reader.obter_item_n1(estado, classe, item_id)
    if item is None:
        return None

    dir_fichas = encontrar_dir_fichas(obra_dir)
    return obra_dir, item, dir_fichas


def montar_ficha(conn: sqlite3.Connection, row) -> Optional[dict]:
    """Monta a resposta pública de `/ficha/{code}` a partir da linha
    resolvida de `public_codes` (STORY-03). Retorna None se o item não for
    encontrado na fonte real (estado_<pav>.json pode ter mudado desde a
    publicação) — o router trata isso como 404 genérico, igual código
    inexistente (nunca revela a diferença)."""
    resolvido = resolver_item_e_fichas(row)
    if resolvido is None:
        return None
    obra_dir, item, dir_fichas = resolvido
    classe = row["classe"]
    fotos = ficha_reader.extrair_fotos_ficha(dir_fichas, classe_das_fotos(classe), item)

    code = row["code"]
    beam_name = item.get("beam_name") or row["item_id"]
    payload = payload_do_row(row)

    segmentos = []
    segs_payload = payload.get("segmentos") or []
    estado = ficha_reader.ler_estado_pavimento(obra_dir, row["pavimento"]) if segs_payload else None
    for i, s in enumerate(segs_payload):
        seg_item = ficha_reader.obter_item_n1(
            estado or {}, s.get("classe", ""), s.get("item_id", ""),
        )
        seg_fotos = (ficha_reader.extrair_fotos_ficha(dir_fichas, s.get("classe", ""), seg_item)
                     if seg_item else {})
        segmentos.append({
            "indice": i,
            "titulo": f"{s.get('lado', '')}{s.get('segmento', '')}",
            "lado": s.get("lado"),
            "segmento": s.get("segmento"),
            "campos": (seg_item or {}).get("campos") or s.get("campos") or {},
            "atencao": (seg_item or {}).get("atencao") or s.get("atencao") or "",
            "svg": {
                nivel: f"/api/v1/ficha/{code}/svg/{nivel}?seg={i}" if seg_fotos.get(nivel) else None
                for nivel in ("n1", "n3")
            },
        })

    return {
        "code": code,
        "tipo": row["tipo_elemento"],
        "titulo": row["titulo_publico"] or item["titulo"],
        "obra_rotulo": row["obra_rotulo"],
        "pavimento_label": pavimento_label(row["pavimento"]),
        "pavimento_code": code_do_pavimento(conn, row["obra_id"], row["pavimento"]),
        "campos": item["campos"],
        "atencao": item["atencao"],
        "svg": {
            "n1": f"/api/v1/ficha/{code}/svg/n1" if fotos.get("n1") else None,
            "n3": f"/api/v1/ficha/{code}/svg/n3" if fotos.get("n3") else None,
        },
        "tem_lv": tem_lv(obra_dir, beam_name),
        "modo": payload.get("modo") or payload.get("modo_pilar"),
        "segmentos": segmentos,
    }
