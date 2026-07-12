"""Auto-publicação de obras para a App de Consulta Pública.

[2026-07-12] Pedido explícito do dono: abandona o modelo de "publicação
deliberada" (STORY-01/admin_publish_routes.py, ainda disponível para
publicar/revogar manualmente) em favor de sincronização automática e
periódica — toda obra com `estado='pronta'` no portal é publicada/
republicada em `public_consulta.db` sem ação manual, e correções feitas na
web (que mudam `titulo_publico`/`tipo_elemento`/pavimentos/itens) chegam à
App de Consulta dentro de, no máximo, 1 ciclo (`auto_publish_interval_s`,
default 60s). Conteúdo detalhado (campos/atenção/SVG) já era lido AO VIVO
pela API pública a cada request (STORY-05/06) — não precisa de republicação
para isso, só a projeção denormalizada (`public_codes`) precisa.

Reaproveita `publisher.publish.publicar()` (o MESMO código que o endpoint
manual `/admin/publicar/{obra_id}` já usa) — `publicar()` é seguro de
rodar repetidamente: preserva `code` de itens já publicados, atualiza
título/tipo se mudaram, e revoga qualquer item que tenha desaparecido da
obra (comportamento de upsert, não de append).

Espelha o padrão assíncrono de `drive_poller.py::poller_loop` (task de
fundo no lifespan do FastAPI, com backoff em falha persistente, conexão
aberta/fechada dentro da própria thread do executor para nunca cruzar
fronteira de thread com sqlite3).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from ..db import connection as db_conn
from ..db import repository as repo
from .config import Settings

log = logging.getLogger("portal.auto_publish_poller")

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_CONSULTA_PUBLICA_DIR = _REPO_ROOT / "consulta-publica-api"
if str(_CONSULTA_PUBLICA_DIR) not in sys.path:
    sys.path.insert(0, str(_CONSULTA_PUBLICA_DIR))

from publisher.publish import publicar  # noqa: E402

# Só obras "prontas" são candidatas — 'aguardando_ingestao'/'processando'
# ainda não têm dado estável pra publicar; 'erro' não deve virar público.
_ESTADOS_PUBLICAVEIS = {"pronta"}


def _obra_dir(obra: dict, settings: Settings) -> Path:
    """Mesma lógica de `admin_publish_routes.py::_obra_dir` — `local_path`
    da obra se existir, senão `dados_obras_dir/<nome>`."""
    lp = obra.get("local_path")
    return Path(lp) if lp else settings.dados_obras_dir / obra.get("nome", "obra")


def _ciclo(settings: Settings) -> dict:
    """1 ciclo síncrono — roda dentro de `asyncio.to_thread`, abre e fecha a
    PRÓPRIA conexão sqlite3 na mesma thread (nunca cruza fronteira)."""
    conn = db_conn.get_connection(settings.db_path)
    resultado = {"publicadas": 0, "erros": 0, "ignoradas": 0}
    try:
        obras = repo.listar_todas_obras(conn)
        for obra in obras:
            if obra.get("estado") not in _ESTADOS_PUBLICAVEIS:
                resultado["ignoradas"] += 1
                continue
            obra_dir = _obra_dir(obra, settings)
            if not obra_dir.exists():
                resultado["ignoradas"] += 1
                continue
            try:
                # obra_rotulo = nome real (não o default anonimizado do
                # Publisher) — pedido explícito do dono: consulta pública e
                # portal devem mostrar os MESMOS dados, sem gatekeeping.
                # db_path SEMPRE explícito (nunca None) — settings controla
                # o alvo real; testes sobrescrevem para um tmp, nunca o
                # public_consulta.db de produção.
                publicar(
                    obra, obra_dir,
                    db_path=settings.public_consulta_db_path,
                    obra_rotulo=obra.get("nome"),
                )
                resultado["publicadas"] += 1
            except Exception:
                resultado["erros"] += 1
                log.exception("auto_publish: falha ao publicar obra %s", obra.get("id"))
    finally:
        conn.close()
    return resultado


async def auto_publish_loop(app_state) -> None:
    """Task de fundo: sincroniza a cada `auto_publish_interval_s`, com
    backoff em falha persistente. Roda até cancelamento (shutdown do
    lifespan) — mesmo contrato de `drive_poller.poller_loop`."""
    settings: Settings = app_state.settings
    intervalo = settings.auto_publish_interval_s
    backoff = intervalo
    while True:
        try:
            resultado = await asyncio.to_thread(_ciclo, settings)
            if resultado["publicadas"]:
                log.info(
                    "auto_publish: %d obra(s) sincronizada(s), %d erro(s), %d ignorada(s)",
                    resultado["publicadas"], resultado["erros"], resultado["ignoradas"],
                )
            backoff = intervalo  # sucesso reseta o backoff
            await asyncio.sleep(intervalo)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - nunca derruba o Uvicorn
            log.warning("auto_publish_loop degradado: %s (backoff %ds)", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 1800)  # teto 30min
