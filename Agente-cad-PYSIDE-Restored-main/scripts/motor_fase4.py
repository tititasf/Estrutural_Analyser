"""
motor_fase4.py — Fase 4 Sincronizacao Headless
================================================
Transforma fichas simplificadas (Fase 3) para formato completo dos robos (Fase 4)
SEM PySide6, SEM UI, SEM interacao humana.

Equivalente headless dos botoes de sincronizacao do main.py:
  - sync_pillars_to_robo_pilares_action()
  - sync_beams_to_laterais_action()
  - sync_slabs_to_robo_laje_action()

Uso:
  python scripts/motor_fase4.py --obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV"
  python scripts/motor_fase4.py --obra DADOS-OBRAS/Obra_TREINO_21  # processa todos pav

Input:  Fase-3_Interpretacao_Extracao/{Pilares,Vigas,Lajes}/*.json
Output: Fase-4_Sincronizacao/{pilares_salvos.json, JSON_Pilares/, vigas_salvas.json, ...}
"""

import os
import sys
import json
import re
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("motor_fase4")


# ==============================================================================
# MODELOS STANDALONE (sem dependencia de PySide6 ou robots)
# Replicam PilarModel/Laje/VigaState com campos minimos para Fase 4
# ==============================================================================

class PilarFase4:
    """
    Modelo de Pilar para Fase 4 — campos minimos que os robos esperam.
    Replica logica de PilarModel + PilarService.distribute_face_heights()
    sem dependencia de PySide6.
    """
    def __init__(self, numero: str, nome: str, comprimento: float, largura: float,
                 altura: float, pavimento: str, nivel_chegada: float = 0.0,
                 nivel_saida: float = 0.0, modo_distribuicao: str = "NOVA"):
        self.numero = numero
        self.nome = nome
        self.comprimento = comprimento  # maior dimensao (h da ficha Fase3)
        self.largura = largura          # menor dimensao (b da ficha Fase3)
        self.altura = altura
        self.pavimento = pavimento
        self.nivel_chegada = nivel_chegada
        self.nivel_saida = nivel_saida
        self.modo_distribuicao = modo_distribuicao

        # Distribuir alturas nas faces (h1-h5) — logica de PilarService
        self._distribute_face_heights(altura)
        self.grade_1 = 0.0
        self.grade_2 = 0.0
        self.grade_3 = 0.0
        self.distancia_1 = 0.0
        self.distancia_2 = 0.0

        # Parafusos (inicializar em 0)
        for i in range(1, 9):
            setattr(self, f"par_{i}_{i+1 if i < 8 else 9}", 0.0)

    def _distribute_face_heights(self, h_val: float):
        """
        Distribui a altura total nas hachuras h1-h5 (Regra Legada):
        h1 = 2.0 (se h > 2)
        h2 = 244.0 (se sobra > 244)
        h3 = 244.0 (se sobra > 244)
        h4 = 244.0 (se sobra > 244)
        h5 = Resto.
        Aplica para todas as faces A-H.
        """
        h_rest = h_val
        h1 = 2.0 if h_rest > 2.0 else h_rest
        h_rest -= h1
        h2 = 244.0 if h_rest > 244.0 else h_rest
        h_rest -= h2
        h3 = 244.0 if h_rest > 244.0 else h_rest
        h_rest -= h3
        h4 = 244.0 if h_rest > 244.0 else h_rest
        h_rest -= h4
        h5 = max(0.0, h_rest)

        for face in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
            setattr(self, f"h1_{face}", round(h1, 1))
            setattr(self, f"h2_{face}", round(h2, 1))
            setattr(self, f"h3_{face}", round(h3, 1))
            setattr(self, f"h4_{face}", round(h4, 1))
            setattr(self, f"h5_{face}", round(h5, 1))
            # larguras de face (default 0 — a UI preencheria via calculo automatico)
            setattr(self, f"larg1_{face}", 0.0)
            setattr(self, f"larg2_{face}", 0.0)
            setattr(self, f"larg3_{face}", 0.0)
            setattr(self, f"laje_{face}", 0.0)
            setattr(self, f"posicao_laje_{face}", 0.0)

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items()}
        return d


