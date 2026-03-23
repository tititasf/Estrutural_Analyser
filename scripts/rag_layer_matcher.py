#!/usr/bin/env python3
"""
rag_layer_matcher.py — CAD-ANALYZER Sprint 3
=============================================
Matching semântico de layer names DXF → canonical names do CONFIG-LAYERS.yaml.

Problema resolvido:
  - Firma A chama "Painéis", Firma B chama "PANEL-GEOM", nova firma usa "panneau"
  - Normalização regex falha em variações não-antecipadas
  - RAG resolve: embeddings de texto para 85 layers canônicos + busca por similaridade

Fluxo:
  1. Carregar CONFIG-LAYERS.yaml → extrair canonicals + aliases + descriptions
  2. Criar texto enriquecido por canonical: nome + desc + aliases + elemento
  3. Embed com all-MiniLM-L6-v2 → FAISS FlatIP (cosine similarity)
  4. Salvar: data/vectors/faiss/layers_canonicos.index + layers_canonicos_meta.json
  5. Expor LayerMatcher.match(layer_name) → MatchResult

Score de confiança:
  ≥ 0.92 → EXACT      (provavelmente alias exato)
  ≥ 0.75 → HIGH       (match semântico sólido)
  ≥ 0.55 → MEDIUM     (match plausível, verificar)
  ≥ 0.35 → LOW        (match fraco — usar fallback)
  < 0.35 → NO_MATCH   (layer desconhecido)

Uso:
    from rag_layer_matcher import LayerMatcher
    matcher = LayerMatcher()
    r = matcher.match("Pain?is")
    print(r.canonical, r.score, r.confianca)  # PANEL_GEOMETRY 0.97 EXACT

    # Batch
    results = matcher.match_batch(["fundo", "SARR_2.2x7", "EstranhaFirma"])

    # CLI
    python scripts/rag_layer_matcher.py --build
    python scripts/rag_layer_matcher.py --layer "Pain?is" --tipo pilar
    python scripts/rag_layer_matcher.py --test
"""
import sys, json, unicodedata, argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ── Paths ────────────────────────────────────────────────────────────────────
_SCRIPTS   = Path(__file__).parent
_REPO_ROOT = _SCRIPTS.parent
_YAML_PATH = _REPO_ROOT / 'docs' / 'specs' / 'CONFIG-LAYERS.yaml'
_INDEX_DIR = _REPO_ROOT / 'data' / 'vectors' / 'faiss'
_INDEX_PATH = _INDEX_DIR / 'layers_canonicos.index'
_META_PATH  = _INDEX_DIR / 'layers_canonicos_meta.json'

sys.path.insert(0, str(_SCRIPTS))

# ── Thresholds ────────────────────────────────────────────────────────────────
THRESH_EXACT    = 0.92
THRESH_HIGH     = 0.75
THRESH_MEDIUM   = 0.55
THRESH_LOW      = 0.35


# ── normalize_layer (idêntico ao agente_estrutural.py) ───────────────────────
def normalize_layer(name: str) -> str:
    """NFKD → ASCII → UPPER → strip."""
    nfkd = unicodedata.normalize('NFKD', str(name))
    return nfkd.encode('ascii', 'ignore').decode().upper().strip()


# ── Resultado de matching ────────────────────────────────────────────────────
@dataclass
class MatchResult:
    layer_raw:    str
    layer_norm:   str
    canonical:    Optional[str]   # None se NO_MATCH
    elemento:     Optional[str]   # pilar | viga | laje | universal | None
    score:        float
    confianca:    str             # EXACT | HIGH | MEDIUM | LOW | NO_MATCH
    description:  str = ''
    aliases_hint: list = field(default_factory=list)  # aliases conhecidos do canonical
    robot_uses:   bool = True     # False para layers ignorados pelos robôs

    @property
    def matched(self) -> bool:
        return self.canonical is not None and self.confianca != 'NO_MATCH'

    def __str__(self) -> str:
        if self.matched:
            return (f"[{self.confianca}] '{self.layer_raw}' → {self.canonical} "
                    f"({self.elemento}) score={self.score:.3f}")
        return f"[NO_MATCH] '{self.layer_raw}' score={self.score:.3f}"


