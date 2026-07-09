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
A ficha HTML granular mostra os 4 cards N1/N2/N3/N4 juntos, então UMA imagem serve
qualquer par; muda só o foco do prompt.

Foco POR CLASSE (CLASSE_FOCUS) — injetado no prompt, aumenta precisão e coerência:
  PIL  VISÃO CIMA + ABCD (faces A/B longas, C/D curtas; subtipo ret/L/U/T→EFGH);
       GRADES sem gabarito N2 → validada à parte pelo dono, grade no N4 comparado = bug.
  LV   VC + Face A + Face B — checar AMBAS as faces; h_A/h_B (bug de round-trip); Para/Passa.
  FV   parte única, SEGMENTAÇÃO crítica (viga contínua = múltiplos segmentos, ref V301 ~16).
  LAJ  parte única, HACHURA DE APOIO (N4 costuma faltar); HLAZ; distinguir apoio de vizinho.

Fonte de imagem (--fonte-imagem, default "html"):
  html  Screenshot da ficha HTML granular (.evidence-grid, N1/N2/N3/N4) via
        playwright_loop — legível, com contexto, e SEM o bug de sentinela x=-9000/
        CARIMBO do render DXF cru (VISION-VALIDACAO-CAMINHOS.md §5). Suporta os 3 pares.
  dxf   render_comparacao(recorte, N4) — só n2xn4; fallback quando não há ficha HTML.
O item é sempre resolvido pelo par canônico (get_recorte_path/get_real_n4_path) —
zero contaminação por vizinho.

Backend de veredito (--backend), plugável, mesmo schema de saída:
  cli    (RECOMENDADO) emit-only: gera a imagem + um stub de veredito VAZIO + o prompt,
          para o AGENTE de chat CLI (Claude Code / Codex) LER a imagem e preencher no
          loop. É a ÚNICA via de qualidade comprovada hoje (VISION-VALIDACAO-CAMINHOS.md §1).
  claude API Anthropic (precisa de billing/chave) — NÃO é o mesmo que a visão do agente
          CLI; candidato a batch autônomo FUTURO, só após protocolo de calibração.
  gemini API Google (precisa de billing) — idem, candidato futuro.
  nim    NVIDIA NIM — REPROVADO (4/4 falhas, chegou a inverter achado). Mantido só para
          comparação empírica; nunca como validador de selagem.

Uso:
    # via agente CLI (recomendado): gera imagens + stubs, o agente lê e preenche
    python g2v_harness.py --classe LAJ --pav 13_PAV --n 5 --backend cli
    python g2v_harness.py --classe PIL --par n1xn2 --item P1 P5 --backend cli
    # comparação empírica de APIs (quando houver billing)
    python g2v_harness.py --classe FV --item V301 --backend claude gemini

Saída: JSON em scripts/arete/relatorios/g2v/{timestamp}/relatorio.json + resumo no
console. Formato pronto para o "veredito visual REGISTRADO" que a doutrina exige.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from arete_config import RELATORIOS_DIR, PAV_13, GERADORES, ARETE_ROOT
from ficha_adapter import query_fichas, query_ficha_item, get_recorte_path, get_real_n4_path
from paridade_visual import render_comparacao

CLASSES = list(GERADORES.keys())  # ["PIL", "LV", "FV", "LAJ"]

HTML_FICHA_DIRNAME = {"PIL": "pilares", "LV": "laterais_viga", "FV": "fundos_viga", "LAJ": "lajes"}

