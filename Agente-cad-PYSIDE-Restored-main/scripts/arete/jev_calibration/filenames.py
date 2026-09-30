"""Windows-safe filenames. Original case_id stays inside JSON, never as a raw path."""
from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.arete.jev_sa_second_read import validate_request

WIN_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WIN_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def safe_filename(stem: str, *, suffix: str = ".json", max_len: int = 120) -> str:
    cleaned = WIN_FORBIDDEN.sub("_", str(stem or "case"))
    cleaned = cleaned.replace("|", "_")
    cleaned = re.sub(r"[^\w.\-]+", "_", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"_+", "_", cleaned).strip(" ._")
    if not cleaned:
        cleaned = "case"
    head = cleaned.split(".")[0].upper()
    if head in WIN_RESERVED:
        cleaned = f"case_{cleaned}"
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip(" ._")
    if not suffix.startswith("."):
        suffix = f".{suffix}"
    name = f"{cleaned}{suffix}"
    if ":" in name or any(ch in name for ch in '<>:"/\\|?*'):
        raise ValueError(f"sanitized name still unsafe for Windows: {name!r}")
    return name


def request_filename(index: int, case_id: str) -> str:
    return safe_filename(f"{index:02d}_{case_id}", suffix=".json")


def list_visible_json(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    files = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() != ".json":
            continue
        if ":" in path.name:
            continue
        files.append(path)
    return sorted(files)


def assert_visible_request_files(out_dir: Path, packed: int) -> list[Path]:
    requests_dir = Path(out_dir) / "jev_requests"
    files = list_visible_json(requests_dir)
    if len(files) != packed:
        raise RuntimeError(
            f"jev_requests visible .json count {len(files)} != packed {packed} in {requests_dir}"
        )
    for path in files:
        if path.stat().st_size <= 0:
            raise RuntimeError(f"empty Jev request file: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_request(payload)
        if not payload.get("identity") or "case_id" not in payload:
            raise RuntimeError(f"request JSON must keep original case_id: {path}")
    return files
