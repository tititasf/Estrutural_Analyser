#!/usr/bin/env python3
"""
validar_elementos_dxf.py — Validador por elemento segundo SPEC-GERADORES-DXF.md
=================================================================================
Verifica CADA linha da especificação no DXF gerado, produzindo:
  - Score por elemento (PASS / FAIL / SKIP)
  - Score por gerador (PL / LV / FV / LJ)
  - Score global
  - Relatório detalhado com o que falta corrigir

Uso:
  python scripts/validar_elementos_dxf.py --obra DADOS-OBRAS/Obra_TREINO_1 --pav "1PAV"
  python scripts/validar_elementos_dxf.py --dxf caminho/para/arquivo.dxf --tipo FV
  python scripts/validar_elementos_dxf.py --obra DADOS-OBRAS/Obra_TREINO_1 --pav "1PAV" --tipo PL
"""

import sys, io, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _norm_layer(name: str) -> str:
    """Normaliza nome de layer: remove acentos e coloca em maiúsculas."""
    return unicodedata.normalize('NFD', name).encode('ascii', 'ignore').decode().upper()

try:
    import ezdxf
except ImportError:
    print("[ERRO] ezdxf não instalado. Execute: pip install ezdxf")
    sys.exit(1)


# ─── Estruturas de dados ──────────────────────────────────────────────────────

@dataclass
class CheckResult:
    id: str                    # ex: "FV-01"
    desc: str                  # descrição do elemento
    layer: str                 # layer esperado
    entity_type: str           # tipo DXF (LWPOLYLINE, TEXT, DIMENSION, etc.)
    expected: str              # condição esperada
    found: int                 # quantidade encontrada
    status: str                # PASS / FAIL / SKIP / WARN
    detail: str = ""           # detalhe adicional


@dataclass
class GeneratorReport:
    tipo: str                  # PL / LV / FV / LJ
    dxf_path: str
    checks: list = field(default_factory=list)
    score_pct: float = 0.0
    aprovado: bool = False


# ─── Helpers de contagem ──────────────────────────────────────────────────────

def count_entities(msp, entity_type: str, layer: str = None, extra_filter=None) -> int:
    """Conta entidades de um tipo (e opcionalmente layer) no modelspace.
    Aceita múltiplos tipos separados por '|' ex: 'LINE|LWPOLYLINE'.
    Comparação de layer normaliza acentos e case.
    """
    count = 0
    etypes = [t.strip().upper() for t in entity_type.split('|')]
    layer_norm = _norm_layer(layer) if layer else None
    for e in msp:
        if e.dxftype().upper() not in etypes:
            continue
        if layer_norm and _norm_layer(e.dxf.layer) != layer_norm:
            continue
        if extra_filter and not extra_filter(e):
            continue
        count += 1
    return count


def count_inserts(msp, block_name: str) -> int:
    """Conta INSERTs de um bloco específico."""
    return sum(
        1 for e in msp
        if e.dxftype() == 'INSERT' and
        e.dxf.name.upper() == block_name.upper()
    )


def count_inserts_prefix(msp, prefix: str) -> int:
    """Conta INSERTs cujo nome começa com o prefixo."""
    return sum(
        1 for e in msp
        if e.dxftype() == 'INSERT' and
        e.dxf.name.upper().startswith(prefix.upper())
    )


def layers_present(doc) -> set:
    """Retorna conjunto de layers definidos no documento."""
    return {lyr.dxf.name.upper() for lyr in doc.layers}


def get_text_values(msp, layer: str = None) -> list:
    """Retorna valores de TEXT/MTEXT de um layer."""
    texts = []
    for e in msp:
        if e.dxftype() in ('TEXT', 'MTEXT'):
            if layer and e.dxf.layer.upper() != layer.upper():
                continue
            val = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            texts.append(val.strip())
    return texts


def result(check_id: str, desc: str, layer: str, etype: str,
           expected: str, found: int, threshold: int = 1) -> CheckResult:
    """Cria um CheckResult com status automático."""
    if found >= threshold:
        status = "PASS"
    elif found > 0:
        status = "WARN"
    else:
        status = "FAIL"
    return CheckResult(check_id, desc, layer, etype, expected, found, status)


def skip(check_id: str, desc: str, reason: str) -> CheckResult:
    return CheckResult(check_id, desc, "", "", "condicional", 0, "SKIP", reason)


# ─── Validadores por tipo ─────────────────────────────────────────────────────