@dataclass
class PanelData:
    """6 paineis de uma viga (slot fixo)."""
    width: float = 0.0
    height1: float = 0.0
    height2: float = 0.0
    grade_h1: str = "0"
    grade_h2: str = "0"

    def to_dict(self):
        return {
            "width": self.width, "height1": self.height1,
            "height2": self.height2, "grade_h1": self.grade_h1,
            "grade_h2": self.grade_h2
        }


@dataclass
class HoleData:
    """4 furos de uma viga."""
    active: bool = False
    width: float = 0.0
    height: float = 0.0
    position: float = 0.0

    def to_dict(self):
        return {"active": self.active, "width": self.width,
                "height": self.height, "position": self.position}


@dataclass
class PillarEdge:
    active: bool = False
    width: float = 0.0
    length: float = 0.0

    def to_dict(self):
        return {"active": self.active, "width": self.width, "length": self.length}


class VigaFase4:
    """
    Modelo de Viga para Fase 4 — VigaState com lado A e B.
    Cada viga Fase 3 gera 2 fichas: {nome}_A e {nome}_B.
    """
    def __init__(self, numero: str, nome: str, floor: str, side: str,
                 total_width: float, total_height: float, comprimento: float):
        self.number = numero
        self.name = nome
        self.floor = floor
        self.side = side  # "A" ou "B"
        self.total_width = total_width    # b da ficha Fase3
        self.total_height = str(total_height)  # h da ficha (como string no VigaState)

        # Distribuir comprimento em 6 panels
        self.panels = self._distribute_panels(comprimento, total_height)
        self.holes = [HoleData() for _ in range(4)]
        self.pillar_left = PillarEdge()
        self.pillar_right = PillarEdge()
        self.sarrafo_left_id = 0
        self.sarrafo_right_id = 0

    def _distribute_panels(self, comprimento: float, altura: float) -> List[PanelData]:
        """
        Distribui comprimento em 6 slots de panels.
        Logica simples: paineis de 120cm com resto no ultimo.
        """
        panels = []
        MAX_PANEL_WIDTH = 120.0
        restante = comprimento

        for i in range(6):
            if restante <= 0:
                panels.append(PanelData())
            else:
                w = min(restante, MAX_PANEL_WIDTH)
                restante -= w
                panels.append(PanelData(
                    width=round(w, 1),
                    height1=round(altura, 1),
                    height2=round(altura, 1),
                    grade_h1="0",
                    grade_h2="0"
                ))
        return panels

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "name": self.name,
            "floor": self.floor,
            "side": self.side,
            "total_width": self.total_width,
            "total_height": self.total_height,
            "panels": [p.to_dict() for p in self.panels],
            "holes": [h.to_dict() for h in self.holes],
            "pillar_left": self.pillar_left.to_dict(),
            "pillar_right": self.pillar_right.to_dict(),
            "sarrafo_left_id": self.sarrafo_left_id,
            "sarrafo_right_id": self.sarrafo_right_id
        }


class LajeFase4:
    """
    Modelo de Laje para Fase 4.
    Calcula linhas_verticais automaticamente (100cm spacing).
    """
    def __init__(self, numero: int, nome: str, comprimento: float, largura: float,
                 pavimento: str, coordenadas: List[List[float]], area_cm2: float = 0.0,
                 modo_selecionado: int = 0):
        self.numero = numero
        self.nome = nome
        self.comprimento = comprimento
        self.largura = largura
        self.pavimento = pavimento
        self.coordenadas = coordenadas  # [[x,y], ...]
        self.area_cm2 = area_cm2 if area_cm2 > 0 else comprimento * largura
        self.modo_selecionado = modo_selecionado
        self.linhas_verticais = self._calc_linhas_verticais(comprimento)
        self.linhas_horizontais = []
        self.obstaculos = []
        self.unioes_nos_bordes = False
        self.observacoes = ""

    def _calc_linhas_verticais(self, comprimento: float) -> List[dict]:
        """
        Calcula cortes verticais a cada 100cm.
        is_union = True quando value <= 30cm (marco nao secciona).
        """
        linhas = []
        pos = 0.0
        STEP = 100.0
        UNION_THRESHOLD = 30.0

        while pos < comprimento:
            pos += STEP
            valor = min(pos, comprimento)
            linhas.append({
                "value": round(valor, 1),
                "is_union": valor <= UNION_THRESHOLD
            })
            if valor >= comprimento:
                break

        return linhas

    def to_dict(self) -> dict:
        return {
            "numero": self.numero,
            "nome": self.nome,
            "comprimento": self.comprimento,
            "largura": self.largura,
            "pavimento": self.pavimento,
            "coordenadas": self.coordenadas,
            "area_cm2": self.area_cm2,
            "linhas_verticais": self.linhas_verticais,
            "linhas_horizontais": self.linhas_horizontais,
            "obstaculos": self.obstaculos,
            "modo_selecionado": self.modo_selecionado,
            "unioes_nos_bordes": self.unioes_nos_bordes,
            "observacoes": self.observacoes
        }


