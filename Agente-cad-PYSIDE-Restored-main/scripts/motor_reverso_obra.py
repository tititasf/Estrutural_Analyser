# -*- coding: utf-8 -*-
"""
Motor Reverso Obra v2 — Análise inteligente da obra a partir das fichas N2.

Gera resumo consolidado com:
  • Estatísticas por classe (PIL/LV/FV/LAJ)
  • Padrões dominantes (dimensões, configurações)
  • Insights automáticos e alertas de qualidade
  • Anomalias (outliers dimensionais)
  • Cobertura por pavimento
"""

import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

DB_PATH = "D:/Agente-cad-PYSIDE/project_data.vision"


# ── Helpers estatísticos (sem numpy) ─────────────────────────────────────────

def _mode(values: list):
    """Valor mais frequente, ou None se lista vazia."""
    if not values:
        return None
    return Counter(str(round(v, 1)) if isinstance(v, float) else str(v) for v in values).most_common(1)[0][0]

def _mean(values: list) -> float:
    return sum(values) / len(values) if values else 0.0

def _stdev(values: list) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return (sum((x - m) ** 2 for x in values) / len(values)) ** 0.5

def _dominant_pct(values: list) -> tuple[str, float]:
    """Retorna (valor_dominante, pct_de_ocorrência)."""
    if not values:
        return ('?', 0.0)
    c = Counter(str(round(v, 1)) if isinstance(v, float) else str(v) for v in values)
    top_val, top_count = c.most_common(1)[0]
    return (top_val, round(top_count / len(values) * 100, 1))

def _distribution_top(values: list, n: int = 5) -> list[dict]:
    """Top N valores com contagem e pct."""
    if not values:
        return []
    total = len(values)
    c = Counter(str(round(v, 1)) if isinstance(v, float) else str(v) for v in values)
    return [
        {'valor': val, 'count': cnt, 'pct': round(cnt / total * 100, 1)}
        for val, cnt in c.most_common(n)
    ]

def _outliers(values: list, labels: list, field: str, z_thresh: float = 2.5) -> list[dict]:
    """Detecta outliers (Z-score > z_thresh)."""
    if len(values) < 4:
        return []
    m = _mean(values)
    s = _stdev(values)
    if s < 0.01:
        return []
    result = []
    for val, lbl in zip(values, labels):
        z = abs(val - m) / s
        if z > z_thresh:
            result.append({'elemento': lbl, 'valor': val, 'media': round(m, 2), 'desvio_z': round(z, 2), 'campo': field})
    return result


# ── Análise por classe ────────────────────────────────────────────────────────

def _analisar_pil(items: list) -> dict:
    """Analisa fichas PIL: geometria, grades, padrões de faces."""
    comps  = [(i['campos'].get('comprimento') or 0, i['elemento_id']) for i in items if i['campos'].get('comprimento')]
    largs  = [(i['campos'].get('largura') or 0, i['elemento_id'])     for i in items if i['campos'].get('largura')]
    alts   = [(i['campos'].get('altura') or 0, i['elemento_id'])      for i in items if i['campos'].get('altura')]
    g1vals = [i['campos'].get('grade_1') or 0 for i in items if i['campos'].get('grade_1')]
    g2vals = [i['campos'].get('grade_2') or 0 for i in items if i['campos'].get('grade_2')]

    comp_v = [v for v, _ in comps]
    larg_v = [v for v, _ in largs]
    alt_v  = [v for v, _ in alts]

    result = {}
    if comp_v:
        dom_comp, dom_pct = _dominant_pct(comp_v)
        result['comprimento'] = {
            'min': min(comp_v), 'max': max(comp_v), 'media': round(_mean(comp_v), 1),
            'dominante': dom_comp, 'dominante_pct': dom_pct,
            'distribuicao': _distribution_top(comp_v),
        }
        result['anomalias_comprimento'] = _outliers(comp_v, [l for _, l in comps], 'comprimento')
    if larg_v:
        dom_larg, dom_pct_l = _dominant_pct(larg_v)
        result['largura'] = {
            'min': min(larg_v), 'max': max(larg_v), 'media': round(_mean(larg_v), 1),
            'dominante': dom_larg, 'dominante_pct': dom_pct_l,
            'distribuicao': _distribution_top(larg_v),
        }
    if alt_v:
        dom_alt, _ = _dominant_pct(alt_v)
        result['altura'] = {
            'min': min(alt_v), 'max': max(alt_v), 'media': round(_mean(alt_v), 1),
            'dominante': dom_alt,
        }
    if g1vals:
        result['grade_1_distribuicao'] = _distribution_top(g1vals, 3)
    if g2vals:
        non_zero = [v for v in g2vals if v > 0]
        result['grade_2_taxa_presenca'] = round(len(non_zero) / len(g2vals) * 100, 1)

    return result


