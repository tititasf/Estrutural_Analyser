#!/usr/bin/env python3
"""
auditar_interpretacao.py — Auditoria de campos suspeitos em JSONs Fase-3/Fase-4.

Lê os JSONs produzidos pelo pipeline (Fase-3 e Fase-4) e emite um relatório
de anomalias por item, baseado nos padrões documentados em
MASTERPLAN-INTERPRETACAO-VALIDACAO.md.

Uso:
    python auditar_interpretacao.py --obra <caminho_obra>
    python auditar_interpretacao.py --obra <caminho_obra> --pavimento TERREO
    python auditar_interpretacao.py --obra <caminho_obra> --output resultado.json

Saída:
    interpretation_audit.json (ou --output) com estrutura:
    {
      "meta": { "obra": "...", "total_itens": N, "itens_suspeitos": K, "gerado_em": "..." },
      "resultados": {
        "P1":  [{"campo": "...", "valor": ..., "suspeito": true, "motivo": "...", "classe": "PL"}],
        ...
      },
      "resumo": {
        "PL": {"total": N, "com_suspeitos": K, "anomalias": M},
        "LV": {...}, "FV": {...}, "LJ": {...}
      }
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

Finding = dict[str, Any]  # {"campo", "valor", "suspeito", "motivo", "classe"}


# ---------------------------------------------------------------------------
# Auditores por classe
# ---------------------------------------------------------------------------

FACES_PL = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
FACES_SECUNDARIAS = ['E', 'F', 'G', 'H']


def _auditar_pilar(item_id: str, data: dict) -> list[Finding]:
    """Detecta anomalias em um JSON de pilar (Fase-3 ou Fase-4)."""
    findings: list[Finding] = []

    def f(campo, valor, suspeito: bool, motivo: str):
        findings.append({
            "campo": campo,
            "valor": valor,
            "suspeito": suspeito,
            "motivo": motivo,
            "classe": "PL",
        })

    # 1. Faces secundárias ativas (h2 > 0) mas sem largura (larg1 = 0)
    for face in FACES_SECUNDARIAS:
        h2 = data.get(f"h2_{face}", 0.0) or 0.0
        larg1 = data.get(f"larg1_{face}", 0.0) or 0.0
        if h2 > 0 and larg1 == 0.0:
            f(
                f"larg1_{face}",
                larg1,
                True,
                f"Face {face} tem h2_{face}={h2} (ativa) mas larg1_{face}=0 — largura não extraída",
            )

    # 2. grade_2 ausente / zero em pilares com comprimento razoável
    comp = data.get("comprimento", 0.0) or 0.0
    grade_2 = data.get("grade_2", 0.0)
    if grade_2 in (None, 0.0, "") and comp > 50:
        f(
            "grade_2",
            grade_2,
            True,
            f"grade_2=0/null em pilar com comprimento={comp} — possível grade não detectada",
        )

    # 3. Faces secundárias E-H com h2 == h2_A E larg1=0 (indicam cópia indevida)
    #    Após fix do motor_fase4, E-H devem ter h2=0 em pilares normais.
    #    Se h2_E..H > 0 E == h2_A, é sinal de versão antiga do motor ou extrator especial.
    h2_a = data.get("h2_A", 0.0) or 0.0
    if h2_a > 0:
        sec_nonzero_equal = [
            face for face in FACES_SECUNDARIAS
            if (data.get(f"h2_{face}", 0.0) or 0.0) == h2_a
            and (data.get(f"larg1_{face}", 0.0) or 0.0) == 0.0
        ]
        if sec_nonzero_equal:
            f(
                "faces_secundarias_h2",
                {face: data.get(f"h2_{face}") for face in sec_nonzero_equal},
                True,
                f"Faces {','.join(sec_nonzero_equal)} têm h2={h2_a} idêntico à face A mas larg1=0 — provável cópia de versão antiga do motor",
            )

    # 4. grade_1 = 0 ou nulo
    grade_1 = data.get("grade_1", 0.0)
    if grade_1 in (None, 0.0, ""):
        f("grade_1", grade_1, True, "grade_1=0/null — grade principal não detectada")

    # 5. Parafusos todos zero quando h2_A > 50 (pilar robusto deveria ter parafusos)
    pars = [data.get(f"par_{i}_{i+1}", 0.0) or 0.0 for i in range(1, 9)]
    if h2_a > 50 and all(p == 0.0 for p in pars):
        f(
            "parafusos",
            pars,
            True,
            f"Todos os parafusos são 0 em pilar com h2_A={h2_a} — extração de parafusos falhou",
        )

    return findings


def _auditar_viga(item_id: str, data: dict, tipo: str = "LV") -> list[Finding]:
    """Detecta anomalias em um JSON de viga lateral (LV) ou fundo (FV)."""
    findings: list[Finding] = []

    def f(campo, valor, suspeito: bool, motivo: str):
        findings.append({
            "campo": campo,
            "valor": valor,
            "suspeito": suspeito,
            "motivo": motivo,
            "classe": tipo,
        })

    panels = data.get("panels", []) or []
    holes = data.get("holes", []) or []

    # 1. grade_h1="0" em TODOS os painéis
    if panels:
        grades = [str(p.get("grade_h1", "")) for p in panels]
        if all(g in ("0", "", "0.0") for g in grades):
            f(
                "panels[*].grade_h1",
                grades,
                True,
                f"grade_h1='0' em todos os {len(panels)} painéis — extração de grade não funcionou",
            )

    # 2. holes todos inactive
    if holes:
        all_inactive = all(not h.get("active", False) for h in holes)
        if all_inactive:
            f(
                "holes[*].active",
                [h.get("active") for h in holes],
                True,
                f"Todos os {len(holes)} holes estão active=false — aberturas podem não ter sido detectadas",
            )

    # 3. pillar_left / pillar_right ambos inactive
    pl = data.get("pillar_left", {})
    pr = data.get("pillar_right", {})
    if pl and pr:
        if not pl.get("active", False) and not pr.get("active", False):
            f(
                "pillar_left/pillar_right",
                {"left": pl.get("active"), "right": pr.get("active")},
                True,
                "Ambos pillar_left e pillar_right são active=false — cruzamento de pilares não detectado",
            )

    # 4. total_height como string "0" ou "0.0"
    th = data.get("total_height", "")
    if str(th) in ("0", "0.0", ""):
        f("total_height", th, True, "total_height=0/vazio — altura da viga não extraída")

    # 5. Sem painéis
    if not panels:
        f("panels", [], True, "Lista de painéis vazia — segmentação falhou")

    # 6. LV: total_width == 0
    if tipo == "LV":
        tw = data.get("total_width", 0.0) or 0.0
        if tw == 0.0:
            f("total_width", tw, True, "total_width=0 — largura da viga não extraída")

    return findings


def _auditar_laje(item_id: str, data: dict) -> list[Finding]:
    """Detecta anomalias em um JSON de laje (Fase-3 ou Fase-4)."""
    findings: list[Finding] = []

    def f(campo, valor, suspeito: bool, motivo: str):
        findings.append({
            "campo": campo,
            "valor": valor,
            "suspeito": suspeito,
            "motivo": motivo,
            "classe": "LJ",
        })

    # 1. linhas_horizontais sempre vazia
    lh = data.get("linhas_horizontais", []) or []
    if not lh:
        largura = data.get("largura", 0.0) or 0.0
        if largura > 100:
            f(
                "linhas_horizontais",
                lh,
                True,
                f"linhas_horizontais=[] em laje com largura={largura} — grid horizontal não extraído",
            )

    # 2. Bug de fechamento de polígono: 4º ponto deveria ser [0, largura] mas é [0, 0]
    coords = data.get("coordenadas", []) or []
    largura = data.get("largura", 0.0) or 0.0
    if len(coords) >= 4:
        last = coords[-1]
        if isinstance(last, (list, tuple)) and len(last) >= 2:
            if last[0] == 0.0 and last[1] == 0.0 and largura > 0:
                f(
                    "coordenadas[-1]",
                    last,
                    True,
                    f"Último ponto é [0,0] mas deveria ser [0,{largura}] — bug de fechamento de polígono",
                )

    # 3. modo_selecionado sempre 0
    modo = data.get("modo_selecionado", 0)
    if modo == 0:
        f(
            "modo_selecionado",
            modo,
            True,
            "modo_selecionado=0 em todos os itens — campo nunca definido pelo pipeline",
        )

    # 4. área consistente com dimensões
    comp = data.get("comprimento", 0.0) or 0.0
    area = data.get("area_cm2", 0.0) or 0.0
    if comp > 0 and largura > 0 and area > 0:
        area_calc = comp * largura
        ratio = abs(area - area_calc) / area_calc if area_calc > 0 else 0
        if ratio > 0.05:  # 5% de tolerância
            f(
                "area_cm2",
                area,
                True,
                f"area_cm2={area:.1f} diverge de comp×larg={area_calc:.1f} (delta={ratio*100:.1f}%)",
            )

    # 5. Sem linhas verticais em laje grande
    lv = data.get("linhas_verticais", []) or []
    if not lv and comp > 200:
        f(
            "linhas_verticais",
            lv,
            True,
            f"linhas_verticais=[] em laje com comprimento={comp} — grid vertical ausente",
        )

    return findings


# ---------------------------------------------------------------------------
# Carregamento de JSONs Fase-3 e Fase-4
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[WARN] Falha ao carregar {path}: {e}", file=sys.stderr)
        return None


def _load_fase3(obra_path: Path, pavimento: str | None) -> dict[str, dict]:
    """Retorna {item_id: data} para todos os itens Fase-3 da obra."""
    fase3 = obra_path / "Fase-3_Interpretacao_Extracao"
    items: dict[str, dict] = {}

    # Pilares
    for candidate in [
        fase3 / "Pilares" / "pilares_bh.json",
        fase3 / "Pilares" / "pilares.json",
        fase3 / "Dados_Interpretacao_Pilares" / "pilares_bh.json",
    ]:
        if candidate.exists():
            data = _load_json(candidate)
            if isinstance(data, dict):
                for pid, pdata in data.items():
                    if pavimento and isinstance(pdata, dict):
                        pav_item = pdata.get("pavimento", "")
                        if pav_item and pav_item.upper() != pavimento.upper():
                            continue
                    items[pid] = pdata
            break

    # Vigas
    for fname in ["vigas_dim.json", "vigas.json"]:
        candidate = fase3 / "Vigas" / fname
        if candidate.exists():
            data = _load_json(candidate)
            if isinstance(data, dict):
                for vid, vdata in data.items():
                    if pavimento and isinstance(vdata, dict):
                        pav_item = vdata.get("floor", vdata.get("pavimento", ""))
                        if pav_item and pav_item.upper() != pavimento.upper():
                            continue
                    items[vid] = vdata
            break

    # Lajes
    for fname in ["lajes_data.json", "lajes.json"]:
        candidate = fase3 / "Lajes" / fname
        if candidate.exists():
            data = _load_json(candidate)
            if isinstance(data, dict):
                for lid, ldata in data.items():
                    if pavimento and isinstance(ldata, dict):
                        pav_item = ldata.get("pavimento", "")
                        if pav_item and pav_item.upper() != pavimento.upper():
                            continue
                    items[lid] = ldata
            break

    return items


def _load_fase4_items(obra_path: Path) -> dict[str, dict]:
    """Retorna {item_id: data} para todos os JSONs individuais de Fase-4."""
    fase4 = obra_path / "Fase-4_Sincronizacao"
    dirs = {
        "PL": fase4 / "JSON_Pilares",
        "LV": fase4 / "JSON_Vigas_Laterais",
        "FV": fase4 / "JSON_Vigas_Fundo",
        "LJ": fase4 / "JSON_Lajes",
    }
    items: dict[str, dict] = {}
    for tipo, d in dirs.items():
        if not d.exists():
            continue
        for jf in sorted(d.glob("*.json")):
            data = _load_json(jf)
            if data and isinstance(data, dict):
                # Usa o stem do arquivo como chave (evita colisão quando name ≠ filename)
                items[jf.stem] = data
    return items


def _inferir_classe(item_id: str, data: dict) -> str:
    """Infere classe (PL/LV/FV/LJ) a partir de _sa_meta ou nome/id."""
    meta = data.get("_sa_meta", {}) or {}
    tipo = meta.get("tipo", "")
    if tipo in ("PL", "LV", "FV", "LJ"):
        return tipo

    nome = data.get("nome") or data.get("name") or item_id
    nome_up = str(nome).upper()
    if nome_up.startswith("P") and not nome_up.startswith("PL"):
        return "PL"
    if "_A" in nome_up or "_B" in nome_up:
        return "LV"
    if "_FUNDO" in nome_up or "_F" in nome_up:
        return "FV"
    if nome_up.startswith("L"):
        return "LJ"

    # Fallback por campos presentes
    if "comprimento" in data and "larg1_A" in data:
        return "PL"
    if "panels" in data and "side" in data:
        return "LV"
    if "panels" in data and "coordenadas" not in data:
        return "FV"
    if "coordenadas" in data:
        return "LJ"

    return "??"


# ---------------------------------------------------------------------------
# Auditoria principal
# ---------------------------------------------------------------------------

def auditar_obra(
    obra_path: Path,
    pavimento: str | None = None,
    sprint1_only: bool = False,
) -> dict:
    """Executa auditoria completa da obra e retorna dict com resultados."""
    print(f"[INFO] Auditando obra: {obra_path.name}", file=sys.stderr)

    # Carregar items (Fase-4 tem prioridade sobre Fase-3)
    fase4_items = _load_fase4_items(obra_path)
    fase3_items = _load_fase3(obra_path, pavimento)

    # Merge: Fase-4 sobrescreve Fase-3 (mais completo)
    all_items: dict[str, dict] = {}
    all_items.update(fase3_items)
    all_items.update(fase4_items)

    if not all_items:
        print(
            "[WARN] Nenhum item encontrado. Verifique se pipeline foi executado.",
            file=sys.stderr,
        )

    # Filtrar Sprint 1 (itens prioritários)
    SPRINT1_IDS = {"P1", "V101_A", "V101_fundo", "L101"}
    if sprint1_only:
        all_items = {k: v for k, v in all_items.items() if k in SPRINT1_IDS}

    resultados: dict[str, list[Finding]] = {}
    resumo: dict[str, dict] = {
        "PL": {"total": 0, "com_suspeitos": 0, "anomalias": 0},
        "LV": {"total": 0, "com_suspeitos": 0, "anomalias": 0},
        "FV": {"total": 0, "com_suspeitos": 0, "anomalias": 0},
        "LJ": {"total": 0, "com_suspeitos": 0, "anomalias": 0},
    }

    for item_id, data in sorted(all_items.items()):
        classe = _inferir_classe(item_id, data)

        if classe == "PL":
            findings = _auditar_pilar(item_id, data)
        elif classe == "LV":
            findings = _auditar_viga(item_id, data, tipo="LV")
        elif classe == "FV":
            findings = _auditar_viga(item_id, data, tipo="FV")
        elif classe == "LJ":
            findings = _auditar_laje(item_id, data)
        else:
            findings = []

        resultados[item_id] = findings

        if classe in resumo:
            resumo[classe]["total"] += 1
            sus = [f for f in findings if f.get("suspeito")]
            if sus:
                resumo[classe]["com_suspeitos"] += 1
                resumo[classe]["anomalias"] += len(sus)

    total_itens = sum(r["total"] for r in resumo.values())
    itens_suspeitos = sum(r["com_suspeitos"] for r in resumo.values())
    total_anomalias = sum(r["anomalias"] for r in resumo.values())

    return {
        "meta": {
            "obra": obra_path.name,
            "obra_path": str(obra_path),
            "pavimento": pavimento,
            "sprint1_only": sprint1_only,
            "total_itens": total_itens,
            "itens_suspeitos": itens_suspeitos,
            "total_anomalias": total_anomalias,
            "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "resultados": resultados,
        "resumo": resumo,
    }


# ---------------------------------------------------------------------------
# Relatório human-readable
# ---------------------------------------------------------------------------

def _print_relatorio(resultado: dict) -> None:
    meta = resultado["meta"]
    resumo = resultado["resumo"]
    resultados = resultado["resultados"]

    print("\n" + "=" * 70)
    print(f"  AUDITORIA DE INTERPRETAÇÃO — {meta['obra']}")
    if meta.get("pavimento"):
        print(f"  Pavimento: {meta['pavimento']}")
    print(f"  Gerado em: {meta['gerado_em']}")
    print("=" * 70)

    print(f"\n  Total de itens auditados : {meta['total_itens']}")
    print(f"  Itens com suspeitos      : {meta['itens_suspeitos']}")
    print(f"  Total de anomalias       : {meta['total_anomalias']}")

    print("\n  Por classe:")
    for classe, r in resumo.items():
        if r["total"] > 0:
            pct = (r["com_suspeitos"] / r["total"] * 100) if r["total"] else 0
            print(
                f"    {classe:3s}  {r['total']:3d} itens  |  "
                f"{r['com_suspeitos']:3d} suspeitos ({pct:.0f}%)  |  "
                f"{r['anomalias']:3d} anomalias"
            )

    print("\n" + "-" * 70)
    print("  DETALHES POR ITEM")
    print("-" * 70)

    for item_id, findings in sorted(resultados.items()):
        sus = [f for f in findings if f.get("suspeito")]
        if not sus:
            continue
        print(f"\n  [{item_id}]")
        for finding in sus:
            val = finding["valor"]
            if isinstance(val, (list, dict)):
                val_str = json.dumps(val, ensure_ascii=False)
                if len(val_str) > 60:
                    val_str = val_str[:57] + "..."
            else:
                val_str = str(val)
            print(f"    [!] {finding['campo']}: {val_str}")
            print(f"       {finding['motivo']}")

    print("\n" + "=" * 70 + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audita campos suspeitos em JSONs de interpretação (Fase-3/4)."
    )
    parser.add_argument(
        "--obra",
        required=True,
        metavar="CAMINHO",
        help="Caminho da obra (diretório com Fase-3_Interpretacao_Extracao/ e/ou Fase-4_Sincronizacao/)",
    )
    parser.add_argument(
        "--pavimento",
        default=None,
        metavar="PAV",
        help="Filtrar por pavimento (ex: TERREO, PAV1). Default: todos.",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="ARQUIVO",
        help="Arquivo JSON de saída. Default: <obra>/interpretation_audit.json",
    )
    parser.add_argument(
        "--sprint1",
        action="store_true",
        help="Auditar apenas itens do Sprint 1 (P1, V101_A, V101_fundo, L101).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Não imprimir relatório human-readable (só gerar JSON).",
    )
    args = parser.parse_args()

    obra_path = Path(args.obra).resolve()
    if not obra_path.exists():
        print(f"[ERRO] Obra não encontrada: {obra_path}", file=sys.stderr)
        sys.exit(1)

    resultado = auditar_obra(obra_path, args.pavimento, args.sprint1)

    # Saída JSON
    out_path = Path(args.output) if args.output else (obra_path / "interpretation_audit.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"[OK] Relatório salvo em: {out_path}", file=sys.stderr)

    # Relatório console
    if not args.quiet:
        _print_relatorio(resultado)

    # Exit code: 1 se há anomalias (útil para CI)
    sys.exit(1 if resultado["meta"]["total_anomalias"] > 0 else 0)


if __name__ == "__main__":
    main()
