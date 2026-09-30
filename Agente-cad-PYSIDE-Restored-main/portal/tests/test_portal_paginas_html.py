"""GET real nas 4 páginas HTML server-rendered (login, lista, detalhe, status).

Achado 2026-07-06: as 4 rotas de página (`portal/app/routers/paginas_routes.py`)
chamavam `TemplateResponse(request, nome, ctx)` — convenção que a versão instalada
de `starlette` (0.27.0) NÃO aceita (assinatura real: `TemplateResponse(name, context)`,
sem `request` posicional). Toda página quebrava com `ValueError: context must
include a "request" key` no primeiro acesso via navegador. NENHUM teste anterior
tinha feito um GET real numa página HTML (só nas rotas JSON) — corrigido com um
helper `_render()` centralizado; este arquivo garante que as 4 páginas continuam
renderizando de verdade, não só que "não dá erro de import".
"""

from __future__ import annotations

import contextlib
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from portal.app import auth
from portal.app.main import create_app
from portal.db import connection, repository as repo

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONSULTA_PUBLICA_DIR = _REPO_ROOT / "consulta-publica-api"
if str(_CONSULTA_PUBLICA_DIR) not in sys.path:
    sys.path.insert(0, str(_CONSULTA_PUBLICA_DIR))


def _publicar_obra_fake(db_path: Path, *, obra_id: str, code: str) -> None:
    schema = (_CONSULTA_PUBLICA_DIR / "publisher" / "schema.sql").read_text(encoding="utf-8")
    conn = sqlite3.connect(str(db_path))
    conn.executescript(schema)
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, obra_rotulo, revoked) "
        "VALUES (?, 'obra', ?, '/fake', 'Edificio Aurora', 0)",
        (code, obra_id),
    )
    conn.commit()
    conn.close()


@contextlib.asynccontextmanager
async def _app_cliente(settings):
    c = connection.init_db(settings.db_path)
    repo.criar_membro(
        c, login="ana", nome="Ana Silva",
        senha_hash=auth.hash_senha("segredo123"), drive_folder_id="folder-ana",
    )
    c.close()

    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield app, client


@pytest.mark.asyncio
async def test_pagina_login_renderiza(settings):
    async with _app_cliente(settings) as (_app, client):
        r = await client.get("/login")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "<form" in r.text  # formulário de login real, não stack trace
        assert "manter-conectado" in r.text


@pytest.mark.asyncio
async def test_pagina_obras_vazia_renderiza(settings):
    async with _app_cliente(settings) as (_app, client):
        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get("/app/obras")
        assert r.status_code == 200
        assert "Lista de Obras" in r.text
        assert "Processar Obra Completa" in r.text  # passo 2 do wizard (2026-08)
        assert "Processar 1 Pavimento" in r.text
        assert "Exibir Lista de Obras" in r.text


@pytest.mark.asyncio
async def test_pagina_obras_com_dados_renderiza(settings):
    async with _app_cliente(settings) as (_app, client):
        c = connection.init_db(settings.db_path)  # ana já seedada por _app_cliente
        ana = repo.obter_membro_por_login(c, "ana")
        obra_id = repo.criar_obra(
            c, membro_id=ana["id"], nome="EdificioAurora", pasta_drive_id="folder-ana",
            arquivo_hash="hash-pagina-1", estado="pronta",
        )
        c.close()

        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get("/app/obras")
        assert r.status_code == 200
        assert "EdificioAurora" in r.text
        assert f'/app/obras/{obra_id}' in r.text  # link real para o detalhe


@pytest.mark.asyncio
async def test_pagina_obras_mostra_codigo_publico_quando_ja_publicada(settings):
    """[2026-07-13] Harmonização — a lista de obras mostra o código público
    (App de Consulta) de cada obra já sincronizada, sem precisar abrir o
    detalhe. Obra sem código ainda (não publicada) não quebra a página."""
    async with _app_cliente(settings) as (_app, client):
        c = connection.init_db(settings.db_path)
        ana = repo.obter_membro_por_login(c, "ana")
        obra_com_code = repo.criar_obra(
            c, membro_id=ana["id"], nome="EdificioAurora", pasta_drive_id="folder-ana",
            arquivo_hash="hash-pagina-1", estado="pronta",
        )
        obra_sem_code = repo.criar_obra(
            c, membro_id=ana["id"], nome="TorreSemCodigo", pasta_drive_id="folder-ana",
            arquivo_hash="hash-pagina-2", estado="pronta",
        )
        c.close()

        _publicar_obra_fake(settings.public_consulta_db_path, obra_id=obra_com_code, code="OBRAABCD01")

        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get("/app/obras")
        assert r.status_code == 200
        assert "OBRAABCD01" in r.text
        assert "TorreSemCodigo" in r.text  # renderiza normal, sem quebrar por falta de código


