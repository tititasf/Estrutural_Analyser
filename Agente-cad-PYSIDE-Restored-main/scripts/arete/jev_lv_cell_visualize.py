"""Plot one N1 LV attribution audit in plan coordinates (diagnostic, not source DXF)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--audit", type=Path, required=True)
    ap.add_argument("--beam", default="V420")
    ap.add_argument("--out-prefix", type=Path, required=True)
    args = ap.parse_args()
    state = json.loads(args.state.read_text(encoding="utf-8-sig"))
    audit = json.loads(args.audit.read_text(encoding="utf-8-sig"))
    target = next(row for row in audit["results"] if row["item"] == args.beam)
    fig, ax = plt.subplots(figsize=(14, 5))
    for row in state["segmentos"]["fundo"]:
        if row["beam_name"] != args.beam:
            continue
        xs, ys = zip(*row["points"])
        ax.fill(xs, ys, color="#167a45", alpha=0.5)
        ax.plot(xs, ys, color="#086334", linewidth=1.5)
    for cell in target["cells"]:
        if cell["kind"] != "lateral_b_para":
            continue
        pts = cell["points"]
        xs, ys = zip(*pts)
        bad = cell["suspicious_remote"]
        color = "#c92a2a" if bad else "#0b7285"
        ax.plot(xs, ys, color=color, linewidth=2.2, marker="o", markersize=2)
        ax.annotate(str(cell["segment_label"]), ((min(xs)+max(xs))/2, (min(ys)+max(ys))/2),
                    color=color, fontsize=9)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=0.2)
    ax.set_xlabel("X (coordenada da planta)")
    ax.set_ylabel("Y (coordenada da planta)")
    ax.set_title(f"{args.beam}: FV proprio (verde), LV-B Para local (azul), LV-B Para remoto (vermelho)")
    fig.tight_layout()
    args.out_prefix.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out_prefix.with_suffix(".png"), dpi=160)
    fig.savefig(args.out_prefix.with_suffix(".svg"))
    plt.close(fig)
    print(json.dumps({"beam": args.beam, "remote_lv_b_para": sum(c["suspicious_remote"]
                      for c in target["cells"] if c["kind"] == "lateral_b_para")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
