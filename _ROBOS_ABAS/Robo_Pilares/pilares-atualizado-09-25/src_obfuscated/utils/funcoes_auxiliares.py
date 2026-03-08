
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

# Função para processar pares de linhas e calcular aberturas
def calcular_aberturas_em_pares(linhas, is_vertical, is_esquerda, min_coord, max_coord):
    """
    Classifica linhas em grupos (esquerda/direita) e calcula distâncias das aberturas.
    
    Args:
        linhas: Lista de linhas para classificar
        is_vertical: True se o retângulo está na vertical, False para horizontal
        is_esquerda: True para lado esquerdo/superior, False para direito/inferior
        min_coord, max_coord: Coordenadas mínimas e máximas do retângulo
    
    Returns:
        Lista de aberturas no formato [(distancia, largura), ...]
    """
    print("\n>>> INICIANDO CLASSIFICAÇÃO DE LINHAS")
    
    # Primeiro filtrar linhas muito próximas
    linhas = filtrar_linhas_proximas(linhas)
    
    # Tolerância para considerar se uma linha toca o retângulo (1 cm)
    tolerancia = 1.0
    
    # Filtrar apenas linhas que tocam o retângulo (com tolerância de 1 cm)
    linhas_validas = []
    for linha in linhas:
        pontos = linha["pontos"]
        p1_x, p1_y = pontos[0]
        p2_x, p2_y = pontos[-1]
        
        toca_retangulo = False
        
        if is_vertical:
            # Para retângulo vertical, verificar se a linha está dentro dos limites Y com tolerância
            if ((min_coord - tolerancia) <= p1_y <= (max_coord + tolerancia) or 
                (min_coord - tolerancia) <= p2_y <= (max_coord + tolerancia)):
                toca_retangulo = True
        else:
            # Para retângulo horizontal, verificar se a linha está dentro dos limites X com tolerância
            if ((min_coord - tolerancia) <= p1_x <= (max_coord + tolerancia) or 
                (min_coord - tolerancia) <= p2_x <= (max_coord + tolerancia)):
                toca_retangulo = True
        
        if toca_retangulo:
            linhas_validas.append(linha)
    
    print(f"  Número de linhas válidas após filtro de tolerância ({tolerancia} cm): {len(linhas_validas)}")
    
    # Continuação do código normal
    # Filtrar apenas linhas internas (descarta linhas externas)
    linhas_internas = []
    for linha in linhas_validas:
        pontos = linha["pontos"]
        p1_x, p1_y = pontos[0]
        p2_x, p2_y = pontos[-1]
        
        if is_vertical:
            # Para retângulo vertical, verificar se a linha está dentro dos limites Y
            if (min_coord <= p1_y <= max_coord or min_coord <= p2_y <= max_coord):
                linhas_internas.append(linha)
        else:
            # Para retângulo horizontal, verificar se a linha está dentro dos limites X
            if (min_coord <= p1_x <= max_coord or min_coord <= p2_x <= max_coord):
                linhas_internas.append(linha)
    
    print(f"  Número de linhas válidas após filtro: {len(linhas_internas)}")
    
    # Se não houver linhas, retornar lista vazia
    if not linhas_internas:
        return []
    
    # Função para calcular a largura real de uma abertura
    def calcular_largura_para_par(linha1, linha2):
        """
        Calcula a largura de uma abertura formada por um par de linhas (distância entre elas).
        """
        pontos1 = linha1["pontos"]
        pontos2 = linha2["pontos"]
        
        if is_vertical:
            # Para retângulo vertical, calculamos a distância em Y
            y1 = (pontos1[0][1] + pontos1[-1][1]) / 2
            y2 = (pontos2[0][1] + pontos2[-1][1]) / 2
            return abs(y1 - y2)
        else:
            # Para retângulo horizontal, calculamos a distância em X
            x1 = (pontos1[0][0] + pontos1[-1][0]) / 2
            x2 = (pontos2[0][0] + pontos2[-1][0]) / 2
            return abs(x1 - x2)
    
    # Calcular todas as combinações possíveis de pares de linhas
    from itertools import combinations
    
    # Calcular o par com a menor largura entre todas as linhas
    pares_possiveis = list(combinations(linhas_internas, 2))
    
    # Se não houver pares possíveis, retornar lista vazia
    if not pares_possiveis:
        return []
    
    # Calcular a largura para cada par e armazenar o par com a menor largura
    menor_largura = float('inf')
    par_menor_largura = None
    
    for par in pares_possiveis:
        linha1, linha2 = par
        largura = calcular_largura_para_par(linha1, linha2)
        print(f"  Par possível: {linha1['indice']+1} e {linha2['indice']+1} - largura: {largura:.2f}")
        
        if largura < menor_largura:
            menor_largura = largura
            par_menor_largura = par
    
    # Se não encontrou nenhum par válido, retornar lista vazia
    if par_menor_largura is None:
        return []
    
    linha1, linha2 = par_menor_largura
    print(f"  Par selecionado: {linha1['indice']+1} e {linha2['indice']+1} - largura: {menor_largura:.2f}")
    
    # Calcular a distância do par selecionado até as paredes esquerda e direita
    pontos1 = linha1["pontos"]
    pontos2 = linha2["pontos"]
    
    # Calcular distância à borda (distance real)
    def calcular_distancia_borda(linha):
        """Calcula a distância entre uma linha e a borda mais próxima do retângulo"""
        pontos = linha["pontos"]
        
        if is_vertical:
            # Para retângulo vertical, a distância é até o topo ou o fundo
            dist_topo = min(abs(pontos[0][1] - min_coord), abs(pontos[-1][1] - min_coord))  # Usando [-1] para o último ponto
            dist_fundo = min(abs(pontos[0][1] - max_coord), abs(pontos[-1][1] - max_coord))  # Usando [-1] para o último ponto
            return min(dist_topo, dist_fundo)
        else:
            # Para retângulo horizontal, a distância é até a esquerda ou a direita
            dist_esquerda = min(abs(pontos[0][0] - min_coord), abs(pontos[-1][0] - min_coord))  # Usando [-1] para o último ponto
            dist_direita = min(abs(pontos[0][0] - max_coord), abs(pontos[-1][0] - max_coord))  # Usando [-1] para o último ponto
            return min(dist_esquerda, dist_direita)
    
    # Calcular distância à borda para cada linha do par
    dist1 = calcular_distancia_borda(linha1)
    dist2 = calcular_distancia_borda(linha2)
    distancia = min(dist1, dist2)
    
    print(f"  Abertura calculada: Distância = {distancia:.2f}, Largura = {menor_largura:.2f}")
    
    # Retornar abertura com distância e largura
    return [(distancia, menor_largura)]

