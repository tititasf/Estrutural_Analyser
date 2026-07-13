"""Publisher — projeta uma obra do portal interno para `public_consulta.db`
mintando códigos opacos por item (STORY-01).

Reaproveita `descobrir_pavimentos`/`listar_itens_n1`/`CLASSES_N1` do portal
existente (`portal/app/ficha_reader.py`) — mesma fonte de dados usada pela
STORY-05. Zero acoplamento com `src/core/lv_generation_contract.py` ou
qualquer coisa do motor desktop/PySide6.
"""

from __future__ import annotations

import secrets
import sqlite3
import string
import sys
import uuid
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from portal.app import ficha_reader  # noqa: E402

from .db import get_connection, assert_no_blacklisted_columns  # noqa: E402

_BASE62_ALPHABET = string.digits + string.ascii_uppercase + string.ascii_lowercase
_CODE_LEN = 10
_MAX_RETRIES = 5

# classe (ficha_reader.CLASSES_N1) -> tipo_elemento publico. Classes de
# convencao/meta (convencao_pilares, convencao_niveis_lajes, cortes) e as
# variantes N3 de pilar (pilares_n3_para/passa, reprojecao dos mesmos
# pilares) NAO sao publicadas como item proprio.
_CLASSE_PARA_TIPO_ELEMENTO = {
    "pilares": "pilar",
    "pilares_especiais": "pilar",
    "lajes": "laje",
    "fundo": "viga_fundo",
    "lateral_a_para": "viga_lateral",
    "lateral_b_para": "viga_lateral",
    "lateral_a_passa": "viga_lateral",
    "lateral_b_passa": "viga_lateral",
}


def gerar_code(conn: sqlite3.Connection) -> str:
    """Gera um código opaco base62(10) unico via CSPRNG, com retry em
    colisão (AC 1, AC 7). Nunca deriva/hash de obra_id+item — tabela é a
    unica fonte de verdade (architecture.md §3.1)."""
    for _ in range(_MAX_RETRIES):
        raw = secrets.token_bytes(_CODE_LEN)
        code = "".join(_BASE62_ALPHABET[b % 62] for b in raw)[:_CODE_LEN]
        exists = conn.execute(
            "SELECT 1 FROM public_codes WHERE code = ?", (code,)
        ).fetchone()
        if not exists:
            return code
    raise RuntimeError(
        f"Não foi possível gerar código único após {_MAX_RETRIES} tentativas."
    )


def _obra_rotulo_default() -> str:
    sufixo = "".join(secrets.choice(_BASE62_ALPHABET) for _ in range(4))
    return f"Obra ·· {sufixo}"


def _upsert_obra(
    conn: sqlite3.Connection, obra_id: str, obra_dir: Path, rotulo: str, batch: str,
) -> str:
    """Upsert do registro `kind='obra'` — code preservado se já existir.
    Extraído de `publicar()` [2026-07-13] pra reuso por
    `publicar_pavimento_minimo` (mint antes do SA rodar, na Triagem)."""
    row = conn.execute(
        "SELECT code FROM public_codes WHERE obra_id = ? AND kind = 'obra'",
        (obra_id,),
    ).fetchone()
    code = row["code"] if row else gerar_code(conn)
    conn.execute(
        """
        INSERT INTO public_codes
            (code, kind, obra_id, obra_dir, obra_rotulo, publish_batch)
        VALUES (?, 'obra', ?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            obra_dir=excluded.obra_dir,
            obra_rotulo=excluded.obra_rotulo,
            publish_batch=excluded.publish_batch,
            revoked=0
        """,
        (code, obra_id, str(obra_dir), rotulo, batch),
    )
    return code


def _upsert_pavimento(
    conn: sqlite3.Connection, obra_id: str, obra_dir: Path, pavimento: str, rotulo: str, batch: str,
) -> str:
    """Upsert do registro `kind='pavimento'` — code preservado se já existir.
    Extraído de `publicar()` [2026-07-13], mesmo motivo de `_upsert_obra`."""
    row = conn.execute(
        "SELECT code FROM public_codes WHERE obra_id = ? AND pavimento = ? AND kind = 'pavimento'",
        (obra_id, pavimento),
    ).fetchone()
    code = row["code"] if row else gerar_code(conn)
    conn.execute(
        """
        INSERT INTO public_codes
            (code, kind, obra_id, obra_dir, pavimento, obra_rotulo, publish_batch)
        VALUES (?, 'pavimento', ?, ?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            obra_dir=excluded.obra_dir,
            pavimento=excluded.pavimento,
            obra_rotulo=excluded.obra_rotulo,
            publish_batch=excluded.publish_batch,
            revoked=0
        """,
        (code, obra_id, str(obra_dir), pavimento, rotulo, batch),
    )
    return code


