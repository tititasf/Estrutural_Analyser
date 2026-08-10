#!/usr/bin/env python3
"""Reproduz no Linux o teste que TRAVAVA no Windows.

Contexto (2026-08-07): no Windows, `claude -p` chamado via subprocess.run()
de dentro de um worker FastAPI travava indefinidamente em tarefas longas
(multi-turno) — processos node.exe ficavam vivos segurando o pipe de saída,
e nem o timeout do Python destravava. Tarefas triviais (1 turno) funcionavam
normalmente. Suspeita: herança de handle de pipe, específica do CreateProcess
do Windows.

Este script roda os DOIS casos no Linux para confirmar ou descartar.

Uso (no servidor, após `claude setup-token`):
    python3 /opt/cad-analyzer/teste_subprocess_linux.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time

CLAUDE = shutil.which("claude") or "claude"
CWD = "/opt/cad-analyzer"
PACK = "scripts/arete/html_fichas/Obra_TREINO_1/13_PAV_20260804_155556_pilares_abcd/pilares"

PROMPT_QA = f"""Voce e o revisor agentico Camada 1 do QA de interpretacao PIL (SA/N1), item P9.

Leia estes docs de contexto:
- docs/LOOPING-AGENTICO-INTERPRETACAO-PILARES-ABCD.md
- docs/PROCEDIMENTO-QA-PIL-N1-CONTEXTUAL.md
- docs/INTERPRETACAO-PILARES-ABCD.md
- docs/PADRAO-TAGS-DESTAQUE-AGENTICO-PIL.md

Notas ja registradas: {PACK}/P9.notes.json (arquivo pequeno, use Read normal).

A ficha {PACK}/P9.html e um HTML gigante (280 mil linhas, SVG embutido) —
NAO use Read direto nela. Use Grep procurando por data-ficha-panel="interp"
e leia so o trecho ao redor.

Produza um veredito (validou ou invalidou) sobre a interpretacao ABCD atual do
SA para este pilar, com justificativa curta (2-4 linhas). Responda em JSON puro,
sem texto ao redor. NAO grave nada em disco — esta rodada e so leitura."""


def rodar(nome: str, prompt: str, timeout: int) -> str | None:
    print(f"--- {nome} (timeout {timeout}s) ---", flush=True)
    t0 = time.time()
    try:
        proc = subprocess.run(
            [
                CLAUDE, "-p", prompt,
                "--output-format", "json",
                "--model", "sonnet",
                # --tools (nao --allowedTools) e o que de fato restringe o
                # toolset; com so --allowedTools o agente tentava WebFetch.
                "--tools", "Read", "Grep", "Glob",
                # Claude bloqueia bypassPermissions quando e' executado como
                # root. A rodada e' estritamente de leitura (tools acima),
                # portanto acceptEdits nao concede acoes extras relevantes.
                "--permission-mode", "acceptEdits",
                "--no-session-persistence",
            ],
            cwd=CWD,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        dt = time.time() - t0
        print(f"  OK  {dt:.1f}s  rc={proc.returncode}  stdout={len(proc.stdout)}b")
        if proc.returncode != 0:
            print(f"  stderr: {proc.stderr[:400]}")
            return None
        return proc.stdout
    except subprocess.TimeoutExpired:
        dt = time.time() - t0
        print(f"  TRAVOU apos {dt:.0f}s — mesmo sintoma do Windows")
        return None


def main() -> int:
    print("=== 1) tarefa TRIVIAL (funcionava no Windows) ===")
    rodar("trivial", "responda apenas com a palavra: ok", 90)
    print()

    print("=== 2) tarefa LONGA multi-turno (TRAVAVA no Windows) ===")
    saida = rodar("QA Camada 1 do P9", PROMPT_QA, 300)
    if not saida:
        print("\nVEREDITO: o problema TAMBEM ocorre no Linux — nao era do Windows.")
        return 1

    try:
        dados = json.loads(saida)
    except json.JSONDecodeError as exc:
        print(f"falha ao parsear json: {exc}")
        return 1

    print("\nRESPOSTA DO AGENTE:")
    print((dados.get("result") or "")[:1500])
    print()
    print(
        f"turnos={dados.get('num_turns')} "
        f"custo_estimado_usd={dados.get('total_cost_usd')} "
        f"web_fetch={dados.get('usage', {}).get('server_tool_use', {}).get('web_fetch_requests')}"
    )
    print("\nVEREDITO: funcionou no Linux — o travamento era especifico do Windows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