def _classificar_linhas_por_posicao(linhas, is_vertical, min_coord, max_coord, nome_lado):
    """
    Classifica linhas como esquerda/direita ou superior/inferior com base na posição.
    
    Args:
        linhas: Lista de linhas a classificar
        is_vertical: True se o retângulo está na vertical, False para horizontal
        min_coord, max_coord: Coordenadas mínimas e máximas do retângulo
        nome_lado: Nome do lado para depuração
        
    Returns:
        Dicionário com chaves "esquerda" e "direita" contendo as linhas classificadas
    """
    linhas_esquerda = []
    linhas_direita = []
    
    comprimento = max_coord - min_coord
    metade = min_coord + comprimento / 2
    
    for linha in linhas:
        pontos = linha["pontos"]
        p1 = pontos[0]
        p2 = pontos[-1]
        
        # Perspectiva de frente para o lado em questão
        if is_vertical:
            # Para retângulo vertical (lados esquerdo e direito)
            # Lado A é esquerdo, lado B é direito
            # Esquerda/direita na perspectiva de quem olha de frente para o lado
            x1, y1 = p1
            x2, y2 = p2
            
            # Ponto médio da linha no eixo Y
            y_medio = (y1 + y2) / 2
            
            if y_medio < metade:
                linhas_esquerda.append(linha)
            else:
                linhas_direita.append(linha)
        else:
            # Para retângulo horizontal (lados superior e inferior)
            # Lado A é inferior, lado B é superior
            # Esquerda/direita na perspectiva de quem olha de frente para o lado
            x1, y1 = p1
            x2, y2 = p2
            
            # Ponto médio da linha no eixo X
            x_medio = (x1 + x2) / 2
            
            if x_medio < metade:
                linhas_esquerda.append(linha)
            else:
                linhas_direita.append(linha)
    
    return {"esquerda": linhas_esquerda, "direita": linhas_direita}

def calcular_comprimento_linha(linha):
    """
    Calcula o comprimento de uma linha baseado em seus pontos.
    
    Args:
        linha: Dicionário contendo os pontos da linha
        
    Returns:
        Comprimento da linha em centímetros
    """
    pontos = linha["pontos"]
    if len(pontos) < 2:
        return 0
        
    p1_x, p1_y = pontos[0]
    p2_x, p2_y = pontos[-1]
    
    # Calcular distância euclidiana
    comprimento = ((p2_x - p1_x) ** 2 + (p2_y - p1_y) ** 2) ** 0.5
    return comprimento

def _processar_pares_mesmo_lado(linhas_esquerda, linhas_direita, is_vertical, nome_lado):
    """
    Processa pares de linhas no mesmo lado para calcular aberturas.
    
    Args:
        linhas_esquerda: Lista de linhas classificadas como esquerda
        linhas_direita: Lista de linhas classificadas como direita
        is_vertical: True se o retângulo está na vertical, False para horizontal
        nome_lado: Nome do lado para depuração
        
    Returns:
        Lista de aberturas no formato [(distância, largura, índice_linha_esq, índice_linha_dir), ...]
    """
    # Primeiro filtrar linhas muito curtas (menores que 3 cm)
    linhas_esquerda = [linha for linha in linhas_esquerda if calcular_comprimento_linha(linha) >= 3.0]
    linhas_direita = [linha for linha in linhas_direita if calcular_comprimento_linha(linha) >= 3.0]
    
    print(f"  Após filtrar linhas curtas: {len(linhas_esquerda)} linhas à esquerda, {len(linhas_direita)} linhas à direita")
    
    aberturas = []
    linhas_usadas = set()  # Conjunto para rastrear linhas já utilizadas
    
    # Função auxiliar para calcular distância e largura entre duas linhas
    def calcular_medidas(linha1, linha2):
        pontos1 = linha1["pontos"]
        pontos2 = linha2["pontos"]
        
        if is_vertical:
            # Calcular distância entre linhas (eixo Y para retângulo vertical)
            y1_medio = (pontos1[0][1] + pontos1[-1][1]) / 2
            y2_medio = (pontos2[0][1] + pontos2[-1][1]) / 2
            distancia = abs(y1_medio - y2_medio)
            
            # Calcular largura da abertura (eixo X para retângulo vertical)
            x1_medio = (pontos1[0][0] + pontos1[-1][0]) / 2
            x2_medio = (pontos2[0][0] + pontos2[-1][0]) / 2
            largura = abs(x1_medio - x2_medio)
        else:
            # Calcular distância entre linhas (eixo X para retângulo horizontal)
            x1_medio = (pontos1[0][0] + pontos1[-1][0]) / 2
            x2_medio = (pontos2[0][0] + pontos2[-1][0]) / 2
            distancia = abs(x1_medio - x2_medio)
            
            # Calcular largura da abertura (eixo Y para retângulo horizontal)
            y1_medio = (pontos1[0][1] + pontos1[-1][1]) / 2
            y2_medio = (pontos2[0][1] + pontos2[-1][1]) / 2
            largura = abs(y1_medio - y2_medio)
        
        return distancia, largura
    
    # Função para verificar se duas linhas estão muito próximas
    def linhas_proximas(linha1, linha2, tolerancia=1.0):
        pontos1 = linha1["pontos"]
        pontos2 = linha2["pontos"]
        
        # Calcular pontos médios
        x1_medio = (pontos1[0][0] + pontos1[-1][0]) / 2
        y1_medio = (pontos1[0][1] + pontos1[-1][1]) / 2
        x2_medio = (pontos2[0][0] + pontos2[-1][0]) / 2
        y2_medio = (pontos2[0][1] + pontos2[-1][1]) / 2
        
        # Calcular distância euclidiana
        dist = ((x2_medio - x1_medio) ** 2 + (y2_medio - y1_medio) ** 2) ** 0.5
        return dist < tolerancia
    
    # Processar lado esquerdo
    if len(linhas_esquerda) >= 2:
        # Primeiro, agrupar linhas muito próximas
        grupos_linhas = []
        linhas_agrupadas = set()
        
        for i, linha1 in enumerate(linhas_esquerda):
            if i in linhas_agrupadas:
                continue
                
            grupo_atual = [linha1]
            linhas_agrupadas.add(i)
            
            for j, linha2 in enumerate(linhas_esquerda[i+1:], i+1):
                if j in linhas_agrupadas:
                    continue
                    
                if linhas_proximas(linha1, linha2):
                    grupo_atual.append(linha2)
                    linhas_agrupadas.add(j)
            
            grupos_linhas.append(grupo_atual)
        
        # Agora processar os grupos para formar pares
        for grupo in grupos_linhas:
            if len(grupo) == 1:  # Linha individual
                linha = grupo[0]
                distancia = 0.0  # Distância padrão para linhas individuais
                largura = 19.0   # Largura padrão para linhas individuais
                print(f"  Linha individual {linha['indice']+1} - distância: {distancia:.2f}, largura: {largura:.2f}")
                aberturas.append((distancia, largura, linha['indice'], None))
            else:  # Grupo com múltiplas linhas - formar par com as duas mais distantes
                # Encontrar o par com maior largura no grupo
                max_largura = 0
                par_selecionado = None
                
                for i, linha1 in enumerate(grupo):
                    for linha2 in grupo[i+1:]:
                        distancia, largura = calcular_medidas(linha1, linha2)
                        if largura > max_largura:
                            max_largura = largura
                            par_selecionado = (linha1, linha2, distancia, largura)
                
                if par_selecionado:
                    linha1, linha2, distancia, largura = par_selecionado
                    print(f"  Par selecionado: {linha1['indice']+1} e {linha2['indice']+1} - largura: {largura:.2f}")
                    aberturas.append((distancia, largura, linha1['indice'], linha2['indice']))
    
    # Processar lado direito (mesmo processo)
    if len(linhas_direita) >= 2:
        # Primeiro, agrupar linhas muito próximas
        grupos_linhas = []
        linhas_agrupadas = set()
        
        for i, linha1 in enumerate(linhas_direita):
            if i in linhas_agrupadas:
                continue
                
            grupo_atual = [linha1]
            linhas_agrupadas.add(i)
            
            for j, linha2 in enumerate(linhas_direita[i+1:], i+1):
                if j in linhas_agrupadas:
                    continue
                    
                if linhas_proximas(linha1, linha2):
                    grupo_atual.append(linha2)
                    linhas_agrupadas.add(j)
            
            grupos_linhas.append(grupo_atual)
        
        # Agora processar os grupos para formar pares
        for grupo in grupos_linhas:
            if len(grupo) == 1:  # Linha individual
                linha = grupo[0]
                distancia = 0.0  # Distância padrão para linhas individuais
                largura = 19.0   # Largura padrão para linhas individuais
                print(f"  Linha individual {linha['indice']+1} - distância: {distancia:.2f}, largura: {largura:.2f}")
                aberturas.append((distancia, largura, None, None))
            else:  # Grupo com múltiplas linhas - formar par com as duas mais distantes
                # Encontrar o par com maior largura no grupo
                max_largura = 0
                par_selecionado = None
                
                for i, linha1 in enumerate(grupo):
                    for linha2 in grupo[i+1:]:
                        distancia, largura = calcular_medidas(linha1, linha2)
                        if largura > max_largura:
                            max_largura = largura
                            par_selecionado = (linha1, linha2, distancia, largura)
                
                if par_selecionado:
                    linha1, linha2, distancia, largura = par_selecionado
                    print(f"  Par selecionado: {linha1['indice']+1} e {linha2['indice']+1} - largura: {largura:.2f}")
                    aberturas.append((distancia, largura, None, None))
    
    return aberturas

