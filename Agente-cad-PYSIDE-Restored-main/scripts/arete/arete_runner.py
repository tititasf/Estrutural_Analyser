# -*- coding: utf-8 -*-
"""
arete_runner.py — Orquestrador G0→G1→G2→G6 (batch por classe).

Gates em cascata:
    G0: sanidade do gabarito (recorte + ficha + campos obrigatórios)
    G1: round-trip N2→N4→N2′ (diff campos)
    G2: paridade visual N4 vs recorte (score por layer)
    G6: selar golden set dos PASS

Uso:
    python arete_runner.py --classe PIL
    python arete_runner.py --classe PIL --pav 13_PAV
    python arete_runner.py --classe PIL --item P1 P5
    python arete_runner.py --regressao              # rerodar golden set
    python arete_runner.py --report <dir>           # gerar relatório de rodada anterior
"""

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from arete_config import (
    DB_PATH, PAV_13, ESCOPO_13PAV, GOLDEN_ROOT,
    RELATORIOS_DIR, CAMPOS_OBRIGATORIOS,
    TMP_DIR,
)
from ficha_adapter import (
    query_fichas, query_ficha_item,
    materializar_item, rodar_gerador,
    get_output_dxf_path, get_recorte_path,
    extrair_ficha_dinamica, get_real_n4_path,
)
from roundtrip_ficha import roundtrip_item
from paridade_visual import paridade_item, render_comparacao
from partes_pil import comparar_pil_canonico


# ═════════════════════════════════════════════════════════════════════════════
# Gate G0 — Sanidade do gabarito
# ═════════════════════════════════════════════════════════════════════════════

