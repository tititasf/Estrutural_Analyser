# -*- coding: utf-8 -*-
"""Testes da trava de instância única (scripts/arete/single_instance.py)."""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / 'scripts' / 'arete'))

from single_instance import acquire_lock, release_lock, wait_for_lock  # noqa: E402


def test_wait_adquire_quando_liberar(tmp_path):
    """--wait: subprocesso segura a trava por ~2s; wait_for_lock espera e adquire."""
    code = (
        "import sys, time; sys.path.insert(0, r'%s'); "
        "from single_instance import acquire_lock; "
        "h, e = acquire_lock('t_wait', r'%s'); "
        "assert h is not None; print('LOCKED', flush=True); time.sleep(2)"
        % (str(REPO_ROOT / 'scripts' / 'arete'), str(tmp_path))
    )
    proc = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == 'LOCKED'
        h, err = wait_for_lock('t_wait', tmp_path, poll_s=0.5, timeout_s=30.0)
        assert h is not None and err is None
        release_lock(h)
    finally:
        proc.kill()
        proc.wait()


def test_wait_timeout(tmp_path):
    h1, _ = acquire_lock('t_wait2', tmp_path)
    assert h1 is not None
    h2, err = wait_for_lock('t_wait2', tmp_path, poll_s=0.2, timeout_s=0.5)
    assert h2 is None and err
    release_lock(h1)


def test_segunda_instancia_bloqueada(tmp_path):
    h1, err1 = acquire_lock('t_lock', tmp_path)
    assert h1 is not None and err1 is None
    # Segundo handle (simula outro processo — locks de região do Windows
    # conflitam mesmo entre handles do mesmo processo)
    h2, err2 = acquire_lock('t_lock', tmp_path)
    assert h2 is None
    assert err2  # descreve o detentor (pid/início) ou fallback
    release_lock(h1)


def test_liberacao_permite_nova_aquisicao(tmp_path):
    h1, _ = acquire_lock('t_lock2', tmp_path)
    assert h1 is not None
    release_lock(h1)
    h2, err2 = acquire_lock('t_lock2', tmp_path)
    assert h2 is not None and err2 is None
    release_lock(h2)


def test_lock_sobrevive_entre_processos(tmp_path):
    """Prova real inter-processo: subprocesso segura a trava; pai não consegue."""
    code = (
        "import sys, time; sys.path.insert(0, r'%s'); "
        "from single_instance import acquire_lock; "
        "h, e = acquire_lock('t_lock3', r'%s'); "
        "assert h is not None; print('LOCKED', flush=True); time.sleep(4)"
        % (str(REPO_ROOT / 'scripts' / 'arete'), str(tmp_path))
    )
    proc = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == 'LOCKED'
        h, err = acquire_lock('t_lock3', tmp_path)
        assert h is None
        assert 'pid=' in (err or '')  # conseguiu ler o diagnóstico do detentor
    finally:
        proc.kill()
        proc.wait()
    # Após a morte do subprocesso, o SO libera a trava sozinho (anti-órfão)
    h2, err2 = acquire_lock('t_lock3', tmp_path)
    assert h2 is not None and err2 is None
    release_lock(h2)