NVIDIA_BASE_URL  = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL_DEF = "meta/llama-3.2-90b-vision-instruct"
CLAUDE_MODEL_DEF = "claude-opus-4-8"
GEMINI_MODEL_DEF = "gemini-2.5-pro"
GEMINI_BASE_URL  = "https://generativelanguage.googleapis.com/v1beta/models"


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
        "atenção se a altura de cada face bate). Painéis por lado com contagem/largura."
    ),
    "FV": (
        "CLASSE FUNDO DE VIGA — parte única, mas SEGMENTAÇÃO é o ponto crítico: uma viga "
        "contínua longa deve ter MÚLTIPLOS segmentos (fronteira em cada mudança de "
        "profundidade/apoio — caso de referência V301, ~16 painéis). Se o N1/N4 mostra 1-2 "
        "segmentos onde o N2 mostra muitos, é subdetecção (categoria 'segmentacao', "
        "direcao 'n4_a_menos', motor_suspeito 'interpretacao_n1'). Confira também "
        "sarrafos (SARR_5cm em viga estreita b<=14) e largura."
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

_PROMPT_TEMPLATE = """\
Você está dando o VEREDITO VISUAL (Nível 2) da validação Arete — o julgamento que \
o comparador numérico não consegue dar sozinho (ele é cego para posição, \
sobreposição, esquadro e gestalt).

{par_focus}

{classe_focus}

A imagem pode vir em 2 formatos:
(a) 3 painéis lado a lado: [1] recorte N2 | [2] N4 | [3] overlay (verde=N2, vermelho=N4).
(b) Cartões empilhados (ficha HTML): [N1] contexto do Structural Analyzer | [N2] recorte
    humano | [N3] robô via conversão N1 | [N4] robô via ficha N2. Compare o par do ALVO
    acima; os outros cards são contexto.

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
    "fonte_atual_confirmada": true ou false,
    "recorte_alvo_preciso": true ou false,
    "contorno_area_interna": true ou false,
    "cotas_valores": true ou false,
    "cotas_posicao_legibilidade": true ou false,
    "linhas_paineis": true ou false,
    "hlaz": true ou false,
    "hachuras_apoio": true ou false,
    "sem_contaminacao_vizinha": true ou false
  }},
  "achados": [
    {{"categoria": "cota_sobreposta|painel_torto|sobreposicao|hachura_ausente|hachura_extra|segmentacao|gestalt_geral|contaminacao_recorte|vazamento_gabarito|outro",
      "parte": "...", "direcao": "n4_a_mais|n4_a_menos|divergente|na",
      "motor_suspeito": "gerador|extrator_n2|interpretacao_n1|conversao_n1|indefinido",
      "descricao": "texto curto", "severidade": "baixa|media|alta"}}
  ],
  "resumo": "1-2 frases"
}}"""


def build_prompt(par: str, classe: str = "") -> str:
    return _PROMPT_TEMPLATE.format(
        par_focus=PAR_FOCUS.get(par, PAR_FOCUS["n2xn4"]),
        classe_focus=CLASSE_FOCUS.get(classe, ""),
    )


# ═════════════════════════════════════════════════════════════════════════════
# 2. Parsing robusto de resposta (JSON pode vir com markdown fences, texto solto)
# ═════════════════════════════════════════════════════════════════════════════

def _parse_json_response(raw: str) -> dict:
    clean = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    clean = re.sub(r"```\s*$", "", clean, flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", clean, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return {"veredito": "SUSPEITO", "confianca": 0.0, "achados": [],
            "resumo": "", "erro": "JSON não encontrado na resposta",
            "raw": raw[:500]}


def _png_to_b64(png_path: Path) -> str:
    return base64.standard_b64encode(png_path.read_bytes()).decode()


# ═════════════════════════════════════════════════════════════════════════════
# 3. Backends de visão — mesma assinatura, mesmo schema de saída
# ═════════════════════════════════════════════════════════════════════════════

def avaliar_cli(png_path: Path, prompt: str, model: str = "") -> dict:
    """Backend RECOMENDADO — emit-only. NÃO chama API: devolve um stub de veredito
    VAZIO + o prompt + o path da imagem, para o AGENTE de chat CLI (Claude Code /
    Codex) LER a imagem e preencher no loop. É a única via de qualidade comprovada
    (VISION-VALIDACAO-CAMINHOS.md §1). O agente lê png_path, aplica o prompt e
    escreve o veredito de volta no relatorio.json (ou o consultor faz inline)."""
    return {
        "_backend": "cli",
        "aguardando_agente": True,
        "png_para_ler": str(png_path),
        "prompt": prompt,
        "veredito": None, "confianca": None, "achados": [], "resumo": "",
        "checklist_visual": {
            "fonte_atual_confirmada": None,
            "recorte_alvo_preciso": None,
            "contorno_area_interna": None,
            "cotas_valores": None,
            "cotas_posicao_legibilidade": None,
            "linhas_paineis": None,
            "hlaz": None,
            "hachuras_apoio": None,
            "sem_contaminacao_vizinha": None,
        },
        "_instrucao": "Agente CLI: leia png_para_ler, aplique o prompt e preencha "
                      "checklist_visual/veredito/confianca/achados/resumo. PASS com "
                      "qualquer checklist diferente de true é inválido.",
    }


def avaliar_claude(png_path: Path, prompt: str, model: str = CLAUDE_MODEL_DEF) -> dict:
    """API Anthropic direta (billing/chave). NÃO é a visão do agente CLI — candidato
    a batch autônomo futuro, só após protocolo de calibração."""
    try:
        import anthropic
    except ImportError:
        return {"erro": "pacote anthropic não instalado (pip install anthropic)"}
    client = anthropic.Anthropic()
    img_b64 = _png_to_b64(png_path)
    t0 = __import__("time").time()
    try:
        msg = client.messages.create(
            model=model, max_tokens=1024,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                {"type": "text", "text": prompt},
            ]}],
        )
    except Exception as exc:
        return {"erro": str(exc)}
    dt = __import__("time").time() - t0
    text = msg.content[0].text if msg.content else ""
    result = _parse_json_response(text)
    result.update({"_backend": "claude", "_model": model, "_latencia_s": round(dt, 1)})
    return result


