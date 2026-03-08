
# Helper de ofuscação (adicionado automaticamente)
def _get_obf_str(key):
    """Retorna string ofuscada"""
    _obf_map = {
        _get_obf_str("script.google.com"): base64.b64decode("=02bj5SZsd2bvdmL0BXayN2c"[::-1].encode()).decode(),
        _get_obf_str("macros/s/"): base64.b64decode("vM3Lz9mcjFWb"[::-1].encode()).decode(),
        _get_obf_str("AKfycbz"): base64.b64decode("==geiNWemtUQ"[::-1].encode()).decode(),
        _get_obf_str("credit"): base64.b64decode("0lGZlJ3Y"[::-1].encode()).decode(),
        _get_obf_str("saldo"): base64.b64decode("=8GZsF2c"[::-1].encode()).decode(),
        _get_obf_str("consumo"): base64.b64decode("==wbtV3cu92Y"[::-1].encode()).decode(),
        _get_obf_str("api_key"): base64.b64decode("==Qelt2XpBXY"[::-1].encode()).decode(),
        _get_obf_str("user_id"): base64.b64decode("==AZp9lclNXd"[::-1].encode()).decode(),
        _get_obf_str("calcular_creditos"): base64.b64decode("=M3b0lGZlJ3YfJXYsV3YsF2Y"[::-1].encode()).decode(),
        _get_obf_str("confirmar_consumo"): base64.b64decode("=8Wb1NnbvN2XyFWbylmZu92Y"[::-1].encode()).decode(),
        _get_obf_str("consultar_saldo"): base64.b64decode("vRGbhN3XyFGdsV3cu92Y"[::-1].encode()).decode(),
        _get_obf_str("debitar_creditos"): base64.b64decode("==wcvRXakVmcj9lchRXaiVGZ"[::-1].encode()).decode(),
        _get_obf_str("CreditManager"): base64.b64decode("==gcldWYuFWT0lGZlJ3Q"[::-1].encode()).decode(),
        _get_obf_str("obter_hwid"): base64.b64decode("==AZpdHafJXZ0J2b"[::-1].encode()).decode(),
        _get_obf_str("generate_signature"): base64.b64decode("lJXd0Fmbnl2cfVGdhJXZuV2Z"[::-1].encode()).decode(),
        _get_obf_str("encrypt_string"): base64.b64decode("=cmbpJHdz9Fdwlncj5WZ"[::-1].encode()).decode(),
        _get_obf_str("decrypt_string"): base64.b64decode("=cmbpJHdz9FdwlncjVGZ"[::-1].encode()).decode(),
        _get_obf_str("integrity_check"): base64.b64decode("rNWZoN2X5RXaydWZ05Wa"[::-1].encode()).decode(),
        _get_obf_str("security_utils"): base64.b64decode("=MHbpRXdflHdpJXdjV2c"[::-1].encode()).decode(),
        _get_obf_str("https://"): base64.b64decode("=8yL6MHc0RHa"[::-1].encode()).decode(),
        _get_obf_str("google.com"): base64.b64decode("==QbvNmLlx2Zv92Z"[::-1].encode()).decode(),
        _get_obf_str("apps.script"): base64.b64decode("=QHcpJ3Yz5ycwBXY"[::-1].encode()).decode(),
    }
    return _obf_map.get(key, key)

"""
Arquivo excel_mapping.py - Contém apenas o mapeamento de campos para o Excel
Este arquivo é usado pelo PilarAnalyzer para definir como os campos são mapeados para linhas no Excel.
"""

