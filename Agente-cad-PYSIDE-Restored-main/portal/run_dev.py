"""Launcher de desenvolvimento do portal — liga o poller do Drive e sobe o uvicorn.

Uso: python portal/run_dev.py  (funciona de qualquer cwd — ajusta path/cwd sozinho,
pra rodar de dentro do preview tool que nao garante cwd = raiz do repo).

SA/headless SEMPRE roda em Python 3.12 (pipeline_runner.python_sa_executable),
mesmo se o portal subir com outra versão. Preferível: py -3.12 portal/run_dev.py
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("PORTAL_POLL_ENABLED", "true")
os.environ.setdefault("PORTAL_POLL_INTERVAL_S", "30")  # mais rapido pra teste manual

# Avisa se o portal não está em 3.12 (o SA ainda usa 3.12 dedicado, mas o
# resto do portal fica mais previsível no mesmo runtime do projeto).
if sys.version_info[:2] != (3, 12):
    print(
        f"[portal] AVISO: rodando em Python {sys.version.split()[0]} ({sys.executable}). "
        "O SA será disparado com Python 3.12 dedicado. "
        "Preferível: py -3.12 portal/run_dev.py",
        file=sys.stderr,
    )

import uvicorn

if __name__ == "__main__":
    uvicorn.run("portal.app.main:app", host="127.0.0.1", port=21380, log_level="info")
