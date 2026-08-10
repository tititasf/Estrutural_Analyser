# -*- coding: utf-8 -*-
"""
g2v_harness.py — Harness ÚNICO de veredito VISUAL para todos os gates do Arete
que precisam de olho (não só G2). Nível 2 da hierarquia de validação:
docs/LOOPING-CANONICO.md §1.5 e docs/VISION-VALIDACAO-CAMINHOS.md.

POR QUE ESTE HARNESS É OBRIGATÓRIO: os gates numéricos (G2 paridade, diagnostico_*
N1×N2, paridade_n3_n4) medem matemática — contagens, bbox, valores. São
estruturalmente CEGOS para cota sobre texto, painel torto, sobreposição, hachura
errada, gestalt. Selar/aprovar QUALQUER etapa visual só com número é alucinação de
aprovação (ver incidente do NIM e o bug da sentinela em VISION-VALIDACAO-CAMINHOS.md).
Este harness dá o veredito visual e o REGISTRA — sem ele, "PASS numérico" é candidato,
nunca selagem.

Cobre os 3 pares visuais do Arete (--par):
  n2xn4  (default) G2-V   : recorte N2 (humano) × N4 (robô da ficha N2) — extrator+gerador
  n1xn2            N1-V   : N1 (Structural Analyzer no DXF limpo) × N2 (gabarito) — interpretação SA
  n3xn4            G5-V   : N3 (robô via conversão N1) × N4 (já validado) — vazamento/conversão
A ficha HTML granular contém os cards N1/N2/N3/N4 em SVG. O harness extrai somente
os SVGs do par solicitado; muda só o foco do prompt.

Foco POR CLASSE (CLASSE_FOCUS) — injetado no prompt, aumenta precisão e coerência:
  PIL  VISÃO CIMA + ABCD (faces A/B longas, C/D curtas; subtipo ret/L/U/T→EFGH);
       GRADES sem gabarito N2 → validada à parte pelo dono, grade no N4 comparado = bug.
  LV   VC + Face A + Face B — checar AMBAS as faces; h_A/h_B (bug de round-trip); Para/Passa.
  FV   parte única, SEGMENTAÇÃO crítica (viga contínua = múltiplos segmentos, ref V301 ~16).
  LAJ  parte única, HACHURA DE APOIO (N4 costuma faltar); HLAZ; distinguir apoio de vizinho.

Fonte visual — docs/QA-VISAO-EVIDENCIA-CANONICA.md (dual-mode):
  Agente CLI julga em PNG (render full DXF; vision=pixels). RUÍDO = validação rasa.
  SVG obrigatório no HTML com --persist-db / app / portal web (zoom humano).
  Headless sem persist: pode ser só imagem (dinâmico).
  N2 = recorte DXF full layers (não plot LINE-only).
  html  extrai SVGs da ficha; agente deve rasterizar/PNG vision antes do PASS.
O item é sempre resolvido pelo par canônico (get_recorte_path/get_real_n4_path) —
zero contaminação por vizinho.

Backend de veredito (--backend), plugável, mesmo schema de saída:
  cli    emit-only: gera SVGs + manifesto + stub de veredito vazio para o agente CLI
          ler os vetores e preencher o loop. Não existe backend de API neste harness.

Uso:
    # via agente CLI: gera SVGs + manifesto, o agente lê e preenche
    python g2v_harness.py --classe LAJ --pav 13_PAV --n 5 --backend cli
    python g2v_harness.py --classe PIL --par n1xn2 --item P1 P5 --backend cli
    python g2v_harness.py --classe FV --item V301 --backend cli

Saída: SVGs + manifesto + JSON em scripts/arete/relatorios/g2v/{timestamp}/. Formato
pronto para o "veredito visual REGISTRADO" que a doutrina exige.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from arete_config import RELATORIOS_DIR, PAV_13, GERADORES, ARETE_ROOT
from ficha_adapter import query_fichas, query_ficha_item, get_recorte_path, get_real_n4_path

CLASSES = list(GERADORES.keys())  # ["PIL", "LV", "FV", "LAJ"]

HTML_FICHA_DIRNAME = {"PIL": "pilares", "LV": "laterais_viga", "FV": "fundos_viga", "LAJ": "lajes"}



# ═════════════════════════════════════════════════════════════════════════════
# 1. Prompt canônico — 1 fonte, versionado, parametrizado por par visual
# ═════════════════════════════════════════════════════════════════════════════

# Foco por par: qual comparação é o alvo e o que ela mede (roteia motor_suspeito).
PAR_FOCUS = {
    "n2xn4": (
        "ALVO: N2 (recorte humano, gabarito de conteúdo) × N4 (robô gerado da ficha "
        "extraída de N2). Mede o EXTRATOR N2 + o GERADOR. Divergência → motor_suspeito "
        "'gerador' (N4 desenha errado) ou 'extrator_n2' (ficha saiu errada da extração)."
    ),
    "n1xn2": (
        "ALVO: N1 (Structural Analyzer lendo o DXF estrutural limpo, SEM ver N2) × N2 "
        "(gabarito humano). Mede se a INTERPRETAÇÃO do SA entendeu o desenho: contorno, "
        "posição, forma e SEGMENTAÇÃO detectados. Foque em geometria/quantidade de "
        "segmentos/forma — NÃO em cotagem de estilo. Divergência → motor_suspeito "
        "'interpretacao_n1' (Structural Analyzer / beam_tracer / slab_tracer)."
    ),
    "n3xn4": (
        "ALVO: N3 (robô via conversão N1→Fase-4) × N4 (robô via ficha N2, já validado). "
        "Ambos saem do MESMO gerador — se diferem, é bug de CONVERSÃO N1 ou vazamento. "
        "ATENÇÃO: se N3 'bate' com N4 por ter herdado dado de N2/N4, isso é VAZAMENTO de "
        "gabarito (registre como achado 'vazamento_gabarito', severidade alta). "
        "Divergência → motor_suspeito 'conversao_n1' (Fase-4)."
    ),
    "n3xn2": (
        "ALVO: N3 (robô gerado SOMENTE do contrato N1) × N2 (gabarito humano). "
        "Diagnóstico auxiliar S7 — localiza se a ficha N3 reflete a interpretação N1 "
        "ou se houve desvio na conversão; N2 NUNCA alimenta o motor N3. "
        "Divergência → motor_suspeito 'conversao_n1' ou 'extrator_n2' conforme o achado."
    ),
    "grades": (
        "ALVO: GRADES do PILAR — recorte de grades N2 × N4 GRADES do gerador "
        "(PL_GRADES_preview_*). É a parte GRADES do Modelo de Partes, SÓ para PIL. "
        "IMPORTANTE (granularidade): o recorte de grades é por SHEET do pavimento (todos "
        "os pilares numa folha só, masterplan AR-1'.E), NÃO por pilar. Onde existe recorte "
        "de grades (pavimentos 1º/2º/14º/TÉRREO/TIPO da TREINO_1), há gabarito e vale "
        "veredito visual automático. Onde NÃO existe (ex. 13_PAV), não há par — o DONO "
        "valida olhando só o N4 (Nível 3), não force comparação. Confira: sarrafos de "
        "grade (SARR_2.2x10 etc.), espaçamento, contagem e posição das grades por pilar "
        "na folha. Divergência → motor_suspeito 'gerador'."
    ),
}

# Foco por CLASSE: as partes de cada classe (Modelo de Partes, masterplan §4-A) e os
# defeitos típicos que a visão deve caçar — aumenta precisão e coerência por classe.
CLASSE_FOCUS = {
    "PIL": (
        "CLASSE PILAR — partes: VISÃO CIMA (planta do topo, com a seção) + ABCD (os 4 "
        "painéis de face). Confira: as 4 faces ABCD presentes e proporcionais (faces A/B "
        "são as longas, C/D as curtas); a visão de cima com a seção certa e o subtipo "
        "correto (retangular/L/U/T — se L/U/T, espere faces extras EFGH); nomenclatura "
        "(P##) e seção (ex. 30/60); cotas por face. ATENÇÃO GRADES (parte separada): a "
        "comparação n2xn4 aqui cobre só CIMA+ABCD; GRADES têm seu próprio par ('--par "
        "grades', ver PAR_FOCUS). Nesta imagem, se aparecer geometria de grade/sarrafo "
        "de grade (ex. SARR_2.2x10) no card N4 mas não no N2, marque categoria "
        "'grades_no_n4_comparado' (é bug de SEGREGAÇÃO de partes: grade vazou no N4 de "
        "CIMA+ABCD — NÃO é n4_a_mais legítimo)."
    ),
    "LV": (
        "CLASSE LATERAL DE VIGA — partes: VC (visão de corte) + Face A + Face B. UMA "
        "ficha por viga, mas N3/N4 por lado. Confira AMBAS as faces A e B (não aprove "
        "vendo só uma); segmentos Para/Passa; sarrafo gradeado × sarrafeado; alturas "
        "h_A/h_B por lado (há bug conhecido de round-trip nesses campos — olhe com "
        "atenção se a altura de cada face bate). Painéis por lado com contagem/largura. "
        "RIGOR: contorno Painéis é silhueta quase idêntica (tol ~1–2 cm) — linha extra "
        "no layer Painéis (tick, stub, H duplicada, parede no vão do degrau) = FAIL "
        "alta (n4_a_mais), NÃO 'estilo SCR'. Interior SARR: y-levels e spans. "
        "gate0_geometry FAIL proíbe PASS visual. Cotas: valores legíveis sem colisão. "
        "INVENTÁRIO MÍNIMO OBRIGATÓRIO (docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md): "
        "extrair cada LINE Painéis+SARR (id, rel cm, status MATCH/MISSING/EXTRA/VOID), "
        "cada cota (N2=TEXT numérico em Painéis/COTA; N4=DIMENSION) com valor+posição, "
        "cada texto de identidade. Anexar inventario.path no veredito. "
        "PROIBIDO PASS por contagem de entidades ou 'parece igual'."
    ),
    "FV": (
        "CLASSE FUNDO DE VIGA — parte única, mas SEGMENTAÇÃO é o ponto crítico: uma viga "
        "contínua longa deve ter MÚLTIPLOS segmentos (fronteira em cada mudança de "
        "profundidade/apoio — caso de referência V301, ~16 painéis). Se o N1/N4 mostra 1-2 "
        "segmentos onde o N2 mostra muitos, é subdetecção (categoria 'segmentacao', "
        "direcao 'n4_a_menos', motor_suspeito 'interpretacao_n1'). Confira também "
        "sarrafos (SARR_5cm em viga estreita b<=14) e largura. "
        "RIGOR N1-V / SELO LARANJA (obrigatório): tamanho C×L correto NÃO basta. Cada "
        "contorno N1 (área laranja/laranja do SA) deve estar ALINHADO e POSICIONADO "
        "sobre as linhas estruturais do fundo no DXF (faces longitudinais verdes). "
        "Contorno flutuando paralelo à linha real, com largura certa mas deslocado = "
        "FAIL (categoria 'sobreposicao' ou 'gestalt_geral', motor_suspeito "
        "'interpretacao_n1'). Checklist "
        "contorno_posicao_sobre_estrutural=true só se TODOS os segmentos visíveis "
        "tiverem borda sobreposta às faces DXF; sem isso, PASS e selo laranja são inválidos."
    ),
    "LAJ": (
        "CLASSE LAJE — parte única. Confira: HACHURA DE APOIO nos apoios (pilares/vigas de "
        "borda) — bug conhecido: o N4 costuma NÃO desenhar a hachura de apoio que o N2 tem "
        "(categoria 'hachura_ausente', direcao 'n4_a_menos'); linhas internas de painel; "
        "HLAZ (faixa de união); obstáculos; rótulos de vizinhança (V###, P## com seção); "
        "dimensões comprimento×largura. Distinga hachura de APOIO legítima da laje de "
        "hachura de laje VIZINHA capturada no recorte (essa é contaminação, não conteúdo)."
    ),
}


_BASE_VISUAL_CHECKLIST = (
    "fonte_atual_confirmada",
    "recorte_alvo_preciso",
    "contorno_area_interna",
    "cotas_valores",
    "cotas_posicao_legibilidade",
    "linhas_paineis",
    "hlaz",
    "hachuras_apoio",
    "sem_contaminacao_vizinha",
    "gate0_geometria_ok",
    "svgs_lidos_registrados",
    # Inventário mínimo — proíbe PASS “mais ou menos” / só por contagem
    # (docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md)
    "inventario_minimo_extraido",
    "sem_aprovacao_por_contagem",
)

# Confiança mínima para PASS (FAIL-closed).
PASS_MIN_CONFIANCA = 0.85


def checklist_visual_defaults(classe: str, value: object = None) -> dict[str, object]:
    """Retorna o checklist do gate, incluindo provas que pertencem à classe.

    FV tem apoios locais por segmento e limites globais da viga como famílias
    semânticas distintas. A inspeção SVG precisa vê-los explicitamente: um
    painel com a área certa, mas com o texto de apoio de outra entidade, não
    pode passar S5/G5. As outras classes não herdam esta exigência FV.
    """
    keys = list(_BASE_VISUAL_CHECKLIST)
    if str(classe).upper() == "FV":
        keys.extend(
            (
                "apoios_segmento",
                # Selo laranja N1: tamanho certo com contorno flutuando = FAIL
                "contorno_posicao_sobre_estrutural",
            )
        )
    if str(classe).upper() == "LV":
        keys.extend(
            (
                "face_a_contorno_sem_extra",
                "face_b_contorno_sem_extra",
                "overlay_sem_separacao_visivel",
                "linhas_estruturais_rastreadas",
                "cotas_valores_rastreados",
                "textos_identidade_rastreados",
            )
        )
    return {key: value for key in keys}


def _checklist_prompt_fields(classe: str) -> str:
    fields = checklist_visual_defaults(classe, "true ou false")
    return ",\n    ".join(f'"{key}": {value}' for key, value in fields.items())


_PROMPT_TEMPLATE = """\
Você está dando o VEREDITO VISUAL (Nível 2) da validação Arete — o julgamento que \
o comparador numérico não consegue dar sozinho (ele é cego para posição, \
sobreposição, esquadro e gestalt).