def _calcular_abertura_cruzada(linha_A, linha_B, is_vertical):
    """Calcula a abertura formada por duas linhas de lados diferentes"""
    # Para aberturas que cruzam o retângulo, a distância é sempre zero
    distancia = 0.0
    
    # Calcular largura baseada na distância entre as linhas
    if is_vertical:
        largura = abs(linha_B["pontos"][0][1] - linha_A["pontos"][0][1])
    else:
        largura = abs(linha_B["pontos"][0][0] - linha_A["pontos"][0][0])
    
    if largura == 0:  # Evitar divisão por zero ou largura inválida
        largura = 19.0  # Valor padrão em caso de erro
    
    return (distancia, largura)

def _processar_aberturas_cruzadas(linhas_lado_A, linhas_lado_B, is_vertical, is_esquerda, min_coord, max_coord):
    """Função mantida para compatibilidade. A lógica foi movida para o corpo da função principal."""
    return []

# Função para processar todas as linhas do lado B, independente da classificação
def processar_lado_b(linhas_lado_b, is_vertical, min_coord, max_coord):
    """
    Processa todas as linhas do lado B, independente da classificação esquerda/direita,
    e encontra o par com a menor largura. Linhas individuais (que não formam pares) 
    terão distância 0 e largura igual à distância até a borda.
    
    Args:
        linhas_lado_b: Lista de todas as linhas do lado B
        is_vertical: True se o retângulo está na vertical, False para horizontal
        min_coord, max_coord: Coordenadas mínimas e máximas do retângulo
    
    Returns:
        Lista de aberturas no formato [(distância, largura, índice_linha_esq, índice_linha_dir), ...]
    """
    print("\n>>> PROCESSANDO TODAS AS LINHAS DO LADO B")
    
    # Filtrar linhas válidas (excluir linhas externas e muito curtas)
    linhas_validas = []
    for linha in linhas_lado_b:
        # Verificar comprimento mínimo
        if calcular_comprimento_linha(linha) < 3.0:
            print(f"  Linha {linha['indice']+1} ignorada por ser muito curta (comprimento < 3cm)")
            continue
            
        # Verificar se a linha é externa
        if "is_outside" in linha and linha["is_outside"]:
            print(f"  Linha {linha['indice']+1} ignorada por ser externa")
            continue
        
        # Verificar se a linha realmente toca o retângulo
        if "intersects_a" in linha and "intersects_b" in linha and not linha["intersects_a"] and not linha["intersects_b"]:
            print(f"  Linha {linha['indice']+1} ignorada por não tocar o retângulo")
            continue
        
        # Verificar se a linha está muito distante
        if "dist_a" in linha and "dist_b" in linha and linha["dist_a"] > 100 and linha["dist_b"] > 100:
            print(f"  Linha {linha['indice']+1} ignorada por estar muito distante (dist_a={linha['dist_a']:.2f}, dist_b={linha['dist_b']:.2f})")
            continue
        
        linhas_validas.append(linha)
    
    print(f"  Total de linhas válidas do lado B: {len(linhas_validas)}")
    
    # Se não houver linhas válidas, retornar lista vazia
    if not linhas_validas:
        return []
    
    # Função para calcular a largura entre duas linhas - CORRIGIDA para calcular o valor de 40
    def calcular_largura_para_par(linha1, linha2):
        """Calcula a largura entre duas linhas - ajustado para corresponder à abertura correta de 40cm"""
        pontos1 = linha1["pontos"]
        pontos2 = linha2["pontos"]
        
        if is_vertical:
            # Para retângulo vertical, calculamos a distância em Y (como em calcular_aberturas_em_pares)
            # já que estamos calculando a largura entre duas linhas horizontais
            y1 = (pontos1[0][1] + pontos1[-1][1]) / 2
            y2 = (pontos2[0][1] + pontos2[-1][1]) / 2
            return abs(y1 - y2)
        else:
            # Para retângulo horizontal, calculamos a distância em X (como originalmente)
            # Restaurando a lógica original para retângulos horizontais
            x1 = (pontos1[0][0] + pontos1[-1][0]) / 2
            x2 = (pontos2[0][0] + pontos2[-1][0]) / 2
            return abs(x1 - x2)
    
    # Função para calcular distância à borda
    def calcular_distancia_borda(linha):
        """Calcula a distância entre uma linha e a borda mais próxima do retângulo"""
        pontos = linha["pontos"]
        
        if is_vertical:
            # Para retângulo vertical, a distância é até o topo ou o fundo
            dist_topo = min(abs(pontos[0][1] - min_coord), abs(pontos[-1][1] - min_coord))  # Usando [-1] para o último ponto
            dist_fundo = min(abs(pontos[0][1] - max_coord), abs(pontos[-1][1] - max_coord))  # Usando [-1] para o último ponto
            return min(dist_topo, dist_fundo)
        else:
            # Para retângulo horizontal, a distância é até a esquerda ou a direita
            dist_esquerda = min(abs(pontos[0][0] - min_coord), abs(pontos[-1][0] - min_coord))  # Usando [-1] para o último ponto
            dist_direita = min(abs(pontos[0][0] - max_coord), abs(pontos[-1][0] - max_coord))  # Usando [-1] para o último ponto
            return min(dist_esquerda, dist_direita)
    
    # Função para determinar a parede mais próxima
    def determinar_parede_mais_proxima(linha):
        """Determina qual parede (esquerda ou direita) está mais próxima da linha"""
        pontos = linha["pontos"]
        
        if is_vertical:
            # Para retângulo vertical, verificar distância em Y
            y_medio = (pontos[0][1] + pontos[-1][1]) / 2  # Usando [-1] para o último ponto
            
            # Determinar qual parede está mais próxima
            dist_esquerda = abs(y_medio - min_coord)
            dist_direita = abs(y_medio - max_coord)
        else:
            # Para retângulo horizontal, verificar distância em X
            x_medio = (pontos[0][0] + pontos[-1][0]) / 2  # Usando [-1] para o último ponto
            
            # Determinar qual parede está mais próxima
            dist_esquerda = abs(x_medio - min_coord)
            dist_direita = abs(x_medio - max_coord)
        
        if dist_esquerda <= dist_direita:
            return "esquerda", dist_esquerda
        else:
            return "direita", dist_direita
    
    # Se houver apenas uma linha válida, tratá-la como individual
    if len(linhas_validas) == 1:
        linha = linhas_validas[0]
        parede, distancia_borda = determinar_parede_mais_proxima(linha)
        
        # Para linhas individuais, a distância é 0 e a largura é a distância até a borda
        distancia = 0
        largura = distancia_borda
        
        print(f"  Linha individual {linha['indice']+1} - parede: {parede}, distância: {distancia:.2f}, largura: {largura:.2f}")
        return [(distancia, largura, parede)]
    
    # Se houver mais de uma linha, calcular pares
    # Calcular todas as combinações possíveis de pares
    from itertools import combinations
    pares = list(combinations(linhas_validas, 2))
    
    # Calcular a largura para cada par
    pares_com_largura = []
    for linha1, linha2 in pares:
        largura = calcular_largura_para_par(linha1, linha2)
        # Ignorar pares com largura zero ou muito pequena (menor que 0.1)
        if largura > 0.1:
            pares_com_largura.append((largura, linha1, linha2))
            print(f"  Par {linha1['indice']+1} e {linha2['indice']+1} - largura: {largura:.2f}")
        else:
            print(f"  Par {linha1['indice']+1} e {linha2['indice']+1} ignorado - largura muito pequena: {largura:.2f}")
    
    # Ordenar pares por largura
    pares_com_largura.sort(key=lambda x: x[0])
    
    # Lista para armazenar resultados
    resultados = []
    
    # Se não houver pares válidos, processar todas as linhas como individuais
    if not pares_com_largura:
        print("  Nenhum par válido encontrado (todos com largura zero ou muito pequena)")
        print("  Processando todas as linhas como individuais")
        for linha in linhas_validas:
            parede, distancia_borda = determinar_parede_mais_proxima(linha)
            
            # Para linhas individuais, a distância é 0 e a largura é a distância até a borda
            distancia = 0
            largura = 19.0  # Usar largura padrão de 19cm para aberturas individuais
            
            print(f"  Linha individual {linha['indice']+1} - parede: {parede}, distância: {distancia:.2f}, largura: {largura:.2f}")
            resultados.append((distancia, largura, parede))
        
        return resultados
    
    # Conjunto para rastrear linhas já utilizadas em pares
    linhas_utilizadas = set()
    
    # Selecionar APENAS o par com menor largura
    menor_par = pares_com_largura[0]
    largura = menor_par[0]
    linha1 = menor_par[1]
    linha2 = menor_par[2]
    
    # Marcar linhas como utilizadas
    linhas_utilizadas.add(linha1["indice"])
    linhas_utilizadas.add(linha2["indice"])
    
    print(f"  Par selecionado: {linha1['indice']+1} e {linha2['indice']+1} - largura: {largura:.2f}")
    
    # Calcular a distância do par até as paredes
    pontos1 = linha1["pontos"]
    pontos2 = linha2["pontos"]
    
    # Calcular distância à borda para cada linha do par
    dist1 = calcular_distancia_borda(linha1)
    dist2 = calcular_distancia_borda(linha2)
    distancia = min(dist1, dist2)
    
    # Determinar a parede mais próxima (esquerda ou direita)
    if is_vertical:
        # Para retângulo vertical, verificar distância em Y
        y1 = (pontos1[0][1] + pontos1[-1][1]) / 2
        y2 = (pontos2[0][1] + pontos2[-1][1]) / 2
        y_medio = (y1 + y2) / 2
        
        # Determinar qual parede está mais próxima
        dist_esquerda = abs(y_medio - min_coord)
        dist_direita = abs(y_medio - max_coord)
    else:
        # Para retângulo horizontal, verificar distância em X
        x1 = (pontos1[0][0] + pontos1[-1][0]) / 2
        x2 = (pontos2[0][0] + pontos2[-1][0]) / 2
        x_medio = (x1 + x2) / 2
        
        # Determinar qual parede está mais próxima
        dist_esquerda = abs(x_medio - min_coord)
        dist_direita = abs(x_medio - max_coord)
    
    # Determinar a parede mais próxima
    if dist_esquerda <= dist_direita:
        parede = "esquerda"
    else:
        parede = "direita"
    
    print(f"  Distância para parede {parede}: {distancia:.2f}")
    print(f"  Largura final do par: {largura:.2f}")
    
    # Adicionar o par ao resultado
    resultados.append((distancia, largura, parede))
    
    # Processar linhas individuais (que não formam pares)
    for linha in linhas_validas:
        if linha["indice"] not in linhas_utilizadas:
            parede, distancia_borda = determinar_parede_mais_proxima(linha)
            
            # Para linhas individuais, a distância é 0 e a largura é a distância até a borda
            distancia = 0
            largura = distancia_borda
            
            print(f"  Linha individual {linha['indice']+1} - parede: {parede}, distância: {distancia:.2f}, largura: {largura:.2f}")
            resultados.append((distancia, largura, parede))
    
    return resultados

