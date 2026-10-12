"""Chamadas explícitas de corte; seção e planta nunca são sobrepostas por nome."""
import re


def inventory_cuts(path, *, source_id):
    import ezdxf
    items = []
    for entity in ezdxf.readfile(str(path)).modelspace():
        if entity.dxftype() not in {"TEXT", "MTEXT"}:
            continue
        raw = entity.dxf.text if entity.dxftype() == "TEXT" else entity.plain_mtext()
        match = re.fullmatch(r"\s*(?:(VER)\s+)?(?:CORTE|SE[CÇ][AÃ]O)\s+(.+?)\s*", raw, re.I)
        if not match:
            continue
        items.append({"item_id": f"{source_id}:cut:{entity.dxf.handle}",
                      "raw_text": raw, "source_id": source_id,
                      "evidence_kind": "plan_call" if match[1] else "section_title",
                      "section_label": re.sub(r"\s+", "", match[2]).upper(),
                      "source_entity_handles": [entity.dxf.handle],
                      "position": list(entity.dxf.insert)[:2],
                      "status": "unlinked", "section_geometry": None,
                      "plan_call": None, "beam_id": None, "slab_ids": [],
                      "alternatives": [], "warnings": ["section_link_not_proven"]})
    return {"status": "partial" if items else "not_available", "items": items,
            "capability": "explicit_labels_only"}
