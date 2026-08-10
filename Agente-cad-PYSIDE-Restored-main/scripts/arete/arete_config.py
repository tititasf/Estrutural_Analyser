# -*- coding: utf-8 -*-
"""
arete_config.py - Configuracoes centrais do harness Arete Quality Gates.
Todas as constantes de path, tolerancia e escopo ficam aqui.
"""
import os
from pathlib import Path

# -- Auto-detectar raiz do workspace (Windows ou sandbox Linux) ---------------
def _find_base() -> Path:
    """Retorna o Path base de D:/Agente-cad-PYSIDE independente do SO."""
    import glob as _glob
    candidates = [
        # Sandbox Cowork (session-id muda a cada sessão — usar glob)
        *[Path(p) for p in _glob.glob("/sessions/*/mnt/Agente-cad-PYSIDE")],
        Path("/mnt/Agente-cad-PYSIDE"),                        # Docker generico
        Path("D:/Agente-cad-PYSIDE"),                          # Windows nativo
    ]
    for c in candidates:
        try:
            if c.exists():
                return c
        except (PermissionError, OSError):
            continue
    # Fallback: inferir a partir da localizacao deste arquivo
    # scripts/arete/arete_config.py -> ../../.. = base
    here = Path(__file__).resolve()
    return here.parent.parent.parent.parent

BASE = _find_base()

# -- Paths principais ---------------------------------------------------------
REPO_ROOT     = BASE / "Agente-cad-PYSIDE-Restored-main"
DB_PATH       = BASE / "project_data.vision"
DADOS_OBRAS   = BASE / "DADOS-OBRAS"
OBRA_TREINO_1 = DADOS_OBRAS / "Obra_TREINO_1"

RECORTES_ROOT  = OBRA_TREINO_1 / "Fase-2_Triagem" / "recortes_reversos"
ARETE_ROOT     = REPO_ROOT / "scripts" / "arete"
GOLDEN_ROOT    = REPO_ROOT / "GOLDEN"
RELATORIOS_DIR = ARETE_ROOT / "relatorios"
TMP_DIR        = ARETE_ROOT / "tmp"

# -- Geradores STOG (usar via subprocess, nunca importar) ---------------------
GERADORES = {
    "PIL": REPO_ROOT / "scripts" / "gerar_pl_dxf_stog.py",
    "LV":  REPO_ROOT / "scripts" / "gerar_lv_dxf_stog.py",
    "FV":  REPO_ROOT / "scripts" / "gerar_fv_dxf_stog.py",
    "LAJ": REPO_ROOT / "scripts" / "gerar_lj_dxf_stog.py",
}

# -- Motores reversos (importar como modulo) ----------------------------------
MOTORES = {
    "PIL": REPO_ROOT / "scripts" / "motor_reverso_pil.py",
    "LV":  REPO_ROOT / "scripts" / "motor_reverso_lv.py",
    "FV":  REPO_ROOT / "scripts" / "motor_reverso_fv.py",
    "LAJ": REPO_ROOT / "scripts" / "motor_reverso_laj.py",
}

# -- Funcoes de extracao por classe (importadas dinamicamente) ----------------
MOTOR_FUNC = {
    "PIL": ("motor_reverso_pil", "extrair_ficha_pilar"),
    "LV":  ("motor_reverso_lv",  "extrair_ficha_lateral_viga"),
    "FV":  ("motor_reverso_fv",  "extrair_ficha_fundo_viga"),
    "LAJ": ("motor_reverso_laj", "extrair_ficha_laje"),
}

# -- Escopo 13_PAV (legado, mantido para compat dos scripts em tmp/) ---------
PAV_13 = "13_PAV"
ESCOPO_13PAV = {
    "PIL": 35,
    "LV":  32,
    "FV":  26,
    "LAJ": 18,
}

# -- Escopo PIL por pavimento (Fase A, multi-pavimento) -----------------------
# Total de fichas N2 (reverse_eng_fichas) por pavimento, classe PIL,
# Obra_TREINO_1 — usado por g6_regressao/selagem incremental (Fase F).
ESCOPO_PIL_POR_PAVIMENTO = {
    "1_PAV":     37,
    "2_PAV":     35,
    "12_PAV":    35,
    PAV_13:      35,
    "14_PAV":    27,
    "TERREO":    22,
    "COBERTURA": 29,
}

