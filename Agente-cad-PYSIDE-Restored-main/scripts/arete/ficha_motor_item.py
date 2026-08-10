#!/usr/bin/env python3
"""Ficha visual individual para iterar motores N3/N4 sem abrir o SA.

Recebe um ou mais DXFs já gerados pelo motor da classe, renderiza SVG e
publica uma ficha autocontida com hashes, caminhos e JSONs opcionais. Não usa
Qt, não lê/escreve o DB e não disputa a trava do headless SA.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.arete.dxf_to_svg_casos import render  # noqa: E402
from scripts.arete.qa_content_cache import ContentAddressedCache, content_hash  # noqa: E402

try:
    from src.core.qa_presentation_notice import banner_html as _qa_banner_html
except Exception:  # pragma: no cover - path fallback
    def _qa_banner_html(*, dossier_path: str | None = None) -> str:
        return (
            '<aside style="border:1px solid #b8860b;background:#2a2110;color:#f0d78c;'
            'padding:10px;margin:0 0 14px 0;font:12px monospace">'
            '<strong>Apresentação ≠ prova</strong> — HTML/score não selam N1/Arete.'
            '</aside>'
        )


RENDER_CACHE_VERSION = 'ficha_motor_item_svg/v1'
DEFAULT_CACHE = Path(__file__).resolve().parent / '.cache' / 'qa_fastpaths'


def _labeled_path(raw: str) -> tuple[str, Path]:
    if '=' not in raw:
        raise argparse.ArgumentTypeError('use ROTULO=caminho')
    label, path_raw = raw.split('=', 1)
    label = label.strip()
    path = Path(path_raw.strip()).expanduser().resolve()
    if not label:
        raise argparse.ArgumentTypeError('rótulo vazio')
    if not path.is_file():
        raise argparse.ArgumentTypeError(f'arquivo ausente: {path}')
    return label, path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def build_ficha(
    *, classe: str, item: str, nivel: str,
    artifacts: list[tuple[str, Path]],
    jsons: dict[str, Path] | None,
    contracts: dict[str, Path] | None = None,
    cache: ContentAddressedCache | None = None,
    output_dir: Path,
) -> Path:
    """Renderiza uma ficha de evidência do artefato, sem reinterpretar N1."""
    output_dir.mkdir(parents=True, exist_ok=True)
    jsons = jsons or {}
    contracts = contracts or {}
    cards: list[str] = []
    manifesto: list[dict] = []
    for label, path in artifacts:
        dxf_hash = _sha256(path)
        render_inputs = {'dxf_sha256': dxf_hash, 'width': 1500, 'height': 1100, 'fmt': 'svg'}
        if cache is None:
            svg = render(path, width=1500, height=1100, fmt='svg')
            render_cache_hit = False
            render_cache_key = None
        else:
            render_result = cache.get_or_compute(
                'dxf_svg', engine_version=RENDER_CACHE_VERSION, inputs=render_inputs,
                compute=lambda: {'svg': render(path, width=1500, height=1100, fmt='svg')},
                input_hashes={'dxf': dxf_hash},
            )
            svg = render_result.value['svg']
            render_cache_hit = render_result.hit
            render_cache_key = render_result.key
        json_path = jsons.get(label)
        json_html = ''
        json_hash = None
        if json_path:
            data = json.loads(json_path.read_text(encoding='utf-8'))
            json_hash = _sha256(json_path)
            json_html = (
                '<details><summary>Payload JSON exato</summary><pre>'
                + html.escape(json.dumps(data, ensure_ascii=False, indent=2))
                + '</pre></details>'
            )
        contract_path = contracts.get(label)
        contract_hash = None
        contract_html = ''
        if contract_path:
            contract_hash = _sha256(contract_path)
            raw_contract = contract_path.read_text(encoding='utf-8')
            try:
                contract_data = json.loads(raw_contract)
                rendered_contract = json.dumps(contract_data, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                rendered_contract = raw_contract
            contract_html = (
                '<details><summary>Contrato exato</summary><pre>'
                + html.escape(rendered_contract)
                + '</pre></details>'
            )
        manifesto.append({
            'label': label, 'dxf': str(path), 'dxf_sha256': dxf_hash,
            'svg_sha256': _sha256_text(svg),
            'json': str(json_path) if json_path else None,
            'json_sha256': json_hash,
            'contract': str(contract_path) if contract_path else None,
            'contract_sha256': contract_hash,
            'render_cache_hit': render_cache_hit,
            'render_cache_key': render_cache_key,
        })
        cards.append(
            '<section class="card">'
            f'<h2>{html.escape(label)}</h2>'
            f'<div class="meta">DXF: {html.escape(str(path))}<br>'
            f'SHA-256: <code>{dxf_hash}</code></div>'
            f'<div class="canvas">{svg}</div>{contract_html}{json_html}</section>'
        )

    manifest = {
        'schema': 'arete.ficha_motor_item/v2',
        'classe': classe, 'item': item, 'nivel': nivel,
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'artifacts': manifesto,
        'input_signature': content_hash({
            'classe': classe, 'item': item, 'nivel': nivel,
            'artifacts': [
                {
                    'label': row['label'], 'dxf': row['dxf_sha256'],
                    'json': row['json_sha256'], 'contract': row['contract_sha256'],
                }
                for row in manifesto
            ],
        }),
        'authority': 'visual_iteration_only; no N1 interpretation; no DB write; presentation_not_proof',
        'presentation_notice': 'HTML/checkbox/score are presentation only; proof lives in QA dossier',
    }
    notice = _qa_banner_html()
    document = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>{html.escape(classe)} {html.escape(nivel)} {html.escape(item)}</title>
<style>
body{{background:#171717;color:#ddd;font:12px monospace;margin:18px}}
h1{{color:#61d6b0}}h2{{color:#78b7ff}}.meta{{color:#999;word-break:break-all}}
.card{{border:1px solid #333;background:#101010;padding:12px;margin:14px 0}}
.canvas{{background:#fff;margin-top:10px}}svg{{display:block;width:100%;height:auto}}
pre{{white-space:pre-wrap;background:#0a0a0a;padding:10px;max-height:520px;overflow:auto}}
code{{color:#d8ad61}}
</style></head><body>
{notice}
<h1>Ficha focada de motor — {html.escape(classe)} / {html.escape(nivel)} / {html.escape(item)}</h1>
<p>Iteração visual isolada. Esta ficha não executa interpretação N1, não acessa o DB e não fecha gate visual.</p>
{''.join(cards)}</body></html>'''
    index = output_dir / 'index.html'
    index.write_text(document, encoding='utf-8')
    manifest['html'] = str(index)
    manifest['html_sha256'] = _sha256(index)
    (output_dir / 'manifesto.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    return index


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Gera ficha visual individual de DXFs N3/N4 sem headless SA.'
    )
    parser.add_argument('--classe', required=True, choices=('PIL', 'LAJ', 'FV', 'LV'))
    parser.add_argument('--item', required=True)
    parser.add_argument('--nivel', required=True, choices=('N3', 'N4'))
    parser.add_argument(
        '--artefato', action='append', required=True, type=_labeled_path,
        help='Repetível: ROTULO=caminho.dxf (ex.: PARA=.../PL_ABCD_preview_P35.dxf)',
    )
    parser.add_argument(
        '--json', action='append', default=[], type=_labeled_path,
        help='Opcional, repetível: mesmo ROTULO=caminho.json do artefato.',
    )
    parser.add_argument(
        '--contract', action='append', default=[], type=_labeled_path,
        help='Opcional, repetível: mesmo ROTULO=contrato.json/md do artefato.',
    )
    parser.add_argument('--cache-dir', default=str(DEFAULT_CACHE))
    parser.add_argument('--no-cache', action='store_true')
    parser.add_argument('--out-dir', default=None)
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()

    if any(path.suffix.lower() != '.dxf' for _, path in args.artefato):
        parser.error('--artefato aceita somente DXF')
    jsons = dict(args.json)
    contracts = dict(args.contract)
    cache = ContentAddressedCache(Path(args.cache_dir), enabled=not args.no_cache)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = (
        Path(args.out_dir).resolve() if args.out_dir else
        Path(__file__).resolve().parent / 'relatorios' / 'fichas_motor' /
        f'{timestamp}_{args.classe}_{args.nivel}_{args.item}'
    )
    index = build_ficha(
        classe=args.classe, item=args.item, nivel=args.nivel,
        artifacts=args.artefato, jsons=jsons, contracts=contracts,
        cache=cache, output_dir=out,
    )
    print(index, flush=True)
    if args.open:
        webbrowser.open(index.as_uri())


if __name__ == '__main__':
    main()