def _analisar_lv_fv(items: list, classe: str) -> dict:
    """Analisa fichas LV ou FV: altura, painéis, furos, pilares."""
    heights = []
    widths  = []
    panel_counts = []
    panel_widths_all = []
    furos_ativos = 0
    pilar_esq = 0
    pilar_dir = 0
    elem_ids  = []

    for i in items:
        c = i['campos']
        elem_ids.append(i['elemento_id'])

        h = c.get('total_height') or c.get('altura')
        if h:
            try:
                heights.append(float(h))
            except (TypeError, ValueError):
                pass

        w = c.get('total_width') or c.get('largura')
        if w:
            try:
                widths.append(float(w))
            except (TypeError, ValueError):
                pass

        panels = c.get('panels', [])
        if isinstance(panels, list):
            panel_counts.append(len(panels))
            for p in panels:
                pw = p.get('width', 0)
                if pw:
                    try:
                        panel_widths_all.append(float(pw))
                    except (TypeError, ValueError):
                        pass

        holes = c.get('holes', [])
        if isinstance(holes, list) and any(h.get('active') for h in holes):
            furos_ativos += 1

        pl = c.get('pillar_left', {})
        pr = c.get('pillar_right', {})
        if isinstance(pl, dict) and pl.get('active'):
            pilar_esq += 1
        if isinstance(pr, dict) and pr.get('active'):
            pilar_dir += 1

    result = {}
    n = len(items)

    if heights:
        dom_h, dom_h_pct = _dominant_pct(heights)
        result['altura'] = {
            'min': min(heights), 'max': max(heights), 'media': round(_mean(heights), 1),
            'dominante': dom_h, 'dominante_pct': dom_h_pct,
            'distribuicao': _distribution_top(heights),
        }
        result['anomalias_altura'] = _outliers(heights, elem_ids[:len(heights)], 'total_height')

    if widths:
        dom_w, _ = _dominant_pct(widths)
        result['largura'] = {
            'min': min(widths), 'max': max(widths), 'media': round(_mean(widths), 1),
            'dominante': dom_w,
        }

    if panel_counts:
        dom_pc, dom_pc_pct = _dominant_pct(panel_counts)
        result['num_paineis'] = {
            'dominante': dom_pc, 'dominante_pct': dom_pc_pct,
            'distribuicao': _distribution_top(panel_counts),
        }

    if panel_widths_all:
        result['larguras_paineis'] = {
            'distribuicao': _distribution_top(panel_widths_all, 6),
        }

    if n:
        result['furos_presentes_pct'] = round(furos_ativos / n * 100, 1)
        result['pilar_esq_pct'] = round(pilar_esq / n * 100, 1)
        result['pilar_dir_pct'] = round(pilar_dir / n * 100, 1)

    return result


def _analisar_laj(items: list) -> dict:
    """Analisa fichas LAJ: área, dimensões, pontaletes."""
    areas   = []
    comps   = []
    largs   = []
    pont_counts = []
    elem_ids = []

    for i in items:
        c = i['campos']
        elem_ids.append(i['elemento_id'])
        a = c.get('area_cm2')
        if a:
            try:
                areas.append(float(a))
            except (TypeError, ValueError):
                pass
        cp = c.get('comprimento')
        if cp:
            try:
                comps.append(float(cp))
            except (TypeError, ValueError):
                pass
        lg = c.get('largura')
        if lg:
            try:
                largs.append(float(lg))
            except (TypeError, ValueError):
                pass
        pont = c.get('pontaletes', [])
        if isinstance(pont, list):
            pont_counts.append(len(pont))

    result = {}
    if areas:
        result['area'] = {
            'min': round(min(areas), 1), 'max': round(max(areas), 1),
            'media': round(_mean(areas), 1),
            'distribuicao': _distribution_top(areas, 4),
        }
    if comps:
        result['comprimento'] = {
            'min': min(comps), 'max': max(comps), 'media': round(_mean(comps), 1),
        }
    if largs:
        result['largura'] = {
            'min': min(largs), 'max': max(largs), 'media': round(_mean(largs), 1),
        }
    if pont_counts:
        dom_p, dom_p_pct = _dominant_pct(pont_counts)
        result['pontaletes_por_laje'] = {
            'dominante': dom_p, 'dominante_pct': dom_p_pct,
            'distribuicao': _distribution_top(pont_counts),
        }
    return result


