#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""single_instance.py — trava de instância única via lock exclusivo de arquivo.

Motivação: coordenar processos pesados por recurso. O headless SA usa uma
fila por classe em microciclos read-only e global + quatro classes em rodadas
completas/multiclasse/persistentes. O mecanismo continua genérico por `name`.

Mecanismo: lock exclusivo de 1 byte no arquivo `.{name}.lock`
(`msvcrt.locking` no Windows, `fcntl.flock` em POSIX). O SO libera o lock
quando o processo termina — INCLUSIVE em crash/kill — portanto nunca existe
lock órfão e não há PID-file para limpar à mão.

Uso:
    from single_instance import acquire_lock
    lock, holder = acquire_lock('headless_sa_pil')
    if lock is None:
        print(f'já em execução: {holder}'); sys.exit(2)
    # ... manter `lock` vivo até o fim do processo ...

O byte 0 é o byte travado; a informação de diagnóstico (pid/início/argv) é
gravada a partir do byte 1, para que a segunda instância consiga LER quem
detém a trava (leitura não toca o byte travado).
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import IO


_STARTED_AT_BY_HANDLE: dict[int, str] = {}
_PID_RE = re.compile(r"(?:^|\s)pid=(\d+)(?:\s|$)")


def _lock_file_path(name: str, lock_dir: str | Path | None) -> Path:
    base = Path(lock_dir) if lock_dir else Path(__file__).resolve().parent
    return base / f'.{name}.lock'


def _write_status(fh: IO, *, event: str) -> None:
    """Atualiza telemetria sem tocar no byte 0 que o SO bloqueia.

    A exclusão continua sendo exclusivamente do SO. Este registro só deixa a
    fila informar se o dono ainda está em execução; nunca autoriza apagar ou
    quebrar uma trava.
    """
    now = datetime.now().isoformat(timespec='seconds')
    started_at = _STARTED_AT_BY_HANDLE.get(id(fh), now)
    payload = (
        f'pid={os.getpid()} inicio={started_at} heartbeat={now} '
        f'event={event} cmd={" ".join(sys.argv[:8])}\n'
    )
    try:
        fh.seek(1)
        fh.truncate()
        fh.write(payload)
        fh.flush()
    except OSError:
        pass


def _pid_is_alive(pid: int) -> bool | None:
    """Informa se o PID local existe, sem usar isso para quebrar locks."""
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [
                ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32,
            ]
            kernel32.OpenProcess.restype = ctypes.c_void_p
            handle = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if not handle:
                # ERROR_INVALID_PARAMETER = PID nao existe. Acesso negado e
                # demais falhas continuam desconhecidas e nunca liberam lock.
                if ctypes.get_last_error() == 87:
                    return False
                return None
            try:
                exit_code = ctypes.c_ulong()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return None
                return exit_code.value == 259  # STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return None
    except OSError:
        return None


def describe_holder(holder: str | None) -> str:
    """Anota liveness do metadado sem confundi-lo com a trava real."""
    text = str(holder or "").strip()
    if not text:
        return "instancia ativa (detalhes indisponiveis)"
    match = _PID_RE.search(text)
    if not match:
        return text
    alive = _pid_is_alive(int(match.group(1)))
    if alive is True:
        suffix = "telemetria=processo-vivo"
    elif alive is False:
        suffix = "telemetria-antiga; lock do SO continua sendo a autoridade"
    else:
        suffix = "telemetria=liveness-indisponivel"
    return f"{text} {suffix}"


def refresh_lock(fh: IO, *, event: str = 'running') -> None:
    """Registra progresso do dono sem modificar a trava exclusiva."""
    _write_status(fh, event=event)


def acquire_lock(name: str, lock_dir: str | Path | None = None) -> tuple[IO | None, str | None]:
    """Tenta adquirir a trava `name`.

    Retorna `(handle, None)` em sucesso — o chamador DEVE manter o handle
    vivo até o fim do processo (fechá-lo libera a trava) — ou
    `(None, info)` se outra instância já a detém, onde `info` descreve o
    detentor (pid/início/argv) quando legível.
    """
    lock_path = _lock_file_path(name, lock_dir)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, 'a+', encoding='utf-8', errors='replace')
    try:
        fh.seek(0)
        if sys.platform == 'win32':
            import msvcrt
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        info = ''
        try:
            # Diagnóstico do detentor está a partir do byte 1 (byte 0 = travado)
            fh.seek(1)
            info = fh.read().strip()
        except OSError:
            info = ''
        fh.close()
        return None, describe_holder(info)

    # Trava adquirida — registrar quem somos, a partir do byte 1.
    try:
        fh.seek(0)
        fh.truncate()
        fh.write('\n')  # byte 0 (travado) — placeholder
        _STARTED_AT_BY_HANDLE[id(fh)] = datetime.now().isoformat(timespec='seconds')
        _write_status(fh, event='acquired')
    except OSError:
        pass  # a trava vale mesmo sem o diagnóstico gravado
    return fh, None


def wait_for_lock(
    name: str,
    lock_dir: str | Path | None = None,
    poll_s: float = 10.0,
    timeout_s: float | None = None,
) -> tuple[IO | None, str | None]:
    """Como `acquire_lock`, mas AGUARDA a trava vagar (poll a cada `poll_s`).

    Pensado para agentes/CLIs: em vez de abortar e depender de retry manual,
    o processo espera enquanto o dono real mantiver a trava. Por padrão não
    há relógio artificial; passe ``timeout_s`` só para desistência explícita.
    Retorna `(handle, None)` quando adquirir, ou `(None, info)` se
    `timeout_s` estourar (info = detentor na última checagem).
    """
    import time
    inicio = time.monotonic()
    aviso_dado = False
    ultimo_aviso = 0.0
    while True:
        fh, holder = acquire_lock(name, lock_dir)
        if fh is not None:
            if aviso_dado:
                print(f'[lock:{name}] Trava liberada — prosseguindo.', flush=True)
            return fh, None
        if not aviso_dado:
            print(f'[lock:{name}] Ocupada por: {holder}', flush=True)
            print(f'[lock:{name}] Aguardando liberação (poll {poll_s:.0f}s'
                  + (f', timeout {timeout_s/60:.0f}min' if timeout_s else '')
                  + ')... NÃO finalize o processo detentor.', flush=True)
            aviso_dado = True
            ultimo_aviso = inicio
        elif time.monotonic() - ultimo_aviso >= max(30.0, poll_s * 3):
            elapsed = int(time.monotonic() - inicio)
            print(f'[lock:{name}] Ainda aguardando o dono real ({elapsed}s): {holder}',
                  flush=True)
            ultimo_aviso = time.monotonic()
        if timeout_s is not None and (time.monotonic() - inicio) >= timeout_s:
            return None, holder
        time.sleep(poll_s)


def release_lock(fh: IO) -> None:
    """Libera explicitamente (opcional — fechar o handle ou terminar o
    processo tem o mesmo efeito)."""
    if getattr(fh, 'closed', False):
        _STARTED_AT_BY_HANDLE.pop(id(fh), None)
        return
    # Mantemos o inode porque waiters ja podem te-lo aberto; a ultima
    # telemetria deixa claro que a liberacao foi limpa. Em crash o byte e'
    # solto pelo SO e metadado antigo jamais autoriza quebrar a exclusao.
    _write_status(fh, event='released')
    try:
        if sys.platform == 'win32':
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except (OSError, ValueError):
        pass
    try:
        fh.close()
    except (OSError, ValueError):
        pass
    _STARTED_AT_BY_HANDLE.pop(id(fh), None)
