"""Leitura pura de seção extraída do contrato FV, sem traçador/STOG.

Mesmas regras de FundoVigaInterpreter._iter_dimension_texts e
drop_pillar_section_texts; permite publicação isolada do reconhecimento.
"""
import re


def dimension_texts(texts):
    pair_re = re.compile(r"(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)")
    labels = []
    for item in texts:
        if isinstance(item, dict) and re.fullmatch(r"P\d+[A-Za-z]?", str(item.get("text") or "").strip(), re.I):
            try:
                labels.append((float(item["pos"][0]), float(item["pos"][1])))
            except (KeyError, TypeError, ValueError, IndexError):
                continue
    result, seen = [], set()
    for item in texts:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        match = pair_re.search(text)
        pos = item.get("pos")
        if not match or not isinstance(pos, (list, tuple)) or len(pos) < 2:
            continue
        try:
            x, y = float(pos[0]), float(pos[1])
            a, b = (float(v.replace(',', '.')) for v in match.groups())
        except ValueError:
            continue
        if any(abs(lx-x) <= 8 and 5 <= ly-y <= 25 for lx, ly in labels):
            continue
        key = round(x, 1), round(y, 1), text
        if key not in seen:
            seen.add(key)
            result.append({"text": text, "pos": (x, y), "width": min(a, b), "height": max(a, b)})
    return result