@pytest.mark.asyncio
async def test_pagina_obra_detalhe_renderiza(settings, tmp_path):
    async with _app_cliente(settings) as (_app, client):
        c = connection.init_db(settings.db_path)
        ana = repo.obter_membro_por_login(c, "ana")
        obra_id = repo.criar_obra(
            c, membro_id=ana["id"], nome="TorreCentral", pasta_drive_id="folder-ana",
            arquivo_hash="hash-pagina-2", estado="aguardando_ingestao",
        )
        c.close()

        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/app/obras/{obra_id}")
        assert r.status_code == 200
        assert "TorreCentral" in r.text
        assert 'id="docs-upload-pavimento-padrao"' not in r.text
        scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", r.text, re.DOTALL)
        script = max(scripts, key=len)
        assert 'class="doc-pavimento-sel"' in script
        assert 'Criar e associar' in script
        assert "nomes.push('TIPO')" in script
        script_path = tmp_path / "obra_detalhe.js"
        script_path.write_text(script, encoding="utf-8")
        checked = subprocess.run(["node", "--check", str(script_path)], capture_output=True, text=True)
        assert checked.returncode == 0, checked.stderr


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arquivo_nome", "formato", "texto_fluxo"),
    [
        ("Torre-14P.dwg", "dwg", "Converter DWG → DXF"),
        ("Torre-14P.dxf", "dxf", "Conversão dispensada"),
    ],
)
async def test_onboarding_upload_rapido_mantem_lista_documentos(
    settings, arquivo_nome, formato, texto_fluxo,
):
    """O modo de 1 pavimento usa a mesma ficha progressiva de uma obra completa."""
    async with _app_cliente(settings) as (_app, client):
        c = connection.init_db(settings.db_path)
        ana = repo.obter_membro_por_login(c, "ana")
        obra_dir = settings.dados_obras_dir / "ana" / "torre-14p"
        entrada = obra_dir / "entrada"
        entrada.mkdir(parents=True)
        arquivo = entrada / arquivo_nome
        arquivo.write_bytes(b"cad-teste")
        obra_id = repo.criar_obra(
            c, membro_id=ana["id"], nome="Torre-14P", pasta_drive_id="folder-ana/torre",
            arquivo_hash=f"hash-onboarding-{formato}", estado="aguardando_ingestao",
            local_path=str(obra_dir),
        )
        repo.criar_documento(
            c, obra_id=obra_id, arquivo_nome=arquivo_nome,
            arquivo_hash=f"hash-doc-{formato}", local_path=str(arquivo),
            tipo_documento_sugerido="Bruto", tipo_documento_confirmado="Bruto",
            status="pendente",
        )
        c.close()

        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/app/obras/{obra_id}?onboarding=1&novo=1")
        assert r.status_code == 200
        assert "Revise o nome e siga o processamento" in r.text
        assert texto_fluxo in r.text
        assert "Documentos da obra" in r.text
        assert arquivo_nome in r.text
        assert 'data-auto-edit="1"' in r.text
        assert f'data-formato="{formato}"' in r.text


@pytest.mark.asyncio
async def test_paginas_sem_sessao_redirecionam_para_login(settings):
    async with _app_cliente(settings) as (_app, client):
        for path in ("/app/obras", "/app/status"):
            r = await client.get(path, follow_redirects=False)
            assert r.status_code == 303, f"{path} deveria redirecionar sem sessão"
            assert r.headers["location"] == "/login"


# --------------------------------------------------------------------------- #
# Regressão 2026-07-06 — `_etapa_atual` pulava Recortes/SA quando SÓ a triagem
# tinha rodado, porque TODO job bem-sucedido (mesmo triagem sozinha) marcava a
# obra "pronta" — achado testando de verdade o modo rápido (obra do usuário:
# "nao pula o recorte... o pavimento rapido deve ter essa fase tambem").
# --------------------------------------------------------------------------- #

def test_etapa_atual_usa_etapa_concluida_nao_so_estado():
    from portal.app.routers.paginas_routes import _etapa_atual

    # nada rodou ainda -> etapa 1 (Triagem)
    assert _etapa_atual({"estado": "aguardando_ingestao", "etapa_concluida": None}, [], []) == 1
    # so' a triagem terminou -> etapa 2 (Recortes) — NAO pula pra Validação
    assert _etapa_atual({"estado": "processando", "etapa_concluida": "triagem"}, [], []) == 2
    # recortes tambem terminou -> etapa 3 (SA) — ainda nao e' "pronta"
    assert _etapa_atual({"estado": "processando", "etapa_concluida": "recortes"}, [], []) == 3
    # SA terminou -> etapa 4 (Validação)
    assert _etapa_atual({"estado": "pronta", "etapa_concluida": "sa"}, [], []) == 4
    # erro tentando recortes (triagem ja tinha passado) -> continua mostrando
    # a etapa que falhou (2), nao reseta pra 1
    assert _etapa_atual({"estado": "erro", "etapa_concluida": "triagem"}, [], []) == 2
    # release N5 sempre manda pra etapa 5,
    # independente do que etapa_concluida diga
    assert _etapa_atual({"estado": "pronta", "etapa_concluida": "sa"}, [], [{"id": "r1"}]) == 5


