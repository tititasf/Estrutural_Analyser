"""Pós-processamento conservador de tabelas a partir da topologia N1."""

from __future__ import annotations


_TRUSTED_DIM_SOURCES = {
    "collinear_short_face_band",
    "face_c_top_multi_segment",
    "face_c_top_multi_segment_dual",
}


def restore_trusted_face_beam_dimensions(tables: dict, pillar: dict) -> int:
    """Restaura seções locais que um normalizador global não pode colapsar.

    Uma mesma identidade de viga pode mudar de seção junto ao pilar. Quando o
    N1 possui evidência posicional explícita por canto, ela vence a heurística
    que tenta uniformizar todas as linhas de mesmo nome.
    """
    faces = tables.get("faces") or {}
    topology = pillar.get("face_beams") or {}
    changed = 0

    def apply(face: str, role: str, payload: dict) -> None:
        nonlocal changed
        if not isinstance(payload, dict):
            return
        if str(payload.get("source") or "") not in _TRUSTED_DIM_SOURCES:
            return
        name = str(payload.get("name") or "").strip()
        corner = str(payload.get("corner") or "").strip().upper()
        dim = str(payload.get("dim") or "").strip()
        if not name or not corner or not dim:
            return
        for row in (faces.get(face) or {}).get(role) or []:
            if (
                str(row.get("nome") or "").strip() == name
                and str(row.get("canto") or "").strip().upper() == corner
                and str(row.get("dim") or "").strip() != dim
            ):
                row["dim"] = dim
                row["raw"] = "trusted_n1_corner_dimension"
                changed += 1

    interior_names = {
        str(row.get("name") or "").strip()
        for bucket in topology.values() if isinstance(bucket, dict)
        for row in (bucket.get("interior") or []) if isinstance(row, dict)
    }
    for face, bucket in topology.items():
        if face not in faces or not isinstance(bucket, dict):
            continue
        for slot in ("passa_esq", "passa_dir"):
            payload = bucket.get(slot)
            if not isinstance(payload, dict):
                continue
            behavior = str(payload.get("behavior") or "").lower()
            name = str(payload.get("name") or "").strip()
            role = (
                "chega"
                if behavior == "para" and face in ("A", "B") and name not in interior_names
                else "passa"
            )
            apply(face, role, payload)
        for payload in bucket.get("para") or []:
            apply(face, "chega", payload)
        for payload in bucket.get("interior") or []:
            apply(face, "interior", payload)
    return changed
