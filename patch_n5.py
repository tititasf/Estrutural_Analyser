import re
from pathlib import Path

file_path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\src\core\n5_assembler.py'
content = Path(file_path).read_text(encoding='utf-8')

new_func = '''def assemble_n5(
    obra_dir: str | Path,
    classe: str,
    item_ids: Iterable[str] | None = None,
    pavimento: str = "",
    row_width: float | None = None,
) -> N5AssemblyResult:
    """Monta um DXF N5 consolidado a partir dos previews N3.

    Suportado agora:
      - LJ e FV: ambos empacotam previews em grade de folhas, respeitando ordem natural dos itens.
    """
    obra_dir = Path(obra_dir)
    classe = classe.upper().strip()
    if classe not in ("LJ", "FV"):
        raise ValueError(f"N5 suporta apenas LJ e FV neste ciclo, recebido: {classe}")

    ids = list(item_ids or [])
    if not ids:
        ids = _discover_item_ids(obra_dir, classe)
    ids = sorted(dict.fromkeys(str(i).strip() for i in ids if str(i).strip()), key=natural_key)

    out_dir = obra_dir / "Fase-6_Execucao_CAD" / "n5"
    out_dir.mkdir(parents=True, exist_ok=True)
    pav_tag = _safe_name(pavimento or "GERAL")
    out_path = out_dir / f"N5_{classe}_{pav_tag}.dxf"
    manifest_path = out_dir / f"N5_{classe}_{pav_tag}.json"

    dst = _new_doc_like()
    items = []

    max_row_w = float(row_width or 3200.0)
    margin = 120.0
    gap_x = 160.0
    gap_y = 190.0
    x_cursor = margin
    y_cursor = -margin
    row_h = 0.0
    for item_id in ids:
        src_path = _find_n3_preview(obra_dir, classe, item_id)
        if not src_path:
            items.append(N5ItemResult(item_id, "", "missing", "preview N3 ausente"))
            continue
        try:
            src_doc = ezdxf.readfile(str(src_path))
            bb = _entity_bbox(src_doc, skip_fv_helpers=True)
            if not bb:
                items.append(N5ItemResult(item_id, str(src_path), "error", "bbox vazio"))
                continue
            min_x, min_y, max_x, max_y = bb
            width = max(max_x - min_x, 1.0)
            height = max(max_y - min_y, 1.0)
            if x_cursor > margin and x_cursor + width > max_row_w:
                x_cursor = margin
                y_cursor -= row_h + gap_y
                row_h = 0.0
            dx = x_cursor - min_x
            dy = y_cursor - max_y
            count = _import_doc_entities(src_doc, dst, dx=dx, dy=dy, skip_fv_helpers=True)
            items.append(
                N5ItemResult(
                    item_id,
                    str(src_path),
                    "ok",
                    f"{count} entidades em x={x_cursor:.0f} y={y_cursor:.0f}",
                )
            )
            x_cursor += width + gap_x
            row_h = max(row_h, height)
        except Exception as exc:
            items.append(N5ItemResult(item_id, str(src_path), "error", str(exc)[:120]))

    dst.saveas(str(out_path))
    import json
    manifest = {
        "classe": classe,
        "obra": obra_dir.name,
        "pavimento": pavimento,
        "output": str(out_path),
        "ok_count": sum(1 for item in items if item.status == "ok"),
        "missing_count": sum(1 for item in items if item.status != "ok"),
        "items": [item.__dict__ for item in items],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return N5AssemblyResult(classe, obra_dir.name, pavimento, out_path, manifest_path, items)
'''

# The regex replaces from 'def assemble_n5' to the end of the file.
new_content = re.sub(r'def assemble_n5\(.*', new_func, content, flags=re.DOTALL)
Path(file_path).write_text(new_content, encoding='utf-8')
print("Patched successfully")
