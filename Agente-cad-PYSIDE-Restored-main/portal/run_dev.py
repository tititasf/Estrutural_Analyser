"""Launcher de desenvolvimento do portal — liga o poller do Drive e sobe o uvicorn.

Uso: python portal/run_dev.py  (funciona de qualquer cwd — ajusta path/cwd sozinho,
pra rodar de dentro do preview tool que nao garante cwd = raiz do repo).
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("PORTAL_POLL_ENABLED", "true")
os.environ.setdefault("PORTAL_POLL_INTERVAL_S", "30")  # mais rapido pra teste manual

import uvicorn

if __name__ == "__main__":
    uvicorn.run("portal.app.main:app", host="127.0.0.1", port=21380, log_level="info")
