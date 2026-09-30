# -*- coding: utf-8 -*-
"""3ª passada (2026-09-26): nível dos segmentos de viga derivado das lajes corrigidas.

Regra documentada (docs/NIVEL-SEGMENTO-FUNDO-VIGA.md): nível do segmento = maior cota
das lajes que tocam o trecho. Recalcula só onde o valor atual é um dos valores do bug
(855.12 / 859.12 / 822.19), com os níveis ATUAIS da tabela slabs. Sem lista de lajes:
aplica o deslocamento do erro e marca `estimado`. best_nivel (_lv_cross_class) usa as
lajes dos pilares (pillar_lajes). Sem --aplicar: só lista.
"""
import argparse, json, re, sqlite3
from pathlib import Path

DB = "D:/Agente-cad-PYSIDE/project_data.vision"
PROJ = "dd238e47-1dc6-4f63-a760-4e7ce19a7386"
ERRADOS = {"855.12": "852.15", "859.12": "852.19", "822.19": "852.19"}   # fallback: deslocamento do erro
LAJE_CERTA = {"L317": "852.15", "L318": "852.19", "L324": "852.19", "L325": "852.19"}
AQUI = Path(__file__).resolve().parent
RE_SEG = re.compile(r"(viga_[ab]_seg_\d+)_nivel_viga$")


def niveis_lajes(con):
    out = {}
    for nome, ex in con.execute("select name, extra_data_json from slabs where project_id=?", [PROJ]):
        v = (json.loads(ex or "{}") or {}).get("laje_nivel")
        try:
            out[nome] = float(v)
        except (TypeError, ValueError):
            pass
    return out


def lajes_do_seg(dado, links, seg):
    nomes = []
    for fonte in (dado.get("links") or {}, links or {}):
        for e in ((fonte.get(f"{seg}_lajes") or {}).get("laje") or []):
            if isinstance(e, dict) and e.get("text"):
                nomes.append(e["text"])
    return sorted(set(nomes))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--aplicar", action="store_true"); a = ap.parse_args()
    con = sqlite3.connect(DB if a.aplicar else f"file:{DB}?mode=ro", uri=not a.aplicar, timeout=60)
    nivel = niveis_lajes(con)
    plano, backup, estimados = [], [], []
    for bid, nome, dj, lj in con.execute("select id, name, data_json, links_json from beams where project_id=?", [PROJ]).fetchall():
        if not dj or not any(e in dj for e in ERRADOS):
            continue
        d, links, trocas = json.loads(dj), json.loads(lj or "{}"), []

        def seg_valor(seg, atual):
            nomes = lajes_do_seg(d, links, seg)
            vals = [nivel[n] for n in nomes if n in nivel]
            if vals:
                return f"{max(vals):.2f}", False
            return ERRADOS[atual], True

        for alvo in (d, d.get("fields") if isinstance(d.get("fields"), dict) else {}):
            for k, v in list(alvo.items()):
                m = RE_SEG.match(k)
                if m and isinstance(v, str) and v in ERRADOS:
                    novo, est = seg_valor(m.group(1), v)
                    alvo[k] = novo; trocas.append((k, v, novo + (" (estimado)" if est else "")))
                    if est: estimados.append(f"{nome}.{k}")
        for k, lst in (d.get("links") or {}).items():
            if k.endswith("_lajes") and isinstance(lst, dict):
                for e in lst.get("laje") or []:
                    f = e.get("ficha") if isinstance(e, dict) else None
                    if isinstance(f, dict) and e.get("text") in LAJE_CERTA and f.get("nivel") in ERRADOS:
                        trocas.append((f"links.{k}.{e['text']}", f["nivel"], LAJE_CERTA[e["text"]])); f["nivel"] = LAJE_CERTA[e["text"]]
        cc = d.get("_lv_cross_class")
        if isinstance(cc, dict) and cc.get("best_nivel") in ERRADOS:
            vals = [nivel[n] for n in cc.get("pillar_lajes") or [] if n in nivel]
            novo = f"{max(vals):.2f}" if vals else ERRADOS[cc["best_nivel"]]
            trocas.append(("_lv_cross_class.best_nivel", cc["best_nivel"], novo)); cc["best_nivel"] = novo
        if trocas:
            d.setdefault("_correcoes", []).append({"data": "2026-09-26", "motivo": "nível de laje com bug cm×m (L317/L318/L324/L325); segmento recalculado pela maior cota das lajes que tocam o trecho",
                                                   "estimados": [t[0] for t in trocas if "estimado" in str(t[2])]})
            plano.append((bid, nome, d, trocas)); backup.append({"tabela": "beams", "coluna": "data_json", "id": bid, "valor": dj})
    for bid, nome, _, trocas in plano:
        print(f"{nome}: {len(trocas)} — " + "; ".join(f"{t[0].replace('viga_','')} {t[1]}→{t[2]}" for t in trocas[:4]))
    print(f"TOTAL: {sum(len(p[3]) for p in plano)} trocas em {len(plano)} vigas; estimados: {len(estimados)}")
    if a.aplicar and plano:
        (AQUI / "backup_vigas.json").write_text(json.dumps(backup, ensure_ascii=False, indent=1), encoding="utf-8")
        with con:
            for bid, _, d, _ in plano:
                con.execute("update beams set data_json=? where id=?", (json.dumps(d, ensure_ascii=False), bid))
        print("APLICADO; backup em", AQUI / "backup_vigas.json")


if __name__ == "__main__":
    main()
