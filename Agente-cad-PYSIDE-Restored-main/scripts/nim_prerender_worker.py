#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nim_prerender_worker.py — Daemon de pré-renderização de DXFs para PNG.

Varre DADOS-OBRAS/*/Fase-6_Execucao_CAD/ em busca de DXFs gerados
(PL/LV/FV/LJ_stog_quality.dxf) e seus pares STOG do dxf_discovery.json,
renderiza ambos para PNG e salva em validacao_visual/{obra}/{pav}/.

O validar_visual_dxf.py detecta PNGs pré-renderizados e pula o render caro.

PM2:
  {
    name: 'nim-prerender',
    script: 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts/nim_prerender_worker.py',
    interpreter: 'C:/Python314/python.exe',
    cwd: 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main',
    autorestart: true,
    watch: false,
  }

Uso:
  python scripts/nim_prerender_worker.py              # loop contínuo (60s sleep)
  python scripts/nim_prerender_worker.py --once       # rodar uma vez e sair
  python scripts/nim_prerender_worker.py --obra Obra_TREINO_20
"""

import sys, io, builtins as _builtins

# Force unbuffered output so logs appear immediately when redirected to file
_orig_print = _builtins.print
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    _orig_print(*args, **kwargs)

# Encoding setup: rely on PYTHONIOENCODING=utf-8 env var (set by caller).
# Only reconfigure if the stream is open and writable (avoids ValueError on
# Windows when stderr is closed/redirected at process startup).
for _stream in (sys.stdout, sys.stderr):
    try:
        if _stream and not _stream.closed and hasattr(_stream, 'reconfigure'):
            _stream.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── Constantes ───────────────────────────────────────────────────────────────
DATA_DIR_DEFAULT    = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
DISCOVERY_JSON_NAME = "dxf_discovery.json"
OUT_DIR_DEFAULT     = Path("D:/Agente-cad-PYSIDE/validacao_visual")
SLEEP_INTERVAL      = 60   # segundos entre varreduras
TIPOS_DXF           = ["PL", "LV", "FV", "LJ"]
GERADO_NOMES        = {
    "PL": "PL_stog_quality.dxf",
    "LV": "LV_stog_quality.dxf",
    "FV": "FV_stog_quality.dxf",
    "LJ": "LJ_stog_quality.dxf",
}

# ─── Import render functions de validar_visual_dxf ────────────────────────────
print("[PRERENDER] Carregando módulo de render...", flush=True)
_SCRIPT_DIR = Path(__file__).parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

try:
    from validar_visual_dxf import (
        render_dxf_to_array,
        render_dxf_prancha_strip,
        render_dxf_samples,
        detectar_prancha,
    )
    _RENDER_OK = True
except ImportError as _e:
    print(f"[PRERENDER] ERRO: falha ao importar validar_visual_dxf: {_e}")
    _RENDER_OK = False


def _ts() -> str:
    """Timestamp ISO8601 UTC para logs."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def carregar_discovery(data_dir: Path) -> dict:
    disc_path = data_dir / DISCOVERY_JSON_NAME
    if not disc_path.exists():
        return {}
    try:
        return json.loads(disc_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[PRERENDER] AVISO: falha ao ler discovery: {e}")
        return {}


def _is_fresh(png_path: Path, *dxf_paths: Path) -> bool:
    """Retorna True se o PNG existe e é mais novo que todos os DXFs informados."""
    if not png_path.exists():
        return False
    png_mtime = png_path.stat().st_mtime
    for dxf in dxf_paths:
        if dxf.exists() and dxf.stat().st_mtime > png_mtime:
            return False
    return True


def renderizar_tipo(
    obra_nome: str,
    pav_nome: str,
    tipo: str,
    dxf_stog: Path,
    dxf_gen: Path,
    pav_out: Path,
) -> bool:
    """
    Renderiza o par (dxf_stog, dxf_gen) para PNG se necessário.
    Retorna True se renderizou, False se já estava atualizado ou falhou.
    """
    png_stog_path = pav_out / f"{tipo}_stog.png"
    png_gen_path  = pav_out / f"{tipo}_gerado.png"

    # Verificar freshness de cada PNG individualmente
    stog_fresh = _is_fresh(png_stog_path, dxf_stog)
    gen_fresh  = _is_fresh(png_gen_path, dxf_gen)

    if stog_fresh and gen_fresh:
        return False  # Nada a fazer

    pav_out.mkdir(parents=True, exist_ok=True)

    # ── Renderizar STOG ───────────────────────────────────────────────────────
    if not stog_fresh:
        try:
            prancha_frames = detectar_prancha(dxf_stog)
            if prancha_frames:
                png_stog = render_dxf_prancha_strip(dxf_stog, prancha_frames)
            else:
                png_stog = render_dxf_to_array(dxf_stog)
            png_stog_path.write_bytes(png_stog)
        except Exception as e:
            print(f"[PRERENDER] ERRO render STOG {obra_nome}/{pav_nome}/{tipo}: {e}")
            return False
    else:
        png_stog = png_stog_path.read_bytes()

    # ── Renderizar Gerado ─────────────────────────────────────────────────────
    if not gen_fresh:
        # Deriva obra_dir subindo pelo caminho do DXF STOG até encontrar Fase-1
        obra_dir = dxf_stog.parent
        for p in dxf_stog.parents:
            if (p / "Fase-1_Ingestao").exists():
                obra_dir = p
                break

        try:
            if tipo in ("LV", "FV"):
                png_gen = render_dxf_to_array(dxf_gen)
            else:
                png_gen = render_dxf_samples(obra_dir, tipo, n_sample=6, label_prefix=tipo)
                if png_gen is None:
                    png_gen = render_dxf_to_array(dxf_gen)
            png_gen_path.write_bytes(png_gen)
        except Exception as e:
            print(f"[PRERENDER] ERRO render Gerado {obra_nome}/{pav_nome}/{tipo}: {e}")
            return False
    else:
        png_gen = png_gen_path.read_bytes()

    size_kb = (len(png_stog) + len(png_gen)) // 1024
    print(f"[PRERENDER] {obra_nome}/{pav_nome}/{tipo} → renderizado ({size_kb}KB) [ts={_ts()}]")
    return True


def atualizar_manifest(pav_out: Path, tipos_prontos: list, tipos_pendentes: list) -> None:
    """Escreve/atualiza manifest JSON com estado dos PNGs pré-renderizados."""
    manifest = {
        "timestamp": _ts(),
        "tipos_prontos": sorted(tipos_prontos),
        "tipos_pendentes": sorted(tipos_pendentes),
    }
    try:
        pav_out.mkdir(parents=True, exist_ok=True)
        manifest_path = pav_out / "prerender_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"[PRERENDER] AVISO: não salvou manifest em {pav_out}: {e}")


def processar_obra(
    obra_nome: str,
    discovery: dict,
    data_dir: Path,
    out_dir: Path,
    obra_filter: str | None = None,
) -> dict:
    """
    Processa todos os pavimentos de uma obra.
    Retorna stats: {tipos_renderizados, tipos_prontos, tipos_pulados, erros}.
    """
    stats = {"renderizados": 0, "prontos": 0, "pulados": 0, "erros": 0}

    if obra_filter and obra_nome != obra_filter:
        return stats

    obra_dir  = data_dir / obra_nome
    obra_disc = discovery.get(obra_nome, {})

    if not obra_disc:
        return stats

    for pav_nome, pav_tipos in obra_disc.items():
        if not isinstance(pav_tipos, dict):
            continue

        pav_safe = pav_nome.replace(" ", "_").replace("/", "-")
        pav_out  = out_dir / obra_nome / pav_safe

        tipos_prontos   = []
        tipos_pendentes = []

        for tipo in TIPOS_DXF:
            # ── DXF STOG do discovery ──────────────────────────────────────────
            dxf_stog_path = pav_tipos.get(tipo)
            if not dxf_stog_path:
                tipos_pendentes.append(tipo)
                stats["pulados"] += 1
                continue

            dxf_stog = Path(dxf_stog_path)
            if not dxf_stog.exists():
                tipos_pendentes.append(tipo)
                stats["pulados"] += 1
                continue

            # ── Pular DXFs muito grandes (>20MB) — render levaria horas ──────
            MAX_DXF_BYTES = 20 * 1024 * 1024  # 20 MB
            try:
                stog_size = dxf_stog.stat().st_size
            except Exception:
                stog_size = 0
            if stog_size > MAX_DXF_BYTES:
                print(f"[PRERENDER] SKIP {obra_nome}/{pav_safe}/{tipo} — DXF muito grande ({stog_size//1024//1024}MB > 20MB)")
                tipos_pendentes.append(tipo)
                stats["pulados"] += 1
                continue

            # ── DXF Gerado em Fase-6 ──────────────────────────────────────────
            gerado_nome = GERADO_NOMES.get(tipo)
            if not gerado_nome:
                tipos_pendentes.append(tipo)
                stats["pulados"] += 1
                continue

            dxf_gen = obra_dir / "Fase-6_Execucao_CAD" / gerado_nome
            if not dxf_gen.exists():
                tipos_pendentes.append(tipo)
                stats["pulados"] += 1
                continue

            # ── Renderizar se necessário ────────────────────────────────────────
            try:
                rendered = renderizar_tipo(
                    obra_nome, pav_safe, tipo,
                    dxf_stog, dxf_gen, pav_out,
                )
                if rendered:
                    stats["renderizados"] += 1
                    tipos_prontos.append(tipo)
                else:
                    stats["prontos"] += 1
                    tipos_prontos.append(tipo)
            except Exception as e:
                print(f"[PRERENDER] ERRO inesperado {obra_nome}/{pav_safe}/{tipo}: {e}")
                stats["erros"] += 1
                tipos_pendentes.append(tipo)
                continue

        # ── Atualizar manifest do pavimento ────────────────────────────────────
        if tipos_prontos or tipos_pendentes:
            atualizar_manifest(pav_out, tipos_prontos, tipos_pendentes)

    return stats


def varredura_completa(
    data_dir: Path,
    out_dir: Path,
    obra_filter: str | None = None,
) -> None:
    """Varre todas as obras do discovery e pré-renderiza DXFs."""
    discovery = carregar_discovery(data_dir)
    if not discovery:
        print(f"[PRERENDER] Discovery vazio ou não encontrado em {data_dir} [ts={_ts()}]")
        return

    obras = [obra_filter] if obra_filter and obra_filter in discovery else sorted(discovery.keys())
    if not obras:
        print(f"[PRERENDER] Nenhuma obra encontrada [ts={_ts()}]")
        return

    print(f"[PRERENDER] Iniciando varredura: {len(obras)} obras [ts={_ts()}]")

    total_render = 0
    total_prontos = 0
    total_erros = 0

    for obra_nome in obras:
        try:
            stats = processar_obra(obra_nome, discovery, data_dir, out_dir, obra_filter)
            total_render  += stats["renderizados"]
            total_prontos += stats["prontos"]
            total_erros   += stats["erros"]
        except Exception as e:
            print(f"[PRERENDER] ERRO fatal {obra_nome}: {e}")
            total_erros += 1

    print(
        f"[PRERENDER] Varredura concluída: "
        f"renderizados={total_render} prontos={total_prontos} erros={total_erros} "
        f"[ts={_ts()}]"
    )


def main():
    parser = argparse.ArgumentParser(
        description="nim_prerender_worker — pré-renderiza DXFs para PNG para acelerar NIM validation"
    )
    parser.add_argument("--data-dir", default=str(DATA_DIR_DEFAULT),
                        help="Diretório DADOS-OBRAS/")
    parser.add_argument("--out-dir", default=str(OUT_DIR_DEFAULT),
                        help="Diretório de saída para PNGs (validacao_visual/)")
    parser.add_argument("--obra", default=None,
                        help="Processar somente esta obra (ex: Obra_TREINO_20)")
    parser.add_argument("--once", action="store_true",
                        help="Rodar uma varredura e sair (default: loop contínuo)")
    parser.add_argument("--interval", default=SLEEP_INTERVAL, type=int,
                        help=f"Intervalo entre varreduras em segundos (default: {SLEEP_INTERVAL})")
    args = parser.parse_args()

    if not _RENDER_OK:
        print("[PRERENDER] Abortando: módulo de render não disponível.")
        sys.exit(1)

    data_dir = Path(args.data_dir)
    out_dir  = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[PRERENDER] Iniciando daemon nim_prerender_worker [ts={_ts()}]")
    print(f"[PRERENDER] data_dir={data_dir}  out_dir={out_dir}")
    if args.obra:
        print(f"[PRERENDER] Filtrando obra: {args.obra}")

    while True:
        varredura_completa(data_dir, out_dir, obra_filter=args.obra)

        if args.once:
            print(f"[PRERENDER] --once: encerrando [ts={_ts()}]")
            break

        print(f"[PRERENDER] Aguardando {args.interval}s até próxima varredura...")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