def publicar_pavimento_minimo(
    obra_id: str,
    obra_dir: Path,
    pavimento: str,
    obra_rotulo: Optional[str] = None,
    *,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[Path] = None,
) -> dict:
    """Mint mínimo — só obra + 1 pavimento, SEM depender de
    `estado_<pavimento>.json` (SA) existir [2026-07-13, pedido do dono]:
    "o código de pavimento continua 'ainda não publicado' mesmo depois de
    validar [um recorte], porque só minta quando a obra inteira chega em
    'pronta'". Chamado no momento em que o dono valida um recorte na
    Triagem/Recortes — bem antes do SA rodar. Preserva code de chamadas
    anteriores (mesmo upsert de `publicar()`), nunca gera um novo
    `publish_batch` (não revoga nada — só adiciona/atualiza)."""
    obra_id = str(obra_id)
    fechar_no_final = conn is None
    if conn is None:
        conn = get_connection(db_path) if db_path else get_connection()
    assert_no_blacklisted_columns(conn)
    try:
        rotulo = obra_rotulo or _obra_rotulo_default()
        batch = str(uuid.uuid4())
        with conn:
            code_obra = _upsert_obra(conn, obra_id, obra_dir, rotulo, batch)
            code_pavimento = _upsert_pavimento(conn, obra_id, obra_dir, pavimento, rotulo, batch)
        return {"code_obra": code_obra, "code_pavimento": code_pavimento}
    finally:
        if fechar_no_final:
            conn.close()


def publicar_recorte(
    obra_id: str,
    obra_dir: Path,
    pavimento: str,
    recorte_tipo: str,
    bruto_id: str,
    titulo: str,
    obra_rotulo: Optional[str] = None,
    *,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[Path] = None,
) -> str:
    """Mint de 1 código PRÓPRIO de recorte (Torre 1/Detalhes/etc, ainda sem
    SA rodado) [2026-07-13] — kind='recorte', identidade
    (obra_id, pavimento, classe=recorte_tipo, item_id=bruto_id). Reusa
    `_upsert_obra`/`_upsert_pavimento` pra garantir que obra/pavimento
    também existam. Só existe no Portal por enquanto — a Consulta Pública
    não expõe/renderiza recorte (ela só lê SVG já pronto do SA)."""
    obra_id = str(obra_id)
    fechar_no_final = conn is None
    if conn is None:
        conn = get_connection(db_path) if db_path else get_connection()
    assert_no_blacklisted_columns(conn)
    try:
        rotulo = obra_rotulo or _obra_rotulo_default()
        batch = str(uuid.uuid4())
        with conn:
            _upsert_obra(conn, obra_id, obra_dir, rotulo, batch)
            _upsert_pavimento(conn, obra_id, obra_dir, pavimento, rotulo, batch)

            existente = conn.execute(
                """
                SELECT code FROM public_codes
                WHERE obra_id = ? AND pavimento = ? AND classe = ? AND item_id = ?
                      AND kind = 'recorte'
                """,
                (obra_id, pavimento, recorte_tipo, bruto_id),
            ).fetchone()
            code = existente["code"] if existente else gerar_code(conn)
            conn.execute(
                """
                INSERT INTO public_codes
                    (code, kind, obra_id, obra_dir, pavimento, classe,
                     item_id, titulo_publico, obra_rotulo, publish_batch)
                VALUES (?, 'recorte', ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    obra_dir=excluded.obra_dir,
                    pavimento=excluded.pavimento,
                    classe=excluded.classe,
                    item_id=excluded.item_id,
                    titulo_publico=excluded.titulo_publico,
                    obra_rotulo=excluded.obra_rotulo,
                    publish_batch=excluded.publish_batch,
                    revoked=0
                """,
                (code, obra_id, str(obra_dir), pavimento, recorte_tipo, bruto_id, titulo, rotulo, batch),
            )
        return code
    finally:
        if fechar_no_final:
            conn.close()