{par_focus}

{classe_focus}

Os SVGs vêm em cartões vetoriais: [N1] contexto do Structural Analyzer | [N2] recorte
humano | [N3] robô via conversão N1 | [N4] robô via ficha N2. Compare o par do ALVO
acima; os outros cards são contexto. Leia cada SVG indicado no manifesto.

Regra de conteúdo: julgue MESMO CONTEÚDO SEMÂNTICO, não traço idêntico. O robô desenha
no estilo-padrão SCR; não penalize diferença de estilo. Confira contagem e tamanho
aproximado de painéis/sarrafos/chapas, valores de cota (não a geometria do traço),
textos, e hachura presente onde deve (ausente onde não deve).

Procure o que o número não vê: cota/texto sobreposto (ilegível), elemento torto/fora de
esquadro, sobreposição indevida, hachura ausente/extra, gestalt errado. Se o card do
gabarito contiver elementos de OUTRO item (nome de viga/pilar/laje diferente), é
contaminação da EXTRAÇÃO DA IMAGEM (categoria 'contaminacao_recorte'), não defeito do
elemento avaliado.

REGRA DE VETO: PASS exige confirmar TODOS os itens do checklist_visual. Para LAJ,
contorno/área interna, quantidade e POSIÇÃO de cada cota, legibilidade, linhas de
painel, HLAZ e hachuras são independentes. Acertar somente comprimento×largura ou o
bbox nunca basta. Qualquer campo falso/não verificável, nota humana ainda visível,
contaminação ou fonte desatualizada proíbe PASS.