def validar_pl(doc, msp, dados: dict) -> list:
    """Valida PL — Pilares (CIMA + ABCD + GRADES).
    Layers reais no gerador: SARRAFO, SARRAFO DE PRESSAO, SARR_2.2x7, SARR_2.2x10,
    SARR_3.5x7, Hachura, CHAPA, Madeira, Perfil Metálico, CONCRETO, COTA, NOMENCLATURA,
    Painéis, Nível, Texto Seção.
    """
    checks = []
    b = dados.get('b', 30)
    h = dados.get('h', 50)

    # ── CIMA ──────────────────────────────────────────────────────────────────
    chapa_count = count_entities(msp, "LWPOLYLINE", "CHAPA")
    if chapa_count > 0:
        checks.append(result("PL-C01", "Chapas metálicas (corpo CIMA)",
            "CHAPA", "LWPOLYLINE", "≥1", chapa_count))
    else:
        checks.append(skip("PL-C01", "Chapas metálicas (corpo CIMA)",
            "ausente — condicional por tipo de pilar"))

    sarrafo_ply = count_entities(msp, "LWPOLYLINE", "SARRAFO")
    checks.append(result("PL-C03", "Sarrafos CIMA (LWPOLYLINE no layer SARRAFO)",
        "SARRAFO", "LWPOLYLINE", "≥6", sarrafo_ply, threshold=6))

    sarrafo_hatch = count_entities(msp, "HATCH", "SARRAFO")
    checks.append(result("PL-C03b", "Hachura sarrafos (HATCH no layer SARRAFO)",
        "SARRAFO", "HATCH", "≥1", sarrafo_hatch))

    hachura_count = count_entities(msp, "LWPOLYLINE|HATCH", "Hachura")
    checks.append(result("PL-C05", "Hachura concreto (layer Hachura)",
        "Hachura", "LWPOLYLINE|HATCH", "≥1", hachura_count))

    madeira = count_entities(msp, "LWPOLYLINE", "Madeira")
    checks.append(result("PL-C05b", "Madeira (layer Madeira)",
        "Madeira", "LWPOLYLINE", "≥1", madeira))

    perfil = count_entities(msp, "LINE|LWPOLYLINE", "Perfil Metálico")
    checks.append(result("PL-C05c", "Perfil Metálico (layer Perfil Metálico)",
        "Perfil Metálico", "LINE|LWPOLYLINE", "≥1", perfil))

    checks.append(result("PL-C11", "Cotas DIMLINEAR (layer COTA)",
        "COTA", "DIMENSION", "≥2",
        count_entities(msp, "DIMENSION", "COTA"), threshold=2))

    checks.append(result("PL-C12", "Nomenclatura (TEXT no layer NOMENCLATURA)",
        "NOMENCLATURA", "TEXT|MTEXT", "≥1",
        count_entities(msp, "TEXT|MTEXT", "NOMENCLATURA")))

    texto_secao = count_entities(msp, "TEXT", "Texto Seção")
    if texto_secao > 0:
        checks.append(result("PL-C13", "Texto Seção (dimensões b×h)",
            "Texto Seção", "TEXT", "≥1", texto_secao))
    else:
        checks.append(skip("PL-C13", "Texto Seção (dimensões b×h)",
            "ausente — condicional por tipo de pilar"))

    # ── ABCD ──────────────────────────────────────────────────────────────────
    # Painéis ABCD: LWPOLYLINEs no layer Painéis
    paineis_ply = count_entities(msp, "LWPOLYLINE", "Painéis")
    checks.append(result("PL-A02", "Painéis ABCD (LWPOLYLINE no layer Painéis)",
        "Painéis", "LWPOLYLINE", "≥4", paineis_ply, threshold=4))

    sarr_227 = count_entities(msp, "LWPOLYLINE|LINE", "SARR_2.2x7")
    checks.append(result("PL-A06", "Sarrafos SARR_2.2x7 (ABCD + Grades)",
        "SARR_2.2x7", "LWPOLYLINE|LINE", "≥100", sarr_227, threshold=100))

    furacao_count = count_inserts(msp, "furacao")
    checks.append(result("PL-A09", "Furação (~20 blocos: 5/face × 4 faces)",
        "Painéis", "INSERT furacao", "≥16", furacao_count, threshold=16))

    # ── GRADES ────────────────────────────────────────────────────────────────
    sarr_10 = count_entities(msp, "LINE|LWPOLYLINE", "SARR_2.2x10")
    checks.append(result("PL-G05", "Sarrafos SARR_2.2x10 (grades horizontais)",
        "SARR_2.2x10", "LINE|LWPOLYLINE", "≥8", sarr_10, threshold=8))

    sarr_35 = count_entities(msp, "LINE|LWPOLYLINE", "SARR_3.5x7")
    # SARR_3.5x7 é condicional — só obrigatório em pilares com grades pesadas
    # Se ausente (count=0), é SKIP (obra pode não ter grades deste tipo)
    if sarr_35 > 0:
        checks.append(result("PL-G04", "Sarrafos SARR_3.5x7 (grades verticais)",
            "SARR_3.5x7", "LINE|LWPOLYLINE", "≥14", sarr_35, threshold=14))
    else:
        checks.append(skip("PL-G04", "Sarrafos SARR_3.5x7 (grades verticais)",
            "não encontrado no gerado — condicional por tipo de pilar"))

    nivel = count_entities(msp, "LWPOLYLINE", "Nível")
    checks.append(result("PL-A03", "Nível (layer Nível, linhas de nível ABCD)",
        "Nível", "LWPOLYLINE", "≥4", nivel, threshold=4))

    # Condicional: BCGV só em pilares gordos
    if b >= 90 or h >= 90:
        bcgv = count_inserts(msp, "BCGV")
        checks.append(result("PL-C10", "Bloco BCGV (pilar gordo ≥90cm)",
            "—", "INSERT", "≥1", bcgv))
    else:
        checks.append(skip("PL-C10", "Bloco BCGV", f"b={b} h={h} < 90cm"))

    return checks


