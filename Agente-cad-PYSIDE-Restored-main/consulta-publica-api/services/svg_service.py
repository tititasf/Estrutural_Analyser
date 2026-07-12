"""Resolução do SVG puro N1/N3 de um item (STORY-06).

Reusa `services.ficha_service.resolver_item_e_fichas` (mesmo núcleo de
resolução da STORY-05) + `ficha_reader.extrair_fotos_ficha` — o SVG em si
já vem embutido (string) na ficha HTML gerada pelo SA real, então aqui só
extraímos e validamos, nunca renderizamos nada do zero.

Anti-path-traversal (AC 6): antes de qualquer leitura, valida que o
`obra_dir` resolvido é descendente de `dados_obras_root` — `code` nunca vira
componente de caminho, e o path já vem pré-resolvido do Publisher (STORY-01),
mas a validação aqui é defesa em profundidade.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from services.ficha_service import resolver_item_e_fichas
from portal.app import ficha_reader

NIVEIS_VALIDOS = {"n1", "n3"}


def _dentro_da_raiz(obra_dir: Path, dados_obras_root: Path) -> bool:
    try:
        obra_dir.resolve().relative_to(dados_obras_root.resolve())
        return True
    except ValueError:
        return False


def obter_svg(row, nivel: str, dados_obras_root: Path) -> Optional[str]:
    """Retorna o SVG puro (string) do `nivel` pedido, ou None se: nível
    inválido, código não é item, item não existe mais na fonte, obra_dir
    foge da raiz permitida, ou o SVG daquele nível simplesmente não existe
    ainda (N3 não gerado). O router trata todos esses casos como o mesmo
    404 genérico — nunca diferencia o motivo."""
    if nivel not in NIVEIS_VALIDOS:
        return None

    resolvido = resolver_item_e_fichas(row)
    if resolvido is None:
        return None
    obra_dir, item, dir_fichas = resolvido

    if not _dentro_da_raiz(obra_dir, dados_obras_root):
        return None

    classe = row["classe"]
    fotos = ficha_reader.extrair_fotos_ficha(dir_fichas, classe, item)
    return fotos.get(nivel)


def etag_de(conteudo: str) -> str:
    """Content-hash truncado — usado como `ETag` (AC 2). Não é hash de
    segurança (não é o mesmo uso do `hash_code` do audit logger), só
    fingerprint de cache."""
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()[:16]