@pytest.mark.asyncio
async def test_pagina_obra_detalhe_nao_pula_recortes_apos_so_triagem(settings):
    """Reproduz de verdade o bug: roda 1 job de triagem (via processar_um_job,
    o mesmo caminho do worker real) e confirma que a PÁGINA mostra "Recortes"
    como próxima etapa — não "Validação" (que exigiria SA já ter rodado)."""
    from portal.app import jobs as jobs_mod

    async with _app_cliente(settings) as (_app, client):
        c = connection.init_db(settings.db_path)
        ana = repo.obter_membro_por_login(c, "ana")
        obra_id = repo.criar_obra(
            c, membro_id=ana["id"], nome="ObraSoTriagem", pasta_drive_id="folder-ana",
            arquivo_hash="hash-so-triagem", estado="aguardando_ingestao",
        )
        doc_id = repo.criar_documento(
            c, obra_id=obra_id, arquivo_nome="14P.dxf",
            classe_sugerida="PIL", pavimento_sugerido="14_PAV", status="pendente",
        )
        job_id = repo.enfileirar_job(c, obra_id=obra_id)
        job = repo.consumir_job(c)
        assert job["id"] == job_id

        class _AppStateFake:
            def __init__(self, settings_obj, conn_obj):
                self.settings = settings_obj
                self.db = conn_obj
                self.job_meta = {job_id: {"etapa": "triagem"}}

        import unittest.mock as mock
        with mock.patch.object(
            jobs_mod.pipeline_runner, "executar_triagem_documentos",
            return_value=type("R", (), {
                "ok": True, "log_tail": "",
                "artefatos": {"documentos": [{
                    "doc_id": doc_id, "ok": True,
                    "dxf_path": "14P.dxf", "erro_msg": None,
                }]},
            })(),
        ), mock.patch.object(jobs_mod, "wait_for_lock", return_value=(object(), None)), \
           mock.patch.object(jobs_mod, "release_lock", lambda *a, **k: None):
            jobs_mod.processar_um_job(_AppStateFake(settings, c), job)

        obra_depois = repo.obter_obra(c, obra_id)
        assert obra_depois["etapa_concluida"] == "triagem"
        assert obra_depois["estado"] != "pronta"  # NAO pode marcar pronta so' com triagem

        # [novo 2026-07-08, a pedido do dono] a triagem agora encadeia recortes
        # automaticamente (jobs.py, apos triagem terminar com sucesso) — sem
        # o usuario precisar clicar num botao separado. Confirma que o job de
        # recortes foi enfileirado de verdade pra essa obra.
        jobs_da_obra = repo.listar_jobs_por_obra(c, obra_id)
        assert any(j["id"] != job_id for j in jobs_da_obra), (
            "esperava um job de recortes encadeado apos a triagem"
        )
        c.close()

        await client.post("/login", json={"login": "ana", "senha": "segredo123"})
        r = await client.get(f"/app/obras/{obra_id}")
        assert r.status_code == 200
        # [FIX 2026-07-06] navegação nunca mais bloqueia — a etapa_concluida
        # real é o que importa (ja verificado acima), nao a presenca de um
        # botao especifico. [ATUALIZADO 2026-07-08] o botão "Rodar recortes"
        # isolado foi eliminado a pedido do dono — recortes agora roda
        # encadeado automaticamente logo após a Triagem (botão único "Triagem
        # + Recortes"); a seção "Recortes" continua sempre visível/informativa.
        # O job de recortes encadeado ainda está "na_fila" (o teste não roda o
        # JobWorker de verdade) — job_ativo fica true e os botões mostram
        # "Job em andamento…" em vez do texto normal, comportamento esperado.
        assert "Recortes" in r.text
        # [2026-07-30] Era `"Job em andamento" in r.text`. O template nunca
        # imprimiu esse literal: ele mostra "Rodando a triagem/os recortes/a
        # Análise Estrutural (SA)" conforme a etapa. A intenção do teste segue
        # valendo — job na fila tem de renderizar o painel de progresso — mas a
        # asserção agora ancora na ESTRUTURA (a seção e o status vivo), não na
        # redação, que muda sem quebrar comportamento.
        assert 'class="job-panel"' in r.text
        assert 'id="job-estado"' in r.text
        assert "Rodando" in r.text
        # Recortes ainda nao terminaram -> a pagina INFORMA sem bloquear.
        # [2026-07-30] Era `"recortes ainda não terminaram" in r.text`. Esse
        # aviso em prosa nao existe mais: a pagina foi redesenhada em painel de
        # fases, e a pendencia aparece como estado da "Fase 2: Aprovação
        # Recortes" (icone de espera em vez de check). A garantia que importa —
        # a secao continua visivel e marcada como nao concluida — segue testada.
        assert 'id="fase2-icon"' in r.text
        assert "Aprovação Recortes" in r.text
        posicao = r.text.index('id="fase2-icon"')
        assert "⏳" in r.text[posicao:posicao + 120], "Fase 2 deveria estar pendente"
