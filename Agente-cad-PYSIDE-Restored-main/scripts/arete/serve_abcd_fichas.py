#!/usr/bin/env python
"""Serve fichas ABCD + API de notas (looping agêntico PIL).

Uso:
  py -3.12 scripts/arete/serve_abcd_fichas.py --dir scripts/arete/html_fichas/Obra_TREINO_1/13_PAV_..._pilares_abcd
  py -3.12 scripts/arete/serve_abcd_fichas.py --latest --obra Obra_TREINO_1 --pav 13_PAV --open

API (espelho FV notes server):
  GET  /api/notes/{page}   → {version,page,updated_at,notes:{...}}
  POST /api/notes/{page}   → grava pilares/{page}.notes.json
  GET  /api/atencao        → legado (agregado)
  POST /api/atencao        → legado texto simples
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import re
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
OUT_BASE = Path(__file__).resolve().parent / "html_fichas"
DEFAULT_PORT = 18765


def _latest_pack(obra: str, pav: str) -> Path | None:
    base = OUT_BASE / obra
    if not base.is_dir():
        return None
    cands = sorted(
        [
            p
            for p in base.iterdir()
            if p.is_dir() and p.name.startswith(f"{pav}_") and p.name.endswith("_pilares_abcd")
        ],
        key=lambda p: p.name,
        reverse=True,
    )
    return cands[0] if cands else None


def _load_notes(path: Path) -> dict:
    if not path.is_file():
        return {
            "schema": "abcd_atencao.v1",
            "updated_at": None,
            "items": {},
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("not dict")
        data.setdefault("schema", "abcd_atencao.v1")
        data.setdefault("items", {})
        return data
    except Exception:
        return {"schema": "abcd_atencao.v1", "updated_at": None, "items": {}}


def _save_notes(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # espelho estável na pasta da obra
    try:
        obra = data.get("obra") or ""
        pav = data.get("pav") or ""
        if obra and pav:
            mirror = OUT_BASE / obra / f"atencao_{pav}_pilares_abcd.json"
            mirror.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    except Exception:
        pass


def _page_notes_path(root: Path, page: str) -> Path:
    safe = re.sub(r"[^\w.\-]+", "_", page)[:80]
    # prefer pilares/{page}.notes.json when HTML is under pilares/
    pil = root / "pilares" / f"{safe}.notes.json"
    if (root / "pilares").is_dir():
        return pil
    return root / f"{safe}.notes.json"


def _read_page_notes(root: Path, page: str) -> dict:
    p = _page_notes_path(root, page)
    if not p.is_file():
        return {"version": 1, "page": page, "updated_at": "", "notes": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {"notes": {}}
        data.setdefault("notes", {})
        data.setdefault("page", page)
        data.setdefault("version", 1)
        return data
    except Exception:
        return {"version": 1, "page": page, "updated_at": "", "notes": {}}


def _write_page_notes(root: Path, page: str, payload: dict, obra: str, pav: str) -> dict:
    notes = payload.get("notes") if isinstance(payload, dict) else None
    if notes is None and isinstance(payload, dict):
        notes = {
            k: v
            for k, v in payload.items()
            if k not in ("version", "page", "updated_at", "notes")
        } or {}
    if not isinstance(notes, dict):
        notes = {}
    out = {
        "version": 1,
        "page": page,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }
    path = _page_notes_path(root, page)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # agrega no atencao_notas.json (humano texto + validadores)
    try:
        agg = _load_notes(root / "atencao_notas.json")
        agg["obra"] = obra
        agg["pav"] = pav
        agg["updated_at"] = out["updated_at"]
        items = agg.setdefault("items", {})
        # extrai texto humano se chave aten_pil_ctx_human_*
        human_text = ""
        for k, v in notes.items():
            if "ctx_human_" in k and isinstance(v, str):
                human_text = v
                break
        entry = {
            "text": human_text,
            "updated_at": out["updated_at"],
            "notes": notes,
        }
        # validadores
        for k, v in notes.items():
            if k.endswith("_verdict") or "hl_sa_human" in k or "hl_agent_human" in k:
                entry[k.split("_")[-3] if False else k] = v  # keep full key below
        entry["verdicts"] = {
            k: v
            for k, v in notes.items()
            if "hl_sa_human" in k
            or "hl_agent_human" in k
            or "agent_verdict" in k
            or k.endswith("_verdict")
        }
        items[page] = entry
        _save_notes(root / "atencao_notas.json", agg)
    except Exception as exc:
        print(f"[notes] agg skip: {exc}", flush=True)

    print(f"[notes] saved {path} ({len(notes)} keys)", flush=True)
    return out


def make_handler(root: Path, notes_path: Path, obra: str, pav: str):
    root = root.resolve()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _json(self, code: int, obj: dict):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            u = urlparse(self.path)
            # FV-compatible page notes
            if u.path.startswith("/api/notes/") or u.path == "/api/notes":
                if u.path == "/api/notes":
                    # list pages with notes
                    pages = []
                    for p in (root / "pilares").glob("*.notes.json") if (root / "pilares").is_dir() else []:
                        pages.append(p.stem.replace(".notes", "") if False else p.name.replace(".notes.json", ""))
                    for p in root.glob("*.notes.json"):
                        pages.append(p.name.replace(".notes.json", ""))
                    return self._json(200, {"pages": sorted(set(pages))})
                page = unquote(u.path[len("/api/notes/") :].strip("/"))
                return self._json(200, _read_page_notes(root, page))

            if u.path == "/api/atencao":
                data = _load_notes(notes_path)
                qs = parse_qs(u.query or "")
                item = (qs.get("item") or [None])[0]
                if item:
                    ent = (data.get("items") or {}).get(item) or {}
                    return self._json(
                        200,
                        {
                            "item": item,
                            "text": ent.get("text") or "",
                            "updated_at": ent.get("updated_at"),
                            "notes": ent.get("notes") or {},
                        },
                    )
                return self._json(200, data)

            # static (pilares/P1.html, propostas/..., index)
            rel = u.path.lstrip("/") or "index.html"
            if ".." in rel.split("/"):
                return self._json(400, {"error": "bad path"})
            fp = (root / rel).resolve()
            if not str(fp).startswith(str(root)) or not fp.is_file():
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"not found")
                return
            ctype = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
            if fp.suffix.lower() in (".html", ".htm"):
                ctype = "text/html; charset=utf-8"
            elif fp.suffix.lower() == ".svg":
                ctype = "image/svg+xml"
            raw = fp.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            u = urlparse(self.path)
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                return self._json(400, {"error": "invalid json"})

            if u.path.startswith("/api/notes/"):
                page = unquote(u.path[len("/api/notes/") :].strip("/"))
                if not page:
                    return self._json(400, {"error": "page required"})
                out = _write_page_notes(root, page, payload, obra, pav)
                return self._json(200, {"ok": True, **out, "path": str(_page_notes_path(root, page))})

            if u.path != "/api/atencao":
                return self._json(404, {"error": "not found"})
            item = str(payload.get("item") or "").strip()
            if not item:
                return self._json(400, {"error": "item required"})
            text = payload.get("text")
            if text is None:
                text = ""
            text = str(text)
            ts = payload.get("updated_at") or datetime.now().isoformat(timespec="seconds")
            data = _load_notes(notes_path)
            data["obra"] = payload.get("obra") or data.get("obra") or obra
            data["pav"] = payload.get("pav") or data.get("pav") or pav
            data["updated_at"] = ts
            data["pack_dir"] = str(root)
            items = data.setdefault("items", {})
            if text.strip():
                items[item] = {"text": text, "updated_at": ts}
            else:
                items.pop(item, None)
            _save_notes(notes_path, data)
            print(f"[ATENCAO] {item}: {len(text)} chars → {notes_path}", flush=True)
            return self._json(200, {"ok": True, "item": item, "path": str(notes_path)})

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="pasta do pack (..._pilares_abcd)")
    ap.add_argument("--latest", action="store_true", help="usa pack mais recente")
    ap.add_argument("--obra", default="Obra_TREINO_1")
    ap.add_argument("--pav", default="13_PAV")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args()

    if args.dir:
        root = Path(args.dir)
    elif args.latest:
        root = _latest_pack(args.obra, args.pav)
        if not root:
            print("[ERR] nenhum pack encontrado", flush=True)
            return 2
    else:
        print("[ERR] passe --dir ou --latest", flush=True)
        return 2

    root = root.resolve()
    if not root.is_dir():
        print(f"[ERR] dir inexistente: {root}", flush=True)
        return 2

    notes_path = root / "atencao_notas.json"
    if not notes_path.is_file():
        _save_notes(
            notes_path,
            {
                "schema": "abcd_atencao.v1",
                "obra": args.obra,
                "pav": args.pav,
                "pack_dir": str(root),
                "updated_at": None,
                "items": {},
            },
        )

    handler = make_handler(root, notes_path, args.obra, args.pav)
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    url = f"http://127.0.0.1:{args.port}/index.html"
    print(f"[OK] servindo {root}", flush=True)
    print(f"[OK] notas → {notes_path}", flush=True)
    print(f"[OK] espelho → {OUT_BASE / args.obra / f'atencao_{args.pav}_pilares_abcd.json'}", flush=True)
    print(f"[OK] abra {url}", flush=True)

    if args.open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[stop]", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
