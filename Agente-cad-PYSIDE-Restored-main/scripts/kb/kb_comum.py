# -*- coding: utf-8 -*-
"""
kb_comum.py — esquema, fatiamento e embedder da base de conhecimento (global e por obra).

Um índice = um arquivo SQLite com:
  chunks      trechos com metadados (escopo, tipo, status, tier, classes, fonte)
  chunks_fts  busca textual FTS5 (acentos ignorados) — acerta termos exatos (grade_1, V301)
  vetores     embeddings por hash de conteúdo + embedder — acerta por significado
  meta        embedder, dimensão, data, escopo

O mesmo esquema serve a KB global (KB-GLOBAL/kb_global.sqlite) e a KB de cada obra
(KB-GLOBAL/obras/<obra>.sqlite) — ver docs/CONHECIMENTO/CONTRATO-KB-MULTIOBRA.md.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
WORKSPACE = REPO.parent
KB_DIR = REPO / "docs" / "CONHECIMENTO"
INDEX_DIR = WORKSPACE / "KB-GLOBAL"
GLOBAL_DB = INDEX_DIR / "kb_global.sqlite"
OBRAS_DIR = INDEX_DIR / "obras"

ESQUEMA_VERSAO = "1"
MAX_CHARS = 900

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS chunks (
    rowid   INTEGER PRIMARY KEY,
    id      TEXT UNIQUE,          -- sha1(path|secao|ordem)
    escopo  TEXT,                 -- 'global' | 'obra:<nome>'
    tipo    TEXT,                 -- doc | decisao | glossario | regra_semantica | codigo
    path    TEXT,                 -- relativo a D:/Agente-cad-PYSIDE
    titulo  TEXT,
    secao   TEXT,                 -- trilha de títulos "A > B > C"
    status  TEXT,                 -- entrada | canonico | ativo | historico | legado | ...
    tier    TEXT,                 -- T1/T2 para decisões e regras; NULL para docs
    classes TEXT,                 -- ',PIL,LV,' (vírgulas nas pontas para LIKE)
    data    TEXT,
    ordem   INTEGER,
    texto   TEXT,
    sha     TEXT                  -- sha256 do texto indexado (chave do cache de vetor)
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    titulo, secao, texto, content='chunks', content_rowid='rowid',
    tokenize="unicode61 remove_diacritics 2");
CREATE TABLE IF NOT EXISTS vetores (
    sha TEXT, embedder TEXT, vec BLOB, PRIMARY KEY (sha, embedder));
"""

# Pesos por status na fusão final: canônico sobe, histórico desce. Legado não entra no índice.
PESO_STATUS = {"entrada": 1.2, "canonico": 1.2, "ativo": 1.0, "historico": 0.7}
STATUS_INDEXADOS = set(PESO_STATUS)

_RE_CLASSE = {
    "PIL": re.compile(r"\b(PIL|pilar(es)?)\b", re.I),
    "LV": re.compile(r"\b(LV|laterai?s? de viga)\b", re.I),
    "FV": re.compile(r"\b(FV|fundos? de viga)\b", re.I),
    "LAJ": re.compile(r"\b(LAJ|lajes?)\b", re.I),
}


