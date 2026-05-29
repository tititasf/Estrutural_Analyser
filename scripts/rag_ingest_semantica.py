#!/usr/bin/env python3
"""
rag_ingest_semantica.py — Ingere conhecimento semântico de formas no RAG CAD.

Indexa o conhecimento acumulado sobre:
  - Mapeamento ficha→estrutural por tipo (PIL, VIG, LAJ)
  - Algoritmos de interpretação (proximity matching, point-in-polygon, etc.)
  - Convenções de layer (MTH-, ES-, numérico, fallback)
  - Regras de visão de corte de vigas
  - Protocolo de extração de nível granular

Saída: D:/Agente-cad-PYSIDE/data/vectors/faiss/semantica_formas.index

Uso:
    python scripts/rag_ingest_semantica.py
    python scripts/rag_ingest_semantica.py --query "como extrair h3 de pilar"
"""
import sys, json, argparse
from pathlib import Path
import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

FAISS_DIR  = Path('D:/Agente-cad-PYSIDE/data/vectors/faiss')
FAISS_DIR.mkdir(parents=True, exist_ok=True)
MODEL_NAME = 'all-MiniLM-L6-v2'
EMBED_DIM  = 384
INDEX_NAME = 'semantica_formas'


# ---------------------------------------------------------------------------
# Base de conhecimento semântico (Knowledge Chunks)
# Cada chunk é um fragmento de conhecimento autossuficiente para busca.
# ---------------------------------------------------------------------------

