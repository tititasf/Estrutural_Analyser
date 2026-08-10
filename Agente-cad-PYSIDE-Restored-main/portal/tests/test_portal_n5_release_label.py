"""§5 R9 — rótulo certificado/beta na liberação do N5.

Código-alvo real: portal/app/certification.py (classificar_certificacao a partir de
STATUS.md read-only) + portal/app/n5_release.py (liberar_n5, snapshot do rótulo) +
repository.registrar_n5_release (validação de domínio PL/LV/FV/LJ).

O handoff supôs `build_release_view(...) -> ReleaseView.cert_status`. A implementação
real espalha a mesma garantia por: classificar_certificacao (rótulo) + liberar_n5
(congela o snapshot no release) + o gate 409 na rota /obras/{id}/n5 (testado no
test_portal_http_flow.py, S9.5). Aqui cobrimos S9.1–S9.3 e o snapshot.
"""

from __future__ import annotations

import pytest

from portal.app import certification, n5_release
from portal.db import repository as repo

CLASSES = ("PL", "LV", "FV", "LJ")


def _status_md(tmp_path, linhas: list[str]):
    """Escreve um STATUS.md com a tabela 'Arete por classe' que o parser espera."""
    cabecalho = [
        "| Classe | Pav | Run | PASS | FAIL | BLOCKED | Arete % | Golden selado | Alerta |",
        "|--------|-----|-----|------|------|---------|---------|---------------|--------|",
    ]
    p = tmp_path / "STATUS.md"
    p.write_text("\n".join(cabecalho + linhas), encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# S9.1 — classe certificada -> rótulo 'certificado', nunca None/vazio
# --------------------------------------------------------------------------- #

def test_s9_1_classe_certificada(tmp_path):
    status = _status_md(tmp_path, [
        "| PIL | 13 | r1 | 50 | 0 | 0 | 100.0% | sim | ok |",
    ])
    rotulo = certification.classificar_certificacao(status, "PL")
    assert rotulo == "certificado"
    assert rotulo  # não vazio


# --------------------------------------------------------------------------- #
# S9.2 — classe beta -> rótulo 'beta', presente e correto
# --------------------------------------------------------------------------- #

def test_s9_2_classe_beta_por_arete_incompleto(tmp_path):
    status = _status_md(tmp_path, [
        "| FV | 13 | r1 | 40 | 3 | 0 | 87.5% | nao | FAIL aberto |",
    ])
    assert certification.classificar_certificacao(status, "FV") == "beta"


def test_s9_2b_beta_por_fail_mesmo_com_100pct(tmp_path):
    """Conservador: 100% mas com 'FAIL aberto' no alerta -> beta (nunca superestima)."""
    status = _status_md(tmp_path, [
        "| LV | 13 | r1 | 60 | 1 | 0 | 100.0% | sim | FAIL aberto |",
    ])
    assert certification.classificar_certificacao(status, "LV") == "beta"


def test_um_pavimento_beta_rebaixa_a_classe_inteira(tmp_path):
    """Se qualquer pavimento da classe está beta, a classe inteira vira beta."""
    status = _status_md(tmp_path, [
        "| LJ | 13 | r1 | 30 | 0 | 0 | 100.0% | sim | ok |",
        "| LJ | 14 | r1 | 20 | 2 | 0 | 90.0%  | nao | FAIL aberto |",
    ])
    assert certification.classificar_certificacao(status, "LJ") == "beta"


# --------------------------------------------------------------------------- #
# S9.3 — INVARIANTE anti-omissão: toda classe SEMPRE recebe um rótulo válido
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("classe", CLASSES)
def test_s9_3_nunca_omite_rotulo_status_presente(tmp_path, classe):
    status = _status_md(tmp_path, [
        "| PIL | 13 | r1 | 10 | 0 | 0 | 100.0% | sim | ok |",
        "| LV  | 13 | r1 | 10 | 2 | 0 |  80.0% | nao | FAIL aberto |",
    ])
    rotulo = certification.classificar_certificacao(status, classe)
    assert rotulo in ("certificado", "beta")  # nunca None/vazio, sempre um dos dois


@pytest.mark.parametrize("classe", CLASSES)
def test_s9_3b_nunca_omite_rotulo_status_ausente(tmp_path, classe):
    """Fail-safe R9: STATUS.md inexistente -> 'beta' (cauteloso), nunca omite."""
    ausente = tmp_path / "nao_existe_STATUS.md"
    rotulo = certification.classificar_certificacao(ausente, classe)
    assert rotulo == "beta"


def test_classe_desconhecida_retorna_beta(tmp_path):
    """Classe fora do domínio -> fail-safe 'beta' (nunca 'certificado' por engano)."""
    status = _status_md(tmp_path, ["| PIL | 13 | r1 | 10 | 0 | 0 | 100.0% | sim | ok |"])
    assert certification.classificar_certificacao(status, "XX") == "beta"


def test_override_do_dono_tem_ultima_palavra(tmp_path, monkeypatch):
    """PORTAL_CERT_OVERRIDE força o rótulo mesmo contra o STATUS.md."""
    status = _status_md(tmp_path, ["| FV | 13 | r1 | 40 | 3 | 0 | 87.5% | nao | FAIL aberto |"])
    monkeypatch.setenv("PORTAL_CERT_OVERRIDE", "FV:certificado")
    assert certification.classificar_certificacao(status, "FV") == "certificado"


# --------------------------------------------------------------------------- #
# liberar_n5 — snapshot do rótulo congela no momento da liberação (R9)
# --------------------------------------------------------------------------- #

def test_liberar_n5_congela_snapshot_beta(conn, settings, membro_id, tmp_path):
    """liberar_n5 (dry_run) grava o rótulo LIDO no momento; STATUS ausente -> beta."""
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra", pasta_drive_id="p")
    obra = repo.obter_obra(conn, obra_id)

    info = n5_release.liberar_n5(
        conn, settings, obra=obra, classe="FV", pavimento="13",
        membro_id=membro_id, dry_run=True,  # não dispara assemble_n5 real
    )
    assert info["status_certificacao"] == "beta"  # STATUS.md do settings não existe
    releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    assert len(releases) == 1
    assert releases[0]["status_certificacao"] == "beta"  # snapshot persistido


def test_liberar_n5_classe_invalida_levanta(conn, settings, membro_id):
    """Domínio N5 é PL/LV/FV/LJ; classe inválida estoura ValueError (repository valida)."""
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="O", pasta_drive_id="p")
    obra = repo.obter_obra(conn, obra_id)
    with pytest.raises(ValueError):
        n5_release.liberar_n5(
            conn, settings, obra=obra, classe="ZZ", pavimento="13",
            membro_id=membro_id, dry_run=True,
        )


