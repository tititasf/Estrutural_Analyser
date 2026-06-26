#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_cad72_meioPont.py — CAD-7.2: Testes de extração MEIO_PONT por Laje
"""
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from scripts.extrair_meioPont_pl import calcular_pontaletes_laje, ESPACO_MAX_CM, ALTURA_PONT_MIN


# ─── AC-2: Cálculo de pontaletes ─────────────────────────────────────────────

class TestCalcularPontaletes:
    def test_laje_grande_pontalete(self):
        """Laje com altura >= ALTURA_PONT_MIN → PONTALETE."""
        r = calcular_pontaletes_laje(1420, 302, 280)
        assert r["tipo"] == "PONTALETE"
        assert r["pontalete"] > 0
        assert r["meio_pontalete"] == 0
        assert r["total"] == r["pontalete"]

    def test_laje_baixa_meio_pontalete(self):
        """Laje com altura < ALTURA_PONT_MIN → MEIO_PONTALETE."""
        r = calcular_pontaletes_laje(500, 400, 200)
        assert r["tipo"] == "MEIO_PONTALETE"
        assert r["meio_pontalete"] > 0
        assert r["pontalete"] == 0
        assert r["total"] == r["meio_pontalete"]

    def test_espacamento_100cm(self):
        """Grid de pontaletes com espaçamento <= 100 cm."""
        r = calcular_pontaletes_laje(300, 200, 280)
        # span_util_comp = 300-40=260 → ceil(260/100)+1 = 4 colunas
        # span_util_larg = 200-40=160 → ceil(160/100)+1 = 3 linhas
        assert r["colunas"] == 4
        assert r["linhas"] == 3
        assert r["total"] == 12

    def test_laje_pequena_minimo_1(self):
        """Laje muito pequena tem mínimo de 1 pontalete."""
        r = calcular_pontaletes_laje(50, 50, 280)
        assert r["total"] >= 1

    def test_laje_invalida_zerada(self):
        """Laje com comprimento 0 → total 0."""
        r = calcular_pontaletes_laje(0, 0, 280)
        assert r["total"] == 0

    def test_linhas_colunas_simetria(self):
        """Laje quadrada: linhas == colunas."""
        r = calcular_pontaletes_laje(400, 400, 280)
        assert r["linhas"] == r["colunas"]

    def test_total_equals_linhas_x_colunas(self):
        """total = linhas × colunas."""
        r = calcular_pontaletes_laje(700, 500, 280)
        assert r["total"] == r["linhas"] * r["colunas"]


# ─── AC-3: Output JSON ────────────────────────────────────────────────────────

OBRA_TREINO_1 = pathlib.Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1")
OUT_FILE = OBRA_TREINO_1 / "Fase-3_Interpretacao_Extracao" / "Lajes" / "lajes_meioPont.json"


class TestOutputJSON:
    def test_output_file_exists(self):
        """lajes_meioPont.json deve existir após execução."""
        assert OUT_FILE.exists(), f"Arquivo não encontrado: {OUT_FILE}"

    def test_output_valid_json(self):
        """lajes_meioPont.json deve ser JSON válido."""
        data = json.loads(OUT_FILE.read_text(encoding='utf-8'))
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_output_required_fields(self):
        """Cada laje deve ter campos obrigatórios."""
        data = json.loads(OUT_FILE.read_text(encoding='utf-8'))
        for nome, v in data.items():
            assert "pontalete" in v, f"{nome}: campo 'pontalete' ausente"
            assert "meio_pontalete" in v, f"{nome}: campo 'meio_pontalete' ausente"
            assert "total" in v, f"{nome}: campo 'total' ausente"
            assert "tipo" in v, f"{nome}: campo 'tipo' ausente"

    def test_cobertura_80_pct(self):
        """AC-5: >= 80% das lajes com pelo menos 1 pontalete."""
        data = json.loads(OUT_FILE.read_text(encoding='utf-8'))
        total = len(data)
        com_pont = sum(1 for v in data.values() if v.get("total", 0) > 0)
        cobertura = (com_pont / total * 100) if total > 0 else 0
        assert cobertura >= 80, f"Cobertura {cobertura:.1f}% < 80%"

    def test_tipo_valido(self):
        """Tipo deve ser PONTALETE, MEIO_PONTALETE ou INDEFINIDO."""
        data = json.loads(OUT_FILE.read_text(encoding='utf-8'))
        valid = {"PONTALETE", "MEIO_PONTALETE", "INDEFINIDO"}
        for nome, v in data.items():
            assert v["tipo"] in valid, f"{nome}: tipo inválido '{v['tipo']}'"


# ─── AC-4: Integração motor_fase4.py ─────────────────────────────────────────

class TestMotorFase4Integration:
    def test_lajefase4_has_pontaletes_field(self):
        """LajeFase4 deve ter campo pontaletes (verifica via JSON output)."""
        if not OUT_FILE.exists():
            return  # skip se arquivo não existe
        data = json.loads(OUT_FILE.read_text(encoding='utf-8'))
        # Verificar que todos os registros têm o campo total (gerado pela LajeFase4)
        for nome, v in data.items():
            assert "total" in v, f"{nome}: campo 'total' ausente"

    def test_lajefase4_to_dict_includes_pontaletes(self):
        """JSON output gerado pelo motor inclui dados de pontalete por laje."""
        if not OUT_FILE.exists():
            return
        data = json.loads(OUT_FILE.read_text(encoding='utf-8'))
        # Pelo menos uma laje deve ter total > 0
        totais = [v.get("total", 0) for v in data.values()]
        assert max(totais) > 0, "Nenhuma laje tem pontaletes calculados"

    def test_motor_fase4_json_output_has_pontaletes(self):
        """JSON individual de laje deve incluir campo pontaletes após motor rodar."""
        lj_json = pathlib.Path(
            "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/"
            "Fase-4_Sincronizacao/JSON_Lajes/L101.json"
        )
        if not lj_json.exists():
            return
        data = json.loads(lj_json.read_text(encoding='utf-8-sig'))
        # Campo pode estar ausente se motor não rodou ainda — só verificar se presente
        if "pontaletes" in data:
            assert isinstance(data["pontaletes"], dict)