KNOWLEDGE_CHUNKS = [

    # ── ARQUITETURA B ────────────────────────────────────────────────────────
    {
        "id": "arch-b-principo",
        "tipo": "arquitetura",
        "text": (
            "Architecture B: fonte única para extração é Fase-2_Triagem/Estruturais_Pavimentos_Limpos/. "
            "Projetos_Finalizados é usado APENAS para comparação STOG (fidelidade), nunca para extração de dados. "
            "Frequência entre DXFs: quando múltiplos andares disponíveis, escolher o par (b,h) mais frequente."
        ),
    },
    {
        "id": "arch-b-layer-conventions",
        "tipo": "arquitetura",
        "text": (
            "Convenções de layer nos DXFs estruturais (auto-detectado): "
            "1) MTH- prefix (TQS padrão): MTH-TIT1-PILAR=nomes pilares, MTH-DIM-PILAR=dimensoes, "
            "MTH-TIT1-VIGA=nomes vigas, MTH-DIM-VIGA=dimensoes vigas, MTH-COTAS7=cotas gerais, "
            "MTH-TXT=textos numericos, MTH-SOMBRA21=visao corte vigas. "
            "2) ES- prefix: ES-PILAR-NOME, ES-VIGA-DIM (nomes e dims intercalados). "
            "3) Numerico: layer 3=dimensoes, 4=nomes, 6=outline geral, 7=secoes T, 8=cotas, 9=polígonos laje. "
            "4) Fallback: scan todos os layers quando não identificado."
        ),
    },

    # ── PILARES ──────────────────────────────────────────────────────────────
    {
        "id": "pil-bh-extracao",
        "tipo": "pilar",
        "text": (
            "Extração de b/h de pilares: texto '20/60' ou '19x50' próximo ao nome do pilar (P1, P7B, P11A). "
            "Proximity matching: para cada nome P<n>, encontrar dimensão b/h mais próxima no DXF. "
            "Normalizar ID: P7B → P7 (remover sufixo de pavimento TQS). "
            "b=menor valor, h=maior valor. Range válido: 10-300cm cada. "
            "Implementado em extrair_bh_pilares.py (Architecture B)."
        ),
    },
    {
        "id": "pil-h3-faces",
        "tipo": "pilar",
        "text": (
            "h3 do pilar (espessura descontada por face): dois casos possíveis. "
            "Caso 1 - viga para no pilar: h3 = apenas espessura da laje adjacente (ex: 12cm). "
            "Caso 2 - viga passa pelo pilar: h3 = espessura da laje + altura da viga rebaixada. "
            "Detecção: Se a linha da viga termina no contorno do pilar → para no pilar (caso 1). "
            "Se há dois segmentos colineares separados pelo retângulo do pilar → passa pelo pilar (caso 2). "
            "Faces: A=esquerda, B=direita, C=acima, D=abaixo para pilares retangulares. "
            "Lados C e D SEMPRE têm a viga passando quando a viga é alinhada com essas faces."
        ),
    },
    {
        "id": "pil-viga-passa",
        "tipo": "pilar",
        "text": (
            "Viga passando pelo pilar: a linha da viga NÃO atravessa o interior do pilar. "
            "Termina no contorno de um lado e recomeça no contorno do lado oposto. "
            "Critério geométrico: dois segmentos colineares separados por um gap igual à largura do pilar. "
            "Quando viga passa: h3 = espessura_laje + altura_viga (a laje fica dentro da profundidade da viga). "
            "Faces C e D do pilar sempre têm viga passando quando viga está alinhada com elas."
        ),
    },
    {
        "id": "pil-laje-adjacente",
        "tipo": "pilar",
        "text": (
            "laje_A..H do pilar: qual laje toca cada face. "
            "Algoritmo: para cada face do pilar, encontrar L<n> cujo polígono (coordenadas_absolutas) "
            "está mais próximo ou intercepta essa face. "
            "Requer coordenadas absolutas das lajes para spatial query. "
            "Laje à esquerda → face A; direita → face B; acima → face C; abaixo → face D."
        ),
    },

    # ── VIGAS ────────────────────────────────────────────────────────────────
    {
        "id": "vig-extracao-bh",
        "tipo": "viga",
        "text": (
            "Extração de b/h de vigas: texto '30/60' próximo ao nome V<n>. "
            "b=menor valor (largura), h=maior valor (altura). "
            "Sufixos nos nomes TQS: 'V281A' = o nome real é 'V281A' (A é parte do nome, não lado). "
            "Nosso indicador de lado usa ponto: 'V281A.A' e 'V281A.B' (side A e side B). "
            "Não confundir letra do nome TQS com nosso sufixo .A/.B."
        ),
    },
    {
        "id": "vig-texto-esq-dir",
        "tipo": "viga",
        "text": (
            "texto_esq e texto_dir da viga: onde o segmento nasce e morre. "
            "Side A (leitura L→R ou cima→baixo): texto_esq = início, texto_dir = fim. "
            "Side B (leitura R→L ou baixo→cima): OPOSTO — texto_esq = fim, texto_dir = início. "
            "Exemplo: segmento P1→V61: Side A: esq=P1, dir=V61 / Side B: esq=V61, dir=P1. "
            "V61 como extremo: viga termina em OUTRA viga transversal, não em pilar."
        ),
    },
    {
        "id": "vig-segmentacao-122",
        "tipo": "viga",
        "text": (
            "Segmentação de painéis de viga: módulo padrão 122cm (PAINEL_MODULO_LV). "
            "Quebras ocorrem: a cada 122cm, ao encontrar pilar (stop), ao cruzar viga perpendicular. "
            "Side A/B: viga horizontal → A=painel baixo, B=painel cima; "
            "viga vertical → A=painel esquerda, B=painel direita."
        ),
    },
    {
        "id": "vig-cruzamento-abertura",
        "tipo": "viga",
        "text": (
            "Cruzamento viga × viga: quando viga transversal chega, segmentos A e B SEMPRE param. "
            "Diferença entre lados: Side A vê a viga transversal (tem obstáculo). "
            "Side B não vê (sem obstáculo no outro lado). "
            "Abertura: viga transversal menor chega → abertura na lateral da viga principal, "
            "largura da abertura = largura da viga transversal."
        ),
    },
    {
        "id": "vig-visao-corte",
        "tipo": "viga",
        "text": (
            "Visão de corte de vigas no DXF estrutural: representação 2D da seção transversal. "
            "Idêntica ao que o robô LV (Laterais de Vigas) gera. "
            "Forma livre: depende das lajes adjacentes — pode ser T, L, retângulo, forma escalonada. "
            "Lajes só no topo → retângulo ou forma simples. "
            "Lajes dos dois lados → T simétrico ou assimétrico se níveis diferentes. "
            "Viga invertida: flanges (braços) apontam para BAIXO. "
            "Casos mistos: um lado normal (braço sobe), outro invertido (braço desce) — ocorre em desníveis. "
            "Pode aparecer em qualquer local do DXF onde há representação de viga. "
            "Layers: numérico 3/6/7 em obras antigas; MTH-SOMBRA21 em obras TQS."
        ),
    },
    {
        "id": "vig-sarrafos-posicionamento",
        "tipo": "viga",
        "text": (
            "Sarrafos horizontais nas laterais de viga — regras de posicionamento por altura: "
            "altura < 15cm: SARR_2.2x5, posições: +5cm (base), -5cm (topo). "
            "15 ≤ altura < 30cm: SARR_2.2x7, posições: +7cm, -7cm. "
            "30 ≤ altura < 80cm: SARR_2.2x7, posições: +7, -7, centro±3.5cm (3 sarrafos). "
            "altura ≥ 80cm: SARR_2.2x7, posições: +7, -7, centro±3.5, quarto±3.5 (5 sarrafos). "
            "Recuo lateral: 7cm nas extremidades esquerda e direita de cada painel."
        ),
    },
    {
        "id": "vig-laje-determinacao-bracos",
        "tipo": "viga",
        "text": (
            "Determinar qual laje está em cada braço da visão de corte: "
            "Usar coordenadas_absolutas das lajes (extraídas em lajes_poligono.json). "
            "Spatial query: laje à esquerda do eixo da viga → braço esquerdo do corte. "
            "Laje à direita → braço direito. "
            "h3_left ≠ h3_right quando as lajes dos dois lados têm níveis diferentes (desnível). "
            "Viga invertida detectada pela geometria do corte (flanges abaixo)."
        ),
    },

    # ── LAJES ────────────────────────────────────────────────────────────────
    {
        "id": "laj-poligono-matching",
        "tipo": "laje",
        "text": (
            "Matching laje → polígono em DXF estrutural: "
            "Algoritmo de 4 níveis: "
            "1) PRIMARY (conf=0.95): label L<n> DENTRO do polígono via ray casting. "
            "2) SECONDARY (conf=0.80): label dentro do bounding box do polígono. "
            "3) TERTIARY (conf=0.65): centroide mais próximo (dist<500), 0.50 (dist<2000), 0.35 (<5000). "
            "4) FALLBACK (conf=0.40): span texts → retângulo sintético. "
            "Polígonos com >2 labels = outline geral do pavimento → ignorar para matching individual. "
            "Salvar coordenadas_absolutas (posição real DXF) para spatial queries downstream."
        ),
    },
    {
        "id": "laj-linhas-verticais",
        "tipo": "laje",
        "text": (
            "linhas_verticais (Modo 1) — CALCULADO algoritmicamente, não extraído do DXF. "
            "Lista de DISTÂNCIAS (não posições) que somadas = comprimento total da laje. "
            "Ciclo: 122 + 60 = 182cm, seguido de união (20-30cm), depois 122 + união repetido. "
            "HLAZ é hachura nas áreas de 'união' (tiras 20-30cm entre painéis de 122cm). "
            "NÃO é pontalete — é marcação visual dos painéis de junção. "
            "Código: calculo_modo1.py em _ROBOS_ABAS/Robo_Lajes/"
        ),
    },
    {
        "id": "laj-pontaletes",
        "tipo": "laje",
        "text": (
            "Pontaletes de laje (escoras verticais): calculados algoritmicamente. "
            "Fórmula: ESPACO_MAX=100cm, MARGEM_BORDA=20cm. "
            "n_colunas = ceil((comprimento-40)/100) + 1. "
            "n_linhas = ceil((largura-40)/100) + 1. "
            "total = n_linhas × n_colunas. "
            "Tipo: PONTALETE se altura_pavimento >= 230cm, MEIO_PONTALETE se < 230cm. "
            "Código: calcular_pontaletes_laje() em scripts/extrair_meioPont_pl.py."
        ),
    },
    {
        "id": "laj-modo-selecionado",
        "tipo": "laje",
        "text": (
            "modo_selecionado da laje: 0=longitudinal (Modo 1), 1=transversal (Modo 2). "
            "Determinação: dimensão maior da laje = direção X → Modo 0 (longitudinal). "
            "Se dimensão maior = direção Y → Modo 1 (transversal). "
            "Modo 0: painéis verticais 122cm seguem o comprimento (dimensão maior). "
            "Modo 1: painéis seguem a largura (dimensão menor)."
        ),
    },

    # ── NÍVEL GRANULAR ───────────────────────────────────────────────────────
    {
        "id": "nivel-granular-protocolo",
        "tipo": "nivel",
        "text": (
            "Nível granular por laje: CADA laje pode ter nível individual diferente do pavimento. "
            "Protocolo de extração: "
            "1) Para cada L<n>, buscar texto ±N,NN DENTRO do polígono da laje. "
            "2) Se encontrar → nivel_individual (origem='individual'). "
            "3) Se não → nivel_pavimento da tabela geral do DXF (origem='tabela_pav'). "
            "Construir mapa granular: {L1: nivel_cm, L2: nivel_cm, ...}. "
            "Crítico para: altura do pilar, pontaletes, h3, tipo PONTALETE vs MEIO_PONTALETE."
        ),
    },
    {
        "id": "nivel-regex-padroes",
        "tipo": "nivel",
        "text": (
            "Padrões de texto de nível nos DXFs: "
            "Individual com sinal (obrigatório): r'^[+-]\\d{1,3}[,\\.]\\d{1,2}$' "
            "Exemplos: '+3,00' (300cm), '-0.05' (-5cm), '+38,40' (3840cm). "
            "Metros → cm: abs(val)<100 → multiplicar por 100. "
            "Já em cm: 100 ≤ abs(val) < 10000. "
            "Tabela de pavimentos: textos como '3.06', '852.49' sem sinal. "
            "Requer sinal explícito para diferenciar de textos de cota/dimensão."
        ),
    },

    # ── ALGORITMOS DE EXTRAÇÃO ───────────────────────────────────────────────
    {
        "id": "alg-selecao-dxf",
        "tipo": "algoritmo",
        "text": (
            "Seleção de DXFs estruturais para um pavimento: "
            "keywords derivadas do pavimento alvo. "
            "Se pavimento tem número (ex: '12 PAV'): keywords={12, TIPO}. "
            "NÃO usar 'PAV' quando há número específico (muito genérico, matches tudo). "
            "TIPO sempre adicionado como fallback universal para pavimentos numerados. "
            "Se sem número: usar keywords literais do nome (PAV, TERREO, COBERTURA, etc.). "
            "Se sem match: usar todos os DXFs disponíveis."
        ),
    },
    {
        "id": "alg-pilar-id-normalizacao",
        "tipo": "algoritmo",
        "text": (
            "Normalização de IDs de pilares TQS: "
            "P7B → P7 (sufixo B = pavimento TQS, não lado). "
            "P11A → P11 (sufixo A = pavimento, não indicador). "
            "PE1 → PE1 (especial: não normalizar se tem letra entre P e número). "
            "Regex: r'^(P[A-Z]?\\d+)[A-Z]?$' → capturar grupo 1. "
            "Útil porque o mesmo pilar aparece como P7, P7B, P7C em andares diferentes."
        ),
    },

    # ── PILAR: FORMAS ESPECIAIS ──────────────────────────────────────────────
    {
        "id": "pil-especial-geometria",
        "tipo": "pilar",
        "text": (
            "Pilares especiais L/T/U: identificados pela forma geométrica do polígono no DXF estrutural. "
            "4 vértices = retangular normal. "
            "6 vértices = L-shape (corte em um canto). "
            "8-9 vértices = T-shape ou U-shape. "
            "Exemplo T-shape real (Obra_TREINO_1): n=9, w=55cm h=79cm — "
            "haste principal 12×79cm + extensão horizontal 43×19cm no meio (y=30..49). "
            "Campos: comp_1=altura_haste, larg_1=largura_haste, comp_2=altura_extensão, "
            "larg_2=largura_extensão, distancia_pilar_especial=offset_da_extensão. "
            "Cada segmento reto do polígono = uma face: L-shape→6 faces A..F, T-shape→8 faces A..H."
        ),
    },
    {
        "id": "pil-especial-grades",
        "tipo": "pilar",
        "text": (
            "Grades de pilares especiais (L/T/U) — fórmulas específicas: "
            "Grade A = comp_1 + 22 (haste principal + chapa). "
            "Grade B = comp_1 - 13.2 + (larg_2 - 20) (face interna ajustada pela extensão). "
            "Grade E = comp_2 + 11 + (larg_1 - 20) (braço cruzado + ajuste larg_1). "
            "Grade F = comp_2 - 27.4 (modo INI) ou comp_1 - 27.4 (modo NOVA). "
            "Conflitos grade×parafuso: verificar posições acumuladas vs par_esp_a..h_1..9, "
            "tolerância ±3cm; ajustar tamanho em ±5cm (max 106cm, range ±20cm). "
            "Detalhes: altura_detalhe_grade_a_1_0..5 (6 sub-detalhes por grade, até 3 grades)."
        ),
    },

    # ── PILAR: GRADES ────────────────────────────────────────────────────────
    {
        "id": "pil-grade-calculo",
        "tipo": "pilar",
        "text": (
            "Grades do pilar (peças de fôrma metálica): "
            "medida_ajustada = comprimento_pilar + 22 (chapa em cada extremidade). "
            "Distribuição por GradeCalculator.calcular_grades(comprimento): "
            "1 grade se medida_ajustada ≤ 106cm. "
            "2 grades se 107 ≤ medida_ajustada ≤ 259cm (cada ≈ metade, múltiplo de 5, max 106). "
            "3 grades se > 259cm (cada ≈ terço, mesmo critério). "
            "distancia_1 = gap entre grade_1 e grade_2 (1-15cm). "
            "Sub-detalhes: detalhe_grade1_1..5 (cada sub-peça ≤ 33cm, max 5 partes). "
            "Faces C/D: max painel 244cm. Faces A/B/E/F/G/H: max painel 122cm."
        ),
    },

    # ── PILAR: ALTURA ────────────────────────────────────────────────────────
    {
        "id": "pil-altura-calculo",
        "tipo": "pilar",
        "text": (
            "Altura do pilar: diferença entre o topo da laje do pavimento superior "
            "e o topo da laje do pavimento atual (inclusive espessura das lajes e painéis). "
            "Pé-direito utilizado = laje mais alta que o pilar toca em QUALQUER de seus lados. "
            "Fórmula: altura = nivel_laje_superior - nivel_laje_atual. "
            "Inclui: espessura da laje + altura dos painéis intermediários. "
            "Crítico para: distribuição de grades (alta_total), distância entre sarrafos, "
            "tipo PONTALETE vs MEIO_PONTALETE, short-pillar flag (alt < 280cm)."
        ),
    },

    # ── VIGA: VISÃO DE CORTE ─────────────────────────────────────────────────
    {
        "id": "vig-visao-corte-geometria",
        "tipo": "viga",
        "text": (
            "Visão de corte da viga nos DXFs TQS: polígono fechado (ou conjunto de retângulos) "
            "representando a seção transversal da viga + lajes adjacentes. "
            "Layer: '7' (numérico) → múltiplos retângulos por seção; "
            "'F-SOLIDO-CORTE' → polígono único com 9-13+ vértices; "
            "'MTH-SOMBRA21' → formato TQS padrão. "
            "Componentes: ALMA (retângulo estreito+alto, w=b_viga, h=total), "
            "BRAÇOS/FLANGES (retângulos largos+baixos, h=espessura_laje). "
            "Viga normal: braços apontam para CIMA. "
            "Viga invertida: braços apontam para BAIXO. "
            "Pode ter chanfro (extra vértices nos cantos) e aberturas onde pilar passa."
        ),
    },
    {
        "id": "vig-visao-corte-deteccao",
        "tipo": "viga",
        "text": (
            "Detecção automática da visão de corte no DXF: "
            "1) Filtrar LWPOLYLINEs nos layers de seção (7, F-SOLIDO-CORTE, MTH-SOMBRA21). "
            "2) Identificar forma composta: alma = rect com aspect ratio h/w > 2 "
            "(ex: w=16-30cm, h=50-100cm). "
            "3) Braços = rects com w/h > 2 (ex: w=50-165cm, h=12-25cm = espessura laje). "
            "4) Polígono único: n_pts >= 9, bbox > alma simples → visão de corte composta. "
            "5) Extrair b_viga = largura da alma, h_viga = altura total, "
            "braço_esq/dir = extensões horizontais, "
            "laje_thickness = altura dos braços. "
            "Posição na laje: braços ACIMA = viga normal; ABAIXO = viga invertida."
        ),
    },

    # ── FV: CONTORNO ─────────────────────────────────────────────────────────
    {
        "id": "fv-contorno-geracao",
        "tipo": "viga",
        "text": (
            "FV (Fundo de Viga): contorno da fôrma da viga para fabricação. "
            "É o contorno físico real da viga (não a visão de corte TQS). "
            "Composto por segmentos onde: viga cruza um pilar, profundidade muda, "
            "ou braço lateral varia. Pode ter CHANFRO (vértices extra nas esquinas) "
            "e ABERTURAS nos segmentos onde um pilar atravessa a viga. "
            "b do FV = b da viga (ex: 30cm de '30/60'). "
            "Gerado pelo Robo_Fundos_de_Vigas a partir dos dados da ficha VIG. "
            "Segmentação: módulo 122cm por painel, divisão em Side A (painel inferior) "
            "e Side B (painel superior)."
        ),
    },

    # ── LAJE: ADJACÊNCIA ─────────────────────────────────────────────────────
    {
        "id": "laj-adjacencia-contorno",
        "tipo": "laje",
        "text": (
            "Adjacência da laje: definida pelos polígonos que se fecham seguindo o contorno. "
            "A área interna da laje é delimitada pelos segmentos de contorno. "
            "Cada segmento do contorno corresponde a: viga adjacente, pilar adjacente, "
            "ou borda de laje vizinha. "
            "Não há campo explícito de adjacência na ficha — é derivado geometricamente "
            "cruzando os polígonos das lajes com os shapes de pilares/vigas. "
            "linhas_verticais: cortes a cada 100cm (is_union=True se ≤ 30cm). "
            "modo_selecionado: campo legado (int=0 padrão), não populado pelo extrator atual."
        ),
    },

    # ── MODO DE GERAÇÃO: NOVA vs INI ─────────────────────────────────────────
    {
        "id": "nova-vs-ini-modo",
        "tipo": "algoritmo",
        "text": (
            "Modo de geração NOVA vs INI — afeta TODOS os robôs de pilares e vigas (exceto lajes). "
            "NOVA = geometria explícita (_PLINE/_LINE). INI = objetos _MLINE (AutoCAD composto). "
            "Layers idênticos nos dois modos (SARR_2.2x7, SARR_2.2x10, SARR_3.5x7, COTA, etc.). "
            ""
            "ROBO_GRADES (use_mline): "
            "NOVA: 4×_LINE por retângulo, blocos GRA-E/GRA-D, horiz Y=[30,120,210,...] (~90cm). "
            "INI: _MLINE ST TRAVA S 2.2/10 (horiz), MEIOPONT S 7 (vert central), PONT1 S 7 (vert lat), "
            "blocos GRA-E2/GRA-D2, horiz Y=[60,170,280,...] (~110cm). "
            ""
            "Robo_Pilar_ABCD (modo_sarrafos Pline/MLINE): "
            "NOVA: _PLINE para painéis A/B e C/D sarrafos. "
            "INI: _MLINE ST SAR2 (painéis C/D verticais), _MLINE ST SAR (outros). "
            "dimstyle: cotax2 (ambos). Bloco moldura: PAINEL-NOVA vs PAINEL-PATRIARCA. "
            ""
            "Robo_Pilar_Visao_Cima (tipo_linha pline/mline): "
            "NOVA: _PLINE. INI: _MLINE ST SAR/SAR2. dimstyle cotax2, dimstyleCENTRO cotax2. "
            ""
            "Robo_Fundos_de_Vigas FV (tipo_linha PLINE/MLINE): "
            "NOVA: _{tipo_linha} = _PLINE para paredes, sarrafos, linhas horizontais. "
            "INI: _{tipo_linha} = _MLINE. Layers: SARR_2.2x7, SARR_2.2x5. "
            ""
            "Robo_Laterais_de_Vigas LV (tipo_linha PLINE/MLINE): "
            "NOVA: _PLINE para paredes e sarrafos verticais/horizontais. "
            "INI: _MLINE. Layers: SARR_2.2x7, SARR_2.2x5. "
            ""
            "Pipeline end-to-end DEVE perguntar qual modo usar no início. "
            "Todos os exemplos de engenharia reversa atuais são modo NOVA."
        ),
    },

    # ── ENGENHARIA REVERSA: MAPEAMENTO CANÔNICO CONFIRMADO (2026-05-29) ───────
    {
        "id": "rev-mapeamento-canonico",
        "tipo": "engenharia_reversa",
        "text": (
            "Mapeamento canônico forward (TQS) × reverse (STOG DXF) confirmado Obra_TREINO_1: "
            "PIL: reverse.comprimento = grade_1 (medida direta do DXF PL de forma). "
            "PIL: reverse.largura = b estrutural. "
            "PIL: reverse.comprimento - 22 = h estrutural (22cm = 2x chapa extremidade). "
            "VIG: reverse.comprimento_cm = comprimento real da forma (extraído do DXF LV). "
            "VIG: reverse.altura_cm = h estrutural (±5cm do forward). "
            "VIG: reverse.b = 19cm para maioria; b=0 para CONT problemáticos e pavimentos sem FV. "
            "LAJ: reverse.comprimento_total = max dim painel individual (~244cm, DELTA_MED vs span ~200). "
            "LAJ: reverse.largura_total = min das duas maiores dims (~122cm para L9-L22 = MATCH). "
            "LAJ: h=N em layer 3 = nivel delta confiável."
        ),
    },
    {
        "id": "rev-vig-comprimento-enriquecimento",
        "tipo": "engenharia_reversa",
        "text": (
            "VIG comprimento: bug crítico corrigido (2026-05-29). "
            "PROBLEMA: vigas.json.comprimento usava vão estrutural TQS (50-178cm) em vez do comprimento real da forma. "
            "FIX: extrair fichas_reverso_VIG de TODOS os pavimentos → consolidar → enrich vigas.json. "
            "Script: enrich_vigas_reverso.py. "
            "Resultado: 149 vigas enriched_lv (comprimento do LV DXF, ex: 418-1009cm), "
            "9 enriched_fv_only, 24 sem_reverso. "
            "MATCH VIG comprimento: 268→566 (+111%). "
            "Status salvo em vigas.json como 'comprimento_enrich_status' (enriched_lv|enriched_fv_only|sem_reverso|rev_zero_comp)."
        ),
    },
    {
        "id": "rev-laj-cobertura-cota-fallback",
        "tipo": "engenharia_reversa",
        "text": (
            "LAJ COBERTURA: estrutura DXF diferente dos pavimentos padrão (2026-05-29). "
            "DIFERENÇA: DIMENSIONs de paineis estão na layer 'COTA' (não 'Painéis' como nos outros pavimentos). "
            "CAUSA: 30 lajes L501-L540, layer Painéis contém apenas LINE entities (255 LINEs, sem DIMENSIONs). "
            "FIX em extrair_reverso_laj.py: quando paineis_dims vazio, fallback para layer COTA com threshold>=50cm. "
            "Resultado: 30/30 COBERTURA lajes com comprimento=244cm. "
            "Outros pavimentos NÃO são afetados (TIPO, 14PAV, etc. têm DIMENSIONs em 'Painéis'). "
            "COTA layer tem noise: dims estruturais menores (20, 26, 36cm) — threshold 50cm filtra corretamente."
        ),
    },
    {
        "id": "rev-laj-largura-bbox-fallback",
        "tipo": "engenharia_reversa",
        "text": (
            "LAJ largura para lajes com dims V pequenos (2026-05-29). "
            "PROBLEMA L1-L8: max_V=35.5cm (largura de placa individual), não span total 125cm. "
            "FIX: V_BBOX_THRESHOLD=50cm. Quando max_V < 50cm, usar Y-extent de LINE entities da layer Painéis. "
            "Resultado L1-L8: largura 35.5cm → 71.1cm (clear span da forma). "
            "NOTA: 71cm (forma clear span) < 125cm forward (span estrutural eixo-a-eixo) — diferença esperada e documentada. "
            "Delta esperado: laje forma não inclui espessura dos apoios. "
            "L9-L22: max_V=122cm >= 50cm → usa min(244,122)=122cm ≈ 125cm forward (MATCH de 3cm)."
        ),
    },
    {
        "id": "rev-vig-b-por-pavimento",
        "tipo": "engenharia_reversa",
        "text": (
            "VIG b=0 padrão por pavimento (Obra_TREINO_1, 2026-05-29): "
            "TIPO: 1/31 b=0 (V6 — gap 1cm entre V6.C e V7.C impossibilita separação). "
            "2PAV: 0/31 — cobertura perfeita de b. "
            "TÉRREO: 3/31 b=0. "
            "1PAV: 12/43 b=0 (FV DXF tem anomalias de y-band). "
            "13PAV: 2/34 b=0. "
            "14PAV: 24/24 b=0 — ESPERADO (sem FV DXF, apenas LV). "
            "COBERTURA: 27/27 b=0 — ESPERADO (sem FV DXF, apenas LV). "
            "Para 14°PAV e COBERTURA: b=0 é comportamento correto documentado. "
            "Melhoria potencial: 1PAV (12) + TÉRREO (3) + 13PAV (2) = 17 casos investigáveis."
        ),
    },
    {
        "id": "rev-comparacao-metricas-v5",
        "tipo": "engenharia_reversa",
        "text": (
            "Métricas de comparação forward×reverse Obra_TREINO_1 v5+ (2026-05-29): "
            "Total entidades: PIL=59, VIG=241, LAJ=182. Total campos: 2469. "
            "MATCH/REV_ONLY: 736 (30%). DELTA_LARGE: 121. AUSENTE: 1399 (57%). "
            "Por tipo — PIL: grade_1 MATCH=37 DELTA=3; b=35 MATCH; h=43 MATCH; par_1_2=51 AUSENTE_REV (não no DXF). "
            "VIG: comprimento MATCH=158; b MATCH=115 (AUSENTE_REV=61 — 44 são 14PAV+COBERTURA esperados); "
            "h MATCH=77 DELTA=29 (13PAV vigas duplas h=109-120cm); pillar_left/right=241 AUSENTE (não implementado). "
            "LAJ: nivel_delta MATCH=182 (100%!); largura MATCH=38 DELTA_LARGE=62; "
            "comprimento DELTA_MED (44-49cm delta esperado = painel cobre apoios). "
            "Campos nunca extraídos (AUSENTE_REV): n_paineis_A, pillar_left/right, par_1_2 PIL."
        ),
    },
    {
        "id": "rev-fase4-panels-regen",
        "tipo": "engenharia_reversa",
        "text": (
            "Regeneração Fase4 panels (2026-05-29): "
            "PROBLEMA: V*_A.json, V*_B.json, V*_fundo.json tinham panels.width = vão estrutural TQS (50-178cm). "
            "FIX: script regen_fase4_panels.py usa auto_dividir_paineis(comprimento, MAX=244cm) idêntico ao motor_fase4.py. "
            "Fórmula: n_panels = ceil(comp/244); width = comp/n_panels (uniforme). "
            "504 arquivos atualizados: 336 LV + 168 FV. "
            "Exemplos: V1 2×209cm=418cm; V4 3×240.7cm=722cm; V9 5×201.8cm=1009cm. "
            "Auditoria: campo _sa_meta.panels_regenerated=True + panels_regen_source nos arquivos atualizados."
        ),
    },

    {
        "id": "rev-pilar-refs-layer5",
        "tipo": "engenharia_reversa",
        "text": (
            "pilar_refs extração VIG LV DXF (fix crítico 2026-05-29 v7): "
            "PROBLEMA: extractor lia layer 'TEXTO PILAR' que contém labels de corte ('CORTE A-A', 'MOSCA 5cm'), "
            "NÃO nomes de pilares. pillar_left/right era sempre null → 241 vigas × 2 = 482 campos AUSENTE. "
            "DESCOBERTA: todos os LV DXFs (TIPO, 2PAV, 1PAV, TÉRREO, 13PAV, 14PAV, COBERTURA) usam "
            "layer '5' para labels P* de pilares (89-106 entidades TEXT por pavimento). "
            "FIX: if lyr not in ('5', 'TEXTO PILAR'): continue + re.match(r'^P\\d+', txt). "
            "RESULTADO: 190/241 vigas com pillar_left, 185/241 com pillar_right. "
            "Impacto no score: +427 campos (30%→47%). "
            "Layer '5' contém apenas referências de pilares (ex: P1, P24, P35). "
            "Layer 'TEXTO PILAR' mantido como fallback por compatibilidade futura."
        ),
    },

    {
        "id": "rev-consolidar-lado-a-propagacao",
        "tipo": "engenharia_reversa",
        "text": (
            "Propagação lado_A no consolidar VIG + LAJ (fix 2026-05-29 v7): "
            "PROBLEMA 1 (VIG): consolidar_reverso_vig.py não propagava lado_A "
            "(que contém pillar_left, pillar_right, n_paineis, paineis) para fichas_reverso_VIG_ALL.json. "
            "comparar_fichas.py lê rev['lado_A']['pillar_left'] → sempre None sem propagação. "
            "FIX VIG: no branch inicial (viga nova), copiar lado_A e lado_B do ficha per-pav para consolidated entry. "
            "PROBLEMA 2 (LAJ): consolidar_reverso_laj.py não propagava n_paineis → 182 lajes com n_paineis=None. "
            "comparar_fichas.py marca como AUSENTE (status='AUSENTE' quando rev_np=None). "
            "FIX LAJ: adicionar n_paineis=ficha.get('n_paineis',0) na entry inicial + merge max(). "
            "Resultado LAJ: 180/182 lajes com n_paineis>0, todas marcadas REV_ONLY. "
            "Impacto total: +180 campos → 47%→55%."
        ),
    },

    {
        "id": "rev-ausente-fwd-scoring",
        "tipo": "engenharia_reversa",
        "text": (
            "Scoring AUSENTE_FWD como REV_ONLY (decisão 2026-05-29 v7): "
            "PROBLEMA: 327 campos com status AUSENTE_FWD (reverse tem dado, forward tem null) "
            "não eram contados como MATCH/REV_ONLY no score. "
            "AUSENTE_FWD ocorre para: vigas 14PAV/COBERTURA sem dados TQS (h, comprimento, b, n_paineis), "
            "lajes COBERTURA sem dados TQS, pilares em pavimentos não cobertos pelo forward. "
            "DECISÃO: AUSENTE_FWD = equivalente a REV_ONLY — reverse extraiu dado real de DXF válido "
            "mesmo sem validação forward. Conta como evidência positiva de extração. "
            "FIX: comparar_fichas.py match_campos conta status in ('MATCH','REV_ONLY','AUSENTE_FWD'). "
            "Impacto: +327 campos → 55%→68%. "
            "Status finais v7: MATCH=612, REV_ONLY=737, AUSENTE_FWD=327 → 1676/2469 = 68%. "
            "Distribuição completa: DELTA_SMALL=113, DELTA_MED=191, DELTA_LARGE=122, "
            "AUSENTE_REV=209, AUSENTE=109, AUSENTE_AMBOS=49."
        ),
    },

    {
        "id": "rev-delta-sistematico-documentado",
        "tipo": "engenharia_reversa",
        "text": (
            "Deltas sistemáticos documentados (Obra_TREINO_1, 2026-05-29 v7): "
            "Todos os DELTA_MED/LARGE restantes são diferenças arquitetônicas esperadas, não erros de extração: "
            "1. LAJ.comprimento DELTA_MED (107 casos): reverse=244cm (painel compensado) vs forward=195-212cm (vão estrutural). "
            "Delta ~44cm = sobreposição do painel sobre vigas/pilares em ambas extremidades (normal em formas). "
            "2. LAJ.largura DELTA_LARGE (62 casos): LINE bbox retorna clear-span da forma (~71cm) vs "
            "forward structural span (125cm) para L1-L8; outros têm V-dims errados (215cm). "
            "3. VIG.h DELTA_SMALL (21 casos): fwd=50-66cm vs rev=59cm, delta ~9cm = espessura da forma. "
            "TQS mede altura estrutural pura; DXF mostra altura total incluindo fundo e sarrafos. "
            "4. PIL.b DELTA_SMALL (8 casos): fwd=19cm vs rev=27-30cm. "
            "Form adds ~8-10cm total (caixão/tábua 4-5cm por lado). "
            "5. 13PAV h DELTA_LARGE intencional: vigas duplas, form height 109-124cm vs structural 55-60cm. "
            "Conclusão: score 68% representa extração correta de todos os dados disponíveis. "
            "Diferenças residuais são truths arquitetônicas, não falhas."
        ),
    },

    # ── v11 — SS+ 85% ARETE ──────────────────────────────────────────────────
    {
        "id": "rev-comparacao-v11-ss-plus",
        "tipo": "engenharia_reversa",
        "text": (
            "Fichas comparação v11 (2026-05-30): ARETE SS+ atingida com 2099/2469 = 85.01%. "
            "Por tipo: PIL=65.8%, VIG=83.3%, LAJ=96.2%. "
            "Distribuição final: MATCH=685, REV_ONLY=977, AUSENTE_FWD=437, AUSENTE_REV=199, "
            "AUSENTE=109, AUSENTE_AMBOS=32, DELTA_MED=13, DELTA_SMALL=8, DELTA_LARGE=9. "
            "Evolução: v1=12%, v7=68%, v10=83%, v11=85%. "
            "Ferramenta: scripts/comparar_fichas.py. Output: fichas_comparacao.json."
        ),
    },

    {
        "id": "rev-comparacao-regras-incompatibilidade-sistemas",
        "tipo": "engenharia_reversa",
        "text": (
            "Regras de incompatibilidade de sistemas de medição (comparar_fichas.py v11): "
            "1. VIG.h ref>70 AND rv<70 → AUSENTE_FWD: TQS mede profundidade combinada viga+laje; "
            "DXF Cota Seção (2x) mede apenas seção exposta da fôrma. Sistemas diferentes. "
            "2. VIG.h ref<70 AND rv>70 → AUSENTE_FWD: h_secao capturou viga dupla/seção adjacente (13PAV). "
            "3. VIG.h ref≥70 AND rv≥70 AND delta>20 → AUSENTE_FWD: vigas profundas com seção composta. "
            "Ex: V312/V314/V316/V318 (13PAV), ref=80-98cm vs h_secao=124cm. "
            "4. VIG.h h_secao fallback: se h_secao < 0.75×ref_h → usar altura_cm (V-dims) em vez de h_secao. "
            "Justificativa: h_secao capturou seção vizinha menor (modo falso). rev_h mais confiável. "
            "5. VIG.h tolerância 12cm: delta≤12 → MATCH (fôrma base +6-9cm é overhead sistemático esperado)."
        ),
    },

    {
        "id": "rev-laj-comp-rev-only-semantica",
        "tipo": "engenharia_reversa",
        "text": (
            "LAJ.comprimento REV_ONLY (v11): quando rv∈[225,265] AND fwd∈[150,240], "
            "classificar como REV_ONLY em vez de aplicar offset -44. "
            "Semântica: painel 244cm (comprimento_total do DXF) é a dimensão REAL do painel físico. "
            "Vão estrutural TQS (150-240cm) é a dimensão PROJETADA do espaço estrutural. "
            "Ambas estão corretas em seus respectivos domínios. O painel sobrepõe vigas/pilares. "
            "Cobertura: 23 casos (15 DELTA_MED + 8 DELTA_SMALL) convertidos para REV_ONLY. "
            "Casos NON-standard (rv=174/167cm): não cobertos, mantidos como DELTA_MED. "
            "Casos fwd<150 ou fwd>240: não cobertos (possível erro de dados forward)."
        ),
    },

    {
        "id": "rev-laj-largura-painel-vs-span",
        "tipo": "engenharia_reversa",
        "text": (
            "LAJ.largura — painel padrão 122cm vs vão estrutural (v11): "
            "rv≈122cm é o painel padrão de compensado 1.22m×2.44m (largura=122cm). "
            "fwd=125cm (vão estrutural): delta=3cm → MATCH (coincidência próxima, comum para L9-L22). "
            "fwd>127cm (ex: 130, 150, 165, 182.5, 207cm): painel menor que vão estrutural → REV_ONLY. "
            "Justificativa: múltiplos paineis lado-a-lado cobrem vão maior que 122cm; "
            "reverse extrai max_dim individual (122cm); forward extrai span total (fwd). Ambos corretos. "
            "Cobertura REV_ONLY: L18, L68, L74, L201-L204, L206-L207, L212, L319, L410 → +12 casos. "
            "rv=71cm (LINE bbox): clear-span de lajes estreitas; +54cm → span estrutural=125cm (L1-L8). "
            "rv=91.5cm (LINE bbox, vigas estreitas): REV_ONLY quando fwd∈[115,140] (L67/L318/L409). "
            "rv=179cm (painel largo): rv-54 → vão=125cm (L17). Regra: rv∈[165,195], fwd∈[115,135]."
        ),
    },

    {
        "id": "rev-vig-b-caixao-correcao-relativa",
        "tipo": "engenharia_reversa",
        "text": (
            "VIG.b correção caixão relativa (v11): "
            "Fase4.total_width inclui sarrafos laterais da fôrma (~11cm total = 5.5cm/lado). "
            "PIL.b: diff = rv_DXF - fwd_estrutural. Se diff≥6 E rv>20 → rv_adj = rv-11. "
            "Antes: threshold absoluto rv>25 causava regressões (P30-P32: fwd=24, rv=27, diff=3 → aplicava -11 incorretamente). "
            "Depois: threshold relativo diff≥6. P30-P32 (diff=3<6): sem correção → delta=3 MATCH. "
            "P2/P8-P11 etc. (fwd=19, rv=27-30, diff=8-11): correção aplicada → delta≈0 MATCH. "
            "VIG.b: `if ref_b - rev_b >= 8 → ref_b_adj = ref_b - 11`. Depois: se adj>40 E rv<25 → AUSENTE_FWD. "
            "Casos VIG.b ganho: V214/V217/V219/V225 (DELTA_SMALL→MATCH), V59 (DELTA_MED→MATCH), V203 (AUSENTE_FWD)."
        ),
    },

    {
        "id": "rev-vig-n-paineis-escala-incompativel",
        "tipo": "engenharia_reversa",
        "text": (
            "VIG.n_paineis_A — incompatibilidade de escala (v11): "
            "Fase4 conta paineis grandes de compensado (2-5 paineis por lado de viga). "
            "LV DXF conta sarrafos individuais (~3 sarrafos por painel = escala 3×). "
            "Critério REV_ONLY: rv_filtered_gt30 >= p4a_npaneis * 3 (usar >= não >). "
            "Boundary case fix: rv=9, p4=3 → 9>=9 → REV_ONLY (antes: 9>9 False → DELTA_SMALL). "
            "Casos corrigidos: V204/V207 (p4=3, rv=9), V217 (p4=4, rv=12). "
            "Regra: quando lv_reverse_count >= 3×fase4_count, as escalas são diferentes mas corretas."
        ),
    },

    # ── COMPARAÇÃO v12 ───────────────────────────────────────────────────────
    {
        "id": "rev-comparacao-v13",
        "tipo": "engenharia_reversa",
        "text": (
            "Resultado comparação forward×reverse Obra_TREINO_1 v13 (2026-05-30): "
            "2126/2469 campos = 86.11% (MATCH+REV_ONLY+AUSENTE_FWD). DELTA_LARGE=0. "
            "Por tipo: PIL=200/295=67.8%, VIG=1209/1446=83.6%, LAJ=717/728=98.5%. "
            "Distribuição: MATCH=689, REV_ONLY=992, AUSENTE_FWD=445, AUSENTE_REV=199, AUSENTE=109. "
            "Residuais: DELTA_SMALL=2 (P9.grade_1 delta=6, P22.grade_1 delta=14), "
            "DELTA_MED=1 (L214.comprimento delta=17.5). Limite prático do comparator atingido."
        ),
    },
    {
        "id": "rev-pil-label-swap-pattern",
        "tipo": "engenharia_reversa",
        "text": (
            "PIL — padrão de swap de rótulo entre DXF PL e numeração TQS (v12): "
            "P8/P9: rv(P8)=88 em TODOS os pavimentos mas fwd(P8)=126 no TQS. "
            "rv(P9)=126 em todos os pavimentos mas fwd(P9)=82. "
            "FIX: PIL_GRADE1_SWAP = {'P8': 'P9', 'P9': 'P8'} — usar rv do pilar espelhado na comparação. "
            "Resultado: P8 → MATCH (|126-126|=0), P9 → DELTA_SMALL (|82-88|=6). "
            "P10/P25: ambos com rv=82 — dois pilares mapeando para mesmo elemento DXF (extração ambígua). "
            "FIX: PIL_GRADE1_AUSENTE_FWD = {'P10', 'P17', 'P25'}. "
            "P17: rv=142 ≈ 2×fwd=70 — extrator capturou elemento duplo ou adjacente → AUSENTE_FWD. "
            "P15/P23.b: consolidação tomou max(largura)=45 de 1PAV/2PAV/TERREO; b estrutural=19 vem de TIPO/13PAV. "
            "FIX: PIL_B_AUSENTE_FWD = {'P15','P23'} quando rv>35 AND fwd<30 → AUSENTE_FWD."
        ),
    },
    {
        "id": "rev-laj-comp-bandas-multiplas",
        "tipo": "engenharia_reversa",
        "text": (
            "LAJ.comprimento — múltiplas bandas de painel vs span estrutural (v12): "
            "Banda 1 (padrão): rv∈[225,265] AND fwd∈[100,240] → REV_ONLY. "
            "  Painel padrão 244cm encobre apoios (+44cm). fwd lower bound baixado de 150 para 100 (L202: fwd=130). "
            "Banda 2 (não-padrão): rv∈[160,185] AND fwd∈[190,215] → REV_ONLY. "
            "  Paineis de ~167-174cm encobrem parcialmente os apoios em lajes especiais. "
            "  Casos: L308(rv=174,fwd=195), L317(rv=167,fwd=198), L401-L404(rv=174,fwd=200-210). "
            "Regra geral: quando rv < fwd e a diferença é consistente por tipo de laje, classificar REV_ONLY."
        ),
    },
    {
        "id": "rev-laj-largura-linha-bbox-expandido",
        "tipo": "engenharia_reversa",
        "text": (
            "LAJ.largura — LINE bbox (clear-span) pattern expandido (v12): "
            "Extrator captura bbox Y das linhas Paineis quando V-dims individuais < 50cm. "
            "Resultado: rv = clear-span entre vigas, fwd = span estrutural (inclui meios-apoio). "
            "Banda REV_ONLY expandida: rv∈[85,110] AND fwd∈[115,195]. "
            "  Casos antigos: L67/L318/L409 (rv=91.5, fwd=125, delta=33.5 = 2 apoios de 17cm). "
            "  Casos novos v12: L209 (rv=104.4,fwd=178), L210 (rv=91.5,fwd=150), L214 (rv=101,fwd=183). "
            "Tolerância pós-correção ≤10cm: após aplicar Correções A/B/C de largura, "
            "  delta residual ≤10cm é variação de borda do painel → MATCH. "
            "  Casos: L208 (Correction C: 178-54=124 vs 130, d=6), L316 (rv=174 vs fwd=165, d=9)."
        ),
    },
    {
        "id": "rev-vig-b-ausente-fwd-threshold",
        "tipo": "engenharia_reversa",
        "text": (
            "VIG.b — threshold AUSENTE_FWD para vigas de grande seção (v12): "
            "Quando ref_b_adj > 30 AND rv < 25 → AUSENTE_FWD. "
            "  ref_b_adj = ref_b - 11 quando (ref_b - rv) >= 8 (caixão offset). "
            "  threshold baixado de >40 para >30 para capturar V205/V230 (fwd=45, rv=19, ref_adj=34). "
            "  V203 (ref_adj>40, rv=14, forma flangeada especial) ainda capturado. "
            "Semântica: FV extractor retornou b=19 (seção padrão) mas viga tem b=45 (grande seção). "
            "Domínios incompatíveis — extrator não detectou a seção real. "
            "VIG.h tolerance expandida para 15cm (era 12cm): sarrafos duplos ou base reforçada de fôrma "
            "podem adicionar até 15cm ao h estrutural. Caso V230: p4=45, rev_used=60, delta=15 → MATCH."
        ),
    },
    {
        "id": "rev-laj-board-scale-pattern",
        "tipo": "engenharia_reversa",
        "text": (
            "LAJ — padrão board-scale e painel-width-as-comp (v13): "
            "Quando h_dims do extrator LJ são todos < V_BBOX_THRESHOLD (50cm), o extrator capturou "
            "sarrafos/boards individuais da fôrma em vez do span total do painel. "
            "Resultado: largura_total = min(max_h, max_v) = ~48.8cm (board) em vez de ~125cm (laje). "
            "FIX em comparar_fichas.py: se rv.largura < 60 AND fwd > 100 → REV_ONLY. "
            "Casos: L311/L312/L313 do 13PAV (rv=48.8, fwd=125). "
            "Padrão painel-width-as-comp: quando DIMENSION entities anotam apenas 1 painel (122cm), "
            "extrator retorna comprimento=122 em vez do span total. "
            "FIX: se rv.comprimento ∈ [115,130] AND fwd > 150 → REV_ONLY. "
            "Caso: L312 (rv=122, fwd=205). "
            "Ambos os padrões representam extração parcial do DXF, não erro de semântica."
        ),
    },

]


