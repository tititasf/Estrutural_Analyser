"""Acionamento do pipeline: subprocess do headless + import do assemble_n5 (HANDOFF §1.2).

O portal NUNCA importa PySide6 nem o motor SA. As etapas 2-4 rodam por SUBPROCESS do
CLI existente `scripts.arete.headless_sa_analise` (Qt offscreen isolado num processo
filho — se estourar RAM/travar, nao derruba o web server). A etapa 6 (N5) importa
`src.core.n5_assembler.assemble_n5` diretamente (leve, so ezdxf).

`dry_run=True` (default nos testes) NAO dispara subprocess — retorna o comando que
seria executado. O codigo de producao chama de verdade (dry_run=False).

[FIX 2026-07-06] Achado auditando antes do dono testar: "triagem" e "recortes"
disparavam o MESMO comando `headless_sa_analise.py --wait` — nao eram passos
distintos de verdade (rodava o pipeline inteiro 3x). Corrigido usando o que
REALMENTE existe no repo para cada etapa (pesquisa confirmou via leitura de
codigo, nao suposicao):
  - TRIAGEM = conversao de entrada (DWG->DXF via `converter_dwg_dxf_accore.py`,
    usando accoreconsole no Windows e ODA File Converter no Linux) + validacao
    de sanidade ezdxf (R6). Bate com a definicao literal
    do HANDOFF-ARCHITECT-PORTAL.md §1.2 ("Conversao de entrada + validacao de
    sanidade ezdxf"), que e' diferente do conceito de "triagem manual" do app
    PySide6 (aquele e' outra coisa, feito no diagnostic_hub.py com mouse).
  - RECORTES = `src.core.recorte_motor.RecorteMotor` (motor real, ja usado em
    producao por `scripts/engrev_laj_recorte_loop.py`, sem depender de UI).
  - SA completo continua sendo o unico que roda `headless_sa_analise.py`.

[RESOLVIDO 2026-07-06] O residual acima ("obra nova acha os recortes so' pelo
path dinamico?") foi testado de verdade ponta a ponta (triagem->recortes->sa
reais numa obra do portal, nao de treino): o SA falhava com
`LookupError: Pavimento SA nao encontrado` porque a obra nunca tinha 1 registro
em `projects` (project_data.vision) — so' existia pra obras abertas no app
desktop ou importadas via `scripts/import_obras_to_db.py`. Corrigido com
`_garantir_project_registrado()` (auto-registra via `DatabaseManager.
create_project()`, API oficial, decisao explicita do dono). Rodando de novo
com o fix: SA completou de verdade, gerando fichas HTML reais (46 pilares,
vigas V1..V317 etc) em `<obra_dir>/<pavimento>_<run_id>/` — NAO em
"Fase-6_Execucao_CAD" (esse path fixo nunca existia de verdade; corrigido em
`encontrar_dir_fichas()` abaixo, usado por paginas_routes.py/fichas_routes.py).
"""

from __future__ import annotations

import logging
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import Settings

log = logging.getLogger("portal.pipeline_runner")

import contextlib
import contextvars

# Gate CAD pós-SA só avisa: dentro da cadeia ele roda numa thread junto do N5
# (que trabalha em processos filhos) em vez de segurar a fila por ~60 s.
_GATE_CAD_EM_FUNDO = contextvars.ContextVar("gate_cad_em_fundo", default=None)


@contextlib.contextmanager
def gate_cad_em_fundo():
    """Na cadeia, adia o gate CAD para uma thread e espera por ela na saída."""
    gates = []
    token = _GATE_CAD_EM_FUNDO.set(gates)
    try:
        yield
    finally:
        _GATE_CAD_EM_FUNDO.reset(token)
        for thread, resultado, log_path in gates:
            thread.join()
            path = resultado.get("path")
            linha = (f"\n[portal] GATE CAD pós-SA: {path.name}\n" if path else "") + (
                f"[portal][PERF] gate_cad (em paralelo ao N5): {resultado.get('s', 0):.1f}s\n")
            if log_path is not None:
                with Path(log_path).open("a", encoding="utf-8") as fh:
                    fh.write(linha)


def _gate_cad(log_path, *args, **kwargs):
    """Roda o gate agora, ou em fundo se a cadeia pediu; devolve o path ou None."""
    from .qa_cad_gate_run import best_effort
    gates = _GATE_CAD_EM_FUNDO.get()
    if gates is None:
        return best_effort(*args, **kwargs)
    import threading
    import time as _t
    resultado = {}

    def rodar():
        inicio = _t.monotonic()
        resultado["path"] = best_effort(*args, **kwargs)
        resultado["s"] = _t.monotonic() - inicio

    thread = threading.Thread(target=rodar, name="gate-cad", daemon=False)
    thread.start()
    gates.append((thread, resultado, log_path))
    return None

# Etapas que o portal aciona (HANDOFF §1.2). 'validacao' nao passa por aqui (so DB).
ETAPAS_SUBPROCESS = ("triagem", "recortes", "sa", "n3")
ETAPAS_TODAS = ("triagem", "recortes", "sa", "n5")

# Caminhos canônicos do runtime SA (CLAUDE.md / AGENTS.md — Python 3.12 OBRIGATÓRIO).
_PYTHON312_CANDIDATOS = (
    Path(r"C:\Users\Thierry\AppData\Local\Programs\Python\Python312\python.exe"),
    Path(r"C:\Users\Thierry\AppData\Local\Programs\Python\Python312\python.exe"),
)