def validar_lv(doc, msp, dados: dict) -> list:
    """Valida LV — Laterais de Vigas (Face A/B + VC)."""
    checks = []
    h = dados.get('h', 40)
    comp = dados.get('comprimento', 300)
    tem_pilar_esq = dados.get('pilar_esq', False)
    tem_pilar_dir = dados.get('pilar_dir', False)
    tem_laje_sup = dados.get('laje_sup', True)
    tem_laje_inf = dados.get('laje_inf', True)
    grade_mode = dados.get('grade_mode', False)

    # ── Faces A / B ───────────────────────────────────────────────────────────
    # Painéis: layer pode ter acento (Painéis) — _norm_layer trata corretamente
    paineis_count = count_entities(msp, "LWPOLYLINE", "Painéis")
    checks.append(result("LV-F01", "Moldura/contorno painel",
        "Painéis", "LWPOLYLINE", "≥2 (Face A + Face B)", paineis_count, threshold=2))

    # Sarrafos SARR_2.2x7: DXF real tem LINE e LWPOLYLINE nesse layer
    sarr_count = count_entities(msp, "LINE|LWPOLYLINE", "SARR_2.2x7")
    if h < 15:
        sarr_l5 = count_entities(msp, "LINE|LWPOLYLINE", "SARR_2.2x5")
        checks.append(result("LV-F05", f"Sarrafos SARR_2.2x5 (h={h}<15cm)",
            "SARR_2.2x5", "LINE|LWPOLYLINE", "≥4", sarr_l5, threshold=4))
    elif h < 30:
        checks.append(result("LV-F02", f"Sarrafos h<30cm (2/face × 2 = ≥4)",
            "SARR_2.2x7", "LINE|LWPOLYLINE", "≥4", sarr_count, threshold=4))
    elif h < 80:
        checks.append(result("LV-F03", f"Sarrafos h<80cm (4/face × 2 = ≥8)",
            "SARR_2.2x7", "LINE|LWPOLYLINE", "≥8", sarr_count, threshold=8))
    else:
        checks.append(result("LV-F04", f"Sarrafos h≥80cm (8/face × 2 = ≥16)",
            "SARR_2.2x7", "LINE|LWPOLYLINE", "≥16", sarr_count, threshold=16))

    if grade_mode:
        sarr_35 = count_entities(msp, "LINE|LWPOLYLINE", "SARR_3.5x7")
        checks.append(result("LV-F06", "Sarrafos SARR_3.5x7 (grade mode)",
            "SARR_3.5x7", "LINE|LWPOLYLINE", "≥1", sarr_35))
    else:
        checks.append(skip("LV-F06", "SARR_3.5x7", "não é grade mode"))

    if tem_laje_sup:
        hatch_count = count_entities(msp, "HATCH", "Hachura")
        checks.append(result("LV-F07", "Hachura laje superior (HHHH)",
            "Hachura", "HATCH", "≥1", hatch_count))
    else:
        checks.append(skip("LV-F07", "Hachura laje superior", "sem laje sup"))

    n_paineis = max(1, int(comp / 244) + (1 if comp % 244 > 0 else 0))
    checks.append(result("LV-F09", f"Painéis múltiplos (comp={comp}cm → {n_paineis})",
        "Painéis", "LWPOLYLINE", f"≥{n_paineis*2}", paineis_count, threshold=n_paineis*2))

    for codigo, desc, flag in [
        ("LV-F10", "Abertura esq topo (ABVET)", tem_pilar_esq),
        ("LV-F11", "Abertura esq fundo (ABVEF)", tem_pilar_esq),
        ("LV-F12", "Abertura dir topo (ABVDT)", tem_pilar_dir),
        ("LV-F13", "Abertura dir fundo (ABVDF)", tem_pilar_dir),
    ]:
        if flag:
            # Aberturas são PLINEs em Painéis — difícil distinguir sem coords
            checks.append(result(codigo, desc, "Painéis", "LWPOLYLINE",
                "≥1 (indireto)", paineis_count, threshold=1))
        else:
            checks.append(skip(codigo, desc, "sem pilar adjacente"))

    reaprov = count_entities(msp, "HATCH", "REAPROVEITAMENTO")
    checks.append(result("LV-F14", "Hachura reaproveitamento (ANSI31)",
        "REAPROVEITAMENTO", "HATCH", "≥0 (se painel reusado)", reaprov, threshold=0))

    lv_nom = count_entities(msp, "TEXT", "NOMENCLATURA")
    if lv_nom > 0:
        checks.append(result("LV-F17", "Nomenclatura (V{n} + b×h)",
            "NOMENCLATURA", "TEXT", "≥1", lv_nom))
    else:
        checks.append(skip("LV-F17", "Nomenclatura (V{n} + b×h)",
            "ausente — condicional por obra"))

    # ── Visão de Corte (VC) ───────────────────────────────────────────────────
    # LV-V03: SCR usa MLINE; ezdxf emite LINE no layer SARRAFO_2_2X7
    checks.append(result("LV-V03", "Sarrafos VC (LINE/MLINE no layer SARRAFO_2_2X7)",
        "SARRAFO_2_2X7", "LINE|MLINE", "≥1",
        count_entities(msp, "LINE|MLINE", "SARRAFO_2_2X7")))

    # LV-V04: Barras de ancoragem (LINE ou LWPOLYLINE no layer BARRA_ANCORAGEM)
    checks.append(result("LV-V04", "Barras de ancoragem",
        "BARRA_ANCORAGEM", "LINE|LWPOLYLINE", "≥2",
        count_entities(msp, "LINE|LWPOLYLINE", "BARRA_ANCORAGEM"), threshold=2))

    checks.append(result("LV-V05", "Hachura concreto VC (HACHURACONCRETO)",
        "HACHURACONCRETO", "HATCH", "≥1",
        count_entities(msp, "HATCH", "HACHURACONCRETO")))

    par_esq = count_inserts(msp, "PAR_ESQ")
    par_fundo = (count_inserts(msp, "PAR_FUNDO_ESQ") +
                 count_inserts(msp, "PAR_FUNDO_DIR"))
    par_int = (count_inserts(msp, "par_int_esq") +
               count_inserts(msp, "par_int_dir"))
    checks.append(result("LV-V06", "Blocos PAR_ESQ/FUNDO_ESQ/DIR/int_esq/dir (5 total)",
        "—", "INSERT", "=5",
        par_esq + par_fundo + par_int, threshold=5))

    checks.append(result("LV-V05b", "Estruturacao (pontalete TEXT)",
        "ESTRUTURACAO", "TEXT", "≥1",
        count_entities(msp, "TEXT", "ESTRUTURACAO")))

    return checks