# ── Carregador do YAML ────────────────────────────────────────────────────────
def _load_yaml(path: Path = _YAML_PATH) -> dict:
    try:
        import yaml
        with open(path, encoding='utf-8', errors='replace') as f:
            return yaml.safe_load(f)
    except ImportError:
        # fallback manual mínimo — parse básico sem dependência
        return _parse_yaml_minimal(path)
    except Exception as e:
        raise RuntimeError(f"Não foi possível carregar {path}: {e}")


def _parse_yaml_minimal(path: Path) -> dict:
    """Parser YAML mínimo para extrair aliases sem dependência de pyyaml."""
    sections = {}
    current_section = None
    current_canonical = None
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#') or not stripped:
            continue
        # Seções de nível 0
        if not line.startswith(' ') and line.endswith(':') and not stripped.startswith('-'):
            key = stripped.rstrip(':')
            if key in ('pilares', 'vigas', 'lajes', 'universal'):
                current_section = key
                sections[key] = {}
                current_canonical = None
            else:
                current_section = None
            continue
        # Canonical (2 espaços)
        if line.startswith('  ') and not line.startswith('   ') and line.strip().endswith(':'):
            if current_section:
                key = stripped.rstrip(':')
                sections[current_section][key] = {'aliases': [], 'description': '', 'robot_uses': True}
                current_canonical = key
            continue
        # aliases
        if '- ' in line and current_section and current_canonical:
            alias = stripped.lstrip('- ').strip().strip('"\'')
            if alias:
                sections[current_section][current_canonical]['aliases'].append(alias)
        # description
        if 'description:' in line and current_canonical and current_section:
            desc = stripped.split('description:', 1)[-1].strip().strip('"\'')
            sections[current_section][current_canonical]['description'] = desc
        # robot_uses: false
        if 'robot_uses: false' in line and current_canonical and current_section:
            sections[current_section][current_canonical]['robot_uses'] = False

    return sections


def extract_canonicals(data: dict) -> list:
    """
    Extrai lista de dicts canônicos do YAML carregado.
    Cada dict: {canonical, elemento, description, aliases, robot_uses, text}
    """
    SECTIONS = ['pilares', 'vigas', 'lajes', 'universal']
    result = []

    for secao in SECTIONS:
        secao_data = data.get(secao, {})
        if not isinstance(secao_data, dict):
            continue
        elemento_map = {'pilares': 'pilar', 'vigas': 'viga', 'lajes': 'laje', 'universal': 'universal'}
        elem = elemento_map[secao]

        for canonical, info in secao_data.items():
            if not isinstance(info, dict):
                continue

            description = info.get('description', '')
            robot_uses  = info.get('robot_uses', True)
            aliases_raw = info.get('aliases', [])
            aliases     = [str(a) for a in aliases_raw if a] if isinstance(aliases_raw, list) else []

            # Texto enriquecido para embedding:
            # canonical name + description + aliases normalizados + elemento
            parts = [canonical]
            if description:
                parts.append(description)
            if aliases:
                parts.append('aliases: ' + ' '.join(normalize_layer(a) for a in aliases))
            parts.append(f'elemento {elem}')
            text = ' | '.join(parts)

            result.append({
                'canonical':   canonical,
                'elemento':    elem,
                'description': description,
                'aliases':     aliases,
                'robot_uses':  robot_uses,
                'text':        text,
            })

    return result


# ── LayerMatcher ─────────────────────────────────────────────────────────────