def publicar(
    obra: dict,
    obra_dir: Path,
    *,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[Path] = None,
    obra_rotulo: Optional[str] = None,
) -> dict:
    """Publica (ou republica) uma obra em `public_consulta.db`.

    `obra`: dict do portal (ex.: `repo.obter_obra(conn_portal, obra_id)`) —
    só usamos `obra["id"]`; nenhum outro campo (nome/cliente/etc) cruza a
    fronteira, exceto se `obra_rotulo` for passado explicitamente pelo
    curador (AC 5 — nunca o `nome` cru por default).
    `obra_dir`: path absoluto PRÉ-RESOLVIDO da pasta da obra em
    DADOS-OBRAS — nunca construído a partir de input de usuário aqui.

    Retorna resumo: {publish_batch, itens_publicados, itens_preservados}.
    """
    obra_id = str(obra["id"])
    fechar_no_final = conn is None
    if conn is None:
        conn = get_connection(db_path) if db_path else get_connection()
    assert_no_blacklisted_columns(conn)

    try:
        novo_batch = str(uuid.uuid4())
        rotulo = obra_rotulo or _obra_rotulo_default()

        pavimentos = ficha_reader.descobrir_pavimentos(obra_dir)
        itens_publicados = 0
        itens_preservados = 0

        with conn:
            code_obra = _upsert_obra(conn, obra_id, obra_dir, rotulo, novo_batch)

            for pavimento in pavimentos:
                estado = ficha_reader.ler_estado_pavimento(obra_dir, pavimento)
                if not estado:
                    continue

                # [2026-07-12] código próprio por pavimento — "ficha do
                # pavimento"/recorte limpo da torre, resolve direto pra
                # lista de itens DAQUELE pavimento (não do obra inteiro).
                _upsert_pavimento(conn, obra_id, obra_dir, pavimento, rotulo, novo_batch)

                for classe, tipo_elemento in _CLASSE_PARA_TIPO_ELEMENTO.items():
                    itens = ficha_reader.listar_itens_n1(estado, classe)
                    for item in itens:
                        item_id = str(item.get("item_id") or "")
                        if not item_id:
                            continue
                        titulo = str(item.get("titulo") or item_id)

                        existente = conn.execute(
                            """
                            SELECT code FROM public_codes
                            WHERE obra_id = ? AND pavimento = ? AND classe = ? AND item_id = ?
                                  AND kind = 'item'
                            """,
                            (obra_id, pavimento, classe, item_id),
                        ).fetchone()
                        if existente:
                            code_item = existente["code"]
                            itens_preservados += 1
                        else:
                            code_item = gerar_code(conn)
                            itens_publicados += 1

                        conn.execute(
                            """
                            INSERT INTO public_codes
                                (code, kind, obra_id, obra_dir, pavimento, classe,
                                 item_id, tipo_elemento, titulo_publico, obra_rotulo,
                                 publish_batch)
                            VALUES (?, 'item', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(code) DO UPDATE SET
                                obra_dir=excluded.obra_dir,
                                pavimento=excluded.pavimento,
                                classe=excluded.classe,
                                item_id=excluded.item_id,
                                tipo_elemento=excluded.tipo_elemento,
                                titulo_publico=excluded.titulo_publico,
                                obra_rotulo=excluded.obra_rotulo,
                                publish_batch=excluded.publish_batch,
                                revoked=0
                            """,
                            (
                                code_item, obra_id, str(obra_dir), pavimento, classe,
                                item_id, tipo_elemento, titulo, rotulo, novo_batch,
                            ),
                        )

            # Revoga qualquer publish_batch anterior desta obra (AC 3) —
            # nunca gera novo código, só marca revoked=1 nos batches antigos.
            conn.execute(
                """
                UPDATE public_codes SET revoked = 1
                WHERE obra_id = ? AND publish_batch != ? AND publish_batch IS NOT NULL
                """,
                (obra_id, novo_batch),
            )

        return {
            "publish_batch": novo_batch,
            "code_obra": code_obra,
            "itens_publicados": itens_publicados,
            "itens_preservados": itens_preservados,
        }
    finally:
        if fechar_no_final:
            conn.close()


def revogar(
    *,
    obra_id: Optional[str] = None,
    code: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Revoga uma obra inteira (por `obra_id`) ou um item específico (por
    `code`) — AC 4. Retorna o número de linhas afetadas."""
    if not obra_id and not code:
        raise ValueError("Informe obra_id ou code para revogar.")
    fechar_no_final = conn is None
    if conn is None:
        conn = get_connection(db_path) if db_path else get_connection()
    try:
        with conn:
            if code:
                cur = conn.execute(
                    "UPDATE public_codes SET revoked = 1 WHERE code = ?", (code,)
                )
            else:
                cur = conn.execute(
                    "UPDATE public_codes SET revoked = 1 WHERE obra_id = ?", (obra_id,)
                )
            return cur.rowcount
    finally:
        if fechar_no_final:
            conn.close()