def g0_sanidade(row: dict) -> dict:
    """
    Verifica se o par (ficha N2, recorte DXF) é válido.

    Returns:
        {"pass": bool, "resultado": str, "erros": list[str]}
    """
    erros = []
    classe     = row["classe"]
    elemento_id = row["elemento_id"]
    campos      = row.get("campos_json") or {}

    # 1. campos_json existe e é parseável
    if not campos:
        erros.append("campos_json vazio ou nulo")

    # 2. Campos obrigatórios presentes e não-nulos
    obrig = CAMPOS_OBRIGATORIOS.get(classe, [])
    for c in obrig:
        v = campos.get(c)
        if v is None or v == "" or v == 0:
            erros.append(f"Campo obrigatório ausente/nulo: {c}={v!r}")

    # 3. Recorte DXF existe
    recorte_path = get_recorte_path(elemento_id, classe, row=row)
    if recorte_path is None:
        erros.append(f"Recorte DXF não encontrado para {classe}/{elemento_id}")
    elif not recorte_path.exists():
        erros.append(f"Recorte DXF não existe: {recorte_path}")
    else:
        # 4. Recorte legível com ezdxf
        try:
            import ezdxf
            doc = ezdxf.readfile(str(recorte_path))
            msp = doc.modelspace()
            cnt = sum(1 for _ in msp)
            if cnt == 0:
                erros.append(f"Recorte vazio (0 entidades): {recorte_path.name}")
        except Exception as exc:
            erros.append(f"Recorte ilegível: {exc}")

    # 5. Proveniência
    status_ficha = row.get("status", "unknown")

    passou = len(erros) == 0
    return {
        "pass":        passou,
        "resultado":   "PASS" if passou else "FAIL",
        "erros":       erros,
        "recorte_path": str(recorte_path) if recorte_path else None,
        "proveniencia": status_ficha,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Gate G6 — Selar golden set
# ═════════════════════════════════════════════════════════════════════════════

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def g6_selar(row: dict, n4_path: Path, g1_result: dict,
             g2_result: dict, png_path: Path | None = None) -> dict:
    """
    Sela snapshot golden para item que passou em G1+G2.

    Destino: GOLDEN/{obra}/{pav}/{classe}/{elemento_id}/
    Arquivos: ficha.json, n4.dxf (+ hash), scores.json, comparacao.png, proveniencia
    """
    classe      = row["classe"]
    elemento_id = row["elemento_id"]
    pav         = row.get("pavimento", PAV_13)
    obra        = row.get("obra_name", "desconhecida")

    golden_dir = GOLDEN_ROOT / obra / pav / classe / elemento_id
    golden_dir.mkdir(parents=True, exist_ok=True)

    # ficha.json
    ficha_dest = golden_dir / "ficha.json"
    ficha_dest.write_text(
        json.dumps(row["campos_json"], indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # n4.dxf
    n4_dest = golden_dir / "n4.dxf"
    shutil.copy2(n4_path, n4_dest)
    n4_hash = _sha256(n4_dest)

    # scores.json
    scores = {
        "g1": {
            "resultado":         g1_result["resultado"],
            "campos_comparados": g1_result.get("campos_comparados", 0),
            "n_diffs":           len(g1_result.get("diffs", [])),
        },
        "g2": {
            "resultado":  g2_result["resultado"],
            "scores":     g2_result.get("scores", {}),
            "n_diffs_ent": len(g2_result.get("diffs_entidades", [])),
            "n_diffs_geom": len(g2_result.get("diffs_geometria", [])),
            "n_diffs_txt":  len(g2_result.get("diffs_textos", [])),
        },
        "n4_sha256": n4_hash,
        "selado_em": datetime.now().isoformat(),
        "proveniencia": row.get("status", "unknown"),
    }
    (golden_dir / "scores.json").write_text(
        json.dumps(scores, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # comparacao.png
    if png_path and Path(png_path).exists():
        shutil.copy2(png_path, golden_dir / "comparacao.png")

    # proveniencia (texto simples para git diff fácil)
    (golden_dir / "proveniencia").write_text(
        row.get("status", "unknown"), encoding="utf-8"
    )

    return {
        "golden_dir": str(golden_dir),
        "n4_sha256":  n4_hash,
    }


def g6_regressao(classe: str, pavimento: str = PAV_13) -> dict:
    """
    Rerodar golden set: recarregar cada snapshot salvo e comparar scores.
    Retorna {pass: bool, regressoes: list[str]}.
    """
    obra_dir_base = GOLDEN_ROOT
    regressoes    = []
    total         = 0

    # Encontrar todos os snapshots da classe/pav
    for scores_path in obra_dir_base.rglob(f"*/{pavimento}/{classe}/*/scores.json"):
        elem_dir    = scores_path.parent
        elemento_id = elem_dir.name
        total       += 1

        try:
            scores_prev = json.loads(scores_path.read_text(encoding="utf-8"))
            n4_path     = elem_dir / "n4.dxf"
            ficha_path  = elem_dir / "ficha.json"

            if not n4_path.exists():
                regressoes.append(f"{elemento_id}: n4.dxf removido")
                continue

            # Verificar hash
            cur_hash = _sha256(n4_path)
            if cur_hash != scores_prev.get("n4_sha256", ""):
                regressoes.append(
                    f"{elemento_id}: n4.dxf mudou (hash diverge)"
                )

        except Exception as exc:
            regressoes.append(f"{elemento_id}: erro na regressão — {exc}")

    return {
        "pass":       len(regressoes) == 0,
        "total":      total,
        "regressoes": regressoes,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Gate G2 (PIL) — paridade por partes (CIMA/ABCD; GRADES N/A no 13_PAV)
# ═════════════════════════════════════════════════════════════════════════════

def paridade_item_pil(recorte_path: str | Path, n4_path: str | Path,
                      out_png: str | Path | None = None,
                      verbose: bool = True) -> dict:
    """
    G2 para PIL: compara recorte N2 vs N4 por parte (CIMA/ABCD) via
    partes_pil.comparar_pil_canonico — FORMA CANONICA (§G2 v1.2, AR-1' item 2).
    GRADES é N/A nos recortes do 13_PAV e não entra no cômputo do PASS/FAIL.

    Apenas `textos` bloqueia o gate (FORMA_BLOQUEIA_GATE / COTAS_BLOQUEIA_GATE
    = False em forma_canonica_pil.py — paineis/cotas são diagnóstico, ver
    EXC-PIL-ABCD-FORMA / EXC-PIL-CIMA-FORMA em G2_EXCECOES).

    Retorna estrutura compatível com paridade_item() (paridade_visual),
    para reaproveitar g6_selar() e _gerar_relatorio_md().
    """
    resultados = comparar_pil_canonico(recorte_path, n4_path, verbose=verbose)

    diffs_ent, diffs_geom, diffs_txt = [], [], []
    nao_mapeado = {}
    pass_geral = True

    for parte, r in resultados.items():
        if r["resultado"] == "FAIL":
            pass_geral = False
        diff = r.get("diff")
        if not diff:
            continue

        # textos — única categoria que bloqueia o gate G2 canônico
        td = diff["textos"]["detalhe"]
        for txt in td.get("so_ref", []):
            diffs_txt.append({"parte": parte, "tipo": "texto_ausente", "texto": txt})
        for txt in td.get("so_n4", []):
            diffs_txt.append({"parte": parte, "tipo": "texto_extra", "texto": txt})

        # paineis — diagnóstico (não bloqueia gate)
        for cat, det in diff["paineis"]["detalhe"].items():
            if not det["pass"]:
                diffs_ent.append({
                    "layer": parte, "dxftype": cat,
                    "ref": det["ref_count"], "n4": det["n4_count"],
                    "delta": det["n4_count"] - det["ref_count"],
                    "parte": parte,
                })

        # cotas — diagnóstico (não bloqueia gate)
        cd = diff["cotas"]["detalhe"]
        if not diff["cotas"]["pass"]:
            total = max(cd["ref_count"] + cd["n4_count"], 1)
            divergentes = len(cd.get("so_ref", [])) + len(cd.get("so_n4", []))
            diffs_geom.append({
                "layer": parte, "ref_len": cd["ref_count"], "n4_len": cd["n4_count"],
                "delta_pct": round(divergentes / total * 100, 1), "parte": parte,
            })

        nao_mapeado[parte] = {
            "ref": diff.get("nao_mapeado_ref", {}),
            "n4": diff.get("nao_mapeado_n4", {}),
        }

    png_path = None
    if out_png:
        ok_png = render_comparacao(recorte_path, n4_path, out_png,
                                    {"pass": pass_geral,
                                     "diffs_entidades": diffs_ent,
                                     "diffs_geometria": diffs_geom,
                                     "diffs_textos": diffs_txt})
        png_path = str(out_png) if ok_png else None

    return {
        "gate": "G2",
        "resultado": "PASS" if pass_geral else "FAIL",
        "scores": {parte: r["resultado"] for parte, r in resultados.items()},
        "diffs_entidades": diffs_ent,
        "diffs_geometria": diffs_geom,
        "diffs_textos": diffs_txt,
        "diffs_hatches": [],
        "nao_mapeado": nao_mapeado,
        "partes": resultados,
        "png_path": png_path,
        "erro": "",
    }


# ═════════════════════════════════════════════════════════════════════════════
# Pipeline principal: G0→G1→G2→G6
# ═════════════════════════════════════════════════════════════════════════════

def processar_item(row: dict, ts_dir: Path,
                   png_dir: Path, verbose: bool = True) -> dict:
    """
    Processa 1 item pelos gates G0→G1→G2→G6.

    Returns: resultado completo do item.
    """
    classe      = row["classe"]
    elemento_id = row["elemento_id"]

    resultado = {
        "elemento_id": elemento_id,
        "classe":      classe,
        "g0": {}, "g1": {}, "g2": {}, "g6": {},
        "resultado_final": "FAIL",
        "golden_selado":   False,
    }

    if verbose:
        print(f"\n  ── {classe}/{elemento_id} ──", flush=True)

    # ── G0 ────────────────────────────────────────────────────────────────────
    g0 = g0_sanidade(row)
    resultado["g0"] = g0
    if g0["resultado"] != "PASS":
        resultado["resultado_final"] = "BLOCKED" if "não encontrado" in " ".join(g0["erros"]) else "FAIL"
        if verbose:
            print(f"  G0 FAIL: {g0['erros']}")
        return resultado

    if verbose:
        print(f"  G0 PASS  recorte={Path(g0['recorte_path']).name}  prov={g0['proveniencia']}")

    # ── G1 ────────────────────────────────────────────────────────────────────
    g1 = roundtrip_item(classe, elemento_id,
                        pavimento=row.get("pavimento", PAV_13),
                        verbose=verbose)
    resultado["g1"] = g1
    if g1["resultado"] == "BLOCKED":
        resultado["resultado_final"] = "BLOCKED"
        return resultado

    # G1 FAIL não impede G2 (ainda queremos a análise visual),
    # mas não sela o golden

    # ── Gerar N4 (para G2, se ainda não gerado por G1) ────────────────────────
    n4_path_str = g1.get("n4_path")
    if not n4_path_str:
        # G1 BLOCKED antes de gerar (ex: motor falhou, recorte ausente).
        # Tentar gerar mesmo assim para G2, usando motor dinâmico se possível.
        recorte_path_fb = g0.get("recorte_path")
        campos_fb = None
        if recorte_path_fb:
            n2_fb = extrair_ficha_dinamica(
                Path(recorte_path_fb), classe, elemento_id)
            if "_extracao_erro" not in n2_fb:
                campos_fb = n2_fb
        obra_dir, _ = materializar_item(row, campos_override=campos_fb)
        ok_gen, log = rodar_gerador(obra_dir, classe, elemento_id)
        if ok_gen:
            dxf = get_output_dxf_path(obra_dir, classe, elemento_id)
            if dxf.exists():
                # Copiar para path real da obra
                obra_name = row.get("obra_name")
                if obra_name:
                    real = get_real_n4_path(obra_name, classe, elemento_id)
                    real.parent.mkdir(parents=True, exist_ok=True)
                    import shutil as _shutil
                    _shutil.copy2(dxf, real)
                    n4_path_str = str(real)
                else:
                    n4_path_str = str(dxf)
        if verbose and not ok_gen:
            print(f"  [AVISO] Gerador falhou; G2 será BLOCKED")

    # ── G2 ────────────────────────────────────────────────────────────────────
    recorte_path = g0.get("recorte_path")
    if n4_path_str and recorte_path:
        png_path = png_dir / f"{classe}_{elemento_id}.png"
        if classe == "PIL":
            g2 = paridade_item_pil(
                recorte_path=recorte_path,
                n4_path=n4_path_str,
                out_png=png_path,
                verbose=verbose,
            )
        else:
            g2 = paridade_item(
                recorte_path=recorte_path,
                n4_path=n4_path_str,
                out_png=png_path,
                verbose=verbose,
                classe=classe,
            )
    else:
        g2 = {"gate": "G2", "resultado": "BLOCKED",
              "erro": "N4 ou recorte não disponível", "scores": {}}

    resultado["g2"] = g2

    # ── Resultado final ───────────────────────────────────────────────────────
    if g1["resultado"] == "PASS" and g2["resultado"] == "PASS":
        resultado["resultado_final"] = "PASS"
    elif g1["resultado"] == "BLOCKED" or g2["resultado"] == "BLOCKED":
        resultado["resultado_final"] = "BLOCKED"
    else:
        resultado["resultado_final"] = "FAIL"

    # ── G6: selar se PASS ─────────────────────────────────────────────────────
    if resultado["resultado_final"] == "PASS" and n4_path_str:
        g6 = g6_selar(
            row=row,
            n4_path=Path(n4_path_str),
            g1_result=g1,
            g2_result=g2,
            png_path=g2.get("png_path"),
        )
        resultado["g6"]           = g6
        resultado["golden_selado"] = True
        if verbose:
            print(f"  G6 SELADO → {g6['golden_dir']}")

    return resultado


def rodar_classe(classe: str, pavimento: str = PAV_13,
                 elemento_ids: list[str] | None = None,
                 verbose: bool = True) -> dict:
    """
    Roda o pipeline G0→G2 para uma classe inteira (ou subset).

    Returns: sumário da rodada.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_dir  = RELATORIOS_DIR / ts
    png_dir = ts_dir / "png"
    ts_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)

    # Carregar fichas
    if elemento_ids:
        rows = [r for r in query_fichas(classe, pavimento)
                if r["elemento_id"] in elemento_ids]
    else:
        rows = query_fichas(classe, pavimento)

    if not rows:
        print(f"[AVISO] Nenhuma ficha encontrada para {classe}/{pavimento}")
        return {"erro": "sem fichas"}

    print(f"\n╔══ ARETE RUNNER: {classe} / {pavimento} ({len(rows)} itens) ══╗")

    resultados = []
    for row in rows:
        r = processar_item(row, ts_dir, png_dir, verbose=verbose)
        resultados.append(r)

    # Sumário
    n_pass = sum(1 for r in resultados if r["resultado_final"] == "PASS")
    n_fail = sum(1 for r in resultados if r["resultado_final"] == "FAIL")
    n_blk  = sum(1 for r in resultados if r["resultado_final"] == "BLOCKED")

    sumario = {
        "classe": classe, "pavimento": pavimento,
        "rodada_ts": ts,
        "total": len(resultados),
        "pass": n_pass, "fail": n_fail, "blocked": n_blk,
        "arete_pct": round(n_pass / max(len(resultados)-n_blk, 1) * 100, 1),
        "itens": resultados,
    }

    print(f"\n╚══ RESULTADO: {n_pass}P / {n_fail}F / {n_blk}B  "
          f"Arete={sumario['arete_pct']}% ══╝\n")

    # Salvar relatorio.json
    rel_json = ts_dir / "relatorio.json"
    rel_json.write_text(
        json.dumps(sumario, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # Gerar RELATORIO.md
    _gerar_relatorio_md(sumario, ts_dir)

    print(f"  Relatório: {ts_dir / 'RELATORIO.md'}")
    return sumario


# ═════════════════════════════════════════════════════════════════════════════
# Gerador de relatório Markdown
# ═════════════════════════════════════════════════════════════════════════════

def _gerar_relatorio_md(sumario: dict, ts_dir: Path):
    """Gera RELATORIO.md legível a partir do sumário."""
    ts     = sumario["rodada_ts"]
    cls    = sumario["classe"]
    pav    = sumario["pavimento"]
    n_p    = sumario["pass"]
    n_f    = sumario["fail"]
    n_b    = sumario["blocked"]
    total  = sumario["total"]
    arete  = sumario["arete_pct"]

    linhas = [
        f"# Relatório Arete — {cls} / {pav}",
        f"**Rodada:** {ts}",
        "",
        f"## Resultado: {n_p}P / {n_f}F / {n_b}B  |  Arete {arete}%",
        "",
        "| Elemento | G0 | G1 | G2 | Final | Golden |",
        "|----------|----|----|-----|-------|--------|",
    ]

    fails = []
    for r in sumario["itens"]:
        eid   = r["elemento_id"]
        g0r   = r.get("g0", {}).get("resultado", "—")
        g1r   = r.get("g1", {}).get("resultado", "—")
        g2r   = r.get("g2", {}).get("resultado", "—")
        final = r["resultado_final"]
        gold  = "✓" if r.get("golden_selado") else ""
        mark  = {"PASS": "✓", "FAIL": "✗", "BLOCKED": "⊘"}.get(final, "?")
        linhas.append(f"| {eid} | {g0r} | {g1r} | {g2r} | {mark} {final} | {gold} |")
        if final == "FAIL":
            fails.append(r)

    if fails:
        linhas += ["", "## FAILs — Causas e Próximas Ações", ""]
        for r in fails:
            eid = r["elemento_id"]
            linhas.append(f"### {eid}")
            g1  = r.get("g1", {})
            g2  = r.get("g2", {})
            if g1.get("resultado") == "FAIL":
                diffs_g1 = g1.get("diffs", [])
                linhas.append(f"- **G1 FAIL** — {len(diffs_g1)} diffs no round-trip:")
                for d in diffs_g1[:3]:
                    linhas.append(f"  - `{d.get('campo')}`: N2={d.get('n2')} N2′={d.get('n2p')} [{d.get('tipo')}]")
            if g2.get("resultado") == "FAIL":
                nde = len(g2.get("diffs_entidades", []))
                ndg = len(g2.get("diffs_geometria", []))
                ndt = len(g2.get("diffs_textos", []))
                linhas.append(f"- **G2 FAIL** — ent={nde} geom={ndg} txt={ndt}")
                for d in g2.get("diffs_textos", [])[:5]:
                    if "tipo" in d and "texto" in d:
                        rotulo = "ausente em N4" if d["tipo"] == "texto_ausente" else "extra em N4"
                        linhas.append(f"  - `{d.get('parte','?')}` texto {rotulo}: \"{d['texto']}\"")
                    else:
                        for t in d.get("faltam", []):
                            linhas.append(f"  - `{d.get('layer','?')}/{d.get('parte','?')}` texto ausente em N4: \"{t}\"")
                        for t in d.get("extras", []):
                            linhas.append(f"  - `{d.get('layer','?')}/{d.get('parte','?')}` texto extra em N4: \"{t}\"")
                for d in g2.get("diffs_entidades", [])[:3]:
                    linhas.append(f"  - `{d['layer']}/{d['dxftype']}`: ref={d['ref']} n4={d['n4']}")
                for d in g2.get("diffs_geometria", [])[:2]:
                    linhas.append(f"  - `{d['layer']}`: {d['delta_pct']:.1f}% divergência")
            linhas.append("")

    linhas += [
        "## Próxima ação",
        _proximo_fail(fails),
        "",
        f"_Gerado em {ts} — Arete Quality Gates_",
    ]

    md_path = ts_dir / "RELATORIO.md"
    md_path.write_text("\n".join(linhas), encoding="utf-8")


def _proximo_fail(fails: list) -> str:
    if not fails:
        return "Nenhum FAIL — classe em Arete! Selar e avançar para próxima classe."
    r   = fails[0]
    eid = r["elemento_id"]
    g1  = r.get("g1", {})
    g2  = r.get("g2", {})
    if g1.get("resultado") == "FAIL":
        d  = g1.get("diffs", [{}])[0]
        return (f"Atacar G1-FAIL em {eid}: campo `{d.get('campo')}` "
                f"diverge N2={d.get('n2')} vs N2′={d.get('n2p')} [{d.get('tipo')}].")
    if g2.get("resultado") == "FAIL":
        dts = g2.get("diffs_textos", [])
        if dts:
            d = dts[0]
            if "tipo" in d and "texto" in d:
                rotulo = "ausente em N4" if d["tipo"] == "texto_ausente" else "extra em N4"
                return (f"Atacar G2-FAIL em {eid}: texto {rotulo} na parte "
                        f"`{d.get('parte','?')}`: \"{d['texto']}\".")
            for t in d.get("faltam", []):
                return (f"Atacar G2-FAIL em {eid}: texto ausente em N4 na "
                        f"`{d.get('layer','?')}/{d.get('parte','?')}`: \"{t}\".")
            for t in d.get("extras", []):
                return (f"Atacar G2-FAIL em {eid}: texto extra em N4 na "
                        f"`{d.get('layer','?')}/{d.get('parte','?')}`: \"{t}\".")
        de = g2.get("diffs_entidades", [{}])[0] if g2.get("diffs_entidades") else {}
        return (f"Atacar G2-FAIL em {eid}: entidade "
                f"`{de.get('layer','?')}/{de.get('dxftype','?')}` "
                f"ref={de.get('ref')} n4={de.get('n4')}.")
    return f"Investigar {eid}: verificar visualmente o PNG."


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Arete Runner — AR-0.4")
    parser.add_argument("--classe", default=None, help="PIL|LV|FV|LAJ")
    parser.add_argument("--pav",    default=PAV_13)
    parser.add_argument("--item",   nargs="*", default=None,
                        help="Processar só estes itens")
    parser.add_argument("--regressao", action="store_true",
                        help="Rerrodar golden set e verificar regressão")
    parser.add_argument("--quiet", action="store_true",
                        help="Menos output")
    args = parser.parse_args()

    if args.regressao:
        classe = args.classe or "PIL"
        print(f"Regressão golden set: {classe}/{args.pav}")
        reg = g6_regressao(classe, args.pav)
        status = "PASS" if reg["pass"] else f"FAIL ({len(reg['regressoes'])} regressões)"
        print(f"  {status}  total_snaps={reg['total']}")
        for r in reg["regressoes"]:
            print(f"  ✗ {r}")
    elif args.classe:
        rodar_classe(
            classe=args.classe,
            pavimento=args.pav,
            elemento_ids=args.item,
            verbose=not args.quiet,
        )
    else:
        parser.print_help()