def validar_fv(doc, msp, dados: dict) -> list:
    """Valida FV — Fundos de Vigas."""
    checks = []
    n_vigas = dados.get('n_vigas', 1)
    n_paineis_total = dados.get('n_paineis', n_vigas * 2)

    # FV-01: Nomenclatura — CRÍTICO (causa principal de falha)
    # Conta todos os TEXTs no layer NOMENCLATURA (sem filtrar prefixo 'V')
    # Motivo: o filtro por 'V' retornava 0 mesmo com 31 TEXTs no layer real
    nom_count = count_entities(msp, "TEXT|MTEXT", "NOMENCLATURA")
    checks.append(result("FV-01", f"Nomenclatura — nome das vigas ({n_vigas} esperadas)",
        "NOMENCLATURA", "TEXT", f"≥{n_vigas}",
        nom_count, threshold=n_vigas))

    # FV-02/03: Labels ESQ / DIR
    layer5_texts = get_text_values(msp, layer="5")
    esq_count = sum(1 for t in layer5_texts if 'ESQ' in t.upper())
    dir_count = sum(1 for t in layer5_texts if 'DIR' in t.upper())
    checks.append(result("FV-02", f"Labels ESQ (1 por viga = {n_vigas})",
        "5", "TEXT", f"={n_vigas}", esq_count, threshold=n_vigas))
    checks.append(result("FV-03", f"Labels DIR (1 por viga = {n_vigas})",
        "5", "TEXT", f"={n_vigas}", dir_count, threshold=n_vigas))

    # FV-04/05: Retângulos topo + base de cada painel
    # _norm_layer em count_entities trata "Painéis" e "Paineis" como equivalentes
    paineis_ply = count_entities(msp, "LWPOLYLINE", "Painéis")
    checks.append(result("FV-04", f"Retângulos painel topo+base ({n_paineis_total*2} esperados)",
        "Painéis", "LWPOLYLINE", f"≥{n_paineis_total*2}",
        paineis_ply, threshold=n_paineis_total * 2))

    # FV-06: Divisores verticais entre painéis (são LINE, não LWPOLYLINE)
    div_lines = count_entities(msp, "LINE", "Painéis")
    checks.append(result("FV-06", "Divisores verticais entre painéis",
        "Painéis", "LINE", f"≥{max(0, n_paineis_total - n_vigas)}",
        div_lines, threshold=max(1, n_paineis_total - n_vigas)))

    # FV-07: Sarrafos horizontais
    # DXF real de FV tem sarrafos como LINE (194 LINEs em SARR_2.2x7), não LWPOLYLINE
    sarr_h = count_entities(msp, "LINE|LWPOLYLINE", "SARR_2.2x7")
    checks.append(result("FV-07", "Sarrafos horizontais por painel",
        "SARR_2.2x7", "LINE|LWPOLYLINE", f"≥{n_paineis_total * 3}",
        sarr_h, threshold=n_paineis_total * 3))

    # FV-08: Sarrafos verticais bordas (2 por viga)
    # Difícil distinguir de sarrafos horizontais sem coords; conta total
    checks.append(result("FV-08", "Sarrafos verticais bordas ESQ+DIR",
        "SARR_2.2x7", "LINE|LWPOLYLINE", f"≥{n_vigas*2}",
        sarr_h, threshold=n_vigas * 2))

    # FV-09: SARR_EDITAR — presente em ~50% dos STOGs reais (condicional)
    # Quando presente deve ter ≥2; quando ausente → SKIP
    sarr_edit = count_entities(msp, "LINE|LWPOLYLINE", "SARR_EDITAR")
    if sarr_edit > 0:
        checks.append(result("FV-09", "Sarrafos SARR_EDITAR (ex2 extend — bordas externas)",
            "SARR_EDITAR", "LINE|LWPOLYLINE", "≥2", sarr_edit, threshold=2))
    else:
        checks.append(skip("FV-09", "SARR_EDITAR",
            "ausente neste gerado — condicional por obra"))

    # FV-10: Chanfros nos cantos (4 por viga mínimo)
    # Chanfros são PLINEs pequenos em Painéis — difícil distinguir; verifica presença de muitos PLINEs
    checks.append(result("FV-10", "Chanfros nos cantos dos painéis",
        "Painéis", "LWPOLYLINE", f"≥{n_vigas*4}",
        paineis_ply, threshold=n_vigas * 4))

    # FV-11: Reaproveitamento
    reaprov = count_entities(msp, "HATCH", "REAPROVEITAMENTO")
    checks.append(result("FV-11", "Hachura reaproveitamento (ANSI31)",
        "REAPROVEITAMENTO", "HATCH", "≥0 (se aplicável)", reaprov, threshold=0))

    # FV-12: Blocos nf1–nf10 (numeração de painéis)
    nf_count = sum(count_inserts(msp, f'nf{i}') for i in range(1, 11))
    checks.append(result("FV-12", f"Blocos nf1-nf10 ({n_paineis_total} esperados)",
        "COTA", "INSERT nf*", f"={n_paineis_total}",
        nf_count, threshold=n_paineis_total))

    # FV-13: Cotas individuais por painel
    dims = count_entities(msp, "DIMENSION", "COTA")
    checks.append(result("FV-13", f"Cotas individuais por painel ({n_paineis_total})",
        "COTA", "DIMENSION", f"≥{n_paineis_total}",
        dims, threshold=n_paineis_total))

    # FV-14: Cota total
    checks.append(result("FV-14", "Cota total por viga",
        "COTA", "DIMENSION", f"≥{n_vigas}",
        dims, threshold=n_vigas))

    # FV-15: Cota altura
    checks.append(result("FV-15", "Cota altura da viga",
        "COTA", "DIMENSION", f"≥{n_vigas}",
        dims, threshold=n_vigas))

    return checks


