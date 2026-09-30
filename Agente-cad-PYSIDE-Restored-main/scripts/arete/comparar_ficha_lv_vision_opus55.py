# -*- coding: utf-8 -*-
"""
comparar_ficha_lv_vision_opus55.py — variante Opus 5.5 de comparar_ficha_lv_vision.py.

O original (claude-sonnet-4-6) fica intacto para comparação A/B. Este arquivo
reutiliza dele o render DXF→PNG, a localização de DXF e o pipeline por elemento,
e troca apenas a chamada de visão:
  - modelo claude-opus-5-5, effort explícito (thinking sempre ligado no 5.5);
  - max_tokens com folga para o thinking (1024 cortaria a resposta);
  - JSON garantido por structured outputs (sai a regex sobre texto livre);
  - leitura da resposta por tipo de bloco + tratamento de refusal/max_tokens;
  - fallback server-side em caso de refusal.

⚠ ORDEM DO DONO (03/07, docs/VISION-VALIDACAO-CAMINHOS.md): API visual NÃO entra
no fluxo de veredito sem ordem explícita + protocolo de calibração (§4). Por isso
a chamada exige --permitir-api. O resultado é diagnóstico/calibração, nunca selo.

Uso:
    python comparar_ficha_lv_vision_opus55.py V301 --permitir-api
    python comparar_ficha_lv_vision_opus55.py V301 V303 --permitir-api --effort high
    python comparar_ficha_lv_vision_opus55.py V301 --mostrar-request   # sem API
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comparar_ficha_lv_vision as base  # noqa: E402

MODEL = "claude-opus-5-5"
EFFORT_PADRAO = "medium"
MAX_TOKENS = 16000

_VISION_PROMPT = """\
Você é especialista em plantas de forma de concreto estrutural (STOG).

A imagem é um recorte N2 de uma LATERAL DE VIGA — desenho técnico STOG feito por
humano — contendo:
- Face A (lateral superior/direita no STOG)
- Face B (lateral oposta)
- Vista Corte/Seção transversal (parte esquerda)
- Cotas STOG em centímetros (camada COTA)

Campos extraídos automaticamente pelo motor de engenharia reversa:
{ficha_json}