# Lista canonica dos 7 pavimentos de treino (Obra_TREINO_1, classe PIL)
PAVIMENTOS_TREINO_1_PIL = list(ESCOPO_PIL_POR_PAVIMENTO.keys())

# -- Pe-direito (PD) por pavimento — carimbo do cabecalho ABCD ----------------
# Constante de PAVIMENTO (nao de recorte individual): confirmado em 8/8
# amostras do 13_PAV (P1,P5,P10,P15,P20,P25,P30,P35 — REF "13 PAVIMENTO -
# PD: 3.21" em todos, independente da altura de cada pilar). Usado por
# ficha_adapter.materializar_item para injetar `pd_pavimento_cm` na ficha
# materializada (campo de pavimento, nao do elemento) — ver
# scripts/arete/relatorios/AR-1prime-canonico/RELATORIO.md.
#
# Fase A (multi-pavimento, sessao 2026-06-13): extraido do cabecalho ABCD
# (texto "{N} PAVIMENTO - PD: {valor}") de 1 recorte por pavimento, para os
# 7 pavimentos da Obra_TREINO_1 classe PIL.
PD_PAVIMENTO_CM = {
    "1_PAV":     425.0,
    "2_PAV":     323.0,
    "12_PAV":    280.0,  # pasta "TIPO - 3 AO 12 PAV" -> fichas pavimento=12_PAV
    PAV_13:      321.0,
    "14_PAV":    306.0,
    "TERREO":    312.0,
    "COBERTURA": 350.0,
}

# -- Layout Fase-4 por classe (subpath dentro do obra_adapter_dir) ------------
FASE4_SUBDIR = {
    "PIL": Path("Fase-4_Sincronizacao") / "JSON_Pilares",
    "LV":  Path("Fase-4_Sincronizacao") / "JSON_Vigas_Laterais",
    "FV":  Path("Fase-4_Sincronizacao") / "JSON_Vigas_Fundo",
    "LAJ": Path("Fase-4_Sincronizacao") / "JSON_Lajes",
}

# Sufixo do arquivo JSON por classe: {elem_id}{SUFIXO}.json
FASE4_SUFIXO = {
    "PIL": "",        # P1.json
    "LV":  "_A",      # V13_A.json
    "FV":  "_fundo",  # V301_fundo.json
    "LAJ": "",        # L301.json
}

# -- Naming do DXF de saida do gerador com --item -----------------------------
GERADOR_OUTPUT_PREFIX = {
    "PIL": "PL_preview_",
    "LV":  "LV_preview_",
    "FV":  "FV_preview_",
    "LAJ": "LJ_preview_",
}

# -- Tolerancias G2 -----------------------------------------------------------
TOL_GEOMETRIA_PCT  = 1.0   # comprimento total por layer +-1%
TOL_HATCH_AREA_PCT = 2.0   # hatch area +-2%
TOL_TEXTO_POS_CM   = 2.0   # posicao de texto +-2cm (unidades DXF = cm)
SSIM_THRESHOLD     = 0.70  # SSIM informativo (nao bloqueante)

# -- Campos obrigatorios por classe (G0 sanidade minima) ----------------------
CAMPOS_OBRIGATORIOS = {
    "PIL": ["comprimento", "largura", "altura", "nome", "numero"],
    "LV":  ["total_width", "total_height", "panels"],
    "FV":  ["total_width", "total_height", "panels"],
    "LAJ": ["comprimento", "largura"],
}

# -- Padroes de pasta dos recortes por classe (FALLBACK apenas) ---------------
# Fase A (multi-pavimento, sessao 2026-06-13): removido o hardcode "*13*PAV*".
# A localizacao primaria do recorte de um item agora vem da propria ficha
# (`row["recorte_path"]`, ja gravado por pavimento/obra no DB) — ver
# ficha_adapter.get_recorte_path. Estes padroes so' sao usados quando essa
# coluna estiver ausente/invalida (fallback generico, varre qualquer pasta
# "* PL *"/"* LV *"/etc. em RECORTES_ROOT).
RECORTE_PASTA_PAT = {
    "PIL": "*PL*",
    "LV":  "*LV*",
    "FV":  "*FV*",
    "LAJ": "*LJ*",
}

RECORTE_FILE_PREFIX = {
    "PIL": "PIL_",
    "LV":  "LV_",
    "FV":  "FV_",
    "LAJ": "LAJ_",
}