def avaliar_nim(png_path: Path, prompt: str, model: str = NVIDIA_MODEL_DEF) -> dict:
    """NVIDIA NIM — REPROVADO como validador (4/4 falhas, inverteu achado). Mantido
    só para comparação empírica; NUNCA como validador de selagem."""
    import os
    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        return {"erro": "NVIDIA_API_KEY não definido no ambiente"}
    try:
        from openai import OpenAI
    except ImportError:
        return {"erro": "pacote openai não instalado (pip install openai)"}
    client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)
    img_b64 = _png_to_b64(png_path)
    t0 = __import__("time").time()
    try:
        resp = client.chat.completions.create(
            model=model, max_tokens=1024,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
            ]}],
        )
    except Exception as exc:
        return {"erro": str(exc)}
    dt = __import__("time").time() - t0
    text = resp.choices[0].message.content or ""
    result = _parse_json_response(text)
    result.update({"_backend": "nim", "_model": model, "_latencia_s": round(dt, 1)})
    return result


def avaliar_gemini(png_path: Path, prompt: str, model: str = GEMINI_MODEL_DEF) -> dict:
    """API Gemini (Google, billing). Candidato futuro, só após calibração."""
    import os
    import requests
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return {"erro": "GEMINI_API_KEY não definido no ambiente"}
    img_b64 = _png_to_b64(png_path)
    url = f"{GEMINI_BASE_URL}/{model}:generateContent?key={api_key}"
    body = {"contents": [{"parts": [
        {"text": prompt},
        {"inline_data": {"mime_type": "image/png", "data": img_b64}},
    ]}]}
    t0 = __import__("time").time()
    try:
        resp = requests.post(url, json=body, timeout=90)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return {"erro": str(exc)}
    dt = __import__("time").time() - t0
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return {"erro": f"Resposta Gemini sem texto: {json.dumps(data)[:500]}"}
    result = _parse_json_response(text)
    result.update({"_backend": "gemini", "_model": model, "_latencia_s": round(dt, 1)})
    return result


