#!/usr/bin/env python
"""PoC local: web (localhost) -> subprocess `claude -p` (OAuth do plano
mensal, SEM API key) -> QA agêntico Camada 1 de um item PIL real.

Objetivo desta rodada (2026-08-06, pedido do dono): provar a invocação
web -> CLI headless -> OAuth antes de decidir se isso vira job de verdade no
portal (rodando na VPS). Roda 100% local; não escreve em notes.json ainda —
só lê os docs + a ficha/pack do item e devolve o veredito em JSON, pra
conferir a resposta sem risco de mexer em dado real.

Por que `claude -p` (subprocess) e não o Agent SDK direto:
- O plano é assinatura mensal (OAuth), não billing por API key. `claude -p`
  em modo normal (NÃO --bare) lê a sessão OAuth já logada nesta máquina —
  validado abaixo, sem custo de API separado.
- Subprocess headless por item = processo leve e efêmero (sobe, responde,
  morre) — mais barato em memória que manter um SDK/processo Python com
  client Anthropic residente pra cada requisição.
- Ferramentas restritas a Read/Grep/Glob (sem Bash/Edit/Write) — a etapa
  atual é só leitura+veredito; quando formos persistir de verdade, o próprio
  agente chama `qa_pil_n1_contextual_pipeline.py write-agent` via Bash
  (mesmo CLI que a sessão humana já usa hoje — não muda a persistência).

Uso:
  py -3.12 scripts/arete/qa_agent_web_poc.py
  (sobe em http://127.0.0.1:8790)

  curl -X POST http://127.0.0.1:8790/qa/pilares/P9/camada1
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

# No Windows, "claude" resolve pra claude.CMD (shim do npm). subprocess sem
# shell=True não sabe executar .CMD por nome puro (WinError 2) — precisa do
# caminho já resolvido por shutil.which, aí funciona direto (testado, inclusive
# com prompt multi-linha) sem precisar de cmd /c nem shell=True.
CLAUDE_BIN = shutil.which("claude") or "claude"

ROOT = Path(__file__).resolve().parents[2]
PACK_DIR = ROOT / "scripts/arete/html_fichas/Obra_TREINO_1/13_PAV_20260804_155556_pilares_abcd"

DOCS_CONTEXTO = [
    "docs/LOOPING-AGENTICO-INTERPRETACAO-PILARES-ABCD.md",
    "docs/PROCEDIMENTO-QA-PIL-N1-CONTEXTUAL.md",
    "docs/INTERPRETACAO-PILARES-ABCD.md",
    "docs/PADRAO-TAGS-DESTAQUE-AGENTICO-PIL.md",
]

app = FastAPI(title="QA Agêntico PIL — PoC local (não usar em produção)")


def montar_prompt(item: str) -> str:
    ficha = PACK_DIR / "pilares" / f"{item}.html"
    notes = PACK_DIR / "pilares" / f"{item}.notes.json"
    docs_lista = "\n".join(f"- {d}" for d in DOCS_CONTEXTO)
    return (
        f"Você é o revisor agêntico Camada 1 do QA de interpretação PIL (SA/N1), item {item}.\n"
        f"Leia primeiro estes docs de contexto (nessa ordem):\n{docs_lista}\n\n"
        f"As notas já registradas (se existirem): {notes.relative_to(ROOT)} — leia com Read normal, é pequeno.\n\n"
        f"A ficha do item ({ficha.relative_to(ROOT)}) é um HTML gigante (centenas de milhares de "
        "linhas, tem SVG embutido) — NÃO use Read nela direto, vai estourar limite de tamanho. "
        "Em vez disso use Grep nesse arquivo procurando por "
        '\'data-ficha-panel="interp"\' e leia só o trecho ao redor (a tabela ABCD de 4 faces já '
        "vem inteira numa única linha logo depois desse marcador).\n\n"
        "Produza um veredito (validou ou invalidou) sobre a interpretação ABCD atual "
        "do SA para este pilar, com justificativa curta (2-4 linhas), seguindo o método "
        "de evidência do procedimento. Responda em JSON puro, sem texto ao redor: "
        '{"item": "...", "verdict": "validou|invalidou", "nota": "..."}. '
        "NÃO grave nada em disco — esta rodada é só leitura, pra eu conferir a resposta."
    )


def invocar_claude(prompt: str, timeout_s: int = 300) -> dict:
    # [achado ao vivo] uma rodada real (4 docs de contexto + grep na ficha +
    # notas + raciocínio) levou 14 turnos e ~125s no teste direto via
    # terminal — timeout curto corta no meio de um turno legítimo, não de um
    # travamento de verdade (memória do processo parada não é sinal de hang
    # aqui, só significa "pensando/chamando ferramenta").
    cmd = [
        CLAUDE_BIN, "-p", prompt,
        "--output-format", "json",
        "--model", "sonnet",
        # [achado ao vivo] --allowedTools só afeta prompt de permissão pra
        # ferramentas que JÁ estão disponíveis — não remove o resto do
        # toolset. Rodada anterior com só --allowedTools tentou bater em
        # localhost:8790/pilares/*.html e /api/notes/* (provavelmente via
        # WebFetch, inferido do PROCEDIMENTO-QA-PIL-N1-CONTEXTUAL.md) e
        # travou 5min. --tools de fato restringe o conjunto disponível.
        "--tools", "Read", "Grep", "Glob",
        "--permission-mode", "bypassPermissions",
        "--no-session-persistence",
    ]
    t0 = time.time()
    proc = subprocess.run(
        cmd, cwd=str(ROOT), capture_output=True, text=True,
        timeout=timeout_s, encoding="utf-8",
        # sem isso, se o CLI tentar pedir confirmação por stdin ele fica
        # esperando pra sempre (stdin herdado do uvicorn não é um TTY de
        # verdade) — DEVNULL força falha rápida em vez de travar o processo.
        stdin=subprocess.DEVNULL,
    )
    dt = time.time() - t0
    print(
        f"[qa-poc] fim em {dt:.1f}s · returncode={proc.returncode} · "
        f"stdout={len(proc.stdout)}b · stderr={len(proc.stderr)}b",
        flush=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI falhou (code {proc.returncode}): {proc.stderr[:2000]}")
    if not proc.stdout.strip():
        raise RuntimeError(f"claude CLI voltou com stdout vazio (returncode 0). stderr: {proc.stderr[:2000]!r}")
    payload = json.loads(proc.stdout)
    payload["_invocacao_local_s"] = round(dt, 2)
    return payload


@app.post("/qa/pilares/{item}/camada1")
def qa_camada1(item: str):
    ficha = PACK_DIR / "pilares" / f"{item}.html"
    if not ficha.is_file():
        raise HTTPException(404, f"item {item} não encontrado no pack de teste (13_PAV pilares_abcd)")
    prompt = montar_prompt(item)
    try:
        resultado = invocar_claude(prompt)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "claude CLI não respondeu a tempo")
    except Exception as exc:  # noqa: BLE001 — PoC: qualquer falha vira 500 legível
        raise HTTPException(500, str(exc))
    return JSONResponse({
        "item": item,
        "resposta_agente": resultado.get("result"),
        "custo_estimado_usd": resultado.get("total_cost_usd"),
        "duracao_api_ms": resultado.get("duration_ms"),
        "duracao_invocacao_local_s": resultado.get("_invocacao_local_s"),
        "num_turns": resultado.get("num_turns"),
        "session_id": resultado.get("session_id"),
    })


@app.get("/")
def home():
    return {
        "ok": True,
        "uso": "POST /qa/pilares/{item}/camada1 — ex.: P9, P1, P11, P32 (13_PAV pilares_abcd)",
        "aviso": "PoC local — não escreve em disco, só lê e devolve o veredito do agente.",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8790, log_level="info")