# ── Geração de insights ───────────────────────────────────────────────────────

def _gerar_insights(resumo: dict, por_classe: dict) -> list[dict]:
    """Gera lista de insights automáticos com severidade e categoria."""
    insights = []

    def add(text: str, nivel: str = 'info', categoria: str = 'geral'):
        insights.append({'texto': text, 'nivel': nivel, 'categoria': categoria})

    total = resumo.get('total_fichas', 0)
    conf_media = resumo.get('confianca_media_geral', 0)
    classes_presentes = list(resumo.get('por_classe_stats', {}).keys())

    # Cobertura geral
    if total == 0:
        add("Nenhuma ficha gerada ainda. Execute 'Gerar Fichas' com recortes aprovados.", 'alerta', 'cobertura')
        return insights

    # Confiança global
    if conf_media >= 0.9:
        add(f"Confiança média geral excelente: {conf_media*100:.0f}%", 'sucesso', 'qualidade')
    elif conf_media >= 0.75:
        add(f"Confiança média geral boa: {conf_media*100:.0f}%", 'info', 'qualidade')
    elif conf_media >= 0.6:
        add(f"Confiança média moderada ({conf_media*100:.0f}%). Revisar fichas com baixa confiança.", 'aviso', 'qualidade')
    else:
        add(f"Confiança média baixa ({conf_media*100:.0f}%). Extração requer revisão manual.", 'alerta', 'qualidade')

    # Baixa confiança por classe
    for cls, stats in resumo.get('por_classe_stats', {}).items():
        conf_cls = stats.get('confianca_media', 0)
        baixa_conf = stats.get('baixa_confianca_count', 0)
        total_cls = stats.get('total', 0)
        if baixa_conf > 0:
            pct_baixa = round(baixa_conf / total_cls * 100, 0) if total_cls else 0
            nivel = 'alerta' if pct_baixa > 30 else 'aviso'
            add(f"{cls}: {baixa_conf} elemento(s) com confiança < 60% ({pct_baixa:.0f}%) — revisar recortes manualmente.",
                nivel, 'qualidade')

    # Padrões PIL
    pil_analise = por_classe.get('PIL', {}).get('analise', {})
    if pil_analise:
        comp = pil_analise.get('comprimento', {})
        if comp and comp.get('dominante_pct', 0) >= 70:
            add(f"PIL: {comp['dominante_pct']:.0f}% dos pilares têm comprimento {comp['dominante']} cm (padrão dominante).",
                'info', 'padrao')
        elif comp and comp.get('dominante_pct', 0) < 50:
            add(f"PIL: Alta diversidade de comprimentos — sem dimensão dominante clara ({comp.get('dominante_pct', 0):.0f}% no valor mais frequente).",
                'info', 'padrao')

        larg = pil_analise.get('largura', {})
        if larg and larg.get('dominante_pct', 0) >= 80:
            add(f"PIL: Largura padronizada em {larg['dominante']} cm ({larg['dominante_pct']:.0f}% dos elementos).",
                'sucesso', 'padrao')

        anomalias = pil_analise.get('anomalias_comprimento', [])
        if anomalias:
            nomes = ', '.join(a['elemento'] for a in anomalias[:3])
            add(f"PIL: {len(anomalias)} pilar(es) com comprimento atípico detectado(s): {nomes}.",
                'aviso', 'anomalia')

    # Padrões LV
    lv_analise = por_classe.get('LV', {}).get('analise', {})
    if lv_analise:
        h = lv_analise.get('altura', {})
        if h and h.get('dominante_pct', 0) >= 70:
            add(f"LV: Altura dominante {h['dominante']} cm ({h['dominante_pct']:.0f}% das vigas laterais).",
                'info', 'padrao')
        np_ = lv_analise.get('num_paineis', {})
        if np_ and np_.get('dominante_pct', 0) >= 80:
            add(f"LV: Configuração de {np_['dominante']} painel(s) predomina em {np_['dominante_pct']:.0f}% das vigas laterais.",
                'info', 'padrao')
        anom = lv_analise.get('anomalias_altura', [])
        if anom:
            nomes = ', '.join(a['elemento'] for a in anom[:3])
            add(f"LV: {len(anom)} viga(s) lateral(is) com altura atípica: {nomes}.", 'aviso', 'anomalia')

    # Padrões FV
    fv_analise = por_classe.get('FV', {}).get('analise', {})
    if fv_analise:
        h = fv_analise.get('altura', {})
        if h and h.get('dominante_pct', 0) >= 70:
            add(f"FV: Altura dominante {h['dominante']} cm ({h['dominante_pct']:.0f}% dos fundos de viga).",
                'info', 'padrao')
        furo_pct = fv_analise.get('furos_presentes_pct', 0)
        if furo_pct > 60:
            add(f"FV: {furo_pct:.0f}% dos fundos de viga têm furos ativos.", 'info', 'padrao')
        anom = fv_analise.get('anomalias_altura', [])
        if anom:
            add(f"FV: {len(anom)} fundo(s) de viga com altura atípica detectado(s).", 'aviso', 'anomalia')

    # Pavimentos
    pavimentos = resumo.get('pavimentos', [])
    if len(pavimentos) >= 5:
        add(f"Obra com alta verticalidade: {len(pavimentos)} pavimentos processados ({', '.join(sorted(pavimentos)[:3])}…).",
            'info', 'estrutura')
    elif len(pavimentos) > 0:
        add(f"Pavimentos processados: {', '.join(sorted(pavimentos))}.", 'info', 'estrutura')

    # Classes faltando
    esperadas = {'PIL', 'LV', 'FV', 'LAJ'}
    faltando = esperadas - set(classes_presentes)
    if faltando:
        add(f"Classes sem fichas geradas: {', '.join(sorted(faltando))}. Adicione recortes aprovados para estas classes.",
            'aviso', 'cobertura')

    # Volume
    if total >= 500:
        add(f"Grande volume de fichas: {total} elementos processados.", 'info', 'estrutura')
    elif total >= 100:
        add(f"Volume médio: {total} fichas geradas.", 'info', 'estrutura')
    else:
        add(f"Volume baixo: apenas {total} fichas. A obra pode estar parcialmente processada.", 'aviso', 'cobertura')

    return insights


