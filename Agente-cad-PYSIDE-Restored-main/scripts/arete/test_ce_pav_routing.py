# -*- coding: utf-8 -*-
"""
test_ce_pav_routing.py — Valida que _get_recorte_dxf_for_er retorna o recorte
correto para TODOS os pavimentos × itens × classes da Obra_TREINO_1.

Replica a SQL exata do CE sem precisar do app Qt rodando.
Roda em ~2s (puro DB + disco).

Uso:
    pytest scripts/arete/test_ce_pav_routing.py -v
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from arete_config import DB_PATH, PAVIMENTOS_TREINO_1_PIL

OBRA   = "Obra_TREINO_1"
CLASSES = ["PIL", "LV", "FV", "LAJ"]

# Map CE classe -> DB classe (mesmo mapeamento do CE)
_CLS_MAP = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}


# ─── helpers que replicam EXATAMENTE a logica do CE ──────────────────────────

def _ce_get_recorte(obra: str, db_cls: str, item_id: str, pav: str) -> Path | None:
    """Replica _get_recorte_dxf_for_er do CE (tentativas 1 e 2 apenas — DB)."""
    conn = sqlite3.connect(str(DB_PATH))
    cur  = conn.cursor()

    # Tentativa 1: fichas filtradas por pavimento (caminho principal do fix)
    if pav:
        cur.execute(
            "SELECT recorte_path FROM reverse_eng_fichas "
            "WHERE obra_name=? AND classe=? AND elemento_id=? AND pavimento=? "
            "ORDER BY id DESC LIMIT 1",
            (obra, db_cls, item_id, pav)
        )
    else:
        cur.execute(
            "SELECT pavimento FROM reverse_eng_fichas "
            "WHERE obra_name=? AND classe=? AND elemento_id=? ORDER BY id DESC LIMIT 1",
            (obra, db_cls, item_id)
        )
        row = cur.fetchone()
        derived = row[0] if row else None
        if derived:
            cur.execute(
                "SELECT recorte_path FROM reverse_eng_fichas "
                "WHERE obra_name=? AND classe=? AND elemento_id=? AND pavimento=? "
                "ORDER BY id DESC LIMIT 1",
                (obra, db_cls, item_id, derived)
            )
        else:
            cur.execute(
                "SELECT recorte_path FROM reverse_eng_fichas "
                "WHERE obra_name=? AND classe=? AND elemento_id=? ORDER BY id DESC LIMIT 1",
                (obra, db_cls, item_id)
            )

    row = cur.fetchone()
    conn.close()
    if row and row[0]:
        p = Path(row[0])
        return p if p.exists() else None
    return None


def _ficha_pav_for_recorte(obra: str, db_cls: str, item_id: str,
                            recorte_path: Path) -> str | None:
    """Retorna o pavimento da ficha que originou este recorte_path."""
    conn = sqlite3.connect(str(DB_PATH))
    cur  = conn.cursor()
    cur.execute(
        "SELECT pavimento FROM reverse_eng_fichas "
        "WHERE obra_name=? AND classe=? AND elemento_id=? AND recorte_path=? "
        "ORDER BY id DESC LIMIT 1",
        (obra, db_cls, item_id, str(recorte_path))
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def _all_items_for_class(db_cls: str) -> list[str]:
    conn = sqlite3.connect(str(DB_PATH))
    cur  = conn.cursor()
    cur.execute(
        "SELECT DISTINCT elemento_id FROM reverse_eng_fichas "
        "WHERE obra_name=? AND classe=? ORDER BY elemento_id",
        (OBRA, db_cls)
    )
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def _combos_with_fichas() -> list[tuple[str, str, str]]:
    """Retorna todas as (db_cls, item_id, pav) que tem ficha no DB."""
    conn = sqlite3.connect(str(DB_PATH))
    cur  = conn.cursor()
    cur.execute(
        "SELECT DISTINCT classe, elemento_id, pavimento "
        "FROM reverse_eng_fichas WHERE obra_name=? "
        "ORDER BY classe, elemento_id, pavimento",
        (OBRA,)
    )
    rows = cur.fetchall()
    conn.close()
    return [(r[0], r[1], r[2]) for r in rows if r[2]]  # exclui pav=NULL


# ─── TESTES ──────────────────────────────────────────────────────────────────

class TestDbSchema:
    """Sanidade do schema antes de tudo."""

    def test_fichas_tem_coluna_pavimento(self):
        conn = sqlite3.connect(str(DB_PATH))
        cur  = conn.cursor()
        cur.execute("PRAGMA table_info(reverse_eng_fichas)")
        cols = {r[1] for r in cur.fetchall()}
        conn.close()
        assert "pavimento" in cols, "reverse_eng_fichas nao tem coluna 'pavimento'"

    def test_fichas_tem_recortes_preenchidos(self):
        conn = sqlite3.connect(str(DB_PATH))
        cur  = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM reverse_eng_fichas "
            "WHERE obra_name=? AND recorte_path IS NOT NULL AND recorte_path != ''",
            (OBRA,)
        )
        n = cur.fetchone()[0]
        conn.close()
        assert n > 0, "Nenhuma ficha com recorte_path preenchido"
        print(f"\n  fichas com recorte_path: {n}")

    def test_combos_pav_item_disponiveis(self):
        combos = _combos_with_fichas()
        assert len(combos) > 0, "Nenhuma combinacao (classe, item, pav) no DB"
        print(f"\n  combos disponiveis: {len(combos)}")
        by_cls = {}
        for cls, item, pav in combos:
            by_cls.setdefault(cls, set()).add(pav)
        for cls, pavs in sorted(by_cls.items()):
            print(f"    {cls}: {sorted(pavs)}")


class TestPavRouting:
    """Para cada (classe, item, pav) no DB, valida que o CE retorna o recorte
    do pavimento correto — sem cruzar COBERTURA/TIPO/13_PAV etc."""

    @pytest.fixture(scope="class")
    def combos(self):
        return _combos_with_fichas()

    def test_recorte_existe_para_cada_combo(self, combos):
        """Recorte resolvido e arquivo existe em disco para cada combo."""
        sem_recorte = []
        for db_cls, item_id, pav in combos:
            p = _ce_get_recorte(OBRA, db_cls, item_id, pav)
            if p is None:
                sem_recorte.append(f"{db_cls}/{item_id}/{pav}")

        if sem_recorte:
            print(f"\n  Combos sem recorte em disco ({len(sem_recorte)}):")
            for s in sem_recorte[:20]:
                print(f"    {s}")
        pct_ok = (len(combos) - len(sem_recorte)) / len(combos) * 100
        print(f"\n  {len(combos)-len(sem_recorte)}/{len(combos)} combos com recorte ({pct_ok:.1f}%)")
        # Aceita ate 5% sem recorte (fichas recentes podem ter path nao gravado)
        assert len(sem_recorte) / len(combos) <= 0.05, (
            f"{len(sem_recorte)} combos sem recorte (>{5}%): {sem_recorte[:10]}")

    def test_recorte_pertence_ao_pav_correto(self, combos):
        """O recorte retornado pertence à ficha do pavimento solicitado —
        nao a outro pavimento (bug original: TIPO/COBERTURA em vez de 13_PAV)."""
        erros_pav = []
        sem_recorte = []

        for db_cls, item_id, pav in combos:
            p = _ce_get_recorte(OBRA, db_cls, item_id, pav)
            if p is None:
                sem_recorte.append(f"{db_cls}/{item_id}/{pav}")
                continue

            # Verifica que a ficha que originou este recorte_path e do pav correto
            ficha_pav = _ficha_pav_for_recorte(OBRA, db_cls, item_id, p)
            if ficha_pav and ficha_pav != pav:
                erros_pav.append(
                    f"{db_cls}/{item_id}: pediu pav={pav}, "
                    f"recebeu recorte de pav={ficha_pav} ({p.name})"
                )

        if erros_pav:
            print(f"\n  ERROS de pavimento ({len(erros_pav)}):")
            for e in erros_pav:
                print(f"    {e}")

        assert not erros_pav, (
            f"{len(erros_pav)} itens com recorte do pav errado:\n" +
            "\n".join(erros_pav))

    def test_nao_cruza_pavimentos_criticos(self, combos):
        """Garante que PIL 13_PAV nao retorna recorte de COBERTURA/TIPO/12_PAV
        (os tres pavimentos que causavam o bug original)."""
        criticos = {"COBERTURA", "12_PAV", "TIPO"}
        erros = []

        for db_cls, item_id, pav in combos:
            if db_cls != "PIL" or pav != "13_PAV":
                continue
            p = _ce_get_recorte(OBRA, db_cls, item_id, "13_PAV")
            if p is None:
                continue
            ficha_pav = _ficha_pav_for_recorte(OBRA, db_cls, item_id, p)
            if ficha_pav in criticos:
                erros.append(
                    f"PIL/{item_id}: retornou pav={ficha_pav} em vez de 13_PAV"
                )

        assert not erros, "Bug original ainda presente:\n" + "\n".join(erros)

    def test_todos_pavimentos_treino1_resolvem_pil(self):
        """Para PIL, todos os 7 pavimentos tem ao menos 1 item resolvendo corretamente."""
        itens = _all_items_for_class("PIL")
        falhas_por_pav = {}

        for pav in PAVIMENTOS_TREINO_1_PIL:
            conn = sqlite3.connect(str(DB_PATH))
            cur  = conn.cursor()
            cur.execute(
                "SELECT DISTINCT elemento_id FROM reverse_eng_fichas "
                "WHERE obra_name=? AND classe='PIL' AND pavimento=?",
                (OBRA, pav)
            )
            itens_no_pav = [r[0] for r in cur.fetchall()]
            conn.close()

            if not itens_no_pav:
                falhas_por_pav[pav] = "sem fichas no DB para este pav"
                continue

            ok = 0
            for item_id in itens_no_pav:
                p = _ce_get_recorte(OBRA, "PIL", item_id, pav)
                if p:
                    ok += 1

            pct = ok / len(itens_no_pav) * 100
            print(f"\n  PIL/{pav}: {ok}/{len(itens_no_pav)} itens com recorte ({pct:.0f}%)")
            if ok == 0:
                falhas_por_pav[pav] = f"0/{len(itens_no_pav)} itens resolvidos"

        assert not falhas_por_pav, (
            "Pavimentos sem nenhum recorte resolvido: " +
            str(falhas_por_pav))


class TestCePavIntegration:
    """Simula o loop completo: para cada pav que o usuario poderia selecionar
    na UI, verifica que a cadeia pav -> recorte -> pav_correto fecha."""

    @pytest.mark.parametrize("pav", PAVIMENTOS_TREINO_1_PIL)
    def test_pil_pav_loop(self, pav):
        """Simula current_pav_key=pav para todos os itens PIL desse pavimento."""
        conn = sqlite3.connect(str(DB_PATH))
        cur  = conn.cursor()
        cur.execute(
            "SELECT DISTINCT elemento_id FROM reverse_eng_fichas "
            "WHERE obra_name=? AND classe='PIL' AND pavimento=? ORDER BY elemento_id",
            (OBRA, pav)
        )
        itens = [r[0] for r in cur.fetchall()]
        conn.close()

        if not itens:
            pytest.skip(f"Sem fichas PIL para {pav}")

        erros = []
        sem_recorte = []
        for item_id in itens:
            p = _ce_get_recorte(OBRA, "PIL", item_id, pav)
            if p is None:
                sem_recorte.append(item_id)
                continue
            ficha_pav = _ficha_pav_for_recorte(OBRA, "PIL", item_id, p)
            if ficha_pav and ficha_pav != pav:
                erros.append(f"{item_id}: esperado {pav}, recebeu {ficha_pav}")

        total = len(itens)
        print(f"\n  PIL/{pav}: {total-len(sem_recorte)-len(erros)}/{total} OK  "
              f"| sem_recorte={len(sem_recorte)} | pav_errado={len(erros)}")
        if sem_recorte:
            print(f"    sem_recorte: {sem_recorte[:10]}")
        if erros:
            print(f"    pav_errado: {erros[:5]}")

        assert not erros, f"PIL/{pav} — recortes com pav errado: {erros}"
        # Tolerancia: max 10% sem recorte em disco (paths podem nao existir para todos os pavs)
        assert len(sem_recorte) / total <= 0.10, (
            f"PIL/{pav} — {len(sem_recorte)}/{total} sem recorte em disco (>10%)")
