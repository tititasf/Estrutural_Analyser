"""
Recalcula todos os campos auto-binding dos 50 pilares da Obra50_entidades.
Usa GradeCalculator exato do robo para gerar valores corretos.
Mantém laje_X, posicao_laje_X e abertura_* configurados manualmente.
Distribui variações de laje entre os 50 pilares.
"""
import sys, os, json, math

# Adiciona o path do GradeCalculator
pilares_path = "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25"
sys.path.insert(0, os.path.join(pilares_path, "src", "utils"))

from grade_calculator import GradeCalculator


# ─── Funções de cálculo ───────────────────────────────────────────────────────

def calc_parafusos(comprimento):
    resultado = GradeCalculator.calcular_parafusos(comprimento)
    return {f"par_{i+1}_{i+2}": resultado[i] for i in range(8)}


def calc_grades(comprimento):
    """Retorna dict com grade_1/2/3, distancia_1/2 baseado no comprimento."""
    num, tam, dist = GradeCalculator.calcular_grades(comprimento)
    return {
        "grade_1":      float(tam) if num >= 1 else 0.0,
        "distancia_1":  float(dist) if num >= 2 else 0.0,
        "grade_2":      float(tam) if num >= 2 else 0.0,
        "distancia_2":  float(dist) if num >= 3 else 0.0,
        "grade_3":      float(tam) if num >= 3 else 0.0,
    }


def calc_face_heights(altura, face):
    """Retorna dict h1_X..h5_X para a face dada."""
    h = GradeCalculator.calculate_face_heights(altura, face)
    return {f"h{i+1}_{face}": round(h[i], 1) for i in range(5)}


def calc_face_larguras(comprimento, largura, face):
    """Retorna larg1_X=comprimento (A/B) ou largura (C/D), larg2/3=0."""
    if face in ("A", "B"):
        larg1 = comprimento
    else:
        larg1 = largura
    return {f"larg1_{face}": float(larg1), f"larg2_{face}": 0.0, f"larg3_{face}": 0.0}


def calc_detalhes(grade_vals):
    """
    grade_vals = resultado de calc_grades.
    Retorna detalhe_grade1_1..5, detalhe_grade2_1..5, detalhe_grade3_1..5
    e seus grupos2 (espelho inverso).
    """
    d = {}
    for gidx, key in enumerate(["grade_1", "grade_2", "grade_3"], start=1):
        val = grade_vals.get(key, 0.0)
        dets = GradeCalculator.calculate_details_legacy(val) if val > 0 else [0.0]*5
        for j in range(1, 6):
            d[f"detalhe_grade{gidx}_{j}"] = round(dets[j-1], 1)
    return d


def calc_detalhes_grupo2(dets_grupo1):
    """Espelha Grupo1 para Grupo2 com inversão simples."""
    d = {}
    for gidx in range(1, 4):
        vals = [dets_grupo1.get(f"detalhe_grade{gidx}_{j}", 0.0) for j in range(1, 6)]
        vals_inv = vals[::-1]
        for j in range(1, 6):
            d[f"detalhe_grade{gidx}_{j}_grupo2"] = round(vals_inv[j-1], 1)
    return d


def calc_altura_detalhes(dets, group=1):
    """Calcula alturas cumulativas dos detalhes."""
    suffix = "" if group == 1 else "_grupo2"
    d = {}
    for gidx in range(1, 4):
        c = 0.0
        for didx in range(0, 6):
            if didx == 0:
                if group == 1:
                    d[f"altura_detalhe_{gidx}_0"] = 0.0
                else:
                    d[f"altura_detalhe_g2_{gidx}_0"] = 0.0
            else:
                key = f"detalhe_grade{gidx}_{didx}{suffix}"
                c += dets.get(key, 0.0)
                if group == 1:
                    d[f"altura_detalhe_{gidx}_{didx}"] = round(c, 1)
                else:
                    d[f"altura_detalhe_g2_{gidx}_{didx}"] = round(c, 1)
    return d


def calc_hachuras_zero(face):
    """Todos hachuras = 0."""
    d = {}
    for l in range(1, 4):
        for h in range(2, 6):
            d[f"hachura_l{l}_h{h}_{face}"] = 0
    return d


def calc_face_completo(comprimento, largura, altura, face):
    """Consolida larguras + alturas + hachuras para uma face."""
    d = {}
    d.update(calc_face_larguras(comprimento, largura, face))
    d.update(calc_face_heights(altura, face))
    d.update(calc_hachuras_zero(face))
    return d


def calc_zero_detalhe_face(face):
    """Campos detalhe_X_N_N e altura_detalhe_X_N_N para faces especiais (C/D)."""
    d = {}
    face_l = face.lower()
    for gidx in range(1, 3):
        for j in range(1, 6):
            d[f"detalhe_{face_l}_{gidx}_{j}"] = 0.0
        for j in range(0, 6):
            d[f"altura_detalhe_{face_l}_{gidx}_{j}"] = float(0 if j == 0 else 0)
    # altura_detalhe_X_1_0 = altura (total)
    return d


