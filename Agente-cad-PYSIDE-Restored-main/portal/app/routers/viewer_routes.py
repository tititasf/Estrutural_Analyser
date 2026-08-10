"""Viewer do ESTRUTURAL LIMPO por pavimento (P2 do MASTERPLAN-CONSOLIDACAO-ENTREGA).

Serve o que o operador precisa para desenhar sobre o estrutural:

  1. a torre LIMPA do pavimento (`torre_1.dxf`), não o DXF bruto — o bruto ainda
     traz a faixa de detalhes/convenções ao lado da planta;
  2. a TRANSFORM exata da imagem (pixel <-> coordenada DXF), vinda do próprio
     render, para o clique do usuário virar coordenada real;
  3. os itens já interpretados pelo SA, por classe, com geometria — base dos
     botões "ver pilares / lajes / laterais / fundos".

Só LÊ. Nenhuma escrita, nenhuma tabela nova. A criação de item (P3) virá em rota
própria e usará a transform daqui.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import access, auth, dxf_preview, ficha_reader, pipeline_runner, torre_crop
from ..dbdep import get_db_conn
from ...db import repository as repo
from src.core import item_manual
from src.core.obra_identity import (
    normalizar_pavimento,
    pavimento_de_codigo_prancha,
)

router = APIRouter(prefix="/obras", tags=["viewer"])

log = logging.getLogger("portal.viewer_routes")

# Botões de destaque no estrutural limpo (pedido 2026-07-31):
#  - Pilares: retangulares + especiais juntos (um botão)
#  - Laterais: **4 botões isolados** A/B × Para/Passa — mesmo que a geometria
#    "para" e "passa" coincida no 13_PAV, o dono precisa ligar/desligar cada
#    tratamento sozinho pra validar a interpretação
#  - Fundos e lajes
GRUPOS_VIEWER: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("pilares", "Pilares", ("pilares", "pilares_especiais")),
    ("lat_a_para", "Lat. A · Para", ("lateral_a_para",)),
    ("lat_a_passa", "Lat. A · Passa", ("lateral_a_passa",)),
    ("lat_b_para", "Lat. B · Para", ("lateral_b_para",)),
    ("lat_b_passa", "Lat. B · Passa", ("lateral_b_passa",)),
    ("fundos", "Fundos de viga", ("fundo",)),
    ("lajes", "Lajes", ("lajes",)),
)

# Recorte de torre = estrutural limpo. "detalhes" é a faixa de convenções, que
# NÃO serve de fundo para desenhar (não tem a planta).
_PREFIXO_TORRE = "torre"

# Botão do viewer -> classe canônica gravada em reverse_eng_fichas/recortes.
# [2026-07-31] GRUPOS_VIEWER passou a separar laterais em 4 botões de destaque
# (A/Para, A/Passa, B/Para, B/Passa) — os 4 gravam a MESMA classe "LV": o item
# nasce como geometria crua, e separar em lado A/B/para/passa é trabalho do
# motor headless (P4), não da criação manual. Construído a partir de
# GRUPOS_VIEWER (não duplicado à mão) para as duas constantes nunca divergirem
# de novo — foi exatamente essa divergência que quebrou esta rota quando o
# grupo "laterais" virou 4 grupos "lat_*" sem atualizar este dicionário.
_GRUPO_PARA_CLASSE = {"pilares": "PIL", "fundos": "FV", "lajes": "LAJ"}
_GRUPO_PARA_CLASSE.update(
    {grupo: "LV" for grupo, _rotulo, _classes in GRUPOS_VIEWER if grupo.startswith("lat_")}
)

# Mapeamento da classe SA (PIL, LAJ, FV, LV) para o argumento --secao do motor headless.
_CLASSE_PARA_SECAO = {
    "PIL": "pilares",
    "FV": "fundos_viga",
    "LAJ": "lajes",
    "LV": "laterais_viga",
}


class _PontoPx(BaseModel):
    x: float
    y: float


class CriarItemPayload(BaseModel):
    grupo: str
    poligono_px: list[_PontoPx]
    elemento_id: Optional[str] = None


def _obra_do_membro(conn: sqlite3.Connection, obra_id: str, membro: dict) -> dict:
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    return obra


def _obra_dir(request: Request, obra: dict) -> Path:
    settings = request.app.state.settings
    lp = obra.get("local_path")
    return Path(lp) if lp else settings.dados_obras_dir / obra.get("nome", "obra")


def _brutos_com_recorte(obra_dir: Path) -> list[str]:
    """Brutos que REALMENTE têm pasta de recorte em disco.

    Descoberta, não derivação. Derivar o bruto_id do nome da obra falha em obra
    real: `portal_obras.arquivo_nome` é NULL nas duas obras cadastradas, e o
    fallback pelo nome só acerta quando obra e arquivo se chamam igual — em
    Obra-Teste-Inicial2 os brutos são TMC-EST-EX-0000-LOC-R03 e outros, nada a
    ver com o nome da obra. Uma obra pode ter vários brutos.
    """
    raiz = obra_dir / "Fase-2_Triagem" / "recortes"
    if not raiz.is_dir():
        return []
    return sorted(p.name for p in raiz.iterdir() if p.is_dir())


def _primeira_torre(obra_dir: Path, bruto_id: str) -> Optional[dict]:
    for item in torre_crop.listar_recortes_bruto(obra_dir, bruto_id):
        if str(item.get("item_id", "")).startswith(_PREFIXO_TORRE):
            return {"bruto_id": bruto_id, **item}
    return None


def encontrar_estrutural_limpo(
    obra_dir: Path, obra: dict, pavimento: Optional[str] = None
) -> Optional[dict]:
    """Torre limpa DO PAVIMENTO pedido.

    Cada pavimento tem seu próprio bruto: Obra-Teste-Inicial2 tem 20, um por
    prancha (`...-6000-13P`, `...-7000-14P`, `...-8000-COB`). Sem casar pelo
    pavimento, qualquer pavimento selecionado mostrava SEMPRE o mesmo desenho —
    o bug que o dono viu ("só funciona no link que você passou").

    Com `pavimento`, só devolve torre cujo bruto corresponda àquele pavimento.
    Não achou? None, e o viewer responde 409. Cair num bruto qualquer mostraria
    o pavimento ERRADO com cara de certo, que é pior do que não mostrar nada.

    Sem `pavimento` (compatibilidade), mantém o comportamento antigo: prefere o
    bruto sugerido pelo nome da obra, senão o primeiro em ordem alfabética.
    """
    disponiveis = _brutos_com_recorte(obra_dir)
    if not disponiveis:
        return None

    if pavimento:
        alvo = normalizar_pavimento(pavimento)
        for bruto_id in disponiveis:
            if alvo and pavimento_de_codigo_prancha(bruto_id) == alvo:
                torre = _primeira_torre(obra_dir, bruto_id)
                if torre:
                    return torre
        return None

    sugerido = Path(obra.get("arquivo_nome") or "").stem or str(obra.get("nome") or "")
    ordem = ([sugerido] if sugerido in disponiveis else []) + [
        b for b in disponiveis if b != sugerido
    ]
    for bruto_id in ordem:
        torre = _primeira_torre(obra_dir, bruto_id)
        if torre:
            return torre
    return None


def _rotulo(item: dict) -> str:
    """Texto a desenhar junto da linha/área.

    Pilar e laje usam o próprio nome (P1, L301). Segmento de viga usa
    "<viga> SEG <n>" — o dono pediu a contagem do segmento explícita nos fundos
    (SEG 1, SEG 2, SEG 3), e "V2 (segmento 1)" é longo demais para caber sobre
    o desenho.
    """
    campos = item.get("campos") or {}
    viga = item.get("beam_name")
    segmento = str(campos.get("Segmento") or "").strip()
    if viga and segmento:
        return f"{viga} SEG {segmento}"
    return str(item.get("titulo") or item.get("item_id") or "")


def _geometria_dos_itens(estado: dict, classe: str, transform) -> list[dict]:
    """Itens de uma classe com geometria em DXF e em pixel da imagem servida.

    Manda os dois: DXF é a verdade (e o que o motor consome), pixel é o que o
    front desenha sem precisar reimplementar a transform — reimplementá-la no
    cliente é justamente como o recorte manual ficou acoplado no passado.
    """
    saida: list[dict] = []
    for item in ficha_reader.listar_itens_n1(estado, classe):
        pontos = item.get("points") or []
        if not pontos:
            continue
        try:
            dxf = [(float(p[0]), float(p[1])) for p in pontos]
        except (TypeError, ValueError, IndexError):
            log.warning("pontos ilegiveis em %s/%s", classe, item.get("item_id"))
            continue
        xs = [p[0] for p in dxf]
        ys = [p[1] for p in dxf]
        campos = item.get("campos") or {}
        pontos_px = [transform.dxf_para_px(x, y) for x, y in dxf]
        # Item cuja geometria cai FORA da prancha renderizada. Medido no 13_PAV:
        # 8 segmentos (V2 SEG 2, V302 SEG 2/3/4, V329 SEG 2...) com Y entre 4175
        # e 5320 num desenho que termina em Y=3796. Não é erro de transform (o X
        # bate) — é geometria do SA fora do papel. O viewer SINALIZA em vez de
        # recortar em silêncio: item invisível parece item inexistente, e é assim
        # que erro de interpretação passa despercebido.
        fora = any(
            not (-2 <= px <= transform.largura_px + 2
                 and -2 <= py <= transform.altura_px + 2)
            for px, py in pontos_px
        )
        saida.append({
            "item_id": item.get("item_id"),
            "classe_sa": classe,
            "rotulo": _rotulo(item),
            "beam_name": item.get("beam_name"),
            "segmento": campos.get("Segmento"),
            "lado": campos.get("Lado"),
            "bbox_dxf": [min(xs), min(ys), max(xs), max(ys)],
            "pontos_dxf": dxf,
            "pontos_px": pontos_px,
            "fora_do_frame": fora,
        })
    return saida


@router.get("/{obra_id}/viewer/{pavimento}")
def viewer_pavimento_endpoint(
    obra_id: str, pavimento: str, request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Estrutural limpo do pavimento + transform + itens por classe."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)

    fonte = encontrar_estrutural_limpo(obra_dir, obra, pavimento)
    if fonte is None:
        raise HTTPException(
            status_code=409,
            detail="estrutural limpo ainda nao gerado — rode Triagem + Recortes",
        )

    caminho = Path(fonte["path"])
    if not caminho.is_file():
        raise HTTPException(status_code=410, detail="DXF do estrutural limpo sumiu do disco")

    try:
        transform = dxf_preview.transform_preview_completo(
            caminho, cache_dir=obra_dir / ".previews"
        )
    except Exception as exc:  # noqa: BLE001 - DXF pode ter geometria nao suportada
        log.exception("falha ao renderizar estrutural limpo: %s", caminho)
        raise HTTPException(status_code=502, detail=f"falha ao renderizar: {exc}") from exc
    if transform is None:
        raise HTTPException(status_code=502, detail="estrutural limpo sem extents legiveis")

    estado = ficha_reader.ler_estado_pavimento(obra_dir, pavimento)
    grupos: list[dict] = []
    if estado is not None:
        for grupo, rotulo, classes_sa in GRUPOS_VIEWER:
            itens: list[dict] = []
            for classe in classes_sa:
                itens.extend(_geometria_dos_itens(estado, classe, transform))
            if itens:
                grupos.append({
                    "grupo": grupo, "rotulo": rotulo, "total": len(itens),
                    "fora_do_frame": sum(1 for i in itens if i["fora_do_frame"]),
                    "itens": itens,
                })

    return {
        "obra_id": obra_id,
        "pavimento": pavimento,
        "sa_rodado": estado is not None,
        "fonte": {
            "bruto_id": fonte["bruto_id"],
            "item_id": fonte["item_id"],
            "arquivo": caminho.name,
        },
        "svg_url": (
            f"/obras/{obra_id}/recortes/brutos/{fonte['bruto_id']}"
            f"/{fonte['item_id']}/foto"
        ),
        "transform": transform.como_dict(),
        "grupos": grupos,
    }


@router.get("/{obra_id}/viewer/{pavimento}/transform")
def transform_pavimento_endpoint(
    obra_id: str, pavimento: str, request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Só a transform — para o front converter clique sem baixar os itens todos."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    fonte = encontrar_estrutural_limpo(obra_dir, obra, pavimento)
    if fonte is None:
        raise HTTPException(status_code=409, detail="estrutural limpo ainda nao gerado")
    transform = dxf_preview.transform_preview_completo(
        Path(fonte["path"]), cache_dir=obra_dir / ".previews"
    )
    if transform is None:
        raise HTTPException(status_code=502, detail="estrutural limpo sem extents legiveis")
    return {"obra_id": obra_id, "pavimento": pavimento, **transform.como_dict()}


@router.get("/{obra_id}/viewer/{pavimento}/sugerir-nome")
def sugerir_nome_endpoint(
    obra_id: str, pavimento: str, grupo: str, request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Próximo nome livre da classe (P36 se já existem P1..P35) — preenche o
    campo de nome do laço de desenho sem o operador ter de conferir na mão."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    classe = _GRUPO_PARA_CLASSE.get(grupo)
    if classe is None:
        raise HTTPException(status_code=422, detail=f"grupo desconhecido: {grupo}")

    settings = request.app.state.settings
    sa_conn = sqlite3.connect(str(settings.sa_db_path))
    try:
        sugestao = item_manual.sugerir_proximo_nome(
            sa_conn, obra_dir.name, pavimento, classe
        )
    finally:
        sa_conn.close()
    return {"grupo": grupo, "classe": classe, "sugestao": sugestao}


@router.post("/{obra_id}/viewer/{pavimento}/itens", status_code=201)
def criar_item_endpoint(
    obra_id: str, pavimento: str, payload: CriarItemPayload, request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Laço desenhado no viewer -> recorte real + ficha manual (P3) + microciclo SA (P4).

    Escopo desta rota: recortar a geometria dentro do traço, persistir
    ficha+recorte com status='manual' e, na sequência, disparar o motor
    headless da classe sobre esse item (--item) em modo --wait com lock,
    refletindo a interpretação N1 gerada no JSON de resposta.
    """
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)

    classe = _GRUPO_PARA_CLASSE.get(payload.grupo)
    if classe is None:
        raise HTTPException(status_code=422, detail=f"grupo desconhecido: {payload.grupo}")
    if len(payload.poligono_px) < 3:
        raise HTTPException(status_code=422, detail="o traço precisa de pelo menos 3 pontos")

    fonte = encontrar_estrutural_limpo(obra_dir, obra, pavimento)
    if fonte is None:
        raise HTTPException(status_code=409, detail="estrutural limpo ainda nao gerado")
    caminho = Path(fonte["path"])
    if not caminho.is_file():
        raise HTTPException(status_code=410, detail="DXF do estrutural limpo sumiu do disco")

    transform = dxf_preview.transform_preview_completo(
        caminho, cache_dir=obra_dir / ".previews"
    )
    if transform is None:
        raise HTTPException(status_code=502, detail="estrutural limpo sem extents legiveis")

    # px (tela) -> DXF (mesma transform que serve o desenho): o traço do
    # operador vira coordenada real, não estimativa.
    poligono_dxf = [transform.px_para_dxf(p.x, p.y) for p in payload.poligono_px]

    settings = request.app.state.settings
    sa_conn = sqlite3.connect(str(settings.sa_db_path))
    sa_conn.row_factory = sqlite3.Row
    out_path: Optional[Path] = None
    try:
        obra_name = obra_dir.name  # pasta em disco, não obra["nome"] do portal —
        # os dois já divergiram em obra real (Obra-Teste-Inicial2 / Obra-Teste-Inicial).
        elemento_id = item_manual.normalizar_nome_item(
            payload.elemento_id
            or item_manual.sugerir_proximo_nome(sa_conn, obra_name, pavimento, classe)
        )

        pav_norm = normalizar_pavimento(pavimento) or pavimento
        out_dir = obra_dir / "Fase-2_Triagem" / "recortes_web" / pav_norm
        out_path = out_dir / f"{classe}_{elemento_id}.dxf"

        from scripts.obra_crop_engine import crop_dxf_by_polygon
        resultado = crop_dxf_by_polygon(caminho, out_path, poligono_dxf)
        if resultado.get("error"):
            raise HTTPException(status_code=500, detail=f"falha ao recortar: {resultado['error']}")
        if resultado["entities_copied"] == 0:
            out_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=422,
                detail="nenhuma entidade do estrutural caiu dentro do traço desenhado",
            )

        try:
            ident = item_manual.criar_item_manual(
                sa_conn, obra_name=obra_name, pavimento=pavimento, classe=classe,
                elemento_id=elemento_id, recorte_path=str(out_path),
                bbox=tuple(resultado["bbox"]), entity_count=resultado["entities_copied"],
            )
        except item_manual.ItemDuplicado as exc:
            out_path.unlink(missing_ok=True)
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception:
            out_path.unlink(missing_ok=True)
            raise
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - falha de criacao vira erro de request
        log.exception("criar_item_endpoint falhou: obra=%s pav=%s", obra_id, pavimento)
        if out_path is not None:
            out_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"falha ao criar item: {exc}") from exc
    finally:
        sa_conn.close()

    # P5 — materializa preview N3 no path que assemble_n5 varre. Sem isso o
    # item some da prancha sem erro (G-3). Cópia do recorte até o robô N3 real
    # sobrescrever com a fôrma gerada.
    n3_path: Optional[str] = None
    try:
        n3 = item_manual.materializar_preview_n3(
            obra_dir,
            classe=ident.classe,
            elemento_id=ident.elemento_id,
            recorte_path=out_path,
        )
        n3_path = str(n3)
    except Exception as exc:  # noqa: BLE001 - preview é best-effort; item já no DB
        log.warning(
            "P5 materializar_preview_n3 falhou para %s/%s: %s",
            ident.classe, ident.elemento_id, exc,
        )

    # P4 — microciclo headless da classe sobre o item (--secao + --item +
    # --persist-db + --wait), ENFILEIRADO no JobWorker existente (mesma fila
    # de triagem/SA/N5 — jobs.py, GET /jobs/{id}) em vez de rodado aqui dentro
    # do handler HTTP. subprocess_timeout_s default é 3600s: rodar de forma
    # síncrona travaria a aba do operador por até 1h sem feedback nenhum, e
    # quebraria o padrão que o resto do portal já usa (job na_fila -> polling).
    # `job_id` fica None quando headless_enabled=False (default nos testes,
    # ver conftest.py) — mesma semântica que o antigo `dry_run`.
    settings = request.app.state.settings
    secao = _CLASSE_PARA_SECAO.get(ident.classe, "pilares")
    comando_sa = pipeline_runner.montar_comando_headless(
        settings, obra, secao=[secao], pav=pavimento, item=[ident.elemento_id],
    )  # so' para exibir/depurar na tela — a EXECUCAO e' do job, nao daqui.
    job_id: Optional[str] = None
    if getattr(settings, "headless_enabled", True):
        ev = pipeline_runner.engine_version(settings.repo_root)
        job_id = repo.enfileirar_job(conn, obra_id=obra_id, engine_version=ev)
        request.app.state.job_meta[job_id] = {
            "etapa": "sa_item", "secao": secao, "item": ident.elemento_id, "pav": pavimento,
        }

    # Reflete N1 na lista do pavimento SE já houver interpretação prévia no
    # estado_*.json (best-effort: o job de cima ainda não rodou nesse ponto —
    # o front descobre a interpretação de verdade fazendo polling de
    # GET /jobs/{job_id} e, ao concluir, refazendo GET .../viewer/{pav}).
    item_interpretado = None
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pavimento)
    if estado is not None:
        classes_sa = next(
            (cls_tup for grp, _, cls_tup in GRUPOS_VIEWER if grp == payload.grupo),
            (ident.classe.lower(),),
        )
        for c in classes_sa:
            for it in _geometria_dos_itens(estado, c, transform):
                if (it.get("item_id") or "").strip().upper() == ident.elemento_id.upper():
                    item_interpretado = it
                    break
            if item_interpretado is not None:
                break

    return {
        "obra_id": obra_id,
        "pavimento": ident.pavimento,
        "classe": ident.classe,
        "elemento_id": ident.elemento_id,
        "entities_copied": resultado["entities_copied"],
        "recorte_path": str(out_path),
        "n3_preview_path": n3_path,
        "job_id": job_id,
        "comando_sa": comando_sa,
        "item_interpretado": item_interpretado,
    }
