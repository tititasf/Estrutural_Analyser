"""
niveis_extractor.py — Motor de extração de cotas da Elevação Típica.

Parseia os textos de um DXF de Convenção de Níveis (Elevação Típica) e retorna
uma lista ordenada de entradas com chegada/saida/altura por pavimento.

Semântica de níveis:
  chegada[n] = topo do pav anterior = nível do piso do pav n
  saida[n]   = topo do pav n       = chegada do pav n+1
  altura[n]  = saida[n] - chegada[n]   (por andar em ranges)
"""
from __future__ import annotations
import re
from collections import defaultdict

_PAV_RE        = re.compile(r'(\d+)\s*[oaº°]?\s*PAV\.?', re.IGNORECASE)
_RANGE_RE      = re.compile(
    r'(\d+)\s*[oaº°]?\s*[Aa][Oo]?\s*(\d+)\s*[oaº°]?\s*PAV\.?', re.IGNORECASE
)
_COB_RE        = re.compile(r'^COBERTURA$|^COB\.?$', re.IGNORECASE)
_FUND_RE       = re.compile(r'^FUND\.?$|^FUNDA[CÇ][AÃ]O$', re.IGNORECASE)
_TER_RE        = re.compile(r'^TER\.?$|^T[EÉ]RREO$', re.IGNORECASE)
_COTA_RE       = re.compile(r'^(\d{3,}[.,]\d{1,2})$')
_PAV_NUM_IN_SA = re.compile(r'[-_](\d+)[Pp][Vv]?[-_]')

MAX_FLOOR_HEIGHT = 10.0  # unidade do projeto (ex: metros) — anti-alucinação


# ── helpers públicos ───────────────────────────────────────────────────────────

def derive_nome_pav(pav_num: 'int | None') -> str:
    """Nome legível de pavimento a partir do número canônico."""
    if pav_num is None:   return 'TIPO'
    if pav_num == 9999:   return 'COBERTURA'
    if pav_num == 10000:  return 'ÁTICO'
    if pav_num == 0:      return 'TÉRREO'
    if pav_num == -1:     return 'SUBSOLO'
    if pav_num == -2:     return 'GARAGEM'
    if pav_num == -3:     return 'FUNDAÇÃO'
    return f'{pav_num}° PAV.'


def lajes_by_nivel(laje_list: 'list[dict]') -> str:
    """
    Formata lista de lajes agrupadas por nivel_str, em ordem numérica crescente.

    Saída (uma linha por nível, word-wrap amigável):
      820.98:  L51, L52, L53
      823.78:  L57, L58
    """
    by_nivel: dict[str, list[str]] = defaultdict(list)
    for e in laje_list:
        name  = (e.get('name') or '').strip()
        nivel = (e.get('nivel_str') or '').strip()
        if name:
            by_nivel[nivel].append(name)
    if not by_nivel:
        return '—'

    def _key(k: str) -> float:
        try:
            return float(k.replace(',', '.'))
        except Exception:
            return 0.0

    parts: list[str] = []
    for nivel in sorted(by_nivel.keys(), key=_key):
        prefix = f'{nivel}:' if nivel else '(sem nível):'
        parts.append(f'{prefix}  {", ".join(sorted(by_nivel[nivel]))}')
    return '\n'.join(parts)