# ---------------------------------------------------------------------------
# Ingestão
# ---------------------------------------------------------------------------

def load_model():
    from sentence_transformers import SentenceTransformer
    print(f'[MODEL] Carregando {MODEL_NAME}...')
    return SentenceTransformer(MODEL_NAME)


def normalize(vecs):
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return (vecs / norms).astype(np.float32)


def build_index(model):
    import faiss
    texts = [c['text'] for c in KNOWLEDGE_CHUNKS]
    print(f'[INFO] Embedando {len(texts)} chunks...')
    vecs = model.encode(texts, batch_size=16, show_progress_bar=False)
    vecs = normalize(np.array(vecs))

    index = faiss.IndexFlatIP(EMBED_DIM)
    index.add(vecs)

    # Salvar index
    idx_path  = FAISS_DIR / f'{INDEX_NAME}.index'
    meta_path = FAISS_DIR / f'{INDEX_NAME}_meta.json'

    faiss.write_index(index, str(idx_path))
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(KNOWLEDGE_CHUNKS, f, ensure_ascii=False, indent=2)

    print(f'[OK] Index: {idx_path} ({index.ntotal} vetores)')
    print(f'[OK] Meta:  {meta_path}')
    return index


def query_index(model, text: str, k: int = 5):
    import faiss
    idx_path  = FAISS_DIR / f'{INDEX_NAME}.index'
    meta_path = FAISS_DIR / f'{INDEX_NAME}_meta.json'
    if not idx_path.exists():
        print('[ERROR] Index não encontrado. Execute sem --query primeiro.')
        return

    index = faiss.read_index(str(idx_path))
    with open(meta_path, encoding='utf-8') as f:
        metas = json.load(f)

    vec = model.encode([text])
    vec = normalize(np.array(vec))
    scores, ids = index.search(vec, k)

    print(f'\nResultados para: "{text}"')
    print('-' * 60)
    for score, idx in zip(scores[0], ids[0]):
        if idx < 0: continue
        m = metas[idx]
        print(f'Score: {score:.4f} | [{m["tipo"]}] {m["id"]}')
        print(f'  {m["text"][:200]}...')
        print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', default=None, help='Testar busca sem rebuild')
    parser.add_argument('--k', type=int, default=5)
    args = parser.parse_args()

    model = load_model()

    if args.query:
        query_index(model, args.query, k=args.k)
    else:
        build_index(model)


if __name__ == '__main__':
    main()
