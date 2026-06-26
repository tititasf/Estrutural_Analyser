#!/usr/bin/env python3
"""
batch_stog_validate.py — Roda os 4 geradores STOG + validação em todas as obras.
"""
import subprocess, sys, io, shutil, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SCRIPTS = Path(__file__).parent
DADOS   = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
PYTHON  = sys.executable
DISCOVERY = DADOS / "dxf_discovery.json"
TIPOS_STOG = ["PL", "LV", "FV", "LJ"]

# Carrega discovery uma vez
_disc = {}
if DISCOVERY.exists():
    try:
        _disc = json.loads(DISCOVERY.read_text(encoding="utf-8"))
    except Exception:
        pass


def best_pav(obra_name: str) -> str | None:
    """Retorna o pavimento com mais tipos STOG não-None (espelha lógica dos geradores)."""
    obra_data = _disc.get(obra_name, {})
    if not obra_data:
        return None
    best, best_count = None, -1
    for pav, tipos in obra_data.items():
        if not isinstance(tipos, dict):
            continue
        count = sum(1 for t in TIPOS_STOG if tipos.get(t) and str(tipos[t]) != "None")
        if count > best_count:
            best_count = count
            best = pav
    return best

OBRAS = sorted([
    d.name for d in DADOS.iterdir()
    if d.is_dir() and d.name.startswith("Obra_")
])

# map: generator script → output filename → target (gerado) filename
GENS = [
    ("gerar_pl_dxf_stog.py", "PL_stog_quality.dxf", "PL_gerado.dxf"),
    ("gerar_lv_dxf_stog.py", "LV_stog_quality.dxf",  "LV_gerado.dxf"),
    ("gerar_fv_dxf_stog.py", "FV_stog_quality.dxf", "FV_gerado.dxf"),
    ("gerar_lj_dxf_stog.py", "LJ_stog_quality.dxf", "LJ_gerado.dxf"),
]

results = {}

for obra in OBRAS:
    obra_path = DADOS / obra
    fase6 = obra_path / "Fase-6_Execucao_CAD"
    if not fase6.exists():
        print(f"[SKIP] {obra} — sem Fase-6")
        continue

    print(f"\n{'='*60}")
    print(f"  {obra}")
    print(f"{'='*60}")
    gen_ok = []

    for script, out_name, target_name in GENS:
        script_path = SCRIPTS / script
        if not script_path.exists():
            print(f"  [SKIP] {script} não encontrado")
            continue

        # Run generator
        r = subprocess.run(
            [PYTHON, str(script_path), "--obra", str(obra_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if r.returncode != 0:
            print(f"  [ERR ] {script}: {r.stderr[-200:].strip()}")
            continue

        # Find output and copy to target
        src = fase6 / out_name if out_name else None

        if src and src.exists():
            shutil.copy2(src, fase6 / target_name)
            print(f"  [OK ] {script} → {target_name}")
            gen_ok.append(target_name)
        else:
            print(f"  [WARN] {script} — output não encontrado ({out_name})")

    if not gen_ok:
        print(f"  [SKIP] nenhum gerador produziu saída")
        continue

    # Validate — escolhe melhor pavimento (mais tipos STOG disponíveis)
    pav = best_pav(obra)
    val_cmd = [PYTHON, str(SCRIPTS / "validar_visual_dxf.py"),
               "--obra", obra, "--sem-api"]
    if pav:
        val_cmd += ["--pav", pav]
        print(f"  [PAV ] usando: {pav}")
    val_r = subprocess.run(
        val_cmd,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS.parent)
    )

    # Parse score from output
    score_line = ""
    for line in val_r.stdout.splitlines():
        if "Consolidado" in line or "RESUMO" in line or "score=" in line:
            score_line += line.strip() + " | "
        if "score=" in line:
            print(f"  {line.strip()}")

    # Try to read consolidado JSON
    consolidado = Path(f"D:/Agente-cad-PYSIDE/validacao_visual/consolidado_{obra}.json")
    if consolidado.exists():
        try:
            data = json.loads(consolidado.read_text(encoding="utf-8"))
            # Structure: {pav_name: {score_pavimento: float, ...}, ...}
            scores = [v["score_pavimento"] for v in data.values()
                      if isinstance(v, dict) and "score_pavimento" in v]
            score = round(sum(scores) / len(scores), 1) if scores else "?"
            print(f"  >>> SCORE CONSOLIDADO: {score}")
            results[obra] = score
        except Exception as e:
            print(f"  [WARN] JSON parse: {e}")
    else:
        print(f"  [WARN] consolidado nao encontrado")

print("\n" + "="*60)
print("  RESUMO BATCH")
print("="*60)
for obra, score in sorted(results.items()):
    print(f"  {obra:<30} {score}")
print(f"\nTotal obras processadas: {len(results)}")
