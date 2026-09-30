import json
from pathlib import Path

from bs4 import BeautifulSoup

root = Path(r"D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main")
pack = root / "scripts/arete/html_fichas/Obra_TREINO_1/TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/fundos_viga"
state_path = Path(r"D:/Agente-cad-PYSIDE/.codex-tmp/fv-hifi-20260910/estado_vps_13_PAV.json")

html_counts = {}
for path in sorted(pack.glob("*.html")):
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    html_counts[path.stem] = len(soup.select(".fv-seg-table tbody tr.fv-seg-item"))

state = json.loads(state_path.read_text(encoding="utf-8"))
state_counts = {}
for item in (state.get("segmentos") or {}).get("fundo") or []:
    name = str(item.get("beam_name") or "")
    state_counts[name] = state_counts.get(name, 0) + 1

print("html", len(html_counts), sum(html_counts.values()))
print("state", len(state_counts), sum(state_counts.values()))
for name in sorted(set(html_counts) | set(state_counts)):
    if html_counts.get(name, 0) != state_counts.get(name, 0):
        print(name, "html", html_counts.get(name, 0), "state", state_counts.get(name, 0))
        path = pack / f"{name}.html"
        soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
        rows = soup.select(".fv-seg-table tbody tr.fv-seg-item")
        print("  html_rows", [
            [r.get("data-seg")] + [c.get_text(" ", strip=True) for c in r.find_all("td", recursive=False)[2:5]]
            for r in rows
        ])
        print("  state_rows", [
            [x.get("segment_label"), x.get("length"), x.get("width")]
            for x in (state.get("segmentos") or {}).get("fundo") or []
            if str(x.get("beam_name") or "") == name
        ])
