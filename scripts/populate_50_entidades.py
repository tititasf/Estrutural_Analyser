"""
populate_50_entidades.py
Popula 50 entidades nos robos Laterais e Fundos (paths corretos do app principal)
Lajes já estava OK.
"""

import json
import uuid
import os

BASE = "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/_ROBOS_ABAS"

LATERAIS_FILE = os.path.join(BASE, "Robo_Laterais_de_Vigas", "dados_vigas_ultima_sessao.json")
FUNDOS_FILE   = os.path.join(BASE, "Robo_Fundos_de_Vigas", "compactador-producao", "fundos_salvos.json")
LAJES_PROJECT = (
    "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/"
    "projects_repo/1b2a3019-af5f-4fe2-bf1d-ac0d814baa83/laje_data/obras.json"
)

OBRA_NOME = "Obra50_entidades"
PAV_NOME  = "Pav50_entidades"

WIDTHS  = [100, 120, 140, 160, 180, 200, 220, 240, 260, 280,
           300, 320, 340, 360, 380, 400, 150, 170, 190, 210,
           230, 250, 270, 290, 310, 330, 350, 370, 390, 410,
           108, 132, 156, 184, 204, 228, 252, 276, 304, 328,
           112, 136, 164, 188, 208, 236, 264, 288, 312, 336]

HEIGHTS = [ 60,  65,  70,  75,  80,  85,  90,  95, 100, 105,
           110, 115, 120,  62,  68,  72,  78,  82,  88,  92,
            98, 102, 108, 112, 118,  61,  67,  73,  79,  83,
            89,  93,  99, 103, 109, 113, 119,  63,  69,  74,
            81,  87,  91,  97, 104, 111, 116,  66,  76,  86]

BOTTOMS = [14,16,18,19,20,22,14,16,18,19,20,22,14,16,18,19,20,22,14,16,
           18,19,20,22,14,16,18,19,20,22,14,16,18,19,20,22,14,16,18,19,
           20,22,14,16,18,19,20,22,14,16]


# ─────────────────────────────────────────────
# LATERAIS  (format: project_data > obra > pav > vigas > {name: {...}})
# ─────────────────────────────────────────────

def make_panel(w, h, idx, obra_key):
    return {
        "width": float(w),
        "height1": str(h),
        "height2": "0",
        "type1": "Grade",
        "type2": "Sarrafeado",
        "grade_h1": round(float(h) - 2.2, 1),
        "grade_h2": 0.0,
        "slab_top": 14.0,
        "slab_bottom": 0.0,
        "slab_center": 0.0,
        "uid": f"{obra_key}-X-LISTAGERAL-X-P{idx+1}-H1",
        "uid_h2": "",
        "reused_from": "",
        "reused_in": "",
        "reused_from_h2": "",
        "reused_in_h2": "",
        "link_saved": False,
    }


def make_viga(i):
    w = WIDTHS[i]; h = HEIGHTS[i]; b = BOTTOMS[i]
    side = "A" if i % 2 == 0 else "B"
    nome = f"LV50_{i+1:02d}.{side}"
    obra_key = OBRA_NOME.replace(" ", "").upper()

    panels = [make_panel(w, h, j, obra_key) for j in range(3)] + \
             [{**make_panel(0, h, 3+k, obra_key), "width": 0.0} for k in range(5)]

    return nome, {
        "number": str(i + 1),
        "name": nome,
        "floor": PAV_NOME,
        "obs": "",
        "level_beam": "",
        "level_opposite": "",
        "level_ceiling": "",
        "adjust": "",
        "text_left": "",
        "text_right": f"P{i+1}",
        "side": side,
        "continuation": "Nenhuma",
        "segment_class": "Lista Geral",
        "combined_faces": [],
        "unique_id": str(uuid.uuid4()),
        "total_width": float(w),
        "total_height": str(h),
        "bottom": str(b),
        "height2_global": "0",
        "panels": panels,
    }


def populate_laterais():
    with open(LATERAIS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    project_data = data.setdefault("project_data", {})
    if OBRA_NOME in project_data:
        del project_data[OBRA_NOME]

    vigas = {}
    for i in range(50):
        nome, viga = make_viga(i)
        vigas[nome] = viga

    project_data[OBRA_NOME] = {PAV_NOME: {"vigas": vigas}}

    with open(LATERAIS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"[LATERAIS] OK — 50 vigas em '{OBRA_NOME}/{PAV_NOME}'")
    print(f"  → {LATERAIS_FILE}")


# ─────────────────────────────────────────────
# FUNDOS  (format: {obra: {pav: {numero_str: {...}}}})
# All numeric fields are STRINGS (QLineEdit values)
# ─────────────────────────────────────────────

def make_fundo(i):
    w = WIDTHS[i]; h = HEIGHTS[i]
    num = str(i + 1)

    p1 = min(w, 244)
    p2 = max(0, w - p1)
    p3 = max(0, p2 - 244)
    if p2 > 244: p2 = 244

    area = round(w * h / 10000.0, 4)  # cm2 → m2

    return num, {
        "numero": num,
        "nome": f"Fundo50_{i+1:02d}",
        "obs": "",
        "pavimento": PAV_NOME,
        "largura": str(float(w)),
        "altura": str(float(h)),
        "texto_esq": "",
        "texto_dir": "",
        "distribuicao": "122",
        "paineis": [str(float(p1)), str(float(p2)), str(float(p3)), "0.0", "0.0", "0.0"],
        "recuos": ["0", "0", "0", "0"],
        "aberturas": [["0", "0"], ["0", "0"], ["0", "0"], ["0", "0"]],
        "tipo_painel2": "E/T",
        "comprimento_2": "0",
        "largura_2": "0",
        "paineis_2": ["0", "0", "0"],
        "recuos_2": ["0", "0", "0", "0"],
        "aberturas_2": [["0", "0"], ["0", "0"], ["0", "0"], ["0", "0"]],
        "sarrafo_esq": True,
        "sarrafo_dir": True,
        "continuacao": "UltimoSegmento",
        "obra": OBRA_NOME,
        "m2": area,
    }


def populate_fundos():
    # Carregar existente ou criar novo
    if os.path.exists(FUNDOS_FILE):
        with open(FUNDOS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}

    # Remove obra50 já existente
    if OBRA_NOME in data:
        del data[OBRA_NOME]

    pav_dict = {}
    for i in range(50):
        num, fundo = make_fundo(i)
        pav_dict[num] = fundo

    data[OBRA_NOME] = {PAV_NOME: pav_dict}

    with open(FUNDOS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"[FUNDOS]   OK — 50 fundos em '{OBRA_NOME}/{PAV_NOME}'")
    print(f"  → {FUNDOS_FILE}")


# ─────────────────────────────────────────────
# LAJES  (já estava correto — só confirma)
# ─────────────────────────────────────────────

def populate_lajes():
    with open(LAJES_PROJECT, encoding="utf-8") as f:
        data = json.load(f)
    obras = data.get("obras", [])
    obra = next((o for o in obras if o.get("nome") == OBRA_NOME), None)
    if obra:
        n = sum(len(p.get("lajes", [])) for p in obra.get("pavimentos", []))
        print(f"[LAJES]    OK — já existe '{OBRA_NOME}' com {n} lajes (sem alteração)")
    else:
        print(f"[LAJES]    AVISO — '{OBRA_NOME}' não encontrado em {LAJES_PROJECT}")


# ─────────────────────────────────────────────

if __name__ == "__main__":
    populate_laterais()
    populate_fundos()
    populate_lajes()
    print("\nDONE — abra os robos e procure 'Obra50_entidades / Pav50_entidades'")