# ==============================================================================
# ENGINE DE TRANSFORMACAO
# ==============================================================================

class MotorFase4:
    """
    Engine headless de sincronizacao Fase 3 -> Fase 4.
    Replica logica dos botoes sync do main.py sem PySide6.
    """

    def __init__(self, obra_path: str, pavimento: Optional[str] = None,
                 nivel_chegada: float = 0.0, nivel_saida: float = 280.0):
        self.obra_path = Path(obra_path)
        self.pavimento = pavimento
        self.nivel_chegada = nivel_chegada
        self.nivel_saida = nivel_saida
        self.altura_padrao = abs(nivel_saida - nivel_chegada) or 280.0

        # Detectar nome da obra
        self.obra_nome = self.obra_path.name

        # Paths de input (Fase 3)
        self.fase3_path = self.obra_path / "Fase-3_Interpretacao_Extracao"

        # Paths de output (Fase 4)
        self.fase4_path = self.obra_path / "Fase-4_Sincronizacao"
        self.fase4_path.mkdir(parents=True, exist_ok=True)

        (self.fase4_path / "JSON_Pilares").mkdir(exist_ok=True)
        (self.fase4_path / "JSON_Vigas_Laterais").mkdir(exist_ok=True)
        (self.fase4_path / "JSON_Vigas_Fundo").mkdir(exist_ok=True)
        (self.fase4_path / "JSON_Lajes").mkdir(exist_ok=True)

        self.stats = {"pilares": 0, "vigas": 0, "lajes": 0, "errors": 0}

    # --------------------------------------------------------------------------
    # PILARES
    # --------------------------------------------------------------------------

    def process_pilares(self) -> Dict[str, Any]:
        """Ler fichas Fase3, transformar, salvar Fase4."""
        fichas = self._load_fase3_fichas("Pilares", "pilares.json")
        if not fichas:
            log.warning("Sem fichas de pilares para processar.")
            return {}

        pilares_salvos = {}
        pav = self.pavimento or "Pavimento"

        for nome, dados in fichas.items():
            if nome.startswith("_"):
                continue  # Pular _meta
            try:
                b = float(dados.get("b", 0))
                h = float(dados.get("h", 0))
                altura = float(dados.get("altura", self.altura_padrao))

                if b <= 0 or h <= 0:
                    log.warning(f"Pilar {nome}: dimensoes invalidas (b={b}, h={h}). Pular.")
                    continue

                # b=largura (menor), h=comprimento (maior) — convencao do PilarModel
                comprimento = max(b, h)
                largura = min(b, h)

                # Extrair numero
                nums = re.findall(r"\d+", nome)
                numero = nums[0] if nums else "0"

                pilar = PilarFase4(
                    numero=numero,
                    nome=nome,
                    comprimento=comprimento,
                    largura=largura,
                    altura=altura,
                    pavimento=pav,
                    nivel_chegada=self.nivel_chegada,
                    nivel_saida=self.nivel_saida or altura,
                    modo_distribuicao="NOVA"
                )

                pilar_dict = pilar.to_dict()
                pilares_salvos[nome] = pilar_dict

                # Salvar JSON individual
                out_path = self.fase4_path / "JSON_Pilares" / f"{nome}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(pilar_dict, f, ensure_ascii=False, indent=2)

                self.stats["pilares"] += 1
                log.info(f"  ✅ Pilar {nome}: {comprimento}x{largura}cm, h={altura}cm")

            except Exception as e:
                log.error(f"  ❌ Pilar {nome}: {e}")
                self.stats["errors"] += 1

        # Salvar pilares_salvos.json (formato simplificado para compatibilidade)
        salvos_path = self.fase4_path / "pilares_salvos.json"
        simplified = {k: {"b": v.get("largura", 0), "h": v.get("comprimento", 0),
                          "altura": v.get("altura", 0)}
                      for k, v in pilares_salvos.items()}
        with open(salvos_path, "w", encoding="utf-8") as f:
            json.dump(simplified, f, ensure_ascii=False, indent=2)

        log.info(f"Pilares: {self.stats['pilares']} processados -> {salvos_path}")
        return pilares_salvos

    # --------------------------------------------------------------------------
    # VIGAS
    # --------------------------------------------------------------------------

    def process_vigas(self) -> Dict[str, Any]:
        """Cada viga Fase3 gera 2 fichas: lado A e lado B."""
        fichas = self._load_fase3_fichas("Vigas", "vigas.json")
        if not fichas:
            log.warning("Sem fichas de vigas para processar.")
            return {}

        vigas_salvos = {}
        pav = self.pavimento or "Pavimento"

        for nome, dados in fichas.items():
            if nome.startswith("_"):
                continue
            try:
                b = float(dados.get("b", 0))
                h = float(dados.get("h", 0))
                comprimento = float(dados.get("comprimento", 0))

                if b <= 0 or comprimento <= 0:
                    log.warning(f"Viga {nome}: dimensoes invalidas. Pular.")
                    continue

                nums = re.findall(r"\d+", nome)
                numero = nums[0] if nums else "0"

                # Gerar lado A e lado B
                for side in ["A", "B"]:
                    nome_side = f"{nome}_{side}"
                    viga = VigaFase4(
                        numero=numero,
                        nome=nome_side,
                        floor=pav,
                        side=side,
                        total_width=b,
                        total_height=h,
                        comprimento=comprimento
                    )
                    viga_dict = viga.to_dict()
                    vigas_salvos[nome_side] = viga_dict

                    # Salvar JSON individual em JSON_Vigas_Laterais
                    out_path = self.fase4_path / "JSON_Vigas_Laterais" / f"{nome_side}.json"
                    with open(out_path, "w", encoding="utf-8") as f:
                        json.dump(viga_dict, f, ensure_ascii=False, indent=2)

                # Salvar fundo (simplificado - mesmo que lado A mas em JSON_Vigas_Fundo)
                fundo_dict = vigas_salvos[f"{nome}_A"].copy()
                fundo_path = self.fase4_path / "JSON_Vigas_Fundo" / f"{nome}_fundo.json"
                with open(fundo_path, "w", encoding="utf-8") as f:
                    json.dump(fundo_dict, f, ensure_ascii=False, indent=2)

                self.stats["vigas"] += 1
                log.info(f"  ✅ Viga {nome}: b={b}cm, h={h}cm, L={comprimento}cm -> A+B")

            except Exception as e:
                log.error(f"  ❌ Viga {nome}: {e}")
                self.stats["errors"] += 1

        # Salvar vigas_salvas.json
        salvos_path = self.fase4_path / "vigas_salvas.json"
        simplified = {}
        for nome_orig, dados in fichas.items():
            if not nome_orig.startswith("_"):
                simplified[nome_orig] = {
                    "b": dados.get("b", 0), "h": dados.get("h", 0),
                    "comprimento": dados.get("comprimento", 0)
                }
        with open(salvos_path, "w", encoding="utf-8") as f:
            json.dump(simplified, f, ensure_ascii=False, indent=2)

        log.info(f"Vigas: {self.stats['vigas']} processadas -> {salvos_path}")
        return vigas_salvos

    # --------------------------------------------------------------------------
    # LAJES
    # --------------------------------------------------------------------------

    def process_lajes(self) -> Dict[str, Any]:
        """Transformar fichas de laje para formato Laje dataclass."""
        fichas = self._load_fase3_fichas("Lajes", "lajes.json")
        if not fichas:
            log.warning("Sem fichas de lajes para processar.")
            return {}

        lajes_salvos = {}
        pav = self.pavimento or "Pavimento"

        for nome, dados in fichas.items():
            if nome.startswith("_"):
                continue
            try:
                comprimento = float(dados.get("comprimento", 0))
                largura = float(dados.get("largura", 0))
                area_cm2 = float(dados.get("area_cm2", comprimento * largura))
                coordenadas = dados.get("coordenadas", [])

                if comprimento <= 0 or largura <= 0:
                    log.warning(f"Laje {nome}: dimensoes invalidas. Pular.")
                    continue

                # Gerar coordenadas padrao se nao existirem
                if not coordenadas:
                    coordenadas = [
                        [0.0, 0.0], [comprimento, 0.0],
                        [comprimento, largura], [0.0, largura], [0.0, 0.0]
                    ]

                nums = re.findall(r"\d+", nome)
                numero = int(nums[0]) if nums else 0

                laje = LajeFase4(
                    numero=numero,
                    nome=nome,
                    comprimento=comprimento,
                    largura=largura,
                    pavimento=pav,
                    coordenadas=coordenadas,
                    area_cm2=area_cm2,
                    modo_selecionado=dados.get("modo_selecionado", 0)
                )

                laje_dict = laje.to_dict()
                lajes_salvos[nome] = laje_dict

                # Salvar JSON individual
                out_path = self.fase4_path / "JSON_Lajes" / f"{nome}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(laje_dict, f, ensure_ascii=False, indent=2)

                self.stats["lajes"] += 1
                log.info(f"  ✅ Laje {nome}: {comprimento}x{largura}cm, {len(laje.linhas_verticais)} cortes")

            except Exception as e:
                log.error(f"  ❌ Laje {nome}: {e}")
                self.stats["errors"] += 1

        # Salvar lajes_salvas.json
        salvos_path = self.fase4_path / "lajes_salvas.json"
        simplified = {}
        for nome_orig, dados in fichas.items():
            if not nome_orig.startswith("_"):
                simplified[nome_orig] = {
                    "comprimento": dados.get("comprimento", 0),
                    "largura": dados.get("largura", 0),
                    "area_cm2": dados.get("area_cm2", 0)
                }
        with open(salvos_path, "w", encoding="utf-8") as f:
            json.dump(simplified, f, ensure_ascii=False, indent=2)

        log.info(f"Lajes: {self.stats['lajes']} processadas -> {salvos_path}")
        return lajes_salvos

    # --------------------------------------------------------------------------
    # HELPERS
    # --------------------------------------------------------------------------

    def _load_fase3_fichas(self, tipo: str, filename: str) -> Dict[str, Any]:
        """Carregar fichas da Fase 3. Tenta paths alternatives."""
        candidates = [
            self.fase3_path / tipo / filename,
            self.fase3_path / f"Dados_Interpretacao_{tipo}" / filename,
            self.fase3_path / filename.replace(".json", f"_{tipo.lower()}.json"),
        ]
        for path in candidates:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                log.info(f"Carregado: {path} ({len(data)} itens)")
                return data
        log.warning(f"Fichas de {tipo} nao encontradas em {self.fase3_path}")
        return {}

    def run(self):
        """Executar pipeline completo."""
        log.info(f"=== motor_fase4.py | Obra: {self.obra_nome} | Pav: {self.pavimento or 'Todos'} ===")

        self.process_pilares()
        self.process_vigas()
        self.process_lajes()

        log.info(f"=== RESULTADO: {self.stats['pilares']} pilares, {self.stats['vigas']} vigas, {self.stats['lajes']} lajes | {self.stats['errors']} erros ===")

        # Salvar relatorio
        relatorio = {
            "obra": self.obra_nome,
            "pavimento": self.pavimento,
            "stats": self.stats,
            "output_path": str(self.fase4_path)
        }
        relatorio_path = self.fase4_path / "motor_fase4_relatorio.json"
        with open(relatorio_path, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, ensure_ascii=False, indent=2)

        return self.stats


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="motor_fase4 — Fase 4 Sincronizacao Headless")
    parser.add_argument("--obra", required=True, help="Path da obra (ex: DADOS-OBRAS/Obra_TREINO_21)")
    parser.add_argument("--pavimento", default=None, help="Nome do pavimento (ex: '12 PAV'). Se omitido: processa todos.")
    parser.add_argument("--nivel-chegada", type=float, default=0.0, help="Nivel de chegada em cm (default: 0)")
    parser.add_argument("--nivel-saida", type=float, default=280.0, help="Nivel de saida em cm (default: 280)")

    args = parser.parse_args()

    motor = MotorFase4(
        obra_path=args.obra,
        pavimento=args.pavimento,
        nivel_chegada=args.nivel_chegada,
        nivel_saida=args.nivel_saida
    )
    stats = motor.run()

    # Exit code baseado em erros
    sys.exit(1 if stats["errors"] > 0 and stats["pilares"] + stats["vigas"] + stats["lajes"] == 0 else 0)


if __name__ == "__main__":
    main()
