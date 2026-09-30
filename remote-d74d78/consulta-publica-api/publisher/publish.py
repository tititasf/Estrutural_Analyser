"""Publisher — projeta uma obra do portal interno para `public_consulta.db`
mintando códigos opacos por item (STORY-01).

Reaproveita `descobrir_pavimentos`/`listar_itens_n1`/`CLASSES_N1` do portal
existente (`portal/app/ficha_reader.py`) — mesma fonte de dados usada pela
STORY-05. Zero acoplamento com `src/core/lv_generation_contract.py` ou
qualquer coisa do motor desktop/PySide6.
"""

from __future__ import annotations

import json
import re
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

# classe (ficha_reader.CLASSES_N1) -> tipo_elemento publico, 1 código por
# item. Classes de convencao/meta (convencao_pilares, convencao_niveis_lajes,
# cortes) NAO sao publicadas como item proprio.
_CLASSE_PARA_TIPO_ELEMENTO = {
    "lajes": "laje",
    "fundo": "viga_fundo",
}

# [2026-09-28] Pilar: 2 códigos por pilar, 1 por variante N3 (a ficha muda
# conforme as vigas param ou passam nele). A identidade usa a própria classe
# da variante (item_id "P1_Para"/"P1_Passa"); o código legado de `pilares`/
# `pilares_especiais` (antes 1 por pilar) é herdado pela variante, pra QR já
# impresso continuar abrindo. `pilares_especiais` deixa de existir como lista
# (era cópia dos não-retangulares).
_PILAR_VARIANTES = (
    ("param", "pilares_n3_para", "_Para", ("pilares",)),
    ("passa", "pilares_n3_passa", "_Passa", ("pilares_especiais",)),
)

# [2026-09-28] Lateral de viga: 1 código por viga por listagem (Para/Passa),
# com os segmentos dos lados A e B no payload. A âncora (classe, item_id) da
# linha é o 1º segmento — é o que `/ficha/{code}` resolve sem saber de payload.
_LV_LISTAGENS = (
    ("param", ("lateral_a_para", "lateral_b_para")),
    ("passa", ("lateral_a_passa", "lateral_b_passa")),
)
_LV_LADO = {"lateral_a_para": "A", "lateral_b_para": "B",
            "lateral_a_passa": "A", "lateral_b_passa": "B"}


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


def _num_segmento(item: dict) -> int:
    m = re.search(r"[0-9]+", str((item.get("campos") or {}).get("Segmento") or ""))
    return int(m.group(0)) if m else 0


def _unidades_do_pavimento(estado: dict) -> list[dict]:
    """Tudo o que vira 1 código público num pavimento. Cada unidade traz a
    âncora (classe, item_id) que `/ficha/{code}` resolve, o payload e os
    candidatos legados cujo código ela herda."""
    unidades: list[dict] = []

    for classe, tipo in _CLASSE_PARA_TIPO_ELEMENTO.items():
        for item in ficha_reader.listar_itens_n1(estado, classe):
            item_id = str(item.get("item_id") or "")
            if item_id:
                unidades.append(dict(classe=classe, item_id=item_id, tipo=tipo,
                                     titulo=str(item.get("titulo") or item_id),
                                     payload=None, legado=[]))

    for modo, classe, sufixo, classes_legado in _PILAR_VARIANTES:
        for item in ficha_reader.listar_itens_n1(estado, classe):
            item_id = str(item.get("item_id") or "")
            if not item_id:
                continue
            nome = item_id.removesuffix(sufixo)
            unidades.append(dict(classe=classe, item_id=item_id, tipo="pilar", titulo=nome,
                                 payload={"modo_pilar": modo},
                                 legado=[(c, nome) for c in classes_legado]))

    for modo, classes in _LV_LISTAGENS:
        por_viga: dict[str, list[tuple[str, dict]]] = {}
        for classe in classes:
            for item in ficha_reader.listar_itens_n1(estado, classe):
                if item.get("item_id") and item.get("beam_name"):
                    por_viga.setdefault(str(item["beam_name"]), []).append((classe, item))
        for viga, segs in por_viga.items():
            segs.sort(key=lambda s: (_LV_LADO[s[0]], _num_segmento(s[1])))
            segmentos = [{
                "classe": classe,
                "item_id": str(item["item_id"]),
                "lado": _LV_LADO[classe],
                "segmento": str((item.get("campos") or {}).get("Segmento") or ""),
                "campos": item.get("campos") or {},
                "atencao": item.get("atencao") or "",
            } for classe, item in segs]
            ancora = segmentos[0]
            unidades.append(dict(classe=ancora["classe"], item_id=ancora["item_id"],
                                 tipo="viga_lateral", titulo=viga,
                                 payload={"modo": modo, "viga": viga, "segmentos": segmentos},
                                 legado=[], viga=viga, modo=modo))
    return unidades