# ── Motor principal ───────────────────────────────────────────────────────────

def consolidar_ficha_obra(obra_name: str, pavimento: str | None = None) -> dict:
    """
    Consolida todas as fichas N2 da obra em análise inteligente.

    Fixes v2:
    - Query com (obra_name=? OR obra_name='') para recortes sem obra
    - Status inclui 'draft', 'approved', 'aprovado' (todos gerados)
    - Análise estatística por classe com anomalias
    - Geração de insights automáticos
    """
    conn = sqlite3.connect(DB_PATH)

    where_pav = "AND pavimento=?" if pavimento else ""
    params = (obra_name, pavimento) if pavimento else (obra_name,)

    rows = conn.execute(f"""
        SELECT classe, elemento_id, campos_json, confianca, status, pavimento
        FROM reverse_eng_fichas
        WHERE (obra_name=? OR obra_name='')
        {where_pav}
        ORDER BY classe, pavimento, elemento_id
    """, params).fetchall()

    conn.close()

    por_classe: dict[str, list] = {}
    pavimentos_encontrados: set[str] = set()
    total_confianca: list[float] = []
    baixa_conf_por_classe: dict[str, int] = {}

    for classe, elem_id, campos_json, conf, status, pav in rows:
        try:
            campos = json.loads(campos_json) if campos_json else {}
        except Exception:
            campos = {}

        cls = (classe or '?').upper()
        por_classe.setdefault(cls, []).append({
            'elemento_id': elem_id,
            'campos': campos,
            'confianca': float(conf or 0),
            'status': status,
            'pavimento': pav,
        })
        if pav:
            pavimentos_encontrados.add(pav)
        if conf:
            total_confianca.append(float(conf))
            if float(conf) < 0.6:
                baixa_conf_por_classe[cls] = baixa_conf_por_classe.get(cls, 0) + 1

    # Estatísticas de alto nível por classe
    stats_por_classe: dict[str, dict] = {}
    for cls, items in por_classe.items():
        confs = [i['confianca'] for i in items if i['confianca']]
        stats_por_classe[cls] = {
            'total': len(items),
            'confianca_media': round(_mean(confs), 3) if confs else 0.0,
            'confianca_min': round(min(confs), 3) if confs else 0.0,
            'confianca_max': round(max(confs), 3) if confs else 0.0,
            'baixa_confianca_count': baixa_conf_por_classe.get(cls, 0),
            'elementos': [i['elemento_id'] for i in items],
            'pavimentos_cobertos': sorted({i['pavimento'] for i in items if i['pavimento']}),
        }

    # Análise detalhada por classe
    analise_por_classe: dict[str, dict] = {}
    for cls, items in por_classe.items():
        if cls == 'PIL':
            analise_por_classe[cls] = {'analise': _analisar_pil(items)}
        elif cls in ('LV', 'FV'):
            analise_por_classe[cls] = {'analise': _analisar_lv_fv(items, cls)}
        elif cls == 'LAJ':
            analise_por_classe[cls] = {'analise': _analisar_laj(items)}

    conf_geral = round(_mean(total_confianca), 3) if total_confianca else 0.0

    resumo_base = {
        'obra_name': obra_name,
        'pavimentos': sorted(pavimentos_encontrados),
        'total_fichas': len(rows),
        'confianca_media_geral': conf_geral,
        'por_classe_stats': stats_por_classe,
        'gerado_em': datetime.now().isoformat(),
    }

    insights = _gerar_insights(resumo_base, analise_por_classe)

    resumo = {
        **resumo_base,
        'por_classe': analise_por_classe,
        'insights': insights,
    }

    return resumo


