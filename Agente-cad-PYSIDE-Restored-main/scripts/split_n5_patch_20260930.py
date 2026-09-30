from pathlib import Path
import json

patches = []
def edit(file, old, new):
    p = Path(file)
    text = p.read_text(encoding='utf-8')
    assert text.count(old) == 1, (file, text.count(old), old[:80])
    p.write_text(text.replace(old, new), encoding='utf-8')
    patches.append(dict(file=file, old=old, new=new))

edit('src/core/n5_assembler.py', '    db_path: str | Path | None = None,\n) -> N5AssemblyResult:', '    db_path: str | Path | None = None,\n    pillar_group: str | None = None,\n) -> N5AssemblyResult:')
edit('src/core/n5_assembler.py', '    descoberta_automatica = item_ids is None', '''    if pillar_group is not None:
        pillar_group = pillar_group.upper()
        if classe != "PL" or pillar_group not in {"PARA", "PASSA"}:
            raise ValueError("Grupo N5 de pilares inválido")

    descoberta_automatica = item_ids is None''')
edit('src/core/n5_assembler.py', '    out_path = out_dir / f"N5_{classe}_{pav_tag}_{visual_mode}.dxf"\n    manifest_path = out_dir / f"N5_{classe}_{pav_tag}_{visual_mode}.json"', '''    group_tag = f"_{pillar_group}" if pillar_group else ""
    out_path = out_dir / f"N5_{classe}_{pav_tag}_{visual_mode}{group_tag}.dxf"
    manifest_path = out_path.with_suffix(".json")''')
edit('src/core/n5_assembler.py', '''            src_paths = _find_n3_previews(obra_dir, classe, item_id, pavimento, visual_mode)
            if not src_paths:
                items.append(N5ItemResult(
                    item_id, "", "missing",
                    "conjunto N3 de pilares incompleto ou ausente",
''', '''            src_paths = _find_n3_previews(obra_dir, classe, item_id, pavimento, visual_mode)
            if pillar_group:
                # Cima é universal. Preserva ordem e escala das vistas N3.
                indices = (0, 3, 4) if pillar_group == "PARA" else (0, 1, 2)
                src_paths = [src_paths[i] for i in indices] if len(src_paths) == 5 else []
            if not src_paths:
                items.append(N5ItemResult(
                    item_id, "", "missing",
                    "conjunto N3 de pilares incompleto ou ausente",
''')
edit('src/core/n5_assembler.py', '        "output": str(out_path),', '        "pillar_group": pillar_group,\n        "output": str(out_path),')
edit('portal/app/pipeline_runner.py', '''            db_path=str(settings.sa_db_path), visual_mode=visual_mode,
        )
    except Exception as exc:  # noqa: BLE001 - erro do assembler vira estado de job 'error'
''', '''            db_path=str(settings.sa_db_path), visual_mode=visual_mode,
        )
        pillar_parts = {}
        if classe.upper() == "PL":
            for group in ("PARA", "PASSA"):
                part = assemble_n5(
                    obra_dir, classe, pavimento=pavimento,
                    db_path=str(settings.sa_db_path), visual_mode=visual_mode,
                    pillar_group=group,
                )
                if part.missing_count or not part.ok_count:
                    raise ValueError(f"N5 PL {group}: conjunto incompleto")
                pillar_parts[group] = str(part.output_path)
    except Exception as exc:  # noqa: BLE001 - erro do assembler vira estado de job 'error'
''')
edit('portal/app/pipeline_runner.py', '        "n5_manifest": str(resultado.manifest_path),', '        "n5_manifest": str(resultado.manifest_path),\n        "pillar_parts": pillar_parts,')

file = 'portal/app/routers/jobs_routes.py'
edit(file, '\ndef _n5_pl_tiled_svg(', '''
def _n5_group_path(dxf_path: Path, classe: str, pillar_group: str | None) -> Path:
    if not pillar_group:
        return dxf_path
    if classe.upper() != "PL" or pillar_group not in {"PARA", "PASSA"}:
        raise HTTPException(status_code=422, detail="grupo de pilares inválido")
    path = dxf_path.with_name(f"{dxf_path.stem}_{pillar_group}.dxf")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Rode o N5 para gerar os conjuntos Para e Passa")
    return path


def _n5_pl_tiled_svg(''')
edit(file, '    obra_id: str, pavimento: str, dxf_path: Path, visual_mode: str = "NOVA",\n) -> bytes:', '    obra_id: str, pavimento: str, dxf_path: Path, visual_mode: str = "NOVA",\n    pillar_group: str | None = None,\n) -> bytes:')
edit(file, '            for index in range(5)\n        ] if len(sources) == 5 else [fallback_size] * 5', '            for index in range(3 if pillar_group else 5)\n        ] if len(sources) == (3 if pillar_group else 5) else [fallback_size] * (3 if pillar_group else 5)')
edit(file, '        row_width = label_w + sum(size[0] for size in sizes) + 4 * gap_x', '        row_width = label_w + sum(size[0] for size in sizes) + (len(sizes) - 1) * gap_x')
edit(file, '                f"&amp;v={version}"', '                f"&amp;v={version}"\n                + (f"&amp;pillar_group={pillar_group}" if pillar_group else "")')
for name in ['n5_download', 'n5_foto']:
    p = Path(file); t = p.read_text(encoding='utf-8'); start=t.index('def '+name+'('); end=t.index('\n\n@router',start)
    old=t[start:end]
    new=old.replace('visual_mode: Optional[Literal["NOVA", "INI"]] = None,', 'visual_mode: Optional[Literal["NOVA", "INI"]] = None,\n            pillar_group: Optional[Literal["PARA", "PASSA"]] = None,')
    new=new.replace('    from pathlib import Path as _P\n    if not _P(alvo["dxf_path"]).exists():', '    from pathlib import Path as _P\n    path = _n5_group_path(_P(alvo["dxf_path"]), classe, pillar_group)\n    if not path.exists():')
    new=new.replace('        alvo["dxf_path"], filename=_P(alvo["dxf_path"]).name,', '        path, filename=path.name,')
    new=new.replace('    dxf_path = _P(alvo["dxf_path"])', '    dxf_path = _n5_group_path(_P(alvo["dxf_path"]), classe, pillar_group)')
    new=new.replace('                _n5_release_mode(alvo),', '                _n5_release_mode(alvo), pillar_group,')
    edit(file,old,new)
