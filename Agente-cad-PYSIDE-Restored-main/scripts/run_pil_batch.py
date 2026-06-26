#!/usr/bin/env python3
"""Run PIL fidelidade scorer for all obras."""
import subprocess, sys, re, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCRIPTS = Path(__file__).parent
DADOS = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
PYTHON = sys.executable

obras = sorted([d.name for d in DADOS.iterdir() if d.is_dir() and d.name.startswith("Obra_")])

results = []
for obra in obras:
    fase6 = DADOS / obra / "Fase-6_Execucao_CAD"
    gerado_dxf = fase6 / "PL_stog_quality.dxf"

    if not gerado_dxf.exists():
        print(f"  {obra:<35} NO_GERADO")
        results.append((obra, None, None))
        continue

    r = subprocess.run(
        [PYTHON, str(SCRIPTS / "fidelidade_pilares.py"), "--obra", str(DADOS / obra)],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )

    score = None
    aprovado = None
    for line in r.stdout.splitlines():
        if "APROVADO" in line or "REPROVADO" in line:
            m = re.search(r'([\d.]+)/100', line)
            if m:
                score = float(m.group(1))
            aprovado = "APROVADO" in line

    if score is None:
        print(f"  {obra:<35} ERR: {r.stderr[-80:].strip()}")
        results.append((obra, None, None))
    else:
        status = "PASS" if aprovado else "FAIL"
        print(f"  {obra:<35} {score:>6.1f}  {status}")
        results.append((obra, score, aprovado))

passed = sum(1 for r in results if r[2] is True)
total = sum(1 for r in results if r[1] is not None)
print(f"\n=== PIL TOTAL: {passed}/{total} aprovadas ===")