def conectar(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    con.executescript(SCHEMA)
    return con


def sha256(txt: str) -> str:
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()


def detectar_classes(path: str, secao: str, texto: str) -> str:
    """Classes citadas no trecho: no caminho/seção basta uma menção; no texto, duas."""
    achadas = []
    for cls, rx in _RE_CLASSE.items():
        if rx.search(path) or rx.search(secao) or len(rx.findall(texto)) >= 2:
            achadas.append(cls)
    return "," + ",".join(achadas) + "," if achadas else ""


def fatiar_markdown(texto: str, max_chars: int = MAX_CHARS) -> list[tuple[str, str]]:
    """Divide por títulos (# a ####) e depois por parágrafo até max_chars.

    Devolve [(trilha_de_secao, trecho)]. Tabelas são cortadas por linha repetindo o
    cabeçalho, para cada pedaço continuar legível sozinho.
    """
    trilha: list[str] = []
    secoes: list[tuple[str, list[str]]] = []
    atual: list[str] = []
    em_codigo = False
    for ln in texto.splitlines():
        if ln.strip().startswith("```"):
            em_codigo = not em_codigo
        m = None if em_codigo else re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            if atual:
                secoes.append((" > ".join(trilha), atual))
            nivel = len(m.group(1))
            trilha = trilha[: nivel - 1] + [m.group(2).strip()]
            atual = []
        else:
            atual.append(ln)
    if atual:
        secoes.append((" > ".join(trilha), atual))

    saida: list[tuple[str, str]] = []
    for secao, linhas in secoes:
        blocos = re.split(r"\n\s*\n", "\n".join(linhas).strip())
        buf = ""
        for bloco in blocos:
            for pedaco in _quebrar_bloco(bloco, max_chars):
                if buf and len(buf) + len(pedaco) + 2 > max_chars:
                    saida.append((secao, buf))
                    buf = pedaco
                else:
                    buf = f"{buf}\n\n{pedaco}" if buf else pedaco
        if buf.strip():
            saida.append((secao, buf))
    return [(s, t) for s, t in saida if len(t.strip()) >= 40 or s]


def _quebrar_bloco(bloco: str, max_chars: int) -> list[str]:
    if len(bloco) <= max_chars:
        return [bloco]
    linhas = bloco.splitlines()
    cab = linhas[:2] if len(linhas) > 2 and linhas[0].startswith("|") and set(linhas[1]) <= set("|-: ") else []
    corpo = linhas[len(cab):]
    pedacos, buf = [], list(cab)
    for ln in corpo:
        if sum(len(x) + 1 for x in buf) + len(ln) > max_chars and len(buf) > len(cab):
            pedacos.append("\n".join(buf))
            buf = list(cab)
        buf.append(ln[: max_chars * 2])
    if len(buf) > len(cab):
        pedacos.append("\n".join(buf))
    return pedacos


# ── Embedders ────────────────────────────────────────────────────────────────

class Embedder:
    nome: str
    dim: int

    def codificar(self, textos: list[str], consulta: bool = False) -> np.ndarray:
        raise NotImplementedError


class EmbedderLocal(Embedder):
    """Modelo multilíngue offline (bom em português), roda em CPU. Sem rede."""
    MODELO = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

    def __init__(self) -> None:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        import torch
        torch.set_num_threads(os.cpu_count() or 2)  # padrão do torch aqui era 2 de 6 núcleos
        from sentence_transformers import SentenceTransformer
        self._m = SentenceTransformer(self.MODELO, device="cpu")
        self._m.max_seq_length = 256
        self.nome = "local:" + self.MODELO.split("/")[-1]
        self.dim = (getattr(self._m, 'get_embedding_dimension', None) or self._m.get_sentence_embedding_dimension)()

    def codificar(self, textos, consulta=False):
        return self._m.encode(textos, batch_size=32, normalize_embeddings=True,
                              show_progress_bar=False).astype(np.float32)


class EmbedderNIM(Embedder):
    """NVIDIA NIM (DP-6). Envia o texto à API da NVIDIA; exige NVIDIA_API_KEY e rede.

    Modelo padrão medido em 2026-09-26: `nvidia/nemotron-3-embed-1b` (2048-dim). O
    `nv-embed-v1` da DP-6 e outros três embedders NIM respondem 410 (fim de vida) —
    catálogo NIM muda sem aviso; KB_NIM_MODELO troca o modelo sem mexer no código.
    """
    MODELO = os.environ.get("KB_NIM_MODELO", "nvidia/nemotron-3-embed-1b")

    def __init__(self) -> None:
        import requests
        chave = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVIDIA_NIM_API_KEY")
        if not chave:
            raise RuntimeError("NVIDIA_API_KEY ausente")
        self._url = (os.environ.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1") + "/embeddings"
        self._s = requests.Session()
        self._s.headers.update({"Authorization": f"Bearer {chave}", "Content-Type": "application/json"})
        self.nome = "nim:" + self.MODELO
        self.dim = len(self._post(["teste"], "query")[0])

    def _post(self, textos, tipo):
        import time
        for tentativa in range(5):
            r = self._s.post(self._url, timeout=60, json={
                "input": textos, "model": self.MODELO, "input_type": tipo, "truncate": "END"})
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** tentativa)
                continue
            r.raise_for_status()
            return [d["embedding"] for d in sorted(r.json()["data"], key=lambda d: d["index"])]
        r.raise_for_status()

    def codificar(self, textos, consulta=False):
        vecs = []
        for i in range(0, len(textos), 32):
            vecs += self._post(textos[i:i + 32], "query" if consulta else "passage")
        arr = np.asarray(vecs, dtype=np.float32)
        return arr / np.linalg.norm(arr, axis=1, keepdims=True).clip(min=1e-9)


def criar_embedder(nome: str) -> Embedder:
    if nome == "nim":
        return EmbedderNIM()
    if nome == "local":
        return EmbedderLocal()
    raise ValueError(f"embedder desconhecido: {nome} (use local | nim)")


def _limpar_tabela(texto: str) -> str:
    """Tabela markdown vira frase: sem linha separadora, sem barras.

    Linha de glossário/decisão chega como "cabeçalho\\nlinha": o cabeçalho (| ID | Data |…)
    não diz nada do assunto e afogava o conteúdo no embedding (medido: D-48 fora do top 60).
    """
    linhas = texto.splitlines()
    if len(linhas) == 2 and all(ln.lstrip().startswith("|") for ln in linhas):
        linhas = linhas[1:]
    saida = []
    for ln in linhas:
        s = ln.strip()
        if s.startswith("|"):
            if set(s) <= set("|-: "):
                continue
            celulas = [c.strip() for c in s.strip("|").split("|") if c.strip() and c.strip() != "—"]
            ln = " ; ".join(celulas)
        saida.append(ln)
    return "\n".join(saida)


def texto_para_vetor(titulo: str, secao: str, texto: str) -> str:
    """O que o embedder vê: título e trilha de seção primeiro (é onde está o assunto)."""
    cab = f"{titulo} — {secao}" if secao else titulo
    corpo = _limpar_tabela(texto) if "|" in texto else texto
    return f"{cab}\n{corpo}"
