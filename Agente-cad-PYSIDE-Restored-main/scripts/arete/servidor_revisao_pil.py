"""Servidor local do painel PIL, com persistência explícita das revisões humanas."""
from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Lock


class ReviewHandler(SimpleHTTPRequestHandler):
    root: Path
    state_path: Path
    state_lock = Lock()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.root), **kwargs)

    def do_POST(self):
        if self.path != '/api/state':
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get('Content-Length', '0'))
        try:
            incoming = json.loads(self.rfile.read(length).decode('utf-8'))
            if not isinstance(incoming, dict):
                raise ValueError('objeto esperado')
            with self.state_lock:
                current = json.loads(self.state_path.read_text(encoding='utf-8')) if self.state_path.exists() else {}
                current.update(incoming)
                self.state_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
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
    args = parser.parse_args()
    ReviewHandler.root = args.directory.resolve()
    ReviewHandler.state_path = ReviewHandler.root / 'revisoes_humanas.json'
    server = ThreadingHTTPServer(('127.0.0.1', args.port), ReviewHandler)
    print(f'http://127.0.0.1:{args.port}/index.html')
    server.serve_forever()


if __name__ == '__main__':
    main()
