"""Servidor local do painel PIL, com persistência explícita das revisões humanas."""
from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse


class ReviewHandler(SimpleHTTPRequestHandler):
    root: Path
    state_path: Path
    state_lock = Lock()
    live_ledger_path: Path | None = None
    live_preview_path: Path | None = None
    live_lock = Lock()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.root), **kwargs)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _live_spec(self) -> tuple[dict, Path, tuple[float, float, float, float]]:
        if self.live_ledger_path is None:
            raise FileNotFoundError('visualizador DXF ao vivo não configurado')
        ledger = json.loads(self.live_ledger_path.read_text(encoding='utf-8'))
        dxf_path = Path(ledger['source_dxf'])
        ox, oy = (float(v) for v in ledger['origin_abs'])
        xmin, ymin, xmax, ymax = (float(v) for v in ledger['clip_rel'])
        clip = (ox + xmin, oy + ymin, ox + xmax, oy + ymax)
        return ledger, dxf_path, clip

    last_build_version: int = 0
    build_lock = Lock()

    @classmethod
    def get_source_version(cls) -> int:
        n4_dir = Path(r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-6_Execucao_CAD\n4")
        times = []
        for p in n4_dir.glob("LV_preview_V301*.dxf"):
            try:
                times.append(p.stat().st_mtime_ns)
            except Exception:
                pass
        return max(times) if times else 0

    def do_GET(self):
        route = urlparse(self.path).path
        if route == '/api/dxf-version':
            try:
                src_ver = self.get_source_version()
                with self.build_lock:
                    # NOTA: `self.last_build_version = ...` gravaria num atributo de
                    # INSTANCIA — o http.server cria uma instancia nova por request,
                    # entao isso nunca persistiria e cada poll rebuildaria de novo.
                    # Por isso a escrita é sempre na CLASSE.
                    if src_ver > ReviewHandler.last_build_version:
                        import sys
                        import importlib
                        scripts_dir = Path(__file__).resolve().parent
                        if str(scripts_dir) not in sys.path:
                            sys.path.insert(0, str(scripts_dir))
                        import _build_segments_html_v301
                        # Hot-reload real do gerador: se o .py do builder foi editado
                        # nesta sessao, o processo do servidor (import cacheado em
                        # sys.modules) so pega a mudanca com reload explicito.
                        # `importlib.reload` NAO propaga pra modulos importados via
                        # "from X import Y" dentro do builder — reload de
                        # _build_segments_html_v301 sozinho deixava geometry_lv_units
                        # (e os demais) presos na versao antiga em memoria, entao um
                        # fix nesses arquivos nunca aparecia na pagina servida ate
                        # reiniciar o processo (achado 2026-09-08: correcao do
                        # viewBox N2×N4 em geometry_lv_units.py nao surtia efeito
                        # nenhum na ficha ao vivo por causa disso). Recarregar cada
                        # submodulo de primeira-parte explicitamente, na ordem certa
                        # (dependencias antes de quem as usa).
                        for _mod_name in (
                            'arete.geometry_lv_units',
                            'gerar_lv_dxf_stog',
                            'lv_n4_face_unit_selection',
                            'arete.gerar_lv_n4_fichas',
                            'motor_reverso_lv',
                        ):
                            _mod = sys.modules.get(_mod_name)
                            if _mod is not None:
                                importlib.reload(_mod)
                        importlib.reload(_build_segments_html_v301)
                        _build_segments_html_v301.build()
                        ReviewHandler.last_build_version = src_ver
                self._send_json({'ok': True, 'version': ReviewHandler.last_build_version})
            except Exception as exc:
                self._send_json({'ok': False, 'error': str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if route == '/api/live-dxf/version':
            try:
                ledger, dxf_path, _ = self._live_spec()
                stat = dxf_path.stat()
                self._send_json({
                    'ok': True,
                    'version': stat.st_mtime_ns,
                    'label': ledger.get('label'),
                    'source': str(dxf_path),
                })
            except Exception as exc:
                self._send_json({'ok': False, 'error': str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if route == '/api/live-dxf/preview.png':
            try:
                ledger, dxf_path, clip = self._live_spec()
                if self.live_preview_path is None:
                    raise FileNotFoundError('cache do visualizador não configurado')
                with self.live_lock:
                    if (
                        not self.live_preview_path.exists()
                        or self.live_preview_path.stat().st_mtime_ns < dxf_path.stat().st_mtime_ns
                    ):
                        from _build_segments_html_v301 import render_dxf_clip
                        ok = render_dxf_clip(
                            dxf_path,
                            self.live_preview_path,
                            clip=clip,
                            title=f"N4 · {ledger.get('label', '')} (DXF ao vivo)",
                            width_px=700,
                            height_px=400,
                        )
                        if not ok:
                            raise RuntimeError('falha ao renderizar o DXF atual')
                    body = self.live_preview_path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                self._send_json({'ok': False, 'error': str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        super().do_GET()

    def _state_path_do_referer(self):
        """Estado na pasta da PAGINA que enviou, nao na raiz do servidor.

        A pagina le `revisoes_humanas.json` por caminho RELATIVO (portanto o da
        pasta dela) mas posta em `/api/state`, que e' absoluto. Servindo uma
        raiz com varias pastas de item — o caso da rodada LV, uma pasta por
        viga — o GET lia de um arquivo e o POST gravava em outro, e a validacao
        parecia nao persistir (2026-09-11). Com `Referer` cada item grava no
        seu proprio arquivo; sem `Referer` mantem o comportamento antigo.
        """
        ref = self.headers.get('Referer') or ''
        try:
            from urllib.parse import unquote, urlparse
            caminho = unquote(urlparse(ref).path or '')
        except Exception:
            caminho = ''
        rel = caminho.strip('/').rsplit('/', 1)[0] if '/' in caminho.strip('/') else ''
        if not rel:
            return self.state_path
        destino = (self.root / rel).resolve()
        try:
            destino.relative_to(self.root.resolve())   # nunca sair da raiz
        except ValueError:
            return self.state_path
        if not destino.is_dir():
            return self.state_path
        return destino / 'revisoes_humanas.json'

    def do_POST(self):
        if self.path != '/api/state':
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get('Content-Length', '0'))
        try:
            incoming = json.loads(self.rfile.read(length).decode('utf-8'))
            if not isinstance(incoming, dict):
                raise ValueError('objeto esperado')
            alvo = self._state_path_do_referer()
            with self.state_lock:
                current = json.loads(alvo.read_text(encoding='utf-8')) if alvo.exists() else {}
                current.update(incoming)
                alvo.parent.mkdir(parents=True, exist_ok=True)
                alvo.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as exc:
            body = json.dumps({'ok': False, 'error': str(exc)}).encode('utf-8')
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = b'{"ok":true}'
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--live-ledger', type=Path)
    args = parser.parse_args()
    ReviewHandler.root = args.directory.resolve()
    ReviewHandler.state_path = ReviewHandler.root / 'revisoes_humanas.json'
    ReviewHandler.live_ledger_path = args.live_ledger.resolve() if args.live_ledger else None
    ReviewHandler.live_preview_path = ReviewHandler.root / '.live_dxf_preview.png'
    server = ThreadingHTTPServer(('127.0.0.1', args.port), ReviewHandler)
    print(f'http://127.0.0.1:{args.port}/index.html')
    server.serve_forever()


if __name__ == '__main__':
    main()
