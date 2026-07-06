"""§1.1 poller + §1.2 parsing/R6 + §4.2 R8 — testes unitários do poller do Drive.

Código-alvo real: portal/app/drive_poller.py (varrer_uma_vez / _varrer_ciclo /
FakeDriveClient). A API do Drive é sempre mockada — nenhum teste toca rede.

Mapeamento handoff -> realidade: o handoff supôs `poll_once(client, seen_store,
download_dir)`. A implementação real é `varrer_uma_vez(conn, client, settings, membros=...)`
— a dedup ("seen store") é a coluna UNIQUE portal_obras.arquivo_hash + obter_obra_por_hash,
e o "download_dir" é settings.dados_obras_dir/<login>/<slug>/entrada. Os testes seguem a
interface real; cada critério GWT do handoff (U1.*, U2.*, S8.*) é preservado.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from portal.app import drive_poller
from portal.app.drive_poller import DriveClient, DriveFile, FakeDriveClient, varrer_uma_vez
from portal.db import repository as repo


# --------------------------------------------------------------------------- #
# Helpers / fakes
# --------------------------------------------------------------------------- #

def _dxf_valido(path: Path) -> None:
    """Escreve um DXF mínimo real via ezdxf (mesma lib do dxf_loader de produção)."""
    import ezdxf

    doc = ezdxf.new()
    doc.modelspace().add_line((0, 0), (1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(path)


class ContadorFakeDrive(FakeDriveClient):
    """FakeDriveClient com contadores de list/download (U1.2: assert download_calls == 0)."""

    def __init__(self, raiz):
        super().__init__(raiz)
        self.list_calls = 0
        self.download_calls = 0

    def list_new_files(self, pasta_id: str) -> list[DriveFile]:
        self.list_calls += 1
        return super().list_new_files(pasta_id)

    def download_file(self, file_id: str, dest: Path) -> Path:
        self.download_calls += 1
        return super().download_file(file_id, dest)


class DriveQuebrado(DriveClient):
    """Cliente que sempre estoura em list_new_files (S8.1/R8: exceção de rede)."""

    def __init__(self, exc: Exception):
        self._exc = exc

    def list_new_files(self, pasta_id):
        raise self._exc

    def download_file(self, file_id, dest):  # pragma: no cover - nunca chega aqui
        raise AssertionError("download não deveria ser chamado num cliente quebrado")

    def obter_ou_criar_pasta(self, nome, pasta_pai_id=None):  # pragma: no cover - nao usado aqui
        raise AssertionError("obter_ou_criar_pasta não deveria ser chamado neste teste")


def _membro(conn, login: str, folder: str) -> dict:
    mid = repo.criar_membro(conn, login=login, nome=login.title(),
                            senha_hash="h", drive_folder_id=folder)
    return repo.obter_membro_por_login(conn, login)


# --------------------------------------------------------------------------- #
# U1.1 — detecção de arquivo novo
# --------------------------------------------------------------------------- #

def test_u1_1_detecta_arquivo_novo(conn, settings, tmp_path):
    fake_raiz = tmp_path / "drive"
    pasta = fake_raiz / "folder-ana"
    _dxf_valido(pasta / "obra_x.dxf")
    client = ContadorFakeDrive(fake_raiz)
    membro = _membro(conn, "ana", "folder-ana")

    novas = varrer_uma_vez(conn, client, settings, membros=[membro])

    assert len(novas) == 1
    obra = repo.obter_obra(conn, novas[0])
    assert obra["membro_id"] == membro["id"]
    assert obra["arquivo_nome"] == "obra_x.dxf"
    assert obra["estado"] == "aguardando_ingestao"
    # arquivo baixado dentro de dados_obras_dir/<login>/<slug>/entrada/
    baixado = Path(obra["local_path"]) / "entrada" / "obra_x.dxf"
    assert baixado.exists()
    assert client.download_calls == 1


# --------------------------------------------------------------------------- #
# U1.2 — idempotência (o núcleo): mesmo conteúdo não rebaixa nem reprocessa
# --------------------------------------------------------------------------- #

def test_u1_2_idempotencia_nao_reprocessa(conn, settings, tmp_path):
    fake_raiz = tmp_path / "drive"
    _dxf_valido(fake_raiz / "folder-ana" / "obra_x.dxf")
    client = ContadorFakeDrive(fake_raiz)
    membro = _membro(conn, "ana", "folder-ana")

    n1 = varrer_uma_vez(conn, client, settings, membros=[membro])
    assert len(n1) == 1
    downloads_apos_primeira = client.download_calls

    # segunda varredura: mesmo conteúdo (mesmo md5) -> nada novo, nenhum download extra
    n2 = varrer_uma_vez(conn, client, settings, membros=[membro])
    assert n2 == []
    assert client.download_calls == downloads_apos_primeira  # nenhum download novo


# --------------------------------------------------------------------------- #
# U1.3 — idempotência por conteúdo (md5), não por id: reenvio corrigido reprocessa
# --------------------------------------------------------------------------- #

def test_u1_3_md5_mudou_reprocessa(conn, settings, tmp_path):
    fake_raiz = tmp_path / "drive"
    alvo = fake_raiz / "folder-ana" / "obra_x.dxf"
    _dxf_valido(alvo)
    client = ContadorFakeDrive(fake_raiz)
    membro = _membro(conn, "ana", "folder-ana")

    n1 = varrer_uma_vez(conn, client, settings, membros=[membro])
    assert len(n1) == 1

    # usuário reenvia a obra CORRIGIDA (conteúdo diferente -> md5 diferente)
    import ezdxf
    doc = ezdxf.new()
    doc.modelspace().add_circle((0, 0), 5)  # geometria distinta => outro md5
    doc.modelspace().add_line((2, 2), (9, 9))
    doc.saveas(alvo)

    n2 = varrer_uma_vez(conn, client, settings, membros=[membro])
    assert len(n2) == 1  # md5 diferente -> obra nova (versão)
    assert n2[0] != n1[0]


# --------------------------------------------------------------------------- #
# U1.4 — multi-usuário isolado: autoria nunca cruza
# --------------------------------------------------------------------------- #

def test_u1_4_multiusuario_isolado(conn, settings, tmp_path):
    fake_raiz = tmp_path / "drive"
    _dxf_valido(fake_raiz / "folder-ana" / "obra_ana.dxf")
    _dxf_valido(fake_raiz / "folder-bruno" / "obra_bruno.dxf")
    client = FakeDriveClient(fake_raiz)
    ana = _membro(conn, "ana", "folder-ana")
    bruno = _membro(conn, "bruno", "folder-bruno")

    novas = varrer_uma_vez(conn, client, settings, membros=[ana, bruno])
    assert len(novas) == 2
    por_membro = {repo.obter_obra(conn, oid)["membro_id"]: repo.obter_obra(conn, oid)
                  for oid in novas}
    assert por_membro[ana["id"]]["arquivo_nome"] == "obra_ana.dxf"
    assert por_membro[bruno["id"]]["arquivo_nome"] == "obra_bruno.dxf"
    # nunca cruza: obra do bruno nunca tem membro_id da ana
    assert por_membro[ana["id"]]["membro_id"] != bruno["id"]


# --------------------------------------------------------------------------- #
# U1.5 — persistência do "visto" entre reinícios (store é o DB em disco)
# --------------------------------------------------------------------------- #

def test_u1_5_visto_sobrevive_reinicio(db_path, settings, tmp_path):
    from portal.db import connection

    fake_raiz = tmp_path / "drive"
    _dxf_valido(fake_raiz / "folder-ana" / "obra_x.dxf")
    client = ContadorFakeDrive(fake_raiz)

    # "processo 1": abre conexão, varre, fecha
    c1 = connection.init_db(db_path)
    m1 = repo.criar_membro(c1, login="ana", nome="Ana", senha_hash="h",
                           drive_folder_id="folder-ana")
    membro1 = repo.obter_membro_por_login(c1, "ana")
    n1 = varrer_uma_vez(c1, client, settings, membros=[membro1])
    assert len(n1) == 1
    c1.close()

    # "processo 2": nova conexão para o MESMO db em disco -> f1 continua visto
    c2 = connection.init_db(db_path)
    membro2 = repo.obter_membro_por_login(c2, "ana")
    downloads_antes = client.download_calls
    n2 = varrer_uma_vez(c2, client, settings, membros=[membro2])
    c2.close()
    assert n2 == []  # dedup durável: não reprocessa
    assert client.download_calls == downloads_antes


# --------------------------------------------------------------------------- #
# §1.2 R6 — parsing: extensão e tamanho filtrados ANTES de virar obra
# --------------------------------------------------------------------------- #

def test_u2_2_extensao_nao_permitida_ignorada(conn, settings, tmp_path):
    fake_raiz = tmp_path / "drive"
    pasta = fake_raiz / "folder-ana"
    pasta.mkdir(parents=True)
    # arquivos fora de .dwg/.dxf: devem ser ignorados pelo poller
    (pasta / "malicioso.exe").write_bytes(b"MZ\x90\x00binario")
    (pasta / "planilha.zip").write_bytes(b"PK\x03\x04zipbomb")
    (pasta / "script.py").write_text("import os; os.system('rm -rf /')")
    (pasta / "notas.txt").write_text("isto nao e um dxf")
    client = ContadorFakeDrive(fake_raiz)
    membro = _membro(conn, "ana", "folder-ana")

    novas = varrer_uma_vez(conn, client, settings, membros=[membro])
    assert novas == []  # nenhum vira obra
    assert client.download_calls == 0  # nem baixados


def test_u2_5_arquivo_acima_do_limite_ignorado(conn, tmp_path):
    from portal.app.config import load_settings

    fake_raiz = tmp_path / "drive"
    pasta = fake_raiz / "folder-ana"
    pasta.mkdir(parents=True)
    # DXF acima do limite (limite = 1 MB neste teste; conteúdo > 1 MB)
    grande = pasta / "gigante.dxf"
    grande.write_bytes(b"0" * (2 * 1024 * 1024))
    settings_1mb = load_settings(
        db_path=tmp_path / "portal_data.db", poll_enabled=False,
        dados_obras_dir=tmp_path / "DADOS-OBRAS", logs_dir=tmp_path / "logs",
        status_md_path=tmp_path / "STATUS.md", max_obra_mb=1,
    )
    client = ContadorFakeDrive(fake_raiz)
    membro = _membro(conn, "ana", "folder-ana")

    novas = varrer_uma_vez(conn, client, settings_1mb, membros=[membro])
    assert novas == []  # ignorado por tamanho (R6) — nunca baixado (checa st_size antes)
    assert client.download_calls == 0


def test_dwg_aceito_como_extensao_valida(conn, settings, tmp_path):
    """Só .dwg/.dxf passam o filtro de extensão. Um .dwg (que iria pra fila ODA) é aceito."""
    fake_raiz = tmp_path / "drive"
    pasta = fake_raiz / "folder-ana"
    pasta.mkdir(parents=True)
    # .dwg não é parseável por ezdxf aqui, mas o poller só filtra extensão/tamanho e
    # baixa; a validação estrutural é etapa posterior. Basta o poller aceitar a extensão.
    (pasta / "obra.dwg").write_bytes(b"AC1027 fake dwg header")
    client = ContadorFakeDrive(fake_raiz)
    membro = _membro(conn, "ana", "folder-ana")

    novas = varrer_uma_vez(conn, client, settings, membros=[membro])
    assert len(novas) == 1
    assert repo.obter_obra(conn, novas[0])["arquivo_nome"] == "obra.dwg"


# --------------------------------------------------------------------------- #
# §4.2 R8 — Drive indisponível: loga, reagenda, NUNCA propaga exceção
# --------------------------------------------------------------------------- #

def test_s8_1_erro_de_rede_nao_derruba(conn, settings, caplog):
    """varrer_uma_vez degrada por membro: exceção do client vira log + sync_state, não crash."""
    membro = _membro(conn, "ana", "folder-ana")
    client = DriveQuebrado(ConnectionError("503 Service Unavailable"))

    # não deve propagar exceção nenhuma
    novas = varrer_uma_vez(conn, client, settings, membros=[membro])
    assert novas == []

    # estado do poller marcado como indisponível para esse membro (reagendável)
    estado = repo.obter_sync_state(conn, membro["id"])
    assert estado is not None
    assert estado["ultimo_scan_status"] == "drive_indisponivel"


def test_s8_1b_erro_em_um_membro_nao_para_os_outros(conn, settings, tmp_path):
    """Degradação por membro (R8): Drive do bruno cai, mas a obra da ana ainda é ingerida."""
    fake_raiz = tmp_path / "drive"
    _dxf_valido(fake_raiz / "folder-ana" / "obra_ana.dxf")

    class ParcialmenteQuebrado(FakeDriveClient):
        def list_new_files(self, pasta_id):
            if pasta_id == "folder-bruno":
                raise TimeoutError("rede caiu para bruno")
            return super().list_new_files(pasta_id)

    client = ParcialmenteQuebrado(fake_raiz)
    ana = _membro(conn, "ana", "folder-ana")
    bruno = _membro(conn, "bruno", "folder-bruno")

    novas = varrer_uma_vez(conn, client, settings, membros=[ana, bruno])
    assert len(novas) == 1  # ana processou apesar de bruno falhar
    assert repo.obter_obra(conn, novas[0])["membro_id"] == ana["id"]
    # bruno ficou marcado como indisponível
    assert repo.obter_sync_state(conn, bruno["id"])["ultimo_scan_status"] == "drive_indisponivel"


def test_s8_4_recuperacao_transparente(conn, settings, tmp_path):
    """Poll #1 falha (R8); poll #2 com API de volta pega o que chegou — nada perdido."""
    fake_raiz = tmp_path / "drive"
    _dxf_valido(fake_raiz / "folder-ana" / "obra_x.dxf")
    membro = _membro(conn, "ana", "folder-ana")

    # poll #1: API fora do ar
    quebrado = DriveQuebrado(ConnectionError("503"))
    assert varrer_uma_vez(conn, quebrado, settings, membros=[membro]) == []

    # poll #2: API voltou -> detecta o arquivo que já estava lá
    ok = FakeDriveClient(fake_raiz)
    novas = varrer_uma_vez(conn, ok, settings, membros=[membro])
    assert len(novas) == 1