VISÃO CANÓNICA (docs/QA-VISAO-EVIDENCIA-CANONICA.md):
agente: ler PNG full-render (camadas + cotas + hatch). Humano/web: SVG.
Extract LINE-only NÃO é N2 do CE. Validação rasa = ruído.

INVENTÁRIO MÍNIMO (obrigatório — ver docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md):
antes do veredito, extrair e anexar rastreio linha/cota/texto (não só contagem).
PASS com checklist true mas sem bloco "inventario" (path de JSON/MD) é inválido.
Achados devem citar id de inventário quando o defeito for geométrico/cota
(ex. "A-L0009 MISSING_N4", "cota 50.5 sem equivalente granular").

PRECISÃO PARA AJUSTE DE MOTOR (obrigatória em cada achado):
- parte: onde está o defeito — CIMA/ABCD/face_A/face_B/segmento_N/laje_inteira/geral
- direcao: 'n4_a_mais' (o candidato tem elemento que o gabarito NÃO tem → gerador criou
  lixo) | 'n4_a_menos' (falta no candidato o que o gabarito tem → extrator/motor perdeu)
  | 'divergente' (existe nos dois mas diferente) | 'na'
- motor_suspeito: gerador | extrator_n2 | interpretacao_n1 | conversao_n1 | indefinido