def pav_num_from_sa_name(sa_name: str) -> 'int | None':
    """
    Extrai número canônico de pavimento de um nome de arquivo SA.

    Exemplos:
      'TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA' → 13
      'TMC-EST-EX-3000-1PV-R00_R2018_ASCII_ODA' → 1
      'TMC-EST-EX-2000-TER-R01_R2018_ASCII_ODA' → 0   (Térreo)
      'TMC-EST-PE-8000-COB-R03_R2018_ASCII_ODA' → 9999 (Cobertura)
      'TMC-EST-PE-9000-ATC-R02_R2018_ASCII_ODA' → 10000 (Ático)
      'TMC-EST-EX-5000-TIP-R00_R2018_ASCII_ODA' → None  (Tipo)
    """
    m = _PAV_NUM_IN_SA.search(sa_name)
    if m:
        return int(m.group(1))
    if re.search(r'[-_]COB[-_]', sa_name, re.IGNORECASE):
        return 9999
    if re.search(r'[-_]ATC[-_]', sa_name, re.IGNORECASE):
        return 10000
    if re.search(r'[-_]TER[-_]', sa_name, re.IGNORECASE):
        return 0
    for pat, num in [('SUB', -1), ('GAR', -2), ('FUN', -3)]:
        if re.search(rf'[-_]{pat}[-_]', sa_name, re.IGNORECASE):
            return num
    if re.search(r'[-_]TIP[-_]', sa_name, re.IGNORECASE):
        return None
    return None


# ── extração principal ─────────────────────────────────────────────────────────

def _parse_pav_label(raw: str) -> 'tuple[str, int, int] | tuple[None, None, None]':
    """Interpreta um texto como label de pavimento.
    Retorna (key, pav_num_start, pav_num_end) ou (None, None, None)."""
    m_r = _RANGE_RE.search(raw)
    if m_r:
        a, b = int(m_r.group(1)), int(m_r.group(2))
        s, e = min(a, b), max(a, b)
        return f'range_{s:04d}_{e:04d}', s, e
    m_p = _PAV_RE.search(raw)
    if m_p:
        n = int(m_p.group(1))
        return f'pav_{n:04d}', n, n
    if _COB_RE.match(raw):
        return 'cob', 9999, 9999
    if _FUND_RE.match(raw):
        return 'fund', -3, -3
    if _TER_RE.match(raw):
        return 'ter', 0, 0
    return None, None, None