# -- Excecoes documentadas G2 -------------------------------------------------
LJ_CONTEXTO = {
    "id": "CTX-LJ-CONTORNO-ESTRUTURAL",
    "classe": "LAJ",
    "status": "APROVADO",
    "itens_exemplo": ["L308"],
    "padroes_texto": [
        r"^P\d+$",            # pilares vizinhos, ex.: P8, P49
        r"^\d+(?:[,.]\d+)?/\d+(?:[,.]\d+)?$",  # vigas de contorno, ex.: 19/120
        r"^\d{3,4}[,.]\d{1,2}$",  # nivel, ex.: 852.12
        r"^h\s*=\s*\d+(?:[,.]\d+)?$",  # espessura anotada, ex.: h=13
    ],
    "motivo": (
        "Anotacoes de vigas de contorno, pilares vizinhos, nivel e espessura "
        "pertencem ao contexto estrutural circundante. O produto do robo de "
        "laje e o contorno interno, linhas internas, cotas internas, HLAZ, "
        "nome e obstaculos."
    ),
    "aprovado_por": "usuario (sessao ARETE LAJE 2026-06-15)",
    "referencia": "docs/MASTERPLAN-ARETE-LAJE.md secao 6",
}

G2_EXCECOES = [
    {
        "id": "EXC-PIL-ABCD-FORMA",
        "status": "PENDENTE",  # nao e' aprovacao definitiva — revisar quando
                                # o algoritmo de corte/distribuicao de forma
                                # (painel/sarrafo/hachura) for replicado
        "classe": "PIL",
        "partes": ["ABCD"],
        "categorias_afetadas": ["paineis", "cotas"],
        "motivo": (
            "REF (recorte STOG humano) decompoe a forma em paineis/sarrafos/"
            "hachura via um algoritmo de corte/distribuicao em modulos "
            "(producao decimais nao-redondos, ex.: 4.24/23.35/48.36cm, "
            "variando por item). N4 (gerador atual) usa um modelo de 3 "
            "bandas fixas (h1/h2/h3). Amostragem de 5 itens (P1,P5,P10,P15,"
            "P20) confirmou que a decomposicao do REF NAO e' uma formula "
            "simples derivavel da ficha — e' um subsistema novo, fora do "
            "escopo de AR-1'."
        ),
        "extensao_cotas": (
            "Em P1#ABCD, 17/19 valores extras de `cotas` do REF sao "
            "dimensoes EXATAS de pecas de forma ja cobertas por esta "
            "exceção (so_ref de paineis); os outros 2 (4x valor '7') sao a "
            "largura de perfil do sarrafo 'SARR_2.2x7' (atributo do nome da "
            "layer, mesma classe). As cotas que CASAM (2.0x4 + 321.0) sao "
            "exatamente o 'modelo de 3 bandas' que ja bate hoje. Logo o "
            "FAIL de `cotas` e' o MESMO gap de fôrma, visto por outra "
            "categoria."
        ),
        "efeito": (
            "Para PIL/ABCD, `paineis` e `cotas` sao DIAGNOSTICO (calculados "
            "e reportados) mas NAO bloqueiam o gate G2 — apenas `textos` "
            "bloqueia (ver FORMA_BLOQUEIA_GATE / COTAS_BLOQUEIA_GATE em "
            "forma_canonica_pil.py)."
        ),
        "aprovado_por": "usuario (sessao 2026-06-13)",
        "referencia": "scripts/arete/relatorios/AR-1prime-canonico/RELATORIO.md",
        "revisao_futura": (
            "Quando um epico futuro replicar o algoritmo de corte/"
            "distribuicao de forma do STOG, remover esta exceção e "
            "reativar FORMA_BLOQUEIA_GATE/COTAS_BLOQUEIA_GATE para ABCD."
        ),
    },
    {
        "id": "EXC-PIL-P26-FASE4-VALIDACAO-ZERADA",
        "status": "SUPERSEDED",  # ver EXC-PIL-U-SHAPE-EFGH (sessao 2026-06-13
                                  # tarde): usuario refez recortes _sel_ de
                                  # P26/P27 nos 7 pavimentos e confirmou
                                  # "pilar em U" em todos — a hipotese
                                  # "extracao N2 zerada/atipica" foi
                                  # descartada. Mantido apenas como historico.
        "classe": "PIL",
        "pavimento": PAV_13,
        "partes": ["ABCD", "CIMA"],
        "itens": ["P26"],
        "categorias_afetadas": ["textos"],
        "motivo": (
            "REF#ABCD de P26 contem APENAS 2 vistas de face (P26.C, P26.D, "
            "larg=19), sem P26.A/P26.B (larg=60). N4 (gerador atual) sempre "
            "desenha as 4 faces padrao (A-D). O `_er_meta.dxf_validation` da "
            "ficha fase4 de P26 esta INTEIRAMENTE ZERADO (o motor reverso "
            "nao mediu nenhum campo a partir do DXF do recorte, apesar de "
            "confianca=0.95) — ou seja, a propria extracao N2/fase4 ja "
            "sinaliza que este recorte e' atipico. Como o gerador e o "
            "comparador canonico operam a partir da mesma ficha, nenhum fix "
            "de formula resolve isso; o gap esta na extracao N2 do recorte "
            "de P26. O mesmo recorte atipico afeta a vista CIMA: REF#CIMA "
            "traz rotulos '2 sar'/'5 sar' + 'P26.A'/'P26.B' (em vez de "
            "A-D), enquanto N4#CIMA desenha A-D padrao."
        ),
        "efeito": (
            "P26#ABCD permanece FAIL no gate canonico (textos: so_n4="
            "['P26.A','P26.B']) e P26#CIMA tambem FAIL (textos: so_ref="
            "['2 sar','2 sar','5 sar','5 sar','5 sar','5 sar','P26.A',"
            "'P26.B'], so_n4=['A','B','C','D']) ate' reextracao/revisao da "
            "ficha N2 deste item."
        ),
        "aprovado_por": "usuario (sessao 2026-06-13)",
        "referencia": "scripts/arete/relatorios/AR-1prime-canonico/RELATORIO.md",
        "revisao_futura": (
            "Reprocessar a extracao fase4 de P26 a partir do DXF do recorte "
            "(epico futuro de qualidade N2) e reavaliar se REF "
            "genuinamente so' tem 2 faces (caso em que o gerador precisaria "
            "de um modo 'pilar de 2 faces') ou se e' erro de extracao."
        ),
    },
    {
        "id": "EXC-PIL-P18-CAMBOTA",
        "status": "PENDENTE",
        "classe": "PIL",
        "pavimento": "TODOS",  # baseline 7 pisos (2026-06-13): P18 tambem
                                # FAIL em 12_PAV, com sintoma DIFERENTE
                                # (troca de letras de face A-E, sem
                                # CAMBOTA/CORTE A-A) — ver BIBLIOTECA Caso 1
        "partes": ["ABCD", "CIMA"],
        "itens": ["P18"],
        "categorias_afetadas": ["textos"],
        "motivo": (
            "REF#ABCD de P18 contem, alem de P18.B/P18.C, um bloco extra "
            "'CAMBOTA' + 'CORTE A-A' (duas vistas trapezoidais com cotas "
            "267.6/266/31.2) que substitui as posicoes onde N4 desenharia "
            "P18.A/P18.D. Esse bloco e' um detalhe construtivo adicional "
            "(provavel elemento de cobertura apoiado neste pilar), fora do "
            "modelo generico de 4 faces do gerador atual. Adicionalmente, "
            "`_er_meta.dxf_validation.largura=7.0` da ficha fase4 difere de "
            "`largura=19.0` (gap 63.2%, `fase4_vs_dxf_gaps`), indicando que "
            "a ficha N2 deste item ja' e' marcada como divergente do DXF "
            "medido. O mesmo bloco extra aparece na vista CIMA: REF#CIMA "
            "traz 'ENCH.' (enchimento) + 'P18.A' adicionais sem par em N4. "
            "Baseline 7 pisos (2026-06-13): em 12_PAV, P18 FAIL com sintoma "
            "DIFERENTE — sem CAMBOTA/CORTE A-A, apenas trocas de letra de "
            "face (P18.C/P18.E ausentes, P18.A/P18.B/P18.D extras em N4). "
            "PENDENTE separar 'cambota real' (13_PAV) de 'troca de "
            "rotulagem de face' (12_PAV) quando houver mais amostras."
        ),
        "efeito": (
            "P18#ABCD permanece FAIL no gate canonico (textos: so_ref="
            "['CAMBOTA','CORTE A-A','ENCH.','P18.C'], so_n4=['P18.A','P18.D'])"
            " e P18#CIMA tambem FAIL (textos: so_ref=['ENCH.','P18.A'], "
            "so_n4=[]) ate' o gerador suportar um modo 'pilar com cambota' "
            "(subsistema novo, fora do escopo AR-1') e/ou reextracao da "
            "ficha N2."
        ),
        "aprovado_por": "usuario (sessao 2026-06-13)",
        "referencia": "scripts/arete/relatorios/AR-1prime-canonico/RELATORIO.md",
        "revisao_futura": (
            "Epico futuro: suporte a pilares com detalhe de cambota/corte "
            "no gerador STOG + reextracao da ficha N2 de P18."
        ),
    },
    {
        "id": "EXC-PIL-P27-RECORTE-DUPLO",
        "status": "SUPERSEDED",  # ver EXC-PIL-U-SHAPE-EFGH (sessao 2026-06-13
                                  # tarde): a hipotese "recorte capturou 2
                                  # pilares (vizinho duplicado)" foi
                                  # descartada — os 6 labels A-F sao do
                                  # proprio P27 (pilar em U, confirmado pelo
                                  # usuario em 7 pavimentos). Mantido apenas
                                  # como historico.
        "classe": "PIL",
        "pavimento": PAV_13,
        "partes": ["ABCD", "CIMA"],
        "itens": ["P27"],
        "categorias_afetadas": ["textos"],
        "motivo": (
            "O recorte Fase-2 de P27 (`PIL_P27_motor_*.dxf`) tem ~3920 "
            "unidades de largura no eixo X — cerca de 3.2x a largura tipica "
            "de um recorte de 1 pilar (~1200 unidades, confirmado em P25 e "
            "P28). Esse recorte contem 6 labels de face (P27.A-F) e 2 "
            "cabecalhos '13° PAVIMENTO - PD: 3.21' duplicados — ou seja, "
            "capturou o bloco ABCD de um pilar vizinho (E/F + header "
            "duplicado) junto com o bloco proprio de P27 (A-D). "
            "`_er_meta.dxf_validation` de P27 mediu 6 faces com "
            "comprimento=98/largura=6/grade_1=120, divergindo da ficha "
            "fase4 (comprimento=60/largura=19/grade_1=88, gaps de "
            "63.3%/68.4%/36.4%) — consistente com o recorte conter geometria"
            " de 2 pilares distintos. O mesmo recorte duplo afeta a vista "
            "CIMA: REF#CIMA traz 'E'/'F' adicionais (faces do pilar "
            "vizinho) sem par em N4."
        ),
        "efeito": (
            "P27#ABCD permanece FAIL no gate canonico (textos: so_ref tem "
            "22 itens extras incluindo P27.E, P27.F, header PD duplicado e "
            "labels 'X sar'/'SP' do pilar vizinho; so_n4=[] — todos os 5 "
            "itens de N4 casaram). P27#CIMA tambem FAIL (textos: so_ref="
            "['E','F'], so_n4=[]). Nao e' um problema do gerador nem da "
            "regua canonica (P25/P28, com recortes normais, passam "
            "limpamente)."
        ),
        "aprovado_por": "usuario (sessao 2026-06-13)",
        "referencia": "scripts/arete/relatorios/AR-1prime-canonico/RELATORIO.md",
        "revisao_futura": (
            "Epico futuro de qualidade N2/Fase-2: re-recortar "
            "`PIL_P27_motor_*.dxf` para conter apenas o bloco ABCD proprio "
            "de P27 (x ~6400-7400), removendo o bloco do pilar vizinho "
            "(E/F + header duplicado, x ~8100-8900)."
        ),
    },
    {
        "id": "EXC-PIL-CIMA-FORMA",
        "status": "PENDENTE",  # mesma natureza de EXC-PIL-ABCD-FORMA, agora
                                # para a vista CIMA (secao transversal)
        "classe": "PIL",
        "partes": ["CIMA"],
        "categorias_afetadas": ["paineis", "cotas"],
        "motivo": (
            "Assim como em ABCD (EXC-PIL-ABCD-FORMA), a vista CIMA do REF "
            "(recorte STOG humano) decompoe a secao transversal em "
            "centenas de entidades de hachura/sarrafo/chapa (ex.: P1#CIMA "
            "REF tem 615 entidades vs. 46 em N4) — resultado de um "
            "algoritmo de corte/preenchimento que N4 (gerador atual, modelo"
            " simplificado de secao) nao replica. Layers adicionais nao "
            "mapeadas aparecem nesta vista: REF tem 'CONCRETO', "
            "'MEIO_PONT', 'SARRAFO' (alem das ja mapeadas); N4 tem "
            "'GRAVATA', 'SARRAFO' — confirmado na uniao das 35 amostras "
            "(ver scripts/arete/tmp/check_cima_naomapeado.py)."
        ),
        "efeito": (
            "Para PIL/CIMA, `paineis` e `cotas` sao DIAGNOSTICO (calculados"
            " e reportados, incluindo as layers nao mapeadas acima em "
            "`nao_mapeado_ref`/`nao_mapeado_n4`) mas NAO bloqueiam o gate "
            "G2 — apenas `textos` bloqueia (mesmas flags globais "
            "FORMA_BLOQUEIA_GATE/COTAS_BLOQUEIA_GATE=False de "
            "forma_canonica_pil.py, ja aprovadas para ABCD)."
        ),
        "aprovado_por": "usuario (sessao 2026-06-13, extensao do escopo "
                         "EXC-PIL-ABCD-FORMA aprovado para ABCD)",
        "referencia": "scripts/arete/relatorios/AR-1prime-canonico/RELATORIO.md",
        "revisao_futura": (
            "Quando o epico futuro de corte/distribuicao de forma (citado "
            "em EXC-PIL-ABCD-FORMA) for executado, mapear 'CONCRETO', "
            "'MEIO_PONT', 'SARRAFO' (REF) e 'GRAVATA', 'SARRAFO' (N4) em "
            "LAYER_CATEGORY_MAP, replicar a decomposicao de CIMA no "
            "gerador, e reativar FORMA_BLOQUEIA_GATE/COTAS_BLOQUEIA_GATE "
            "para CIMA."
        ),
    },
    {
        "id": "EXC-PIL-U-SHAPE-EFGH",
        "status": "PENDENTE",
        "classe": "PIL",
        "pavimento": "TODOS",  # confirmado em 7 pavimentos da Obra_TREINO_1
        "partes": ["ABCD", "CIMA"],
        "itens": ["P15", "P23", "P26", "P27"],  # baseline 7 pisos
                                                  # (2026-06-13): P15/P23
                                                  # confirmados na mesma
                                                  # familia (rotulos "N sar")
        "categorias_afetadas": ["textos", "paineis", "cotas"],
        "motivo": (
            "Sessao 2026-06-13 (tarde): usuario refez manualmente os "
            "recortes (_sel_*) de TODOS os pilares dos 7 pavimentos da "
            "Obra_TREINO_1 e confirmou que P26 e P27 sao genuinamente "
            "PILARES EM U (subtipo) em TODOS os pavimentos — supersede "
            "EXC-PIL-P26-FASE4-VALIDACAO-ZERADA e EXC-PIL-P27-RECORTE-DUPLO. "
            "Apos ficha_adapter.get_recorte_path passar a preferir _sel_* "
            "sobre _motor_* (Fase A+B/AR-1'), o G2 canonico de 13_PAV mostra "
            "padrao SIMETRICO para ambos: REF#ABCD tem rotulos 'N sar' "
            "(sarrafo) sem par em N4, e REF#ABCD/CIMA decompoem a secao em "
            "centenas de paineis/hachura (P26: hachura ref=1113 vs n4=0, "
            "painel ref=104 vs n4=13; P27: painel ref=198 vs n4=13) — a "
            "vista CIMA real (secao em U) esta projetada dentro do bloco "
            "ABCD do recorte. A ficha Fase-4 (motor_reverso_pil) continua "
            "com comprimento=60/largura=19 constantes e campos *_E/*_F "
            "zerados para P26/P27 nos 7 pavimentos — o gap migrou do "
            "recorte (resolvido) para a EXTRACAO N2->Fase4 e para o "
            "GERADOR (que so' desenha A-D). "
            "Baseline 7 pisos (2026-06-13): P15 e P23 (FAIL em 1_PAV, "
            "2_PAV, TERREO) tem o MESMO padrao 'N sar' ausente em N4#ABCD — "
            "mesma familia 'pilar em U'. Total 19 amostras "
            "(P26x7+P27x6+P15x3+P23x3). Duas variantes visuais do mesmo "
            "defeito: 'N sar' (contagem de sarrafo) ou 'A-E' (letra de "
            "face solta) ausentes em N4#ABCD, dependendo do recorte — "
            "P26 em 14_PAV/COBERTURA e P27 em 1_PAV usam a variante 'A-E'."
        ),
        "efeito": (
            "P26, P27, P15 e P23 permanecem FAIL no gate canonico (ABCD e "
            "CIMA, textos+paineis+cotas) ate' (1) motor_reverso_pil popular "
            "*_E/*_F a partir da geometria CIMA real do recorte (Fase C, "
            "usando as 19 amostras como dataset), e (2) gerar_pl_dxf_stog.py "
            "implementar 'modo EFGH' portado da logica de pilar especial de "
            "grade_calculator.py (Fase D, com regressao verde nas 20 "
            "obras)."
        ),
        "aprovado_por": "usuario (sessao 2026-06-13 tarde)",
        "referencia": "scripts/arete/BIBLIOTECA_ANORMALIDADES_PIL.md (Caso 2)",
        "revisao_futura": (
            "Remover esta exceção quando Fases C+D estiverem concluidas e "
            "P15/P23/P26/P27 passarem no G2 canonico em todos os "
            "pavimentos onde existem. PENDENTE: aguardando mais obras antes "
            "de iniciar Fase C/D (decisao usuario 2026-06-13)."
        ),
    },
    {
        "id": "EXC-PIL-CORNER-3FACE",
        "status": "PENDENTE",
        "classe": "PIL",
        "pavimento": "TERREO",  # so' 1 pavimento ate' agora
        "partes": ["ABCD", "CIMA"],
        "itens": ["P28", "P29", "P30", "P31", "P32"],
        "categorias_afetadas": ["textos"],
        "motivo": (
            "Baseline 7 pisos (2026-06-13): em TERREO, 5 itens (P28,P29,"
            "P30,P31,P32) tem padrao INVERSO ao 'pilar em U' — N4 gera um "
            "rotulo de face EXTRA que o REF nao tem: P28/P29 tem "
            "'PXX.D'/'D' extra em N4 (ABCD/CIMA); P30/P31/P32 tem "
            "'PXX.A'/'A' extra em N4. Hipotese nao confirmada: pilares de "
            "canto/extremidade com apenas 3 faces fisicas (face encostada "
            "em parede/viga, sem painel visivel) — REF nao desenha essa "
            "face mas N4 sempre desenha as 4 faces A-D padrao."
        ),
        "efeito": (
            "P28/P29/P30/P31/P32 permanecem FAIL no gate canonico (ABCD e "
            "CIMA, textos) ate' confirmar a hipotese 'pilar de canto (3 "
            "faces)' com mais obras e o gerador suportar modo '3 faces'."
        ),
        "aprovado_por": "usuario (sessao 2026-06-13 tarde)",
        "referencia": "scripts/arete/BIBLIOTECA_ANORMALIDADES_PIL.md (Caso 3)",
        "revisao_futura": (
            "PENDENTE: aguardando mais obras/pavimentos para confirmar "
            "hipotese 'pilar de canto (3 faces)' antes de implementar fix."
        ),
    },
    {
        "id": "EXC-PIL-LABEL-PLACEMENT-CIMA-ABCD",
        "status": "PENDENTE",
        "classe": "PIL",
        "pavimento": "TODOS",  # ocorre em 14_PAV e COBERTURA ate' agora
        "partes": ["ABCD", "CIMA"],
        "itens": ["P43", "P47", "P49", "P51", "P25"],
        "categorias_afetadas": ["textos"],
        "motivo": (
            "Baseline 7 pisos (2026-06-13): em 14_PAV (P43,P47,P49) e "
            "COBERTURA (P49,P51,P25), N4 desenha os rotulos 'PXX.A'/'PXX.B' "
            "na parte ABCD, mas o REF espera esses rotulos na parte CIMA "
            "(sem equivalente em ABCD). Total 6 ocorrencias. Hipotese nao "
            "confirmada: bug sistematico de placement no gerador (rotulo "
            "vai para o bloco errado), possivelmente um fix de causa unica "
            "de alto impacto — mas por decisao do usuario fica PENDENTE "
            "ate' reunir evidencia de mais obras/pavimentos."
        ),
        "efeito": (
            "P43/P47/P49/P51/P25 permanecem FAIL no gate canonico (ABCD e "
            "CIMA, textos) ate' confirmar e corrigir o placement no "
            "gerador."
        ),
        "aprovado_por": "usuario (sessao 2026-06-13 tarde)",
        "referencia": "scripts/arete/BIBLIOTECA_ANORMALIDADES_PIL.md (Caso 4)",
        "revisao_futura": (
            "PENDENTE: aguardando mais obras antes de investigar/corrigir "
            "placement CIMA vs ABCD (decisao usuario 2026-06-13)."
        ),
    },
    {
        "id": "EXC-PIL-P24-NAMING-DOT",
        "status": "PENDENTE",
        "classe": "PIL",
        "pavimento": "TODOS",  # 1_PAV, 2_PAV, 12_PAV, TERREO
        "partes": ["ABCD"],
        "itens": ["P24"],
        "categorias_afetadas": ["textos"],
        "motivo": (
            "Baseline 7 pisos (2026-06-13): em 1_PAV, 2_PAV, 12_PAV e "
            "TERREO (mesmo item, mesmo bug em todos), REF#ABCD tem texto "
            "'P24C' (sem separador) enquanto N4#ABCD gera 'P24.C' (com "
            "ponto). Hipotese nao confirmada: (a) bug de normalizacao no "
            "comparador canonico (forma_canonica_pil.py deveria tratar "
            "'P24C' == 'P24.C'), ou (b) convencao de nome de face sem ponto "
            "genuina no recorte de P24 (possivel erro de digitacao STOG "
            "recorrente por copy-paste entre pavimentos)."
        ),
        "efeito": (
            "P24 permanece FAIL no gate canonico (ABCD, textos) ate' "
            "confirmar se e' bug de normalizacao ou convencao do recorte."
        ),
        "aprovado_por": "usuario (sessao 2026-06-13 tarde)",
        "referencia": "scripts/arete/BIBLIOTECA_ANORMALIDADES_PIL.md (Caso 5)",
        "revisao_futura": (
            "PENDENTE: aguardando mais obras antes de investigar "
            "normalizacao 'P24C' vs 'P24.C' (decisao usuario 2026-06-13)."
        ),
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Subtipo PIL — classificação canônica por elemento_id (Obra_TREINO_1 baseline)
# ─────────────────────────────────────────────────────────────────────────────
# Valores possíveis:
#   'RETANGULAR' — pilar padrão, 4 faces A-D, gerador cobre completamente
#   'L'          — pilar em L; CIMA combinada e faces adicionais E/F (sem G/H)
#   'ESPECIAL'   — outros subtipos (P15/P23: rótulos N-sar, possivelmente
#                  L/T/Canto; P18: cambota diagonal; P28-32: canto/3-face;
#                  P43/47/49/51/P25: placement; P24: naming; P2: face-swap)
#                  → sem regras de desenho ainda; classificação registrada
#                  para futura implementação por subtipo
#
# Fonte: BIBLIOTECA_ANORMALIDADES_PIL.md (sessão 2026-06-13)
# Baseline: Obra_TREINO_1, 7 pavimentos
# Nota: elemento_ids sem entrada aqui são RETANGULAR por default
SUBTIPO_PIL: dict[str, str] = {
    # ── Subtipo L (CIMA combinada + faces E/F, sem G/H) ───────────────────
    "P26": "L",
    "P27": "L",
    # ── Especial — família "rótulo N-sar/letra-face" (possivelmente L/T) ──
    "P15": "ESPECIAL",
    "P23": "ESPECIAL",
    # ── Especial — outros padrões individuais ─────────────────────────────
    "P18": "ESPECIAL",   # cambota diagonal (CAMBOTA / CORTE A-A)
    "P28": "ESPECIAL",   # corner / 3-face (TERREO)
    "P29": "ESPECIAL",
    "P30": "ESPECIAL",
    "P31": "ESPECIAL",
    "P32": "ESPECIAL",
    "P43": "ESPECIAL",   # label placement CIMA↔ABCD
    "P47": "ESPECIAL",
    "P49": "ESPECIAL",
    "P51": "ESPECIAL",
    "P25": "ESPECIAL",
    "P24": "ESPECIAL",   # naming dot "P24C" vs "P24.C"
    "P2":  "ESPECIAL",   # face-swap A↔B (1 amostra, 1_PAV)
}


def get_subtipo_pil(elemento_id: str) -> str:
    """Retorna o subtipo canônico de um pilar PIL.

    Valores: 'RETANGULAR' | 'U' | 'ESPECIAL'
    Pilares não listados em SUBTIPO_PIL são 'RETANGULAR' por default.
    """
    return SUBTIPO_PIL.get(elemento_id.upper(), "RETANGULAR")