BACKENDS = {"cli": avaliar_cli, "claude": avaliar_claude, "nim": avaliar_nim, "gemini": avaliar_gemini}


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


def screenshot_evidence_grid(html_path: Path, out_png: Path,
                             viewport_width: int = 1000,
                             par: str = "n2xn4") -> bool:
    """
    Screenshot da seção .evidence-grid (N1/N2/N3/N4) de 1 ficha HTML.
    Reusa o mesmo fix de paint-culling de playwright_loop.capture_granular_item_pages
    (mede .main-wrap.scrollHeight, não document.documentElement — o layout de
    2 colunas da ficha faz o scrollHeight do documento mentir).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False

    wait_js = ("Array.from(document.images).every("
               "img => img.complete && img.naturalHeight > 0)")
    ok = False
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": viewport_width, "height": 800})
        try:
            page.goto(f"file:///{html_path.as_posix()}", timeout=15_000)
            try:
                page.wait_for_function(wait_js, timeout=15_000)
            except Exception:
                pass
            page.wait_for_timeout(150)
            target_selector = ".evidence-grid"
            grid_count = page.locator(target_selector).count()
            if grid_count > 0:
                # FV possui uma grade N1 por segmento e outra grade agregada
                # para N2/N3/N4. Um locator direto fica ambíguo no Playwright e,
                # pior, escolher apenas a primeira grade esconderia segmentos.
                # Monte no DOM uma grade transitória contendo todos os cards do
                # par solicitado, sem alterar o HTML/ficha de produção.
                wanted_stages = {
                    "n1xn2": ["N1", "N2"],
                    "n2xn4": ["N2", "N4"],
                    "n3xn4": ["N3", "N4"],
                    "grades": ["N4"],
                }.get(par, ["N1", "N2", "N3", "N4"])
                selected = page.evaluate(
                    """(wanted => {
                      const cards = Array.from(document.querySelectorAll('.evidence-grid .evidence-card'));
                      const grid = document.createElement('div');
                      grid.id = 'g2v-evidence-grid';
                      grid.style.cssText = 'display:grid;grid-template-columns:1fr;gap:18px;width:100%;';
                      for (const card of cards) {
                        const title = card.querySelector('.evidence-title b');
                        const match = title && title.textContent.trim().toUpperCase().match(/^N[1-4]/);
                        if (!match || !wanted.includes(match[0])) continue;
                        grid.appendChild(card.cloneNode(true));
                      }
                      if (!grid.children.length) return 0;
                      const main = document.querySelector('.main-content') || document.body;
                      main.replaceChildren(grid);
                      document.body.style.overflow = 'auto';
                      document.body.style.height = 'auto';
                      const wrap = document.querySelector('.main-wrap');
                      if (wrap) { wrap.style.overflow = 'visible'; wrap.style.height = 'auto'; }
                      return grid.children.length;
                    })""",
                    wanted_stages,
                )
                if not selected:
                    return False
                target_selector = "#g2v-evidence-grid"
            else:
                # As fichas PIL atuais organizam N1/N2/N3/N4 em seções `.sec`
                # (e não dentro de `.evidence-grid`). Monte uma grade transitória
                # apenas no DOM da página carregada, sem alterar/regenerar o HTML.
                assembled = page.evaluate(
                    """(par => {
                      const specs = par === 'grades' ? [
                        ['N4', t => t.startsWith('N4')],
                      ] : [
                        ['N1', t => t.startsWith('Foto N1')],
                        ['N2', t => t.startsWith('Foto N2')],
                        ['N3', t => t.startsWith('N3')],
                        ['N4', t => t.startsWith('N4')],
                      ];
                      const sections = Array.from(document.querySelectorAll('.sec'));
                      const grid = document.createElement('div');
                      grid.id = 'g2v-evidence-grid';
                      grid.style.cssText = 'display:grid;grid-template-columns:1fr;gap:18px;width:100%;';
                      for (const [label, match] of specs) {
                        const sec = sections.find(s => {
                          const title = s.querySelector('.sec-title');
                          return title && match(title.textContent.trim());
                        });
                        if (!sec) return false;
                        const clone = sec.cloneNode(true);
                        const views = Array.from(clone.querySelectorAll('.view-block'));
                        for (const view of views) {
                          const viewLabel = view.querySelector('.view-label');
                          const isGrades = viewLabel && viewLabel.textContent.trim().toUpperCase() === 'GRADES';
                          if ((par === 'n2xn4' && isGrades) || (par === 'grades' && !isGrades)) {
                            view.remove();
                          }
                        }
                        clone.dataset.g2vCard = label;
                        grid.appendChild(clone);
                      }
                      const main = document.querySelector('.main-content') || document.body;
                      main.replaceChildren(grid);
                      document.body.style.overflow = 'auto';
                      document.body.style.height = 'auto';
                      const wrap = document.querySelector('.main-wrap');
                      if (wrap) { wrap.style.overflow = 'visible'; wrap.style.height = 'auto'; }
                      return true;
                    })""",
                    par,
                )
                if not assembled:
                    return False
                target_selector = "#g2v-evidence-grid"
            height = page.evaluate(
                "(() => {"
                "  const w = document.querySelector('.main-wrap');"
                "  return Math.max(w ? w.scrollHeight : 0, document.documentElement.scrollHeight);"
                "})()"
            )
            page.set_viewport_size({"width": viewport_width, "height": min(int(height) + 100, 32000)})
            page.wait_for_timeout(150)
            page.locator(target_selector).screenshot(path=str(out_png), timeout=60_000)
            ok = True
        except Exception as exc:
            print(f"  [WARN] Falha ao capturar ficha HTML {html_path.name}: {exc}")
            ok = False
        finally:
            browser.close()
    return ok


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


def _laj_reference_geometry(recorte_path: Path, elemento_id: str, obra_name: str):
    """Retorna polígono absoluto N2 e halo controlado para leitura das cotas."""
    scripts_dir = str(ARETE_ROOT.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from motor_reverso_laj import extrair_ficha_laje

    ficha = extrair_ficha_laje(str(recorte_path), elemento_id, obra_name)
    coords = ficha.get("coordenadas") or []
    if len(coords) < 3:
        return None, None
    xs = [float(point[0]) for point in coords]
    ys = [float(point[1]) for point in coords]
    pose = ficha.get("_stog_pose") or {}
    off_x = float(pose.get("x", 0.0)) if abs(min(xs)) <= 0.5 else 0.0
    off_y = float(pose.get("y", 0.0)) if abs(min(ys)) <= 0.5 else 0.0
    outline = [(x + off_x, y + off_y) for x, y in zip(xs, ys)]
    abs_xs = [point[0] for point in outline]
    abs_ys = [point[1] for point in outline]
    bbox = (
        min(abs_xs) - 70.0, min(abs_ys) - 105.0,
        max(abs_xs) + 70.0, max(abs_ys) + 105.0,
    )
    return outline, bbox


def validar_veredito_cli(veredito: dict) -> tuple[bool, str]:
    """Veto mecânico mínimo para impedir PASS sem inspeção campo a campo."""
    verdict = str(veredito.get("veredito") or "").upper()
    checklist = veredito.get("checklist_visual") or {}
    if verdict == "PASS":
        missing = [key for key, value in checklist.items() if value is not True]
        if not checklist or missing:
            return False, f"PASS inválido; checklist pendente/falso: {missing or ['todos']}"
    if verdict == "FAIL" and not (veredito.get("achados") or []):
        return False, "FAIL inválido; registre ao menos um achado acionável"
    return verdict in {"PASS", "FAIL", "SUSPEITO"}, ""


def avaliar_item(row: dict, backends: list[str], out_dir: Path,
                 fonte_imagem: str = "html", par: str = "n2xn4",
                 n3_dir: Path | None = None, lista_lv: str = "passa") -> dict:
    """
    Resolve o par canônico do item, gera a imagem (ficha HTML preferida) e roda
    cada backend de veredito pedido, com o prompt focado no par (--par).
    """
    classe = row["classe"]
    elemento_id = row["elemento_id"]
    obra_name = row["obra_name"]
    prompt = build_prompt(par, classe)

    resultado = {
        "classe": classe, "elemento_id": elemento_id, "pavimento": row.get("pavimento"),
        "par": par, "recorte_path": None, "n3_path": None,
        "n4_path": None, "png_path": None,
        "vereditos": {}, "erro": None,
    }

    recorte_path = get_recorte_path(elemento_id, classe, row=row)
    if recorte_path is None or not recorte_path.exists():
        resultado["erro"] = f"Recorte (N2) não encontrado para {classe} {elemento_id}"
        return resultado
    resultado["recorte_path"] = str(recorte_path)

    # N4 só é obrigatório nos pares que o envolvem (n2xn4, n3xn4).
    n4_path = get_real_n4_path(obra_name, classe, elemento_id)
    if par in ("n2xn4", "n3xn4"):
        if not n4_path.exists():
            resultado["erro"] = f"N4 não encontrado: {n4_path} (gerar N4 antes de avaliar)"
            return resultado
        resultado["n4_path"] = str(n4_path)
        resultado["evidencia_fontes"] = {
            "n2": _file_evidence(recorte_path),
            "n4": _file_evidence(n4_path),
        }

    n3_path = None
    if par == "n3xn4" and n3_dir is not None:
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

    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / f"{classe}_{elemento_id}_{par}.png"
    ok = False
    precise_laj = classe == "LAJ" and par == "n2xn4"
    laj_outline = laj_bbox = None
    if precise_laj:
        laj_outline, laj_bbox = _laj_reference_geometry(
            recorte_path, elemento_id, obra_name
        )
        resultado["roi_n2"] = {
            "outline": laj_outline,
            "bbox_com_halo_cotas": laj_bbox,
        }

    if fonte_imagem == "html" and not precise_laj:
        html_path = resolver_html_ficha(
            obra_name, classe, elemento_id, lista_lv=lista_lv
        )
        if html_path:
            ok = screenshot_evidence_grid(html_path, png_path, par=par)
            if ok:
                resultado["fonte_imagem"] = "html_ficha"
                resultado["html_path"] = str(html_path)
        if not ok:
            print(f"  [{classe} {elemento_id}] ficha HTML indisponível/falhou.")

    if not ok:
        # Fallback DXF cru só cobre n2xn4 (render_comparacao(recorte, N4)).
        if par == "n3xn4" and n3_path is not None:
            ok = render_comparacao(
                n3_path, n4_path, png_path,
                ref_label="N3 limpo (N1 → robô)",
                candidate_label="N4 (N2 → robô)",
            )
            resultado["fonte_imagem"] = "dxf_render_n3xn4"
        elif par != "n2xn4":
            resultado["erro"] = (f"par '{par}' precisa da ficha HTML (mostra os 4 cards); "
                                 f"render DXF cru só faz n2xn4. Gere a ficha HTML antes.")
            return resultado
        else:
            ok = render_comparacao(
                recorte_path, n4_path, png_path,
                ref_bbox_override=laj_bbox,
                ref_outline=laj_outline,
                high_resolution=precise_laj,
            )
            resultado["fonte_imagem"] = (
                "dxf_render_roi_laj" if precise_laj else "dxf_render"
            )

    if not ok:
        resultado["erro"] = "Falha ao gerar imagem (nem ficha HTML nem render_comparacao)"
        return resultado
    resultado["png_path"] = str(png_path)

    for backend in backends:
        fn = BACKENDS[backend]
        if backend != "cli":
            print(f"  [{classe} {elemento_id}] chamando {backend}...", flush=True)
        resultado["vereditos"][backend] = fn(png_path, prompt)

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
        description="Harness de veredito VISUAL do Arete (G2-V/N1-V/G5-V) — 1 harness, "
                    "todos os pares visuais, backend plugável (default cli = agente lê a imagem)")
    parser.add_argument("--classe", required=True, choices=CLASSES)
    parser.add_argument("--pav", default=PAV_13)
    parser.add_argument("--par", default="n2xn4", choices=list(PAR_FOCUS.keys()),
                        help="n2xn4=G2-V (default) | n1xn2=N1-V (interpretação SA) | "
                             "n3xn4=G5-V | grades=GRADES-V (só PIL, onde há recorte de grades)")
    parser.add_argument("--item", nargs="+", default=None, help="elemento_id específico(s), ex: V13 V16")
    parser.add_argument("--n", type=int, default=None, help="Avaliar os N primeiros itens da classe/pav")
    parser.add_argument("--backend", nargs="+", default=["cli"], choices=list(BACKENDS.keys()),
                        help="cli (default, ÚNICO permitido): emit-only p/ o agente ler. "
                             "claude/gemini/nim (API) estão DESLIGADOS por ordem do dono "
                             "(03/07) — exigem --permitir-api + calibração.")
    parser.add_argument("--fonte-imagem", default="html", choices=["html", "dxf"],
                        help="html = screenshot da ficha granular (default, cobre os 3 pares); "
                             "dxf = render_comparacao cru (n2xn4 ou n3xn4 com --n3-dir)")
    parser.add_argument(
        "--lista-lv",
        default="passa",
        choices=["para", "passa"],
        help="Lista HTML de LV usada no veredito. Default passa (N2/N4 do 13_PAV); "
        "use para somente na validação humana da lista Para.",
    )
    parser.add_argument("--n3-dir", default=None,
                        help="Diretório dos DXFs N3 do run numérico alvo; obrigatório para "
                             "--par n3xn4 --fonte-imagem dxf")
    parser.add_argument("--permitir-api", action="store_true",
                        help="Override explícito para usar backend de API. SÓ com ordem do "
                             "dono E após o protocolo de calibração (VISION-VALIDACAO-CAMINHOS.md).")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    n3_dir = Path(args.n3_dir).resolve() if args.n3_dir else None
    if args.par == "n3xn4" and args.fonte_imagem == "dxf" and n3_dir is None:
        parser.error("--par n3xn4 --fonte-imagem dxf exige --n3-dir")

    # OBEDIÊNCIA (ordem do dono, 03/07): nada de API por enquanto. O veredito visual é
    # dado SÓ pela visão do agente CLI (backend cli). APIs (claude/gemini/nim) ficam
    # bloqueadas até ordem explícita + calibração — evita alucinação de aprovação por
    # modelo não validado (histórico: NIM 4/4 falhas).
    _API_BACKENDS = {"claude", "gemini", "nim"}
    _apis_pedidas = _API_BACKENDS.intersection(args.backend)
    if _apis_pedidas and not args.permitir_api:
        print(f"[BLOQUEADO] Backend(s) de API {sorted(_apis_pedidas)} desligado(s) por "
              f"ordem do dono (03/07). Use --backend cli (visão do agente CLI, única "
              f"fonte de qualidade comprovada). Para usar API mesmo assim: --permitir-api "
              f"(só com ordem do dono + calibração — VISION-VALIDACAO-CAMINHOS.md).")
        return 2

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
            "grades": "GRADES-V"}.get(args.par, args.par)
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
                    print(f"  {r['classe']} {r['elemento_id']} [cli]: imagem pronta -> "
                          f"{v['png_para_ler']} (agente lê e preenche)")
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
    print(f"Imagens:   {out_dir}")
    if "cli" in args.backend:
        print("\n>>> Backend CLI: as imagens estão prontas. O AGENTE (Claude Code/Codex) "
              "deve LER cada png e preencher veredito/achados no relatorio.json. "
              "Sem esse passo, NÃO há veredito visual — não selar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