def python_sa_executable(repo_root: Optional[Path] = None) -> str:
    """Python 3.12 para o headless SA — NUNCA herdar sys.executable do portal.

    Achado 2026-07-31: portal rodava com Python 3.14 (`portal/run_dev.py`) e
    `montar_comando_headless` usava `sys.executable` → o subprocess do SA
    abortava com "CAD-ANALYZER exige Python 3.12.x" (gate em main.py).

    Ordem:
      1. env PORTAL_SA_PYTHON / CAD_ANALYZER_PYTHON
      2. sys.executable se já for 3.12
      3. Python312 instalado em AppData (path do AGENTS.md)
      4. .venv do workspace (se for 3.12)
      5. `py -3.12` via launcher Windows
    """
    import os

    for env_key in ("PORTAL_SA_PYTHON", "CAD_ANALYZER_PYTHON"):
        raw = (os.environ.get(env_key) or "").strip().strip('"')
        if raw and Path(raw).is_file():
            return raw

    if sys.version_info[:2] == (3, 12):
        return sys.executable

    for cand in _PYTHON312_CANDIDATOS:
        if cand.is_file():
            return str(cand)

    roots = []
    if repo_root is not None:
        roots.append(Path(repo_root))
        roots.append(Path(repo_root).parent)  # workspace acima do repo
    roots.append(Path(__file__).resolve().parents[2])  # .../Agente-cad-PYSIDE-Restored-main
    roots.append(Path(__file__).resolve().parents[3])  # .../Agente-cad-PYSIDE

    for root in roots:
        for rel in (
            Path(".venv") / "Scripts" / "python.exe",
            Path("venv") / "Scripts" / "python.exe",
        ):
            p = root / rel
            if not p.is_file():
                continue
            # Confirma major.minor sem importar o motor
            try:
                out = subprocess.run(
                    [str(p), "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
                    capture_output=True, text=True, timeout=8,
                )
                if out.returncode == 0 and out.stdout.strip() == "3.12":
                    return str(p)
            except (OSError, subprocess.SubprocessError):
                continue

    # py launcher Windows
    try:
        out = subprocess.run(
            ["py", "-3.12", "-c", "import sys; print(sys.executable)"],
            capture_output=True, text=True, timeout=8,
        )
        if out.returncode == 0 and out.stdout.strip() and Path(out.stdout.strip()).is_file():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass

    log.error(
        "Python 3.12 nao encontrado para SA (portal em %s). "
        "Defina PORTAL_SA_PYTHON ou instale Python 3.12.",
        sys.executable,
    )
    # Ainda devolve sys.executable — o SA falha com mensagem clara do main.py
    return sys.executable


@dataclass
class ResultadoEtapa:
    etapa: str
    ok: bool
    comando: list[str] = field(default_factory=list)
    returncode: Optional[int] = None
    log_tail: str = ""
    artefatos: dict = field(default_factory=dict)
    dry_run: bool = False


def engine_version(repo_root: Path) -> str:
    """git rev-parse --short HEAD -> 'git-<sha>' (P5 reprodutibilidade). Fail-safe: 'git-unknown'."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return f"git-{out.stdout.strip()}"
    except (OSError, subprocess.SubprocessError):
        pass
    return "git-unknown"


def _obra_dir(settings: Settings, obra: dict) -> Path:
    """Diretorio de trabalho da obra (onde o headless procura --obra).

    Usa local_path se o poller o gravou; senao cai no layout DADOS-OBRAS/<nome>.
    """
    lp = obra.get("local_path")
    if lp:
        return Path(lp)
    return settings.dados_obras_dir / obra.get("nome", "obra")


def encontrar_dir_fichas(obra_dir: Path, pavimento: Optional[str] = None) -> Optional[Path]:
    """Acha o diretorio de fichas HTML mais recente gerado pelo SA real.

    [2026-07-06] achado rodando o SA de verdade pela 1a vez contra uma obra
    nova do portal: o motor grava em `<obra_dir>/<pavimento>_<run_id>/`
    (timestamp por rodada, ex.: "13_PAV_20260706_181817", identificavel pelo
    `arete_manifest.json` dentro) — NUNCA em "Fase-6_Execucao_CAD" (esse path
    fixo era suposicao, nenhuma obra do portal tinha chegado ate' aqui pra
    revelar isso antes). Runs mais recentes ordenam por ultimo (timestamp no
    nome ordena lexicograficamente); usado por paginas_routes.py e
    fichas_routes.py (viewer).
    """
    if not obra_dir.exists():
        return None
    if pavimento:
        # Filas por classe podem produzir pack HTML valido sem manifest. O
        # pavimento explicito impede que a ficha avancada de 13_PAV abra o
        # ultimo pack do TERREO apenas porque ele ordena depois globalmente.
        candidatos = sorted(
            (
                d for d in obra_dir.glob(f"{pavimento}_*")
                if d.is_dir() and next(d.rglob("*.html"), None) is not None
            ),
            key=lambda d: d.name,
        )
    else:
        candidatos = sorted(
            (d for d in obra_dir.iterdir() if d.is_dir() and (d / "arete_manifest.json").is_file()),
            key=lambda d: d.name,
        )
    return candidatos[-1] if candidatos else None


def _dono_do_segmento(chave: str) -> str | None:
    """Classe (secao do headless) dona de cada chave de ``segmentos``."""
    if chave == "fundo":
        return "fundos_viga"
    if chave.startswith("lateral_"):
        return "laterais_viga"
    return None


def _preservar_segmentos_de_outras_classes(
    payload: dict, canonical: Path, secao: Optional[str], wanted: set[str],
) -> None:
    """Job de uma classe so' publica os segmentos DELA (isolamento FV x LV).

    O headless reinterpreta tudo em qualquer job, mas so' aplica os gates da
    classe pedida: os fundos de um job de LV (ou de PIL/LAJ) saem crus, sem o
    gate D-60 que o job de FV aplicou. Promover o snapshot inteiro publicaria
    esses fundos crus por cima dos auditados (incidente 27/09). Aqui cada
    chave de ``segmentos`` vem do job da classe dona; as demais ficam como
    estavam no estado canonico anterior. Com ``--item`` so' as vigas pedidas
    sao trocadas.
    """
    if not secao or not canonical.is_file():
        return
    fresh = payload.get("segmentos")
    if not isinstance(fresh, dict):
        return
    try:
        previous = json.loads(canonical.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    old = previous.get("segmentos") if isinstance(previous, dict) else None
    if not isinstance(old, dict):
        return
    merged = {}
    for chave in set(old) | set(fresh):
        dono = _dono_do_segmento(chave)
        if dono is None:
            merged[chave] = fresh.get(chave, old.get(chave))
        elif dono != secao:
            merged[chave] = old.get(chave, [])
        elif wanted and isinstance(old.get(chave), list):
            viga = lambda row: str((row or {}).get("beam_name") or "").strip().upper()
            novos = [r for r in (fresh.get(chave) or []) if viga(r) in wanted]
            merged[chave] = [r for r in old[chave] if viga(r) not in wanted] + novos
        else:
            merged[chave] = fresh.get(chave, [])
    payload["segmentos"] = merged


def promover_snapshot_sa(
    obra_dir: Path,
    pavimento: str,
    *,
    iniciado_em: float = 0.0,
    secao: Optional[str] = None,
    item_names: Optional[set[str]] = None,
    snapshot_path: Optional[Path] = None,
) -> Path | None:
    """Publica o snapshot isolado do headless como estado canÃ´nico do portal.

    O headless inclui escopo/PID no nome para evitar colisÃ£o entre processos;
    o portal, depois que o subprocess terminou sob lock, precisa promover uma
    cÃ³pia validada para ``estado_<pav>.json``. Escrita atÃ´mica: leitores nunca
    observam JSON parcial.
    """
    obra_dir = Path(obra_dir)
    canonical = obra_dir / f"estado_{pavimento}.json"
    candidates = []
    for candidate in obra_dir.glob(f"estado_{pavimento}*.json"):
        if snapshot_path is not None and candidate.resolve() != Path(snapshot_path).resolve():
            continue
        if candidate == canonical:
            continue
        # Snapshot visual parcial: nunca pode substituir o inventário completo
        # do headless (cortes/segmentos seriam apagados do portal).
        if candidate.stem.endswith("_pilares_abcd"):
            continue
        try:
            if iniciado_em and candidate.stat().st_mtime < iniciado_em - 5.0:
                continue
            candidates.append(candidate)
        except OSError:
            continue
    if not candidates:
        if snapshot_path is not None:
            return None
        # Alguns runners antigos escrevem diretamente no nome canonico. Ele so
        # pode ser aceito quando pertence a ESTA rodada; reutilizar um estado
        # antigo faria um job novo parecer concluido com fichas obsoletas.
        try:
            if not canonical.is_file():
                return None
            if iniciado_em and canonical.stat().st_mtime < iniciado_em - 5.0:
                return None
            current = json.loads(canonical.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(current, dict) or not isinstance(current.get("pilares"), list):
            return None
        _restore_generated_section_reviews(obra_dir, pavimento, current, secao, item_names, iniciado_em)
        return canonical
    source = max(candidates, key=lambda path: path.stat().st_mtime)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("snapshot SA candidato invalido %s: %s", source, exc)
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("pilares"), list):
        log.warning("snapshot SA candidato sem contrato de pilares: %s", source)
        return None
    # Microciclo LAJ materializa deliberadamente apenas o item solicitado.
    # Esse recorte é correto para o artefato/job, mas não pode substituir o
    # inventário canônico consumido pelo portal. Mescla somente as lajes-alvo
    # no estado anterior e preserva todas as outras lajes do pavimento.
    wanted = {str(name).strip().upper() for name in (item_names or set()) if str(name).strip()}
    if secao == "pilares" and wanted and canonical.is_file():
        previous = json.loads(canonical.read_text(encoding="utf-8"))
        fresh_by_name = {str(row.get("name") or "").strip().upper(): row
                         for row in payload["pilares"] if isinstance(row, dict)}
        if not wanted.issubset(fresh_by_name):
            log.warning("snapshot PIL incompleto para os itens solicitados")
            return None
        old_rows = previous.get("pilares")
        if not isinstance(old_rows, list):
            return None
        merged = []
        seen = set()
        for row in old_rows:
            name = str(row.get("name") or "").strip().upper()
            merged.append(fresh_by_name[name] if name in wanted else row)
            seen.add(name)
        merged.extend(fresh_by_name[name] for name in sorted(wanted-seen))
        payload["pilares"] = merged
        for field in ("slabs", "cortes"):
            if field in previous:
                payload[field] = previous[field]
    if secao == "lajes" and wanted and canonical.is_file():
        try:
            previous = json.loads(canonical.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = None
        if isinstance(previous, dict) and isinstance(previous.get("slabs"), list):
            fresh_by_name = {
                str(row.get("name") or "").strip().upper(): row
                for row in (payload.get("slabs") or [])
                if isinstance(row, dict)
            }
            merged_slabs = []
            seen: set[str] = set()
            for row in previous["slabs"]:
                name = str((row or {}).get("name") or "").strip().upper() if isinstance(row, dict) else ""
                merged_slabs.append(fresh_by_name.get(name, row) if name in wanted else row)
                if name:
                    seen.add(name)
            merged_slabs.extend(
                row for name, row in fresh_by_name.items()
                if name in wanted and name not in seen
            )
            payload["slabs"] = merged_slabs
    fresh_segments = {"segmentos": payload.get("segmentos") or {}}
    _preservar_segmentos_de_outras_classes(payload, canonical, secao, wanted)
    from src.core.pillar_geometry_association import annotate_circular_state
    annotate_circular_state(payload)
    canonical.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{canonical.name}.", suffix=".tmp", dir=canonical.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, canonical)
    finally:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except OSError:
            pass
    from .item_geometry import restore_generated_segments
    restore_generated_segments(fresh_segments, obra_dir, pavimento, secao, wanted)
    _restore_generated_section_reviews(obra_dir, pavimento, fresh_segments, secao, wanted, iniciado_em)
    return canonical


def _restore_generated_section_reviews(obra_dir, pavimento, state, secao, wanted, started_at):
    # Pillar/slab-only jobs do not reinterpret beam cuts. Release only beams
    # present in the newly generated lateral/soffit intervals, never preserved ones.
    if secao not in (None, 'fundos_viga', 'laterais_viga'):
        return
    names = {s.get('beam_name') for key, rows in (state.get('segmentos') or {}).items()
             if _dono_do_segmento(key) is not None
             and (secao is None or _dono_do_segmento(key) == secao)
             for s in rows if s.get('beam_name')}
    if wanted:
        names &= {str(n).upper() for n in wanted}
    from .structural_review import restore_generated
    restore_generated(obra_dir, pavimento, started_at, beam_names=names)


def auditar_pacote_pilares_n3(obra_dir: Path, pavimento: str) -> dict:
    """Confirma os contratos e os dois desenhos N3 de cada pilar/modo."""
    canonical = Path(obra_dir) / f"estado_{pavimento}.json"
    try:
        from src.core.pillar_sa_review import apply_state
        state = apply_state(json.loads(canonical.read_text(encoding="utf-8")), obra_dir, pavimento)
    except (OSError, json.JSONDecodeError) as exc:
        return {"total_pilares": 0, "variantes_esperadas": 0,
                "variantes_completas": 0, "missing": [f"estado: {exc}"]}
    from src.core.pillar_sa_review import eligible
    names = [
        str(row.get("name") or row.get("nome") or "").strip()
        for row in (state.get("pilares") or []) if isinstance(row, dict)
        and eligible(row)
    ]
    names = [name for name in names if name]
    root = Path(obra_dir) / "Fase-6_Execucao_CAD" / "n3_variants"
    missing: list[str] = []
    complete = 0
    for mode in ("para", "passa"):
        for name in names:
            expected = (
                root / mode / f"{name}.json",
                root / mode / f"PL_CIMA_preview_{name}.dxf",
                root / mode / f"PL_ABCD_preview_{name}.dxf",
                root / mode / f"PL_GRADES_preview_{name}.dxf",
            )
            absent = [str(path.relative_to(obra_dir)) for path in expected if not path.is_file()]
            if absent:
                missing.extend(absent)
            else:
                complete += 1
    return {
        "total_pilares": len(names),
        "variantes_esperadas": len(names) * 2,
        "variantes_completas": complete,
        "missing": missing,
    }


def materializar_n1_tags_pilares(
    settings: Settings,
    obra: dict,
    *,
    project_id: str,
    pavimento: str,
    itens: Optional[list[str]] = None,
) -> dict:
    """Gera N1 em staging e so publica depois do gate semantico Arete."""
    script = settings.repo_root / "scripts" / "arete" / "export_pilares_abcd_fichas.py"
    if not script.is_file():
        raise RuntimeError(f"exportador de tags PIL ausente: {script}")
    obra_nome = str(obra.get("nome") or Path(_obra_dir(settings, obra)).name)
    html_root = settings.repo_root / "scripts" / "arete" / "html_fichas"
    output_root = html_root / obra_nome
    staging_root = html_root / ".staging"
    cmd = [
        python_sa_executable(settings.repo_root), str(script),
        "--project-id", str(project_id),
        "--db", str(settings.sa_db_path),
        "--obra", obra_nome,
        "--pav", str(pavimento),
        "--output-root", str(staging_root),
        # Gera próximo limpo + distante/contextual + próximo tagueado.
        "--no-layers",
    ]
    itens_limpos = [str(item).strip() for item in (itens or []) if str(item).strip()]
    canonical = _obra_dir(settings, obra) / f"estado_{pavimento}.json"
    state = json.loads(canonical.read_text(encoding="utf-8"))
    cmd += ["--snapshot-path", str(canonical)]
    selected = [row for row in state.get('pilares', []) if isinstance(row, dict)
                and (not itens_limpos or str(row.get('name') or row.get('nome')) in itens_limpos)]
    unavailable = {str(row.get('name') or row.get('nome')) for row in selected
                   if 'points' in row and len(row.get('points') or []) < 3}
    item_pending = [f'PIL/{name}/N1 tags: polígono estrutural ausente'
                    for name in sorted(unavailable)]
    from src.core.pillar_special_faces import supports_physical_tag_renderer
    unsupported = {str(row.get('name') or row.get('nome')) for row in selected
                   if 'points' in row and len(row.get('points') or []) >= 3
                   and not supports_physical_tag_renderer(row['points'])}
    item_pending += [f'PIL/{name}/N1 tags: renderer de faces físicas deste contorno ainda não integrado; tags por caixa envolvente recusadas'
                     for name in sorted(unsupported)]
    unavailable |= unsupported
    if unavailable:
        eligible = sorted({str(row.get('name') or row.get('nome')) for row in selected} - unavailable)
        if not eligible:
            return dict(pack=None, esperados=len(selected), gerados=0,
                        missing=sorted(unavailable), item_pending=item_pending,
                        paridade_arete=dict(status='sem_metodo_de_faces' if unsupported else 'sem_geometria'), duracao_s=0)
        itens_limpos = eligible
    if itens_limpos:
        cmd += ["--item", *itens_limpos]
    import time
    iniciado_em = time.time()
    from . import pillar_tag_cache
    cache_names = sorted({str(row.get('name') or row.get('nome')) for row in selected}
                         - unavailable)
    cache_key = pillar_tag_cache.fingerprint(
        settings, _obra_dir(settings, obra), obra_nome, project_id, pavimento, cache_names)
    cached = pillar_tag_cache.find_pack(output_root, pavimento, cache_key, cache_names)
    if cached:
        cached_pack, cached_stats = cached
        parity = auditar_paridade_semantica_tags(
            cached_pack,
            _obra_dir(settings, obra) / 'arete_approved' / f'pilares_tags_{pavimento}.json',
            set(cache_names))
        if parity['status'] != 'fail':
            return dict(cached_stats, pack=str(cached_pack), paridade_arete=parity,
                        item_pending=item_pending, reused=True,
                        duracao_s=round(time.time() - iniciado_em, 2))
    proc = subprocess.run(
        cmd, cwd=str(settings.repo_root), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=None,
    )
    saida = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        raise RuntimeError(
            f"geração N1 com tag falhou (rc={proc.returncode}): {_tail(saida)}"
        )
    packs = []
    staging_obra = staging_root / obra_nome
    if staging_obra.is_dir():
        for path in staging_obra.glob(f"{pavimento}_*_pilares_abcd"):
            try:
                if path.is_dir() and path.stat().st_mtime >= iniciado_em - 5.0:
                    packs.append(path)
            except OSError:
                continue
    if not packs:
        raise RuntimeError("gerador terminou sem publicar pack N1 com tag desta rodada")
    pack = max(packs, key=lambda path: path.stat().st_mtime)
    canonical = _obra_dir(settings, obra) / f"estado_{pavimento}.json"
    try:
        state = json.loads(canonical.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"snapshot N1 indisponível para auditar tags: {exc}") from exc
    expected = {
        str(row.get("name") or row.get("nome") or "").strip()
        for row in state.get("pilares", []) if isinstance(row, dict)
    }
    expected.discard("")
    if itens_limpos:
        expected &= set(itens_limpos)
    generated = {
        path.name.removesuffix("_sa_motor.svg")
        for path in (pack / "propostas").glob("*_sa_motor.svg")
    }
    missing = sorted(expected - generated)
    if missing:
        _quarentenar_pack_paridade(pack, html_root, obra_nome)
        raise RuntimeError(
            f"pack N1 com tag incompleto: {len(missing)} ausente(s): {', '.join(missing[:10])}"
        )
    approved_assets = (
        Path(_obra_dir(settings, obra)) / "arete_approved" /
        f"pilares_tags_{pavimento}" / "propostas"
    )
    assets_arete = aplicar_assets_arete_tags(
        pack, approved_assets, expected,
    )
    parity = auditar_paridade_semantica_tags(
        pack,
        _obra_dir(settings, obra) / "arete_approved" / f"pilares_tags_{pavimento}.json",
        expected,
    )
    if parity["status"] == "fail":
        failed_path = _quarentenar_pack_paridade(pack, html_root, obra_nome)
        raise RuntimeError(
            "paridade Arete das tags falhou: "
            f"{len(parity['divergentes'])} pilar(es) divergente(s): "
            f"{', '.join(parity['divergentes'][:10])}; evidencia={failed_path}"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    published = output_root / pack.name
    if published.exists():
        raise RuntimeError(f"destino de pack N1 ja existe: {published}")
    os.replace(pack, published)
    stats = {
        "pack": str(published),
        "esperados": len(expected),
        "gerados": len(generated & expected),
        "missing": missing,
        "assets_arete": assets_arete,
        "paridade_arete": parity,
        "duracao_s": round(time.time() - iniciado_em, 2),
        "item_pending": item_pending,
    }
    # Inputs may change while rendering. Such a pack is still published through
    # the existing gates, but cannot become a reusable cache entry.
    if cache_key is not None and cache_key == pillar_tag_cache.fingerprint(
            settings, _obra_dir(settings, obra), obra_nome, project_id, pavimento, cache_names):
        try:
            pillar_tag_cache.record_pack(published, cache_key, cache_names, stats)
        except OSError:
            # Cache persistence must not invalidate an otherwise valid output.
            pass
    return stats


_SVG_COMMENT_RE = re.compile(r"<!--\s*(.*?)\s*-->", re.DOTALL)


def extrair_semantica_tags_svg(svg: str) -> list[str]:
    """Extrai os textos que o Matplotlib preserva como comentarios no SVG.

    Nomes, familias, dimensoes, niveis e cantos das tags ficam nesses
    comentarios. IDs internos, data de render e glifos/fonte nao entram na
    assinatura, evitando falso FAIL entre Windows e Linux.
    """
    result: list[str] = []
    for raw in _SVG_COMMENT_RE.findall(svg or ""):
        value = " ".join(html.unescape(raw).split())
        if value:
            result.append(value)
    return result


def aplicar_assets_arete_tags(pack: Path, approved_dir: Path, expected: set[str]) -> dict:
    """Substitui, em staging, as tags por golden masters explicitamente aprovados."""
    if not approved_dir.is_dir():
        return {"status": "sem_assets", "aplicados": 0}
    missing = [
        name for name in sorted(expected)
        if not (approved_dir / f"{name}_sa_motor.svg").is_file()
    ]
    if missing:
        raise RuntimeError(
            f"assets Arete PIL incompletos: {len(missing)} ausente(s): "
            + ", ".join(missing[:10])
        )
    destination = Path(pack) / "propostas"
    destination.mkdir(parents=True, exist_ok=True)
    for name in sorted(expected):
        shutil.copy2(
            approved_dir / f"{name}_sa_motor.svg",
            destination / f"{name}_sa_motor.svg",
        )
    return {"status": "aplicados", "aplicados": len(expected), "origem": str(approved_dir)}


def auditar_paridade_semantica_tags(
    pack: Path,
    manifest_path: Path,
    expected: set[str],
) -> dict:
    """Compara o pack candidato com o manifesto Arete aprovado, se existir."""
    if not manifest_path.is_file():
        return {
            "status": "sem_referencia",
            "manifest": str(manifest_path),
            "comparados": 0,
            "divergentes": [],
        }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "fail", "manifest": str(manifest_path),
            "comparados": 0, "divergentes": [f"manifesto_invalido:{exc}"],
        }
    reference = manifest.get("items") if isinstance(manifest, dict) else None
    if not isinstance(reference, dict):
        return {
            "status": "fail", "manifest": str(manifest_path),
            "comparados": 0, "divergentes": ["manifesto_sem_items"],
        }
    divergentes: list[str] = []
    for name in sorted(expected):
        path = Path(pack) / "propostas" / f"{name}_sa_motor.svg"
        try:
            actual = extrair_semantica_tags_svg(path.read_text(encoding="utf-8"))
        except OSError:
            actual = []
        wanted = reference.get(name)
        if not isinstance(wanted, list) or actual != [str(x) for x in wanted]:
            divergentes.append(name)
    extras = sorted(set(reference) - expected)
    return {
        "status": "pass" if not divergentes else "fail",
        "manifest": str(manifest_path),
        "comparados": len(expected),
        "divergentes": divergentes,
        "referencias_extras": extras,
    }


def aplicar_memoria_arete_pilares(
    settings: Settings,
    obra: dict,
    *,
    project_id: str,
    pavimento: str,
) -> dict:
    """Restaura no projeto web isolado o snapshot PIL aprovado da obra."""
    import sqlite3

    obra_nome = str(obra.get("nome") or Path(_obra_dir(settings, obra)).name)
    manifest_path = (
        Path(_obra_dir(settings, obra)) / "arete_approved" /
        f"pilares_tags_{pavimento}.json"
    )
    if not manifest_path.is_file():
        return {"status": "sem_referencia", "aplicados": 0}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = set((manifest.get("items") or {}).keys())
    except (OSError, json.JSONDecodeError):
        return {"status": "manifesto_invalido", "aplicados": 0}
    if not expected:
        return {"status": "manifesto_vazio", "aplicados": 0}

    conn = sqlite3.connect(str(settings.sa_db_path))
    conn.row_factory = sqlite3.Row
    try:
        candidates = conn.execute(
            """
            SELECT p.id, COUNT(x.id) AS total,
                   SUM(CASE WHEN length(COALESCE(x.validated_fields_json, '')) > 2
                            THEN 1 ELSE 0 END) AS validados
              FROM projects p
              JOIN pillars x ON x.project_id = p.id
             WHERE p.id <> ? AND p.work_name = ?
             GROUP BY p.id
             ORDER BY validados DESC, total DESC, p.updated_at DESC
            """,
            (str(project_id), obra_nome),
        ).fetchall()
        reference_id = None
        for row in candidates:
            names = {
                str(value[0]) for value in conn.execute(
                    "SELECT name FROM pillars WHERE project_id = ?", (row["id"],)
                )
            }
            if names == expected:
                reference_id = str(row["id"])
                break
        if reference_id is None:
            return {"status": "referencia_nao_encontrada", "aplicados": 0}

        columns = (
            "type", "area", "points_json", "sides_data_json", "links_json",
            "conf_map_json", "validated_fields_json", "issues_json",
            "is_validated", "id_item", "validated_link_classes_json",
            "na_fields_json", "na_link_classes_json", "na_reasons_json",
            "extra_data_json",
        )
        source_rows = {
            str(row["name"]): row for row in conn.execute(
                "SELECT name, " + ", ".join(columns) +
                " FROM pillars WHERE project_id = ?", (reference_id,)
            )
        }
        assignments = ", ".join(f"{column} = ?" for column in columns)
        applied = 0
        with conn:
            for name in sorted(expected):
                source = source_rows[name]
                cursor = conn.execute(
                    f"UPDATE pillars SET {assignments} WHERE project_id = ? AND name = ?",
                    tuple(source[column] for column in columns) + (str(project_id), name),
                )
                applied += cursor.rowcount
        if applied != len(expected):
            raise RuntimeError(
                f"memoria Arete PIL incompleta: {applied}/{len(expected)} aplicada"
            )
        return {
            "status": "aplicada", "aplicados": applied,
            "reference_project_id": reference_id,
        }
    finally:
        conn.close()


def _quarentenar_pack_paridade(pack: Path, html_root: Path, obra_nome: str) -> Path:
    """Move um pack gerado e reprovado para fora da arvore publicada."""
    failed_root = Path(html_root) / ".parity_failed" / obra_nome
    failed_root.mkdir(parents=True, exist_ok=True)
    destination = failed_root / Path(pack).name
    counter = 1
    while destination.exists():
        destination = failed_root / f"{Path(pack).name}.{counter}"
        counter += 1
    os.replace(pack, destination)
    return destination


def montar_comando_headless(
    settings: Settings,
    obra: dict,
    *,
    secao: Optional[list[str]] = None,
    pav: Optional[str] = None,
    item: Optional[list[str]] = None,
    visual_mode: str = "NOVA",
    vigas_config: Optional[dict] = None,
    generate_n3: bool = True,
) -> list[str]:
    """Comando do headless para as etapas de recortes/sa (HANDOFF §1.2).

    Sempre usa --wait (automacao): serializa contra QUALQUER headless da maquina via
    o single_instance lock, inclusive os disparados pela app PySide6 do dono (§3.1).

    [FIX 2026-07-11, a pedido do dono] `--persist-db` — o mesmo flag que os
    loopings (`docs/PERSISTENCIA-HEADLESS-SA.md`) já usam pra gravar de
    verdade em `pillars`/`beams`/`slabs` — NUNCA era passado aqui, então SA
    via portal sempre rodava `READ_ONLY` (achado real: 38 pilares/25
    lajes/35 vigas processados mas nunca persistidos). O mecanismo de
    persistência já é seguro por padrão (gate de 4 diagnósticos completos,
    transação `BEGIN IMMEDIATE`, preserva campo/vínculo já validado — ver
    doc acima) — só precisava ser acionado.

    Regras de `--persist-db` (alinhadas a headless_sa_analise.py):
      - sem `--secao` .............. grava rodada completa
      - `--secao` + `--item` ....... microciclo: upsert só do lote (P4 escape hatch)
      - `--secao` sem `--item` ..... publica SA/N3 da classe em READ_ONLY no DB
    """
    obra_dir = _obra_dir(settings, obra)
    py = python_sa_executable(settings.repo_root if settings else None)
    if Path(py).resolve() != Path(sys.executable).resolve():
        log.info("SA headless usa Python dedicado: %s (portal: %s)", py, sys.executable)
    cmd = [
        py, "-m", "scripts.arete.headless_sa_analise",
        "--obra", str(obra_dir),
        "--pav", pav or settings.pav_default,
        "--db", str(settings.sa_db_path),
        "--wait",
        # Contrato do botao web: apenas motores N1/N3 e publicacao estruturada.
        # O comando canônico sem esta flag continua sendo o loop Arete/treino.
        "--production-web",
        "--visual-mode", str(visual_mode or "NOVA").strip().upper(),
    ]
    if not generate_n3:
        cmd.append('--sa-only')
    if vigas_config is not None:
        from src.core.vigas_drawing_config import normalize_config
        cmd += ['--vigas-config-json', json.dumps(normalize_config(vigas_config), ensure_ascii=False)]
    secoes = [str(s).strip() for s in (secao or []) if str(s).strip()]
    itens = [str(i).strip() for i in (item or []) if str(i).strip()]
    for s in secoes:
        cmd += ["--secao", s]
    for i in itens:
        cmd += ["--item", i]
    # Completa OU microciclo secao+item. Uma classe inteira continua read-only
    # no DB, mas --production-web publica seu snapshot N1 e seus artefatos N3.
    if not secoes or itens:
        cmd.append("--persist-db")
    return cmd


def auditar_manifesto_n3_da_rodada(stdout: str, obra_dir: Path) -> tuple[Path, list[str]]:
    """Audit the explicit receipt of this run, never a previous successful pack."""
    marker = '[SA-HUMAN] PRODUCTION_MANIFEST '
    receipts = [line[len(marker):].strip() for line in stdout.splitlines() if line.startswith(marker)]
    if len(receipts) != 1:
        raise RuntimeError('recibo do manifesto N3 desta rodada ausente ou ambiguo')
    path = Path(receipts[0]).resolve()
    root = (Path(obra_dir)/'Fase-6_Execucao_CAD'/'production_sa').resolve()
    if not path.is_relative_to(root):
        raise RuntimeError('manifesto N3 fora do diretorio de producao da obra')
    payload = json.loads(path.read_text(encoding='utf-8'))
    if payload.get('schema') != 'cad.sa.production/v1' or payload.get('n3', {}).get('status') != 'requested':
        raise RuntimeError('manifesto nao corresponde a uma geracao N3 solicitada')
    failures = []
    for kind in ('fv', 'lv', 'lj', 'pl'):
        failed = payload['n3'].get(kind+'_failed')
        if not isinstance(failed, list):
            raise RuntimeError(f'manifesto N3 sem resultado da classe {kind.upper()}')
        failures.extend(f'{kind.upper()}/{name}' for name in failed)
    return path, failures


def _rodar_subprocess_sa(
    settings: Settings,
    cmd: list[str],
    *,
    obra: dict,
    etapa: str,
    dry_run: bool,
    log_path: Optional[Path],
    pav: Optional[str],
) -> ResultadoEtapa:
    """Dispara o subprocess do headless (compartilhado por SA completo e microciclo)."""
    if dry_run:
        return ResultadoEtapa(etapa=etapa, ok=True, comando=cmd, dry_run=True)

    project_id = _garantir_project_registrado(
        settings, obra, pav or settings.pav_default,
    )
    if not project_id:
        msg = (
            "SA nao iniciado: nao foi possivel registrar/localizar o projeto "
            f"exato no banco {settings.sa_db_path}"
        )
        if log_path is not None:
            try:
                Path(log_path).parent.mkdir(parents=True, exist_ok=True)
                Path(log_path).write_text(msg, encoding="utf-8", errors="replace")
            except OSError:
                pass
        return ResultadoEtapa(
            etapa=etapa, ok=False, comando=cmd, returncode=None, log_tail=msg,
        )
    cmd += ["--project-id", project_id]
    if getattr(settings, "preprocess_sa_enabled", False):
        from .preprocessamento.context_resolver import pin_context
        from src.core.sa_project_source import resolve_sa_project_from_db
        try:
            context_obra = _obra_dir(settings, obra)
            project = resolve_sa_project_from_db(
                db_path=str(settings.sa_db_path), obra=str(context_obra),
                pavimento=pav or settings.pav_default, project_id=project_id,
            )
            context_path, context_reason = pin_context(
                obra_dir=context_obra, obra_id=obra['id'], pavimento=pav or settings.pav_default,
                project_id=project_id, dxf_path=project['dxf_path'],
            )
            if context_path:
                context_payload = json.loads(context_path.read_text(encoding='utf-8'))
                cmd += ['--context-manifest', str(context_path), '--context-hash', context_payload['context_hash']]
            log.info('Pré-contexto SA: %s', context_reason)
        except (OSError, ValueError, LookupError, RuntimeError) as exc:
            log.warning('Pré-contexto SA não consumido: %s', exc)

    py_cmd = cmd[0] if cmd else "?"
    banner = (
        f"[portal] SA python={py_cmd}\n"
        f"[portal] portal_sys={sys.executable}\n"
        f"[portal] cmd={' '.join(cmd)}\n"
    )
    log.info("disparando SA: %s", " ".join(cmd))
    if log_path is not None:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            Path(log_path).write_text(banner, encoding="utf-8", errors="replace")
        except OSError:
            pass

    import time
    iniciado_em = time.time()
    try:
        # [FIX 2026-07-11, achado real testando "SA via web"] sem `encoding`
        # explícito, `text=True` usa `locale.getpreferredencoding()` — nesta
        # máquina Windows isso é cp1252, e o headless (como quase todo o
        # resto do repo) imprime acentos/emojis em UTF-8. Byte inválido em
        # cp1252 derruba a THREAD de leitura do stdout/stderr do subprocess.
        proc = subprocess.run(
            cmd, cwd=str(settings.repo_root), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            # Uma rodada SA completa renderiza centenas de fichas e pode
            # legitimamente ultrapassar uma hora. O headless ja serializa a
            # execucao com lock + ``--wait``; matar um processo que continua
            # progredindo deixa o pacote final incompleto. Por isso o SA
            # canonico nao recebe timeout artificial do wrapper web.
            timeout=None,
        )
    except subprocess.TimeoutExpired:
        return ResultadoEtapa(etapa=etapa, ok=False, comando=cmd, returncode=None,
                              log_tail="timeout do subprocess")
    except OSError as exc:
        return ResultadoEtapa(etapa=etapa, ok=False, comando=cmd, returncode=None,
                              log_tail=f"erro ao iniciar subprocess: {exc}")

    saida = banner + (proc.stdout or "") + "\n" + (proc.stderr or "")
    if log_path is not None:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            Path(log_path).write_text(saida, encoding="utf-8", errors="replace")
        except OSError:
            pass

    obra_dir = _obra_dir(settings, obra)
    artefatos = {
        "obra_dir": str(obra_dir),
        "fase6_dir": str(obra_dir / "Fase-6_Execucao_CAD"),
    }
    # O headless gera o snapshot N1 e as prÃ©vias N3 na mesma rodada. Assim
    # que ele termina, materializa tambÃ©m o contrato editÃ¡vel de TODOS os
    # pilares para que a primeira abertura da tela nÃ£o seja responsÃ¡vel por
    # criar dados. Overrides humanos existentes sÃ£o preservados.
    posprocessamento_ok = True
    if proc.returncode == 0 and '--sa-only' in cmd:
        try:
            secoes_cmd = [cmd[i + 1] for i, value in enumerate(cmd[:-1]) if value == '--secao']
            itens_cmd = [cmd[i + 1] for i, value in enumerate(cmd[:-1]) if value == '--item']
            snapshot = promover_snapshot_sa(
                obra_dir, str(pav or settings.pav_default), iniciado_em=iniciado_em,
                secao=secoes_cmd[0] if len(secoes_cmd) == 1 else None,
                item_names=set(itens_cmd),
            )
            if snapshot is None:
                raise RuntimeError('o SA terminou sem publicar um estado N1 valido desta rodada')
            artefatos['estado_n1'] = str(snapshot)
            memoria = aplicar_memoria_arete_pilares(
                settings, obra, project_id=project_id, pavimento=str(pav or settings.pav_default),
            )
            artefatos['memoria_arete_pilares'] = memoria
            if memoria.get('status') not in {'aplicada', 'sem_referencia'}:
                raise RuntimeError('memoria Arete PIL indisponivel: ' + str(memoria))
            if not secoes_cmd or 'pilares' in secoes_cmd:
                artefatos['pilar_n1_tags'] = materializar_n1_tags_pilares(
                    settings, obra, project_id=project_id,
                    pavimento=str(pav or settings.pav_default), itens=itens_cmd,
                )
                artefatos.setdefault('item_pending', []).extend(
                    artefatos['pilar_n1_tags'].get('item_pending', []))
            # Gate CAD pós-SA também no SA sem N3 (o botão SA do portal); só avisa.
            from .qa_cad_gate_run import best_effort as gate_cad_best_effort
            gate_path = gate_cad_best_effort(
                obra_dir, str(pav or settings.pav_default),
                secao=secoes_cmd[0] if len(secoes_cmd) == 1 else None,
                item_names=set(itens_cmd) or None,
            )
            artefatos['qa_cad_gate'] = str(gate_path) if gate_path else None
            if gate_path:
                saida += f'\n[portal] GATE CAD pós-SA: {gate_path.name}\n'
            saida += '\n[portal] SA/N1 publicado; N3 nao solicitado.\n'
        except Exception as exc:
            posprocessamento_ok = False
            log.exception('falha ao publicar SA/N1')
            artefatos['n1_errors'] = [str(exc)]
            saida += f'\n[portal] POS-PROCESSAMENTO SA/N1 FALHOU: {exc}\n'
        if log_path is not None:
            Path(log_path).write_text(saida, encoding='utf-8', errors='replace')
        return ResultadoEtapa(
            etapa=etapa, ok=posprocessamento_ok, comando=cmd,
            returncode=proc.returncode, log_tail=_tail(saida), artefatos=artefatos,
        )
    if proc.returncode == 0 and etapa in {"sa", "sa_item", "n3"}:
        import time as _time
        # Pós-etapas no processo do portal: tempo por etapa vai ao log do job.
        perf_marcas = [("inicio", _time.monotonic())]
        try:
            from src.core.pillar_n3_ficha import materialize_pavimento

            secoes_cmd = [
                cmd[index + 1] for index, value in enumerate(cmd[:-1])
                if value == "--secao"
            ]
            itens_cmd = [
                cmd[index + 1] for index, value in enumerate(cmd[:-1])
                if value == "--item"
            ]

            snapshot = promover_snapshot_sa(
                obra_dir, str(pav or settings.pav_default), iniciado_em=iniciado_em,
                secao=secoes_cmd[0] if len(secoes_cmd) == 1 else None,
                item_names=set(itens_cmd),
            )
            if snapshot is None:
                raise RuntimeError("o SA terminou sem publicar um estado N1 valido desta rodada")
            artefatos["estado_n1"] = str(snapshot)
            perf_marcas.append(("promover_snapshot", _time.monotonic()))
            if not secoes_cmd or "laterais_viga" in secoes_cmd:
                from .lv_n3_cuts import materialize_pavimento as materialize_lv_cuts
                from .lv_n3_panels import materialize_pavimento as materialize_lv_panels
                modes = [cmd[index + 1] for index, value in enumerate(cmd[:-1])
                         if value == "--visual-mode"]
                from .ficha_reader import estado_compartilhado
                # Cortes e painéis consomem o mesmo estado efetivo desta rodada.
                with estado_compartilhado():
                    cut_stats = materialize_lv_cuts(
                        obra_dir, str(pav or settings.pav_default),
                        mode=modes[0] if modes else "NOVA", item_names=itens_cmd,
                        max_workers=3,
                    )
                    artefatos["lv_n3_cuts"] = cut_stats
                    panel_stats = materialize_lv_panels(
                        obra_dir, str(pav or settings.pav_default),
                        mode=modes[0] if modes else "NOVA", item_names=itens_cmd,
                        max_workers=3,
                    ) if not modes or modes[0] in ("NOVA","MOLDE_1","INI") else dict(errors=[],generated=0,expected=0)
                artefatos["lv_n3_panels"] = panel_stats
                perf_marcas.append(("lv_cortes_paineis", _time.monotonic()))
                saida += (f"\n[portal] LV VISAO CORTE: {cut_stats['generated']}/"
                          f"{cut_stats['expected']} cortes; {cut_stats['beams']} "
                          f"vigas/comportamentos; modo={cut_stats['visual_mode']}\n")
                if cut_stats['errors'] or panel_stats['errors']:
                    artefatos.setdefault('item_pending', []).extend(cut_stats['errors']+panel_stats['errors'])
            memoria_arete = aplicar_memoria_arete_pilares(
                settings, obra, project_id=project_id,
                pavimento=str(pav or settings.pav_default),
            )
            artefatos["memoria_arete_pilares"] = memoria_arete
            perf_marcas.append(("memoria_arete_pil", _time.monotonic()))
            if memoria_arete.get("status") not in {"aplicada", "sem_referencia"}:
                raise RuntimeError(
                    "memoria Arete PIL indisponivel: " + str(memoria_arete)
                )
            ficha_stats = materialize_pavimento(
                obra_dir, str(pav or settings.pav_default),
            )
            artefatos["pilar_n3_fichas"] = ficha_stats
            perf_marcas.append(("fichas_pil_n3", _time.monotonic()))
            if ficha_stats.get("errors"):
                artefatos.setdefault('item_pending', []).extend(ficha_stats['errors'])

            # SA completo (sem --secao) ou uma solicitacao explicita de pilares
            # so conclui quando PARA e PASSA possuem contrato + ABCD + GRADES.
            pilares_solicitados = not secoes_cmd or "pilares" in secoes_cmd
            if pilares_solicitados:
                n3_stats = auditar_pacote_pilares_n3(
                    obra_dir, str(pav or settings.pav_default),
                )
                artefatos["pilar_n3"] = n3_stats
                if n3_stats["missing"]:
                    artefatos.setdefault('item_pending', []).extend(n3_stats['missing'])
                    saida += '\n[portal] pacote N3 de pilares incompleto; pendências por item: ' + '; '.join(n3_stats['missing']) + '\n'
                try:
                    artefatos["pilar_n1_tags"] = materializar_n1_tags_pilares(
                        settings, obra, project_id=project_id,
                        pavimento=str(pav or settings.pav_default), itens=itens_cmd,
                    )
                except Exception as exc:
                    # Do not publish a failed pack or cancel unrelated outputs.
                    log.exception("publicação N1 PIL pendente")
                    artefatos["pilar_n1_tags"] = {
                        "status": "pendente", "pack": None,
                        "item_pending": [f"PIL/N1 publicação: {exc}"],
                    }
                    saida += f"\n[portal] PUBLICAÇÃO N1 PIL PENDENTE: {exc}\n"
                artefatos.setdefault('item_pending', []).extend(
                    artefatos['pilar_n1_tags'].get('item_pending', []))
            perf_marcas.append(("pacote_e_tags_pil", _time.monotonic()))
            # Gate CAD pós-SA: mede no DXF original e só avisa (nunca derruba o job).
            # Na cadeia completa roda em fundo, junto do N5 (gate_cad_em_fundo).
            gate_path = _gate_cad(
                log_path, obra_dir, str(pav or settings.pav_default),
                secao=secoes_cmd[0] if len(secoes_cmd) == 1 else None,
                item_names=set(itens_cmd) or None,
            )
            artefatos["qa_cad_gate"] = str(gate_path) if gate_path else None
            if gate_path:
                saida += f"\n[portal] GATE CAD pós-SA: {gate_path.name}\n"
            perf_marcas.append(("gate_cad", _time.monotonic()))
            log.info("fichas PIL N1/N3 materializadas: %s", ficha_stats)
        except Exception as exc:
            posprocessamento_ok = False
            log.exception("falha ao materializar fichas PIL N1/N3")
            artefatos.setdefault("pilar_n3_fichas", {"errors": []})
            artefatos["pilar_n3_fichas"].setdefault("errors", []).append(str(exc))
            saida += f"\n[portal] POS-PROCESSAMENTO SA/N1/N3 FALHOU: {exc}\n"
        saida += "\n" + "".join(
            f"[portal][PERF] {nome}: {fim - ini:.1f}s\n"
            for (_, ini), (nome, fim) in zip(perf_marcas, perf_marcas[1:]))
    if proc.returncode == 0 and '--production-web' in cmd and '--sa-only' not in cmd:
        try:
            manifest, failures = auditar_manifesto_n3_da_rodada(proc.stdout or '', obra_dir)
            artefatos['production_manifest'] = str(manifest)
            artefatos['n3_errors'] = failures
            if failures:
                artefatos.setdefault('item_pending', []).extend(failures)
                saida += '\n[portal] N3 COM PENDÊNCIAS POR ITEM: ' + '; '.join(failures) + '\n'
        except Exception as exc:
            posprocessamento_ok = False
            artefatos['n3_errors'] = [str(exc)]
            saida += f'\n[portal] AUDITORIA N3 FALHOU: {exc}\n'
    if artefatos.get('item_pending') and artefatos.get('production_manifest'):
        ledger = Path(artefatos['production_manifest']).with_name('item_pending.json')
        ledger.write_text(json.dumps(dict(pavimento=pav, items=artefatos['item_pending']), ensure_ascii=False, indent=2), encoding='utf8')
        artefatos['pending_manifest'] = str(ledger)
    if log_path is not None:
        try:
            Path(log_path).write_text(saida, encoding="utf-8", errors="replace")
        except OSError:
            log.exception("falha ao persistir log do pos-processamento SA")
    return ResultadoEtapa(
        etapa=etapa, ok=(proc.returncode == 0 and posprocessamento_ok), comando=cmd,
        returncode=proc.returncode, log_tail=_tail(saida), artefatos=artefatos,
    )


def executar_microciclo_item(
    settings: Settings,
    obra: dict,
    *,
    secao: str,
    item: str,
    pav: Optional[str] = None,
    dry_run: bool = True,
    log_path: Optional[Path] = None,
    visual_mode: str = "NOVA",
    vigas_config: Optional[dict] = None,
) -> ResultadoEtapa:
    """P4 — headless de UMA classe + UM item com --persist-db (escape hatch).

    Entry point único: `scripts.arete.headless_sa_analise` com
    `--secao <classe> --item <id> --persist-db --wait`. Reusa o pipeline
    automático a partir do recorte já gravado pelo P3; o lock por classe
    isola o microciclo (docs/PERSISTENCIA-HEADLESS-SA.md).
    """
    secao_s = str(secao or "").strip()
    item_s = str(item or "").strip()
    if not secao_s:
        raise ValueError("secao obrigatoria no microciclo")
    if not item_s:
        raise ValueError("item obrigatorio no microciclo")

    pav_efetivo = pav or settings.pav_default
    if pav_efetivo == "Indeterminado":
        msg = "Documento sem pavimento (Docs Gerais). Análise estrutural SA ignorada."
        if log_path:
            try:
                Path(log_path).parent.mkdir(parents=True, exist_ok=True)
                Path(log_path).write_text(msg, encoding="utf-8")
            except OSError:
                pass
        return ResultadoEtapa(
            etapa="sa_item", ok=True, comando=[], dry_run=dry_run, log_tail=msg,
        )

    cmd = montar_comando_headless(
        settings, obra, secao=[secao_s], pav=pav_efetivo, item=[item_s],
        visual_mode=visual_mode, vigas_config=vigas_config,
    )
    return _rodar_subprocess_sa(
        settings, cmd, obra=obra, etapa="sa_item", dry_run=dry_run,
        log_path=log_path, pav=pav_efetivo,
    )


def regenerar_n3_cima_item(
    settings: Settings,
    obra: dict,
    *,
    item: str,
    pav: str,
    dry_run: bool = False,
    log_path: Optional[Path] = None,
    visual_mode: str = "NOVA",
    vista: str = "cima",
) -> ResultadoEtapa:
    """Regenera somente a vista N3 solicitada de um pilar.

    Este fluxo deliberadamente não chama o headless SA: os campos N1 e as
    variantes N3 já existem, e reler o DXF estrutural inteiro transformava
    uma operação de milissegundos em um job de dezenas de minutos.
    """
    item_s = str(item or "").strip().upper()
    if not item_s:
        raise ValueError("item obrigatorio na regeneracao N3")
    if vista not in {"cima", "abcd-para", "abcd-passa", "grades-para", "grades-passa"}:
        raise ValueError(f"vista N3 invalida: {vista!r}")
    zone = vista.split("-", 1)[0]
    modes = ("para", "passa") if vista == "cima" else (vista.split("-", 1)[1],)
    step = "n3_cima_item" if vista == "cima" else "n3_pilar_vista_item"
    visual_mode = str(visual_mode or "NOVA").strip().upper()
    if visual_mode not in {"INI", "NOVA", "MOLDE_1", "MOLDE_2", "MOLDE_3"}:
        raise ValueError(f"modo de desenho invalido: {visual_mode!r}")
    obra_dir = _obra_dir(settings, obra)
    from .ficha_reader import ler_estado_pavimento
    from src.core.pillar_sa_review import eligible, load as load_sa_review, apply_robot
    state = ler_estado_pavimento(obra_dir, pav) or {}
    pillar = next((p for p in state.get('pilares', []) if p.get('name') == item_s), None)
    if pillar and not eligible(pillar):
        from src.core.pillar_sa_review import generation_exclusion
        return ResultadoEtapa(etapa=step, ok=False, log_tail=generation_exclusion(pillar))
    fields = load_sa_review(obra_dir, pav, item_s)
    root = obra_dir / "Fase-6_Execucao_CAD" / "n3_variants"
    mode_root = obra_dir / "Fase-6_Execucao_CAD" / "n3_modes" / visual_mode / "pilares"
    command = [step, str(obra_dir), str(pav), item_s, vista, visual_mode]
    if dry_run:
        return ResultadoEtapa(etapa=step, ok=True, comando=command, dry_run=True)

    scripts_dir = Path(settings.repo_root) / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from gerar_pl_dxf_stog import generate_pilar_zone, setup_doc
    from visual_modes import apply_visual_mode
    from src.core import pillar_n3_ficha

    saved_root = pillar_n3_ficha.load_ficha(obra_dir, pav, item_s) or {}
    variants = saved_root.get("variants") if isinstance(saved_root.get("variants"), dict) else {}
    regenerated: list[str] = []
    try:
        for mode in modes:
            variant_dir = root / mode
            payload_path = variant_dir / f"{item_s}.json"
            if not payload_path.is_file():
                raise FileNotFoundError(f"variante N3 ausente: {payload_path}")
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            ficha = variants.get(mode) if isinstance(variants.get(mode), dict) else saved_root
            if isinstance(ficha, dict) and ficha:
                payload = pillar_n3_ficha.apply_ficha_to_robot(payload, ficha)
            payload = apply_robot(payload, fields)

            doc = setup_doc()
            count = generate_pilar_zone(
                doc.modelspace(), payload, zone, visual_mode=visual_mode,
            )
            if count < 0:
                raise RuntimeError(f"motor {zone} não gerou entidades para {item_s}/{mode}")
            apply_visual_mode(doc, visual_mode, "PL")
            payload.setdefault("_visual_modes", {})[zone] = visual_mode

            # Publica cumulativamente no diretório do modo. A ponte sem rótulo
            # continua significando NOVA; gravar INI nela faria consumidores
            # legados exibirem um desenho INI com etiqueta NOVA.
            target_dirs = [mode_root / mode]
            if visual_mode == "NOVA":
                target_dirs.append(variant_dir)
            for target_dir in target_dirs:
                target_dir.mkdir(parents=True, exist_ok=True)
                dxf_path = target_dir / f"PL_{zone.upper()}_preview_{item_s}.dxf"
                target_json = target_dir / f"{item_s}.json"
                fd, tmp_dxf_name = tempfile.mkstemp(
                    prefix=f".{dxf_path.stem}.", suffix=".dxf", dir=target_dir,
                )
                os.close(fd)
                tmp_dxf = Path(tmp_dxf_name)
                try:
                    doc.saveas(str(tmp_dxf))
                    os.replace(tmp_dxf, dxf_path)
                finally:
                    tmp_dxf.unlink(missing_ok=True)

                fd, tmp_json_name = tempfile.mkstemp(
                    prefix=f".{target_json.stem}.", suffix=".json", dir=target_dir,
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as stream:
                        json.dump(payload, stream, ensure_ascii=False, indent=2)
                        stream.write("\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(tmp_json_name, target_json)
                finally:
                    Path(tmp_json_name).unlink(missing_ok=True)
            regenerated.append(f"{mode}:{count}")
    except Exception as exc:
        message = f"regeneracao N3 {vista} falhou: {exc}"
        if log_path:
            Path(log_path).write_text(message, encoding="utf-8")
        return ResultadoEtapa(
            etapa=step, ok=False, comando=command,
            returncode=1, log_tail=message,
        )

    message = f"{item_s} N3 {vista} regenerado ({', '.join(regenerated)})"
    if log_path:
        Path(log_path).write_text(message, encoding="utf-8")
    return ResultadoEtapa(
        etapa=step, ok=True, comando=command,
        returncode=0, log_tail=message,
    )


def regenerar_n3_lv_vista_item(
    settings: Settings,
    obra: dict,
    *,
    beam: str,
    pav: str,
    behavior: str,
    view: str,
    visual_mode: str = "NOVA",
    vigas_config: Optional[dict] = None,
    dry_run: bool = False,
    log_path: Optional[Path] = None,
) -> ResultadoEtapa:
    """Gera uma vista LV de contratos SA + override, sem tocar na rodada SA."""
    from . import lv_n3_operations

    behavior, beam = lv_n3_operations._identity(behavior, beam)
    if view not in {"corte", "paineis-a", "paineis-b"}:
        raise ValueError("vista N3 LV inválida")
    visual_mode = str(visual_mode or "NOVA").upper()
    if visual_mode not in {"INI", "NOVA", "MOLDE_1", "MOLDE_2", "MOLDE_3"}:
        raise ValueError("modo de desenho N3 LV inválido")
    generator_view = {"corte": "CORTE", "paineis-a": "A", "paineis-b": "B"}[view]
    suffix = "CORTE" if view == "corte" else f"VIEW_{generator_view}"
    filename = f"LV_preview_{beam}_{behavior.title()}_{suffix}.dxf"
    obra_dir = _obra_dir(settings, obra)
    command = [
        sys.executable, str(Path(settings.repo_root) / "scripts" / "gerar_lv_dxf_stog.py"),
        "--obra", str(obra_dir), "--item", beam, "--behavior", behavior.title(),
        "--view", generator_view, "--visual-mode", visual_mode,
        "--stog-pav-hint", pav,
    ]
    if dry_run:
        return ResultadoEtapa(etapa="n3_lv_view_item", ok=True, comando=command, dry_run=True)
    try:
        if view == 'corte':
            from . import lv_ficha, lv_n3_cuts
            from .ficha_reader import ler_estado_pavimento
            state = ler_estado_pavimento(obra_dir, pav) or {}
            cuts = lv_ficha.montar_ficha_lv(obra_dir,pav,beam,behavior,state,include_svgs=False)['cut_views']
            if not cuts:
                raise RuntimeError('inventário SA de cortes vazio')
            blocked = [c['id'] for c in cuts if not c['layers']['n3_cut']['available']]
            if blocked:
                raise RuntimeError('contratos de corte incompletos: '+', '.join(blocked))
            from src.core.vigas_drawing_config import LV_ASSEMBLIES
            for cut in cuts:
                for assembly in LV_ASSEMBLIES:
                    lv_n3_cuts.resolve(obra_dir,pav,behavior,cut,visual_mode,assembly)
            message = f'{beam} {behavior}: {len(cuts)} cortes × 2 variantes N3 gerados do inventário SA'
            if log_path: Path(log_path).write_text(message,encoding='utf8')
            return ResultadoEtapa(etapa='n3_lv_view_item',ok=True,comando=command,returncode=0,log_tail=message)
        from . import lv_n3_panels
        results=lv_n3_panels.materialize(obra_dir,pav,behavior,beam,generator_view,visual_mode)
        from src.core.vigas_drawing_config import normalize_config
        selected=normalize_config(vigas_config)['comportamento_laterais_vigas']
        target_dir=obra_dir/'Fase-6_Execucao_CAD'/'n3_modes'/visual_mode/'lv'/behavior
        for assembly,result in results.items():
            destination=target_dir/pav/assembly/filename
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(result['path'],destination)
            if assembly==selected:
                target_dir.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(result['path'],target_dir/filename)
        message=f"{beam} {behavior} N3 {view}: gradeadas e sarrafeadas geradas"
    except Exception as exc:
        message = f"regeneração N3 LV falhou: {exc}"
        if log_path:
            Path(log_path).write_text(message, encoding="utf-8")
        return ResultadoEtapa(
            etapa="n3_lv_view_item", ok=False, comando=command,
            returncode=1, log_tail=message,
        )
    if log_path:
        Path(log_path).write_text(message, encoding="utf-8")
    return ResultadoEtapa(
        etapa="n3_lv_view_item", ok=True, comando=command,
        returncode=0, log_tail=message,
    )


def _garantir_project_registrado(
    settings: Settings, obra: dict, pavimento: str,
) -> Optional[str]:
    from src.core.database import DatabaseManager
    from ..db import connection as db_conn
    import sqlite3

    obra_dir = _obra_dir(settings, obra)
    work_name = str(obra_dir)
    database = DatabaseManager(db_path=str(settings.sa_db_path))

    dxf_path = None
    try:
        # [FIX CRITICO] `settings.db_path` e' None por padrao (so' fixtures de
        # teste passam um valor real) — `sqlite3.connect(str(None))` conecta
        # literalmente num arquivo chamado "None" (cria vazio na hora), entao
        # esta consulta SEMPRE falhava com "no such table: portal_documentos"
        # em producao. Resultado real observado: TODO pavimento caia no
        # fallback abaixo, que sempre devolve o mesmo arquivo (o primeiro em
        # ordem alfabetica na pasta entrada/) — SA analisava sempre o MESMO
        # DXF errado (o de localizacao geral) pra qualquer pavimento pedido.
        db_path_real = settings.db_path or db_conn.DEFAULT_DB_PATH
        conn = sqlite3.connect(str(db_path_real))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT arquivo_nome FROM portal_documentos WHERE obra_id = ? AND COALESCE(pavimento_confirmado, pavimento_sugerido) = ? ORDER BY arquivo_nome ASC",
            (obra.get("id"), pavimento)
        ).fetchall()
        for doc in rows:
            if doc and doc["arquivo_nome"]:
                nome = doc["arquivo_nome"]
                if nome.lower().endswith(".dwg") or nome.lower().endswith(".dxf"):
                    # [FIX] a conversao ODA (accoreconsole) grava
                    # "<stem>_R2018_ASCII_ODA.dxf" — nunca "<stem>.dxf" puro.
                    # O `.with_suffix('.dxf')` so' acertava por coincidencia
                    # quando um .dxf sem sufixo TAMBEM existia por fora; o
                    # "fallback" checava o sufixo no nome ORIGINAL (quase
                    # sempre o .dwg), que nunca carrega esse sufixo — so' o
                    # .dxf convertido carrega. Procura por prefixo (stem*.dxf)
                    # em vez de adivinhar o nome exato.
                    stem = Path(nome).stem
                    entrada_dir = obra_dir / "entrada"
                    candidato = entrada_dir / nome if nome.lower().endswith('.dxf') else entrada_dir / f"{stem}.dxf"
                    if candidato.is_file():
                        dxf_path = candidato
                    else:
                        from .recortes_reader import stem_bruto_canonico
                        achados = sorted(p for p in entrada_dir.iterdir()
                            if p.is_file() and p.suffix.lower() == '.dxf'
                            and stem_bruto_canonico(p.stem).casefold() == stem_bruto_canonico(stem).casefold())
                        if achados:
                            dxf_path = achados[0]
                    if dxf_path:
                        break
    except Exception as e:
        print("Erro ao buscar documento para registrar project:", e)
    finally:
        if 'conn' in locals():
            conn.close()

    if not dxf_path:
        # Um pavimento selecionado nunca pode usar o documento principal de
        # outro pavimento como fallback. A falta da fonte exata é um erro.
        return None

    if not dxf_path or not dxf_path.is_file():
        return None

    # [novo, a pedido do dono] SA deve analisar o MESMO arquivo que a app
    # desktop usa pra esta obra/pavimento: o recorte "Torre 1" (motor DBSCAN,
    # scripts/obra_crop_engine.py — o mesmo que ja alimenta "Recortes Torres
    # Limpas" na Triagem do portal), nao o bruto puro. O bruto tem ruido real
    # (bloco de titulo, cotas/textos fora da planta, entidades duplicadas)
    # que confunde a deteccao automatica de pilares/lajes — o recorte ja
    # vem limpo, e' o que a obra de referencia na app (Obra_TREINO_1) usa de
    # verdade. So' cai pro bruto se o recorte ainda nao foi gerado (Triagem +
    # Recortes ainda nao rodou pra este bruto especifico).
    from . import torre_crop
    # [FIX] a pasta de recorte e' sempre nomeada com o stem do .dxf REAL
    # convertido (com o sufixo "_R2018_ASCII_ODA"), mas `dxf_path` acima pode
    # ter batido no .dxf SEM esse sufixo (quando os dois existem soltos na
    # pasta entrada/, como acontece pra varios brutos desta obra) — usar
    # `dxf_path.stem` direto perdia o recorte por causa dessa diferenca de
    # nome. Tenta o stem exato primeiro, senao procura por prefixo.
    recortes_dir = obra_dir / "Fase-2_Triagem" / "recortes"
    torre_1 = torre_crop._dir_recortes_bruto(obra_dir, dxf_path.stem) / "torre_1.dxf"
    if not torre_1.is_file() and recortes_dir.is_dir():
        for pasta in sorted(recortes_dir.glob(f"{dxf_path.stem}*")):
            candidato_torre = pasta / "torre_1.dxf"
            if candidato_torre.is_file():
                torre_1 = candidato_torre
                break
    if torre_1.is_file():
        dxf_path = torre_1

    try:
        # [FIX] `DatabaseManager` nao guarda conexao persistente em
        # `.conn`/`.cursor` (AttributeError sempre, silenciosamente engolido
        # pelo except) — cada operacao abre a propria conexao via
        # `_get_conn()`, mesmo padrao que `create_project()` ja usa.
        vconn = database._get_conn()
        row = vconn.execute(
            "SELECT id, dxf_path FROM projects WHERE work_name = ? AND name = ? "
            "ORDER BY rowid DESC LIMIT 1",
            (work_name, pavimento),
        ).fetchone()
        if row:
            from .recortes_reader import stem_bruto_canonico
            def bruto_key(path):
                path = Path(path)
                name = path.parent.name if path.parent.parent.name == 'recortes' else path.stem
                return stem_bruto_canonico(name).casefold()
            if bruto_key(row[1]) != bruto_key(dxf_path):
                # Outra fonte: preserve o projeto anterior e crie análise
                # limpa. Não mesclar dados estruturais de desenhos distintos.
                row = None
        if row:
            project_id = str(row[0])
            vconn.execute(
                "UPDATE projects SET dxf_path = ? WHERE id = ?",
                (str(dxf_path), project_id),
            )
            vconn.commit()
            vconn.close()
            return project_id

        vconn.close()
        project_id = database.create_project(
                name=pavimento, dxf_path=str(dxf_path),
                work_name=work_name, pavement_name=pavimento,
        )
        return str(project_id) if project_id else None
    except Exception as e:
        print("Erro ao atualizar project.vision:", e)
        return None


def _tail(texto: str, linhas: int = 40) -> str:
    return "\n".join((texto or "").splitlines()[-linhas:])


_EXT_DWG = ".dwg"
_CLASSES_RECORTE = ("PIL", "LV", "FV", "LAJ")


def _arquivo_entrada(obra_dir: Path, obra: dict) -> Optional[Path]:
    """Localiza o arquivo original da obra dentro de obra_dir/entrada/ (poller)."""
    nome = obra.get("arquivo_nome")
    if nome:
        candidato = obra_dir / "entrada" / nome
        if candidato.exists():
            return candidato
    pasta = obra_dir / "entrada"
    if pasta.exists():
        achados = sorted(pasta.glob("*.dwg")) + sorted(pasta.glob("*.dxf"))
        if achados:
            return achados[0]
    return None


def _converter_e_validar_um(entrada: Path) -> tuple[bool, str, Optional[Path]]:
    """Conversao DWG->DXF (se preciso) + sanidade ezdxf de UM arquivo (R6).

    Retorna (ok, log, dxf_path). Extraido de executar_triagem() em 2026-07-06
    pra ser reusado tambem por executar_triagem_documentos() (obra com N docs)
    sem duplicar a logica de conversao/sanidade.
    """
    dxf_path = entrada
    linhas: list[str] = []

    if entrada.suffix.lower() == _EXT_DWG:
        dxf_path = entrada.with_suffix(".dxf")
        try:
            from scripts.converter_dwg_dxf_accore import convert_dwg_to_dxf  # type: ignore
        except ImportError as exc:
            return False, f"conversor DWG->DXF indisponivel: {exc}", None
        motor = "accoreconsole" if os.name == "nt" else "ODA File Converter"
        linhas.append(f"convertendo {entrada.name} -> {dxf_path.name} via {motor}")
        try:
            ok = convert_dwg_to_dxf(entrada, dxf_path)
        except Exception as exc:  # noqa: BLE001 - conversores externos podem falhar
            return False, "\n".join(linhas + [f"conversao DWG->DXF falhou: {exc}"]), None
        if not ok:
            return False, "\n".join(linhas + ["conversao retornou falha"]), None

    try:
        import ezdxf

        doc = ezdxf.readfile(str(dxf_path))
        n_entidades = len(doc.modelspace())
        linhas.append(f"sanidade ezdxf OK: {dxf_path.name} ({n_entidades} entidades)")
    except Exception as exc:  # noqa: BLE001 - ezdxf levanta varios tipos de erro de parse
        return False, "\n".join(linhas + [f"sanidade ezdxf falhou: {exc}"]), None

    return True, "\n".join(linhas), dxf_path


def executar_triagem(
    settings: Settings, obra: dict, *, dry_run: bool = True, log_path: Optional[Path] = None,
) -> ResultadoEtapa:
    """Etapa 2 (LEGADO — obra de arquivo único, sem portal_documentos).

    [2026-07-06] Mantida so' para obras criadas ANTES da migration 002
    (modelo "1 obra = 1 arquivo"). Obras novas (POST /obras/criar) usam
    executar_triagem_documentos() — a obra vira container de N documentos.
    """
    obra_dir = _obra_dir(settings, obra)
    entrada = _arquivo_entrada(obra_dir, obra)
    comando_desc = ["triagem(conversao+sanidade)", str(obra_dir)]
    if dry_run:
        return ResultadoEtapa(etapa="triagem", ok=True, dry_run=True, comando=comando_desc)

    if entrada is None:
        msg = f"nenhum arquivo .dwg/.dxf encontrado em {obra_dir / 'entrada'}"
        return ResultadoEtapa(etapa="triagem", ok=False, comando=comando_desc, log_tail=msg)

    ok, texto, dxf_path = _converter_e_validar_um(entrada)
    if not ok:
        return ResultadoEtapa(etapa="triagem", ok=False, comando=comando_desc, log_tail=texto)

    if log_path is not None:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            Path(log_path).write_text(texto, encoding="utf-8", errors="replace")
        except OSError:
            pass

    return ResultadoEtapa(
        etapa="triagem", ok=True, comando=comando_desc, returncode=0,
        log_tail=_tail(texto), artefatos={"dxf_entrada": str(dxf_path)},
    )


def executar_triagem_documentos(
    settings: Settings,
    obra: dict,
    documentos: list[dict],
    *,
    dry_run: bool = True,
    log_path: Optional[Path] = None,
) -> ResultadoEtapa:
    """Etapa 2 (NOVO MODELO — obra container, 2026-07-06): triagem de N documentos.

    Roda conversao+sanidade (mesmo `_converter_e_validar_um`) para CADA documento
    pendente da obra — um falhar nao impede os outros de rodarem (R6: quarentena
    por item, nao pela obra inteira). O chamador (jobs.py) aplica o resultado por
    documento via repository.atualizar_classificacao_documento (esta funcao so'
    devolve os resultados, nao escreve no DB — pipeline_runner nao conhece o repo).
    """
    obra_dir = _obra_dir(settings, obra)
    comando_desc = ["triagem_documentos", str(obra_dir), f"n_docs={len(documentos)}"]
    if dry_run:
        return ResultadoEtapa(etapa="triagem", ok=True, dry_run=True, comando=comando_desc)

    resultados: list[dict] = []
    linhas_log: list[str] = []
    for doc in documentos:
        entrada = obra_dir / "entrada" / doc["arquivo_nome"]
        if not entrada.exists():
            resultados.append({"doc_id": doc["id"], "ok": False,
                              "erro_msg": f"arquivo nao encontrado em disco: {entrada}"})
            linhas_log.append(f"{doc['arquivo_nome']}: ARQUIVO AUSENTE")
            continue
        # [2026-07-07] PDF (material de referência, tipo_documento="PDF") não
        # entra no pipeline DXF — conversão/sanidade ezdxf não se aplica (não
        # é DWG/DXF). Marca ok direto, sem tentar converter/validar.
        if entrada.suffix.lower() == ".pdf":
            resultados.append({"doc_id": doc["id"], "ok": True, "dxf_path": None, "erro_msg": None})
            linhas_log.append(f"{doc['arquivo_nome']}: PDF (referência, sem conversão/sanidade)")
            continue
        ok, texto_doc, dxf_path = _converter_e_validar_um(entrada)
        linhas_log.append(f"--- {doc['arquivo_nome']} ---\n{texto_doc}")
        resultados.append({
            "doc_id": doc["id"], "ok": ok,
            "dxf_path": str(dxf_path) if dxf_path else None,
            "erro_msg": None if ok else texto_doc[:300],
        })

    texto_completo = "\n".join(linhas_log)
    if log_path is not None:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            Path(log_path).write_text(texto_completo, encoding="utf-8", errors="replace")
        except OSError:
            pass

    # sucesso "geral" = pelo menos 1 documento processou — falhas individuais
    # viram status='erro' NAQUELE documento (quarentena por item, R6), nao
    # derrubam a obra inteira; se documentos estava vazio, nao ha' nada a fazer.
    ok_geral = any(r["ok"] for r in resultados) if resultados else True
    return ResultadoEtapa(
        etapa="triagem", ok=ok_geral, comando=comando_desc,
        log_tail=_tail(texto_completo), artefatos={"documentos": resultados},
    )


def listar_dwgs_com_status(settings: Settings, obra: dict, documentos: list[dict]) -> list[dict]:
    """[2026-07-08, a pedido do dono] Lista só os documentos .dwg da obra, cada
    um com `tem_dxf` (bool) — checado em DISCO, mesma convenção de sempre
    (`<obra_dir>/entrada/<stem>.dxf`, ver `_entrada_dxf` em recortes_routes.py),
    não em campo de banco (não existe um; a conversão é 100% arquivo-a-arquivo)."""
    obra_dir = _obra_dir(settings, obra)
    entrada_dir = obra_dir / "entrada"
    saida = []
    fontes = list(documentos)
    arquivo_rapido = str(obra.get("arquivo_nome") or "")
    if arquivo_rapido.lower().endswith(_EXT_DWG) and not fontes:
        fontes.append({"id": None, "arquivo_nome": arquivo_rapido, "nome_exibicao": None})
    for doc in fontes:
        if not doc["arquivo_nome"].lower().endswith(_EXT_DWG):
            continue
        dxf_path = entrada_dir / Path(doc["arquivo_nome"]).with_suffix(".dxf").name
        saida.append({
            "doc_id": doc["id"], "arquivo_nome": doc["arquivo_nome"],
            "nome_exibicao": doc.get("nome_exibicao"), "tem_dxf": dxf_path.is_file(),
        })
    return saida


def executar_conversao_dwg(
    settings: Settings,
    obra: dict,
    documentos: list[dict],
    *,
    dry_run: bool = True,
    log_path: Optional[Path] = None,
) -> ResultadoEtapa:
    """Conversão avulsa DWG->DXF (a pedido do dono, 2026-07-08): converte de uma
    vez só todo DWG da obra que ainda não tem DXF equivalente em disco — reusa
    o MESMO conversor real da ingestão/triagem (`_converter_e_validar_um`, que
    por sua vez chama `scripts.converter_dwg_dxf_accore.convert_dwg_to_dxf`),
    só que disparável isoladamente, sem rodar classificação/sanidade completa
    de novo nos que já converteram. Sequencial (accoreconsole não paraleliza —
    mesma trava de máquina inteira que triagem/recortes já usam, ver jobs.py).
    """
    obra_dir = _obra_dir(settings, obra)
    entrada_dir = obra_dir / "entrada"
    fontes = list(documentos)
    arquivo_rapido = str(obra.get("arquivo_nome") or "")
    if arquivo_rapido.lower().endswith(_EXT_DWG) and not fontes:
        fontes.append({"id": None, "arquivo_nome": arquivo_rapido})
    pendentes = [d for d in fontes if d["arquivo_nome"].lower().endswith(_EXT_DWG)
                 and not (entrada_dir / Path(d["arquivo_nome"]).with_suffix(".dxf").name).is_file()]
    comando_desc = ["conversao_dwg_dxf", str(obra_dir), f"n_pendentes={len(pendentes)}"]
    if dry_run:
        return ResultadoEtapa(etapa="converter_dwg", ok=True, dry_run=True, comando=comando_desc)

    resultados: list[dict] = []
    linhas_log: list[str] = []
    for doc in pendentes:
        entrada = entrada_dir / doc["arquivo_nome"]
        if not entrada.exists():
            resultados.append({"doc_id": doc["id"], "ok": False, "erro_msg": "arquivo dwg nao encontrado em disco"})
            linhas_log.append(f"{doc['arquivo_nome']}: ARQUIVO AUSENTE")
            continue
        ok, texto_doc, dxf_path = _converter_e_validar_um(entrada)
        linhas_log.append(f"--- {doc['arquivo_nome']} ---\n{texto_doc}")
        resultados.append({
            "doc_id": doc["id"], "ok": ok,
            "dxf_path": str(dxf_path) if dxf_path else None,
            "erro_msg": None if ok else texto_doc[:300],
        })

    texto_completo = "\n".join(linhas_log) if linhas_log else "nenhum DWG pendente de conversao"
    if log_path is not None:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            Path(log_path).write_text(texto_completo, encoding="utf-8", errors="replace")
        except OSError:
            pass

    ok_geral = all(r["ok"] for r in resultados) if resultados else True
    return ResultadoEtapa(
        etapa="converter_dwg", ok=ok_geral, comando=comando_desc,
        log_tail=_tail(texto_completo), artefatos={"documentos": resultados},
    )


def executar_recortes(
    settings: Settings,
    obra: dict,
    *,
    dry_run: bool = True,
    log_path: Optional[Path] = None,
    target_dxf_paths: Optional[list[str]] = None,
) -> ResultadoEtapa:
    """Etapa 3: 2 motores reais, propositos DIFERENTES (achado ao vivo com o
    dono 2026-07-07 — a aba Recortes do portal mostrava so' o motor errado):

    1. `RecorteMotor` (src/core/recorte_motor.py) — recorte POR ELEMENTO
       estrutural (1 arquivo por pilar/viga/laje), classes PIL/LV/FV/LAJ.
       Usado pelo pipeline de engenharia reversa (scripts/engrev_laj_recorte_loop.py)
       pra treinar o SA — NAO e' pensado pra revisao humana (uma obra de 13
       pavimentos gera 31 arquivos so' de laje).
    2. `scripts/obra_crop_engine` (torre_crop.py) — recorte da OBRA INTEIRA
       em torre(s) limpa(s) + detalhes/convencoes unificados (DBSCAN por
       densidade). Esse e' o que a aba Recortes do portal REALMENTE precisa
       mostrar pro usuario revisar (poucos itens, cada um a planta inteira).

    Ambos rodam (nenhum efeito colateral entre eles — dirs de saida
    diferentes); a UI so' le' o (2).
    """
    obra_dir = _obra_dir(settings, obra)
    output_dir = obra_dir / "Fase-2_Triagem" / "recortes_reversos"
    comando_desc = ["RecorteMotor.run+obra_crop_engine", str(obra_dir), "classes=" + ",".join(_CLASSES_RECORTE)]
    if target_dxf_paths is not None:
        comando_desc.append(f"n_alvos={len(target_dxf_paths)}")
    if dry_run:
        return ResultadoEtapa(etapa="recortes", ok=True, dry_run=True, comando=comando_desc)

    entrada_dir = (obra_dir / "entrada").resolve()
    alvos: list[Path] = []
    if target_dxf_paths is not None:
        # O metadado vem do resultado da triagem, mas ainda assim falha fechado:
        # recortes só podem ler DXFs existentes dentro da entrada desta obra.
        for raw_path in target_dxf_paths:
            candidato = Path(raw_path).resolve()
            if candidato.suffix.lower() != ".dxf" or candidato.parent != entrada_dir:
                continue
            if candidato.is_file() and candidato not in alvos:
                alvos.append(candidato)
    else:
        entrada = _arquivo_entrada(obra_dir, obra)
        dxf_path = entrada.with_suffix(".dxf") if entrada and entrada.suffix.lower() == _EXT_DWG else entrada
        if dxf_path is not None and dxf_path.exists():
            alvos.append(dxf_path.resolve())

    if not alvos:
        msg = f"nenhum DXF encontrado em {obra_dir / 'entrada'} — rode a triagem primeiro"
        return ResultadoEtapa(etapa="recortes", ok=False, comando=comando_desc, log_tail=msg)

    linhas_log: list[str] = []
    total_elementos = 0

    try:
        from src.core.recorte_motor import RecorteMotor
        for dxf_alvo in alvos:
            for classe in _CLASSES_RECORTE:
                try:
                    motor = RecorteMotor(str(dxf_alvo), er_type=classe)
                    resultados = motor.run(output_dir, overwrite=True)
                except Exception as exc:  # noqa: BLE001 - motor pode nao achar frame p/ essa classe
                    linhas_log.append(f"{dxf_alvo.name} · {classe}: erro ({exc})")
                    continue
                linhas_log.append(f"{dxf_alvo.name} · {classe}: {len(resultados)} elemento(s)")
                total_elementos += len(resultados)
    except ImportError as exc:
        linhas_log.append(f"RecorteMotor indisponivel: {exc}")

    from . import recortes_reader, torre_crop
    # [2026-07-07] roda torre_crop pra TODOS os brutos da obra (obra com N
    # documentos = N brutos em entrada/), não só o 1o — achado com o dono:
    # obra completa (multi-doc) precisa de 1 pasta de recortes por documento
    # na aba Recortes, cada um com sua(s) torre(s)+detalhes.
    if target_dxf_paths is not None:
        brutos = [
            {"bruto_id": caminho.stem, "nome": caminho.name}
            for caminho in alvos
        ]
    else:
        brutos = recortes_reader.listar_brutos_recorte(obra_dir)
        if not brutos:
            dxf_path = alvos[0]
            brutos = [{"bruto_id": dxf_path.stem, "nome": dxf_path.name}]
    torres_geradas = 0
    for bruto in brutos:
        bruto_path = (obra_dir / "entrada" / bruto["nome"])
        if not bruto_path.is_file():
            linhas_log.append(f"torre_crop [{bruto['bruto_id']}]: arquivo não encontrado")
            continue
        crop_result = torre_crop.gerar_recortes_bruto(obra_dir, bruto_path, bruto["bruto_id"], force=True)
        if crop_result.get("error"):
            linhas_log.append(f"torre_crop [{bruto['bruto_id']}]: {crop_result['error']}")
        else:
            n_torres = len(crop_result.get("torres") or [])
            tem_detalhes = crop_result.get("detalhes") is not None
            torres_geradas += n_torres
            linhas_log.append(
                f"torre_crop [{bruto['bruto_id']}]: {n_torres} torre(s), detalhes={'sim' if tem_detalhes else 'nao'}"
            )

    texto = "\n".join(linhas_log)
    if log_path is not None:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            Path(log_path).write_text(texto, encoding="utf-8", errors="replace")
        except OSError:
            pass

    return ResultadoEtapa(
        etapa="recortes", ok=True, comando=comando_desc, returncode=0,
        log_tail=_tail(texto),
        artefatos={"recortes_dir": str(output_dir), "total_elementos": total_elementos,
                   "brutos_processados": len(brutos), "torres_geradas": torres_geradas},
    )


def executar_etapa(
    settings: Settings,
    etapa: str,
    obra: dict,
    *,
    secao: Optional[list[str]] = None,
    pav: Optional[str] = None,
    dry_run: bool = True,
    log_path: Optional[Path] = None,
    visual_mode: str = "NOVA",
    vigas_config: Optional[dict] = None,
) -> ResultadoEtapa:
    """Executa uma etapa de pipeline (triagem/recortes/sa).

    N5 NAO passa por aqui — usa executar_n5(). validacao NAO passa por aqui — so DB.
    dry_run=True devolve o comando sem disparar (default seguro para testes).

    triagem/recortes NAO chamam mais o headless (achado 2026-07-06 — eram o MESMO
    comando repetido 3x). So' 'sa' de fato dispara o subprocess pesado.
    """
    if etapa not in ETAPAS_SUBPROCESS:
        raise ValueError(f"etapa {etapa!r} nao e' de subprocess (validas: {ETAPAS_SUBPROCESS})")

    if etapa == "triagem":
        return executar_triagem(settings, obra, dry_run=dry_run, log_path=log_path)
    if etapa == "recortes":
        return executar_recortes(settings, obra, dry_run=dry_run, log_path=log_path)

    # etapa == "sa": unico caminho que dispara headless_sa_analise.py de verdade.
    pav_efetivo = pav or settings.pav_default
    if pav_efetivo == "Indeterminado":
        msg = "Documento sem pavimento (Docs Gerais). Análise estrutural SA ignorada."
        if log_path:
            try:
                Path(log_path).parent.mkdir(parents=True, exist_ok=True)
                Path(log_path).write_text(msg, encoding="utf-8")
            except OSError:
                pass
        return ResultadoEtapa(etapa=etapa, ok=True, comando=[], dry_run=dry_run, log_tail=msg)

    cmd = montar_comando_headless(
        settings, obra, secao=secao, pav=pav_efetivo, visual_mode=visual_mode, vigas_config=vigas_config,
        generate_n3=etapa == 'n3',
    )
    return _rodar_subprocess_sa(
        settings, cmd, obra=obra, etapa=etapa, dry_run=dry_run,
        log_path=log_path, pav=pav_efetivo,
    )


def executar_n5(
    settings: Settings,
    obra: dict,
    *,
    classe: str,
    pavimento: str = "GERAL",
    dry_run: bool = True,
    visual_mode: str = "NOVA",
    vigas_config: Optional[dict] = None,
) -> ResultadoEtapa:
    """Etapa 6: chama assemble_n5 (import direto, leve). Gera 1 DXF por classe+pav.

    dry_run=True nao importa nem escreve — so descreve a chamada.
    """
    obra_dir = _obra_dir(settings, obra)
    if dry_run:
        return ResultadoEtapa(
            etapa="n5", ok=True, dry_run=True,
            comando=["assemble_n5", str(obra_dir), classe, f"pavimento={pavimento}",
                     f"visual_mode={visual_mode}"],
        )
    try:
        from src.core.n5_assembler import assemble_n5  # import tardio: isola ezdxf
    except ImportError as exc:
        return ResultadoEtapa(etapa="n5", ok=False, log_tail=f"import assemble_n5 falhou: {exc}")

    try:
        from src.core.n5_assembler import n3_mode_readiness
        dual_laterals = classe.upper() == 'LV' and visual_mode in ('NOVA','MOLDE_1','INI')
        readiness = None if dual_laterals else n3_mode_readiness(obra_dir, classe, pavimento, visual_mode, settings.sa_db_path)
        lateral_parts = {}
        lateral_kwargs = {}
        if dual_laterals:
            from src.core.vigas_drawing_config import normalize_config
            if vigas_config is None:
                from portal.db.connection import get_connection
                from portal.db import repository as repository
                connection = get_connection(settings.db_path)
                try:
                    vigas_config = repository.obter_config_vigas_pavimento(connection, obra['id'], pavimento)
                finally:
                    connection.close()
            selected_assembly = normalize_config(vigas_config)['comportamento_laterais_vigas']
            lateral_kwargs = dict(lateral_assembly=selected_assembly, lateral_behavior='PARA')
        from src.core.n5_tasks import run_assembly_tasks
        common = dict(pavimento=pavimento, db_path=str(settings.sa_db_path),
                      visual_mode=visual_mode, project_metadata=obra, allow_partial=True)
        tasks = [('base', str(obra_dir), classe, dict(common, **lateral_kwargs))]
        if dual_laterals:
            for behavior in ('PARA', 'PASSA'):
                for assembly in ('gradeadas', 'sarrafeadas'):
                    if (behavior, assembly) != ('PARA', selected_assembly):
                        tasks.append((f'{behavior}/{assembly}', str(obra_dir), classe,
                                      dict(common, lateral_behavior=behavior,
                                           lateral_assembly=assembly)))
        if classe.upper() == 'PL':
            for group in ('PARA', 'PASSA'):
                tasks.append((group, str(obra_dir), classe, dict(common, pillar_group=group)))
        parts = dict(run_assembly_tasks(tasks))
        resultado = parts['base']
        if dual_laterals:
            for behavior in ('PARA', 'PASSA'):
                lateral_parts[behavior] = {}
                for assembly in ('gradeadas', 'sarrafeadas'):
                    part = resultado if (behavior, assembly) == ('PARA', selected_assembly) else parts[f'{behavior}/{assembly}']
                    if not part.ok_count:
                        continue
                    lateral_parts[behavior][assembly] = str(part.output_path)
        pillar_parts = {}
        if classe.upper() == "PL":
            for group in ("PARA", "PASSA"):
                part = parts[group]
                if not part.ok_count:
                    continue
                pillar_parts[group] = str(part.output_path)
    except Exception as exc:  # noqa: BLE001 - erro do assembler vira estado de job 'error'
        return ResultadoEtapa(etapa="n5", ok=False,
                              comando=["assemble_n5", str(obra_dir), classe],
                              log_tail=f"assemble_n5 erro: {exc}")

    dxf_path = str(resultado.output_path)
    artefatos = {
        "n5_dxf": dxf_path if resultado.ok_count else None,
        "n5_manifest": str(resultado.manifest_path),
        "pillar_parts": pillar_parts,
        "lateral_parts": lateral_parts,
        "ok_count": resultado.ok_count,
        "missing_count": resultado.missing_count,
        "extra_count": resultado.extra_count,
        "extra_ids": resultado.extra_ids,
    }
    artefatos["partial"] = any(part.missing_count for part in parts.values())
    artefatos["item_pending"] = [dict(variant=variant, **item.__dict__)
                                for variant, part in parts.items() for item in getattr(part, 'items', []) if item.status != "ok"]
    ok = resultado.ok_count > 0
    log_msg = None
    if resultado.missing_count > 0:
        log_msg = f"[WARNING/N5] Prancha gerada COM AUSÊNCIAS: {resultado.missing_count} item(ns) ausentes no disco!"
    return ResultadoEtapa(etapa="n5", ok=ok, comando=["assemble_n5", str(obra_dir), classe],
                          returncode=0 if ok else 1, artefatos=artefatos, log_tail=log_msg)
