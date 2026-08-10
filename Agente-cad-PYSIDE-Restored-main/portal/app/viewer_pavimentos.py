"""Quais pavimentos da obra têm estrutural limpo para abrir no viewer.

Fica fora do router porque duas telas precisam: o seletor do próprio viewer e o
link na página de detalhe da obra. Duplicar a varredura nas duas levaria a listas
divergentes — uma oferecendo pavimento que a outra não abre.

Só LÊ o disco.
"""

from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from src.core.obra_identity import pavimento_de_codigo_prancha  # noqa: E402

from . import ficha_reader, torre_crop  # noqa: E402


def listar_pavimentos_com_torre(obra_dir: Path, obra: dict) -> list[dict]:
    """Pavimentos com torre limpa gerada, na ordem natural de leitura.

    Marca `tem_sa` quando existe `estado_<pav>.json`: sem SA o viewer abre o
    desenho mas não tem item nenhum para destacar, e é honesto avisar antes do
    clique em vez de mostrar uma tela vazia sem explicação.
    """
    raiz = obra_dir / "Fase-2_Triagem" / "recortes"
    if not raiz.is_dir():
        return []

    com_sa = set(ficha_reader.descobrir_pavimentos(obra_dir))
    achados: dict[str, str] = {}
    for pasta in sorted(p for p in raiz.iterdir() if p.is_dir()):
        pavimento = pavimento_de_codigo_prancha(pasta.name)
        if not pavimento or pavimento in achados:
            continue
        tem_torre = any(
            str(item.get("item_id", "")).startswith("torre")
            for item in torre_crop.listar_recortes_bruto(obra_dir, pasta.name)
        )
        if tem_torre:
            achados[pavimento] = pasta.name

    return [
        {"pavimento": pav, "bruto_id": bruto, "tem_sa": pav in com_sa}
        for pav, bruto in sorted(achados.items(), key=lambda kv: _ordem(kv[0]))
    ]


def _ordem(pavimento: str) -> tuple[int, float, str]:
    """Ordem de leitura: subsolo, fundação, térreo, 1..N, tipo, cobertura, ático.

    Ordenar alfabeticamente poria "COBERTURA" antes de "1_PAV" e "13_PAV" antes
    de "2_PAV" — lista de prédio que não sobe na ordem do prédio confunde.
    """
    fixos = {
        "LOCACAO": (0, 0.0, ""), "FUNDACAO": (1, 0.0, ""),
        "TERREO": (3, 0.0, ""), "TIPO": (5, 0.0, ""),
        "COBERTURA": (6, 0.0, ""), "ATICO": (7, 0.0, ""),
    }
    if pavimento in fixos:
        return fixos[pavimento]
    if pavimento.endswith("_SUBSOLO"):
        return (2, -float(pavimento.split("_")[0] or 0), "")
    if pavimento.endswith("_PAV"):
        try:
            return (4, float(pavimento.split("_")[0]), "")
        except ValueError:
            pass
    return (8, 0.0, pavimento)
