"""Isolated local portal for browser verification; no production DB or credentials."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from portal.app.config import load_settings
from portal.app.main import create_app
from portal.app import auth
from portal.db import connection, repository
import uvicorn

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='cad_frame_ui_') as folder:
        root = Path(folder)
        os.environ['ARETE_DRAWING_MODE_CONFIG'] = str(root / 'drawing.json')
        settings = load_settings(db_path=root/'portal.db', poll_enabled=False,
            auto_publish_enabled=False, headless_enabled=False, dados_obras_dir=root/'obras',
            logs_dir=root/'logs', status_md_path=root/'status.md', drive_oauth_json=root/'no-oauth.json',
            drive_sa_json=root/'no-sa.json', sa_db_path=root/'sa.vision', public_consulta_db_path=root/'public.db')
        conn = connection.init_db(settings.db_path)
        repository.criar_membro(conn, login='frame-test', nome='Verificação local', papel='dono',
                                senha_hash=auth.hash_senha('frame-test-only'))
        conn.close()
        uvicorn.run(create_app(settings), host='127.0.0.1', port=23186)
