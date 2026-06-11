"""
personalizar_50_entidades.py
Adiciona variedade/complexidade aos 50 exemplos de cada robo.
Distribui cenarios: simples, aberturas, chanfros, tipos de painel,
continuacoes, multipainel, grades, furacoes, laje central, etc.
"""

import json, copy, os

BASE = "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/_ROBOS_ABAS"
LATERAIS_FILE = os.path.join(BASE, "Robo_Laterais_de_Vigas", "dados_vigas_ultima_sessao.json")
FUNDOS_FILE   = os.path.join(BASE, "Robo_Fundos_de_Vigas", "compactador-producao", "fundos_salvos.json")
LAJES_PROJECT = ("D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/"
                 "projects_repo/1b2a3019-af5f-4fe2-bf1d-ac0d814baa83/laje_data/obras.json")
OBRAS_FILE    = os.path.join(BASE, "Robo_Pilares/pilares-atualizado-09-25/src/core/obras_salvas.json")
PILARES_FILE  = os.path.join(BASE, "Robo_Pilares/pilares-atualizado-09-25/src/core/pilares_salvos.json")

OBRA = "Obra50_entidades"
PAV  = "Pav50_entidades"

# ─── LATERAIS ──────────────────────────────────────────────────────────────

# Cenarios por indice (0-49):
# 0-9   simples (grade, 1 painel)
# 10-19 abertura no painel central
# 20-24 laje no topo (slab_top)
# 25-29 laje central (slab_center)
# 30-34 tipo Sarrafeado
# 35-39 Sarrafeado + Abertura
# 40-44 multi-painel (2-3 paineis reais)
# 45-49 continuacao (Proxima Parte / PrimeiraParte)

PANEL_TYPES = [
    ("Grade",      "Sarrafeado"),
    ("Grade",      "Grade"),
    ("Sarrafeado", "Sarrafeado"),
    ("Compensado", "Sarrafeado"),
]

CONTINUATIONS = ["Nenhuma", "Proxima Parte", "UltimoSegmento", "PrimeiraParte"]