def processar_lado_a(linhas_lado_a, is_vertical, min_coord, max_coord):
    """
    Processa todas as linhas do lado A, independente da classificação, e encontra o par com menor largura.
    Linhas individuais (que não formam pares) terão distância 0 e largura igual à distância até a borda.
    
    Args:
        linhas_lado_a: Lista de linhas do lado A para processar
        is_vertical: True se o retângulo está na vertical, False para horizontal
        min_coord: Coordenada mínima do retângulo (Y mínimo para vertical, X mínimo para horizontal)
        max_coord: Coordenada máxima do retângulo (Y máximo para vertical, X máximo para horizontal)
    
    Returns:
        Lista contendo tuplas com (distância, largura, parede)
    """
    # Filtrar linhas válidas (excluir linhas externas e muito curtas)
    linhas_validas = []
    for linha in linhas_lado_a:
        # Verificar comprimento mínimo
        if calcular_comprimento_linha(linha) < 3.0:
            print(f"  Linha {linha['indice']+1} ignorada por ser muito curta (comprimento < 3cm)")
            continue
            
        # Verificar se a linha é externa
        if "is_outside" in linha and linha["is_outside"]:
            print(f"  Linha {linha['indice']+1} ignorada por ser externa")
            continue
        
        # Verificar se a linha realmente toca o retângulo
        if "intersects_a" in linha and "intersects_b" in linha and not linha["intersects_a"] and not linha["intersects_b"]:
            print(f"  Linha {linha['indice']+1} ignorada por não tocar o retângulo")
            continue
        
        # Verificar se a linha está muito distante
        if "dist_a" in linha and "dist_b" in linha and linha["dist_a"] > 100 and linha["dist_b"] > 100:
            print(f"  Linha {linha['indice']+1} ignorada por estar muito distante (dist_a={linha['dist_a']:.2f}, dist_b={linha['dist_b']:.2f})")
            continue
        
        # Verificar se a linha está dentro dos limites do retângulo
        pontos = linha["pontos"]
        p1_x, p1_y = pontos[0]
        p2_x, p2_y = pontos[-1]
        
        if is_vertical:
            # Para retângulo vertical, verificar se a linha está dentro dos limites Y
            if not (min_coord <= p1_y <= max_coord or min_coord <= p2_y <= max_coord):
                print(f"  Linha {linha['indice']+1} ignorada por estar fora dos limites Y")
                continue
        else:
            # Para retângulo horizontal, verificar se a linha está dentro dos limites X
            if not (min_coord <= p1_x <= max_coord or min_coord <= p2_x <= max_coord):
                print(f"  Linha {linha['indice']+1} ignorada por estar fora dos limites X")
                continue
        
        linhas_validas.append(linha)
    
    # Verificar se há pelo menos uma linha válida
    if not linhas_validas:
        print("  Não há linhas válidas no lado A")
        return []
    
    print(f"  Processando {len(linhas_validas)} linhas válidas no lado A")
    
    # Função para calcular a largura entre duas linhas - CORRIGIDA para calcular o valor de 40
    def calcular_largura_para_par(linha1, linha2):
        """Calcula a largura entre duas linhas - ajustado para corresponder à abertura correta de 40cm"""
        pontos1 = linha1["pontos"]
        pontos2 = linha2["pontos"]
        
        if is_vertical:
            # Para retângulo vertical, calculamos a distância em Y (como em calcular_aberturas_em_pares)
            # já que estamos calculando a largura entre duas linhas horizontais
            y1 = (pontos1[0][1] + pontos1[-1][1]) / 2
            y2 = (pontos2[0][1] + pontos2[-1][1]) / 2
            return abs(y1 - y2)
        else:
            # Para retângulo horizontal, calculamos a distância em X (como originalmente)
            # Restaurando a lógica original para retângulos horizontais
            x1 = (pontos1[0][0] + pontos1[-1][0]) / 2
            x2 = (pontos2[0][0] + pontos2[-1][0]) / 2
            return abs(x1 - x2)
    
    # Função para calcular distância à borda
    def calcular_distancia_borda(linha):
        """Calcula a distância entre uma linha e a borda mais próxima do retângulo"""
        pontos = linha["pontos"]
        
        if is_vertical:
            # Para retângulo vertical, a distância é até o topo ou o fundo
            dist_topo = min(abs(pontos[0][1] - min_coord), abs(pontos[-1][1] - min_coord))  # Usando [-1] para o último ponto
            dist_fundo = min(abs(pontos[0][1] - max_coord), abs(pontos[-1][1] - max_coord))  # Usando [-1] para o último ponto
            return min(dist_topo, dist_fundo)
        else:
            # Para retângulo horizontal, a distância é até a esquerda ou a direita
            dist_esquerda = min(abs(pontos[0][0] - min_coord), abs(pontos[-1][0] - min_coord))  # Usando [-1] para o último ponto
            dist_direita = min(abs(pontos[0][0] - max_coord), abs(pontos[-1][0] - max_coord))  # Usando [-1] para o último ponto
            return min(dist_esquerda, dist_direita)
    
    # Função para determinar a parede mais próxima
    def determinar_parede_mais_proxima(linha):
        """Determina qual parede (esquerda ou direita) está mais próxima da linha"""
        pontos = linha["pontos"]
        
        if is_vertical:
            # Para retângulo vertical, verificar distância em Y
            y_medio = (pontos[0][1] + pontos[-1][1]) / 2  # Usando [-1] para o último ponto
            
            # Determinar qual parede está mais próxima
            dist_esquerda = abs(y_medio - min_coord)
            dist_direita = abs(y_medio - max_coord)
        else:
            # Para retângulo horizontal, verificar distância em X
            x_medio = (pontos[0][0] + pontos[-1][0]) / 2  # Usando [-1] para o último ponto
            
            # Determinar qual parede está mais próxima
            dist_esquerda = abs(x_medio - min_coord)
            dist_direita = abs(x_medio - max_coord)
        
        if dist_esquerda <= dist_direita:
            return "esquerda", dist_esquerda
        else:
            return "direita", dist_direita
    
    # Se houver apenas uma linha válida, tratá-la como individual
    if len(linhas_validas) == 1:
        linha = linhas_validas[0]
        parede, distancia_borda = determinar_parede_mais_proxima(linha)
        
        # Para linhas individuais, a distância é 0 e a largura é a distância até a borda
        distancia = 0
        largura = distancia_borda
        
        print(f"  Linha individual {linha['indice']+1} - parede: {parede}, distância: {distancia:.2f}, largura: {largura:.2f}")
        return [(distancia, largura, parede)]
    
    # Se houver mais de uma linha, calcular pares
    # Calcular todas as combinações possíveis de pares
    from itertools import combinations
    pares = list(combinations(linhas_validas, 2))
    
    # Calcular a largura para cada par
    pares_com_largura = []
    for linha1, linha2 in pares:
        largura = calcular_largura_para_par(linha1, linha2)
        # Ignorar pares com largura zero ou muito pequena (menor que 0.1)
        if largura > 0.1:
            pares_com_largura.append((largura, linha1, linha2))
            print(f"  Par {linha1['indice']+1} e {linha2['indice']+1} - largura: {largura:.2f}")
        else:
            print(f"  Par {linha1['indice']+1} e {linha2['indice']+1} ignorado - largura muito pequena: {largura:.2f}")
    
    # Ordenar pares por largura
    pares_com_largura.sort(key=lambda x: x[0])
    
    # Lista para armazenar resultados
    resultados = []
    
    # Se não houver pares válidos, processar todas as linhas como individuais
    if not pares_com_largura:
        print("  Nenhum par válido encontrado (todos com largura zero ou muito pequena)")
        print("  Processando todas as linhas como individuais")
        for linha in linhas_validas:
            parede, distancia_borda = determinar_parede_mais_proxima(linha)
            
            # Para linhas individuais, a distância é 0 e a largura é a distância até a borda
            distancia = 0
            largura = 19.0  # Usar largura padrão de 19cm para aberturas individuais
            
            print(f"  Linha individual {linha['indice']+1} - parede: {parede}, distância: {distancia:.2f}, largura: {largura:.2f}")
            resultados.append((distancia, largura, parede))
        
        return resultados
    
    # Conjunto para rastrear linhas já utilizadas em pares
    linhas_utilizadas = set()
    
    # Selecionar o par com menor largura
    menor_par = pares_com_largura[0]
    largura = menor_par[0]
    linha1 = menor_par[1]
    linha2 = menor_par[2]
    
    # Marcar linhas como utilizadas
    linhas_utilizadas.add(linha1["indice"])
    linhas_utilizadas.add(linha2["indice"])
    
    print(f"  Par selecionado: {linha1['indice']+1} e {linha2['indice']+1} - largura: {largura:.2f}")
    
    # Calcular a distância do par até as paredes
    pontos1 = linha1["pontos"]
    pontos2 = linha2["pontos"]
    
    # Calcular distância à borda para cada linha do par
    dist1 = calcular_distancia_borda(linha1)
    dist2 = calcular_distancia_borda(linha2)
    distancia = min(dist1, dist2)
    
    # Determinar a parede mais próxima (esquerda ou direita)
    if is_vertical:
        # Para retângulo vertical, verificar distância em Y
        y1 = (pontos1[0][1] + pontos1[-1][1]) / 2
        y2 = (pontos2[0][1] + pontos2[-1][1]) / 2
        y_medio = (y1 + y2) / 2
        
        # Determinar qual parede está mais próxima
        dist_esquerda = abs(y_medio - min_coord)
        dist_direita = abs(y_medio - max_coord)
    else:
        # Para retângulo horizontal, verificar distância em X
        x1 = (pontos1[0][0] + pontos1[-1][0]) / 2
        x2 = (pontos2[0][0] + pontos2[-1][0]) / 2
        x_medio = (x1 + x2) / 2
        
        # Determinar qual parede está mais próxima
        dist_esquerda = abs(x_medio - min_coord)
        dist_direita = abs(x_medio - max_coord)
    
    # Determinar a parede mais próxima
    if dist_esquerda <= dist_direita:
        parede = "esquerda"
    else:
        parede = "direita"
    
    print(f"  Distância para parede {parede}: {distancia:.2f}")
    print(f"  Largura final do par: {largura:.2f}")
    
    # Adicionar o par ao resultado
    resultados.append((distancia, largura, parede))
    
    # Processar linhas individuais (que não formam pares)
    for linha in linhas_validas:
        if linha["indice"] not in linhas_utilizadas:
            parede, distancia_borda = determinar_parede_mais_proxima(linha)
            
            # Para linhas individuais, a distância é 0 e a largura é a distância até a borda
            distancia = 0
            largura = distancia_borda
            
            print(f"  Linha individual {linha['indice']+1} - parede: {parede}, distância: {distancia:.2f}, largura: {largura:.2f}")
            resultados.append((distancia, largura, parede))
    
    return resultados