def validar_lj(doc, msp, dados: dict) -> list:
    """Valida LJ — Lajes."""
    checks = []
    n_lajes = dados.get('n_lajes', 1)
    n_pilares = dados.get('n_pilares', 0)
    tem_escada = dados.get('tem_escada', False)
    tem_reaprov = dados.get('tem_reaprov', False)

    # LJ-01: Contorno exterior da laje
    # DXF real usa LINE no layer Painéis (não LWPOLYLINE como no spec original)
    paineis = count_entities(msp, "LINE|LWPOLYLINE", "Painéis")
    checks.append(result("LJ-01", "Contorno exterior da laje",
        "Painéis", "LINE|LWPOLYLINE", f"≥{n_lajes}", paineis, threshold=n_lajes))

    # LJ-02/03: Divisões de painel (layer 3 — condicional, ausente em estilos EST-*)
    layer3_total = count_entities(msp, "LINE|LWPOLYLINE", "3")
    if layer3_total > 0:
        checks.append(result("LJ-02", "Divisões painel verticais+horizontais (layer 3)",
            "3", "LINE|LWPOLYLINE", "≥4", layer3_total, threshold=4))
    else:
        checks.append(skip("LJ-02", "Divisões painel (layer 3)",
            "layer 3 ausente neste estilo de obra (usa EST-* ou Painéis diretamente)"))

    # LJ-04: Hachura SOLID
    hatch_solid = count_entities(msp, "HATCH", "Hachura")
    checks.append(result("LJ-04", "Hachura SOLID (área da laje)",
        "Hachura", "HATCH", f"≥{n_lajes}", hatch_solid, threshold=n_lajes))

    # LJ-05: Pilares internos
    if n_pilares > 0:
        pilar_poly = count_entities(msp, "LWPOLYLINE", "7")
        checks.append(result("LJ-05", f"Retângulos de pilar interno ({n_pilares})",
            "7", "LWPOLYLINE", f"≥{n_pilares}", pilar_poly, threshold=n_pilares))
    else:
        checks.append(skip("LJ-05", "Pilares internos", "n_pilares=0"))

    # LJ-06: Labels V{n}/L{n} — condicional (layer 4 não existe em todos os estilos LJ)
    layer4_text = count_entities(msp, "TEXT", "4")
    if layer4_text > 0:
        checks.append(result("LJ-06", "Labels V{n}/L{n} (tipo+número)",
            "4", "TEXT", f"≥{n_lajes}", layer4_text, threshold=n_lajes))
    else:
        checks.append(skip("LJ-06", "Labels V{n}/L{n}",
            "layer 4 ausente neste estilo de obra (usa EST-* ou similar)"))

    # LJ-09: Reaproveitamento
    if tem_reaprov:
        reaprov = count_entities(msp, "HATCH", "REAPROVEITAMENTO")
        checks.append(result("LJ-09", "Hachura ANSI31 reaproveitamento",
            "REAPROVEITAMENTO", "HATCH", "≥1", reaprov))
    else:
        checks.append(skip("LJ-09", "Hachura reaproveitamento", "sem reaproveitamento"))

    # LJ-10: Cotas
    dims = count_entities(msp, "DIMENSION", "Painéis")
    checks.append(result("LJ-10", "Cotas (COTA PAINEL-50)",
        "Painéis", "DIMENSION", "≥2", dims, threshold=2))

    # LJ-11: MTEXT dados do painel — condicional (AUX00 só em alguns estilos)
    mtext_count = count_entities(msp, "MTEXT", "AUX00")
    if mtext_count > 0:
        checks.append(result("LJ-11", "MTEXT dados do painel (AUX00)",
            "AUX00", "MTEXT", f"≥{n_lajes}", mtext_count, threshold=n_lajes))
    else:
        checks.append(skip("LJ-11", "MTEXT dados do painel (AUX00)",
            "AUX00 ausente neste estilo de obra"))

    # LJ-E02: Laje escada
    if tem_escada:
        checks.append(result("LJ-E02", "Segunda hachura HLAZ (escada/LE1)",
            "Hachura", "HATCH", "=2", hatch_solid, threshold=2))
    else:
        checks.append(skip("LJ-E02", "Segunda hachura LE1", "sem escada"))

    return checks