def personalizar_laterais():
    with open(LATERAIS_FILE, encoding="utf-8") as f: data = json.load(f)
    vigas = data["project_data"][OBRA][PAV]["vigas"]
    keys  = list(vigas.keys())

    for i, key in enumerate(keys):
        v = vigas[key]
        w = v["total_width"]; h = int(v["total_height"]); b = int(v["bottom"])
        panels = v["panels"]

        # 10-19: abertura no painel 0
        if 10 <= i <= 19:
            ab_pos  = round(w * 0.15, 1)
            ab_size = round(w * 0.2, 1)
            panels[0]["aberturas"] = [[ab_pos, ab_size], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]
            v["obs"] = "abertura lateral"

        # 20-24: slab_top no primeiro painel
        if 20 <= i <= 24:
            panels[0]["slab_top"] = 14.0
            panels[0]["slab_bottom"] = 0.0
            v["obs"] = "laje no topo"

        # 25-29: slab_center (laje central)
        if 25 <= i <= 29:
            panels[0]["slab_center"] = round(h * 0.45, 1)
            v["obs"] = "laje central"

        # 30-34: tipo Sarrafeado h1 e h2
        if 30 <= i <= 34:
            panels[0]["type1"] = "Sarrafeado"
            panels[0]["type2"] = "Sarrafeado"
            v["obs"] = "sarrafeado"

        # 35-39: Sarrafeado + abertura
        if 35 <= i <= 39:
            panels[0]["type1"] = "Sarrafeado"
            ab_pos  = round(w * 0.1, 1)
            ab_size = round(w * 0.25, 1)
            panels[0]["aberturas"] = [[ab_pos, ab_size], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]
            v["obs"] = "sarrafeado + abertura"

        # 40-44: multi-painel com 2 paineis reais (dividir largura em 2)
        if 40 <= i <= 44:
            w1 = round(w * 0.55, 1)
            w2 = round(w - w1, 1)
            panels[0]["width"] = w1
            panels[1]["width"] = w2
            panels[1]["grade_h1"] = round(h - 2.2, 1)
            v["obs"] = "2 paineis"

        # 45-49: continuacao
        if 45 <= i <= 49:
            cont = CONTINUATIONS[(i - 45) % len(CONTINUATIONS)]
            v["continuation"] = cont
            v["obs"] = f"continuacao: {cont}"

        # Tipo de painel (varia a cada 10)
        t1, t2 = PANEL_TYPES[(i // 10) % len(PANEL_TYPES)]
        if i < 10 or (30 <= i <= 34):  # simples e sarrafeado ja setados
            panels[0]["type1"] = t1
            panels[0]["type2"] = t2

        v["panels"] = panels

    with open(LATERAIS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"[LATERAIS] Personalizado: {len(keys)} vigas")


# ─── FUNDOS ────────────────────────────────────────────────────────────────

# 0-9   simples (1 painel, sem aberturas)
# 10-19 abertura no painel (posicao e tamanho variados)
# 20-24 chanfros (recuos esq/dir)
# 25-29 distribuicao 307 (3 paineis iguais)
# 30-34 abertura + chanfro combinados
# 35-39 2 paineis com segunda face (L-type)
# 40-44 aberturas em multiplos segmentos
# 45-49 tipo painel "307" + chanfros

def personalizar_fundos():
    with open(FUNDOS_FILE, encoding="utf-8") as f: data = json.load(f)
    fundos = data[OBRA][PAV]
    keys   = sorted(fundos.keys(), key=lambda x: int(x))

    for k in keys:
        i = int(k) - 1
        d = fundos[k]
        w = float(d["largura"]); h = float(d["altura"])
        p1 = float(d["paineis"][0])

        # 10-19: abertura no segmento central
        if 10 <= i <= 19:
            pos  = round(p1 * 0.2, 1)
            size = round(p1 * 0.3, 1)
            d["aberturas"] = [["0", "0"], [str(pos), str(size)], ["0", "0"], ["0", "0"]]
            d["nome"] += "_AB"

        # 20-24: chanfros (recuos)
        if 20 <= i <= 24:
            recuo_esq = round(w * 0.05, 1)
            recuo_dir = round(w * 0.05, 1)
            d["recuos"] = [str(recuo_esq), str(recuo_dir), "0", "0"]
            d["nome"] += "_CH"

        # 25-29: distribuicao 307 (3 paineis iguais)
        if 25 <= i <= 29:
            p = round(w / 3.0, 1)
            d["distribuicao"] = "307"
            d["paineis"] = [str(p), str(p), str(round(w - 2*p, 1)), "0.0", "0.0", "0.0"]
            d["nome"] += "_307"

        # 30-34: abertura + chanfro
        if 30 <= i <= 34:
            pos  = round(p1 * 0.25, 1)
            size = round(p1 * 0.25, 1)
            d["aberturas"] = [["0", "0"], [str(pos), str(size)], ["0", "0"], ["0", "0"]]
            rec  = round(w * 0.04, 1)
            d["recuos"] = [str(rec), str(rec), "0", "0"]
            d["nome"] += "_AB+CH"

        # 35-39: segunda face (L invertido) com comprimento_2 e largura_2
        if 35 <= i <= 39:
            d["tipo_painel2"] = "L"
            d["comprimento_2"] = str(round(w * 0.4, 1))
            d["largura_2"]     = str(round(h * 0.3, 1))
            d["paineis_2"]     = [str(round(w * 0.4, 1)), "0", "0"]
            d["nome"] += "_L"

        # 40-44: abertura em 3 segmentos
        if 40 <= i <= 44:
            seg = round(p1 / 3.0, 1)
            d["aberturas"] = [
                [str(round(seg*0.1,1)), str(round(seg*0.3,1))],
                [str(round(seg*0.1,1)), str(round(seg*0.3,1))],
                [str(round(seg*0.1,1)), str(round(seg*0.3,1))],
                ["0", "0"]
            ]
            d["nome"] += "_AB3"

        # 45-49: 307 + chanfros
        if 45 <= i <= 49:
            p = round(w / 3.0, 1)
            d["distribuicao"] = "307"
            d["paineis"] = [str(p), str(p), str(round(w - 2*p, 1)), "0.0", "0.0", "0.0"]
            rec = round(w * 0.06, 1)
            d["recuos"] = [str(rec), str(rec), "0", "0"]
            d["nome"] += "_307+CH"

        fundos[k] = d

    with open(FUNDOS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"[FUNDOS] Personalizado: {len(keys)} fundos")


# ─── LAJES ─────────────────────────────────────────────────────────────────

# 0-9   simples (3 paineis verticais iguais)
# 10-19 unioes_nos_bordes = True
# 20-24 linhas com is_union=True (juntas)
# 25-29 4 paineis verticais
# 30-34 2 linhas horizontais (2 alturas)
# 35-39 obstaculos retangulares
# 40-44 paineis mistos union+normal
# 45-49 lajes quadradas com 2x2 grid

def personalizar_lajes():
    with open(LAJES_PROJECT, encoding="utf-8") as f: data = json.load(f)
    obra = next(o for o in data["obras"] if o["nome"] == OBRA)
    lajes = obra["pavimentos"][0]["lajes"]

    for i, laje in enumerate(lajes):
        c = laje["comprimento"]; l = laje["largura"]

        # 10-19: unioes_nos_bordes
        if 10 <= i <= 19:
            laje["unioes_nos_bordes"] = True
            laje["nome"] += "_U"

        # 20-24: uma linha vertical com is_union=True
        if 20 <= i <= 24:
            p = round(c / 3.0, 4)
            laje["linhas_verticais"] = [
                {"value": p, "is_union": False},
                {"value": p, "is_union": True},   # junta
            ]
            laje["nome"] += "_J"

        # 25-29: 4 paineis verticais (3 linhas)
        if 25 <= i <= 29:
            p = round(c / 4.0, 4)
            laje["linhas_verticais"] = [
                {"value": p, "is_union": False},
                {"value": p, "is_union": False},
                {"value": p, "is_union": False},
            ]
            laje["nome"] += "_4P"

        # 30-34: 2 linhas horizontais (3 alturas)
        if 30 <= i <= 34:
            h1 = round(l * 0.4, 4)
            h2 = round(l * 0.35, 4)
            laje["linhas_horizontais"] = [
                {"value": h1, "is_union": False},
                {"value": h2, "is_union": False},
            ]
            laje["nome"] += "_2H"

        # 35-39: obstaculo central
        if 35 <= i <= 39:
            x0, y0 = laje["coordenadas"][0]
            obs_w = round(c * 0.2, 1)
            obs_h = round(l * 0.2, 1)
            cx = x0 + c / 2
            cy = y0 + l / 2
            laje["obstaculos"] = [{
                "tipo": "retangulo",
                "x": round(cx - obs_w/2, 2),
                "y": round(cy - obs_h/2, 2),
                "largura": obs_w,
                "altura": obs_h,
            }]
            laje["nome"] += "_OB"

        # 40-44: mix union + normal + 3 linhas
        if 40 <= i <= 44:
            p = round(c / 4.0, 4)
            laje["linhas_verticais"] = [
                {"value": p,              "is_union": False},
                {"value": round(p*1.5,4), "is_union": True},
                {"value": p,              "is_union": False},
            ]
            laje["unioes_nos_bordes"] = True
            laje["nome"] += "_MX"

        # 45-49: laje com dimensao ajustada para quadrado e grid 2x2
        if 45 <= i <= 49:
            lado = min(c, l)
            laje["comprimento"] = lado
            laje["largura"]     = lado
            laje["area_cm2"]    = round(lado * lado, 2)
            p = round(lado / 2.0, 4)
            laje["linhas_verticais"]   = [{"value": p, "is_union": False}]
            laje["linhas_horizontais"] = [{"value": p, "is_union": False}]
            laje["nome"] += "_Q"

    with open(LAJES_PROJECT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[LAJES] Personalizado: {len(lajes)} lajes")


# ─── PILARES ───────────────────────────────────────────────────────────────

# 0-9   simples (1 par par_1_2, grade basica)
# 10-19 grade alta (grade_1=136, grade_2=136)
# 20-24 furacoes nas faces A e B (distancia_esq_1)
# 25-29 laje nas faces A e B (laje_A=1, posicao_laje_A)
# 30-34 multiplos pares (par_1_2 + par_3_4)
# 35-39 furacoes + laje combinados
# 40-44 3 alturas por face (h1+h2+h3)
# 45-49 tudo: grade alta + 2 pares + furacoes + laje

def personalizar_pilares():
    with open(OBRAS_FILE, encoding="utf-8") as f: obras = json.load(f)
    with open(PILARES_FILE, encoding="utf-8") as f: pilares = json.load(f)

    pav_dict = obras[OBRA][PAV]
    keys = sorted(pav_dict.keys(), key=lambda k: int(k.split("_")[-1]))

    for idx, pid in enumerate(keys):
        i = idx  # 0-based
        d = pav_dict[pid]
        comp = d["comprimento"]; larg = d["largura"]; alt = d["altura"]

        # 10-19: grade alta
        if 10 <= i <= 19:
            d["grade_1"] = 136.0; d["grade_2"] = 136.0
            d["grade_1_grupo2"] = 136.0; d["grade_2_grupo2"] = 136.0

        # 20-24: furacoes nas faces A e B
        if 20 <= i <= 24:
            fura_dist = round(comp * 0.25, 1)
            fura_larg = round(comp * 0.15, 1)
            fura_prof = 5.0
            for face in ["A", "B"]:
                d[f"distancia_esq_1_{face}"] = fura_dist
                d[f"largura_esq_1_{face}"]   = fura_larg
                d[f"profundidade_esq_1_{face}"] = fura_prof
                d[f"posicao_esq_1_{face}"]   = round(alt * 0.3, 1)

        # 25-29: laje nas faces A e B
        if 25 <= i <= 29:
            for face in ["A", "B"]:
                d[f"laje_{face}"] = 1
                d[f"posicao_laje_{face}"] = round(alt * 0.4, 1)

        # 30-34: 2 pares de paineis (par_1_2 e par_3_4)
        if 30 <= i <= 34:
            par = round(comp / 4.0, 1)
            d["par_1_2"] = par; d["par_2_3"] = par
            d["par_3_4"] = par; d["par_4_5"] = par

        # 35-39: furacoes + laje combinados
        if 35 <= i <= 39:
            for face in ["A", "B"]:
                d[f"laje_{face}"] = 1
                d[f"posicao_laje_{face}"] = round(alt * 0.5, 1)
                d[f"distancia_dir_1_{face}"] = round(comp * 0.2, 1)
                d[f"largura_dir_1_{face}"]   = round(comp * 0.1, 1)
                d[f"profundidade_dir_1_{face}"] = 5.0
                d[f"posicao_dir_1_{face}"]   = round(alt * 0.6, 1)

        # 40-44: 3 segmentos de altura por face (h1+h2+h3)
        if 40 <= i <= 44:
            seg = round((alt - 2.0) / 3.0, 1)
            for face in ["A", "B", "C", "D"]:
                d[f"h1_{face}"] = 2.0
                d[f"h2_{face}"] = seg
                d[f"h3_{face}"] = seg
                d[f"h4_{face}"] = seg
                d[f"h5_{face}"] = 0.0

        # 45-49: grade alta + 2 pares + furacoes + laje
        if 45 <= i <= 49:
            d["grade_1"] = 136.0; d["grade_2"] = 136.0
            d["grade_1_grupo2"] = 136.0; d["grade_2_grupo2"] = 136.0
            par = round(comp / 4.0, 1)
            d["par_1_2"] = par; d["par_2_3"] = par; d["par_3_4"] = par
            for face in ["A", "B"]:
                d[f"laje_{face}"] = 1
                d[f"posicao_laje_{face}"] = round(alt * 0.45, 1)
                d[f"distancia_esq_1_{face}"] = round(comp * 0.15, 1)
                d[f"largura_esq_1_{face}"]   = round(comp * 0.1, 1)
                d[f"profundidade_esq_1_{face}"] = 5.0
                d[f"posicao_esq_1_{face}"]   = round(alt * 0.3, 1)

        pav_dict[pid] = d
        # Sync para pilares_salvos.json
        if pid in pilares:
            pilares[pid]["dados"] = copy.deepcopy(d)

    obras[OBRA][PAV] = pav_dict

    with open(OBRAS_FILE, "w", encoding="utf-8") as f:
        json.dump(obras, f, ensure_ascii=False, indent=4)
    with open(PILARES_FILE, "w", encoding="utf-8") as f:
        json.dump(pilares, f, ensure_ascii=False, indent=4)
    print(f"[PILARES] Personalizado: {len(keys)} pilares")


# ─── MAIN ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import copy
    personalizar_laterais()
    personalizar_fundos()
    personalizar_lajes()
    personalizar_pilares()
    print("\nDONE - 50 entidades personalizadas em cada robo")
    print("Distribuicao de cenarios (por bloco de 10):")
    print("  0-9:  simples")
    print("  10-19: aberturas")
    print("  20-24: chanfros/laje topo")
    print("  25-29: distribuicao alternativa / laje central")
    print("  30-34: sarrafeado / 2 pares / multi-painel")
    print("  35-39: sarrafeado+abertura / segunda face L / furacoes+laje")
    print("  40-44: multi-painel / obstaculos / 3 alturas")
    print("  45-49: continuacao / 307+chanfros / configuracao completa")