# --------------------------------------------------------------------------- #
# [2026-07-30] Tabela lida por NOME DE CABECALHO, nao por posicao.
# O parser antigo contava colunas fixas e quebrou quando o gerador ganhou a
# coluna "Regressao". Como este rotulo gateia a liberacao do N5, o parser tem
# de aguentar o gerador evoluir.
# --------------------------------------------------------------------------- #

def _status_md_bruto(tmp_path, texto: str):
    p = tmp_path / "STATUS.md"
    p.write_text(texto, encoding="utf-8")
    return p


def test_layout_com_coluna_regressao_e_lido(tmp_path):
    """Layout atual do gerar_status.py (10 colunas, com Regressao)."""
    status = _status_md_bruto(tmp_path, "\n".join([
        "| Classe | Pav | Run | PASS | FAIL | BLOCKED | Arete % | Golden selado | Regressão | Alerta |",
        "|--------|-----|-----|------|------|---------|---------|---------------|-----------|--------|",
        "| FV | 13_PAV | r1 | 26 | 0 | 0 | 100.0% | 26 | 0 |  |",
    ]))
    assert certification.classificar_certificacao(status, "FV") == "certificado"


def test_layout_legado_sem_regressao_continua_lido(tmp_path):
    """Layout de 9 colunas (anterior a 2026-07-30) nao pode virar 'beta' por engano."""
    status = _status_md_bruto(tmp_path, "\n".join([
        "| Classe | Pav | Run | PASS | FAIL | BLOCKED | Arete % | Golden selado | Alerta |",
        "|--------|-----|-----|------|------|---------|---------|---------------|--------|",
        "| FV | 13_PAV | r1 | 26 | 0 | 0 | 100.0% | 26 |  |",
    ]))
    assert certification.classificar_certificacao(status, "FV") == "certificado"


def test_coluna_nova_desconhecida_nao_quebra(tmp_path):
    """Gerador pode adicionar coluna sem derrubar o gate do N5."""
    status = _status_md_bruto(tmp_path, "\n".join([
        "| Classe | Pav | Run | PASS | FAIL | BLOCKED | Arete % | Golden selado | Regressão | Custo | Alerta |",
        "|--------|-----|-----|------|------|---------|---------|---------------|-----------|-------|--------|",
        "| FV | 13_PAV | r1 | 26 | 0 | 0 | 100.0% | 26 | 0 | 3.2 |  |",
    ]))
    assert certification.classificar_certificacao(status, "FV") == "certificado"


def test_regressao_positiva_rebaixa_para_beta(tmp_path):
    """Item selado reprovando nunca pode sair rotulado como certificado."""
    status = _status_md_bruto(tmp_path, "\n".join([
        "| Classe | Pav | Run | PASS | FAIL | BLOCKED | Arete % | Golden selado | Regressão | Alerta |",
        "|--------|-----|-----|------|------|---------|---------|---------------|-----------|--------|",
        "| FV | 13_PAV | r1 | 26 | 0 | 0 | 100.0% | 26 | 2 |  |",
    ]))
    assert certification.classificar_certificacao(status, "FV") == "beta"
