"""Leitor dos recortes reais gerados por `RecorteMotor` (2026-07-06).

`executar_recortes` (pipeline_runner.py) roda o motor com `overwrite=True`, mas
o motor GRAVA um arquivo novo por rodada (nome com timestamp), não sobrescreve
de fato o mesmo nome — então o diretório acumula várias versões do mesmo item
ao longo de re-execuções. Este módulo lê o que já está em disco e escolhe
SEMPRE a versão mais recente por item (nunca inventa dado: se não achar
nenhum arquivo, devolve lista vazia).
"""

from __future__ import annotations

import re
from pathlib import Path

_PADRAO_ARQUIVO = re.compile(r"^(?P<classe>[A-Z]+)_(?P<item>.+?)_motor_(?P<ts>\d+)\.dxf$")

# mesma ordem/domínio de src/core/recorte_motor.py (via pipeline_runner._CLASSES_RECORTE)
# — [2026-07-06] sempre listadas, mesmo com 0 itens: a "pasta" da classe existe
# estruturalmente (o motor RODOU pra ela) mesmo quando nao achou nenhum
# elemento nesta obra especifica — mostrar isso deixa claro que e' honesto
# ("rodou e nao achou"), nao "esqueceram de mostrar".
CLASSES_RECORTE = ("PIL", "LV", "FV", "LAJ")


def _dir_recortes(obra_dir: Path) -> Path:
    return obra_dir / "Fase-2_Triagem" / "recortes_reversos"


def listar_classes_recorte(obra_dir: Path) -> list[dict]:
    """As 4 classes reais do RecorteMotor (sempre, mesmo com 0 itens) + a
    contagem de itens únicos de cada (última versão), pra montar as sub-abas
    (as "pastas") do viewer."""
    diretorio = _dir_recortes(obra_dir)
    por_classe: dict[str, dict[str, tuple[int, Path]]] = {c: {} for c in CLASSES_RECORTE}
    if diretorio.exists():
        for arquivo in diretorio.glob("*.dxf"):
            m = _PADRAO_ARQUIVO.match(arquivo.name)
            if not m:
                continue
            classe, item, ts = m.group("classe"), m.group("item"), int(m.group("ts"))
            atuais = por_classe.setdefault(classe, {})
            anterior = atuais.get(item)
            if anterior is None or ts > anterior[0]:
                atuais[item] = (ts, arquivo)
    return [{"classe": c, "total": len(itens)} for c, itens in por_classe.items()]


def listar_itens_recorte(obra_dir: Path, classe: str) -> list[dict]:
    """Itens (já deduplicados pra ultima versão) de 1 classe de recorte."""
    diretorio = _dir_recortes(obra_dir)
    if not diretorio.exists():
        return []
    itens: dict[str, tuple[int, Path]] = {}
    for arquivo in diretorio.glob(f"{classe}_*.dxf"):
        m = _PADRAO_ARQUIVO.match(arquivo.name)
        if not m or m.group("classe") != classe:
            continue
        item, ts = m.group("item"), int(m.group("ts"))
        anterior = itens.get(item)
        if anterior is None or ts > anterior[0]:
            itens[item] = (ts, arquivo)
    return [
        {"item_id": item, "titulo": item, "recorte_path": str(caminho)}
        for item, (_, caminho) in sorted(itens.items())
    ]


def obter_item_recorte(obra_dir: Path, classe: str, item_id: str) -> dict | None:
    for item in listar_itens_recorte(obra_dir, classe):
        if item["item_id"] == item_id:
            return item
    return None


# Sufixo que o conversor ODA/accoreconsole grava em `entrada/`
# (ex.: TMC-…-TER-R01_R2018_ASCII_ODA.dxf). Sem dedup, o mesmo pavimento
# aparece com 2 "Bruto" no drill (stem original + stem ODA) — achado 2026-07-31.
_ODA_SUFFIX = "_R2018_ASCII_ODA"


def stem_bruto_canonico(stem: str) -> str:
    """Remove o sufixo de conversão ODA para colapsar variantes do mesmo arquivo."""
    s = (stem or "").strip()
    if s.upper().endswith(_ODA_SUFFIX.upper()):
        return s[: -len(_ODA_SUFFIX)]
    return s


def _score_bruto_entrada(path: Path) -> tuple[int, int]:
    """Preferência: ODA (pipeline/recortes usam esse stem) > .dxf > .dwg."""
    stem = path.stem
    is_oda = 1 if stem.upper().endswith(_ODA_SUFFIX.upper()) else 0
    is_dxf = 1 if path.suffix.lower() == ".dxf" else 0
    return (is_oda, is_dxf)


def listar_brutos_recorte(obra_dir: Path) -> list[dict]:
    """Os DXF/DWG de entrada da obra (o "bruto" real de onde os recortes saem) —
    [2026-07-07] navegação trocada de "por classe" pra "por bruto/pavimento",
    espelhando o diagnostic_hub.py real (lista de brutos à esquerda, não abas de
    classe). Dedup por stem (dwg+dxf do mesmo arquivo contam como 1 bruto,
    preferindo o .dxf pra exibição — é o que os recortes realmente usam).

    [2026-07-31] também colapsa variantes `_R2018_ASCII_ODA` no mesmo bruto
    canônico (preferindo o ODA, pasta de recortes e SA usam esse stem)."""
    pasta = obra_dir / "entrada"
    if not pasta.exists():
        return []
    por_canon: dict[str, Path] = {}
    for arquivo in sorted(pasta.glob("*.dxf")) + sorted(pasta.glob("*.dwg")):
        canon = stem_bruto_canonico(arquivo.stem)
        atual = por_canon.get(canon)
        if atual is None or _score_bruto_entrada(arquivo) > _score_bruto_entrada(atual):
            por_canon[canon] = arquivo
    return [
        {
            "bruto_id": caminho.stem,
            "nome": caminho.name,
            "bruto_base": canon,
        }
        for canon, caminho in sorted(por_canon.items())
    ]


def listar_todos_recortes(obra_dir: Path) -> list[dict]:
    """Todos os recortes da obra, de qualquer classe, numa lista só (achatada) —
    cada item já vem com sua `classe` pra desenhar cabeçalhos de grupo na UI,
    igual ao `━━━ {classe} ━━━` do diagnostic_hub.py real, em vez de abas
    separadas por classe."""
    itens: list[dict] = []
    for classe in CLASSES_RECORTE:
        for item in listar_itens_recorte(obra_dir, classe):
            itens.append({**item, "classe": classe})
    return itens


def obter_detalhes_recorte(recorte_path: Path) -> dict:
    """Metadados reais do recorte (não é imagem — é o "detalhes e convenções"
    em campos de texto: quantidade de entidades, dimensões do bbox, camadas
    usadas). Lido direto do DXF, nunca inventado."""
    import ezdxf
    import ezdxf.bbox as ez_bbox

    doc = ezdxf.readfile(str(recorte_path))
    msp = doc.modelspace()
    entidades = list(msp)
    ext = ez_bbox.extents(msp)
    camadas = sorted({e.dxf.layer for e in entidades if e.dxf.hasattr("layer")})
    tipos = sorted({e.dxftype() for e in entidades})
    largura = round(ext.extmax.x - ext.extmin.x, 2) if ext.has_data else None
    altura = round(ext.extmax.y - ext.extmin.y, 2) if ext.has_data else None
    return {
        "arquivo": recorte_path.name,
        "entidades": len(entidades),
        "camadas": camadas,
        "tipos_entidade": tipos,
        "largura": largura,
        "altura": altura,
    }