def salvar_ficha_obra(obra_name: str, pavimento: str, resumo: dict) -> bool:
    """Salva ou atualiza reverse_eng_obra_ficha."""
    stats = resumo.get('por_classe_stats', resumo.get('por_classe', {}))

    def _total(cls: str) -> int:
        v = stats.get(cls, {})
        return v.get('total', 0) if isinstance(v, dict) else 0

    total_pil = _total('PIL')
    total_lv  = _total('LV')
    total_fv  = _total('FV')
    total_laj = _total('LAJ')
    conf_media = resumo.get('confianca_media_geral', 0)

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO reverse_eng_obra_ficha
                (obra_name, pavimento, total_pil, total_lv, total_fv, total_laj,
                 confianca_media, resumo_json, gerado_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(obra_name, pavimento) DO UPDATE SET
                total_pil=excluded.total_pil, total_lv=excluded.total_lv,
                total_fv=excluded.total_fv, total_laj=excluded.total_laj,
                confianca_media=excluded.confianca_media,
                resumo_json=excluded.resumo_json, gerado_at=excluded.gerado_at
        """, (obra_name, pavimento, total_pil, total_lv, total_fv, total_laj,
              conf_media, json.dumps(resumo, ensure_ascii=False), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    except Exception as ex:
        print(f"[motor_reverso_obra] erro DB: {ex}")
        return False


if __name__ == '__main__':
    import sys
    obra = sys.argv[1] if len(sys.argv) > 1 else 'Obra_TREINO_1'
    resumo = consolidar_ficha_obra(obra)
    n_insights = len(resumo.get('insights', []))
    n_fichas = resumo.get('total_fichas', 0)
    print(f"Obra: {obra} | Fichas: {n_fichas} | Insights: {n_insights}")
    for ins in resumo.get('insights', []):
        nivel = ins['nivel'].upper()
        print(f"  [{nivel}] {ins['texto']}")