Valide cada campo de campos_validados contra o desenho:
- "✓" quando o valor extraído confere com o desenho;
- "✗" quando diverge — informe em valor_visto o valor que o desenho mostra;
- "?" quando o campo não é visível no recorte.
score_geral vai de 0.0 a 1.0. Em observacoes, descreva as discrepâncias principais.
"""

_CAMPOS_NUM = ["h_A", "h_B", "b_cm", "laje_sup_A", "laje_inf_A", "laje_sup_B",
               "laje_inf_B", "n_segmentos_A", "n_segmentos_B"]
_CAMPOS_STR = ["tipo_viga"]


def _campo_schema(tipo_valor: str) -> dict:
    return {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["✓", "✗", "?"]},
            "valor_visto": {"anyOf": [{"type": tipo_valor}, {"type": "null"}]},
        },
        "required": ["status", "valor_visto"],
        "additionalProperties": False,
    }


_RESPOSTA_SCHEMA = {
    "type": "object",
    "properties": {
        "campos_validados": {
            "type": "object",
            "properties": {
                **{c: _campo_schema("number") for c in _CAMPOS_NUM},
                **{c: _campo_schema("string") for c in _CAMPOS_STR},
            },
            "required": _CAMPOS_NUM + _CAMPOS_STR,
            "additionalProperties": False,
        },
        "score_geral": {"type": "number"},
        "observacoes": {"type": "string"},
    },
    "required": ["campos_validados", "score_geral", "observacoes"],
    "additionalProperties": False,
}

_CFG = {"effort": EFFORT_PADRAO, "permitir_api": False}


def _ficha_resumo(ficha: dict) -> dict:
    """Mesmo resumo do original — o conteúdo enviado ao modelo não muda."""
    return {
        'h_A':          ficha.get('h_A', 0),
        'h_B':          ficha.get('h_B', 0),
        'b_cm':         ficha.get('b_geom', 19.0),
        'laje_sup_A':   ficha.get('laje_sup_A', 0),
        'laje_inf_A':   ficha.get('laje_inf_A', 0),
        'laje_sup_B':   ficha.get('laje_sup_B', 0),
        'laje_inf_B':   ficha.get('laje_inf_B', 0),
        'tipo_viga':    ficha.get('tipo_viga', '?'),
        'n_segmentos_A': len(ficha.get('panels_A', [])),
        'n_segmentos_B': len(ficha.get('panels_B', [])),
        'n_face_units': len(ficha.get('face_units', [])),
        'face_units': [
            {
                'label': u.get('label'),
                'side': u.get('side'),
                'n_segmentos': len(u.get('panels', [])),
                'h_total': u.get('h_total'),
                'laje_sup': u.get('laje_sup'),
                'marco_laje_sup': u.get('marco_laje_sup'),
                'sarrafo_vertical_esquerdo': u.get('sarrafo_vertical_esquerdo'),
                'sarrafo_vertical_direito': u.get('sarrafo_vertical_direito'),
                'n_sarrafos_verticais': len(u.get('sarrafos_verticais') or []),
            }
            for u in ficha.get('face_units', [])
        ],
        'h_section':    ficha.get('h_section', 0),
        'h_section_all': ficha.get('h_section_all', []),
    }


def montar_request(ficha: dict, png_path: Path, effort: str) -> dict:
    prompt = _VISION_PROMPT.format(
        ficha_json=json.dumps(_ficha_resumo(ficha), indent=2, ensure_ascii=False))
    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "output_config": {
            "effort": effort,
            "format": {"type": "json_schema", "schema": _RESPOSTA_SCHEMA},
        },
        "betas": ["server-side-fallback-2026-07-01"],
        # SDK 0.79 ainda não declara `fallbacks` — vai no corpo cru
        "extra_body": {"fallbacks": "default"},
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": "image/png",
                            "data": base._png_to_b64(png_path)}},
                {"type": "text", "text": prompt},
            ],
        }],
    }


def validar_com_vision(ficha: dict, png_path: Path) -> dict:
    """Substitui base.validar_com_vision: mesma assinatura e mesmo dict de saída."""
    if not _CFG["permitir_api"]:
        return {'erro': 'API visual bloqueada (ordem do dono 03/07) — use --permitir-api'}
    if not base.ANTHROPIC_OK:
        return {'erro': 'anthropic não instalado — pip install anthropic'}
    if not png_path.exists():
        return {'erro': f'PNG não encontrado: {png_path}'}

    import anthropic
    client = anthropic.Anthropic()
    try:
        msg = client.beta.messages.create(**montar_request(ficha, png_path, _CFG["effort"]))
    except anthropic.APIStatusError as e:
        return {'erro': f'API {e.status_code}: {e.message}'}
    except anthropic.APIConnectionError as e:
        return {'erro': f'conexão: {e}'}

    meta = {'_modelo': msg.model, '_effort': _CFG["effort"],
            '_stop_reason': msg.stop_reason,
            '_output_tokens': getattr(msg.usage, 'output_tokens', None)}
    if msg.stop_reason == "refusal":
        cat = getattr(msg.stop_details, 'category', None) if msg.stop_details else None
        return {**meta, 'erro': f'refusal (categoria={cat})'}
    if msg.stop_reason == "max_tokens":
        return {**meta, 'erro': f'max_tokens={MAX_TOKENS} atingido — resposta incompleta'}

    text = next((b.text for b in msg.content if b.type == "text"), "")
    try:
        return {**json.loads(text), **meta}
    except json.JSONDecodeError:
        return {**meta, 'resposta_raw': text[:500], 'erro': 'JSON inválido'}


base.validar_com_vision = validar_com_vision


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Comparação ficha LV N2 + vision (Opus 5.5)')
    parser.add_argument('elementos', nargs='*', help='V301 V303 ...')
    parser.add_argument('--todos', action='store_true')
    parser.add_argument('--effort', default=EFFORT_PADRAO,
                        choices=['low', 'medium', 'high', 'xhigh', 'max'])
    parser.add_argument('--permitir-api', action='store_true',
                        help='Exige ordem explícita do dono (VISION-VALIDACAO-CAMINHOS §4)')
    parser.add_argument('--mostrar-request', action='store_true',
                        help='Imprime o request (imagem omitida) do 1º elemento, sem chamar a API')
    parser.add_argument('--out', type=str, default=None)
    args = parser.parse_args()

    _CFG["effort"] = args.effort
    _CFG["permitir_api"] = args.permitir_api
    elems = base._all_elems() if args.todos else (args.elementos or ['V301'])

    if args.mostrar_request:
        from motor_reverso_lv import extrair_ficha_lateral_viga
        dxf = base._find_dxf(elems[0])
        if dxf is None:
            sys.exit(f'DXF não encontrado para {elems[0]}')
        ficha = extrair_ficha_lateral_viga(str(dxf), elems[0] + '_A',
                                           obra_root=str(base.OBRA_DIR))
        png = base.OUT_DIR / f"{elems[0]}_n2.png"
        req = montar_request(ficha, png, args.effort) if png.exists() else None
        if req is None:
            sys.exit(f'PNG ainda não renderizado: {png}')
        req["messages"][0]["content"][0]["source"]["data"] = "<omitido>"
        print(json.dumps(req, indent=2, ensure_ascii=False))
        sys.exit(0)

    if not args.permitir_api:
        print("AVISO: sem --permitir-api a etapa de visão retorna erro (só extração + PNG).")

    resultados = []
    for elem in elems:
        print(f"[{elem}] ...", end=' ', flush=True)
        r = base.comparar_elemento(elem, usar_vision=True, salvar_png=True)
        resultados.append(r)
        v = r.get('vision', {})
        print(f"score={r.get('score_vision', '?')} effort={v.get('_effort')} "
              f"tokens={v.get('_output_tokens')} {v.get('erro', '')}")

    out_path = Path(args.out) if args.out else base.OUT_DIR / 'comparacao_lv_report_opus55.json'
    out_path.write_text(json.dumps(resultados, indent=2, ensure_ascii=False, default=str),
                        encoding='utf-8')
    print(f"\nRelatorio: {out_path}")