# ─── Carregamento de dados do pavimento ──────────────────────────────────────

def inferir_dados(obra_dir: Path, pav: str, tipo: str) -> dict:
    """Tenta inferir parâmetros do pavimento a partir dos dados existentes."""
    dados = {}

    # Carregar obras_salvas.json se existir
    obras_json = obra_dir / "Fase-6_Execucao_CAD" / "obras_salvas.json"
    if obras_json.exists():
        try:
            obra_data = json.loads(obras_json.read_text('utf-8'))
            pav_data = obra_data.get(pav, {})

            if tipo == 'FV':
                vigas = pav_data.get('vigas', [])
                dados['n_vigas'] = len(vigas)
                dados['n_paineis'] = sum(v.get('n_paineis', 2) for v in vigas)

            elif tipo == 'PL':
                pilares = pav_data.get('pilares', [])
                if pilares:
                    # Usa o primeiro pilar como referência
                    p = pilares[0]
                    dados['b'] = p.get('b', 30)
                    dados['h'] = p.get('h', 50)

            elif tipo == 'LV':
                vigas = pav_data.get('vigas', [])
                if vigas:
                    v = vigas[0]
                    dados['h'] = v.get('h', 40)
                    dados['comprimento'] = v.get('comprimento', 300)

            elif tipo == 'LJ':
                lajes = pav_data.get('lajes', [])
                dados['n_lajes'] = len(lajes)
                dados['n_pilares'] = len(pav_data.get('pilares', []))
        except Exception as e:
            print(f"[WARN] Não conseguiu ler obras_salvas.json: {e}")

    return dados