# --------------------------------------------------------------------------- #
# _varrer_ciclo — abre/fecha a própria conexão na thread (fix cross-thread)
# --------------------------------------------------------------------------- #

def test_varrer_ciclo_abre_propria_conexao(settings, tmp_path):
    """_varrer_ciclo não recebe conn: abre e fecha a sua dentro da própria thread.

    Regressão do bug cross-thread corrigido em 2026-07-05 (asyncio.to_thread + sqlite3).
    Aqui: pré-cadastra um membro no db, chama _varrer_ciclo (que abre a própria conexão),
    e confirma que a obra foi persistida — provando que a conexão interna funcionou.
    """
    from portal.db import connection

    fake_raiz = tmp_path / "drive"
    _dxf_valido(fake_raiz / "folder-ana" / "obra_x.dxf")

    c = connection.init_db(settings.db_path)
    repo.criar_membro(c, login="ana", nome="Ana", senha_hash="h", drive_folder_id="folder-ana")
    c.close()

    client = FakeDriveClient(fake_raiz)
    novas = drive_poller._varrer_ciclo(settings, client)
    assert len(novas) == 1

    # persistiu no db em disco (conexão interna commitou e fechou)
    c2 = connection.get_connection(settings.db_path)
    total = c2.execute("SELECT COUNT(*) FROM portal_obras").fetchone()[0]
    c2.close()
    assert total == 1