def extract_elevacao_tipica(texts: 'list[dict]') -> 'list[dict]':
    """
    Extrai chegada/saida/altura por pavimento a partir de textos DXF.

    Retorna lista de dicts ordenada por pav_num:
      pav_raw    : str   — texto original do label no DXF
      pav_num    : int   — número canônico do pav (start de ranges)
      pav_num_end: int   — número final (= pav_num para pavs simples)
      is_range   : bool  — True se é bloco de pavimentos (ex: "3o ao 8o PAV")
      is_tipo    : bool  — True para linhas expandidas de um range
      chegada    : str   — cota de chegada (nível do piso deste pav)
      saida      : str   — cota de saída  (topo deste pav = chegada do próximo)
      altura     : str   — saída − chegada por andar
      y_pos      : float — posição Y no DXF (debug)

    Anti-alucinação: altura por andar deve ser 0 < h ≤ MAX_FLOOR_HEIGHT.
    """
    pav_entries: list[tuple[float, float, str, str, int, int]] = []
    cota_list:   list[tuple[float, float, str]] = []

    for t in texts:
        raw = (t.get('text') or '').strip()
        pos = t.get('pos', (0.0, 0.0))
        try:
            y, x = float(pos[1]), float(pos[0])
        except Exception:
            continue

        m_cota = _COTA_RE.match(raw.replace(',', '.'))
        if m_cota:
            try:
                cf = float(raw.replace(',', '.'))
                if 100.0 < cf < 99999.0:
                    cota_list.append((y, x, raw))
                    continue
            except Exception:
                pass

        key, start, end = _parse_pav_label(raw)
        if key is not None:
            pav_entries.append((y, x, raw, key, start, end))

    # Deduplica por chave (guarda menor Y)
    seen: dict[str, tuple[float, float, str, int, int]] = {}
    for y, x, raw, key, start, end in pav_entries:
        if key not in seen or y < seen[key][0]:
            seen[key] = (y, x, raw, start, end)

    sorted_entries = sorted(seen.values(), key=lambda v: v[0])

    # Match pav → cota por proximidade Y (≤ 60 unidades, prefere X menor)
    used_cota: set[int] = set()
    raw_result: list[dict] = []

    for pav_y, _px, pav_raw, pav_start, pav_end in sorted_entries:
        best_idx: 'int | None' = None
        best_dist = float('inf')
        best_x    = float('inf')

        for i, (cy, cx, _cs) in enumerate(cota_list):
            if i in used_cota:
                continue
            dist = abs(cy - pav_y)
            if dist > 60.0:
                continue
            if dist < best_dist or (dist == best_dist and cx < best_x):
                best_dist = dist
                best_x    = cx
                best_idx  = i

        chegada_str = cota_list[best_idx][2] if best_idx is not None else '?'
        if best_idx is not None:
            used_cota.add(best_idx)

        raw_result.append({
            'pav_raw':     pav_raw,
            'pav_num':     pav_start,
            'pav_num_end': pav_end,
            'is_range':    pav_start != pav_end,
            'is_tipo':     False,
            'chegada':     chegada_str,
            'saida':       '?',
            'altura':      '?',
            'y_pos':       pav_y,
        })

    raw_result.sort(key=lambda r: r['pav_num'])

    # Calcula saida/altura com anti-alucinação
    for i in range(len(raw_result) - 1):
        cur = raw_result[i]
        nxt = raw_result[i + 1]
        if cur['chegada'] == '?' or nxt['chegada'] == '?':
            continue
        try:
            c_val    = float(cur['chegada'].replace(',', '.'))
            n_val    = float(nxt['chegada'].replace(',', '.'))
            diff     = n_val - c_val
            range_sz = max(1, cur['pav_num_end'] - cur['pav_num'] + 1)
            alt_por  = diff / range_sz
            if 0 < alt_por <= MAX_FLOOR_HEIGHT:
                cur['saida']  = nxt['chegada']
                cur['altura'] = f'{alt_por:.2f}' if cur['is_range'] else f'{diff:.2f}'
        except Exception:
            pass

    # Expande ranges: uma linha por pavimento (interpolação linear)
    expanded: list[dict] = []
    for entry in raw_result:
        if not entry['is_range']:
            expanded.append(entry)
            continue

        start, end = entry['pav_num'], entry['pav_num_end']
        try:
            c_val = float(entry['chegada'].replace(',', '.'))
            alt   = float(entry['altura'])
            for k, n in enumerate(range(start, end + 1)):
                chegada_k = c_val + k * alt
                saida_k   = chegada_k + alt
                expanded.append({
                    'pav_raw':     entry['pav_raw'],
                    'pav_num':     n,
                    'pav_num_end': n,
                    'is_range':    False,
                    'is_tipo':     True,
                    'chegada':     f'{chegada_k:.2f}',
                    'saida':       f'{saida_k:.2f}',
                    'altura':      entry['altura'],
                    'y_pos':       entry['y_pos'],
                })
        except Exception:
            # Sem cota — expande sem interpolação
            for n in range(start, end + 1):
                row = dict(entry)
                row.update({'pav_num': n, 'pav_num_end': n,
                            'is_range': False, 'is_tipo': True})
                expanded.append(row)

    expanded.sort(key=lambda r: r['pav_num'])
    return expanded


def build_pav_cota_map(
    elevacao_tipica: 'list[dict]',
    sa_pav_names: 'list[str]',
) -> 'dict[str, str]':
    """
    Cruza cotas extraídas com nomes SA.
    Retorna {sa_pav_name: chegada_str}.  Mantido por compatibilidade.
    """
    num_to_chegada: dict[int, str] = {
        e['pav_num']: e['chegada'] for e in elevacao_tipica
    }

    def _resolve(sa: str) -> str:
        n = pav_num_from_sa_name(sa)
        return num_to_chegada.get(n, '?') if n is not None else '?'

    return {sa: _resolve(sa) for sa in sa_pav_names}