def processar_aberturas(linhas_lado_a, linhas_lado_b, is_vertical, min_coord_a, max_coord_a, min_coord_b, max_coord_b):
    """
    Processa as aberturas para os lados A e B, calculando distâncias e larguras.
    
    Args:
        linhas_lado_a: Lista de linhas do lado A, classificadas por posição
        linhas_lado_b: Lista de linhas do lado B, classificadas por posição
        is_vertical: True se o retângulo está na vertical, False para horizontal
        min_coord_a, max_coord_a: Coordenadas mínimas e máximas do lado A
        min_coord_b, max_coord_b: Coordenadas mínimas e máximas do lado B
    
    Returns:
        Dicionário com as aberturas calculadas para cada lado
    """
    # Inicializar dicionário de resultados
    resultados = {
        "A_esq": [],
        "A_dir": [],
        "B_esq": [],
        "B_dir": []
    }
    
    # Processar lado A - usando APENAS a função processar_lado_a
    print(">>> Processando lado A com todas as linhas:")
    # Verificar se há linhas no lado A
    if "todas" in linhas_lado_a and linhas_lado_a["todas"]:
        # Extrair todas as linhas do lado A
        todas_linhas_a = []
        for linha in linhas_lado_a["todas"]:
            todas_linhas_a.append(linha)
        
        # Processar todas as linhas do lado A juntas
        aberturas_lado_a = processar_lado_a(todas_linhas_a, is_vertical, min_coord_a, max_coord_a)
        
        # Distribuir as aberturas do lado A conforme a parede mais próxima
        for distancia, largura, parede in aberturas_lado_a:
            if is_vertical:
                # Para retângulo vertical, inverter a lógica
                if parede == "esquerda":
                    resultados["A_dir"].append((distancia, largura))
                    print(f"  Abertura adicionada ao lado A-Direita: Distância = {distancia:.2f}, Largura = {largura:.2f}")
                else:
                    resultados["A_esq"].append((distancia, largura))
                    print(f"  Abertura adicionada ao lado A-Esquerda: Distância = {distancia:.2f}, Largura = {largura:.2f}")
            else:
                # Para retângulo horizontal, inverter a lógica
                if parede == "esquerda":
                    resultados["A_esq"].append((distancia, largura))
                    print(f"  Abertura adicionada ao lado A-Esquerda: Distância = {distancia:.2f}, Largura = {largura:.2f}")
                else:
                    resultados["A_dir"].append((distancia, largura))
                    print(f"  Abertura adicionada ao lado A-Direita: Distância = {distancia:.2f}, Largura = {largura:.2f}")
    else:
        print("  Nenhuma linha encontrada no lado A")
    
    # NÃO processar o lado A novamente com calcular_aberturas_em_pares
    
    # Processar lado B - usando a nova função que considera todas as linhas
    print(">>> Processando lado B com todas as linhas:")
    # Verificar se há linhas no lado B
    if "todas" in linhas_lado_b and linhas_lado_b["todas"]:
        # Extrair todas as linhas do lado B
        todas_linhas_b = []
        for linha in linhas_lado_b["todas"]:
            todas_linhas_b.append(linha)
        
        # Processar todas as linhas do lado B juntas
        aberturas_lado_b = processar_lado_b(todas_linhas_b, is_vertical, min_coord_b, max_coord_b)
        
        # Distribuir as aberturas do lado B conforme a parede mais próxima
        for distancia, largura, parede in aberturas_lado_b:
            if is_vertical:
                # Para retângulo vertical, manter a lógica original
                if parede == "esquerda":
                    resultados["B_esq"].append((distancia, largura))
                    print(f"  Abertura adicionada ao lado B-Esquerda: Distância = {distancia:.2f}, Largura = {largura:.2f}")
                else:
                    resultados["B_dir"].append((distancia, largura))
                    print(f"  Abertura adicionada ao lado B-Direita: Distância = {distancia:.2f}, Largura = {largura:.2f}")
            else:
                # Para retângulo horizontal, inverter esquerda e direita
                if parede == "esquerda":
                    resultados["B_dir"].append((distancia, largura))
                    print(f"  Abertura adicionada ao lado B-Direita (invertido): Distância = {distancia:.2f}, Largura = {largura:.2f}")
                else:
                    resultados["B_esq"].append((distancia, largura))
                    print(f"  Abertura adicionada ao lado B-Esquerda (invertido): Distância = {distancia:.2f}, Largura = {largura:.2f}")
    else:
        print("  Nenhuma linha encontrada no lado B")
    
    return resultados