edit(file, '''                    archive.write(src, arcname=f"{pav}/{src.name}")''', '''                    parts = [_n5_group_path(src, classe, group) for group in ("PARA", "PASSA")] if classe == "PL" else [src]
                    for part in parts:
                        archive.write(part, arcname=f"{pav}/{part.name}")''')
p=Path(file);t=p.read_text(encoding='utf-8');start=t.index('def n5_pl_foto_tile(');old=t[start:]
new=old.replace('    visual_mode: Optional[Literal["NOVA", "INI"]] = None,', '    visual_mode: Optional[Literal["NOVA", "INI"]] = None,\n    pillar_group: Optional[Literal["PARA", "PASSA"]] = None,')
new=new.replace('    if view_index not in range(5):', '    if view_index not in range(3 if pillar_group else 5):')
new=new.replace('    dxf_path = Path(alvo["dxf_path"])', '    dxf_path = _n5_group_path(Path(alvo["dxf_path"]), "PL", pillar_group)')
new=new.replace('    if len(sources) != 5:', '    if len(sources) != (3 if pillar_group else 5):')
edit(file,old,new)

file='portal/app/templates/obra_detalhe.html'
p=Path(file);t=p.read_text(encoding='utf-8');start=t.index('            <div class="zoom-pan-viewport n5-pav-preview"');end=t.index('            {% if aprovado %}',start);old=t[start:end]
new='''            {% if classe == 'PL' %}
            <nav class="n5-pav-tabs" role="tablist" aria-label="Conjuntos de pilares">
              <button type="button" role="tab" data-pillar-group="PARA" aria-selected="true" class="active">Pilares Para</button>
              <button type="button" role="tab" data-pillar-group="PASSA" aria-selected="false">Pilares Passa</button>
            </nav>
            {% endif %}
            {% for group in (['PARA', 'PASSA'] if classe == 'PL' else ['']) %}
            <section data-pillar-panel="{{ group }}" {% if group == 'PASSA' %}hidden{% endif %}>
              {% if group %}<p>Cima · ABCD {{ group|title }} · Grade {{ group|title }}</p>{% endif %}
'''+old.replace('&amp;visual_mode={{ n5_modo_ativo }}','&amp;visual_mode={{ n5_modo_ativo }}{% if group %}&amp;pillar_group={{ group }}{% endif %}').replace('N5 {{ titulo }} · {{ pavimento }}','N5 {{ titulo }} {{ group|title }} · {{ pavimento }}')+'''            </section>
            {% endfor %}
'''
edit(file,old,new)
edit(file, "      if (viewport.dataset.n5SvgSrc) carregarSvgN5(viewport);", "      if (viewport.closest('[hidden]')) return;\n      if (viewport.dataset.n5SvgSrc) carregarSvgN5(viewport);")
edit(file, "    var tabs = Array.from(root.querySelectorAll('[data-n5-tab]'));", '''    root.querySelectorAll('[data-pillar-group]').forEach(function (button) {
      button.addEventListener('click', function () {
        var panel = button.closest('[data-n5-panel]');
        var group = button.dataset.pillarGroup;
        panel.querySelectorAll('[data-pillar-group]').forEach(function (tab) {
          var active = tab.dataset.pillarGroup === group;
          tab.classList.toggle('active', active);
          tab.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        panel.querySelectorAll('[data-pillar-panel]').forEach(function (view) {
          view.hidden = view.dataset.pillarPanel !== group;
        });
        ativarZoomEmContainer(panel);
      });
    });
    var tabs = Array.from(root.querySelectorAll('[data-n5-tab]'));''')
Path('scripts/split_n5_deploy_20260930.json').write_text(json.dumps(patches,ensure_ascii=False),encoding='utf-8')
print(len(patches), 'guarded edits')