class LayerMatcher:
    """
    Matching semântico de layer names DXF → canonical names.

    Uso:
        matcher = LayerMatcher()

        # Matching simples
        r = matcher.match('Pain?is')
        print(r)  # [EXACT] 'Pain?is' → PANEL_GEOMETRY (pilar) score=0.971

        # Com filtro de elemento
        r = matcher.match('fundo', elemento='viga')

        # Batch
        results = matcher.match_batch(['NOMENCLATURA', 'fundo', 'SARRAFO', 'xyz123'])

        # Reconstruir índice
        matcher.build_index()
    """

    def __init__(self, auto_build: bool = True):
        """
        Args:
            auto_build: Se True e índice não existir, constrói automaticamente.
        """
        self._index   = None
        self._meta    = None   # list[dict]
        self._model   = None

        if auto_build and not _INDEX_PATH.exists():
            self.build_index()
        elif _INDEX_PATH.exists():
            self._load_index()

    # ── Build ──────────────────────────────────────────────────────────────
    def build_index(self, yaml_path: Path = _YAML_PATH) -> None:
        """Carrega YAML, embeds, salva FAISS index."""
        import numpy as np
        import faiss
        from rag_commons import load_model, normalize

        print('[LayerMatcher] Carregando CONFIG-LAYERS.yaml...')
        raw = _load_yaml(yaml_path)
        canonicals = extract_canonicals(raw)
        print(f'[LayerMatcher] {len(canonicals)} canonical layers encontrados')

        model = load_model()
        texts = [c['text'] for c in canonicals]
        print('[LayerMatcher] Gerando embeddings...')
        vecs  = model.encode(texts, show_progress_bar=False, normalize_embeddings=False)
        vecs  = normalize(vecs.astype('float32'))

        dim   = vecs.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(vecs)

        _INDEX_DIR.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(_INDEX_PATH))
        with open(_META_PATH, 'w', encoding='utf-8') as f:
            json.dump(canonicals, f, ensure_ascii=False, indent=2)

        self._index = index
        self._meta  = canonicals
        self._model = model
        print(f'[LayerMatcher] Índice salvo: {_INDEX_PATH} ({len(canonicals)} vectors)')

    def _load_index(self) -> None:
        """Carrega índice do disco (lazy)."""
        import faiss
        self._index = faiss.read_index(str(_INDEX_PATH))
        with open(_META_PATH, encoding='utf-8') as f:
            self._meta = json.load(f)

    def _ensure_loaded(self) -> None:
        if self._index is None:
            if not _INDEX_PATH.exists():
                self.build_index()
            else:
                self._load_index()
        if self._model is None:
            from rag_commons import load_model
            self._model = load_model()

    # ── Match ──────────────────────────────────────────────────────────────
    def match(
        self,
        layer_name: str,
        elemento:   Optional[str] = None,
        k:          int = 3,
    ) -> MatchResult:
        """
        Faz matching de um layer name para canonical.

        Args:
            layer_name: Layer name do DXF (pode ter encoding corrompido, acentos, etc.)
            elemento:   Filtrar por elemento ('pilar', 'viga', 'laje', 'universal').
                        None = buscar em todos.
            k:          Top-k candidatos a avaliar

        Returns:
            MatchResult com canonical, score e confiança
        """
        import numpy as np
        from rag_commons import normalize as _normalize_vec

        self._ensure_loaded()

        layer_norm = normalize_layer(layer_name)

        # 1. Exact alias check primeiro (determinístico, mais rápido)
        exact = self._exact_match(layer_norm, elemento)
        if exact:
            return exact

        # 2. Semantic search
        query_text = f'{layer_name} | {layer_norm}'
        vec = self._model.encode([query_text], show_progress_bar=False, normalize_embeddings=False)
        vec = _normalize_vec(vec.astype('float32'))

        scores, idxs = self._index.search(vec, k * 2)  # buscar mais, filtrar depois
        scores = scores[0]; idxs = idxs[0]

        best_score = -1.0
        best_meta  = None
        for score, idx in zip(scores, idxs):
            if idx < 0 or idx >= len(self._meta):
                continue
            m = self._meta[idx]
            # Filtrar por elemento se especificado
            if elemento and m['elemento'] not in (elemento, 'universal'):
                continue
            if score > best_score:
                best_score = float(score)
                best_meta  = m
            if len([i for i in idxs[:k] if i >= 0]) >= k:
                break

        if best_meta is None or best_score < THRESH_LOW:
            return MatchResult(
                layer_raw=layer_name, layer_norm=layer_norm,
                canonical=None, elemento=None,
                score=float(best_score) if best_score >= 0 else 0.0,
                confianca='NO_MATCH',
            )

        confianca = self._score_to_confianca(best_score)

        return MatchResult(
            layer_raw=layer_name,
            layer_norm=layer_norm,
            canonical=best_meta['canonical'],
            elemento=best_meta['elemento'],
            score=best_score,
            confianca=confianca,
            description=best_meta.get('description', ''),
            aliases_hint=best_meta.get('aliases', [])[:5],
            robot_uses=best_meta.get('robot_uses', True),
        )

    def match_batch(
        self,
        layer_names: list,
        elemento:    Optional[str] = None,
    ) -> list:
        """Batch matching para lista de layers. Retorna list[MatchResult]."""
        return [self.match(ln, elemento) for ln in layer_names]

    def match_dxf_file(self, layers_in_file: list) -> dict:
        """
        Dado lista de layers de um DXF, retorna mapa {layer_raw: MatchResult}.
        Útil para fingerprint de firma e debug.
        """
        return {ln: self.match(ln) for ln in layers_in_file}

    def suggest_firma(self, layers_in_file: list) -> dict:
        """
        Tenta identificar a família/firma de um arquivo DXF
        com base nos layers encontrados vs canônicos.
        Retorna dict com scores por família.
        """
        results = self.match_batch(layers_in_file)
        matched = [r for r in results if r.matched and r.confianca in ('EXACT', 'HIGH')]

        if not matched:
            return {'familia': 'DESCONHECIDA', 'confianca': 0.0, 'scores': {}}

        # Heurísticas simples de família
        familia_hints = {
            'METHODUS': ['MTH-PILAR', 'MTH-VIGA'],
            'TQS':      ['TQS_COLUMN', 'TQS_BEAM', 'S-COLS', 'S-BEAM'],
        }
        scores = {'BIM': 0, 'TQS': 0, 'METHODUS': 0}
        for r in matched:
            for fam, hints in familia_hints.items():
                if r.canonical in hints or any(h in r.layer_raw.upper() for h in ['MTH-', 'TX_', 'S-COL', 'S-BEAM']):
                    scores[fam] += 1
            # BIM é padrão — tudo que não é TQS/METHODUS
            scores['BIM'] += 0.5

        best_fam = max(scores, key=lambda k: scores[k])
        return {
            'familia':   best_fam,
            'confianca': min(1.0, scores[best_fam] / max(1, len(matched))),
            'n_matched': len(matched),
            'n_total':   len(layers_in_file),
            'scores':    scores,
        }

    # ── Helpers ────────────────────────────────────────────────────────────
    def _exact_match(self, layer_norm: str, elemento: Optional[str]) -> Optional[MatchResult]:
        """Verifica se layer_norm é alias exato (string match)."""
        if self._meta is None:
            return None
        for m in self._meta:
            if elemento and m['elemento'] not in (elemento, 'universal'):
                continue
            # Checar canonical name e aliases
            aliases_norm = [normalize_layer(a) for a in m.get('aliases', [])]
            if layer_norm == normalize_layer(m['canonical']) or layer_norm in aliases_norm:
                return MatchResult(
                    layer_raw=layer_norm,
                    layer_norm=layer_norm,
                    canonical=m['canonical'],
                    elemento=m['elemento'],
                    score=1.0,
                    confianca='EXACT',
                    description=m.get('description', ''),
                    aliases_hint=m.get('aliases', [])[:5],
                    robot_uses=m.get('robot_uses', True),
                )
        return None

    @staticmethod
    def _score_to_confianca(score: float) -> str:
        if score >= THRESH_EXACT:  return 'EXACT'
        if score >= THRESH_HIGH:   return 'HIGH'
        if score >= THRESH_MEDIUM: return 'MEDIUM'
        if score >= THRESH_LOW:    return 'LOW'
        return 'NO_MATCH'

    def stats(self) -> dict:
        """Estatísticas do índice carregado."""
        if self._meta is None:
            return {'loaded': False}
        por_elem = {}
        for m in self._meta:
            e = m['elemento']
            por_elem[e] = por_elem.get(e, 0) + 1
        return {
            'loaded':     True,
            'n_canonicals': len(self._meta),
            'por_elemento': por_elem,
            'index_path': str(_INDEX_PATH),
        }


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RAG Layer Matcher — CAD-ANALYZER')
    parser.add_argument('--build',   action='store_true', help='(Re)construir índice FAISS')
    parser.add_argument('--layer',   help='Layer name para testar matching')
    parser.add_argument('--tipo',    help='Filtrar por elemento (pilar/viga/laje)')
    parser.add_argument('--test',    action='store_true', help='Executar suite de testes')
    parser.add_argument('--stats',   action='store_true', help='Estatísticas do índice')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    matcher = LayerMatcher(auto_build=args.build)

    if args.build:
        matcher.build_index()
        print('Índice reconstruído.')

    if args.stats:
        s = matcher.stats()
        import json as _json
        print(_json.dumps(s, ensure_ascii=False, indent=2))

    if args.layer:
        r = matcher.match(args.layer, elemento=args.tipo)
        print(f'\nResultado:')
        print(f'  Layer raw:   {r.layer_raw}')
        print(f'  Normalizado: {r.layer_norm}')
        print(f'  Canonical:   {r.canonical}')
        print(f'  Elemento:    {r.elemento}')
        print(f'  Score:       {r.score:.4f}')
        print(f'  Confiança:   {r.confianca}')
        print(f'  Descrição:   {r.description}')
        if r.aliases_hint:
            print(f'  Aliases:     {r.aliases_hint}')
        print(f'  Robot uses:  {r.robot_uses}')

    if args.test:
        print('\n=== LayerMatcher — Suite de Testes ===\n')
        casos = [
            # (layer_input,           tipo,    expected_canonical,     min_score)
            ('Painéis',               'pilar', 'PANEL_GEOMETRY',        0.85),
            ('Pain?is',               'pilar', 'PANEL_GEOMETRY',        0.70),
            ('PAINEIS',               'pilar', 'PANEL_GEOMETRY',        0.90),
            ('fundo',                 'viga',  'BEAM_BOTTOM',           0.90),
            ('SARRAFO',               'pilar', 'WOOD_BATTEN',           0.90),
            ('SARR_2.2x7',            'pilar', 'BATTEN_2x7',            0.90),
            ('EST-LAJE-TEXT',         'laje',  'SLAB_TEXT',             0.90),
            ('NOMENCLATURA',          None,    'ELEMENT_LABEL',         0.90),
            ('Vázio',                 'laje',  'VOID_OPENING',          0.80),
            ('CARIMBO',               None,    'TITLE_BLOCK',           0.90),
            ('XYZ_DESCONHECIDO_999',  None,    None,                    0.0),
        ]

        ok = 0; fail = 0
        for layer, tipo, expected, min_score in casos:
            r = matcher.match(layer, elemento=tipo)
            hit = (r.canonical == expected if expected else not r.matched)
            score_ok = r.score >= min_score if expected else True
            status = 'OK' if hit and score_ok else 'FAIL'
            if status == 'OK': ok += 1
            else:              fail += 1
            print(f'  [{status}] "{layer}" → {r.canonical} ({r.confianca}, {r.score:.3f})'
                  f'  expected={expected}')

        print(f'\n  Resultado: {ok}/{ok+fail} OK')
        print(f'  Taxa: {ok/(ok+fail):.1%}')