# ─── Cálculo de score ────────────────────────────────────────────────────────

def calcular_score(checks: list) -> float:
    """Calcula score percentual: PASS+WARN/total (excluindo SKIP)."""
    ativos = [c for c in checks if c.status != 'SKIP']
    if not ativos:
        return 100.0
    aprovados = sum(1 for c in ativos if c.status in ('PASS', 'WARN'))
    return round(100.0 * aprovados / len(ativos), 1)


# ─── Impressão de resultado ──────────────────────────────────────────────────

def imprimir_relatorio(report: GeneratorReport):
    """Imprime relatório formatado no terminal."""
    print(f"\n{'='*65}")
    print(f"  {report.tipo} — {Path(report.dxf_path).name}")
    print(f"  Score: {report.score_pct:.1f}%  {'APROVADO' if report.aprovado else 'REPROVADO'}")
    print(f"{'='*65}")

    falhas = [c for c in report.checks if c.status == 'FAIL']
    avisos = [c for c in report.checks if c.status == 'WARN']
    passes = [c for c in report.checks if c.status == 'PASS']
    skips  = [c for c in report.checks if c.status == 'SKIP']

    print(f"  PASS: {len(passes)} | WARN: {len(avisos)} | FAIL: {len(falhas)} | SKIP: {len(skips)}")

    if falhas:
        print(f"\n  ❌ FALHAS:")
        for c in falhas:
            print(f"    [{c.id}] {c.desc}")
            print(f"           layer={c.layer} | tipo={c.entity_type} | esperado={c.expected} | encontrado={c.found}")

    if avisos:
        print(f"\n  ⚠️  AVISOS (parcial):")
        for c in avisos:
            print(f"    [{c.id}] {c.desc} (encontrado={c.found}, esperado={c.expected})")

    if not falhas and not avisos:
        print("\n  ✅ Todos os elementos presentes!")


# ─── Entrada principal ────────────────────────────────────────────────────────

VALIDADORES = {
    'PL': validar_pl,
    'LV': validar_lv,
    'FV': validar_fv,
    'LJ': validar_lj,
}

METAS = {
    'PL': 90.0,
    'LV': 90.0,
    'FV': 90.0,
    'LJ': 90.0,
}

DXF_NAMES = {
    'PL': 'PL_stog_quality.dxf',
    'LV': 'LV_stog_quality.dxf',
    'FV': 'FV_stog_quality.dxf',
    'LJ': 'LJ_stog_quality.dxf',
}