def _achar_code(conn: sqlite3.Connection, obra_id: str, pavimento: str, u: dict) -> Optional[str]:
    """Código já publicado desta unidade (preserva o link), senão None."""
    if u.get("viga"):
        row = conn.execute(
            """
            SELECT code FROM public_codes
            WHERE obra_id = ? AND pavimento = ? AND kind = 'item'
                  AND tipo_elemento = 'viga_lateral'
                  AND json_extract(payload_json, '$.viga') = ?
                  AND json_extract(payload_json, '$.modo') = ?
            ORDER BY revoked, created_at LIMIT 1
            """,
            (obra_id, pavimento, u["viga"], u["modo"]),
        ).fetchone()
        if row:
            return row["code"]
    for classe, item_id in [(u["classe"], u["item_id"]), *u["legado"]]:
        row = conn.execute(
            """
            SELECT code FROM public_codes
            WHERE obra_id = ? AND pavimento = ? AND classe = ? AND item_id = ?
                  AND kind = 'item'
            """,
            (obra_id, pavimento, classe, item_id),
        ).fetchone()
        if row:
            return row["code"]
    return None


def _gravar_item(
    conn: sqlite3.Connection, code: str, u: dict, *,
    obra_id: str, obra_dir: Path, pavimento: str, rotulo: str, batch: str,
) -> None:
    payload = u["payload"]
    if payload and payload.get("segmentos"):
        payload = {**payload, "segmentos": [
            {**s, "indice": i, "svg": {
                nivel: f"/api/v1/ficha/{code}/svg/{nivel}?seg={i}" for nivel in ("n1", "n3")
            }}
            for i, s in enumerate(payload["segmentos"])
        ]}
    # A âncora pode estar ocupada por um código antigo que esta unidade não
    # herdou (ex.: código do segmento 2 quando a viga já tinha código próprio):
    # esse código sai da identidade e fica revogado.
    conn.execute(
        """
        UPDATE public_codes SET item_id = item_id || '#' || code, revoked = 1
        WHERE obra_id = ? AND pavimento = ? AND classe = ? AND item_id = ?
              AND kind = 'item' AND code != ?
        """,
        (obra_id, pavimento, u["classe"], u["item_id"], code),
    )
    conn.execute(
        """
        INSERT INTO public_codes
            (code, kind, obra_id, obra_dir, pavimento, classe,
             item_id, tipo_elemento, titulo_publico, obra_rotulo,
             publish_batch, payload_json)
        VALUES (?, 'item', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            obra_dir=excluded.obra_dir,
            pavimento=excluded.pavimento,
            classe=excluded.classe,
            item_id=excluded.item_id,
            tipo_elemento=excluded.tipo_elemento,
            titulo_publico=excluded.titulo_publico,
            obra_rotulo=excluded.obra_rotulo,
            publish_batch=excluded.publish_batch,
            payload_json=excluded.payload_json,
            revoked=0
        """,
        (
            code, obra_id, str(obra_dir), pavimento, u["classe"], u["item_id"],
            u["tipo"], u["titulo"], rotulo, batch,
            json.dumps(payload, ensure_ascii=False, default=str) if payload else None,
        ),
    )


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

                ctx = dict(obra_id=obra_id, obra_dir=obra_dir, pavimento=pavimento,
                           rotulo=rotulo, batch=novo_batch)
                for unidade in _unidades_do_pavimento(estado):
                    code_item = _achar_code(conn, obra_id, pavimento, unidade)
                    if code_item:
                        itens_preservados += 1
                    else:
                        code_item = gerar_code(conn)
                        itens_publicados += 1
                    _gravar_item(conn, code_item, unidade, **ctx)

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