Responda APENAS com JSON válido, sem texto fora do JSON:
{{
  "veredito": "PASS ou FAIL ou SUSPEITO",
  "confianca": 0.0 a 1.0,
  "checklist_visual": {{
    {checklist_fields}
  }},
  "inventario": {{
    "path": "path/do/trace_ou_inventory.json",
    "md": "path/opcional.md",
    "partes": ["face_A"],
    "summary": {{"lines": {{}}, "cotas": {{}}, "texts": {{}}}}
  }},
  "achados": [
    {{"categoria": "cota_sobreposta|painel_torto|sobreposicao|hachura_ausente|hachura_extra|segmentacao|gestalt_geral|contaminacao_recorte|vazamento_gabarito|inventario_gap|outro",
      "parte": "...", "direcao": "n4_a_mais|n4_a_menos|divergente|na",
      "motor_suspeito": "gerador|extrator_n2|interpretacao_n1|conversao_n1|indefinido",
      "n2_id": "id do inventário se houver",
      "descricao": "texto curto", "severidade": "baixa|media|alta"}}
  ],
  "resumo": "1-2 frases"
}}"""


def build_prompt(par: str, classe: str = "") -> str:
    return _PROMPT_TEMPLATE.format(
        par_focus=PAR_FOCUS.get(par, PAR_FOCUS["n2xn4"]),
        classe_focus=CLASSE_FOCUS.get(classe, ""),
        checklist_fields=_checklist_prompt_fields(classe),
    )


# ═════════════════════════════════════════════════════════════════════════════
# 3. Backend visual — SVG fonte, sem raster e sem API
# ═════════════════════════════════════════════════════════════════════════════

def avaliar_cli(svg_paths: list[Path], prompt: str, manifesto_svg: Path, classe: str = "") -> dict:
    """Emite a evidência SVG vetorial para leitura do agente CLI.

    SVG é a fonte de verdade visual: mantém texto, cotas, camadas e geometria
    selecionável. O harness não materializa PNG e não chama nenhuma API visual.
    """
    return {
        "_backend": "cli",
        "aguardando_agente": True,
        "svgs_para_ler": [str(path) for path in svg_paths],
        "manifesto_svg": str(manifesto_svg),
        "prompt": prompt,
        "veredito": None, "confianca": None, "achados": [], "resumo": "",
        "checklist_visual": checklist_visual_defaults(classe),
        "_instrucao": "Agente CLI: leia todos os svgs_para_ler e o manifesto_svg, aplique o prompt e preencha "
                      "checklist_visual/veredito/confianca/achados/resumo. PASS com "
                      "qualquer checklist diferente de true é inválido.",
    }
BACKENDS = {"cli": avaliar_cli}


# ═════════════════════════════════════════════════════════════════════════════
# 4. Fonte de imagem — ficha HTML (preferida) com fallback pro render DXF cru
# ═════════════════════════════════════════════════════════════════════════════

def resolver_html_ficha(
    obra_name: str,
    classe: str,
    elemento_id: str,
    lista_lv: str = "passa",
) -> Path | None:
    """
    Acha o HTML da ficha granular mais recente para este item, varrendo os
    runs timestampados de scripts/arete/html_fichas/{obra}/*/ do mais novo
    pro mais velho. Cada run só gera as classes pedidas naquele ciclo, então
    nem todo run tem toda pasta de classe — por isso a varredura, não um
    path fixo.
    """
    base = ARETE_ROOT / "html_fichas" / obra_name
    dirname = HTML_FICHA_DIRNAME.get(classe)
    if not base.is_dir() or not dirname:
        return None
    runs = sorted((d for d in base.iterdir() if d.is_dir()),
                  key=lambda d: d.stat().st_mtime, reverse=True)
    # O manifest é publicado ao fim do headless. Evite consumir um run ainda
    # sendo escrito por outra sessão; só caia para runs sem manifest quando
    # não existir nenhum run concluído no workspace.
    completed_runs = [run for run in runs if (run / "arete_manifest.json").exists()]
    if completed_runs:
        runs = completed_runs
    for run in runs:
        class_dirs = [run / dirname]
        if classe == "PIL":
            # PIL agrupa as fichas por comportamento (NASCE/SEGUE/MORRE) e
            # mantém os subtipos não-retangulares em pilares_especiais/.
            class_dirs.append(run / "pilares_especiais")

        for class_dir in class_dirs:
            if not class_dir.is_dir():
                continue
            if classe == "LV":
                behavior = str(lista_lv or "passa").strip().lower()
                suffix = behavior.capitalize()
                candidate = (
                    class_dir
                    / f"LV-{behavior.upper()}"
                    / f"{elemento_id}-{suffix}.html"
                )
                if candidate.exists():
                    return candidate
            candidate = class_dir / f"{elemento_id}.html"
            if candidate.exists():
                return candidate
            matches = sorted(class_dir.rglob(f"{elemento_id}.html"))
            if matches:
                return matches[0]
    return None


def export_evidence_svgs(html_path: Path, out_dir: Path, stem: str,
                         par: str = "n2xn4") -> tuple[list[Path], Path] | None:
    """Extrai SVGs já presentes na ficha, sem rasterizar ou alterar a ficha fonte."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    wanted_stages = {
        "n1xn2": ["N1", "N2"],
        "n2xn4": ["N2", "N4"],
        "n3xn4": ["N3", "N4"],
        "n3xn2": ["N3", "N2"],
        "grades": ["N4"],
    }.get(par, ["N1", "N2", "N3", "N4"])
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(f"file:///{html_path.as_posix()}", timeout=15_000)
            cards = page.evaluate(
                """(wanted => Array.from(document.querySelectorAll('.evidence-card'))
                  .flatMap((card, cardIndex) => {
                    const title = card.querySelector('.evidence-title b');
                    const stage = title && title.textContent.trim().toUpperCase().match(/^N[1-4]/);
                    if (!stage || !wanted.includes(stage[0])) return [];
                    return Array.from(card.querySelectorAll('svg')).map((svg, svgIndex) => ({
                      stage: stage[0], card_index: cardIndex, svg_index: svgIndex,
                      label: (title.textContent || stage[0]).trim(),
                      aria_label: svg.getAttribute('aria-label') || '',
                      source_svg: svg.outerHTML,
                    }));
                  }))""",
                wanted_stages,
            )
        except Exception as exc:
            print(f"  [WARN] Falha ao extrair SVG da ficha {html_path.name}: {exc}")
            return None
        finally:
            browser.close()

    if not cards:
        return None
    exported: list[Path] = []
    manifest_cards: list[dict] = []
    for index, card in enumerate(cards, start=1):
        svg_text = str(card["source_svg"]).strip()
        if not svg_text.startswith("<svg"):
            continue
        stage = re.sub(r"[^A-Za-z0-9_-]+", "_", str(card["stage"]))
        target = out_dir / f"{stem}_{index:02d}_{stage}.svg"
        target.write_text('<?xml version="1.0" encoding="utf-8"?>\n' + svg_text, encoding="utf-8")
        exported.append(target)
        manifest_cards.append({
            "path": str(target), "stage": card["stage"], "label": card["label"],
            "aria_label": card["aria_label"], "source_html": str(html_path),
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        })
    if not exported:
        return None
    manifest = out_dir / f"{stem}_svg_manifest.json"
    manifest.write_text(json.dumps({
        "format": "svg-evidence-v1", "pair": par, "source_html": str(html_path),
        "cards": manifest_cards,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return exported, manifest


# ═════════════════════════════════════════════════════════════════════════════
# 5. Núcleo — 1 item, N backends
# ═════════════════════════════════════════════════════════════════════════════

def _file_evidence(path: Path) -> dict:
    stat = path.stat()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _inventario_path_ok(veredito: dict) -> tuple[bool, str]:
    """Exige bloco inventario com path de arquivo de rastreio existente."""
    inv = veredito.get("inventario")
    if not isinstance(inv, dict) or not inv:
        return (
            False,
            "PASS inválido; falta bloco inventario "
            "(docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md)",
        )
    path_raw = inv.get("path") or inv.get("trace") or inv.get("json")
    if not path_raw:
        return False, "PASS inválido; inventario.path ausente"
    p = Path(str(path_raw))
    if not p.is_file():
        return False, f"PASS inválido; inventario.path não existe: {p}"
    return True, ""


def validar_veredito_cli(veredito: dict) -> tuple[bool, str]:
    """Veto mecânico FAIL-closed: PASS exige checklist, confiança, gate0, leitura e inventário.

    Portão 0 (gate0_geometry): se presente e status != PASS, proíbe PASS visual.
    Portão 1: checklist todo True + confianca >= PASS_MIN_CONFIANCA + svgs_lidos.
    Portão inventário: path de rastreio linha/cota/texto (proíbe PASS por contagem).
    """
    verdict = str(veredito.get("veredito") or "").upper()
    checklist = veredito.get("checklist_visual") or {}
    if verdict == "PASS":
        missing = [key for key, value in checklist.items() if value is not True]
        if not checklist or missing:
            return False, f"PASS inválido; checklist pendente/falso: {missing or ['todos']}"
        try:
            conf = float(veredito.get("confianca"))
        except (TypeError, ValueError):
            conf = -1.0
        if conf < PASS_MIN_CONFIANCA:
            return False, (
                f"PASS inválido; confianca={veredito.get('confianca')} "
                f"< {PASS_MIN_CONFIANCA}"
            )
        gate0 = veredito.get("gate0") or veredito.get("gate0_geometry")
        if gate0 is not None:
            g_status = str(gate0.get("status") or "").upper()
            if g_status != "PASS" or gate0.get("pass_allowed") is False:
                return False, (
                    f"PASS inválido; gate0={g_status or '?'} "
                    f"reasons={gate0.get('reasons') or []}"
                )
            if checklist.get("gate0_geometria_ok") is not True:
                return False, "PASS inválido; checklist.gate0_geometria_ok deve ser true"
        para_ler = list(veredito.get("svgs_para_ler") or [])
        lidos = list(veredito.get("svgs_lidos") or [])
        if para_ler:
            if not lidos:
                return False, "PASS inválido; preencha svgs_lidos com paths realmente lidos"
            if checklist.get("svgs_lidos_registrados") is not True:
                return False, "PASS inválido; checklist.svgs_lidos_registrados deve ser true"
            lidos_norm = {str(Path(p)) for p in lidos}
            para_norm = {str(Path(p)) for p in para_ler}
            if not (lidos_norm & para_norm) and not (
                set(map(str, lidos)) & set(map(str, para_ler))
            ):
                return False, "PASS inválido; svgs_lidos não intersecta svgs_para_ler"
        # Inventário mínimo (docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md)
        if "inventario_minimo_extraido" in checklist:
            if checklist.get("inventario_minimo_extraido") is not True:
                return False, "PASS inválido; checklist.inventario_minimo_extraido deve ser true"
            if checklist.get("sem_aprovacao_por_contagem") is not True:
                return False, "PASS inválido; checklist.sem_aprovacao_por_contagem deve ser true"
            ok_inv, reason_inv = _inventario_path_ok(veredito)
            if not ok_inv:
                return False, reason_inv
        classe = str(veredito.get("classe") or "").upper()
        if classe == "LV":
            for key in (
                "linhas_estruturais_rastreadas",
                "cotas_valores_rastreados",
                "textos_identidade_rastreados",
            ):
                if key in checklist and checklist.get(key) is not True:
                    return False, f"PASS inválido; checklist.{key} deve ser true"
        if classe == "FV":
            # Selo laranja N1 exige prova visual de posição no estrutural —
            # largura/vão corretos com contorno flutuante não autorizam PASS.
            for key in (
                "contorno_posicao_sobre_estrutural",
                "apoios_segmento",
            ):
                if key in checklist and checklist.get(key) is not True:
                    return False, f"PASS inválido; checklist.{key} deve ser true"
    if verdict == "FAIL" and not (veredito.get("achados") or []):
        return False, "FAIL inválido; registre ao menos um achado acionável"
    return verdict in {"PASS", "FAIL", "SUSPEITO"}, ""


def _infer_n4_face_origin_y(n4_path: Path, h_face: float) -> float:
    """Origem Y do corpo da face no VIEW_A (y0 do draw_lv_face)."""
    # Layout dedicado: y_baseline = y_top-150, y0 = y_baseline - h_face (y_top≈0).
    expected = -150.0 - float(h_face or 0)
    try:
        import ezdxf
        doc = ezdxf.readfile(str(n4_path))
        ys = []
        for e in doc.modelspace():
            if e.dxftype() != "LINE":
                continue
            if not str(e.dxf.layer).startswith("Pain") and e.dxf.layer != "Painéis":
                continue
            ys.extend([e.dxf.start.y, e.dxf.end.y])
        if ys:
            y_min = min(ys)
            # Corpo costuma ser o piso mais baixo entre y_min e y_min+h (ignora cotas abaixo)
            # Preferir expected se estiver perto do y_min de painéis.
            if abs(y_min - expected) < 40:
                return expected
            return float(y_min)
    except Exception:
        pass
    return expected


def run_gate0_lv_face_a(
    recorte_path: Path,
    n4_view_a: Path,
    elemento_id: str,
) -> dict | None:
    """Compara Painéis+SARR da face A (N2 recorte × N4 VIEW_A). None se não aplicável."""
    try:
        from g2v_gate0_geometry import gate0_n2_n4_files, write_gate0_report
    except ImportError:
        from scripts.arete.g2v_gate0_geometry import (  # type: ignore
            gate0_n2_n4_files,
            write_gate0_report,
        )
    try:
        import importlib.util
        import contextlib
        import io
        import sqlite3

        # ARETE_ROOT = .../scripts/arete → parent = scripts/
        scripts_dir = ARETE_ROOT.parent
        motor_path = scripts_dir / "motor_reverso_lv.py"
        lv_path = scripts_dir / "gerar_lv_dxf_stog.py"
        if not motor_path.is_file():
            motor_path = Path(__file__).resolve().parents[1] / "motor_reverso_lv.py"
        if not lv_path.is_file():
            lv_path = Path(__file__).resolve().parents[1] / "gerar_lv_dxf_stog.py"

        def _load(path: Path, name: str):
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            # gerar_lv_dxf_stog re-wrapa sys.stdout.buffer — não redirecionar.
            spec.loader.exec_module(mod)
            return mod

        if not motor_path.is_file() or not lv_path.is_file():
            return {
                "schema": "arete.g2v_gate0_geometry/v1",
                "status": "SKIP",
                "pass_allowed": True,
                "reasons": ["motor/gerador LV indisponível para origem da face"],
            }
        motor = _load(motor_path, "motor_reverso_lv_gate0")
        lv = _load(lv_path, "gerar_lv_dxf_stog_gate0")
        ficha = motor.extrair_ficha_lateral_viga(str(recorte_path), f"{elemento_id}_A")
        units = lv.select_canonical_face_units(ficha.get("face_units") or [])
        unit_a = next(
            (
                u
                for u in units
                if str(u.get("label", "")).upper().endswith(".A")
                or str(u.get("side", "")).upper() == "A"
            ),
            units[0] if units else None,
        )
        if not unit_a:
            return {
                "schema": "arete.g2v_gate0_geometry/v1",
                "status": "SKIP",
                "pass_allowed": True,
                "reasons": ["face_unit A não encontrada"],
            }
        bbox = unit_a.get("bbox") or {}
        x0 = float(unit_a.get("x_left") or bbox.get("x_left") or 0)
        y0 = float(unit_a.get("y_bot") or bbox.get("y_bot") or 0)
        h = float(unit_a.get("h_body") or unit_a.get("h_total") or 0)
        # face_units canônicas às vezes não trazem coords absolutas — fallback pair
        if abs(x0) < 1.0 and abs(y0) < 1.0:
            face_a = ficha.get("face_A") or ficha.get("face_a") or {}
            if face_a:
                x0 = float(face_a.get("x_left") or x0)
                y0 = float(face_a.get("y_bot") or y0)
                h = float(face_a.get("h_body") or h)
        pans = unit_a.get("panels") or unit_a.get("segments") or []
        w = sum(
            float(p.get("width", p.get("largura_cm", 0)) or 0) for p in pans
        )
        if w <= 0 or h <= 0:
            return {
                "schema": "arete.g2v_gate0_geometry/v1",
                "status": "SKIP",
                "pass_allowed": True,
                "reasons": ["largura/altura face A inválida"],
            }
        n4_y0 = _infer_n4_face_origin_y(n4_view_a, h)
        clip = (-5.0, -5.0, w + 20.0, h + 40.0)
        result = gate0_n2_n4_files(
            recorte_path,
            n4_view_a,
            n2_origin=(x0, y0),
            n4_origin=(0.0, n4_y0),
            clip=clip,
        )
        result["face_label"] = unit_a.get("label")
        result["face_w"] = w
        result["face_h"] = h
        return result
    except Exception as exc:
        return {
            "schema": "arete.g2v_gate0_geometry/v1",
            "status": "ERROR",
            "pass_allowed": False,
            "reasons": [f"gate0 exception: {exc}"],
        }


def avaliar_item(row: dict, backends: list[str], out_dir: Path,
                 fonte_imagem: str = "html", par: str = "n2xn4",
                 n3_dir: Path | None = None, lista_lv: str = "passa") -> dict:
    """
    Resolve o par canônico do item, exporta a evidência SVG vetorial da ficha e
    prepara o veredito CLI para o par pedido.
    """
    classe = row["classe"]
    elemento_id = row["elemento_id"]
    obra_name = row["obra_name"]
    prompt = build_prompt(par, classe)

    resultado = {
        "classe": classe, "elemento_id": elemento_id, "pavimento": row.get("pavimento"),
        "par": par, "recorte_path": None, "n3_path": None,
        "n4_path": None, "svg_paths": [], "svg_manifest_path": None,
        "vereditos": {}, "erro": None,
    }

    recorte_path = get_recorte_path(elemento_id, classe, row=row)
    if recorte_path is None or not recorte_path.exists():
        resultado["erro"] = f"Recorte (N2) não encontrado para {classe} {elemento_id}"
        return resultado
    resultado["recorte_path"] = str(recorte_path)

    # N4 só é obrigatório nos pares que o envolvem (n2xn4, n3xn4).
    n4_path = get_real_n4_path(obra_name, classe, elemento_id)
    if classe == "LV":
        # LV is a three-view evidence set.  Do not let a legacy combined DXF
        # stand in for Corte/A/B when recording a visual verdict.
        n4_dir = n4_path.parent
        n4_views = [
            n4_dir / f"LV_preview_{elemento_id}_CORTE.dxf",
            n4_dir / f"LV_preview_{elemento_id}_VIEW_A.dxf",
            n4_dir / f"LV_preview_{elemento_id}_VIEW_B.dxf",
        ]
        missing_n4_views = [path for path in n4_views if not path.is_file()]
        if missing_n4_views:
            resultado["erro"] = "N4 LV incompleto: " + ", ".join(
                str(path) for path in missing_n4_views
            )
            return resultado
        resultado["n4_views"] = [str(path.resolve()) for path in n4_views]
        # Keep the established scalar field for callers, now pointing to Corte.
        n4_path = n4_views[0]
    if par in ("n2xn4", "n3xn4"):
        if not n4_path.exists():
            resultado["erro"] = f"N4 não encontrado: {n4_path} (gerar N4 antes de avaliar)"
            return resultado
        resultado["n4_path"] = str(n4_path)
        resultado["evidencia_fontes"] = {
            "n2": _file_evidence(recorte_path),
            "n4": _file_evidence(n4_path),
        }

    # Portão 0: geometria N2×N4 (LV face A) — FAIL-closed quando aplicável
    if par == "n2xn4" and classe == "LV":
        views = resultado.get("n4_views") or []
        # ordem: CORTE, VIEW_A, VIEW_B
        n4_a = Path(views[1]) if len(views) > 1 else Path()
        if not n4_a.is_file() and n4_path:
            n4_a = Path(n4_path).parent / f"LV_preview_{elemento_id}_VIEW_A.dxf"
        if n4_a.is_file():
            gate0 = run_gate0_lv_face_a(Path(recorte_path), n4_a, elemento_id)
            if gate0:
                resultado["gate0"] = gate0
                try:
                    from g2v_gate0_geometry import write_gate0_report
                except ImportError:
                    write_gate0_report = None  # type: ignore
                if write_gate0_report:
                    write_gate0_report(
                        gate0, out_dir / f"{classe}_{elemento_id}_gate0.json"
                    )

    n3_path = None
    if par in ("n3xn4", "n3xn2") and n3_dir is not None:
        if classe == "LV":
            behavior = str(lista_lv or "passa").strip().capitalize()
            lv_views = [
                n3_dir / f"LV_preview_{elemento_id}_{behavior}_CORTE.dxf",
                n3_dir / f"LV_preview_{elemento_id}_{behavior}_VIEW_A.dxf",
                n3_dir / f"LV_preview_{elemento_id}_{behavior}_VIEW_B.dxf",
            ]
            existing_lv_views = [path for path in lv_views if path.is_file()]
            resultado["n3_views"] = [str(path.resolve()) for path in existing_lv_views]
            if fonte_imagem == "dxf":
                # LV não tem um único DXF N3: corte, A e B são três contratos
                # visuais. Escolher o primeiro glob poderia selecionar FV do
                # mesmo Vxxx e tornar o veredito inválido.
                resultado["erro"] = (
                    "N3 LV em DXF possui Corte/A/B independentes; use --fonte-imagem html "
                    "para revisar as três vistas, nunca o fallback de arquivo único."
                )
                return resultado
        else:
            candidates = [
                n3_dir / f"LJ_preview_{elemento_id}.dxf",
                n3_dir / f"{elemento_id}.dxf",
            ]
            n3_path = next((path for path in candidates if path.is_file()), None)
            if n3_path is None:
                matches = sorted(n3_dir.glob(f"*{elemento_id}*.dxf"))
                n3_path = matches[0] if matches else None
            if n3_path is None:
                resultado["erro"] = f"N3 do run não encontrado em {n3_dir}: {elemento_id}"
                return resultado
            resultado["n3_path"] = str(n3_path.resolve())
            resultado.setdefault("evidencia_fontes", {})["n3"] = _file_evidence(n3_path)

    if fonte_imagem != "html":
        resultado["erro"] = (
            "O gate visual é SVG-only: --fonte-imagem dxf não é aceito porque "
            "renderiza raster. Gere a ficha HTML/SVG canônica do item."
        )
        return resultado
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = resolver_html_ficha(
        obra_name, classe, elemento_id, lista_lv=lista_lv
    )
    if html_path is None:
        resultado["erro"] = "Ficha HTML/SVG canônica indisponível; gere-a antes do gate visual."
        return resultado
    evidence = export_evidence_svgs(
        html_path, out_dir, f"{classe}_{elemento_id}_{par}", par=par
    )
    if evidence is None:
        resultado["erro"] = "Ficha não contém SVGs vetoriais para o par solicitado."
        return resultado
    svg_paths, manifest_path = evidence
    resultado.update({
        "fonte_imagem": "html_svg_vetorial", "html_path": str(html_path),
        "svg_paths": [str(path) for path in svg_paths],
        "svg_manifest_path": str(manifest_path),
    })

    for backend in backends:
        v = BACKENDS[backend](svg_paths, prompt, manifest_path, classe)
        if resultado.get("gate0"):
            v["gate0"] = resultado["gate0"]
            v["_instrucao"] = (
                (v.get("_instrucao") or "")
                + " GATE0 (geometria): status="
                + str(resultado["gate0"].get("status"))
                + " — PASS visual PROIBIDO se gate0 != PASS. "
                "Preencha svgs_lidos e checklist (incl. gate0_geometria_ok)."
            )
        resultado["vereditos"][backend] = v

    return resultado


# ═════════════════════════════════════════════════════════════════════════════
# 5. CLI
# ═════════════════════════════════════════════════════════════════════════════

def _resolver_itens(classe: str, pav: str, itens: list[str] | None, n: int | None) -> list[dict]:
    if itens:
        rows = []
        for eid in itens:
            row = query_ficha_item(classe, eid, pavimento=pav)
            if row is None:
                print(f"  [WARN] {classe} {eid} não encontrado em {pav} — pulando")
                continue
            rows.append(row)
        return rows
    all_rows = query_fichas(classe, pavimento=pav)
    return all_rows[:n] if n else all_rows


def main():
    parser = argparse.ArgumentParser(
        description="Harness de veredito VISUAL SVG do Arete (G2-V/N1-V/G5-V); "
                    "default cli = agente lê SVGs vetoriais")
    parser.add_argument("--classe", required=True, choices=CLASSES)
    parser.add_argument("--pav", default=PAV_13)
    parser.add_argument("--par", default="n2xn4", choices=list(PAR_FOCUS.keys()),
                        help="n2xn4=G2-V (default) | n1xn2=N1-V | n3xn4=G5-V | "
                             "n3xn2=S7 N3×N2 | grades=GRADES-V (só PIL)")
    parser.add_argument("--item", nargs="+", default=None, help="elemento_id específico(s), ex: V13 V16")
    parser.add_argument("--n", type=int, default=None, help="Avaliar os N primeiros itens da classe/pav")
    parser.add_argument("--backend", nargs="+", default=["cli"], choices=["cli"],
                        help="cli (único): emit-only para o agente ler SVGs vetoriais.")
    parser.add_argument("--fonte-imagem", default="html", choices=["html"],
                        help="html = extrai SVGs vetoriais da ficha granular (única fonte aceita)")
    parser.add_argument(
        "--lista-lv",
        default="passa",
        choices=["para", "passa"],
        help="Lista HTML de LV usada no veredito. Default passa (N2/N4 do 13_PAV); "
        "use para somente na validação humana da lista Para.",
    )
    parser.add_argument("--n3-dir", default=None,
                        help="Diretório dos DXFs N3 do run alvo quando a ficha N3 não estiver no run HTML.")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    n3_dir = Path(args.n3_dir).resolve() if args.n3_dir else None
    # GRADES é parte só de PIL (Modelo de Partes §4-A).
    if args.par == "grades" and args.classe != "PIL":
        print(f"[ERRO] --par grades só existe para PIL (é a parte GRADES do pilar); "
              f"--classe {args.classe} não tem grades.")
        return 2

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else RELATORIOS_DIR / "g2v" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _resolver_itens(args.classe, args.pav, args.item, args.n)
    if not rows:
        print("[ERRO] Nenhum item resolvido — confira --classe/--pav/--item/--n")
        return 1

    gate = {"n2xn4": "G2-V", "n1xn2": "N1-V", "n3xn4": "G5-V",
            "n3xn2": "S7-N3N2", "grades": "GRADES-V"}.get(args.par, args.par)
    print(f"\n{'='*70}")
    print(f"HARNESS VISUAL — {gate} ({args.par}) — {args.classe} {args.pav} — "
          f"{len(rows)} item(ns) — backends: {args.backend}")
    print(f"{'='*70}")

    resultados = []
    for row in rows:
        r = avaliar_item(
            row, args.backend, out_dir, fonte_imagem=args.fonte_imagem,
            par=args.par, n3_dir=n3_dir, lista_lv=args.lista_lv,
        )
        resultados.append(r)
        if r["erro"]:
            print(f"  {r['classe']} {r['elemento_id']}: BLOCKED — {r['erro']}")
        else:
            for backend, v in r["vereditos"].items():
                if v.get("aguardando_agente"):
                    print(f"  {r['classe']} {r['elemento_id']} [cli]: SVGs prontos -> "
                          f"{', '.join(v['svgs_para_ler'])} (agente lê e preenche)")
                else:
                    print(f"  {r['classe']} {r['elemento_id']} [{backend}]: "
                          f"{v.get('veredito','?')} (confiança={v.get('confianca','?')}, "
                          f"{len(v.get('achados', []))} achado(s), {v.get('_latencia_s','?')}s)")

    relatorio_path = out_dir / "relatorio.json"
    relatorio_path.write_text(
        json.dumps({"classe": args.classe, "pavimento": args.pav, "par": args.par,
                    "lista_lv": args.lista_lv if args.classe == "LV" else None,
                    "gate": gate, "backends": args.backend, "timestamp": ts,
                    "itens": resultados}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nRelatório: {relatorio_path}")
    print(f"SVGs:      {out_dir}")
    if "cli" in args.backend:
        print("\n>>> Backend CLI: os SVGs vetoriais estão prontos. O AGENTE (Claude Code/Codex) "
              "deve LER cada SVG e preencher veredito/achados no relatorio.json. "
              "Sem esse passo, NÃO há veredito visual — não selar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