# ─── Variações de laje para os 50 pilares ────────────────────────────────────
# Posições Ref 1-6
# Faces: A, B, C, D
# laje_X: valor em cm (0=sem, 20/22/25=com laje)
# posicao_laje_X: 1-6

def get_laje_scenario(idx):
    """
    idx 0-49: retorna dict com laje_X/posicao_laje_X e abertura_laje_* para cada face.
    Cobre: sem laje, laje só A, só B, só C/D, A+B, A+B+C+D, posições variadas.
    """
    d = {}
    # Inicializa sem laje
    for face in "ABCD":
        d[f"laje_{face}"] = 0
        d[f"posicao_laje_{face}"] = 0.0
        for side in ("esq", "dir"):
            for n in (1, 2):
                d[f"abertura_laje_{side}{n}_{face.lower()}"] = 0.0

    # Bloco 0-9: sem laje (default)
    if idx < 10:
        pass

    # Bloco 10-19: laje só na face A, posições 1-6 rotacionando
    elif idx < 20:
        pos = (idx - 10) % 6 + 1
        d["laje_A"] = 20
        d["posicao_laje_A"] = float(pos)

    # Bloco 20-24: laje só na face B, posições variadas
    elif idx < 25:
        pos = (idx - 20) % 6 + 1
        d["laje_B"] = 22
        d["posicao_laje_B"] = float(pos)

    # Bloco 25-29: laje faces A+B (mesma posição)
    elif idx < 30:
        pos = (idx - 25) % 3 + 1
        d["laje_A"] = 20
        d["posicao_laje_A"] = float(pos)
        d["laje_B"] = 20
        d["posicao_laje_B"] = float(pos)

    # Bloco 30-34: laje faces A+B posições diferentes
    elif idx < 35:
        pa = (idx - 30) % 6 + 1
        pb = (pa % 6) + 1
        d["laje_A"] = 20
        d["posicao_laje_A"] = float(pa)
        d["laje_B"] = 25
        d["posicao_laje_B"] = float(pb)

    # Bloco 35-39: laje face C (largura)
    elif idx < 40:
        pos = (idx - 35) % 6 + 1
        d["laje_C"] = 20
        d["posicao_laje_C"] = float(pos)

    # Bloco 40-44: laje faces C+D
    elif idx < 45:
        pos = (idx - 40) % 4 + 1
        d["laje_C"] = 20
        d["posicao_laje_C"] = float(pos)
        d["laje_D"] = 20
        d["posicao_laje_D"] = float(pos)

    # Bloco 45-49: laje em 3-4 faces (A+B+C ou A+B+C+D)
    elif idx < 50:
        sub = idx - 45
        if sub < 3:
            # A+B+C
            d["laje_A"] = 20; d["posicao_laje_A"] = float(sub + 1)
            d["laje_B"] = 20; d["posicao_laje_B"] = float(sub + 2)
            d["laje_C"] = 20; d["posicao_laje_C"] = float(sub + 1)
        else:
            # A+B+C+D
            d["laje_A"] = 20; d["posicao_laje_A"] = 1.0
            d["laje_B"] = 20; d["posicao_laje_B"] = 2.0
            d["laje_C"] = 20; d["posicao_laje_C"] = 3.0
            d["laje_D"] = 20; d["posicao_laje_D"] = 4.0

    return d


# ─── Template zero para aberturas e campos especiais E/F/G/H ─────────────────

def zero_aberturas_face(face):
    d = {}
    for side in ("esq", "dir"):
        for n in (1, 2):
            for campo in ("distancia", "largura", "profundidade", "posicao"):
                d[f"{campo}_{side}_{n}_{face}"] = 0.0
    return d


def zero_especiais():
    """Campos E/F/G/H e detalhe_grade_face = 0."""
    d = {}
    for face in ("E", "F"):
        d[f"laje_{face}"] = 0
        d[f"posicao_laje_{face}"] = 0.0
        d[f"larg1_{face}"] = 0.0
        d[f"h1_{face}"] = 2.0
    for face in ("G", "H"):
        d[f"laje_{face}"] = 0
        d[f"posicao_laje_{face}"] = 0.0
    # detalhe_grade_faces A/B/C/D (grade_X_N, dist_X_N, detalhe_X_N_M)
    for face in ("a", "b", "c", "d"):
        d[f"grade_{face}_1"] = 0.0
        d[f"dist_{face}_1"] = 0.0
        d[f"grade_{face}_2"] = 0.0
        d[f"dist_{face}_2"] = 0.0
        d[f"grade_{face}_3"] = 0.0
        for n in range(1, 4):
            for m in range(1, 6):
                d[f"detalhe_{face}_{n}_{m}"] = 0.0
        for n in range(1, 3):
            for m in range(0, 6):
                d[f"altura_detalhe_{face}_{n}_{m}"] = 300.0 if m == 0 else 0.0
    return d