# Dicionário de mapeamento entre campos do programa e linhas do Excel
EXCEL_MAPPING = {
    # Dados Gerais
    "nome": 4,
    "comprimento": 6,
    "largura": 7,
    "pavimento": 3,
    "pavimento_anterior": 2,
    "nivel_saida": 8,
    "nivel_chegada": 9,
    "nivel_diferencial": 10,
    "altura": 12,

    # Parafusos
    "par_1_2": 173,
    "par_2_3": 174,
    "par_3_4": 175,
    "par_4_5": 176,
    "par_5_6": 177,
    "par_6_7": 178,
    "par_7_8": 179,
    "par_8_9": 180,

    # Grades - CONSISTENTE com interface
    # grade_1 (largura) -> linha 180
    # NADA na linha 181 (era grade_1 antigo)
    # distancia_1 -> linha 182
    # grade_2 (largura) -> linha 183
    # distancia_2 -> linha 184
    # grade_3 (largura) -> linha 185
    "grade_1": 180,
    "distancia_1": 182,
    "grade_2": 183,
    "distancia_2": 184,
    "grade_3": 185,

    # Painel A
    "laje_A": 13,
    "posicao_laje_A": 14,
    "larg1_A": 15,
    "larg2_A": 16,
    "larg3_A": 17,
    "h1_A": 18,
    "h2_A": 19,
    "h3_A": 20,
    "h4_A": 21,
    "h5_A": 22,

    # Aberturas A Esquerda
    "distancia_esq_1_A": 25,
    "largura_esq_1_A": 27,
    "profundidade_esq_1_A": 26,
    "posicao_esq_1_A": 28,
    "distancia_esq_2_A": 29,
    "largura_esq_2_A": 31,
    "profundidade_esq_2_A": 30,
    "posicao_esq_2_A": 32,

    # Aberturas A Direita
    "distancia_dir_1_A": 33,
    "largura_dir_1_A": 35,
    "profundidade_dir_1_A": 34,
    "posicao_dir_1_A": 36,
    "distancia_dir_2_A": 37,
    "largura_dir_2_A": 39,
    "profundidade_dir_2_A": 38,
    "posicao_dir_2_A": 40,

    # Painel B
    "laje_B": 55,
    "posicao_laje_B": 56,
    "larg1_B": 57,
    "larg2_B": 58,
    "larg3_B": 59,
    "h1_B": 60,
    "h2_B": 61,
    "h3_B": 62,
    "h4_B": 63,
    "h5_B": 64,

    # Aberturas B Esquerda
    "distancia_esq_1_B": 67,
    "largura_esq_1_B": 69,
    "profundidade_esq_1_B": 68,
    "posicao_esq_1_B": 70,
    "distancia_esq_2_B": 71,
    "largura_esq_2_B": 73,
    "profundidade_esq_2_B": 72,
    "posicao_esq_2_B": 74,

    # Aberturas B Direita
    "distancia_dir_1_B": 75,
    "largura_dir_1_B": 77,
    "profundidade_dir_1_B": 76,
    "posicao_dir_1_B": 78,
    "distancia_dir_2_B": 79,
    "largura_dir_2_B": 81,
    "profundidade_dir_2_B": 80,
    "posicao_dir_2_B": 82,

    # Painel C
    "laje_C": 97,
    "posicao_laje_C": 98,
    "larg1_C": 99,
    "larg2_C": 100,
    "h1_C": 101,
    "h2_C": 102,
    "h3_C": 103,
    "h4_C": 104,

    # Painel D
    "laje_D": 131,
    "posicao_laje_D": 132,
    "larg1_D": 133,
    "larg2_D": 134,
    "h1_D": 135,
    "h2_D": 136,
    "h3_D": 137,
    "h4_D": 138,

    # Painel E (Pilar Especial)
    "laje_E": 250,
    "posicao_laje_E": 251,
    "larg1_E": 252,
    "larg2_E": 253,
    "larg3_E": 254,
    "h1_E": 255,
    "h2_E": 256,
    "h3_E": 257,
    "h4_E": 258,
    "h5_E": 259,

    # Painel F (Pilar Especial)
    "laje_F": 260,
    "posicao_laje_F": 261,
    "larg1_F": 262,
    "larg2_F": 263,
    "larg3_F": 264,
    "h1_F": 265,
    "h2_F": 266,
    "h3_F": 267,
    "h4_F": 268,
    "h5_F": 269,

    # Painel G (Pilar Especial)
    "laje_G": 270,
    "posicao_laje_G": 271,
    "larg1_G": 272,
    "larg2_G": 273,
    "larg3_G": 274,
    "h1_G": 275,
    "h2_G": 276,
    "h3_G": 277,
    "h4_G": 278,
    "h5_G": 279,

    # Painel H (Pilar Especial)
    "laje_H": 280,
    "posicao_laje_H": 281,
    "larg1_H": 282,
    "larg2_H": 283,
    "larg3_H": 284,
    "h1_H": 285,
    "h2_H": 286,
    "h3_H": 287,
    "h4_H": 288,
    "h5_H": 289,

    # Larguras das Grades (REMOVIDO - usar grade_1, grade_2, grade_3 acima)
    # "grade1_largura": 180,  # DUPLICADO - usar "grade_1"
    # "grade2_largura": 181,  # DUPLICADO - usar "grade_2"
    # "grade3_largura": 182,  # DUPLICADO - usar "grade_3"
    
    # Detalhes das Grades
    "detalhe_grade1_1": 192,
    "detalhe_grade1_2": 193,
    "detalhe_grade1_3": 194,
    "detalhe_grade1_4": 195,
    "detalhe_grade1_5": 196,
    "detalhe_grade2_1": 197,
    "detalhe_grade2_2": 198,
    "detalhe_grade2_3": 199,
    "detalhe_grade2_4": 200,
    "detalhe_grade2_5": 201,
    "detalhe_grade3_1": 202,
    "detalhe_grade3_2": 203,
    "detalhe_grade3_3": 204,
    "detalhe_grade3_4": 205,
    "detalhe_grade3_5": 206,
    
    # === ALTURAS DOS DETALHES - CONJUNTO 1 (GRADE A) ===
    # Grade A - 1 (linhas 207-212)
    "altura_detalhe_grade_a_1_0": 207,  # Campo 0 - Altura do sarrafo da extremidade esquerda
    "altura_detalhe_grade_a_1_1": 208,
    "altura_detalhe_grade_a_1_2": 209,
    "altura_detalhe_grade_a_1_3": 210,
    "altura_detalhe_grade_a_1_4": 211,
    "altura_detalhe_grade_a_1_5": 212,
    
    # Grade A - 2 (linhas 213-218)
    "altura_detalhe_grade_a_2_0": 213,  # Campo 0 - Altura do sarrafo da extremidade esquerda
    "altura_detalhe_grade_a_2_1": 214,
    "altura_detalhe_grade_a_2_2": 215,
    "altura_detalhe_grade_a_2_3": 216,
    "altura_detalhe_grade_a_2_4": 217,
    "altura_detalhe_grade_a_2_5": 218,
    
    # Grade A - 3 (linhas 250-255)
    "altura_detalhe_grade_a_3_0": 250,  # Campo 0 - Altura do sarrafo da extremidade esquerda
    "altura_detalhe_grade_a_3_1": 251,
    "altura_detalhe_grade_a_3_2": 252,
    "altura_detalhe_grade_a_3_3": 253,
    "altura_detalhe_grade_a_3_4": 254,
    "altura_detalhe_grade_a_3_5": 255,
    
    # === ALTURAS DOS DETALHES - CONJUNTO 2 (GRADE B) ===
    # Grade B - 1 (linhas 256-261)
    "altura_detalhe_grade_b_1_0": 256,
    "altura_detalhe_grade_b_1_1": 257,
    "altura_detalhe_grade_b_1_2": 258,
    "altura_detalhe_grade_b_1_3": 259,
    "altura_detalhe_grade_b_1_4": 260,
    "altura_detalhe_grade_b_1_5": 261,
    
    # Grade B - 2 (linhas 262-267)
    "altura_detalhe_grade_b_2_0": 262,
    "altura_detalhe_grade_b_2_1": 263,
    "altura_detalhe_grade_b_2_2": 264,
    "altura_detalhe_grade_b_2_3": 265,
    "altura_detalhe_grade_b_2_4": 266,
    "altura_detalhe_grade_b_2_5": 267,
    
    # Grade B - 3 (linhas 268-273)
    "altura_detalhe_grade_b_3_0": 268,
    "altura_detalhe_grade_b_3_1": 269,
    "altura_detalhe_grade_b_3_2": 270,
    "altura_detalhe_grade_b_3_3": 271,
    "altura_detalhe_grade_b_3_4": 272,
    "altura_detalhe_grade_b_3_5": 273,

    # Pilar Especial - Adicionado para suporte ao checkbox "Pilar Rotacionado"
    "pilar_especial_ativo": 210,      # Indica se pilar especial está ativo (True/False)
    "tipo_pilar_especial": 211,       # Tipo do pilar especial (L, T, U)
    "comp_1": 212,                    # Comprimento 1
    "comp_2": 213,                    # Comprimento 2
    "comp_3": 214,                    # Comprimento 3
    "larg_1": 215,                    # Largura 1
    "larg_2": 216,                    # Largura 2
    "larg_3": 217,                    # Largura 3
    "distancia_pilar_especial": 218,  # Distância (para tipo T)

    # Grade Grupo 2 - Adicionado para suporte ao segundo grupo de grades
    "grade_1_grupo2": 219,            # Grade 1 do Grupo 2
    "distancia_1_grupo2": 220,        # Distância 1 do Grupo 2
    "grade_2_grupo2": 221,            # Grade 2 do Grupo 2
    "distancia_2_grupo2": 222,        # Distância 2 do Grupo 2
    "grade_3_grupo2": 223,            # Grade 3 do Grupo 2

    # Aberturas de Laje - Painel A
    "abertura_laje_esq1_a": 224,      # Abertura Laje Esquerda 1 A
    "abertura_laje_esq2_a": 225,      # Abertura Laje Esquerda 2 A
    "abertura_laje_dir1_a": 226,      # Abertura Laje Direita 1 A
    "abertura_laje_dir2_a": 227,      # Abertura Laje Direita 2 A
    
    # Aberturas de Laje - Painel B
    "abertura_laje_esq1_b": 228,      # Abertura Laje Esquerda 1 B
    "abertura_laje_esq2_b": 229,      # Abertura Laje Esquerda 2 B
    "abertura_laje_dir1_b": 230,      # Abertura Laje Direita 1 B
    "abertura_laje_dir2_b": 231,      # Abertura Laje Direita 2 B
    
    # Aberturas de Laje - Painel C
    "abertura_laje_esq1_c": 232,      # Abertura Laje Esquerda 1 C
    "abertura_laje_esq2_c": 233,      # Abertura Laje Esquerda 2 C
    "abertura_laje_dir1_c": 234,      # Abertura Laje Direita 1 C
    "abertura_laje_dir2_c": 235,      # Abertura Laje Direita 2 C
    
    # Aberturas de Laje - Painel D
    "abertura_laje_esq1_d": 236,      # Abertura Laje Esquerda 1 D
    "abertura_laje_esq2_d": 237,      # Abertura Laje Esquerda 2 D
    "abertura_laje_dir1_d": 238,      # Abertura Laje Direita 1 D
    "abertura_laje_dir2_d": 239,      # Abertura Laje Direita 2 D

    # Detalhes das Grades do Grupo 2 (linhas 518-532 - área livre sem conflitos)
    "detalhe_grade1_1_grupo2": 518,
    "detalhe_grade1_2_grupo2": 519,
    "detalhe_grade1_3_grupo2": 520,
    "detalhe_grade1_4_grupo2": 521,
    "detalhe_grade1_5_grupo2": 522,
    "detalhe_grade2_1_grupo2": 523,
    "detalhe_grade2_2_grupo2": 524,
    "detalhe_grade2_3_grupo2": 525,
    "detalhe_grade2_4_grupo2": 526,
    "detalhe_grade2_5_grupo2": 527,
    "detalhe_grade3_1_grupo2": 528,
    "detalhe_grade3_2_grupo2": 529,
    "detalhe_grade3_3_grupo2": 530,
    "detalhe_grade3_4_grupo2": 531,
    "detalhe_grade3_5_grupo2": 532,
    
    # ===== GRADES ESPECIAIS (A, B, E, F, G, H) - PILARES ESPECIAIS =====
    # NOTA: Campos da interface usam nomenclatura grade_{letra}_{num} (ex: grade_a_1)
    # Usar linhas 290+ para evitar conflitos com campos existentes
    
    # Grade A Especial (linhas 290-327)
    "grade_a_1": 290,  # Grade A Especial - Grade 1
    "dist_a_1": 291,   # Grade A Especial - Distância 1
    "grade_a_2": 292,  # Grade A Especial - Grade 2  
    "dist_a_2": 293,   # Grade A Especial - Distância 2
    "grade_a_3": 294,  # Grade A Especial - Grade 3
    # Detalhes Grade A Especial (linhas 295-309)
    "detalhe_a_1_1": 295,
    "detalhe_a_1_2": 296,
    "detalhe_a_1_3": 297,
    "detalhe_a_1_4": 298,
    "detalhe_a_1_5": 299,
    "detalhe_a_2_1": 300,
    "detalhe_a_2_2": 301,
    "detalhe_a_2_3": 302,
    "detalhe_a_2_4": 303,
    "detalhe_a_2_5": 304,
    "detalhe_a_3_1": 305,
    "detalhe_a_3_2": 306,
    "detalhe_a_3_3": 307,
    "detalhe_a_3_4": 308,
    "detalhe_a_3_5": 309,
    # Alturas Grade A Especial (linhas 310-336)
    "altura_detalhe_a_1_0": 310,
    "altura_detalhe_a_1_1": 311,
    "altura_detalhe_a_1_2": 312,
    "altura_detalhe_a_1_3": 313,
    "altura_detalhe_a_1_4": 314,
    "altura_detalhe_a_1_5": 315,
    "altura_detalhe_a_2_0": 316,
    "altura_detalhe_a_2_1": 317,
    "altura_detalhe_a_2_2": 318,
    "altura_detalhe_a_2_3": 319,
    "altura_detalhe_a_2_4": 320,
    "altura_detalhe_a_2_5": 321,
    "altura_detalhe_a_3_0": 322,
    "altura_detalhe_a_3_1": 323,
    "altura_detalhe_a_3_2": 324,
    "altura_detalhe_a_3_3": 325,
    "altura_detalhe_a_3_4": 326,
    "altura_detalhe_a_3_5": 327,
    
    # Grade B Especial (linhas 328-365)
    "grade_b_1": 328,  # Grade B Especial - Grade 1
    "dist_b_1": 329,   # Grade B Especial - Distância 1
    "grade_b_2": 330,  # Grade B Especial - Grade 2
    "dist_b_2": 331,   # Grade B Especial - Distância 2
    "grade_b_3": 332,  # Grade B Especial - Grade 3
    # Detalhes Grade B Especial (linhas 333-347)
    "detalhe_b_1_1": 333,
    "detalhe_b_1_2": 334,
    "detalhe_b_1_3": 335,
    "detalhe_b_1_4": 336,
    "detalhe_b_1_5": 337,
    "detalhe_b_2_1": 338,
    "detalhe_b_2_2": 339,
    "detalhe_b_2_3": 340,
    "detalhe_b_2_4": 341,
    "detalhe_b_2_5": 342,
    "detalhe_b_3_1": 343,
    "detalhe_b_3_2": 344,
    "detalhe_b_3_3": 345,
    "detalhe_b_3_4": 346,
    "detalhe_b_3_5": 347,
    # Alturas Grade B Especial (linhas 348-374)
    "altura_detalhe_b_1_0": 348,
    "altura_detalhe_b_1_1": 349,
    "altura_detalhe_b_1_2": 350,
    "altura_detalhe_b_1_3": 351,
    "altura_detalhe_b_1_4": 352,
    "altura_detalhe_b_1_5": 353,
    "altura_detalhe_b_2_0": 354,
    "altura_detalhe_b_2_1": 355,
    "altura_detalhe_b_2_2": 356,
    "altura_detalhe_b_2_3": 357,
    "altura_detalhe_b_2_4": 358,
    "altura_detalhe_b_2_5": 359,
    "altura_detalhe_b_3_0": 360,
    "altura_detalhe_b_3_1": 361,
    "altura_detalhe_b_3_2": 362,
    "altura_detalhe_b_3_3": 363,
    "altura_detalhe_b_3_4": 364,
    "altura_detalhe_b_3_5": 365,
    
    # Grade E Especial (linhas 366-403)
    "grade_e_1": 366,
    "dist_e_1": 367,
    "grade_e_2": 368,
    "dist_e_2": 369,
    "grade_e_3": 370,
    # Detalhes Grade E Especial (linhas 371-385)
    "detalhe_e_1_1": 371,
    "detalhe_e_1_2": 372,
    "detalhe_e_1_3": 373,
    "detalhe_e_1_4": 374,
    "detalhe_e_1_5": 375,
    "detalhe_e_2_1": 376,
    "detalhe_e_2_2": 377,
    "detalhe_e_2_3": 378,
    "detalhe_e_2_4": 379,
    "detalhe_e_2_5": 380,
    "detalhe_e_3_1": 381,
    "detalhe_e_3_2": 382,
    "detalhe_e_3_3": 383,
    "detalhe_e_3_4": 384,
    "detalhe_e_3_5": 385,
    # Alturas Grade E Especial (linhas 386-412)
    "altura_detalhe_e_1_0": 386,
    "altura_detalhe_e_1_1": 387,
    "altura_detalhe_e_1_2": 388,
    "altura_detalhe_e_1_3": 389,
    "altura_detalhe_e_1_4": 390,
    "altura_detalhe_e_1_5": 391,
    "altura_detalhe_e_2_0": 392,
    "altura_detalhe_e_2_1": 393,
    "altura_detalhe_e_2_2": 394,
    "altura_detalhe_e_2_3": 395,
    "altura_detalhe_e_2_4": 396,
    "altura_detalhe_e_2_5": 397,
    "altura_detalhe_e_3_0": 398,
    "altura_detalhe_e_3_1": 399,
    "altura_detalhe_e_3_2": 400,
    "altura_detalhe_e_3_3": 401,
    "altura_detalhe_e_3_4": 402,
    "altura_detalhe_e_3_5": 403,
    
    # Grade F Especial (linhas 404-441)
    "grade_f_1": 404,
    "dist_f_1": 405,
    "grade_f_2": 406,
    "dist_f_2": 407,
    "grade_f_3": 408,
    # Detalhes Grade F Especial (linhas 409-423)
    "detalhe_f_1_1": 409,
    "detalhe_f_1_2": 410,
    "detalhe_f_1_3": 411,
    "detalhe_f_1_4": 412,
    "detalhe_f_1_5": 413,
    "detalhe_f_2_1": 414,
    "detalhe_f_2_2": 415,
    "detalhe_f_2_3": 416,
    "detalhe_f_2_4": 417,
    "detalhe_f_2_5": 418,
    "detalhe_f_3_1": 419,
    "detalhe_f_3_2": 420,
    "detalhe_f_3_3": 421,
    "detalhe_f_3_4": 422,
    "detalhe_f_3_5": 423,
    # Alturas Grade F Especial (linhas 424-450)
    "altura_detalhe_f_1_0": 424,
    "altura_detalhe_f_1_1": 425,
    "altura_detalhe_f_1_2": 426,
    "altura_detalhe_f_1_3": 427,
    "altura_detalhe_f_1_4": 428,
    "altura_detalhe_f_1_5": 429,
    "altura_detalhe_f_2_0": 430,
    "altura_detalhe_f_2_1": 431,
    "altura_detalhe_f_2_2": 432,
    "altura_detalhe_f_2_3": 433,
    "altura_detalhe_f_2_4": 434,
    "altura_detalhe_f_2_5": 435,
    "altura_detalhe_f_3_0": 436,
    "altura_detalhe_f_3_1": 437,
    "altura_detalhe_f_3_2": 438,
    "altura_detalhe_f_3_3": 439,
    "altura_detalhe_f_3_4": 440,
    "altura_detalhe_f_3_5": 441,
    
    # Grade G Especial (linhas 442-479)
    "grade_g_1": 442,
    "dist_g_1": 443,
    "grade_g_2": 444,
    "dist_g_2": 445,
    "grade_g_3": 446,
    # Detalhes Grade G Especial (linhas 447-461)
    "detalhe_g_1_1": 447,
    "detalhe_g_1_2": 448,
    "detalhe_g_1_3": 449,
    "detalhe_g_1_4": 450,
    "detalhe_g_1_5": 451,
    "detalhe_g_2_1": 452,
    "detalhe_g_2_2": 453,
    "detalhe_g_2_3": 454,
    "detalhe_g_2_4": 455,
    "detalhe_g_2_5": 456,
    "detalhe_g_3_1": 457,
    "detalhe_g_3_2": 458,
    "detalhe_g_3_3": 459,
    "detalhe_g_3_4": 460,
    "detalhe_g_3_5": 461,
    # Alturas Grade G Especial (linhas 462-488)
    "altura_detalhe_g_1_0": 462,
    "altura_detalhe_g_1_1": 463,
    "altura_detalhe_g_1_2": 464,
    "altura_detalhe_g_1_3": 465,
    "altura_detalhe_g_1_4": 466,
    "altura_detalhe_g_1_5": 467,
    "altura_detalhe_g_2_0": 468,
    "altura_detalhe_g_2_1": 469,
    "altura_detalhe_g_2_2": 470,
    "altura_detalhe_g_2_3": 471,
    "altura_detalhe_g_2_4": 472,
    "altura_detalhe_g_2_5": 473,
    "altura_detalhe_g_3_0": 474,
    "altura_detalhe_g_3_1": 475,
    "altura_detalhe_g_3_2": 476,
    "altura_detalhe_g_3_3": 477,
    "altura_detalhe_g_3_4": 478,
    "altura_detalhe_g_3_5": 479,
    
    # Grade H Especial (linhas 480-517)
    "grade_h_1": 480,
    "dist_h_1": 481,
    "grade_h_2": 482,
    "dist_h_2": 483,
    "grade_h_3": 484,
    # Detalhes Grade H Especial (linhas 485-499)
    "detalhe_h_1_1": 485,
    "detalhe_h_1_2": 486,
    "detalhe_h_1_3": 487,
    "detalhe_h_1_4": 488,
    "detalhe_h_1_5": 489,
    "detalhe_h_2_1": 490,
    "detalhe_h_2_2": 491,
    "detalhe_h_2_3": 492,
    "detalhe_h_2_4": 493,
    "detalhe_h_2_5": 494,
    "detalhe_h_3_1": 495,
    "detalhe_h_3_2": 496,
    "detalhe_h_3_3": 497,
    "detalhe_h_3_4": 498,
    "detalhe_h_3_5": 499,
    # Alturas Grade H Especial (linhas 500-526)
    "altura_detalhe_h_1_0": 500,
    "altura_detalhe_h_1_1": 501,
    "altura_detalhe_h_1_2": 502,
    "altura_detalhe_h_1_3": 503,
    "altura_detalhe_h_1_4": 504,
    "altura_detalhe_h_1_5": 505,
    "altura_detalhe_h_2_0": 506,
    "altura_detalhe_h_2_1": 507,
    "altura_detalhe_h_2_2": 508,
    "altura_detalhe_h_2_3": 509,
    "altura_detalhe_h_2_4": 510,
    "altura_detalhe_h_2_5": 511,
    "altura_detalhe_h_3_0": 512,
    "altura_detalhe_h_3_1": 513,
    "altura_detalhe_h_3_2": 514,
    "altura_detalhe_h_3_3": 515,
    "altura_detalhe_h_3_4": 516,
    "altura_detalhe_h_3_5": 517
}