def classificar_linhas_por_lado(linhas, is_vertical, retangulo):
    """
    Classifica as linhas por lado (A ou B) e por posição (esquerda ou direita).
    
    Args:
        linhas: Lista de linhas para classificar
        is_vertical: True se o retângulo está na vertical, False para horizontal
        retangulo: Coordenadas do retângulo (x_min, y_min, x_max, y_max)
    
    Returns:
        Tupla com (linhas_lado_a, linhas_lado_b, min_coord_a, max_coord_a, min_coord_b, max_coord_b)
    """
    # Extrair coordenadas do retângulo
    x_min, y_min, x_max, y_max = retangulo
    
    # Inicializar listas para cada lado
    linhas_lado_a = {"esquerda": [], "direita": [], "todas": []}
    linhas_lado_b = {"esquerda": [], "direita": [], "todas": []}
    
    # Determinar coordenadas para cada lado
    if is_vertical:
        # Para retângulo vertical, lado A é esquerdo e lado B é direito
        min_coord_a = y_min
        max_coord_a = y_max
        min_coord_b = y_min
        max_coord_b = y_max
    else:
        # Para retângulo horizontal, lado A é inferior e lado B é superior
        min_coord_a = x_min
        max_coord_a = x_max
        min_coord_b = x_min
        max_coord_b = x_max
    
    # Classificar linhas por lado (A ou B)
    linhas_lado_a_todas = []
    linhas_lado_b_todas = []
    
    for linha in linhas:
        if linha["lado"] == "A":
            linhas_lado_a_todas.append(linha)
            # Adicionar à lista "todas" do lado A
            linhas_lado_a["todas"].append(linha)
        elif linha["lado"] == "B":
            linhas_lado_b_todas.append(linha)
            # Adicionar à lista "todas" do lado B
            linhas_lado_b["todas"].append(linha)
    
    # Classificar linhas do lado A por posição (esquerda ou direita)
    for linha in linhas_lado_a_todas:
        if linha["posicao"] == "esquerda":
            linhas_lado_a["esquerda"].append(linha)
        elif linha["posicao"] == "direita":
            linhas_lado_a["direita"].append(linha)
    
    # Classificar linhas do lado B por posição (esquerda ou direita)
    for linha in linhas_lado_b_todas:
        if linha["posicao"] == "esquerda":
            linhas_lado_b["esquerda"].append(linha)
        elif linha["posicao"] == "direita":
            linhas_lado_b["direita"].append(linha)
    
    # Imprimir resultados da classificação
    print("\n>>> LINHAS CLASSIFICADAS:")
    print(f">>> Lado A - Esquerda: {len(linhas_lado_a['esquerda'])} linhas")
    print(f">>> Lado A - Direita: {len(linhas_lado_a['direita'])} linhas")
    print(f">>> Lado B - Esquerda: {len(linhas_lado_b['esquerda'])} linhas")
    print(f">>> Lado B - Direita: {len(linhas_lado_b['direita'])} linhas")
    print(f">>> Lado B - Total: {len(linhas_lado_b['todas'])} linhas")
    
    return (linhas_lado_a, linhas_lado_b, min_coord_a, max_coord_a, min_coord_b, max_coord_b) 