# ─── Recalcula um pilar completo ──────────────────────────────────────────────

def recalc_pilar(dados, idx):
    comp  = float(dados.get("comprimento", 100))
    larg  = float(dados.get("largura", 20))
    alt   = float(dados.get("altura", 300))

    novo = dict(dados)  # preserva numero, nome, obra, pavimento, etc.

    # Parafusos
    novo.update(calc_parafusos(comp))

    # Grades grupo 1
    grade_vals = calc_grades(comp)
    novo.update(grade_vals)

    # Grades grupo 2 (espelho)
    nuevo_grades_g2 = {}
    keys_g1 = ["grade_1", "grade_2", "grade_3", "distancia_1", "distancia_2"]
    for k in keys_g1:
        nuevo_grades_g2[k + "_grupo2"] = grade_vals.get(k, 0.0)
    nuevo_grades_g2["grade_1_grupo2"]     = grade_vals.get("grade_1", 0.0)
    nuevo_grades_g2["grade_2_grupo2"]     = grade_vals.get("grade_2", 0.0)
    nuevo_grades_g2["grade_3_grupo2"]     = grade_vals.get("grade_3", 0.0)
    nuevo_grades_g2["distancia_1_grupo2"] = grade_vals.get("distancia_1", 0.0)
    nuevo_grades_g2["distancia_2_grupo2"] = grade_vals.get("distancia_2", 0.0)
    novo.update(nuevo_grades_g2)

    # Detalhes grades grupo 1
    dets1 = calc_detalhes(grade_vals)
    novo.update(dets1)
    # Detalhes grades grupo 2
    dets2 = calc_detalhes_grupo2(dets1)
    novo.update(dets2)
    # Alturas detalhes
    all_dets = {**dets1, **dets2}
    novo.update(calc_altura_detalhes(all_dets, group=1))
    novo.update(calc_altura_detalhes(all_dets, group=2))

    # Faces A B C D: larguras + alturas + hachuras
    for face in ("A", "B", "C", "D"):
        novo.update(calc_face_completo(comp, larg, alt, face))

    # Aberturas zero (mantém se já tinha)
    for face in ("A", "B", "C", "D"):
        # Só aplica zeros nos campos que estão ausentes
        ab = zero_aberturas_face(face)
        for k, v in ab.items():
            if k not in novo or novo[k] in (None,):
                novo[k] = v

    # Especiais E/F/G/H (mantém zeros)
    esp = zero_especiais()
    for k, v in esp.items():
        novo[k] = v

    # Laje variations por índice (SUBSTITUI sempre)
    laje_scenario = get_laje_scenario(idx)
    novo.update(laje_scenario)

    # modo_distribuicao padrão
    if "modo_distribuicao" not in novo:
        novo["modo_distribuicao"] = "NOVA"

    return novo


# ─── Main ─────────────────────────────────────────────────────────────────────

base = "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src/core"
obras_path   = os.path.join(base, "obras_salvas.json")
pilares_path2 = os.path.join(base, "pilares_salvos.json")

with open(obras_path, "r", encoding="utf-8") as f:
    obras = json.load(f)

with open(pilares_path2, "r", encoding="utf-8") as f:
    pilares_salvos = json.load(f)

OBRA = "Obra50_entidades"
PAV  = "Pav50_entidades"

if OBRA not in obras or PAV not in obras[OBRA]:
    print("Obra50_entidades/Pav50_entidades nao encontrada!")
    sys.exit(1)

pav_data = obras[OBRA][PAV]
pids = sorted(pav_data.keys())
print(f"Pilares encontrados: {len(pids)}")

idx = 0
for pid in pids:
    dados = pav_data[pid]
    novo  = recalc_pilar(dados, idx)
    pav_data[pid] = novo

    # Atualiza pilares_salvos tbm
    if pid in pilares_salvos:
        pilares_salvos[pid]["dados"] = novo
    idx += 1

obras[OBRA][PAV] = pav_data

with open(obras_path, "w", encoding="utf-8") as f:
    json.dump(obras, f, ensure_ascii=False, indent=2)

with open(pilares_path2, "w", encoding="utf-8") as f:
    json.dump(pilares_salvos, f, ensure_ascii=False, indent=2)

print(f"Recalculados {idx} pilares com bindings corretos.")
print("Distribuicao de lajes:")
print("  0-9:  sem laje")
print("  10-19: laje face A (pos 1-6)")
print("  20-24: laje face B (pos 1-5)")
print("  25-29: laje A+B mesma posicao")
print("  30-34: laje A+B posicoes diferentes")
print("  35-39: laje face C")
print("  40-44: laje C+D")
print("  45-49: laje 3-4 faces")
