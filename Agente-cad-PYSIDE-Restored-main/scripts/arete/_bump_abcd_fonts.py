"""Aumenta fontes nas fichas ABCD já exportadas (sem re-render N1)."""
from __future__ import annotations

import sys
from pathlib import Path

REPLACEMENTS = [
    ("font:11px monospace", "font:13px/1.45 Consolas,monospace"),
    ("font-size:14px;margin:0 0 10px", "font-size:18px;margin:0 0 10px"),
    ("font-size:8px;padding:1px 5px", "font-size:11px;padding:2px 7px"),
    (
        "padding:4px 8px;font-size:10px;font-weight:bold",
        "padding:6px 10px;font-size:13px;font-weight:bold",
    ),
    (
        "padding:2px 8px;border-radius:3px;font-size:10px",
        "padding:4px 10px;border-radius:3px;font-size:12px",
    ),
    ("minmax(280px,1fr));gap:10px", "minmax(320px,1fr));gap:12px"),
    ("padding:8px;font-size:10px", "padding:10px;font-size:13px"),
    ("margin-bottom:6px;font-size:11px", "margin-bottom:8px;font-size:14px"),
    (
        ".abcd-mini{width:100%;border-collapse:collapse;font-size:9px}",
        ".abcd-mini{width:100%;border-collapse:collapse;font-size:13px}",
    ),
    ("padding:3px 4px;font-weight:600", "padding:5px 7px;font-weight:600"),
    ("padding:3px 4px;color:#ccc", "padding:5px 7px;color:#ddd"),
    ("font-size:10px;color:#777", "font-size:12px;color:#888"),
    (
        "font-size:10px;font-weight:bold;margin-bottom:2px",
        "font-size:13px;font-weight:bold;margin-bottom:2px",
    ),
    (
        "color:#666;font-size:9px;margin-bottom:6px",
        "color:#777;font-size:12px;margin-bottom:6px",
    ),
    (
        "font:12px/1.45 Consolas,monospace;resize:vertical",
        "font:14px/1.45 Consolas,monospace;resize:vertical",
    ),
    (
        "margin-top:6px;font-size:10px;color:#666",
        "margin-top:6px;font-size:12px;color:#777",
    ),
    ("atencao-hint{font-size:10px", "atencao-hint{font-size:12px"),
    ("atencao-hint{font-size:12px;color:#777", "atencao-hint{font-size:12px;color:#888"),
]


def main() -> int:
    pack = Path(
        r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete"
        r"\html_fichas\Obra_TREINO_1\13_PAV_20260730_210556_pilares_abcd\pilares"
    )
    if len(sys.argv) > 1:
        pack = Path(sys.argv[1])
    n = 0
    for f in sorted(pack.glob("P*.html")):
        t = f.read_text(encoding="utf-8")
        o = t
        for a, b in REPLACEMENTS:
            t = t.replace(a, b)
        if t != o:
            f.write_text(t, encoding="utf-8")
            n += 1
            print("ok", f.name)
        else:
            print("skip", f.name)
    print(f"[OK] {n} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