def filtrar_linhas_proximas(linhas, tolerancia=1.0):
    """
    Filtra linhas que estão muito próximas umas das outras (distância < tolerância).
    Retorna apenas uma linha de cada grupo de linhas próximas.
    """
    if not linhas:
        return []
        
    linhas_filtradas = []
    linhas_usadas = set()
    
    for i, linha1 in enumerate(linhas):
        if i in linhas_usadas:
            continue
            
        grupo_atual = [linha1]
        linhas_usadas.add(i)
        
        for j, linha2 in enumerate(linhas):
            if j <= i or j in linhas_usadas:
                continue
                
            # Calcular distância entre as linhas
            pontos1 = linha1["pontos"]
            pontos2 = linha2["pontos"]
            
            # Calcular ponto médio de cada linha
            x1_medio = (pontos1[0][0] + pontos1[-1][0]) / 2
            y1_medio = (pontos1[0][1] + pontos1[-1][1]) / 2
            x2_medio = (pontos2[0][0] + pontos2[-1][0]) / 2
            y2_medio = (pontos2[0][1] + pontos2[-1][1]) / 2
            
            # Calcular distância entre os pontos médios
            dist = ((x2_medio - x1_medio) ** 2 + (y2_medio - y1_medio) ** 2) ** 0.5
            
            if dist < tolerancia:
                grupo_atual.append(linha2)
                linhas_usadas.add(j)
                print(f">>> Linha {j+1} muito próxima da linha {i+1} (distância={dist:.2f})")
        
        # Adicionar apenas a primeira linha do grupo
        linhas_filtradas.append(grupo_atual[0])
        
    return linhas_filtradas 

def remover_aberturas_duplicadas(aberturas, tolerancia=1.0):
    """
    Remove aberturas duplicadas e inválidas usando uma lógica mais robusta.
    
    Args:
        aberturas: Lista de aberturas no formato [(distancia, largura), ...]
        tolerancia: Tolerância para considerar aberturas como duplicadas
        
    Returns:
        Lista de aberturas únicas e válidas
    """
    if not aberturas:
        return []
    
    # Primeiro, remover aberturas com largura ou distância inválida
    aberturas_validas = []
    for abertura in aberturas:
        distancia, largura = abertura[:2]  # Pegar apenas os dois primeiros valores
        
        # Verificar se a largura é válida (maior que 0.1 para evitar aberturas muito estreitas)
        if largura <= 0.1:
            print(f"  Removendo abertura inválida (largura muito pequena): Distância={distancia:.2f}, Largura={largura:.2f}")
            continue
            
        # Verificar se a distância é válida (não negativa)
        if distancia < 0:
            print(f"  Removendo abertura inválida (distância negativa): Distância={distancia:.2f}, Largura={largura:.2f}")
            continue
            
        # Verificar se a largura é muito grande (provavelmente erro)
        if largura > 100:  # 100cm é um limite razoável
            print(f"  Removendo abertura inválida (largura muito grande): Distância={distancia:.2f}, Largura={largura:.2f}")
            continue
            
        # Verificar se a distância é muito grande (provavelmente erro)
        if distancia > 300:  # 300cm é um limite razoável
            print(f"  Removendo abertura inválida (distância muito grande): Distância={distancia:.2f}, Largura={largura:.2f}")
            continue
            
        aberturas_validas.append(abertura)
    
    if not aberturas_validas:
        return []
    
    # Ordenar aberturas por distância e depois por largura
    aberturas_ordenadas = sorted(aberturas_validas, key=lambda x: (x[0], -x[1]))  # -x[1] para ordenar largura em ordem decrescente
    
    # Lista para armazenar aberturas únicas
    aberturas_unicas = []
    
    # Função para verificar se uma abertura é similar a outra
    def sao_similares(a1, a2):
        dist1, larg1 = a1[:2]
        dist2, larg2 = a2[:2]
        
        # Se as distâncias são muito próximas
        if abs(dist1 - dist2) < tolerancia:
            # Se as larguras também são próximas, são duplicatas
            if abs(larg1 - larg2) < tolerancia:
                return True
            # Se uma largura é muito maior que a outra, não são duplicatas
            if abs(larg1 - larg2) > 3 * tolerancia:
                return False
            # Se as larguras são diferentes mas próximas, considerar duplicata
            return True
        
        return False
    
    # Processar cada abertura
    for abertura in aberturas_ordenadas:
        distancia, largura = abertura[:2]
        
        # Verificar se é similar a alguma abertura já adicionada
        duplicada = False
        for abertura_unica in aberturas_unicas:
            if sao_similares(abertura, abertura_unica):
                dist_unica, larg_unica = abertura_unica[:2]
                # Se a largura atual é significativamente maior, substituir a existente
                if largura > larg_unica + 3 * tolerancia:
                    print(f"  Substituindo abertura menor por maior: {dist_unica:.2f}/{larg_unica:.2f} -> {distancia:.2f}/{largura:.2f}")
                    aberturas_unicas.remove(abertura_unica)
                    duplicada = False
                    break
                else:
                    print(f"  Removendo abertura duplicada: {distancia:.2f}/{largura:.2f} (similar a {dist_unica:.2f}/{larg_unica:.2f})")
                    duplicada = True
                    break
        
        # Se não for duplicada e ainda não temos duas aberturas, adicionar
        if not duplicada and len(aberturas_unicas) < 2:
            aberturas_unicas.append(abertura)
            print(f"  Adicionando abertura única: Distância={distancia:.2f}, Largura={largura:.2f}")
    
    # Se ainda temos mais de duas aberturas (caso raro), manter as duas mais significativas
    if len(aberturas_unicas) > 2:
        print("  Mais de duas aberturas encontradas, selecionando as mais significativas:")
        # Ordenar por uma combinação de largura e distância
        aberturas_unicas.sort(key=lambda x: (-x[1], x[0]))  # Priorizar maior largura, depois menor distância
        aberturas_unicas = aberturas_unicas[:2]
        for abertura in aberturas_unicas:
            print(f"    Mantida: Distância={abertura[0]:.2f}, Largura={abertura[1]:.2f}")
    
    # Ordenar resultado final por distância
    return sorted(aberturas_unicas, key=lambda x: x[0]) 