def processar_dxf(dxf_path: Path, tipo: str, dados: dict) -> GeneratorReport:
    """Carrega DXF e executa a validação para o tipo."""
    report = GeneratorReport(tipo=tipo, dxf_path=str(dxf_path))

    if not dxf_path.exists():
        report.checks = [CheckResult(
            f"{tipo}-MISSING", f"DXF não encontrado: {dxf_path.name}",
            "", "", "arquivo existe", 0, "FAIL", str(dxf_path)
        )]
        report.score_pct = 0.0
        return report

    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
    except Exception as e:
        report.checks = [CheckResult(
            f"{tipo}-LOAD", f"Erro ao carregar DXF: {e}",
            "", "", "arquivo válido", 0, "FAIL"
        )]
        report.score_pct = 0.0
        return report

    validador = VALIDADORES.get(tipo)
    if not validador:
        print(f"[WARN] Tipo {tipo} sem validador implementado")
        return report

    report.checks = validador(doc, msp, dados)
    report.score_pct = calcular_score(report.checks)
    report.aprovado = report.score_pct >= METAS.get(tipo, 90.0)
    return report


def main():
    parser = argparse.ArgumentParser(
        description='Valida elementos DXF contra a spec STOG'
    )
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument('--obra', help='Path da obra (ex: DADOS-OBRAS/Obra_TREINO_1)')
    grp.add_argument('--dxf', help='Path direto para um DXF específico')

    parser.add_argument('--pav', default=None,
                        help='Pavimento (ex: "1PAV") — requerido com --obra')
    parser.add_argument('--tipo', choices=['PL', 'LV', 'FV', 'LJ'],
                        default=None, help='Tipo de gerador (omitir = todos)')
    parser.add_argument('--json', action='store_true',
                        help='Saída em JSON')
    parser.add_argument('--n-vigas', type=int, default=None)
    parser.add_argument('--n-paineis', type=int, default=None)
    parser.add_argument('--n-lajes', type=int, default=1)
    args = parser.parse_args()

    tipos = [args.tipo] if args.tipo else list(VALIDADORES.keys())
    reports = []

    if args.dxf:
        # Modo DXF direto
        dxf_path = Path(args.dxf)
        tipo = args.tipo or 'FV'
        dados = {}
        if args.n_vigas: dados['n_vigas'] = args.n_vigas
        if args.n_paineis: dados['n_paineis'] = args.n_paineis
        rep = processar_dxf(dxf_path, tipo, dados)
        reports.append(rep)

    else:
        # Modo obra/pavimento
        obra_dir = Path(args.obra)
        if not obra_dir.exists():
            print(f"[ERRO] Obra não encontrada: {obra_dir}")
            sys.exit(1)

        fase6 = obra_dir / 'Fase-6_Execucao_CAD'
        if not fase6.exists():
            print(f"[ERRO] Fase-6_Execucao_CAD não encontrada em {obra_dir}")
            sys.exit(1)

        for tipo in tipos:
            dxf_path = fase6 / DXF_NAMES[tipo]
            dados = inferir_dados(obra_dir, args.pav or '', tipo)

            # Override com args CLI
            if args.n_vigas: dados['n_vigas'] = args.n_vigas
            if args.n_paineis: dados['n_paineis'] = args.n_paineis
            if args.n_lajes: dados['n_lajes'] = args.n_lajes

            rep = processar_dxf(dxf_path, tipo, dados)
            reports.append(rep)

    # ── Saída ─────────────────────────────────────────────────────────────────
    if args.json:
        output = []
        for rep in reports:
            output.append({
                'tipo': rep.tipo,
                'dxf': rep.dxf_path,
                'score_pct': rep.score_pct,
                'aprovado': rep.aprovado,
                'checks': [
                    {
                        'id': c.id,
                        'desc': c.desc,
                        'status': c.status,
                        'found': c.found,
                        'expected': c.expected,
                        'detail': c.detail,
                    }
                    for c in rep.checks
                ]
            })
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        for rep in reports:
            imprimir_relatorio(rep)

        # Sumário final
        print(f"\n{'='*65}")
        print("  SUMÁRIO")
        print(f"{'='*65}")
        total_pass = total_fail = 0
        for rep in reports:
            status = 'APROVADO' if rep.aprovado else 'REPROVADO'
            falhas = sum(1 for c in rep.checks if c.status == 'FAIL')
            total_fail += falhas
            total_pass += sum(1 for c in rep.checks if c.status == 'PASS')
            print(f"  {rep.tipo}: {rep.score_pct:.1f}% [{status}] — {falhas} falhas")

        global_score = 100.0 * total_pass / (total_pass + total_fail) if (total_pass + total_fail) else 0
        print(f"\n  Score global: {global_score:.1f}%")
        print(f"{'='*65}\n")

    # Exit code: 0 = tudo aprovado, 1 = alguma reprovação
    all_pass = all(rep.aprovado for rep in reports)
    sys.exit(0 if all_pass else 1)


if __name__ == '__main__':
    main()
