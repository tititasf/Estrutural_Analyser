from pathlib import Path

from src.core.cad_render_cache import render_worker_limit


def test_cache_de_pagina_inativo_nao_conta_como_memoria_em_uso(monkeypatch):
    gig = 1024**3
    service = '/sys/fs/cgroup/system.slice/cad-portal.service'
    content = {
        '/proc/meminfo': 'MemAvailable: 64000000 kB\n',
        '/proc/self/cgroup': '0::/system.slice/cad-portal.service\n',
        f'{service}/memory.max': str(5 * gig),
        f'{service}/memory.current': str(2 * gig),
        f'{service}/memory.stat': f'anon {gig}\nfile {gig}\ninactive_file {gig}\n',
        '/sys/fs/cgroup/system.slice/memory.max': 'max',
    }

    def read(path, *args, **kwargs):
        if path.as_posix() not in content:
            raise FileNotFoundError(str(path))
        return content[path.as_posix()]

    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr('os.sched_getaffinity', lambda _: set(range(8)), raising=False)
    # 5 GB max - (2 GB current - 1 GB inactive cache) = 4 GB spare -> 3 workers.
    assert render_worker_limit(8, 21) == 3
