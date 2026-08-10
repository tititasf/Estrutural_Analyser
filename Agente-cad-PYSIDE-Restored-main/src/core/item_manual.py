"""Identidade e criação de item desenhado na WEB (P3 do caminho de entrega).

Contexto da decisão (auditoria 2026-07-30, confirmada pelo dono):

`projeto_id` NÃO é identidade de obra — é a chave de escopo do Motor Reverso do
app DESKTOP (`diagnostic_reverse_hub.py`). Levantamento de quem realmente lê:

    portal (web) ................ 0 ocorrências
    motor_reverso_*.py .......... 0 ocorrências
    scripts/arete ............... praticamente nenhuma, e com decisão registrada
                                  em qa_laj_quadro_pavimento.py:327 — "Fichas N2
                                  são legadas e podem não ter projeto_id; escopo
                                  explícito obra+pav+classe"

Além disso o campo nunca funcionou como declarado: `database.py:498` cria
`projeto_id INTEGER REFERENCES reverse_eng_projetos(id)` e `database.py:581` o
adiciona por migração como `TEXT`. Por isso convivem UUIDs e a string
'TREINO_1' na mesma coluna, e a tabela referenciada está VAZIA (0 linhas).

Decisão adotada: a chave de trabalho é `(obra_name, pavimento, classe,
elemento_id)` — a mesma que o Arete já usa e que resolve 95,5% dos vínculos
recorte→ficha. `projeto_id` recebe um valor DETERMINÍSTICO e legível em vez de
NULL ou UUID novo: não vira lixo, é rastreável, e uma migração futura para
identidade canônica fica mais fácil, não mais difícil.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .obra_identity import normalizar_pavimento

# Prefixo que marca a origem. Item criado na web é distinguível de item vindo do
# motor sem precisar de outra coluna.
PREFIXO_WEB = "web"

# Status gravado no recorte/ficha. `manual` já é o default da coluna `status` em
# reverse_eng_recortes (database.py:583) — mantido para não inventar vocabulário.
STATUS_MANUAL = "manual"

# Prefixo de nome por classe, igual ao que o desktop usa em create_manual_item.
PREFIXO_CLASSE = {"PIL": "P", "LAJ": "L", "FV": "VF", "LV": "V"}

# Classe SA (banco) → classe N5 assembler + prefixo de preview em Fase-6.
# assemble_n5 descobre por filesystem (`PL_preview_*`, `LJ_preview_*`…); sem
# esse arquivo o item some do N5 em silêncio (G-3 do masterplan de entrega).
CLASSE_SA_PARA_N5 = {"PIL": "PL", "LAJ": "LJ", "FV": "FV", "LV": "LV"}
PREFIXO_PREVIEW_N3 = {
    "PL": "PL_preview_",
    "LJ": "LJ_preview_",
    "LV": "LV_preview_",
    "FV": "FV_preview_",
}


class ItemDuplicado(ValueError):
    """Já existe item com esse nome nesta obra/pavimento/classe.

    Existe porque `reverse_eng_recortes` NÃO tem restrição UNIQUE: nada no banco
    impede gravar `P50` duas vezes. A proteção é do código — e sem ela o
    operador criaria duplicata sem aviso, exatamente o tipo de item fantasma que
    a auditoria encontrou.
    """


@dataclass(frozen=True)
class IdentidadeItem:
    """Chave completa de um item, na forma canônica."""

    obra_name: str
    pavimento: str
    classe: str
    elemento_id: str

    @property
    def projeto_id(self) -> str:
        return projeto_id_web(self.obra_name, self.pavimento)


def projeto_id_web(obra_name: str, pavimento: str) -> str:
    """`projeto_id` determinístico para item criado na web.

    Determinístico de propósito: a mesma obra+pavimento sempre produz o mesmo
    valor, então reprocessar não cria identidade nova. Legível de propósito:
    olhando a linha no banco dá para saber de onde o item veio.

    >>> projeto_id_web("Obra_TREINO_1", "13_PAV")
    'web:Obra_TREINO_1:13_PAV'
    """
    pav = normalizar_pavimento(pavimento) or str(pavimento or "").strip()
    return f"{PREFIXO_WEB}:{str(obra_name or '').strip()}:{pav}"


def eh_projeto_web(projeto_id: Optional[str]) -> bool:
    """O item veio da web? Usado para filtrar/auditar sem coluna nova."""
    return str(projeto_id or "").startswith(f"{PREFIXO_WEB}:")


def normalizar_nome_item(nome: str) -> str:
    """Nome digitado pelo operador -> forma canônica (P12, L301, V301...).

    Só limpa: maiúsculas, sem espaços nas pontas, sem espaço interno. NÃO
    inventa prefixo — se o operador digitou "12" em vez de "P12", quem decide é
    `sugerir_proximo_nome`/a UI, não esta função. Renomear em silêncio esconde
    erro de digitação.
    """
    return re.sub(r"\s+", "", str(nome or "").strip().upper())


def item_ja_existe(
    conn: sqlite3.Connection, ident: IdentidadeItem
) -> bool:
    """Existe ficha OU recorte com essa chave?

    Checa as duas tabelas porque elas podem divergir: um recorte órfão sem ficha
    ainda ocupa o nome, e reusá-lo produziria dois recortes disputando o mesmo
    item na hora de gerar o N3.
    """
    ficha = conn.execute(
        "SELECT 1 FROM reverse_eng_fichas "
        "WHERE obra_name=? AND pavimento=? AND classe=? AND elemento_id=? LIMIT 1",
        (ident.obra_name, ident.pavimento, ident.classe, ident.elemento_id),
    ).fetchone()
    if ficha:
        return True
    recorte = conn.execute(
        "SELECT 1 FROM reverse_eng_recortes "
        "WHERE obra_name=? AND classe=? AND elemento_id=? "
        "AND (projeto_id=? OR projeto_id IS NULL) LIMIT 1",
        (ident.obra_name, ident.classe, ident.elemento_id, ident.projeto_id),
    ).fetchone()
    return recorte is not None


def sugerir_proximo_nome(
    conn: sqlite3.Connection, obra_name: str, pavimento: str, classe: str
) -> str:
    """Próximo nome livre da classe (P36 se existem P1..P35).

    Olha o MAIOR número já usado, não a contagem: com P1..P35 e P41..P51, contar
    daria 46 e colidiria com o P46 existente.
    """
    prefixo = PREFIXO_CLASSE.get(classe.upper(), "IT")
    pav = normalizar_pavimento(pavimento) or pavimento
    usados = conn.execute(
        "SELECT elemento_id FROM reverse_eng_fichas "
        "WHERE obra_name=? AND pavimento=? AND classe=?",
        (obra_name, pav, classe),
    ).fetchall()
    maior = 0
    padrao = re.compile(rf"^{re.escape(prefixo)}(\d+)", re.IGNORECASE)
    for (nome,) in usados:
        achado = padrao.match(str(nome or ""))
        if achado:
            maior = max(maior, int(achado.group(1)))
    return f"{prefixo}{maior + 1}"


def criar_item_manual(
    conn: sqlite3.Connection,
    *,
    obra_name: str,
    pavimento: str,
    classe: str,
    elemento_id: str,
    recorte_path: str,
    bbox: tuple[float, float, float, float],
    entity_count: int = 0,
    campos: Optional[dict] = None,
) -> IdentidadeItem:
    """Grava recorte + ficha de um item desenhado na web.

    NÃO roda motor e NÃO interpreta: só cria a linha com a geometria recortada,
    para o headless da classe processar depois. A ficha nasce com
    `campos_json` vazio e `status='manual'` — inventar campos aqui produziria
    dado que parece interpretado e não é.

    Levanta `ItemDuplicado` se o nome já existe na obra/pavimento/classe.
    """
    ident = IdentidadeItem(
        obra_name=str(obra_name).strip(),
        pavimento=normalizar_pavimento(pavimento) or str(pavimento).strip(),
        classe=str(classe).strip().upper(),
        elemento_id=normalizar_nome_item(elemento_id),
    )
    if not ident.elemento_id:
        raise ValueError("elemento_id vazio")
    if item_ja_existe(conn, ident):
        raise ItemDuplicado(
            f"{ident.elemento_id} ja existe em {ident.obra_name}/"
            f"{ident.pavimento}/{ident.classe}"
        )

    agora = datetime.now().isoformat(timespec="seconds")
    x0, y0, x1, y1 = (float(v) for v in bbox)
    bbox_json = json.dumps({"x0": x0, "y0": y0, "x1": x1, "y1": y1})

    with conn:  # recorte e ficha entram juntos, ou nenhum dos dois
        cur = conn.execute(
            "INSERT INTO reverse_eng_fichas "
            "(projeto_id, obra_name, pavimento, classe, elemento_id, campos_json, "
            " recorte_path, confianca, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ident.projeto_id, ident.obra_name, ident.pavimento, ident.classe,
             ident.elemento_id, "{}", recorte_path, 0.0, STATUS_MANUAL, agora, agora),
        )
        ficha_id = cur.lastrowid
        conn.execute(
            "INSERT INTO reverse_eng_recortes "
            "(ficha_id, obra_name, elemento_id, recorte_path, bbox_json, "
            " entity_count, created_at, projeto_id, classe, status, confidence) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ficha_id, ident.obra_name, ident.elemento_id, recorte_path, bbox_json,
             int(entity_count), agora, ident.projeto_id, ident.classe,
             STATUS_MANUAL, 0.0),
        )
    return ident


def caminho_preview_n3(obra_dir: str | Path, classe: str, elemento_id: str) -> Path:
    """Path canônico do preview N3 que o assemble_n5 varre em Fase-6."""
    n5 = CLASSE_SA_PARA_N5.get(str(classe).strip().upper())
    if n5 is None:
        raise ValueError(f"classe SA desconhecida para N3: {classe}")
    pfx = PREFIXO_PREVIEW_N3[n5]
    nome = normalizar_nome_item(elemento_id)
    return Path(obra_dir) / "Fase-6_Execucao_CAD" / f"{pfx}{nome}.dxf"


def materializar_preview_n3(
    obra_dir: str | Path,
    *,
    classe: str,
    elemento_id: str,
    recorte_path: str | Path,
) -> Path:
    """P5 — grava o recorte manual no path que o assemble_n5 descobre.

    Enquanto o robô N3 real (STOG a partir dos campos N1) não rodar, o recorte
    geométrico é a melhor prévia disponível: sem este arquivo o item some da
    prancha N5 sem erro (G-3). Quando o robô gerar o N3 de verdade no mesmo
    path, ele sobrescreve esta cópia.

    Copia (não move) o DXF do recorte: o path em reverse_eng_recortes continua
    apontando para recortes_web/.
    """
    src = Path(recorte_path)
    if not src.is_file():
        raise FileNotFoundError(f"recorte ausente: {src}")
    dest = caminho_preview_n3(obra_dir, classe, elemento_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest
