import json
import sqlite3
import numpy as np
from laje_src.services.ai.gemini_service import GeminiService
from laje_src.services.ai.groq_service import GroqService # Novo serviço Groq
import logging
from typing import List, Tuple, Dict, Optional, Any
from laje_src.utils.path_helper import PathHelper
import os
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

class LayoutLearner:
    """
    Classe responsável pelo aprendizado e dedução de layouts de lajes.
    Utiliza algoritmos de Machine Learning (KNN) para sugerir configurações
    baseadas em exemplos validados pelo usuário.
    Integra SmartPanner para lógica baseada em regras de engenharia.
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            self.db_path = str(PathHelper.get_app_data_dir() / "learning_map.db")
        else:
            self.db_path = db_path
            
        self._ensure_data_dir()
        self._init_db()
        self._model = None
        self._scaler = None
        
        # MIGRADO PARA GROQ (Llama 3) - Chave fornecida pelo usuário
        # GROQ_API_KEY_REMOVED
        self.ai_service = GroqService("GROQ_API_KEY_REMOVED")
        self.ollama_service = None # Lazy load no fallback
        
        # Smart Panner (Lógica de Engenharia Base)
        from laje_src.services.ai.smart_panner import SmartPanner
        self.smart_panner = SmartPanner()
        
        # self.gemini_service = GeminiService(...) # Deprecado por falta de cota
        
        # self._load_model_if_exists() # Lazy loading agora
        # self._load_model_if_exists() # Lazy loading agora
        
    def _ensure_data_dir(self):
        """Garante que o diretório de dados existe"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
    def _init_db(self):
        """Inicializa o banco de dados SQLite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabela para armazenar os exemplos de treinamento
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS training_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                
                -- Features Geométricas (Input)
                area REAL,
                perimetro REAL,
                aspect_ratio REAL,
                convexidade REAL,
                num_vertices INTEGER,
                num_ilhas INTEGER,
                area_ilhas_relativa REAL,
                bbox_width REAL,
                bbox_height REAL,
                compactness REAL,
                
                -- Configuração Validada (Output - armazenado como JSON)
                modo_calculo INTEGER,
                linhas_verticais TEXT, -- JSON array
                linhas_horizontais TEXT, -- JSON array
                opcoes_extras TEXT, -- JSON object (bordes, alinhamentos, etc)
                
                -- Metadados
                comentarios TEXT,
                feedback_type TEXT DEFAULT 'positive', -- 'positive' ou 'negative'
                intelligence_mode INTEGER DEFAULT 0
            )
        ''')
        
        # Migração simples (se coluna não existir)
        try:
            cursor.execute('ALTER TABLE training_examples ADD COLUMN feedback_type TEXT DEFAULT "positive"')
        except sqlite3.OperationalError:
            pass # Coluna já existe

        # Migração de Features (v2)
        try:
            cursor.execute('ALTER TABLE training_examples ADD COLUMN bbox_width REAL DEFAULT 0')
            cursor.execute('ALTER TABLE training_examples ADD COLUMN bbox_height REAL DEFAULT 0')
            cursor.execute('ALTER TABLE training_examples ADD COLUMN compactness REAL DEFAULT 0')
        except sqlite3.OperationalError:
            pass

        
        # Migração: Intelligence Mode (Modo 1 vs Modo 2)
        try:
            cursor.execute('ALTER TABLE training_examples ADD COLUMN intelligence_mode INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass

        # Tabela para armazenar regras e insights textuais
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interpretation_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                rule_type TEXT DEFAULT 'line', -- 'line' ou 'dimension'
                intelligence_mode INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Migração: Rule Type e Intelligence Mode em Regras
        try:
            cursor.execute('ALTER TABLE interpretation_rules ADD COLUMN rule_type TEXT DEFAULT "line"')
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute('ALTER TABLE interpretation_rules ADD COLUMN intelligence_mode INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        
        conn.commit()
        conn.close()

    def _load_model_if_exists(self):
        """Carrega o modelo treinado em memória (ou treina com dados existentes)"""
        # Em uma implementação real, carregaríamos o modelo serializado ou retreinaríamos
        # com todos os dados do banco na inicialização.
        # Por enquanto, deixaremos para treinar sob demanda (Lazy Learning).
        pass

    def extract_features(self, coordenadas: List[Tuple[float, float]], obstaculos: List[List[Tuple[float, float]]] = None) -> List[float]:
        """
        Extrai vetor de features a partir das coordenadas do polígono e obstáculos.
        
        Features:
        1. Área Total
        2. Perímetro
        3. Aspect Ratio (Bounding Box)
        4. Convexidade (Área / Área Convex Hull)
        5. Número de Vértices
        6. Número de Ilhas
        7. Área Relativa das Ilhas
        8. Width (Bounding Box)
        9. Height (Bounding Box)
        10. Compactness
        """
        if not coordenadas or len(coordenadas) < 3:
            return [0.0] * 10
            
        try:
            from shapely.geometry import Polygon
            poly = Polygon(coordenadas)
            
            # Subtrair buracos (ilhas) se houver
            area_ilhas = 0.0
            num_ilhas = 0
            if obstaculos:
                for obs_coords in obstaculos:
                    if len(obs_coords) >= 3:
                        hole = Polygon(obs_coords)
                        if poly.contains(hole): # Só conta se estiver dentro
                            poly = poly.difference(hole)
                            area_ilhas += hole.area
                            num_ilhas += 1
            
            # Calcular propriedades
            area = poly.area
            perimetro = poly.length
            
            # Bounding Box
            minx, miny, maxx, maxy = poly.bounds
            width = maxx - minx
            height = maxy - miny
            aspect_ratio = width / height if height > 0 else 0
            
            # Convexidade
            convex_hull = poly.convex_hull
            hull_area = convex_hull.area
            convexidade = area / hull_area if hull_area > 0 else 1.0
            
            # Número de vértices (do contorno externo)
            num_vertices = len(coordenadas)
            
            # Área relativa das ilhas
            area_ilhas_relativa = area_ilhas / (area + area_ilhas) if (area + area_ilhas) > 0 else 0
            
            # Compacidade (Isoperimetric Quotient) - Indica quão circular/compacta é a forma
            compactness = (4 * np.pi * area) / (perimetro ** 2) if perimetro > 0 else 0

            features = [
                area,
                perimetro,
                aspect_ratio,
                convexidade,
                float(num_vertices),
                float(num_ilhas),
                area_ilhas_relativa,
                width,
                height,
                compactness
            ]
            
            # Tratar NaNs ou Infinitos
            return [0.0 if np.isnan(x) or np.isinf(x) else x for x in features]
            
        except Exception as e:
            print(f"Erro ao extrair features: {e}")
            return [0.0] * 10

    def save_training_example(self, 
                             coordenadas: List[Tuple[float, float]], 
                             obstaculos: List[List[Tuple[float, float]]],
                             modo_calculo: int,
                             linhas_verticais: List[float],
                             linhas_horizontais: List[float],
                             opcoes_extras: Dict[str, Any],
                             comentarios: str = "",
                             feedback_type: str = "positive",
                             intelligence_mode: int = 0) -> bool:
        """Salva um novo exemplo de treinamento no banco de dados"""
        
        features = self.extract_features(coordenadas, obstaculos)

        linhas_verticais = self._clean_lines(linhas_verticais)
        linhas_horizontais = self._clean_lines(linhas_horizontais)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO training_examples (
                    area, perimetro, aspect_ratio, convexidade, num_vertices, 
                    num_ilhas, area_ilhas_relativa, bbox_width, bbox_height, compactness,
                    modo_calculo, linhas_verticais, linhas_horizontais, opcoes_extras, comentarios, feedback_type, intelligence_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                features[0], features[1], features[2], features[3], int(features[4]), 
                int(features[5]), features[6], features[7], features[8], features[9],
                modo_calculo,
                json.dumps(linhas_verticais),
                json.dumps(linhas_horizontais),
                json.dumps(opcoes_extras),
                comentarios,
                feedback_type,
                intelligence_mode
            ))
            conn.commit()
            
            # --- DETECÇÃO DE REGRAS GLOBAIS ---
            # Se o comentário contém palavras-chave de persistência, salvar como regra global
            if comentarios:
                c_lower = comentarios.lower()
                keywords = ["sempre", "regra", "padrao", "todas", "todos"]
                if any(k in c_lower for k in keywords):
                    print(f"[AI] Detectada intenção de regra global: '{comentarios}'")
                    # Salvar apenas se tiver conteúdo útil de heurística
                    # (Checagem simples para evitar lixo)
                    if "distancia" in c_lower or "uniao" in c_lower or "vertical" in c_lower or "horizontal" in c_lower:
                        self.add_rule(comentarios, intelligence_mode=intelligence_mode)
            
            return True
        except Exception as e:
            print(f"Erro ao salvar exemplo de treino: {e}")
            return False
        finally:
            conn.close()

    def delete_training_example(self, coordenadas: List[Tuple[float, float]], obstaculos: List[List[Tuple[float, float]]], 
                               modo_calculo: int, lines_v: List[float], lines_h: List[float]) -> bool:
        """Exclui um exemplo de treinamento que combine com os dados fornecidos."""
        features = self.extract_features(coordenadas, obstaculos)
        area, perimetro = features[0], features[1]
        bw, bh = features[7], features[8]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Sanitizar linhas da mesma forma que no salvamento
        lines_v = self._clean_lines(lines_v)
        lines_h = self._clean_lines(lines_h)
        
        try:
            # Tentar encontrar um registro muito similar
            # Tolerância pequena para flutuações de float
            cursor.execute('''
                DELETE FROM training_examples 
                WHERE abs(area - ?) < 1.0 
                  AND abs(perimetro - ?) < 1.0
                  AND abs(bbox_width - ?) < 1.0
                  AND abs(bbox_height - ?) < 1.0
                  AND modo_calculo = ?
                  AND linhas_verticais = ?
                  AND linhas_horizontais = ?
            ''', (area, perimetro, bw, bh, modo_calculo, json.dumps(lines_v), json.dumps(lines_h)))
            
            affected = cursor.rowcount
            conn.commit()
            if affected > 0:
                print(f"[AI] Excluídos {affected} exemplos de treinamento idênticos do DB.")
                return True
            return False
        except Exception as e:
            print(f"Erro ao excluir exemplo de treino: {e}")
            return False
        finally:
            conn.close()

    def _clean_lines(self, lines_list: List[Any]) -> List[Any]:
        """Filtra linhas pequenas e ruídos indesejados no treinamento."""
        if not lines_list: return []
        cleaned = []
        for item in lines_list:
            val = item["value"] if isinstance(item, dict) else float(item)
            if val >= 15.0 or (20.0 <= val <= 30.0):
                cleaned.append(item)
        return cleaned

    def _detect_pattern(self, lines: List[Any], total_len: float) -> Dict[str, Any]:
        """Detecta se existe um padrão de repetição nas linhas."""
        if not lines:
            return {"type": "NONE"}
            
        # Padrões conhecidos
        standard_panels = [60.0, 122.0, 182.0, 244.0]
        
        # Contagem de ocorrências
        counts = {}
        total_covered = 0.0
        
        for item in lines:
            val = item["value"] if isinstance(item, dict) else float(item)
            total_covered += val
            # Arredondar para agrupar (ex: 60.1 virar 60.0)
            rounded = round(val, 1)
            # Match com standard
            matched = False
            for s in standard_panels:
                if abs(val - s) < 0.5:
                    rounded = s
                    matched = True
                    break
            
            counts[rounded] = counts.get(rounded, 0) + 1
            
        # Analisar dominância E presença de GAP (União)
        has_gap = False
        gap_size = 0.0
        
        # Detectar se existe um gap comum (entre 18 e 32 cm - tolerância para 20 ou 30)
        gap_candidates = [k for k in counts.keys() if 18.0 <= k <= 32.0]
        if gap_candidates:
            # Pegar o gap mais comum
            gap_size = max(gap_candidates, key=lambda k: counts[k])
            if counts[gap_size] >= (len(lines) // 3): # Se aparece pelo menos 1/3 das vezes (Panel-Gap-Panel...)
                 has_gap = True
        
        # Se um painel aparece mais de 50% das vezes OU cobre mais de 60% do espaço
        for val, count in counts.items():
            if val < 35.0: continue # Ignorar gaps/pequenos na busca pelo Painel Principal
            
            coverage = (val * count)
            coverage_pct = coverage / total_covered if total_covered > 0 else 0
            count_pct = count / len(lines)
            
            print(f"[AI_DEBUG] Pattern Check: Val={val}, Count={count}, Cov%={coverage_pct:.2f}, HasGap={has_gap}")
            
            # Regra: Se cobre > 60% ou é > 70% dos itens
            # Relaxando regra para REPEAT: se contagem > 1 e pct > 50%
            if (coverage_pct > 0.60) or (count_pct > 0.60 and len(lines) > 1):
                if has_gap:
                     return {"type": "REPEAT_WITH_GAP", "value": val, "gap": gap_size}
                return {"type": "REPEAT", "value": val}
                
        return {"type": "EXACT"}

    def _apply_pattern(self, pattern: Dict[str, Any], target_len: float) -> List[float]:
        """Gera novas linhas baseadas no padrão para um comprimento alvo."""
        if pattern["type"] == "REPEAT_WITH_GAP":
             val = pattern["value"]
             gap = pattern["gap"]
             if val <= 0: return []
             
             # Estratégia: Painel + Gap + Painel + Gap...
             unit_complete = val + gap
             
             num_units = int(target_len // unit_complete)
             
             # Verificar o resto
             remainder = target_len - (num_units * unit_complete)
             
             # Se o resto couber mais um painel (sem gap final), adiciona
             extra_panel = False
             if remainder >= val - 5.0: # Tolerancia
                 extra_panel = True
             
             # Se num_units for 0 mas couber 1 painel
             if num_units == 0 and target_len >= val - 5.0:
                 return [val]
             
             result = []
             for _ in range(num_units):
                 result.append(val)
                 result.append(gap)
             
             # Remover o último gap se não for necessário (ou manter se o estilo exige?)
             # Geralmente, não queremos terminar com gap se for o fim da laje.
             # Mas se tiver extra panel, o gap fica.
             
             if extra_panel:
                 result.append(val)
             elif result and result[-1] == gap:
                 result.pop() # Remove gap final se não couber mais nada
                 
             print(f"[AI_DEBUG] Apply Pattern WITH GAP: Val={val} Gap={gap} Target={target_len} Result={result}")
             return result

        if pattern["type"] != "REPEAT":
            return []
            
        val = pattern["value"]
        if val <= 0: return []
        
        # Calcular quantos cabem
        # Estratégia: Preencher até acabar
        # Ex: Target 300, Panel 60 -> 5 painéis.
        # Ex: Target 320, Panel 60 -> 5 painéis (300) + Sobra 20 (UI cuida)
        
        num_panels = int(target_len // val)
        
        # Se for muito próximo do próximo inteiro, arredondar para cima (tolerância de 5cm)
        remainder = target_len - (num_panels * val)
        if val - remainder < 5.0 and remainder > 0: # Fix div by zero check if needed
             num_panels += 1
             
        # Se resultado for 0 (espaço menor que painel), colocar 1 pelo menos?
        if num_panels == 0 and target_len > 10.0:
            num_panels = 1
            
        print(f"[AI_DEBUG] Apply Pattern: Val={val} Target={target_len} Num={num_panels}")
        return [val] * num_panels

    def predict_layout(self, coordenadas: List[Tuple[float, float]], obstaculos: List[List[Tuple[float, float]]], intelligence_mode: int = 0) -> Optional[Dict[str, Any]]:
        """
        Prevê o melhor layout para a forma dada baseada nos vizinhos mais próximos.
        Retorna um dicionário com a configuração sugerida ou None se não houver dados suficientes.
        """
        import sys
        
        features = self.extract_features(coordenadas, obstaculos)
        print(f"[AI_DEBUG] Features extraídas: {[f'{x:.2f}' for x in features]} | Mode: {intelligence_mode}")
        
        # Carregar dados para treinar o KNN on-the-fly (Dataset deve ser pequeno no início)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Selecionar ID, timestamp + 10 features + outputs
            # Filtrar pelo modo de inteligência selecionado
            cursor.execute('''
                SELECT 
                    id, timestamp,
                    area, perimetro, aspect_ratio, convexidade, num_vertices, num_ilhas, area_ilhas_relativa, bbox_width, bbox_height, compactness, 
                    modo_calculo, linhas_verticais, linhas_horizontais, opcoes_extras, feedback_type, comentarios
                FROM training_examples
                WHERE intelligence_mode = ?
                ORDER BY id DESC
            ''', (intelligence_mode,))
            rows = cursor.fetchall()
            
            print(f"[AI_DEBUG] Total de exemplos no DB: {len(rows)}")
            if len(rows) < 1:
                return None
            
            # Mapeamento de índices agora:
            # 0: id, 1: timestamp
            # 2-11: features (10)
            # 12: modo, 13: v_lines, 14: h_lines, 15: extras
            # 16: feedback_type, 17: comentarios
            
            # Separar dataset
            pos_rows = []
            neg_rows = []
            max_id = 0
            
            # Como está ordenado DESC, o primeiro row[0] é o max_id (se houver dados)
            if rows: max_id = rows[0][0]
            
            for row in rows:
                if row[16] == 'negative':
                    neg_rows.append(row)
                else:
                    pos_rows.append(row)
            
            print(f"[AI_DEBUG] Positivos: {len(pos_rows)}, Negativos: {len(neg_rows)}, Max ID: {max_id}")
            
            print(f"[AI_DEBUG] Positivos: {len(pos_rows)}, Negativos: {len(neg_rows)}, Max ID: {max_id}")
            
            # --- INTEGRAÇÃO SMART PANNER (Regra Base) ---
            # Gerar a proposta baseada nas regras geométricas (244 / 122+Uniao)
            smart_proposal = self.smart_panner.suggest_layout(features[7], features[8], features)
            
            # Se não houver dados de treino suficientes, retorna direto a Smart Proposal
            if not pos_rows:
                print("[AI] Sem dados suficientes. Retornando Smart Proposal (Regras Base).")
                return smart_proposal


            
            # Preparar dados Positivos (Features estão nos índices 2 a 11)
            X_pos = np.array([list(row[2:12]) for row in pos_rows])
            scaler = StandardScaler()
            X_pos_scaled = scaler.fit_transform(X_pos)
            
            features_scaled = scaler.transform([features])
            
            # --- FASE 1: Construir Lista Negra (Negatives) ---
            negative_configs = []
            if neg_rows:
                X_neg = np.array([list(row[2:12]) for row in neg_rows])
                # Evitar erro se scaler foi fitado com poucos dados
                if len(pos_rows) > 0:
                   X_neg_scaled = scaler.transform(X_neg)
                else:
                   X_neg_scaled = X_neg # Fallback improvável
                
                k_neg = min(len(neg_rows), 50)
                knn_neg = NearestNeighbors(n_neighbors=k_neg, algorithm='auto')
                knn_neg.fit(X_neg_scaled)
                
                dists_neg, idxs_neg = knn_neg.kneighbors(features_scaled)
                
                print(f"[AI_DEBUG] Distâncias para negativos mais próximos: {[f'{d:.4f}' for d in dists_neg[0]]}")
                
                for i in range(k_neg):
                    dist = dists_neg[0][i]
                    if dist < 3.0: 
                        idx_real = idxs_neg[0][i]
                        row = neg_rows[idx_real]
                        try:
                            config = {
                                "modo": row[12],
                                "linhas_v": json.loads(row[13]),
                                "linhas_h": json.loads(row[14])
                            }
                            negative_configs.append(config)
                            print(f"[AI_DEBUG] Negativo ID={row[0]} blacklistado (Dist {dist:.4f})")
                        except:
                            pass

            # --- FASE 2: Buscar Candidatos (Positivos) com PESO DE RECÊNCIA ---
            k_pos = min(len(pos_rows), 20)
            knn_pos = NearestNeighbors(n_neighbors=k_pos, algorithm='auto')
            knn_pos.fit(X_pos_scaled)
            
            dists_pos, idxs_pos = knn_pos.kneighbors(features_scaled)
            
            best_positive_row = None
            best_score = float('inf') # Menor score é melhor (score base é distância)
            
            print("[AI_DEBUG] Analisando candidatos:")
            
            for i in range(k_pos):
                dist = dists_pos[0][i]
                idx_real = idxs_pos[0][i]
                row = pos_rows[idx_real]
                row_id = row[0]
                comentario = row[17]
                
                # HEURÍSTICA DE PESO:
                recency_factor = 1.0
                is_recent = (max_id - row_id) <= 2 # Últimos 2 inputs globais (muito recente)
                has_comment = bool(comentario and len(comentario) > 3)
                
                effective_score = dist
                
                # LÓGICA "LAST-SHOT" (Efeito Instantâneo)
                # Se for EXTREMAMENTE recente e a distância for aceitável, forçar vitória.
                # Distance < 1.0 em dados normalizados é um match razoável.
                if is_recent and dist < 1.0:
                    effective_score = -100.0 # Prioridade Absoluta (negativo para ganhar de tudo)
                    print(f"   -> ID={row_id} é LAST-SHOT (Prioridade Absoluta)")
                elif is_recent:
                     recency_factor *= 0.1 # Bonus forte se for recente mas não idêntico
                     effective_score *= recency_factor
                     print(f"   -> ID={row_id} é Recente (Bonus x10)")
                
                # Bônus para comentários
                if has_comment and effective_score > 0:
                    recency_factor *= 0.5 # Divide por 2 se tem comentário
                    effective_score *= 0.5
                    print(f"   -> ID={row_id} tem COMENTÁRIO (Bonus x2)")
                
                config_candidate = {
                    "modo": row[12],
                    "linhas_v": json.loads(row[13]),
                    "linhas_h": json.loads(row[14])
                }
                
                # Check Blacklist
                is_bad = False
                for bad_config in negative_configs:
                    if self.is_similar_config(config_candidate, bad_config):
                         is_bad = True
                         break
                
                if not is_bad:
                    status = "Líder" if effective_score < best_score else "Ignorado"
                    print(f"   -> ID={row_id} | Dist Real: {dist:.4f} | Score: {effective_score:.4f} | {status}")
                    
                    if effective_score < best_score:
                        best_positive_row = row
                        best_score = effective_score
                else:
                    print(f"   -> [X] Candidato ID={row_id} REJEITADO: Similar a um Erro (Blacklist)")
            
            sys.stdout.flush()
            
            if not best_positive_row:
                print("[AI_DEBUG] Nenhum candidato positivo aceito pelo KNN. Usando Smart Rule.")
                result = smart_proposal
            else:
                winner_row = best_positive_row
                best_dist = best_score # Simplificacao: best_score é derivado da distancia
                
                # --- DECISÃO: MEMÓRIA VS SMART RULE ---
                # Se a memória for muito forte (distancia pequena, < 0.5 em features normalizadas),
                # significa que é uma laje quase idêntica a uma conhecida (ex: L-Shape treinado).
                # Caso contrário (distancia grande), é uma laje "nova" -> Confiar nas regras de engenharia.
                
                # Relaxando limites para favorecer a Memória (Exemplos Salvos)
                # O usuário prefere que a IA copie um exemplo próximo do que tente "pensar" do zero.
                DISTANCIA_LIMITE_SMART = 2.0 # Aumentado de 0.5 para 2.0 (Match Razoável)
                
                # Formas complexas (não retangulares) merecem mais tolerância de memória
                is_complex = features[3] < 0.95 or features[4] > 4
                if is_complex:
                    DISTANCIA_LIMITE_SMART = 3.0 # Mais tolerante para formas complexas
                
                # Se usar feature de confiança no futuro, pode ser útil
                print(f"[AI_DEBUG] VENCEDOR KNN: ID={winner_row[0]} (Score {best_score:.4f}). Limite={DISTANCIA_LIMITE_SMART}")

                if best_score < DISTANCIA_LIMITE_SMART:
                    print(f"[AI] Memória Venceu (Score {best_score:.4f} < {DISTANCIA_LIMITE_SMART}). Usando caso # {winner_row[0]}")
                    
                    result = {
                        "confianca": float(1.0 / (1.0 + best_score)),
                        "modo_calculo": winner_row[12],
                        "linhas_verticais": json.loads(winner_row[13]),
                        "linhas_horizontais": json.loads(winner_row[14]),
                        "opcoes_extras": json.loads(winner_row[15])
                    }
                    
                    # --- APPLY KNN PATTERNS (Geometric Match) ---
                    try:
                        learned_width = winner_row[9]
                        learned_height = winner_row[10]
                        current_width = features[7]
                        current_height = features[8]
                        
                        if learned_width > 0 and learned_height > 0:
                            pat_v = self._detect_pattern(result["linhas_verticais"], learned_width)
                            if pat_v["type"] == "REPEAT":
                                 print(f"[AI_DEBUG] KNN Pattern V: {pat_v}")
                                 result["linhas_verticais"] = self._apply_pattern(pat_v, current_width)
                                 
                            pat_h = self._detect_pattern(result["linhas_horizontais"], learned_height)
                            if pat_h["type"] == "REPEAT":
                                 print(f"[AI_DEBUG] KNN Pattern H: {pat_h}")
                                 result["linhas_horizontais"] = self._apply_pattern(pat_h, current_height)
                    except Exception as e:
                        print(f"Erro KNN Pattern: {e}")
                        
                else:
                    print(f"[AI] Memória Fraca (Score {best_score:.4f} >= {DISTANCIA_LIMITE_SMART}). Usando Smart Rule (Engenharia).")
                    result = smart_proposal
                    if "opcoes_extras" not in result: result["opcoes_extras"] = {}
                    result["opcoes_extras"]["source"] = "SmartRule_Logic"


            # --- APLICAÇÃO DE REGRAS GLOBAIS (COMENTARIOS) ---
            # Aplicar regras aprendidas e persistidas (sobrepõem o exemplo histórico)
            try:
                global_rules = self.get_all_rules(rule_type='line', mode=intelligence_mode)
                if global_rules:
                    print(f"[AI_DEBUG] Aplicando {len(global_rules)} regras globais...")
                    # Inverter para obter ordem Cronológica (Antigo -> Novo)
                    # get_all_rules retorna DESC (Novo -> Antigo). Queremos aplicar o Novo POR ÚLTIMO.
                    # Então precisamos inverter a lista (agora: Antigo -> Novo)
                    for rule_id, rule_content in reversed(global_rules):
                         print(f"   -> Regra Global #{rule_id}: {rule_content}")
                         self._apply_heuristic_from_comment(result, rule_content, features)
            except Exception as e:
                print(f"Erro ao aplicar regras globais: {e}")

            return result
            
        except Exception as e:
            print(f"Erro na predição: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            conn.close()

    def is_similar_config(self, config_a: Dict, config_b: Dict, tolerance: float = 5.0) -> bool:
        """
        Verifica se duas configurações são funcionalmente similares (Fuzzy Match).
        """
        if config_a['modo'] != config_b['modo']:
            return False
            
        # Converter para float e arredondar para evitar diferenças de precisão (json vs float)
        def to_floats(lines):
            def get_v(x): return x["value"] if isinstance(x, dict) else float(x)
            return sorted([round(get_v(x), 2) for x in lines])
            
        lines_v_a = to_floats(config_a['linhas_v'])
        lines_v_b = to_floats(config_b['linhas_v'])
        
        lines_h_a = to_floats(config_a['linhas_h'])
        lines_h_b = to_floats(config_b['linhas_h'])
        
        if len(lines_v_a) != len(lines_v_b) or len(lines_h_a) != len(lines_h_b):
            return False
            
        # Comparar linhas verticais
        for da, db in zip(lines_v_a, lines_v_b):
            if abs(da - db) > tolerance:
                return False
                
        # Comparar linhas horizontais
        for da, db in zip(lines_h_a, lines_h_b):
            if abs(da - db) > tolerance:
                return False
                
        return True

    def add_rule(self, content: str, intelligence_mode: int = 0) -> bool:
        """Adiciona uma nova regra de interpretação"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Evitar duplicatas exatas
            cursor.execute('SELECT id FROM interpretation_rules WHERE content = ? AND intelligence_mode = ?', (content, intelligence_mode))
            if cursor.fetchone():
                print(f"[AI] Regra já existe, ignorando: {content}")
                return True
                
            cursor.execute('INSERT INTO interpretation_rules (content, intelligence_mode) VALUES (?, ?)', (content, intelligence_mode))
            conn.commit()
            print(f"[AI] Nova regra global aprendida: {content}")
            return True
        except Exception as e:
            print(f"Erro ao adicionar regra: {e}")
            return False
        finally:
            conn.close()

    def _apply_heuristic_from_comment(self, result: Dict, comment: str, features: List[float]):
        """
        Aplica regras baseadas em comentários (textuais ou JSON LLM).
        """
        if not comment or not isinstance(comment, str):
            return

        comment = comment.lower().strip()
        
        # --- TENTATIVA DE PARSE JSON (REGRAS LLM) ---
        if comment.startswith("{") and "condition" in comment:
            try:
                import json
                rule = json.loads(comment)
                # Variáveis disponíveis para o eval seguro
                # features: [num_pts, area, perim, aspect_ratio, convexity, rectangularity, solidity, bbox_w, bbox_h, num_obstacles]
                
                # Segurança: Se features for None, usar vetor vazio
                f = features if features is not None else [0.0] * 10
                
                context = {
                    "width": f[7] if len(f) > 7 else 0.0,
                    "height": f[8] if len(f) > 8 else 0.0,
                    "area": f[1] if len(f) > 1 else 0.0,
                    "num_obstacles": f[9] if len(f) > 9 else 0.0
                }
                
                # Avalia Condição (Safe Eval)
                # Permitido apenas operações matemáticas básicas e comparações
                condition = rule.get("condition", "False")
                # Sanitização básica (remover imports etc)
                if "__" in condition or "import" in condition:
                     print(f"[AI SECURITY] Regra ignorada por segurança: {condition}")
                     return

                if eval(condition, {"__builtins__": None}, context):
                    print(f"[AI] Regra LLM Ativada: {rule.get('rule_name')} -> {rule.get('action')}")
                    action = rule.get("action", "").lower()
                    
                    # Interpretador de Ações (Mapeia string para código)
                    # Ex: "force_panel_80", "use_single_panel", etc.
                    if "force_mode_vertical" in action:
                         print("[AI] Ação LLM: Forçar Modo Vertical (1)")
                         result['modo_calculo'] = 0 # 0 = Vertical/M1
                         # Limpar linhas para forçar recalculo na UI (ou tentar rotacionar?)
                         # Seguro: Limpar
                         result['linhas_verticais'] = []
                         result['linhas_horizontais'] = []
                         
                    elif "force_mode_horizontal" in action:
                         print("[AI] Ação LLM: Forçar Modo Horizontal (2)")
                         result['modo_calculo'] = 1 # 1 = Horizontal/M2
                         result['linhas_verticais'] = []
                         result['linhas_horizontais'] = []

                    elif "prefer_panel_244" in action:
                         print("[AI] Ação LLM: Preferir Painel 244")
                         result['opcoes_extras']['prefer_panel_244'] = True
                         
                    elif "force_gap_logic" in action:
                         print("[AI] Ação LLM: Forçar Lógica de GAP (SmallSide)")
                         result['opcoes_extras']['force_gap_logic'] = True
                         # Pequenas lajes (< 200cm)
                         width = features[7]
                         height = features[8]
                         # Estratégia: 1 painel (122 ou 60) + GAP 20 + Resto
                         modo = result.get('modo_calculo', 0)
                         dim_alvo = width if modo == 0 else height
                         
                         if dim_alvo > 0:
                             panel = 122.0 if dim_alvo >= 142.0 else 60.0
                             gap = 20.0
                             resto = dim_alvo - panel - gap
                             lines = [panel, gap]
                             if resto > 5.0: lines.append(resto)
                             
                             if modo == 0: result['linhas_verticais'] = lines
                             else: result['linhas_horizontais'] = lines
                             print(f"[AI] SmallSide Aplicado: {lines}")

                    elif "align_to_deformity" in action:
                         print("[AI] Ação LLM: Alinhar à Deformidade")
                         result['opcoes_extras']['align_to_deformity'] = True

                    elif "custom_start_101" in action:
                         print("[AI] Ação LLM: Iniciar com 101")
                         result['opcoes_extras']['start_offset'] = 101.0
                        
            except Exception as e:
                print(f"[AI] Erro ao executar regra JSON: {e}")
            return

        # --- REGRAS TEXTUAIS ANTIGAS ---
        self._apply_text_heuristic(result, comment, features)
        
    def _apply_text_heuristic(self, result: Dict, comment: str, features: List[float]):
        """
        Aplica ajustes no resultado baseada em palavras-chave no comentário.
        Permite que o usuário 'programe' o comportamento via texto.
        """
        if not comment:
            return
            
        import re
        c = comment.lower()
        print(f"[AI_DEBUG] Processando heurísticas do comentário: '{c}'")
        
        # Heurística 1: "Forçar espaçamento X" (ex: "distancia 60", "espaço 122")
        # Regex para encontrar número após palavras chave
        match_dist = re.search(r'(?:distancia|espaco|padrao|usar)\s*(\d+(?:[.,]\d+)?)', c)
        if match_dist:
            val = float(match_dist.group(1).replace(',', '.'))
            print(f"[AI_DEBUG] HEURISTICA: Forçando distanciamento padrão de {val}")
            
            # Recalcular linhas baseadas no bbox (width/height)
            width = features[7]
            height = features[8]
            
            # Recriar linhas verticais
            if width > 0:
                num_v = int(width / val)
                rem_v = width - (num_v * val)
                # Distribuir (exemplo simplificado: tudo val, sobra no final)
                result['linhas_verticais'] = [val] * num_v
                if rem_v > 0.1: result['linhas_verticais'].append(rem_v)
                
            # Recriar linhas horizontais
            if height > 0:
                num_h = int(height / val)
                rem_h = height - (num_h * val)
                result['linhas_horizontais'] = [val] * num_h
                if rem_h > 0.1: result['linhas_horizontais'].append(rem_h)

        # Heurística 2: "Somente Borda" ou "Sem Uniões"
        if "somente borda" in c or "sem uniao" in c:
             print("[AI_DEBUG] HEURISTICA: Forçando unioes_bordes = False")
             result['opcoes_extras']['unioes_bordes'] = False

        # Heurística 3: "Com Uniões"
        if "com uniao" in c or "usar uniao" in c:
             print("[AI_DEBUG] HEURISTICA: Forçando unioes_bordes = True")
             result['opcoes_extras']['unioes_bordes'] = True
             
        # Heurística 4: Direção das Uniões (Vertical vs Horizontal)
        # M1 (0) = Verticais com União (Predominância de linhas verticais preenchendo)
        # M2 (1) = Horizontais com União (Predominância de linhas horizontais)
        
        target_mode = None
        
        # Regex Patterns
        # Padrão Condicional: "Se vertical maior horizontal..."
        # Captura variações: "vertical > horizontal", "altura maior largura", "comprimento vertical excede"
        pattern_cond = r'(?:vertical|altura|y).*(?:maior|mais|grande|excede|>).*(?:horizontal|largura|x)'
        
        # Padrão Explícito Vertical
        pattern_vert = r'(?:usar|fazer|colocar|unioes|modo)\s*(?:vertical|verticais|pe|1)'
        
        # Padrão Explícito Horizontal
        pattern_horiz = r'(?:usar|fazer|colocar|unioes|modo)\s*(?:horizontal|horizontais|deitado|2)'

        # Checagem Condicional
        if re.search(pattern_cond, c):
            height = features[8] # bbox_height
            width = features[7]  # bbox_width
            ratio = height / width if width > 0 else 1.0
            
            print(f"[AI_DEBUG] HEURISTICA: Detectada condição condicional (H={height:.1f}, W={width:.1f})")
            
            if height > width:
                 print(f"[AI_DEBUG] -> Altura > Largura. Forçando Modo 1 (Verticais).")
                 target_mode = 0
            else:
                 print(f"[AI_DEBUG] -> Largura >= Altura. Forçando Modo 2 (Horizontais).")
                 target_mode = 1
                 
        # Checagem Explícita (sobrescreve condicional se específico)
        elif re.search(pattern_vert, c):
             print("[AI_DEBUG] HEURISTICA: Comando explícito para VERTICAL (Modo 1).")
             target_mode = 0
             
        elif re.search(pattern_horiz, c):
             print("[AI_DEBUG] HEURISTICA: Comando explícito para HORIZONTAL (Modo 2).")
             target_mode = 1
             
        # Heurística 5: "Corte em X" ou "União em X" (Forçar Splits)
        # Ex: "corte em 188", "uniao 200", "fatia 150"
        match_cut = re.search(r'(?:corte|fatia|uniao|divisao|linha)\s*(?:horizontal|vertical)?\s*(?:em|de|no)?\s*(\d+(?:[.,]\d+)?)', c)
        if match_cut:
            try:
                val = float(match_cut.group(1).replace(',', '.'))
                print(f"[AI_DEBUG] HEURISTICA: Forçando CORTE/UNIÃO em {val}")
                
                # Determinar modo para saber onde aplicar (se não definido, assume o atual)
                mode_to_use = target_mode if target_mode is not None else result.get('modo_calculo', 0)
                
                # Modo 0 (Vertical) -> Cortes são Linhas Horizontais
                if mode_to_use == 0:
                    current_lines = result.get('linhas_horizontais', [])
                    def get_v(x): return x["value"] if isinstance(x, dict) else float(x)
                    # Evitar duplicatas próximas
                    if not any(abs(get_v(x) - val) < 2.0 for x in current_lines):
                        current_lines.append(val)
                        current_lines.sort(key=get_v)
                        result['linhas_horizontais'] = current_lines
                        print(f"[AI_DEBUG] Adicionado corte horizontal em {val}")
                        
                # Modo 1 (Horizontal) -> Cortes são Linhas Verticais
                else:
                    current_lines = result.get('linhas_verticais', [])
                    def get_v(x): return x["value"] if isinstance(x, dict) else float(x)
                    if not any(abs(get_v(x) - val) < 2.0 for x in current_lines):
                        current_lines.append(val)
                        current_lines.sort(key=get_v)
                        result['linhas_verticais'] = current_lines
                        print(f"[AI_DEBUG] Adicionado corte vertical em {val}")
            except Exception as e:
                print(f"[AI_DEBUG] Erro ao aplicar heurística de corte: {e}")

        # Heurística 6: Regra de 182cm (Distância máxima entre uniões)
        if "182" in c and ("uniao" in c or "distancia" in c):
            print("[AI_DEBUG] HEURISTICA: Aplicando regra de distância máxima de 182cm para uniões.")
            result['opcoes_extras']['max_union_dist'] = 182.0

        # Heurística 7: Painel 244 (Eixos longos)
        if "244" in c or "padrao longo" in c:
            print("[AI_DEBUG] HEURISTICA: Preferindo painel de 244cm.")
            result['opcoes_extras']['prefer_panel_244'] = True

        # Heurística 8: Início com 101 (L8 Pattern)
        if "101" in c and "iniciar" in c:
             print("[AI_DEBUG] HEURISTICA: Forçando início com 101cm.")
             result['opcoes_extras']['start_offset'] = 101.0

        # Aplicar Mudança de Modo
        if target_mode is not None:
            current_mode = result.get('modo_calculo', -1)
            
            if current_mode != target_mode:
                print(f"[AI_DEBUG] APLICANDO MUDANÇA: Modo {current_mode} -> {target_mode}")
                result['modo_calculo'] = target_mode
                
                # CRÍTICO: Se mudamos o modo via heurística, as linhas do vizinho (que eram do outro modo)
                # provavelmente são inválidas ou confusas.
                # É mais seguro limpar as linhas sugeridas e deixar o algoritmo de preenchimento padrão da UI atuar
                # ou tentar gerar linhas básicas.
                # Para garantir que a UI recalcule:
                # Vamos tentar 'transpor' ou apenas limpar. Limpar é mais seguro para forçar recálculo.
                print("[AI_DEBUG] Limpando linhas herdadas para forçar recálculo no novo modo.")
                result['linhas_verticais'] = []
                result['linhas_horizontais'] = []
                
                # Dica: Se a UI receber listas vazias, ela pode manter as anteriores ou não desenhar nada.
                # Idealmente, o 'canvas_widget' deveria recalcular se receber vazio.
                # Mas vamos enviar um sinalizador se possível? Não, estrutura fixa.
                # Vamos adicionar uma flag em 'opcoes_extras' para forçar recálculo?
                result['opcoes_extras']['forcar_recalculo'] = True

    def get_all_rules(self, rule_type: str = 'line', mode: int = 0) -> List[Tuple[int, str]]:
        """Retorna todas as regras para um tipo e modo específicos"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id, content FROM interpretation_rules WHERE rule_type = ? AND intelligence_mode = ? ORDER BY created_at DESC', (rule_type, mode))
            rules = cursor.fetchall()
            conn.close()
            return rules
        except Exception as e:
            print(f"Erro ao buscar regras: {e}")
            return []

    def add_rule(self, content: str, rule_type: str = 'line', mode: int = 0):
        """Adiciona uma nova regra ou insight"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('INSERT INTO interpretation_rules (content, rule_type, intelligence_mode) VALUES (?, ?, ?)', (content, rule_type, mode))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Erro ao adicionar regra: {e}")
        
    def apply_dimension_rules(self, candidates: List[Dict[str, Any]], mode: int = 0):
        """Aplica regras textuais globais sobre a lista de cotas candidatas"""
        rules = self.get_all_rules(rule_type='dimension', mode=mode)
        if not rules:
            return

        import re
        for _, content in reversed(rules):
            c = content.lower()
            
            # Regra: "ocultar menores que X"
            match_hide = re.search(r'(?:ocultar|esconder|remover|excluir).*?(?:menores|baixo|inf).*?(\d+(?:[.,]\d+)?)', c)
            if match_hide:
                val_limit = float(match_hide.group(1).replace(',', '.'))
                print(f"[AI_RULES] Aplicando: Ocultar cotas < {val_limit}")
                for cand in candidates:
                    try:
                        val = float(str(cand.get('value', 0)).replace(',', '.'))
                        if val < val_limit:
                            cand['keep_by_rule'] = False
                    except:
                        pass

            # Regra: "manter apenas maiores que X"
            match_keep = re.search(r'(?:manter|exibir|mostrar).*?(?:maiores|cima|sup).*?(\d+(?:[.,]\d+)?)', c)
            if match_keep:
                val_limit = float(match_keep.group(1).replace(',', '.'))
                print(f"[AI_RULES] Aplicando: Manter apenas cotas > {val_limit}")
                for cand in candidates:
                    try:
                        val = float(str(cand.get('value', 0)).replace(',', '.'))
                        if val < val_limit:
                            cand['keep_by_rule'] = False
                    except:
                        pass

    def _get_recent_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Helper para buscar histórico recente de exemplos de treinamento.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(f'''
                SELECT 
                    bbox_width, bbox_height, linhas_verticais, linhas_horizontais, comentarios, feedback_type
                FROM training_examples
                ORDER BY timestamp DESC
                LIMIT {limit}
            ''')
            rows = cursor.fetchall()
            
            history_data = []
            for row in rows:
                try:
                    w = row[0]
                    h = row[1]
                    lines_v = json.loads(row[2])
                    lines_h = json.loads(row[3])
                    comment = row[4]
                    
                    # Filtrar linhas vazias para não poluir
                    if not lines_v and not lines_h:
                        continue
                        
                    history_data.append({
                        "width": w,
                        "height": h,
                        "lines_v": lines_v,
                        "lines_h": lines_h,
                        "comment": comment,
                        "type": row[5] # feedback_type
                    })
                except json.JSONDecodeError as e:
                    logging.warning(f"Erro ao decodificar JSON do histórico: {e} na linha {row}")
                    continue
            return history_data
        finally:
            conn.close()

    def extract_patterns_with_llm(self) -> List[Dict[str, Any]]:
        """
        Extrai padrões usando LLM (Gemini) baseando-se no histórico recente.
        """
        print("[AI] Iniciando extração de aprendizado via LLM...")
        
        # 1. Buscar histórico recente (Limit 50 para economizar tokens e ser relevante)
        history_data = self._get_recent_history(limit=50)
        
        if not history_data:
            return [{"error": "Sem dados de treino suficientes."}]
                
        # 2. Chamar Serviço de IA (Groq Principal -> Ollama Fallback)
        try:
            insights = self.ai_service.analyze_layout_history(history_data)
            
            # Verificar se houve erro na resposta do Groq
            if isinstance(insights, list) and len(insights) == 1 and "error" in insights[0]:
                print(f"[AI] Groq falhou ({insights[0]['error']}). Tentando fallback local (Ollama)...")
                if not self.ollama_service:
                     from laje_src.services.ai.ollama_service import OllamaService
                     self.ollama_service = OllamaService()
                
                insights = self.ollama_service.analyze_layout_history(history_data)
                
            return insights
            
        except Exception as e:
            print(f"[AI] Erro no fluxo LLM: {e}")
            return [{"error": str(e)}]

    def update_rule(self, rule_id: int, content: str) -> bool:
        """Atualiza uma regra existente"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE interpretation_rules SET content = ? WHERE id = ?', (content, rule_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Erro ao atualizar regra: {e}")
            return False
        finally:
            conn.close()

    def delete_rule(self, rule_id: int) -> bool:
        """Exclui uma regra"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM interpretation_rules WHERE id = ?', (rule_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Erro ao excluir regra: {e}")
            return False
        finally:
            conn.close()