# --------------------------------------------------------------------------- #
# obter_ou_criar_pasta — criação dinâmica de pasta por membro (2026-07-06)
# --------------------------------------------------------------------------- #

def test_obter_ou_criar_pasta_idempotente(tmp_path):
    """2ª chamada com o mesmo (nome, pai) devolve o MESMO id — nunca duplica."""
    client = FakeDriveClient(tmp_path / "drive")

    raiz_id = client.obter_ou_criar_pasta("Portal-Obras")
    raiz_id_2 = client.obter_ou_criar_pasta("Portal-Obras")
    assert raiz_id == raiz_id_2

    membro_id_1 = client.obter_ou_criar_pasta("joao", pasta_pai_id=raiz_id)
    membro_id_2 = client.obter_ou_criar_pasta("joao", pasta_pai_id=raiz_id)
    assert membro_id_1 == membro_id_2
    assert membro_id_1 != raiz_id
    assert membro_id_1.startswith("Portal-Obras/")


def test_obter_ou_criar_pasta_nomes_diferentes_sob_mesmo_pai(tmp_path):
    """Dois membros sob o mesmo pai recebem pastas (ids) diferentes."""
    client = FakeDriveClient(tmp_path / "drive")
    raiz_id = client.obter_ou_criar_pasta("Portal-Obras")

    id_joao = client.obter_ou_criar_pasta("joao", pasta_pai_id=raiz_id)
    id_maria = client.obter_ou_criar_pasta("maria", pasta_pai_id=raiz_id)
    assert id_joao != id_maria
